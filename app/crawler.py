import random
import time
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .utils import PROJECT_ROOT, load_json, log_error, save_json


PAPERS_PATH = PROJECT_ROOT / "data" / "papers.json"


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


def parse_papers(all_papers_html: str, all_papers_url: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
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


def _validate_pdf_urls(papers: List[Dict[str, str]]) -> None:
    if len(papers) < 2:
        return
    pdf_urls = [paper.get("pdf_url", "") for paper in papers if paper.get("pdf_url")]
    unique_count = len(set(pdf_urls))
    if unique_count <= 1:
        raise RuntimeError("Parsed PDF URLs are all identical; refusing to cache likely-bad paper data.")


def _repair_pdf_urls_from_detail(papers: List[Dict[str, str]]) -> int:
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


def _has_bad_duplicate_pdf_urls(papers: List[Dict[str, str]]) -> bool:
    if len(papers) < 2:
        return False
    pdf_urls = [paper.get("pdf_url", "") for paper in papers if paper.get("pdf_url")]
    return len(pdf_urls) >= 2 and len(set(pdf_urls)) <= 1


def initialize_papers(config: Dict, force: bool = False) -> List[Dict[str, str]]:
    if PAPERS_PATH.exists() and not force:
        cached = load_json(PAPERS_PATH, [])
        if cached:
            if _has_bad_duplicate_pdf_urls(cached):
                changed = _repair_pdf_urls_from_detail(cached)
                if changed:
                    log_error(f"Repaired {changed} duplicate cached PDF URLs from detail_url.")
                    save_json(PAPERS_PATH, cached)
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
            parse_limit = config.get("paper_parse_limit")
            if parse_limit is not None:
                parse_limit = int(parse_limit)
                if parse_limit <= 0:
                    parse_limit = None
            papers = parse_papers(response.text, url, limit=parse_limit)
            if papers:
                _repair_pdf_urls_from_detail(papers)
                _validate_pdf_urls(papers)
                save_json(PAPERS_PATH, papers)
                return papers
            errors.append(f"No papers parsed from {url}")
        except Exception as exc:
            errors.append(f"{url}: {exc}")
            log_error(errors[-1])

    raise RuntimeError("Could not initialize paper list. " + " | ".join(errors))
