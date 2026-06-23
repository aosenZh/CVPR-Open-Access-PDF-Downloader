import re
import random
import time
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from .utils import PROJECT_ROOT, load_json, log_error, save_json


PAPERS_PATH = PROJECT_ROOT / "data" / "papers.json"


def _safe_source_id(source_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", source_id).strip("._")
    return safe or "default"


def get_papers_path(source_id: str = ""):
    if not source_id or source_id == "cvpr2026":
        return PAPERS_PATH
    return PROJECT_ROOT / "data" / f"papers_{_safe_source_id(source_id)}.json"


def get_paper_sources(config: Dict) -> List[Dict]:
    sources = config.get("paper_sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("config.json must define a non-empty paper_sources list.")

    valid_sources = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        missing = [key for key in ("id", "name", "type", "conference_url") if not source.get(key)]
        if missing:
            raise ValueError(f"Invalid paper source config; missing {', '.join(missing)}: {source}")
        valid_sources.append(source)

    if not valid_sources:
        raise ValueError("config.json paper_sources does not contain any valid sources.")
    return valid_sources


def get_paper_source(config: Dict, source_id: str = "") -> Dict:
    sources = get_paper_sources(config)
    default_id = source_id or config.get("default_paper_source") or sources[0]["id"]
    for source in sources:
        if source.get("id") == default_id:
            return source
    raise ValueError(f"Unknown paper source id: {default_id}")


def _merged_source_config(config: Dict, source: Dict) -> Dict:
    merged = dict(config)
    merged.update(source)
    return merged


def polite_sleep(delay_range) -> None:
    time.sleep(random.uniform(float(delay_range[0]), float(delay_range[1])))


def request_with_retries(url: str, config: Dict, stream: bool = False) -> requests.Response:
    headers = {"User-Agent": config.get("user_agent", "CVPR2026Downloader/1.0")}
    max_retries = int(config.get("max_retries", 3))
    last_error: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=30, stream=stream)
            response.raise_for_status()
            return response
        except Exception as exc:
            last_error = exc
            wait = 2 ** attempt
            log_error(f"Request failed ({attempt + 1}/{max_retries}) {url}: {exc}; retry in {wait}s")
            time.sleep(wait)

    raise RuntimeError(f"Request failed after {max_retries} attempts: {url}; last error: {last_error}")


def find_all_papers_url(home_html: str, home_url: str) -> Optional[str]:
    soup = BeautifulSoup(home_html, "html.parser")
    for link in soup.find_all("a"):
        text = " ".join(link.get_text(" ", strip=True).split()).lower()
        href = link.get("href")
        if href and "all papers" in text:
            return urljoin(home_url, href)
    return None


def _is_paper_detail_href(href: str) -> bool:
    return "content/CVPR2026/html/" in href and href.endswith(".html")


def _derived_pdf_url(detail_url: str) -> str:
    return detail_url.replace("/html/", "/papers/").replace(".html", ".pdf")


def _is_pdf_link(link) -> bool:
    href = link.get("href", "")
    label = link.get_text(" ", strip=True).lower()
    return href.lower().endswith(".pdf") or label == "pdf"


def _is_title_row(tag) -> bool:
    if getattr(tag, "name", None) != "dt":
        return False
    return tag.find("a", href=lambda href: bool(href and _is_paper_detail_href(href))) is not None


def _pdf_link_score(link) -> int:
    href = link.get("href", "").lower()
    label = link.get_text(" ", strip=True).lower()
    if not _is_pdf_link(link):
        return -1
    if "/papers/" in href and label == "pdf":
        return 3
    if "/papers/" in href:
        return 2
    if label == "pdf":
        return 1
    return 0


def _find_pdf_url_in_nodes(nodes, all_papers_url: str) -> str:
    candidates = []
    for node in nodes:
        for link in node.find_all("a", href=True):
            score = _pdf_link_score(link)
            if score >= 0:
                candidates.append((score, link["href"]))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: item[0], reverse=True)
    return urljoin(all_papers_url, candidates[0][1])


def _find_nearby_pdf_url(detail_link, all_papers_url: str, detail_url: str) -> str:
    title_row = detail_link.find_parent("dt")
    if title_row:
        nodes = []
        for sibling in title_row.find_next_siblings():
            if _is_title_row(sibling):
                break
            nodes.append(sibling)
        pdf_url = _find_pdf_url_in_nodes(nodes, all_papers_url)
        if pdf_url:
            return pdf_url

    list_item = detail_link.find_parent("li")
    if list_item:
        pdf_url = _find_pdf_url_in_nodes([list_item], all_papers_url)
        if pdf_url:
            return pdf_url

    return _derived_pdf_url(detail_url)


