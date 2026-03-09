from .question import QuestionGenerator, QuestionGenerationResult
import time
import random

class MockQuestionGenerator(QuestionGenerator):
    """
    Mock implementation for testing RAG Fallback.
    Simulates latency and failure scenarios.
    """
    def __init__(self, should_fail: bool = False, latency: float = 0.0):
        self.should_fail = should_fail
        self.latency = latency

    def generate_question(self, context: dict) -> QuestionGenerationResult:
        if self.latency > 0:
            time.sleep(self.latency)
            
        if self.should_fail:
            return QuestionGenerationResult("", {}, False, "Mock Failure: Intentional Error")
            
        # Simulate generated content
        job_title = context.get("job_title", "Unknown Job")
        q_content = f"Can you describe a situation where you demonstrated leadership in {job_title}?"
        
        return QuestionGenerationResult(
            content=q_content,
            metadata={
                "model": "mock-gpt-4", 
                "timestamp": time.time(),
                "origin_type": "GENERATED"
            },
            success=True
        )
