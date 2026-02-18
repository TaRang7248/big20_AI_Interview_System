import hashlib
import logging

class CanaryManager:
    """
    Manages Canary Release Rollout.
    Uses deterministic hashing to ensure stable user selection.
    
    Phase 4.2 Goal: 1% Rollout.
    """
    def __init__(self, default_percentage: int = 1):
        self.default_percentage = default_percentage
        self.logger = logging.getLogger("imh.canary")

    def check_canary_access(self, user_id: str, percentage: int = None) -> bool:
        """
        Check if user is selected for Canary.
        Deterministic: Same user_id always yields same result for same percentage.
        """
        if percentage is None:
            percentage = self.default_percentage
            
        if percentage <= 0:
            return False
        if percentage >= 100:
            return True
        if not user_id:
            return False
            
        # Deterministic Hash
        hash_val = int(hashlib.md5(user_id.encode('utf-8')).hexdigest(), 16)
        normalized = hash_val % 100
        
        is_selected = normalized < percentage
        
        if is_selected:
            self.logger.info(f"User {user_id} selected for Canary (Rollout: {percentage}%)")
            
        return is_selected
