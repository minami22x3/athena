# Athena — OptiBot Mini-Clone

A backend ingestion pipeline for an OptiBot Mini-Clone. It fetches public OptiSigns support articles, converts them into
clean Markdown files, uploads changed documents to an OpenAI Vector Store via API, and runs as a scheduled daily sync
job on DigitalOcean Platform.

## Features

- Fetches articles from `support.optisigns.com`
- Converts HTML to clean Markdown
- Detects added, updated, and unchanged articles using SHA256 hashes
- Uploads only changed files to an OpenAI Vector Store
- Logs sync results (`added`, `updated`, `skipped`, `failed`, `uploaded_files`, `total_estimated_chunks`)

## Setup

```bash
cp .env.sample .env
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Required environment variables:

```env
OPENAI_API_KEY=
OPENAI_VECTOR_STORE_ID=

SUPPORT_BASE_URL=https://support.optisigns.com
ZENDESK_LOCALE=en-us
MAX_ARTICLES=35

DATA_DIR=data/articles
STATE_PATH=data/state.json
DRY_RUN=false
DELETE_STALE_VECTOR_FILES=true
```

## Run locally

Run the full sync pipeline:

```bash
python src/main.py
```

Run without calling OpenAI API:

```bash
DRY_RUN=true python src/main.py
```

## Run with Docker:

```bash
docker build -t athena .
docker run --env-file .env athena
```

## Delta detection

Each article is converted into Markdown and hashed using SHA256. The sync state stores the article ID, title, URL,
updated timestamp, content hash, local Markdown path, OpenAI file ID, and Vector Store file ID. On each run:

* New article → `added`
* Changed hash → `updated`
* Unchanged hash → `skipped`

This avoids re-uploading identical documents.

## Chunking strategy

Each support article is stored as a single Markdown file with metadata (including `Article URL`) so the assistant can
cite the original source. OpenAI Vector Store built-in chunking is used for retrieval.

## Daily job

The scraper-uploader is deployed as a scheduled DigitalOcean App Platform job and runs once per day.

Latest job logs: `TBU`

## Playground validation

Question used for validation:

```txt
How do I add a YouTube video?
```

The assistant answered using the uploaded documentation and included the corresponding `Article URL` citation.

![screenshots/playground_answer.png](screenshots/playground_answer.png)

