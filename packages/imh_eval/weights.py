from typing import Dict

JOB_WEIGHTS = {
    "DEV": {
        "capability.knowledge": 0.4,
        "capability.problem_solving": 0.3,
        "capability.communication": 0.2,
        "capability.attitude": 0.1
    },
    "NON_TECH": {
        "capability.communication": 0.4,
        "capability.problem_solving": 0.3,
        "capability.knowledge": 0.2,
        "capability.attitude": 0.1
    }
}

def get_weights(job_category: str) -> Dict[str, float]:
    """
    Returns the weight dictionary for the given job category.
    Defaults to DEV if category is unknown.
    """
    return JOB_WEIGHTS.get(job_category, JOB_WEIGHTS["DEV"])
