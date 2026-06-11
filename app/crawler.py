import random
import time
from pathlib import Path
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


def parse_papers(all_papers_html: str, all_papers_url: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
    soup = BeautifulSoup(all_papers_html, "html.parser")
    papers: List[Dict[str, str]] = []
    seen = set()

    for detail_link in soup.find_all("a", href=True):
        href = detail_link["href"]
        if not _is_paper_detail_href(href):
            continue

        title = detail_link.get_text(" ", strip=True)
        if not title:
            parent = detail_link.find_parent()
            title = parent.get_text(" ", strip=True) if parent else ""

        detail_url = urljoin(all_papers_url, href)
        container = detail_link.find_parent(["dl", "li", "div"]) or detail_link.find_parent()
        pdf_url = ""
        search_scope = container.find_all("a", href=True) if container else []
        for link in search_scope:
            pdf_href = link["href"]
            label = link.get_text(" ", strip=True).lower()
            if pdf_href.lower().endswith(".pdf") or label == "pdf":
                pdf_url = urljoin(all_papers_url, pdf_href)
                break

        if not pdf_url:
            pdf_url = detail_url.replace("/html/", "/papers/").replace(".html", ".pdf")

        if detail_url in seen:
            continue
        seen.add(detail_url)
        papers.append({"title": title, "detail_url": detail_url, "pdf_url": pdf_url})
        if limit and len(papers) >= limit:
            break

    return papers


def initialize_papers(config: Dict, force: bool = False) -> List[Dict[str, str]]:
    if PAPERS_PATH.exists() and not force:
        cached = load_json(PAPERS_PATH, [])
        if cached:
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
                save_json(PAPERS_PATH, papers)
                return papers
            errors.append(f"No papers parsed from {url}")
        except Exception as exc:
            errors.append(f"{url}: {exc}")
            log_error(errors[-1])

    raise RuntimeError("Could not initialize paper list. " + " | ".join(errors))
