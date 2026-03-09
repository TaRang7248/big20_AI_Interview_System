from .base import EmbeddingProvider
from .mock import MockEmbeddingProvider

def get_embedding_provider(provider_type: str = "mock", **kwargs) -> EmbeddingProvider:
    """
    Factory to get Embedding Provider instance.

    Args:
        provider_type (str): 'mock', 'local', etc.
        **kwargs: Arguments to pass to the provider constructor.

    Returns:
        EmbeddingProvider instance
    """
    if provider_type == "mock":
        return MockEmbeddingProvider(**kwargs)
    
    # Future extension:
    # elif provider_type == "local":
    #     from .local import LocalEmbeddingProvider
    #     return LocalEmbeddingProvider(**kwargs)
    
    raise ValueError(f"Unknown provider type: {provider_type}")
