class JobError(Exception):
    """Base exception for Job package"""
    pass

class JobStateError(JobError):
    """Raised when an operation is invalid for the current job status"""
    pass

class PolicyValidationError(JobError):
    """Raised when policy validation fails (e.g. editing sensitive fields in PUBLISHED state)"""
    pass
