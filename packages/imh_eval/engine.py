from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from .schema import EvaluationResult, RubricScoreItem, EvidenceData
from .rules import (
    calculate_knowledge_score,
    calculate_problem_solving_score,
    calculate_communication_score,
    calculate_attitude_score
)
from .weights import get_weights
try:
    from packages.imh_core.wiring_flags import WiringFlags
except ModuleNotFoundError:
    try:
        import sys as _sys
        import os as _os
        _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", ".."))
        from packages.imh_core.wiring_flags import WiringFlags
    except Exception:
        class WiringFlags:  # type: ignore
            """Stub: all flags off — legacy unchanged behavior."""
            @classmethod
            def weight_sync_active(cls): return False
            @classmethod
            def phase_active(cls): return False
            @classmethod
            def fixed_q_active(cls): return False

# Canonical rubric keys — must match tag_code used in DistributionCalculator snapshots
_REQUIRED_WEIGHT_KEYS = frozenset([
    "capability.knowledge",
    "capability.problem_solving",
    "capability.communication",
    "capability.attitude",
])

class EvaluationContext(BaseModel):
    """
    Input context for evaluation. 
    Combines raw analysis results and mock data for missing providers.
    """
    job_category: str = Field(..., description="DEV or NON_TECH")
    job_id: Optional[str] = Field(None, description="Job ID")
    
    # Analysis Inputs
    answer_text: str
    code_snippet: Optional[str] = None
    hint_count: int = 0
    
    # Provider Results (Raw Dicts from previous tasks)
    visual_analysis: Optional[Dict[str, Any]] = None
    emotion_analysis: Optional[Dict[str, Any]] = None
    
    # Mock Data for Missing Providers (RAG/LLM)
    # in real implemenation, these would be results from those providers
    # Determinism Inputs (Section 1 / Phase 3-FIX-C1)
    resume_snapshot_hash: Optional[str] = None
    policy_snapshot_hash: Optional[str] = None
    stt_snapshot_hash: Optional[str] = None
    phase_flow: Optional[str] = "MAIN"
    context_history: List[Dict[str, str]] = Field(default_factory=list)
    version: int = 1

