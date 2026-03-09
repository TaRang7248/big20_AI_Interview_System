from typing import List, Optional

def calculate_knowledge_score(keyword_match: Optional[List[str]], ast_complexity: Optional[float] = None) -> int:
    """
    Calculates Job Knowledge score based on keyword matches and code complexity.
    """
    if keyword_match is None:
        return 1
    
    match_count = len(keyword_match)
    
    # Base score on keywords
    if match_count >= 4:
        score = 5
    elif match_count == 3:
        score = 4
    elif match_count == 2:
        score = 3
    elif match_count == 1:
        score = 2
    else:
        score = 1
        
    # Adjustment for Complexity (Bonus/Penalty) - Placeholder logic
    # If code is too simple (complexity < 2), cap score at 3?
    if ast_complexity is not None and ast_complexity < 2:
        score = min(score, 3)
        
    return score

def calculate_problem_solving_score(hint_count: int) -> int:
    """
    Calculates Problem Solving score based on hint usage.
    """
    if hint_count == 0:
        return 5
    elif hint_count == 1:
        return 4
    elif hint_count == 2:
        return 3
    elif hint_count == 3:
        return 2
    else:
        return 1

def calculate_communication_score(star_structure: bool) -> int:
    """
    Calculates Communication score based on STAR structure adherence.
    """
    if star_structure:
        return 5
    else:
        return 3 # Default to Average if not structured

def calculate_attitude_score(gaze_center_percent: float, negative_emotion_percent: float) -> int:
    """
    Calculates Attitude score based on Gaze and Emotion metrics.
    """
    # Gaze Score
    if gaze_center_percent >= 80.0:
        gaze_score = 5
    elif gaze_center_percent >= 50.0:
        gaze_score = 3
    else:
        gaze_score = 1
        
    # Emotion Score (Low negative emotion is good)
    if negative_emotion_percent < 10.0:
        emotion_score = 5
    elif negative_emotion_percent < 30.0:
        emotion_score = 3
    else:
        emotion_score = 1
        
    # Weighted Average for Attitude (50:50)
    final_score = int((gaze_score + emotion_score) / 2)
    return max(1, min(5, final_score))
