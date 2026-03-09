import sys
import os
import json
import logging

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from packages.imh_eval.engine import RubricEvaluator, EvaluationContext
from packages.imh_eval.schema import EvaluationResult

# Setup Logger
log_dir = os.path.join(os.path.dirname(__file__), "../logs/agent")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_dir, "verify_task_011.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger("").addHandler(console)
logger = logging.getLogger(__name__)

def test_dev_perfect_score():
    logger.info("=== Test Case 1: DEV Profile with Perfect Score Inputs ===")
    
    context = EvaluationContext(
        job_category="DEV",
        answer_text="Perfect answer with all keywords",
        rag_keywords_found=["REST", "API", "Stateless", "JSON"], # 4 keywords -> Score 5
        hint_count=0, # Score 5
        star_structure_detected=True, # Score 5
        visual_analysis={"gaze": {"center_ratio": 0.9}}, # >80% -> Score 5
        emotion_analysis={"time_series": [{"emotion": "neutral"}, {"emotion": "happy"}]} # 0% Neg -> Score 5
    )
    
    evaluator = RubricEvaluator()
    result = evaluator.evaluate(context)
    
    logger.info(f"Total Score: {result.total_score}")
    logger.info(f"Details: {json.dumps([d.model_dump() for d in result.details], default=str)}")
    
    # Assertions
    assert result.total_score == 5.0, f"Expected 5.0, got {result.total_score}"
    for item in result.details:
        assert item.score == 5, f"Expected score 5 for {item.category}, got {item.score}"
        
    logger.info("Test Case 1 PASSED")
    return True

def test_non_tech_mixed_score():
    logger.info("\n=== Test Case 2: NON_TECH Profile with Mixed Inputs ===")
    
    # NON_TECH Weights: Comm(0.4), PS(0.3), Job(0.2), Att(0.1)
    
    context = EvaluationContext(
        job_category="NON_TECH",
        answer_text="Average answer",
        rag_keywords_found=["Communication"], # 1 keyword -> Score 2
        hint_count=2, # Score 3
        star_structure_detected=False, # Score 3
        visual_analysis={"gaze": {"center_ratio": 0.6}}, # >50% -> Score 3
        emotion_analysis={"time_series": [{"emotion": "sad"}, {"emotion": "neutral"}]} # 50% Neg -> Score 1
    )
    
    # Attitude Score: (Gaze 3 + Emotion 1) / 2 = 2
    
    evaluator = RubricEvaluator()
    result = evaluator.evaluate(context)
    
    # Expected Calculation:
    # Comm (Score 3) * 0.4 = 1.2
    # PS   (Score 3) * 0.3 = 0.9
    # Job  (Score 2) * 0.2 = 0.4
    # Att  (Score 2) * 0.1 = 0.2
    # Total = 1.2 + 0.9 + 0.4 + 0.2 = 2.7
    
    logger.info(f"Total Score: {result.total_score}")
    
    expected_score = 2.7
    assert abs(result.total_score - expected_score) < 0.001, f"Expected {expected_score}, got {result.total_score}"
    
    # Check Tag Codes
    tags = [d.tag_code for d in result.details]
    assert "capability.communication" in tags
    assert "capability.problem_solving" in tags
    assert "capability.knowledge" in tags
    assert "capability.attitude" in tags
    
    logger.info("Test Case 2 PASSED")
    return True

def test_schema_compliance():
    logger.info("\n=== Test Case 3: JSON Schema Compliance ===")
    
    context = EvaluationContext(
        job_category="DEV",
        answer_text="Test",
        rag_keywords_found=[]
    )
    evaluator = RubricEvaluator()
    result = evaluator.evaluate(context)
    
    json_output = result.model_dump()
    logger.info("JSON Output generated successfully")
    
    # Check required fields in EvidenceData (even if None)
    evidence = result.details[0].evidence_data
    assert hasattr(evidence, "cosine_similarity")
    assert hasattr(evidence, "keyword_match")
    
    logger.info("Test Case 3 PASSED")
    return True

if __name__ == "__main__":
    try:
        success = True
        if not test_dev_perfect_score(): success = False
        if not test_non_tech_mixed_score(): success = False
        if not test_schema_compliance(): success = False
        
        if success:
            logger.info("\nALL VERIFICATION TESTS PASSED")
            print("ALL VERIFICATION TESTS PASSED")
            sys.exit(0)
        else:
            logger.error("\nSOME TESTS FAILED")
            print("SOME TESTS FAILED")
            sys.exit(1)
            
    except Exception as e:
        logger.exception("Verification Script Crashed")
        print(f"Verification Script Crashed: {e}")
        sys.exit(1)
