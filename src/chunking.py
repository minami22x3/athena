def estimate_chunk_count(
    markdown: str, chunk_size_chars: int = 3500, overlap_chars: int = 300
) -> int:
    """
    Estimate chunks for logging purposes.

    Actual vector-store chunking is handled by OpenAI.
    This estimate helps show ingestion volume in job logs.
    """
    text = markdown.strip()
    if not text:
        return 0

    if len(text) <= chunk_size_chars:
        return 1

    effective = max(1, chunk_size_chars - overlap_chars)
    return 1 + max(0, (len(text) - chunk_size_chars + effective - 1) // effective)
