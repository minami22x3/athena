from dataclasses import dataclass


@dataclass(frozen=True)
class Article:
    article_id: str
    title: str
    html_url: str
    body_html: str
    updated_at: str
    locale: str | None = None
