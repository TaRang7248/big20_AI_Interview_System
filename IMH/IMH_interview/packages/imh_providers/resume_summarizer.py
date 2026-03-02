"""
TASK-034 Step 5: ResumeSummarizer
Generates a ResumeSummary from raw PDF text using LLM.
- 1 LLM call per session (GPU Safe)
- Immutable after session start
- Falls back to Generic Persona Summary if no resume is provided
"""
from __future__ import annotations

from typing import Optional


GENERIC_FALLBACK_SUMMARY = (
    "Standard applicant. No resume provided. "
    "Interview proceeds with general capability evaluation."
)


class ResumeSummaryResult:
    """
    Holds the generated resume summary and whether it was generated or fallback.
    This is stored in the session snapshot and must not be regenerated.
    """
    def __init__(self, summary: str, is_fallback: bool = False):
        self.summary = summary
        self.is_fallback = is_fallback


class ResumeSummarizer:
    """
    Generates a single, immutable resume summary at session start.

    GPU Safe Contract:
    - Maximum 1 LLM call per session
    - No iterative refinement
    - Categorical extraction only

    Immutability Contract:
    - Once generated, the summary is stored in session snapshot
    - It is never regenerated during the interview
    """

    def __init__(self, llm_caller=None):
        """
        :param llm_caller: Callable(prompt: str) -> str | None
                           Provides the LLM interface. If None, always uses fallback.
        """
        self._llm_caller = llm_caller
        self._call_count = 0  # GPU safety guard: must never exceed 1 per instance

    def generate(self, raw_pdf_text: Optional[str]) -> ResumeSummaryResult:
        """
        Generate a resume summary from raw PDF text.
        If no PDF text, returns Generic Fallback Summary immediately (no LLM call).

        GPU safe: enforces max 1 LLM call (raises RuntimeError if called again).
        """
        # ── No resume: use fallback (zero LLM cost) ────────────────────
        if not raw_pdf_text or not raw_pdf_text.strip():
            return ResumeSummaryResult(
                summary=GENERIC_FALLBACK_SUMMARY,
                is_fallback=True,
            )

        # ── GPU Safety Guard ────────────────────────────────────────────
        if self._call_count >= 1:
            raise RuntimeError(
                "ResumeSummarizer.generate() called more than once per session. "
                "GPU Safe Mode: max 1 LLM call per session for resume summarization."
            )

        # ── No LLM caller configured: safe fallback ─────────────────────
        if self._llm_caller is None:
            return ResumeSummaryResult(
                summary=GENERIC_FALLBACK_SUMMARY,
                is_fallback=True,
            )

        # ── Single LLM Call ─────────────────────────────────────────────
        self._call_count += 1
        prompt = self._build_prompt(raw_pdf_text)
        try:
            summary = self._llm_caller(prompt)
            if not summary or not summary.strip():
                return ResumeSummaryResult(
                    summary=GENERIC_FALLBACK_SUMMARY, is_fallback=True
                )
            return ResumeSummaryResult(summary=summary.strip(), is_fallback=False)
        except Exception:
            # LLM failure: fall back gracefully
            return ResumeSummaryResult(
                summary=GENERIC_FALLBACK_SUMMARY, is_fallback=True
            )

    @staticmethod
    def _build_prompt(raw_text: str) -> str:
        truncated = raw_text[:3000]   # Token safety: limit input length
        return (
            "You are an interview assistant. Extract and summarize the candidate's "
            "key skills, experience level, and relevant background from this resume text. "
            "Be concise and factual. Output in 3-5 sentences.\n\n"
            f"Resume:\n{truncated}"
        )
