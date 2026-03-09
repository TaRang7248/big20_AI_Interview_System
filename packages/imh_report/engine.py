from typing import List
from packages.imh_eval.schema import EvaluationResult, RubricScoreItem
from packages.imh_report.dto import InterviewReport, ReportHeader, ReportDetail, ReportFooter
from packages.imh_report.mapping import TagTranslator

class ReportGenerator:
    """
    Business Logic Component for Reporting Layer.
    Converts EvaluationResult -> InterviewReport.
    """
    
    @staticmethod
    def generate(eval_result: EvaluationResult) -> InterviewReport:
        # 1. Header Calculation
        # Assume eval_result.total_score is on 5.0 scale (weighted).
        # We convert it to 100 scale.
        score_100 = eval_result.total_score * 20.0 
        
        # Clamp score to 0-100 just in case
        score_100 = max(0.0, min(100.0, score_100))
        
        grade = TagTranslator.get_grade(score_100)
        
        # Collect top scoring tags for keywords
        sorted_items = sorted(eval_result.details, key=lambda x: x.score, reverse=True)
        top_keywords = [item.category for item in sorted_items[:3]] # Simple keyword extraction strategy
        
        header = ReportHeader(
            total_score=round(score_100, 1),
            grade=grade,
            job_category=eval_result.job_category,
            job_id=eval_result.job_id,
            keywords=list(set(top_keywords)) # Deduplicate
        )
        
        # 2. Details & Footer Logic
        details: List[ReportDetail] = []
        strengths: List[str] = []
        weaknesses: List[str] = []
        insights: List[str] = []
        
        for item in eval_result.details:
            # Map Level Description
            level_desc = TagTranslator.get_level_description(float(item.score))
            
            # Map Feedback
            feedback_msg = TagTranslator.get_feedback(item.tag_code, float(item.score))
            if item.improvement_feedback:
                # Append specific feedback from eval layer if exists
                feedback_msg += f" ({item.improvement_feedback})"
            
            # Convert EvidenceData to string list (Simple serialization for now)
            # In real scenario, we might want to iterate fields of evidence_data
            evidence_list = []
            if item.rationale:
                evidence_list.append(f"Rationale: {item.rationale}")
            
            # Create Detail Object
            detail = ReportDetail(
                category=item.category,
                score=float(item.score),
                level_description=level_desc,
                feedback=feedback_msg,
                key_evidence=evidence_list,
                tag_code=item.tag_code
            )
            details.append(detail)
            
            # Identify Strength/Weakness
            if item.score >= 4.0:
                strengths.append(f"[{item.category}] {feedback_msg}")
            elif item.score <= 2.0:
                 weaknesses.append(f"[{item.category}] {feedback_msg}")
                 # Add actionable insight for weakness
                 suggestion = TagTranslator.get_improvement_suggestion(item.tag_code)
                 insights.append(f"[{item.category}] {suggestion}")

        footer = ReportFooter(
            strengths=strengths,
            weaknesses=weaknesses,
            actionable_insights=insights
        )
        
        return InterviewReport(
            header=header,
            details=details,
            footer=footer,
            raw_debug_info={"original_total_score": eval_result.total_score}
        )
