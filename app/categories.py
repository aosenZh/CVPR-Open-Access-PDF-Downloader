import json
import os
import re
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import requests

from .crawler import get_papers_path
from .utils import PROJECT_ROOT, load_json, save_json


CATEGORY_RULES_PATH = PROJECT_ROOT / "data" / "research_categories_keywords.json"
LLM_CATEGORIES_PATH = PROJECT_ROOT / "data" / "research_categories_LLM.json"
OPENAI_API_BASE = "https://api.openai.com/v1"
OPENAI_RETRY_COUNT = 5


def get_categories_path(source_id: str) -> Path:
    return PROJECT_ROOT / "data" / f"papers_{source_id}_with_categories.json"


def candidate_categories_paths(source_id: str) -> List[Path]:
    return [get_categories_path(source_id)]


def existing_categories_path(source_id: str) -> Path:
    for path in candidate_categories_paths(source_id):
        if path.exists():
            return path
    return get_categories_path(source_id)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _keyword_count(text: str, keyword: str) -> int:
    normalized_keyword = _normalize_text(keyword)
    if not normalized_keyword:
        return 0
    if re.fullmatch(r"[a-z0-9]{1,3}", normalized_keyword):
        return len(re.findall(rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])", text))
    return text.count(normalized_keyword)


def _uncategorized_category(rules: List[Dict]) -> Dict:
    for rule in rules:
        if not rule.get("keywords"):
            return {
                "category_id": rule.get("category_id", 0),
                "category": rule.get("category", "其它未分类"),
                "priority": int(rule.get("priority", 0)),
            }
    return {"category_id": 0, "category": "其它未分类", "priority": 0}


def classify_paper_by_keywords(paper: Dict, rules: List[Dict]) -> Dict:
    text = _normalize_text(" ".join(str(paper.get(key, "")) for key in ("title", "abstract", "keywords")))
    best_score = None
    selected = None

    for rule in rules:
        keywords = rule.get("keywords") or []
        match_count = 0
        longest_keyword = 0
        for keyword in keywords:
            count = _keyword_count(text, str(keyword))
            if count <= 0:
                continue
            match_count += count
            longest_keyword = max(longest_keyword, len(_normalize_text(str(keyword))))

        if match_count <= 0:
            continue

        candidate_score = (
            longest_keyword,
            int(rule.get("priority", 0)),
            match_count,
            -int(rule.get("category_id", 0)),
        )
        if best_score is None or candidate_score > best_score:
            best_score = candidate_score
            selected = rule

    selected = selected or _uncategorized_category(rules)
    classified = dict(paper)
    classified["category_id"] = selected.get("category_id", 0)
    classified["category"] = selected.get("category", "其它未分类")
    return classified


def generate_keyword_categories(source_id: str, papers: List[Dict]) -> Tuple[Path, Dict[str, int]]:
    rules = load_json(CATEGORY_RULES_PATH, [])
    if not isinstance(rules, list) or not rules:
        raise ValueError(f"Keyword rules file is missing or invalid: {CATEGORY_RULES_PATH}")

    if not papers:
        papers_path = get_papers_path(source_id)
        papers = load_json(papers_path, [])
    if not isinstance(papers, list) or not papers:
        raise ValueError(f"Paper list is missing or empty for source: {source_id}")

    output = [classify_paper_by_keywords(paper, rules) for paper in papers if isinstance(paper, dict)]
    counts = defaultdict(int)
    for item in output:
        counts[item.get("category", "其它未分类")] += 1

    path = get_categories_path(source_id)
    save_json(path, output)
    return path, dict(counts)


