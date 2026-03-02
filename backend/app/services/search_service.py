import meilisearch
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

class SearchService:
    def __init__(self):
        self._client = None
        self.url = settings.meilisearch_url
        self.api_key = settings.meilisearch_master_key

    @property
    def client(self) -> meilisearch.Client:
        if not self._client:
            try:
                self._client = meilisearch.Client(
                    self.url,
                    self.api_key
                )
                # Verify connection
                self._client.health() 
                logger.info(f"Connected to Meilisearch at {self.url}")
            except Exception as e:
                logger.error(f"Failed to connect to Meilisearch: {e}")
                # We might not want to crash the app, just log error
        return self._client

    def get_index(self, index_name: str):
        """
        Get or create an index.
        """
        if not self.client:
            logger.warning("Meilisearch client not initialized.")
            return None
            
        try:
            # Check if index exists, create if not
            try:
                index = self.client.get_index(index_name)
            except meilisearch.errors.MeilisearchApiError:
               task = self.client.create_index(index_name, {'primaryKey': 'id'})
               self.client.wait_for_task(task['taskUid'])
               index = self.client.get_index(index_name)
            return index
        except Exception as e:
            logger.error(f"Error getting index {index_name}: {e}")
            return None

    def update_settings(self, index_name: str, settings_dict: Dict[str, Any]):
        """
        Update index settings (e.g. for vector search).
        """
        index = self.get_index(index_name)
        if not index:
            return
        
        try:
            task = index.update_settings(settings_dict)
            logger.info(f"Updated settings for index {index_name}: {task} (taskUid: {task['taskUid']})")
            return task
        except Exception as e:
            logger.error(f"Error updating settings for {index_name}: {e}")

    def add_documents(self, index_name: str, documents: List[Dict[str, Any]]):
        """
        Add documents to index.
        """
        index = self.get_index(index_name)
        if not index:
            return

        try:
            task = index.add_documents(documents)
            logger.info(f"Added {len(documents)} documents to {index_name}: {task}")
            return task
        except Exception as e:
            logger.error(f"Error adding documents to {index_name}: {e}")

    def search(self, index_name: str, query: str = "", vector: Optional[List[float]] = None, limit: int = 10, filter: str = None) -> Dict[str, Any]:
        """
        Search in index. Supports full-text and vector search.
        """
        index = self.get_index(index_name)
        if not index:
            return {}

        try:
            search_params = {
                'limit': limit,
            }
            if vector:
                search_params['vector'] = vector
            if filter:
                search_params['filter'] = filter
            
            # If query is empty but vector is provided, Meilisearch handles it if vector search is enabled.
            # Usually vector search requires `vector` param and can be combined with `q` (hybrid) or without (pure vector).
            
            result = index.search(query, search_params)
            return result
        except Exception as e:
            logger.error(f"Error searching {index_name}: {e}")
            return {}

    def perform_hybrid_search(
        self,
        query: str,
        text_vector: Optional[List[float]] = None,
        limit: int = 10,
        semantic_ratio: float = None,
        filter_str: Optional[str] = None,
        ranking_score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Runs text-embedding hybrid search in Meilisearch.
        ranking_score_threshold: if set, only returns hits with _rankingScore >= threshold.
        """
        if semantic_ratio is None:
            semantic_ratio = settings.search_semantic_ratio

        index = self.get_index(settings.meilisearch_index)
        if not index:
            return []

        if not text_vector:
            try:
                fallback_params: dict = {"limit": limit, "showRankingScore": True}
                if filter_str:
                    fallback_params["filter"] = filter_str
                res = index.search(query, fallback_params)
                text_hits = res.get("hits", [])
            except Exception as e:
                logger.error(f"Keyword search failed: {e}")
                text_hits = []
        else:
            params: dict = {
                "hybrid": {"embedder": "text", "semanticRatio": semantic_ratio},
                "vector": text_vector,
                "limit": limit,
                "showRankingScore": True,
            }
            if filter_str:
                params["filter"] = filter_str
            if ranking_score_threshold is not None:
                params["rankingScoreThreshold"] = ranking_score_threshold
            try:
                res = index.search(query, params)
                text_hits = res.get("hits", [])
            except Exception as e:
                logger.error(f"Text embedder search failed: {e}")
                text_hits = []

        # Tag each hit with source metadata (kept for UI badge compatibility)
        for hit in text_hits:
            hit.setdefault("_sources",      ["text"])
            hit.setdefault("_score",        1)
            hit.setdefault("_rankingScore", 0.0)

        if text_hits:
            logger.info("━" * 60)
            logger.info(f"📊 SEARCH RESULTS (Total: {len(text_hits)})")
            for i, hit in enumerate(text_hits[:10]):
                handle        = hit.get("handle", "unknown")
                ranking_score = hit["_rankingScore"]
                logger.info(f"  {i+1:2d}. [rank: {ranking_score:.4f}] {handle}")
            logger.info("━" * 60)

        return text_hits

# Singleton instance
search_service = SearchService()