def _parse_paper_from_title_row(title_row, all_papers_url: str) -> Optional[Dict[str, str]]:
    detail_link = title_row.find("a", href=lambda href: bool(href and _is_paper_detail_href(href)))
    if not detail_link:
        return None

    href = detail_link["href"]
    title = detail_link.get_text(" ", strip=True) or title_row.get_text(" ", strip=True)
    detail_url = urljoin(all_papers_url, href)

    nodes = []
    for sibling in title_row.find_next_siblings():
        if _is_title_row(sibling):
            break
        nodes.append(sibling)
    pdf_url = _find_pdf_url_in_nodes(nodes, all_papers_url) or _derived_pdf_url(detail_url)

    return {"title": title, "detail_url": detail_url, "pdf_url": pdf_url}


def parse_cvf_papers(all_papers_html: str, all_papers_url: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
    soup = BeautifulSoup(all_papers_html, "html.parser")
    papers: List[Dict[str, str]] = []
    seen = set()

    for title_row in soup.find_all("dt"):
        paper = _parse_paper_from_title_row(title_row, all_papers_url)
        if not paper:
            continue
        if paper["detail_url"] in seen:
            continue
        seen.add(paper["detail_url"])
        papers.append(paper)
        if limit and len(papers) >= limit:
            return papers

    if papers:
        return papers

    for detail_link in soup.find_all("a", href=True):
        href = detail_link["href"]
        if not _is_paper_detail_href(href):
            continue

        title = detail_link.get_text(" ", strip=True)
        if not title:
            parent = detail_link.find_parent()
            title = parent.get_text(" ", strip=True) if parent else ""

        detail_url = urljoin(all_papers_url, href)
        pdf_url = _find_nearby_pdf_url(detail_link, all_papers_url, detail_url)

        if detail_url in seen:
            continue
        seen.add(detail_url)
        papers.append({"title": title, "detail_url": detail_url, "pdf_url": pdf_url})
        if limit and len(papers) >= limit:
            break

    return papers


def parse_papers(all_papers_html: str, all_papers_url: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
    return parse_cvf_papers(all_papers_html, all_papers_url, limit)


def _is_pmlr_detail_href(href: str) -> bool:
    return "proceedings.mlr.press/" in href and href.endswith(".html")


def _derive_pmlr_pdf_url(detail_url: str) -> str:
    parsed = urlparse(detail_url)
    volume = parsed.path.strip("/").split("/", 1)[0]
    base = detail_url.rsplit("/", 1)[-1].removesuffix(".html")
    return f"https://raw.githubusercontent.com/mlresearch/{volume}/main/assets/{base}/{base}.pdf"


def _parse_dblp_title(entry) -> str:
    title_node = entry.select_one("span.title")
    if title_node:
        return title_node.get_text(" ", strip=True).rstrip(".")

    cite = entry.select_one("cite.data")
    if cite:
        text = cite.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        return text.rstrip(".")

    return ""


def parse_dblp_pmlr_papers(dblp_html: str, dblp_url: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
    soup = BeautifulSoup(dblp_html, "html.parser")
    papers: List[Dict[str, str]] = []
    seen = set()

    entries = soup.select("li.entry.inproceedings")
    if not entries:
        entries = soup.select("li.entry")

    for entry in entries:
        detail_link = entry.select_one('div.head a[href*="proceedings.mlr.press/"][href$=".html"]')
        if not detail_link:
            detail_link = entry.find("a", href=lambda href: bool(href and _is_pmlr_detail_href(href)))
        if not detail_link:
            continue

        detail_url = urljoin(dblp_url, detail_link["href"])
        if detail_url in seen:
            continue

        title = _parse_dblp_title(entry)
        if not title:
            title = detail_link.get_text(" ", strip=True) or detail_url.rsplit("/", 1)[-1].removesuffix(".html")

        seen.add(detail_url)
        papers.append(
            {
                "title": title,
                "detail_url": detail_url,
                "pdf_url": _derive_pmlr_pdf_url(detail_url),
            }
        )
        if limit and len(papers) >= limit:
            break

    return papers


def _is_openreview_forum_href(href: str) -> bool:
    parsed = urlparse(href)
    return parsed.netloc.endswith("openreview.net") and parsed.path == "/forum" and bool(parse_qs(parsed.query).get("id"))


def _derive_openreview_pdf_url(detail_url: str) -> str:
    parsed = urlparse(detail_url)
    paper_id = parse_qs(parsed.query).get("id", [""])[0]
    return urlunparse((parsed.scheme or "https", parsed.netloc or "openreview.net", "/pdf", "", urlencode({"id": paper_id}), ""))


def parse_dblp_openreview_papers(dblp_html: str, dblp_url: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
    soup = BeautifulSoup(dblp_html, "html.parser")
    papers: List[Dict[str, str]] = []
    seen = set()

    entries = soup.select("li.entry.inproceedings")
    if not entries:
        entries = soup.select("li.entry")

    for entry in entries:
        detail_link = entry.select_one('div.head a[href*="openreview.net/forum?id="]')
        if not detail_link:
            detail_link = entry.find("a", href=lambda href: bool(href and _is_openreview_forum_href(href)))
        if not detail_link:
            continue

        detail_url = urljoin(dblp_url, detail_link["href"])
        if detail_url in seen:
            continue

        title = _parse_dblp_title(entry)
        if not title:
            title = detail_link.get_text(" ", strip=True) or parse_qs(urlparse(detail_url).query).get("id", ["paper"])[0]

        seen.add(detail_url)
        papers.append(
            {
                "title": title,
                "detail_url": detail_url,
                "pdf_url": _derive_openreview_pdf_url(detail_url),
            }
        )
        if limit and len(papers) >= limit:
            break

    return papers


def _validate_pdf_urls(papers: List[Dict[str, str]]) -> None:
    if len(papers) < 2:
        return
    pdf_urls = [paper.get("pdf_url", "") for paper in papers if paper.get("pdf_url")]
    unique_count = len(set(pdf_urls))
    if unique_count <= 1:
        raise RuntimeError("Parsed PDF URLs are all identical; refusing to cache likely-bad paper data.")


def _repair_cvf_pdf_urls_from_detail(papers: List[Dict[str, str]]) -> int:
    changed = 0
    for paper in papers:
        detail_url = paper.get("detail_url", "")
        if "/html/" not in detail_url or not detail_url.endswith(".html"):
            continue
        repaired_pdf_url = _derived_pdf_url(detail_url)
        if paper.get("pdf_url") != repaired_pdf_url:
            paper["pdf_url"] = repaired_pdf_url
            changed += 1
    return changed


def _repair_pdf_urls_from_detail(papers: List[Dict[str, str]]) -> int:
    return _repair_cvf_pdf_urls_from_detail(papers)


def _repair_pmlr_pdf_urls_from_detail(papers: List[Dict[str, str]]) -> int:
    changed = 0
    for paper in papers:
        detail_url = paper.get("detail_url", "")
        if not _is_pmlr_detail_href(detail_url):
            continue
        repaired_pdf_url = _derive_pmlr_pdf_url(detail_url)
        if paper.get("pdf_url") != repaired_pdf_url:
            paper["pdf_url"] = repaired_pdf_url
            changed += 1
    return changed


def _repair_openreview_pdf_urls_from_detail(papers: List[Dict[str, str]]) -> int:
    changed = 0
    for paper in papers:
        detail_url = paper.get("detail_url", "")
        if not _is_openreview_forum_href(detail_url):
            continue
        repaired_pdf_url = _derive_openreview_pdf_url(detail_url)
        if paper.get("pdf_url") != repaired_pdf_url:
            paper["pdf_url"] = repaired_pdf_url
            changed += 1
    return changed


def _has_bad_duplicate_pdf_urls(papers: List[Dict[str, str]]) -> bool:
    if len(papers) < 2:
        return False
    pdf_urls = [paper.get("pdf_url", "") for paper in papers if paper.get("pdf_url")]
    return len(pdf_urls) >= 2 and len(set(pdf_urls)) <= 1


def _parse_limit(config: Dict) -> Optional[int]:
    parse_limit = config.get("paper_parse_limit")
    if parse_limit is not None:
        parse_limit = int(parse_limit)
        if parse_limit <= 0:
            parse_limit = None
    return parse_limit


def _initialize_cvf_papers(config: Dict, force: bool, papers_path) -> List[Dict[str, str]]:
    if papers_path.exists() and not force:
        cached = load_json(papers_path, [])
        if cached:
            if _has_bad_duplicate_pdf_urls(cached):
                changed = _repair_cvf_pdf_urls_from_detail(cached)
                if changed:
                    log_error(f"Repaired {changed} duplicate cached PDF URLs from detail_url.")
                    save_json(papers_path, cached)
                _validate_pdf_urls(cached)
            return cached

    home_url = config["conference_url"]
    delay_range = config.get("request_delay_seconds", [2, 6])

    home_response = request_with_retries(home_url, config)
    polite_sleep(delay_range)
    all_papers_url = find_all_papers_url(home_response.text, home_url)

    candidate_urls = []
    if all_papers_url:
        candidate_urls.append(all_papers_url)
    candidate_urls.extend(config.get("fallback_all_papers_urls", []))

    errors = []
    for url in candidate_urls:
        try:
            response = request_with_retries(url, config)
            polite_sleep(delay_range)
            papers = parse_cvf_papers(response.text, url, limit=_parse_limit(config))
            if papers:
                _repair_cvf_pdf_urls_from_detail(papers)
                _validate_pdf_urls(papers)
                save_json(papers_path, papers)
                return papers
            errors.append(f"No papers parsed from {url}")
        except Exception as exc:
            errors.append(f"{url}: {exc}")
            log_error(errors[-1])

    raise RuntimeError("Could not initialize paper list. " + " | ".join(errors))


def _initialize_dblp_pmlr_papers(config: Dict, force: bool, papers_path) -> List[Dict[str, str]]:
    if papers_path.exists() and not force:
        cached = load_json(papers_path, [])
        if cached:
            changed = _repair_pmlr_pdf_urls_from_detail(cached)
            if changed:
                log_error(f"Repaired {changed} cached PMLR PDF URLs from detail_url.")
                save_json(papers_path, cached)
            if _has_bad_duplicate_pdf_urls(cached):
                _validate_pdf_urls(cached)
            return cached

    conference_url = config["conference_url"]
    delay_range = config.get("request_delay_seconds", [2, 6])
    response = request_with_retries(conference_url, config)
    polite_sleep(delay_range)
    papers = parse_dblp_pmlr_papers(response.text, conference_url, limit=_parse_limit(config))
    if not papers:
        raise RuntimeError(f"Could not initialize paper list. No papers parsed from {conference_url}")
    _repair_pmlr_pdf_urls_from_detail(papers)
    _validate_pdf_urls(papers)
    save_json(papers_path, papers)
    return papers


def _initialize_dblp_openreview_papers(config: Dict, force: bool, papers_path) -> List[Dict[str, str]]:
    if papers_path.exists() and not force:
        cached = load_json(papers_path, [])
        if cached:
            changed = _repair_openreview_pdf_urls_from_detail(cached)
            if changed:
                log_error(f"Repaired {changed} cached OpenReview PDF URLs from detail_url.")
                save_json(papers_path, cached)
            if _has_bad_duplicate_pdf_urls(cached):
                _validate_pdf_urls(cached)
            return cached

    conference_url = config["conference_url"]
    delay_range = config.get("request_delay_seconds", [2, 6])
    response = request_with_retries(conference_url, config)
    polite_sleep(delay_range)
    papers = parse_dblp_openreview_papers(response.text, conference_url, limit=_parse_limit(config))
    if not papers:
        raise RuntimeError(f"Could not initialize paper list. No papers parsed from {conference_url}")
    _repair_openreview_pdf_urls_from_detail(papers)
    _validate_pdf_urls(papers)
    save_json(papers_path, papers)
    return papers


def initialize_papers(config: Dict, force: bool = False, source_id: str = "") -> List[Dict[str, str]]:
    source = get_paper_source(config, source_id)
    source_config = _merged_source_config(config, source)
    papers_path = get_papers_path(source.get("id", ""))
    source_type = source_config["type"]

    if source_type == "cvf_openaccess":
        return _initialize_cvf_papers(source_config, force, papers_path)
    if source_type == "dblp_pmlr":
        return _initialize_dblp_pmlr_papers(source_config, force, papers_path)
    if source_type == "dblp_openreview":
        return _initialize_dblp_openreview_papers(source_config, force, papers_path)

    raise ValueError(f"Unsupported paper source type: {source_type}")