def _chunked(items: List[Dict], size: int) -> List[List[Dict]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def _compact_papers(papers: List[Dict]) -> List[Dict]:
    return [
        {"paper_id": index, "title": str(paper.get("title", ""))}
        for index, paper in enumerate(papers)
        if isinstance(paper, dict)
    ]


def _category_name_map(categories: List[List]) -> Dict[int, str]:
    result = {}
    for item in categories:
        if isinstance(item, list) and len(item) >= 2:
            result[int(item[0])] = str(item[1])
    return result


def _uncategorized_id(categories: List[List]) -> int:
    if categories:
        return int(categories[-1][0])
    return 0


def _openai_headers(api_key: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def _retry_delay(attempt: int) -> int:
    return min(30, 2 ** attempt)


def _request_json(method: str, path: str, api_key: str, **kwargs) -> Dict:
    last_error = None
    for attempt in range(OPENAI_RETRY_COUNT):
        try:
            response = requests.request(
                method,
                f"{OPENAI_API_BASE}{path}",
                headers=_openai_headers(api_key),
                timeout=60,
                **kwargs,
            )
            try:
                payload = response.json()
            except Exception:
                payload = {"error": {"message": response.text}}
            if response.status_code < 400:
                return payload
            message = payload.get("error", {}).get("message", response.text)
            if response.status_code not in {408, 409, 429, 500, 502, 503, 504}:
                raise RuntimeError(f"OpenAI API request failed ({response.status_code}): {message}")
            last_error = RuntimeError(f"OpenAI API request failed ({response.status_code}): {message}")
        except requests.RequestException as exc:
            last_error = exc
        if attempt < OPENAI_RETRY_COUNT - 1:
            time.sleep(_retry_delay(attempt))
    raise RuntimeError(f"OpenAI API request failed after retries: {last_error}")


def _upload_batch_file(path: Path, api_key: str) -> str:
    last_error = None
    for attempt in range(OPENAI_RETRY_COUNT):
        try:
            with path.open("rb") as fh:
                response = requests.post(
                    f"{OPENAI_API_BASE}/files",
                    headers=_openai_headers(api_key),
                    files={"file": (path.name, fh, "application/jsonl")},
                    data={"purpose": "batch"},
                    timeout=120,
                )
            payload = response.json()
            if response.status_code < 400:
                return payload["id"]
            message = payload.get("error", {}).get("message", response.text)
            if response.status_code not in {408, 409, 429, 500, 502, 503, 504}:
                raise RuntimeError(f"OpenAI file upload failed ({response.status_code}): {message}")
            last_error = RuntimeError(f"OpenAI file upload failed ({response.status_code}): {message}")
        except requests.RequestException as exc:
            last_error = exc
        if attempt < OPENAI_RETRY_COUNT - 1:
            time.sleep(_retry_delay(attempt))
    raise RuntimeError(f"OpenAI file upload failed after retries: {last_error}")


def _write_batch_input(path: Path, papers: List[Dict], categories: List[List], model: str, batch_size: int) -> None:
    system_prompt = (
        "Classify each paper into exactly one research category. "
        "Use only the provided compact categories. "
        "Return strict JSON: {\"results\":[{\"paper_id\":0,\"category_id\":16}]}."
    )
    with path.open("w", encoding="utf-8") as fh:
        for group_index, group in enumerate(_chunked(_compact_papers(papers), batch_size)):
            body = {
                "model": model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"categories": categories, "papers": group},
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    },
                ],
            }
            request = {
                "custom_id": f"classify-{group_index:05d}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": body,
            }
            fh.write(json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n")


def _create_batch(input_file_id: str, api_key: str) -> str:
    payload = _request_json(
        "POST",
        "/batches",
        api_key,
        json={
            "input_file_id": input_file_id,
            "endpoint": "/v1/chat/completions",
            "completion_window": "24h",
        },
    )
    return payload["id"]


def _wait_for_batch(
    batch_id: str,
    api_key: str,
    poll_interval: int,
    max_wait_seconds: int,
    status_callback: Optional[Callable[[str], None]],
) -> Dict:
    started = time.time()
    terminal_statuses = {"completed", "failed", "expired", "cancelled"}
    while True:
        payload = _request_json("GET", f"/batches/{batch_id}", api_key)
        status = payload.get("status", "unknown")
        if status_callback:
            status_callback(f"Batch {batch_id}: {status}")
        if status in terminal_statuses:
            return payload
        if time.time() - started > max_wait_seconds:
            raise TimeoutError(f"Timed out waiting for OpenAI batch: {batch_id}")
        time.sleep(max(5, poll_interval))


def _download_file_content(file_id: str, api_key: str) -> str:
    last_error = None
    for attempt in range(OPENAI_RETRY_COUNT):
        try:
            response = requests.get(
                f"{OPENAI_API_BASE}/files/{file_id}/content",
                headers=_openai_headers(api_key),
                timeout=120,
            )
            if response.status_code < 400:
                return response.text
            if response.status_code not in {408, 409, 429, 500, 502, 503, 504}:
                raise RuntimeError(f"OpenAI file download failed ({response.status_code}): {response.text}")
            last_error = RuntimeError(f"OpenAI file download failed ({response.status_code}): {response.text}")
        except requests.RequestException as exc:
            last_error = exc
        if attempt < OPENAI_RETRY_COUNT - 1:
            time.sleep(_retry_delay(attempt))
    raise RuntimeError(f"OpenAI file download failed after retries: {last_error}")


def _parse_model_json(content: str) -> Dict:
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _parse_batch_output(content: str) -> Dict[int, int]:
    assignments: Dict[int, int] = {}
    for line in content.splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("error"):
            raise RuntimeError(f"Batch item failed {item.get('custom_id')}: {item['error']}")
        response = item.get("response", {})
        if response.get("status_code", 200) >= 400:
            raise RuntimeError(f"Batch item failed {item.get('custom_id')}: {response}")
        choices = response.get("body", {}).get("choices", [])
        if not choices:
            continue
        content_json = _parse_model_json(choices[0].get("message", {}).get("content", "{}"))
        for result in content_json.get("results", []):
            assignments[int(result["paper_id"])] = int(result["category_id"])
    return assignments


def generate_api_categories(
    source_id: str,
    papers: List[Dict],
    config: Dict,
    status_callback: Optional[Callable[[str], None]] = None,
) -> Path:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    categories = load_json(LLM_CATEGORIES_PATH, [])
    if not isinstance(categories, list) or not categories:
        raise ValueError(f"LLM categories file is missing or invalid: {LLM_CATEGORIES_PATH}")

    if not papers:
        papers_path = get_papers_path(source_id)
        papers = load_json(papers_path, [])
    if not isinstance(papers, list) or not papers:
        raise ValueError(f"Paper list is missing or empty for source: {source_id}")

    llm_config = config.get("llm_classification", {})
    model = llm_config.get("model", "gpt-4o-mini")
    batch_size = int(llm_config.get("batch_size", 30))
    batch_size = max(20, min(30, batch_size))
    poll_interval = int(llm_config.get("poll_interval_seconds", 60))
    max_wait_seconds = int(llm_config.get("max_wait_seconds", 24 * 60 * 60))

    with tempfile.TemporaryDirectory(prefix="paper_category_batch_") as tmp_dir:
        input_path = Path(tmp_dir) / "batch_input.jsonl"
        _write_batch_input(input_path, papers, categories, model, batch_size)
        if status_callback:
            status_callback("Uploading batch input...")
        input_file_id = _upload_batch_file(input_path, api_key)
        batch_id = _create_batch(input_file_id, api_key)
        batch = _wait_for_batch(batch_id, api_key, poll_interval, max_wait_seconds, status_callback)

        if batch.get("status") != "completed":
            raise RuntimeError(f"OpenAI batch did not complete: {batch}")
        output_file_id = batch.get("output_file_id")
        if not output_file_id:
            raise RuntimeError(f"OpenAI batch completed without output_file_id: {batch}")
        output_content = _download_file_content(output_file_id, api_key)

    assignments = _parse_batch_output(output_content)
    category_names = _category_name_map(categories)
    fallback_id = _uncategorized_id(categories)
    fallback_name = category_names.get(fallback_id, "其它未分类")

    output = []
    for paper_id, paper in enumerate(papers):
        category_id = assignments.get(paper_id, fallback_id)
        output.append(
            {
                "title": paper.get("title", ""),
                "detail_url": paper.get("detail_url", ""),
                "pdf_url": paper.get("pdf_url", ""),
                "category_id": category_id,
                "category": category_names.get(category_id, fallback_name),
            }
        )

    path = get_categories_path(source_id)
    save_json(path, output)
    return path


def generate_api_categories_from_completed_batch(
    source_id: str,
    papers: List[Dict],
    config: Dict,
    batch_id: str,
) -> Path:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    categories = load_json(LLM_CATEGORIES_PATH, [])
    if not isinstance(categories, list) or not categories:
        raise ValueError(f"LLM categories file is missing or invalid: {LLM_CATEGORIES_PATH}")
    if not papers:
        papers_path = get_papers_path(source_id)
        papers = load_json(papers_path, [])
    if not isinstance(papers, list) or not papers:
        raise ValueError(f"Paper list is missing or empty for source: {source_id}")

    batch = _request_json("GET", f"/batches/{batch_id}", api_key)
    if batch.get("status") != "completed":
        raise RuntimeError(f"OpenAI batch is not completed: {batch.get('status')}")
    output_file_id = batch.get("output_file_id")
    if not output_file_id:
        raise RuntimeError(f"OpenAI batch completed without output_file_id: {batch}")

    output_content = _download_file_content(output_file_id, api_key)
    assignments = _parse_batch_output(output_content)
    category_names = _category_name_map(categories)
    fallback_id = _uncategorized_id(categories)
    fallback_name = category_names.get(fallback_id, "其它未分类")

    output = []
    for paper_id, paper in enumerate(papers):
        category_id = assignments.get(paper_id, fallback_id)
        output.append(
            {
                "title": paper.get("title", ""),
                "detail_url": paper.get("detail_url", ""),
                "pdf_url": paper.get("pdf_url", ""),
                "category_id": category_id,
                "category": category_names.get(category_id, fallback_name),
            }
        )

    path = get_categories_path(source_id)
    save_json(path, output)
    return path
