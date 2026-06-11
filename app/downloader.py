import random
import time
from pathlib import Path
from typing import Dict

from .crawler import request_with_retries
from .utils import clean_filename, log_error


def download_pdf(paper: Dict[str, str], target_dir: Path, config: Dict, overwrite: bool = False) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = clean_filename(paper.get("title", "paper")) + ".pdf"
    final_path = target_dir / filename
    part_path = target_dir / (filename + ".part")

    if final_path.exists() and not overwrite:
        raise FileExistsError(final_path)

    try:
        response = request_with_retries(paper["pdf_url"], config, stream=True)
        with part_path.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 128):
                if chunk:
                    fh.write(chunk)
        part_path.replace(final_path)
        delay = config.get("post_download_delay_seconds", [3, 8])
        time.sleep(random.uniform(float(delay[0]), float(delay[1])))
        return final_path
    except Exception as exc:
        log_error(f"Download failed {paper.get('pdf_url')}: {exc}")
        if part_path.exists():
            try:
                part_path.unlink()
            except Exception as cleanup_exc:
                log_error(f"Could not remove temp file {part_path}: {cleanup_exc}")
        raise
