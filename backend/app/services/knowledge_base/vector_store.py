"""
Vector Store Service

Provides unified interface for vector databases (Pinecone, Qdrant, Local).
Handles embedding storage, retrieval, and similarity search.
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import uuid
import numpy as np

logger = logging.getLogger(__name__)


class VectorStore(ABC):
    """
    Abstract base class for vector stores.
    Implement this interface for different vector database providers.
    """

    @abstractmethod
    async def create_index(self, index_name: str, dimension: int, **kwargs) -> bool:
        """Create a new vector index."""
        pass

    @abstractmethod
    async def delete_index(self, index_name: str) -> bool:
        """Delete a vector index."""
        pass

    @abstractmethod
    async def upsert_vectors(
        self,
        index_name: str,
        vectors: List[Tuple[str, List[float], Dict[str, Any]]]
    ) -> bool:
        """
        Insert or update vectors.

        Args:
            index_name: Name of the index
            vectors: List of (id, vector, metadata) tuples
        """
        pass

    @abstractmethod
    async def delete_vectors(self, index_name: str, ids: List[str]) -> bool:
        """Delete vectors by IDs."""
        pass

    @abstractmethod
    async def search(
        self,
        index_name: str,
        query_vector: List[float],
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.

        Returns:
            List of dicts with keys: id, score, metadata
        """
        pass

    @abstractmethod
    async def get_index_stats(self, index_name: str) -> Dict[str, Any]:
        """Get statistics about an index."""
        pass


