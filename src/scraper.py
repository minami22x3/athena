from __future__ import annotations

import requests

from models import Article


class ScraperError(RuntimeError):
    pass


def _get_json(url: str, timeout: int = 30) -> dict:
    response = requests.get(
        url,
        timeout=timeout,
        headers={
            "Accept": "application/json",
            "User-Agent": "athena/0.1.0",
        },
    )

    if response.status_code >= 400:
        raise ScraperError(
            f"GET {url} failed with {response.status_code}: {response.text[:300]}"
        )

    return response.json()


def fetch_articles(
    base_url: str,
    locale: str = "en-us",
    max_articles: int = 50,
) -> list[Article]:
    """
    Fetch public Zendesk Help Center articles.

    Primary endpoint:
      /api/v2/help_center/{locale}/articles.json

    Fallback endpoint:
      /api/v2/help_center/articles.json
    """
    urls_to_try = [
        f"{base_url}/api/v2/help_center/{locale}/articles.json?sort_order=desc",
        f"{base_url}/api/v2/help_center/articles.json?sort_order=desc",
    ]

    last_error: Exception | None = None

    for start_url in urls_to_try:
        try:
            return _fetch_paginated_articles(start_url, max_articles=max_articles)
        except Exception as exc:
            last_error = exc

    raise ScraperError(f"Could not fetch articles. Last error: {last_error}")


def _fetch_paginated_articles(start_url: str, max_articles: int) -> list[Article]:
    articles: list[Article] = []
    next_page: str | None = start_url

    while next_page and len(articles) < max_articles:
        payload = _get_json(next_page)

        for raw in payload.get("articles", []):
            if len(articles) >= max_articles:
                break

            if raw.get("draft") is True:
                continue

            body = raw.get("body") or ""
            title = raw.get("title") or ""
            html_url = raw.get("html_url") or ""

            if not title or not body or not html_url:
                continue

            articles.append(
                Article(
                    article_id=str(raw["id"]),
                    title=title.strip(),
                    html_url=html_url.strip(),
                    body_html=body,
                    updated_at=raw.get("updated_at") or "",
                    locale=raw.get("locale"),
                )
            )

        next_page = payload.get("next_page")

    return articles
