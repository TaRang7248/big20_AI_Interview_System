# IMPLEMENTATION PLAN - TASK-033 Phase 1: Interview Flow Performance Improvement

This plan focuses on optimizing the interview simulation engine to prevent context explosion and implement incremental scoring.

## 1. Context Optimization (Context-Fixed Structure)

Instead of passing the entire chat history, we will use a structured 'fixed context' for each turn generation.

### Input Composition:
- **Job Summary**: 5-8 lines summarizing the JD.
- **Resume Summary**: 5-8 lines summarizing the candidate's CV.
- **Interview State**: [opener/how/why/risk/boundary/summary].
- **Running Summary**: A concise summary of the interview progress so far.
- **Recent Turns**: Only the last 2 interactions.
- **Coverage Tracker**: Checklist of topics addressed (e.g., [x] Tech Depth, [ ] Trade-off).

## 2. Incremental Scoring & Ledger

Evaluation will be broken down into per-turn assessments to keep the evaluation context small.

- **Per-Turn Score**: Immediately after an answer, the LLM evaluates the *latest interaction* ONLY.
- **Ledger**: Accumulates per-turn scores and rationale.
- **Final Result**: Aggregated from the ledger at the end of the simulation.

## 3. Implementation Steps

### Task 1: Refactor `BenchmarkEngine.simulate_interview_flow`
- Initialize `running_summary`, `coverage_tracker`, and `ledger`.
- Define the 6-turn sequence.
- Loop through turns, constructing the minimized prompt.
- Perform incremental scoring in each turn.
- Proof of context size in logs.

### Task 2: Implement Final Aggregation
- Combine ledger entries into a final `score_data`.
- Support `final_score.json` output.

### Task 3: Smoke Verification
- Targeted run: `python scripts/benchmark_task_033.py --mode interview --models exaone3.5:2.4b` (modified to run 1 iteration of S1 only for smoke test).

## 4. Verification Criteria
- [ ] No "full history" injection in Turn 4, 5, 6.
- [ ] `ledger` populated correctly.
- [ ] Execution time remains stable across turns.