class PineconeVectorStore(VectorStore):
    """
    Pinecone vector database implementation.
    Cloud-based, serverless vector database.
    """

    def __init__(self, api_key: str, environment: str):
        """
        Initialize Pinecone client.

        Args:
            api_key: Pinecone API key
            environment: Pinecone environment (e.g., 'us-east-1-aws')
        """
        try:
            import pinecone
            self.pinecone = pinecone
            self.pinecone.init(api_key=api_key, environment=environment)
            self.indexes = {}
            logger.info("Pinecone initialized successfully")
        except ImportError:
            raise ImportError("Pinecone SDK not installed. Run: pip install pinecone-client")
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            raise

    async def create_index(self, index_name: str, dimension: int, **kwargs) -> bool:
        """Create a new Pinecone index."""
        try:
            metric = kwargs.get('metric', 'cosine')

            if index_name not in self.pinecone.list_indexes():
                self.pinecone.create_index(
                    name=index_name,
                    dimension=dimension,
                    metric=metric
                )
                logger.info(f"Created Pinecone index: {index_name}")

            self.indexes[index_name] = self.pinecone.Index(index_name)
            return True
        except Exception as e:
            logger.error(f"Failed to create Pinecone index: {e}")
            return False

    async def delete_index(self, index_name: str) -> bool:
        """Delete a Pinecone index."""
        try:
            if index_name in self.pinecone.list_indexes():
                self.pinecone.delete_index(index_name)
                if index_name in self.indexes:
                    del self.indexes[index_name]
                logger.info(f"Deleted Pinecone index: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete Pinecone index: {e}")
            return False

    async def upsert_vectors(
        self,
        index_name: str,
        vectors: List[Tuple[str, List[float], Dict[str, Any]]]
    ) -> bool:
        """Insert or update vectors in Pinecone."""
        try:
            if index_name not in self.indexes:
                self.indexes[index_name] = self.pinecone.Index(index_name)

            index = self.indexes[index_name]

            # Pinecone accepts list of tuples (id, vector, metadata)
            index.upsert(vectors=vectors)

            logger.info(f"Upserted {len(vectors)} vectors to Pinecone index: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to upsert vectors to Pinecone: {e}")
            return False

    async def delete_vectors(self, index_name: str, ids: List[str]) -> bool:
        """Delete vectors from Pinecone."""
        try:
            if index_name not in self.indexes:
                self.indexes[index_name] = self.pinecone.Index(index_name)

            index = self.indexes[index_name]
            index.delete(ids=ids)

            logger.info(f"Deleted {len(ids)} vectors from Pinecone index: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete vectors from Pinecone: {e}")
            return False

    async def search(
        self,
        index_name: str,
        query_vector: List[float],
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search Pinecone index for similar vectors."""
        try:
            if index_name not in self.indexes:
                self.indexes[index_name] = self.pinecone.Index(index_name)

            index = self.indexes[index_name]

            results = index.query(
                vector=query_vector,
                top_k=top_k,
                filter=filter_dict,
                include_metadata=True
            )

            # Format results
            formatted_results = []
            for match in results['matches']:
                formatted_results.append({
                    'id': match['id'],
                    'score': match['score'],
                    'metadata': match.get('metadata', {})
                })

            return formatted_results
        except Exception as e:
            logger.error(f"Failed to search Pinecone: {e}")
            return []

    async def get_index_stats(self, index_name: str) -> Dict[str, Any]:
        """Get Pinecone index statistics."""
        try:
            if index_name not in self.indexes:
                self.indexes[index_name] = self.pinecone.Index(index_name)

            index = self.indexes[index_name]
            stats = index.describe_index_stats()

            return {
                'total_vectors': stats.get('total_vector_count', 0),
                'dimension': stats.get('dimension', 0),
                'index_fullness': stats.get('index_fullness', 0)
            }
        except Exception as e:
            logger.error(f"Failed to get Pinecone stats: {e}")
            return {}


class QdrantVectorStore(VectorStore):
    """
    Qdrant vector database implementation.
    Can be self-hosted or cloud-based.
    """

    def __init__(self, host: str = "localhost", port: int = 6333, api_key: Optional[str] = None):
        """
        Initialize Qdrant client.

        Args:
            host: Qdrant server host
            port: Qdrant server port
            api_key: Optional API key for Qdrant Cloud
        """
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            self.QdrantClient = QdrantClient
            self.Distance = Distance
            self.VectorParams = VectorParams

            if api_key:
                self.client = QdrantClient(url=f"https://{host}", api_key=api_key)
            else:
                self.client = QdrantClient(host=host, port=port)

            logger.info("Qdrant initialized successfully")
        except ImportError:
            raise ImportError("Qdrant SDK not installed. Run: pip install qdrant-client")
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant: {e}")
            raise

    async def create_index(self, index_name: str, dimension: int, **kwargs) -> bool:
        """Create a new Qdrant collection."""
        try:
            metric = kwargs.get('metric', 'cosine')
            distance_map = {
                'cosine': self.Distance.COSINE,
                'euclidean': self.Distance.EUCLID,
                'dot': self.Distance.DOT
            }

            self.client.create_collection(
                collection_name=index_name,
                vectors_config=self.VectorParams(
                    size=dimension,
                    distance=distance_map.get(metric, self.Distance.COSINE)
                )
            )

            logger.info(f"Created Qdrant collection: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create Qdrant collection: {e}")
            return False

    async def delete_index(self, index_name: str) -> bool:
        """Delete a Qdrant collection."""
        try:
            self.client.delete_collection(collection_name=index_name)
            logger.info(f"Deleted Qdrant collection: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete Qdrant collection: {e}")
            return False

    async def upsert_vectors(
        self,
        index_name: str,
        vectors: List[Tuple[str, List[float], Dict[str, Any]]]
    ) -> bool:
        """Insert or update vectors in Qdrant."""
        try:
            from qdrant_client.models import PointStruct

            points = [
                PointStruct(
                    id=vec_id,
                    vector=vector,
                    payload=metadata
                )
                for vec_id, vector, metadata in vectors
            ]

            self.client.upsert(
                collection_name=index_name,
                points=points
            )

            logger.info(f"Upserted {len(vectors)} vectors to Qdrant collection: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to upsert vectors to Qdrant: {e}")
            return False

    async def delete_vectors(self, index_name: str, ids: List[str]) -> bool:
        """Delete vectors from Qdrant."""
        try:
            self.client.delete(
                collection_name=index_name,
                points_selector=ids
            )

            logger.info(f"Deleted {len(ids)} vectors from Qdrant collection: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete vectors from Qdrant: {e}")
            return False

    async def search(
        self,
        index_name: str,
        query_vector: List[float],
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search Qdrant collection for similar vectors."""
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            # Convert filter_dict to Qdrant filter format
            query_filter = None
            if filter_dict:
                conditions = [
                    FieldCondition(key=key, match=MatchValue(value=value))
                    for key, value in filter_dict.items()
                ]
                query_filter = Filter(must=conditions)

            results = self.client.search(
                collection_name=index_name,
                query_vector=query_vector,
                limit=top_k,
                query_filter=query_filter
            )

            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    'id': str(result.id),
                    'score': result.score,
                    'metadata': result.payload
                })

            return formatted_results
        except Exception as e:
            logger.error(f"Failed to search Qdrant: {e}")
            return []

    async def get_index_stats(self, index_name: str) -> Dict[str, Any]:
        """Get Qdrant collection statistics."""
        try:
            collection_info = self.client.get_collection(collection_name=index_name)

            return {
                'total_vectors': collection_info.points_count,
                'dimension': collection_info.config.params.vectors.size,
                'indexed_vectors': collection_info.indexed_vectors_count
            }
        except Exception as e:
            logger.error(f"Failed to get Qdrant stats: {e}")
            return {}


