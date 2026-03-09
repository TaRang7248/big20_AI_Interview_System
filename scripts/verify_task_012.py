
import sys
import os
import json

# Ensure project root is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from packages.imh_eval.schema import EvaluationResult, RubricScoreItem, EvidenceData
from packages.imh_report.engine import ReportGenerator
from packages.imh_report.dto import InterviewReport

def run_verification():
    print(">>> [TASK-012] Starting Reporting Layer Verification...")
    
    # 1. Create Mock Evaluation Result
    mock_evidence = EvidenceData(
        keyword_match=["REST", "API"],
        cosine_similarity=0.85
    )
    
    mock_items = [
        RubricScoreItem(
            category="직무 역량",
            tag_code="capability.knowledge",
            score=4,
            rationale="Correctly explained REST API concepts.",
            evidence_data=mock_evidence
        ),
        RubricScoreItem(
            category="태도",
            tag_code="attitude.gaze",
            score=2,
            rationale="Frequent gaze avoidance detected.",
            evidence_data=EvidenceData(gaze_center_percent=0.4)
        )
    ]
    
    mock_result = EvaluationResult(
        total_score=3.5, # Weighted average
        details=mock_items,
        job_category="DEV"
    )
    
    print(f"Input Evaluation Result: Total Score={mock_result.total_score}")
    
    # 2. Run Generator
    try:
        report = ReportGenerator.generate(mock_result)
        print(">>> Report Generation Successful.")
    except Exception as e:
        print(f"!!! Generation Failed: {e}")
        raise e
        
    # 3. Validate Output Structure
    print(">>> Validating Output Structure...")
    
    # Check Header
    assert isinstance(report, InterviewReport)
    assert report.header.total_score == 70.0 # 3.5 * 20
    assert report.header.grade == "B"
    print(f" Header: Score={report.header.total_score}, Grade={report.header.grade}")
    
    # Check Details
    assert len(report.details) == 2
    detail_1 = report.details[0]
    assert detail_1.category == "직무 역량"
    assert "우수합니다" in detail_1.feedback
    print(f" Detail[0]: {detail_1.feedback}")
    
    detail_2 = report.details[1]
    assert detail_2.category == "태도"
    assert "보완이 필요합니다" in detail_2.feedback
    print(f" Detail[1]: {detail_2.feedback}")
    
    # Check Footer (Insights)
    assert len(report.footer.actionable_insights) >= 1
    assert "아이컨택" in report.footer.actionable_insights[0] or "태도" in report.footer.actionable_insights[0]
    print(f" Insight: {report.footer.actionable_insights[0]}")
    
    # 4. Dump JSON (Simulation of API response)
    json_output = report.model_dump_json(indent=2)
    print(">>> JSON Output Preview:")
    print(json_output)
    
    print(">>> [TASK-012] Verification PASSED.")

if __name__ == "__main__":
    run_verification()
