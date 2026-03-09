import random
from typing import List
from .base import EmbeddingProvider

class MockEmbeddingProvider(EmbeddingProvider):
    """
    Mock implementation of EmbeddingProvider for testing/development.
    Returns random vectors.
    """

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def embed_query(self, text: str) -> List[float]:
        """
        Returns a random vector of the specified dimension.
        The input text is ignored in the mock implementation.
        """
        # Generate random floats between -1.0 and 1.0
        return [random.uniform(-1.0, 1.0) for _ in range(self.dimension)]

    def get_dimension(self) -> int:
        return self.dimension