class RubricEvaluator:
    def compute_stt_snapshot_hash(self, transcripts: List[Dict[str, Any]]) -> str:
        """
        [C1] Hard Rule: Compute hash from (turn_id, final_text) only.
        Raw transcripts are disposed after this call.
        """
        import json
        import hashlib
        
        # Sort by turn_id for ordering consistency - Section 1.4.2
        sorted_transcripts = sorted(transcripts, key=lambda x: x.get("turn_id", 0))
        
        # Map to canonical form - Section 1.4.2
        canonical_list = [{"id": t.get("turn_id"), "text": t.get("text")} for t in sorted_transcripts]
        
        payload = json.dumps(canonical_list, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    def compute_input_hash(self, context: EvaluationContext) -> str:
        """
        [C1] Single Source of Responsibility for Deterministic Hashing.
        Canonical Form: JSON sorted keys, separators=(',', ':'), UTF-8.
        """
        import json
        import hashlib
        
        # Prepare hashing payload - Section 1.2
        payload = {
            "resume_snapshot_hash": context.resume_snapshot_hash or "",
            "policy_snapshot_hash": context.policy_snapshot_hash or "",
            "context_history": context.context_history, # Already sorted by created_at in engine
            "stt_snapshot_hash": context.stt_snapshot_hash or "",
            "phase_flow": context.phase_flow,
            "version": context.version
        }
        
        # Canonicalization - Section 1.2
        canonical_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

    def evaluate(self, context: EvaluationContext, snapshot_weights: Optional[Dict[str, float]] = None) -> EvaluationResult:
        # ── TASK-035: Weight Sync Wiring ─────────────────────────────────
        # Flag OFF → identical to original behavior (uses legacy get_weights)
        if WiringFlags.weight_sync_active() and snapshot_weights is not None:
            # Snapshot weights EXIST: enforce Fail-Fast on any key mismatch
            missing = _REQUIRED_WEIGHT_KEYS - snapshot_weights.keys()
            unknown = snapshot_weights.keys() - _REQUIRED_WEIGHT_KEYS
            if missing or unknown:
                raise ValueError(
                    f"[Weight Fail-Fast] Snapshot weight key mismatch. "
                    f"Missing: {missing}, Unknown: {unknown}. "
                    f"HTTP 400 — no silent fallback permitted."
                )
            weights = snapshot_weights
        else:
            # Snapshot weights ABSENT → legacy fallback (with warning if flag is active)
            if WiringFlags.weight_sync_active() and snapshot_weights is None:
                import logging
                logging.getLogger("imh.eval").warning(
                    "[Weight Sync] snapshot_weights not provided — falling back to legacy get_weights()."
                )
            weights = get_weights(context.job_category)
        # ────────────────────────────────────────────────────────────────
        
        # 2. Calculate Category Scores
        
        # 2.1 Knowledge
        knowledge_score = calculate_knowledge_score(context.rag_keywords_found, context.ast_complexity)
        knowledge_item = RubricScoreItem(
            category="직무 역량",
            tag_code="capability.knowledge",
            score=knowledge_score,
            rationale=f"Keywords matched: {len(context.rag_keywords_found)}",
            evidence_data=EvidenceData(
                keyword_match=context.rag_keywords_found,
                ast_complexity=context.ast_complexity
            )
        )
        
        # 2.2 Problem Solving
        ps_score = calculate_problem_solving_score(context.hint_count)
        ps_item = RubricScoreItem(
            category="문제 해결",
            tag_code="capability.problem_solving",
            score=ps_score,
            rationale=f"Hints used: {context.hint_count}",
            evidence_data=EvidenceData(
                hint_count=context.hint_count,
                rephrasing_detected=context.rephrasing_detected
            )
        )
        
        # 2.3 Communication
        comm_score = calculate_communication_score(context.star_structure_detected)
        comm_item = RubricScoreItem(
            category="의사소통",
            tag_code="capability.communication",
            score=comm_score,
            rationale=f"STAR structure: {context.star_structure_detected}",
            evidence_data=EvidenceData(
                star_structure=context.star_structure_detected
            )
        )
        
        # 2.4 Attitude
        # Extract metrics from analysis dicts (Defensive extraction)
        gaze_pct = 0.0
        neg_emotion_pct = 0.0
        
        if context.visual_analysis:
            # Assuming imh_providers.visual result structure (TASK-010)
            # visual_analysis = {"gaze": {"center_ratio": 0.8}, ...}
            gaze_pct = context.visual_analysis.get("gaze", {}).get("center_ratio", 0.0) * 100.0
            
        if context.emotion_analysis:
            # Assuming imh_providers.emotion result structure (TASK-008)
            # emotion_analysis = {"time_series": [{"emotion": "fear"}, ...]}
            # For simplicity in mock, let's assume raw counts or list
            # But here we parse list of emotions
            emotions = [entry.get("emotion") for entry in context.emotion_analysis.get("time_series", [])]
            if emotions:
                neg_count = emotions.count("fear") + emotions.count("sad")
                neg_emotion_pct = (neg_count / len(emotions)) * 100.0
        
        attitude_score = calculate_attitude_score(gaze_pct, neg_emotion_pct)
        attitude_item = RubricScoreItem(
            category="태도/비언어",
            tag_code="capability.attitude",
            score=attitude_score,
            rationale=f"Gaze: {gaze_pct:.1f}%, NegEmotion: {neg_emotion_pct:.1f}%",
            evidence_data=EvidenceData(
                gaze_center_percent=gaze_pct,
                negative_emotion_percent=neg_emotion_pct
            )
        )
        
        # 3. Aggregate Total Score
        items = [knowledge_item, ps_item, comm_item, attitude_item]
        total_weighted_score = 0.0
        
        for item in items:
            # Use tag_code as key for weights
            weight = weights.get(item.tag_code, 0.0)
            total_weighted_score += item.score * weight
            
        return EvaluationResult(
            total_score=total_weighted_score,
            details=items,
            job_category=context.job_category,
            job_id=context.job_id,
            input_hash=self.compute_input_hash(context)  # Save hash in result
        )
