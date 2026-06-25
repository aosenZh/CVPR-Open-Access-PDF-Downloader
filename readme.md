# Conference Paper PDF Downloader

A local Tkinter desktop tool for browsing, classifying, and downloading conference papers from configurable sources such as CVPR, ICML, and ICLR.

The app crawls a selected paper source, caches paper metadata locally, supports manual and automatic categorization, and downloads PDFs into category folders with conservative request delays.

## Supported Sources

Sources are configured in `config.json` under `paper_sources`.

Current source types:

- `cvf_openaccess`: CVF Open Access pages, currently used for CVPR 2026.
- `dblp_pmlr`: DBLP conference pages whose paper links point to PMLR pages, currently used for ICML 2024 and ICML 2025.
- `dblp_openreview`: DBLP conference pages whose paper links point to OpenReview forum pages, currently used for ICLR 2024 and ICLR 2025.

## How It Works

1. Choose a paper source in the GUI.
2. On startup or source switch, the app loads the selected source's local cache if it exists. It does not automatically crawl the web.
3. Click **Reinitialize Paper List**/**重新初始化论文列表** to crawl or rebuild the selected source's cache.
4. Browse papers, skip papers, open detail/PDF links, or download one paper into the selected category.
5. Click **Auto Classify**/**自动分类** to load or create a source-specific category file, then download papers automatically.
6. Progress, skipped items, records, language, selected source, and download root are saved in `data/state.json`.

## Installation

Python 3.9+ is recommended.

Windows

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

macOS / Linux

```powershell
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Quick Start

```powershell
python main.py
```

### Reinitializing Paper Lists

Click **Reinitialize Paper List**/**重新初始化论文列表** after selecting a source. The app then crawls the source page, parses `title`, `detail_url`, and `pdf_url`, which are saved as `data/papers_<source_id>.json` (Example: `data/papers_example.json`)

### Automatic Classification

Click **Auto Classify**/**自动分类** after a paper list is loaded.

The app first looks for the selected source's category JSON. If it exists, auto downloading starts immediately.

If the category file is missing, the app offers three choices.

- Keyword Rules

Uses `data/research_categories_keywords.json` to generate `data/papers_<source_id>_with_categories.json`.

- API Classification

Uses OpenAI Batch API and `data/research_categories_LLM.json` to generate `data/papers_<source_id>_with_categories.json`.

Before using it, set:

```powershell
$env:OPENAI_API_KEY="your_api_key"
python main.py
```

- Manual Classification

Choose manual classification if you want to upload the source paper cache to an AI tool yourself.

Save the categorized JSON as:

```text
data/papers_<source_id>_with_categories.json
```

Then click **Auto Classify** again.

## Configuration

Settings live in `config.json`.

```json
{
  "default_paper_source": "cvpr2026",
  "paper_sources": [
    {
      "id": "cvpr2026",
      "name": "CVPR 2026",
      "type": "cvf_openaccess",
      "conference_url": "https://openaccess.thecvf.com/CVPR2026",
      "fallback_all_papers_urls": [
        "https://openaccess.thecvf.com/CVPR2026?day=all"
      ]
    },
    {
      "id": "icml2025",
      "name": "ICML 2025",
      "type": "dblp_pmlr",
      "conference_url": "https://dblp.uni-trier.de/db/conf/icml/icml2025.html"
    },
    {
      "id": "iclr2025",
      "name": "ICLR 2025",
      "type": "dblp_openreview",
      "conference_url": "https://dblp.uni-trier.de/db/conf/iclr/iclr2025.html"
    }
  ],
  "paper_parse_limit": 0,
  "llm_classification": {
    "model": "gpt-4o-mini",
    "batch_size": 20,
    "poll_interval_seconds": 60,
    "max_wait_seconds": 86400
  },
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CVPR2026Downloader/1.0",
  "request_delay_seconds": [2, 6],
  "post_download_delay_seconds": [3, 8],
  "max_retries": 3
}
```

Notes:

- Each source must define `id`, `name`, `type`, and `conference_url`.
- `paper_parse_limit: 0` means parse all available papers.
- For quick tests, set `paper_parse_limit` to a small number such as `10`.
- `llm_classification.batch_size` is clamped to 20-30 papers per Batch request group.

## Responsible Use

This is an unofficial personal research organization tool. It is not affiliated with CVF, DBLP, PMLR or any conference organizer.

Use conservative request rates. Do not use the tool for aggressive crawling, mirroring, redistribution, or behavior that may violate website terms or copyright requirements.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.