from __future__ import annotations

from pathlib import Path

from openai import OpenAI


class OpenAIUploader:
    def __init__(self, api_key: str, vector_store_id: str) -> None:
        self.client = OpenAI(api_key=api_key)
        self.vector_store_id = vector_store_id

    def upload_and_attach(self, path: Path) -> tuple[str, str]:
        """
        Upload a Markdown file to OpenAI Files API,
        then attach it to the configured Vector Store.
        """
        with path.open("rb") as file_obj:
            uploaded_file = self.client.files.create(
                file=file_obj,
                purpose="assistants",
            )

        vector_store_file = self.client.vector_stores.files.create(
            vector_store_id=self.vector_store_id,
            file_id=uploaded_file.id,
        )

        return uploaded_file.id, vector_store_file.id

    def delete_vector_store_file(self, openai_file_id: str) -> None:
        """
        Best-effort cleanup for stale vector store files.

        Depending on SDK/API version, this may delete the association
        between the file and vector store. If it fails, the pipeline logs
        the error but does not crash.
        """
        self.client.vector_stores.files.delete(
            vector_store_id=self.vector_store_id,
            file_id=openai_file_id,
        )
