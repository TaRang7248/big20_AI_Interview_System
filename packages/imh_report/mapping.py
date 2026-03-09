from typing import Dict

class TagTranslator:
    """
    Translates technical tag_codes and scores into user-friendly text.
    In the future, this can be replaced with a file-based loader (YAML/JSON).
    """
    
    # Generic feedback templates per tag_code
    TAG_FEEDBACK: Dict[str, str] = {
        # Job Competency
        "capability.knowledge": "직무 관련 지식의 깊이와 정확도",
        "capability.logic": "논리적인 문제 해결 접근 방식",
        "capability.code_quality": "코드의 효율성 및 가독성",
        
        # Problem Solving
        "problem_solving.hint_usage": "힌트 의존도 및 스스로 해결하는 능력",
        "problem_solving.adaptability": "새로운 정보나 피드백 반영 능력",
        
        # Communication
        "communication.clarity": "답변의 명확성 및 전달력",
        "communication.structure": "논리적이고 구조화된 답변 구성 (STAR 기법 등)",
        
        # Attitude
        "attitude.gaze": "시선 처리 및 아이컨택 유지",
        "attitude.confidence": "자신감 있는 태도와 목소리",
        "attitude.positivity": "긍정적이고 적극적인 자세"
    }

    # Actionable Insights templates per tag_code (Simple version)
    TAG_INSIGHTS: Dict[str, str] = {
        "capability.knowledge": "관련 기술 블로그나 공식 문서를 참고하여 심화 학습이 필요합니다.",
        "capability.logic": "알고리즘 문제 풀이를 통해 논리적 사고력을 기르세요.",
        "capability.code_quality": "Clean Code 원칙을 적용하여 가독성을 높이는 연습을 하세요.",
        "problem_solving.hint_usage": "힌트 없이 문제를 해결해보는 끈기가 필요합니다.",
        "problem_solving.adaptability": "다양한 해결 방안을 유연하게 수용하는 태도를 보여주세요.",
        "communication.clarity": "두괄식으로 핵심을 먼저 말하는 연습을 해보세요.",
        "communication.structure": "STAR (Situation, Task, Action, Result) 기법으로 답변을 구조화하세요.",
        "attitude.gaze": "카메라 렌즈를 응시하며 아이컨택을 유지하는 연습이 필요합니다.",
        "attitude.confidence": "답변 시 끝맺음을 명확히 하여 자신감을 보여주세요.",
         "attitude.positivity": "어려운 질문에도 긍정적인 마인드셋을 보여주려 노력하세요."
    }

    @classmethod
    def get_feedback(cls, tag_code: str, score: float) -> str:
        """
        Returns a feedback string based on tag and score.
        """
        base_msg = cls.TAG_FEEDBACK.get(tag_code, "해당 항목에 대한 평가")
        if score >= 4:
            return f"{base_msg}가 우수합니다."
        elif score >= 3:
            return f"{base_msg}가 양호합니다."
        else:
            return f"{base_msg}에 대한 보완이 필요합니다."

    @classmethod
    def get_level_description(cls, score: float) -> str:
        if score >= 4.5: return "탁월 (Excellent)"
        if score >= 4.0: return "우수 (Good)"
        if score >= 3.0: return "보통 (Average)"
        if score >= 2.0: return "미흡 (Below Average)"
        return "심각 (Poor)"

    @classmethod
    def get_grade(cls, score_100: float) -> str:
        if score_100 >= 90: return "S"
        if score_100 >= 80: return "A"
        if score_100 >= 70: return "B"
        if score_100 >= 60: return "C"
        return "D"
    
    @classmethod
    def get_improvement_suggestion(cls, tag_code: str) -> str:
         return cls.TAG_INSIGHTS.get(tag_code, "해당 역량을 강화하기 위한 지속적인 학습이 필요합니다.")
