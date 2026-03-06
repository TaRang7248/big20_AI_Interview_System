from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class QuestionGenerationResult:
    def __init__(self, content: str, metadata: Dict[str, Any], success: bool, error: Optional[str] = None):
        self.content = content
        self.metadata = metadata
        self.success = success
        self.error = error

class QuestionGenerator(ABC):
    @abstractmethod
    def generate_question(self, context: Dict[str, Any]) -> QuestionGenerationResult:
        """
        Generate a question based on context.
        Must return success=False on failure, never raise exception.
        """
        pass

class LLMQuestionGenerator(QuestionGenerator):
    """
    TASK-032: Bridging ILLMProvider to the synchronous SessionEngine Pipeline.
    """
    def __init__(self, provider: Any): # provider is ILLMProvider
        self.provider = provider
        
    def generate_question(self, context: Dict[str, Any]) -> QuestionGenerationResult:
        import asyncio
        from packages.imh_core.dto import LLMMessageDTO

        # 1. Build prompt based on context
        step = context.get("step", 1)
        job_id = context.get("job_id", "Unknown")
        history = context.get("question_history", [])
        # TASK-035: Resume Summary injection (flag-gated via context key)
        resume_summary: Optional[str] = context.get("resume_summary")
        step_type_val: str = context.get("step_type", "MAIN")
        # Resolve to string name for comparison (SessionStepType enum or plain str)
        step_type_name = step_type_val.value if hasattr(step_type_val, "value") else str(step_type_val)

        # Dynamic job context — no more hardcoding (resolved from session context)
        job_title: str = context.get("job_title") or context.get("job_category") or "Software Engineer"
        persona: str = context.get("persona") or "professional"

        # Persona-based system prompt
        _persona_map = {
            "professional": (
                "You are a professional technical interviewer AI with a structured, formal approach. "
                "Generate ONE concise interview question based on the provided context."
            ),
            "friendly": (
                "You are a friendly and encouraging technical interviewer AI. "
                "Generate ONE warm but professional interview question based on the provided context."
            ),
            "strict": (
                "You are a rigorous and demanding technical interviewer AI who expects precise, detailed answers. "
                "Generate ONE challenging interview question based on the provided context."
            ),
        }
        system_prompt = _persona_map.get(persona, _persona_map["professional"])

        user_prompt = f"Job Role: {job_title}\nInterview Step: {step}\n"
        if history:
            user_prompt += "\nPreviously asked questions (Do NOT repeat these):\n" + "\n".join(f"- {q}" for q in history)

        # TASK-035: Inject resume_summary only for MAIN (not OPENING/GENERAL_SMALLTALK)
        if resume_summary and step_type_name not in ("OPENING", "GENERAL_SMALLTALK"):
            truncated = resume_summary[:1000]
            user_prompt += f"\n\nCandidate Resume Summary (use as context for depth):\n{truncated}"

        user_prompt += "\n\nPlease ask the next interview question. Only output the question text, no conversational filler."

        messages = [LLMMessageDTO(role="user", content=user_prompt)]
        
        # 2. Execute Async Provider Synchronously (Thread isolated to avoid event loop conflicts in FastAPI)
        import threading
        
        result_box = []
        error_box = []
        
        def run_in_new_loop():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                # Assume provider.chat is an async method returning LLMResponseDTO
                res = loop.run_until_complete(
                    self.provider.chat(messages=messages, system_prompt=system_prompt)
                )
                result_box.append(res)
                loop.close()
            except Exception as ex:
                error_box.append(ex)
                
        thread = threading.Thread(target=run_in_new_loop)
        thread.start()
        thread.join()
            
        if error_box:
            e = error_box[0]
            import logging
            logging.getLogger("imh_providers.llm").error(f"LLM Generation Failed (Tier 1): {e}")
            return QuestionGenerationResult(
                content="",
                metadata={},
                success=False,
                error=str(e)
            )
            
        if result_box:
            response = result_box[0]
            return QuestionGenerationResult(
                content=response.content,
                metadata={"model": getattr(self.provider, "model_name", "unknown"), "usage": response.token_usage},
                success=True
            )
            
        return QuestionGenerationResult(content="", metadata={}, success=False, error="Unknown thread failure")
