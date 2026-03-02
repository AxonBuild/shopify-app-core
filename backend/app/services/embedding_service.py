
import logging
from typing import List, Union

from openai import OpenAI

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """
    Text-only embedding service using OpenAI text-embedding-3-small (1536-dim).
    SigLIP / image embeddings have been intentionally removed.
    """

    def embed_text(self, text: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """
        Generate semantic text embeddings using OpenAI.
        Accepts a single string or a list of strings (batch mode).
        """
        try:
            client = OpenAI(api_key=settings.openai_api_key)

            is_single = isinstance(text, str)
            inputs    = [text] if is_single else text

            response   = client.embeddings.create(input=inputs, model="text-embedding-3-small")
            embeddings = [data.embedding for data in response.data]
            return embeddings[0] if is_single else embeddings

        except Exception as e:
            logger.error(f"Error embedding text with OpenAI: {e}")
            raise e


# Singleton instance
embedding_service = EmbeddingService()
