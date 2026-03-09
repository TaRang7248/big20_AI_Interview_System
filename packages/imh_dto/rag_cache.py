from datetime import datetime
from typing import Dict, Any, Optional
from packages.imh_core.dto import BaseDTO

class RAGCacheDTO(BaseDTO):
    """
    RAG Result Cache (Value Object)
    
    Stores the final output and related metadata for a RAG query.
    This object is for Latency/Cost Optimization only, NOT Authority.
    """
    # Key Components (Informational, used for verification)
    job_id: str
    policy_version: str
    prompt_version: str
    model_name: str
    
    # Input Hash (For collision check)
    input_hash: str
    
    # RAG Result Payload
    answer: str
    evidence: Optional[Dict[str, Any]] = None # Simplified representation of evidence
    
    # Metadata
    created_at: datetime
    ttl_minutes: int
    
    # Optimization Metrics
    tokens_used: int = 0
    latency_ms: int = 0
