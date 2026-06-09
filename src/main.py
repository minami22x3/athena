from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from chunking import estimate_chunk_count
from config import load_config
from logger import log_event, setup_logger
from markdown_utils import article_to_markdown
from openai_uploader import OpenAIUploader
from scraper import fetch_articles
from state_backend import (
    get_article_state,
    get_state_backend,
    save_article_markdown,
    set_article_state,
    sha256_text,
)


def main() -> int:
    logger = setup_logger()
    config = load_config()

    started_at = datetime.now(timezone.utc).isoformat()

    log_event(
        logger,
        "run_started",
        started_at=started_at,
        support_base_url=config.support_base_url,
        max_articles=config.max_articles,
        dry_run=config.dry_run,
    )

    if not config.dry_run:
        if not config.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required unless DRY_RUN=true")
        if not config.openai_vector_store_id:
            raise RuntimeError("OPENAI_VECTOR_STORE_ID is required unless DRY_RUN=true")

    uploader = None
    if not config.dry_run:
        uploader = OpenAIUploader(
            api_key=config.openai_api_key or "",
            vector_store_id=config.openai_vector_store_id or "",
        )

    state_backend = get_state_backend(config.state_path)
    state = state_backend.load()

    log_event(
        logger,
        "state_loaded",
        backend=config.state_backend,
        article_count=len(state.get("articles", {})),
    )

    articles = fetch_articles(
        base_url=config.support_base_url,
        locale=config.zendesk_locale,
        max_articles=config.max_articles,
    )

    added = 0
    updated = 0
    skipped = 0
    failed = 0
    total_estimated_chunks = 0
    uploaded_files = 0

    log_event(logger, "articles_fetched", count=len(articles))

    for article in articles:
        try:
            markdown = article_to_markdown(article)
            content_hash = sha256_text(markdown)
            estimated_chunks = estimate_chunk_count(markdown)
            total_estimated_chunks += estimated_chunks

            previous = get_article_state(state, article.article_id)

            if previous and previous.get("content_hash") == content_hash:
                skipped += 1
                log_event(
                    logger,
                    "article_skipped",
                    article_id=article.article_id,
                    title=article.title,
                    reason="unchanged_hash",
                )
                continue

            markdown_path = save_article_markdown(
                data_dir=config.data_dir,
                article=article,
                markdown=markdown,
            )

            status = "added" if previous is None else "updated"

            old_openai_file_id = previous.get("openai_file_id") if previous else None

            openai_file_id = None
            vector_store_file_id = None

            if config.dry_run:
                openai_file_id = "dry_run_file_id"
                vector_store_file_id = "dry_run_vector_store_file_id"
            else:
                assert uploader is not None

                if (
                    status == "updated"
                    and config.delete_stale_vector_files
                    and old_openai_file_id
                ):
                    try:
                        uploader.delete_vector_store_file(old_openai_file_id)
                        log_event(
                            logger,
                            "stale_vector_file_deleted",
                            article_id=article.article_id,
                            old_openai_file_id=old_openai_file_id,
                        )
                    except Exception as exc:
                        log_event(
                            logger,
                            "stale_vector_file_delete_failed",
                            article_id=article.article_id,
                            old_openai_file_id=old_openai_file_id,
                            error=str(exc),
                        )

                openai_file_id, vector_store_file_id = uploader.upload_and_attach(
                    markdown_path
                )
                uploaded_files += 1

            set_article_state(
                state=state,
                article=article,
                markdown_path=markdown_path,
                content_hash=content_hash,
                openai_file_id=openai_file_id,
                vector_store_file_id=vector_store_file_id,
                estimated_chunks=estimated_chunks,
            )

            if status == "added":
                added += 1
            else:
                updated += 1

            log_event(
                logger,
                f"article_{status}",
                article_id=article.article_id,
                title=article.title,
                markdown_path=str(markdown_path),
                estimated_chunks=estimated_chunks,
                openai_file_id=openai_file_id,
                vector_store_file_id=vector_store_file_id,
            )

        except Exception as exc:
            failed += 1
            log_event(
                logger,
                "article_failed",
                article_id=article.article_id,
                title=article.title,
                error=str(exc),
            )

    completed_at = datetime.now(timezone.utc).isoformat()

    summary = {
        "run_id": uuid4().hex,
        "status": "success" if failed == 0 else "failed",
        "started_at": started_at,
        "completed_at": completed_at,
        "state_backend": config.state_backend,
        "fetched_articles": len(articles),
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
        "uploaded_files": uploaded_files,
        "total_estimated_chunks": total_estimated_chunks,
    }

    state_backend.save(state)
    state_backend.save_last_run(summary)

    log_event(logger, "run_completed", **summary)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
