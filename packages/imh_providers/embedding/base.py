from abc import ABC, abstractmethod
from typing import List

class EmbeddingProvider(ABC):
    """
    Interface for Embedding Provider.
    Responsible for converting text into vector representation.
    Focused on Search Query Embedding for Retrieval tasks.
    """

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single query text into a vector.

        Args:
            text (str): The search query text to embed.

        Returns:
            List[float]: The embedding vector.
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """
        Get the dimension of the embedding vector.

        Returns:
            int: Dimension size (e.g., 1536 for OpenAI, 384 for MiniLM).
        """
        pass