class LocalVectorStore(VectorStore):
    """
    Simple local vector store using NumPy.
    Suitable for development and small-scale deployments.
    """

    def __init__(self):
        """Initialize local vector store."""
        self.indexes: Dict[str, Dict[str, Any]] = {}
        logger.info("Local vector store initialized")

    async def create_index(self, index_name: str, dimension: int, **kwargs) -> bool:
        """Create a new local index."""
        try:
            self.indexes[index_name] = {
                'dimension': dimension,
                'vectors': {},
                'metadata': {}
            }
            logger.info(f"Created local index: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create local index: {e}")
            return False

    async def delete_index(self, index_name: str) -> bool:
        """Delete a local index."""
        try:
            if index_name in self.indexes:
                del self.indexes[index_name]
                logger.info(f"Deleted local index: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete local index: {e}")
            return False

    async def upsert_vectors(
        self,
        index_name: str,
        vectors: List[Tuple[str, List[float], Dict[str, Any]]]
    ) -> bool:
        """Insert or update vectors in local store."""
        try:
            if index_name not in self.indexes:
                return False

            index = self.indexes[index_name]

            for vec_id, vector, metadata in vectors:
                index['vectors'][vec_id] = np.array(vector)
                index['metadata'][vec_id] = metadata

            logger.info(f"Upserted {len(vectors)} vectors to local index: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to upsert vectors to local store: {e}")
            return False

    async def delete_vectors(self, index_name: str, ids: List[str]) -> bool:
        """Delete vectors from local store."""
        try:
            if index_name not in self.indexes:
                return False

            index = self.indexes[index_name]

            for vec_id in ids:
                if vec_id in index['vectors']:
                    del index['vectors'][vec_id]
                if vec_id in index['metadata']:
                    del index['metadata'][vec_id]

            logger.info(f"Deleted {len(ids)} vectors from local index: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete vectors from local store: {e}")
            return False

    async def search(
        self,
        index_name: str,
        query_vector: List[float],
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search local index using cosine similarity."""
        try:
            if index_name not in self.indexes:
                return []

            index = self.indexes[index_name]
            query_vec = np.array(query_vector)

            # Calculate cosine similarity for all vectors
            similarities = []
            for vec_id, vector in index['vectors'].items():
                # Apply filter if provided
                if filter_dict:
                    metadata = index['metadata'].get(vec_id, {})
                    if not all(metadata.get(k) == v for k, v in filter_dict.items()):
                        continue

                # Cosine similarity
                similarity = np.dot(query_vec, vector) / (
                    np.linalg.norm(query_vec) * np.linalg.norm(vector)
                )

                similarities.append({
                    'id': vec_id,
                    'score': float(similarity),
                    'metadata': index['metadata'].get(vec_id, {})
                })

            # Sort by similarity and return top_k
            similarities.sort(key=lambda x: x['score'], reverse=True)
            return similarities[:top_k]
        except Exception as e:
            logger.error(f"Failed to search local index: {e}")
            return []

    async def get_index_stats(self, index_name: str) -> Dict[str, Any]:
        """Get local index statistics."""
        try:
            if index_name not in self.indexes:
                return {}

            index = self.indexes[index_name]

            return {
                'total_vectors': len(index['vectors']),
                'dimension': index['dimension']
            }
        except Exception as e:
            logger.error(f"Failed to get local index stats: {e}")
            return {}


def get_vector_store(store_type: str, config: Dict[str, Any]) -> VectorStore:
    """
    Factory function to create vector store instances.

    Args:
        store_type: Type of vector store (pinecone, qdrant, local)
        config: Configuration dict for the specific store

    Returns:
        VectorStore instance
    """
    if store_type == "pinecone":
        return PineconeVectorStore(
            api_key=config['api_key'],
            environment=config['environment']
        )
    elif store_type == "qdrant":
        return QdrantVectorStore(
            host=config.get('host', 'localhost'),
            port=config.get('port', 6333),
            api_key=config.get('api_key')
        )
    elif store_type == "local":
        return LocalVectorStore()
    else:
        raise ValueError(f"Unsupported vector store type: {store_type}")
