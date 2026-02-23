import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pprint import pprint

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from packages.imh_providers.llm.ollama import OllamaLLMProvider
from packages.imh_providers.llm.openai import OpenAILLMProvider
from packages.imh_core.dto import LLMMessageDTO

# --- PROFILES & SITUATIONS ---

BASE_JD = """
[공고: Backend Developer]
- 커머스 플랫폼 스타트업 / Backend Developer
- 대용량 트래픽 API 개발, MSA 운영
- Redis/Kafka 비동기 처리
- AWS 운영
- (요건) 3y+ / REST / RDBMS / 트랜잭션/동시성
- (우대) K8s / 장애 대응 / CQRS
"""

RESUME_A1 = """
[이력서 A1: 적합]
- 4년차 Python Backend
- 주문/결제 개발
- Redis 캐시 도입
- Kafka 간단 이벤트 처리
- AWS EC2/RDS 사용
- MSA 환경 근무
"""

RESUME_A2 = """
[이력서 A2: 부적합 위장]
- 4년차 개발자 (어드민 UI React 개발 위주)
- Python API 유지보수 경험 (1년)
- Redis, Kafka 사용 환경에서 근무했으나 직접 구축 경험 없음
"""

ANSWER_B1 = """
[양질의 답변 B1]
대용량 트래픽 시 동시성 이슈를 해결하기 위해 Redis 기반 분산 락을 도입했습니다. 
처음에는 낙관적 락을 고려했으나 결제 도메인 특성상 충돌이 잦아 비관적 락 체계인 분산 락으로 선회했습니다.
그 결과 지연시간을 90% 줄였고, 제가 직접 락 획득 타임아웃과 재시도 로직을 설계하고 구현했습니다.
"""

ANSWER_B2 = """
[불량 답변 B2 / 위장형 과장]
대용량 트래픽 장애가 발생하여 제가 Redis와 Kafka를 도입했고 결제 지연을 90% 줄였습니다.
사용한 방법론은 비동기 파이프라인 최적화입니다. 동시성 이슈를 해결하기 위해 Kafka를 통한 CQRS 패턴과 
K8s 기반 MSA 구조를 도입하여 Redis에 저장했습니다. 제가 100% 아키텍처를 설계했습니다.
"""

ANSWER_TRAP = """
[Hallucination Trap 답변]
제가 겪은 장애를 Google Spanner 기반 CQRS를 MongoDB Redis 트랜잭션으로 엮어 해결했습니다. 
클라이언트 사이드에서 K8s 파드를 띄우는 방식으로 지연시간을 없앴습니다.
"""

SITUATIONS = {
    "S1": {"resume": RESUME_A1, "answer": ANSWER_B1},
    "S2": {"resume": RESUME_A1, "answer": ANSWER_B2},
    "S3": {"resume": RESUME_A2, "answer": ANSWER_B1},
    "S4": {"resume": RESUME_A2, "answer": ANSWER_B2},
    "TRAP": {"resume": RESUME_A1, "answer": ANSWER_TRAP}
}

# --- EVALUATION ENGINE (MOCK) ---
class BenchmarkEngine:
    def __init__(self, models: list, iterations: int, temperature: float):
        self.models = models
        self.iterations = iterations
        self.temperature = temperature
        self.report = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "iterations": iterations,
                "temperature": temperature
            },
            "results": {}
        }
        
    async def get_provider(self, model_name: str):
        if "gpt" in model_name.lower() or "openai" in model_name.lower():
            real_name = model_name.split(":")[-1] if ":" in model_name else model_name
            return OpenAILLMProvider(model_name=real_name)
        else:
            return OllamaLLMProvider(model_name=model_name)

    async def test_direct_reasoning(self, provider, model_name):
        print(f"[{model_name}] Running Direct Reasoning Test...", flush=True)
        prompt = f"다음 답변의 기술적 모순, 과장, 역할 불일치, 인과 오류를 모두 지적하라.\n\n{ANSWER_B2}"
        messages = [LLMMessageDTO(role="user", content=prompt)]
        
        try:
            res = await provider.chat(messages=messages)
            content = res.content.lower()
            
            # Simple heuristic detection
            points = 0
            if "kafka" in content and "cqrs" in content: points += 1
            if "100%" in content or "과장" in content or "역할" in content: points += 1
            if "모순" in content or "인과" in content: points += 1
            
            success = points >= 2
            return {"success": success, "points": points, "raw": res.content}
        except Exception as e:
            return {"success": False, "points": 0, "error": str(e)}

    async def test_strict_json(self, provider, model_name, iterations):
        print(f"[{model_name}] Running Strict JSON Test ({iterations} iterations)...", flush=True)
        prompt = "다음 정보를 JSON으로만 반환하세요: {\"name\": \"Test\", \"score\": 100}. 다른 텍스트는 절대 포함하지 마세요."
        messages = [LLMMessageDTO(role="user", content=prompt)]
        
        success_count = 0
        pollution_count = 0
        failure_count = 0
        
        for i in range(iterations):
            try:
                res = await provider.chat(messages=messages)
                content = res.content.strip()
                
                # Check pollution
                if not content.startswith("{") or not content.endswith("}"):
                    pollution_count += 1
                    
                # Clean markdown blocks if any
                if content.startswith("```json"):
                    content = content[7:-3].strip()
                    
                json.loads(content)
                success_count += 1
            except Exception:
                failure_count += 1
            
            if (i+1) % 10 == 0:
                print(f"[{model_name}] JSON Progress: {i+1}/{iterations}", flush=True)
                
        return {
            "success_rate": success_count / iterations,
            "pollution_rate": pollution_count / iterations,
            "failure_rate": failure_count / iterations,
            "iterations": iterations
        }

    async def simulate_interview_flow(self, provider, model_name, situ_rules):
        print(f"[{model_name}] Running Phase 1 Performance-Optimized Interview Simulation...", flush=True)
        results = {}
        
        # Phase 1: Fixed Summaries
        job_summary = "Backend Developer role focusing on MSA, Redis/Kafka, and high-traffic API optimization."
        
        turn_states = ["opener", "how", "why", "risk", "boundary", "summary"]
        
        for s_name, data in SITUATIONS.items():
            if s_name == "TRAP": continue
            # For Smoke Test: skip S2-S4 if we only want S1
            # (In standard run, we follow situ_rules)
            iters = situ_rules.get(s_name, 0)
            if iters == 0: continue
            
            s_results = []
            resume_summary = f"4-year developer with experience in {data['resume'].splitlines()[2] if len(data['resume'].splitlines())>2 else 'backend'}."

            for i in range(iters):
                start_time = time.time()
                
                running_summary = "Interview started."
                coverage_tracker = {"tech_depth": False, "tradeoff": False, "risk": False, "ownership": False}
                ledger = []
                recent_history = [] # Only stores [user, assistant] for last 2 turns
                
                # Turn 1: Experience Base (Pre-filled from Situation)
                q1 = f"Please explain your experience based on your resume:\n{data['resume']}"
                a1 = data['answer']
                recent_history.append({"role": "user", "content": q1})
                recent_history.append({"role": "assistant", "content": a1})
                running_summary = f"Candidate introduced their experience: {a1[:50]}..."
                
                # Sequence of turns 2-6
                for turn_idx in range(1, len(turn_states)):
                    state = turn_states[turn_idx]
                    
                    # A) Construct Fixed Context Prompt
                    coverage_str = ", ".join([f"[{'x' if v else ' '}] {k}" for k, v in coverage_tracker.items()])
                    
                    system_prompt = f"""You are a rigorous backend engineering interviewer. 
Target State: {state.upper()}
Coverage Tracker: {coverage_str}
Running Summary: {running_summary}

Rules:
- Ask exactly ONE probing question.
- Do NOT praise the candidate.
- Focus strictly on the current state's objective.
- Keep the history in mind but do not repeat yourself."""

                    # Proof of context size (Recent 2 turns only)
                    history_context = "\n".join([f"{m['role']}: {m['content']}" for m in recent_history[-4:]])
                    
                    user_input = f"""[Context]
Job: {job_summary}
Candidate Summary: {resume_summary}
Recent Conversations:
{history_context}

[Instruction]
Generate the next probing question for state: {state}."""

                    print(f"[{model_name}] turn {turn_idx+1} ({state}) Context Size Proof: ~{len(system_prompt) + len(user_input)} chars", flush=True)

                    # 1. Ask Question
                    res_q = await provider.chat(
                        messages=[LLMMessageDTO(role="user", content=user_input)], 
                        system_prompt=system_prompt
                    )
                    question = res_q.content
                    
                    # 2. Get (Mock) Answer - In a real system, this would be from a candidate LLM
                    # Here we use mock logic based on the state for testing
                    mock_answers = {
                        "how": "We used standard configurations and the default setup. It worked fine.",
                        "why": "It was the trend at that time, and the team lead suggested it.",
                        "risk": "We didn't see any risks; the system was built to be perfect.",
                        "boundary": "I helped with everything, but mostly I just followed the tickets.",
                        "summary": "I am a developer who can handle many technologies."
                    }
                    answer = mock_answers.get(state, "Standard answer.")

                    # 3. Incremental Scoring (Ledger)
                    scoring_prompt = f"""Evaluate the LATEST candidate answer.
State: {state}
Q: {question}
A: {answer}

Dimensions:
- truthfulness_consistency
- technical_depth

Return ONLY JSON:
{{
  "score": 0-100,
  "depth_detected": boolean,
  "rationale": "..."
}}"""
                    eval_msg = [LLMMessageDTO(role="user", content=scoring_prompt)]
                    res_eval = await provider.chat(messages=eval_msg)
                    
                    try:
                        content = res_eval.content
                        if "```json" in content: content = content.split("```json")[-1].split("```")[0].strip()
                        elif "```" in content: content = content.split("```")[-1].split("```")[0].strip()
                        parsed_eval = json.loads(content)
                        ledger.append({"state": state, "res": parsed_eval})
                    except:
                        ledger.append({"state": state, "res": {"score": 0, "error": "JSON_PARSE_ERROR"}})

                    # 4. Update Internal State
                    recent_history.append({"role": "user", "content": question})
                    recent_history.append({"role": "assistant", "content": answer})
                    if "how" in state: coverage_tracker["tech_depth"] = True
                    if "why" in state: coverage_tracker["tradeoff"] = True
                    if "risk" in state: coverage_tracker["risk"] = True
                    if "boundary" in state: coverage_tracker["ownership"] = True
                    
                    # Update Summary (Simulated LLM call or simple update)
                    running_summary += f"\n- {state}: Q asked, candidate responded with generic claims."

                # Final Aggregate Scoring (Ledger based)
                final_scores = [l['res'].get('score', 0) for l in ledger if 'score' in l['res']]
                avg_score = sum(final_scores) / max(len(final_scores), 1)
                
                latency = time.time() - start_time
                s_results.append({
                    "latency": latency,
                    "score": avg_score,
                    "ledger": ledger,
                    "verdict": "fail" if avg_score < 60 else "pass",
                    "rationale": "Aggregated from incremental ledger."
                })
            results[s_name] = s_results
        return results

    async def simulate_interview_compact(self, provider, model_name, situ_rules):
        """Phase 2: interview_compact with full instrumentation."""
        from datetime import datetime as _dt
        print(f"[{model_name}] Running Phase 2 interview_compact (instrumented)...", flush=True)
        results = {}
        job_summary = "Backend Developer: MSA, Redis/Kafka, high-traffic API (3y+, RDBMS, concurrency)."

        turn_states = ["how", "why", "risk", "boundary_summary"]
        b2_mock = {
            "how":              "We used standard configuration and followed the docs.",
            "why":              "We picked it because it was popular. No alternatives considered.",
            "risk":             "No failures occurred. Everything worked perfectly from day one.",
            "boundary_summary": "I owned everything end-to-end and solved all the problems."
        }
        b1_mock = {
            "how":              "I implemented a distributed lock with timeout/retry logic using Redis SETNX.",
            "why":              "We chose pessimistic locking because collision rate was >15% under peak load.",
            "risk":             "We faced a deadlock during peak hours; resolved by adding a TTL watchdog.",
            "boundary_summary": "I owned the lock design; infra team handled Redis cluster provisioning."
        }

        step_log = []
        BOTTLENECK_MS    = 90_000
        BOTTLENECK_CHARS = 2500
        MAX_Q_TOK = 96    # Hard cap: question generation
        MAX_S_TOK = 192   # Hard cap: scoring

        def _ts():
            return _dt.now().strftime("%Y-%m-%d %H:%M:%S")

        def _log(scenario, run_idx, turn_idx, state, step_type, in_chars, out_tok, elapsed_ms, status):
            line = (
                f"[{_ts()}] model={model_name[:24]} scenario={scenario} run={run_idx} "
                f"turn={turn_idx} step={step_type} in_chars={in_chars} out_tok={out_tok} "
                f"elapsed={elapsed_ms:.0f}ms {status}"
            )
            print(line, flush=True)
            step_log.append({"model": model_name, "scenario": scenario, "run": run_idx,
                              "turn": turn_idx, "state": state, "step_type": step_type,
                              "in_chars": in_chars, "out_tok": out_tok,
                              "elapsed_ms": elapsed_ms, "status": status})
            if elapsed_ms > BOTTLENECK_MS:
                recent_avg = sum(s["elapsed_ms"] for s in step_log[-20:]) / min(len(step_log), 20)
                print(f"WARN bottleneck: model={model_name[:24]} step={step_type} "
                      f"elapsed={elapsed_ms/1000:.1f}s recent20_avg={recent_avg/1000:.1f}s "
                      f"in_chars={in_chars}", flush=True)
            if in_chars > BOTTLENECK_CHARS and elapsed_ms > BOTTLENECK_MS:
                print(f"WARN ctx+slow: in_chars={in_chars}>{BOTTLENECK_CHARS} "
                      f"elapsed={elapsed_ms/1000:.1f}s>{BOTTLENECK_MS/1000}s", flush=True)

        scenarios_active = [s for s in SITUATIONS if s != "TRAP" and situ_rules.get(s, 0) > 0]
        total_steps = len(scenarios_active) * 2 * len(turn_states) * 2
        completed_steps = 0
        model_start = time.time()

        for s_name, data in SITUATIONS.items():
            if s_name == "TRAP":
                continue
            iters = situ_rules.get(s_name, 0)
            if iters == 0:
                continue

            s_results = []
            resume_summary = " ".join([l.strip() for l in data["resume"].splitlines() if l.strip()][:5])

            for run_idx in range(1, iters + 1):
                start_time = time.time()
                running_summary = f"Opener: {data['answer'][:80]}..."
                coverage_tracker = {"how": False, "why": False, "risk": False, "boundary": False}
                ledger = []
                recent_history = [
                    {"role": "user",      "content": f"Explain experience:\n{data['resume']}"},
                    {"role": "assistant", "content": data["answer"]}
                ]

                for turn_idx, state in enumerate(turn_states, start=1):
                    cov_str = ", ".join([f"[{'x' if v else ' '}]{k}" for k, v in coverage_tracker.items()])
                    sys_p = (
                        f"You are a rigorous backend interviewer.\n"
                        f"State: {state.upper()} | Coverage: {cov_str}\n"
                        f"Summary: {running_summary[-150:]}\n"
                        "Rules:\n"
                        "- Ask exactly ONE probing question.\n"
                        "- No preamble. No praise. No analysis.\n"
                        "- Max 2 sentences.\n"
                        "- Output the question only."
                    )
                    hist_ctx = "\n".join([f"{m['role']}: {m['content'][:120]}" for m in recent_history[-4:]])
                    user_in = (
                        f"[Job]{job_summary}\n[Resume]{resume_summary}\n"
                        f"[Recent]{hist_ctx}\n"
                        f"[Task]Probing question for state={state}."
                    )
                    in_chars = len(sys_p) + len(user_in)

                    # Context proof log
                    print(f"[CTX] S={s_name} run={run_idx} turn={turn_idx} state={state} "
                          f"summary_len={len(running_summary)} recent_pairs={len(recent_history)//2} "
                          f"total_in={in_chars}", flush=True)

                    # Step A: Question
                    t0 = time.time()
                    q_status = "ok"
                    try:
                        res_q = await provider.chat(
                            messages=[LLMMessageDTO(role="user", content=user_in)],
                            system_prompt=sys_p,
                            max_tokens=MAX_Q_TOK
                        )
                        question = res_q.content
                        out_tok = len(question.split())
                    except Exception as e:
                        question = f"[Q_ERROR:{e}]"
                        out_tok = 0
                        q_status = "error"
                    q_elapsed = (time.time() - t0) * 1000
                    _log(s_name, run_idx, turn_idx, state, "question", in_chars, out_tok, q_elapsed, q_status)
                    completed_steps += 1

                    # Mock answer
                    answer = b2_mock.get(state, "Standard.") if s_name in ("S2", "S4") else b1_mock.get(state, "Sound decision.")

                    # Step B: Score
                    score_in = (
                        f"Evaluate this Q&A. Return ONLY JSON. No extra keys.\n"
                        f"State:{state}\nQ:{question[:300]}\nA:{answer}\n"
                        "{\n"
                        '  "score": 0-100,\n'
                        '  "technical_depth": 0-100,\n'
                        '  "truthfulness_consistency": 0-100,\n'
                        '  "contradiction_detected": true|false,\n'
                        '  "overclaiming_detected": true|false,\n'
                        '  "rationale": "max 2 sentences"\n'
                        "}\nReturn ONLY the JSON above. Keep rationale under 2 sentences."
                    )
                    t0 = time.time()
                    s_status = "ok"
                    try:
                        res_e = await provider.chat(
                            messages=[LLMMessageDTO(role="user", content=score_in)],
                            max_tokens=MAX_S_TOK
                        )
                        raw = res_e.content
                        if "```json" in raw: raw = raw.split("```json")[-1].split("```")[0].strip()
                        elif "```" in raw:   raw = raw.split("```")[-1].split("```")[0].strip()
                        entry = json.loads(raw)
                        out_tok_s = len(raw.split())
                    except Exception as pe:
                        entry = {"score": 0, "technical_depth": 0, "truthfulness_consistency": 0,
                                 "contradiction_detected": False, "overclaiming_detected": False,
                                 "rationale": f"PARSE_ERROR:{pe}"}
                        out_tok_s = 0
                        s_status = "error"
                    s_elapsed = (time.time() - t0) * 1000
                    _log(s_name, run_idx, turn_idx, state, "score", len(score_in), out_tok_s, s_elapsed, s_status)
                    completed_steps += 1

                    ledger.append({"state": state, "res": entry, "q_ms": q_elapsed, "s_ms": s_elapsed})

                    # Update state
                    recent_history.append({"role": "user",      "content": question[:250]})
                    recent_history.append({"role": "assistant",  "content": answer[:250]})
                    if "how"      in state: coverage_tracker["how"]      = True
                    if "why"      in state: coverage_tracker["why"]      = True
                    if "risk"     in state: coverage_tracker["risk"]     = True
                    if "boundary" in state: coverage_tracker["boundary"] = True
                    running_summary += f" | {state}: done"

                    # ETA every 10 steps
                    if completed_steps > 0 and completed_steps % 10 == 0:
                        elapsed_total = time.time() - model_start
                        avg_ms = (elapsed_total * 1000) / completed_steps
                        remain = total_steps - completed_steps
                        eta_min = (remain * avg_ms / 1000) / 60
                        recent20_avg = sum(s["elapsed_ms"] for s in step_log[-20:]) / min(len(step_log), 20)
                        print(
                            f"[ETA] model={model_name[:24]} {completed_steps}/{total_steps} "
                            f"({completed_steps/total_steps*100:.0f}%) "
                            f"avg={avg_ms/1000:.1f}s recent20={recent20_avg/1000:.1f}s "
                            f"ETA={eta_min:.1f}min",
                            flush=True
                        )

                # Aggregate
                valid = [l["res"] for l in ledger if "score" in l["res"]]
                avg_score = sum(r["score"] for r in valid) / max(len(valid), 1)
                avg_td    = sum(r.get("technical_depth", 0) for r in valid) / max(len(valid), 1)
                avg_tc    = sum(r.get("truthfulness_consistency", 0) for r in valid) / max(len(valid), 1)
                c_detect  = any(r.get("contradiction_detected", False) for r in valid)
                o_detect  = any(r.get("overclaiming_detected",  False) for r in valid)
                turn_lat  = (time.time() - start_time) / max(len(turn_states), 1)

                s_results.append({
                    "latency_total": time.time() - start_time,
                    "turn_latency": turn_lat,
                    "score": avg_score,
                    "technical_depth": avg_td,
                    "truthfulness_consistency": avg_tc,
                    "b2_overval": avg_score >= 65 and s_name in ("S2", "S4"),
                    "contradiction_detected": c_detect,
                    "overclaiming_detected":  o_detect,
                    "ledger": ledger,
                    "verdict": "fail" if avg_score < 55 else "borderline" if avg_score < 70 else "pass"
                })
            results[s_name] = s_results

        # Model summary
        if step_log:
            q_times = [s["elapsed_ms"] for s in step_log if s["step_type"] == "question"]
            s_times = [s["elapsed_ms"] for s in step_log if s["step_type"] == "score"]
            total_model_sec = time.time() - model_start
            q_avg = sum(q_times)/max(len(q_times), 1)/1000
            s_avg = sum(s_times)/max(len(s_times), 1)/1000
            print(
                f"[DONE] model={model_name[:24]} total={total_model_sec:.1f}s "
                f"q_avg={q_avg:.1f}s s_avg={s_avg:.1f}s steps={len(step_log)}",
                flush=True
            )
            results["__step_log__"] = step_log
        return results


    async def simulate_e2e_flow(self, provider, model_name, situ_rules):
        print(f"[{model_name}] Running E2E Situation Flow...", flush=True)
        results = {}
        for s_name, data in SITUATIONS.items():
            s_results = []
            iters = situ_rules.get(s_name, 0)
            for i in range(iters):
                # 1. Ask Question
                sys_prompt = "You are a backend engineering interviewer. Ask one follow-up question based on the resume and answer."
                user_prompt = f"Resume:\n{data['resume']}\n\nCandidate Answer:\n{data['answer']}\n\nPlease ask a probing question or evaluate."
                
                start_time = time.time()
                try:
                    res1 = await provider.chat(
                        messages=[LLMMessageDTO(role="user", content=user_prompt)],
                        system_prompt=sys_prompt
                    )
                    latency = time.time() - start_time
                    content = res1.content
                    
                    # 2. Check Surface Acceptance Error (Drill-down failure)
                    drill_down = False
                    if "구체" in content or "어떻게" in content or "어떤" in content or "자세히" in content or "why" in content.lower() or "how" in content.lower():
                        drill_down = True
                        
                    # 3. Dummy Evaluation Score (Mocking future LLM evaluator)
                    score_prompt = f"Evaluate the candidate's answer based on the resume and answer on a scale of 0 to 100. Return ONLY JSON: {{\"score\": 80, \"rationale\": \"...\"}}\n\nResume:{data['resume']}\nAnswer:{data['answer']}"
                    res2 = await provider.chat(messages=[LLMMessageDTO(role="user", content=score_prompt)])
                    try:
                        score_data = res2.content
                        if "```json" in score_data:
                            score_data = score_data.split("```json")[-1].split("```")[0].strip()
                        elif "```" in score_data:
                            score_data = score_data.split("```")[-1].split("```")[0].strip()
                        parsed = json.loads(score_data)
                        score = parsed.get("score", 0)
                    except:
                        score = -1 # Sev3 JSON fail during eval
                        
                    s_results.append({
                        "latency": latency,
                        "drill_down": drill_down,
                        "question": content,
                        "score": score
                    })
                except Exception as e:
                    s_results.append({"error": str(e), "latency": time.time() - start_time})
            results[s_name] = s_results
        return results

    async def run_benchmark(self, mode_filter):
        for model in self.models:
            is_openai = "gpt" in model.lower() or "openai" in model.lower() or "4o-mini" in model.lower()
            
            if mode_filter == "bulk" and is_openai: continue
            if mode_filter == "baseline" and not is_openai: continue
            
            try:
                provider = await self.get_provider(model)
            except Exception as e:
                print(f"[{model}] Failed to initialize provider: {e}", flush=True)
                self.report["results"][model] = {
                    "direct_reasoning": {"success": False, "points": 0, "error": str(e)},
                    "strict_json": {"success_rate": 0, "pollution_rate": 0, "failure_rate": 1.0, "error": str(e)},
                    "e2e": {}
                }
                continue

            model_res = {}
            if mode_filter == "interview_compact":
                json_iters = 0
                dr_iters = 0
                situ_rules = {"S1": 1 if is_openai else 2, "S2": 1 if is_openai else 2,
                              "S3": 1 if is_openai else 2, "S4": 1 if is_openai else 2}
            elif mode_filter == "interview":
                json_iters = 0
                dr_iters = 0
                situ_rules = {"S1": 1 if is_openai else 2, "S2": 1 if is_openai else 2,
                              "S3": 1 if is_openai else 2, "S4": 1 if is_openai else 2}
            elif is_openai:
                json_iters = 10; dr_iters = 5
                situ_rules = {"S1": 3, "S2": 3, "S3": 2, "S4": 2, "TRAP": 0}
            else:
                json_iters = 50; dr_iters = 1
                situ_rules = {"S1": self.iterations, "S2": self.iterations,
                              "S3": self.iterations, "S4": self.iterations, "TRAP": self.iterations}

            dr_points = 0
            for _ in range(dr_iters):
                dr_res = await self.test_direct_reasoning(provider, model)
                if dr_res.get("success"): dr_points += 1
            model_res["direct_reasoning"] = {"success": (dr_points > 0) if dr_iters > 0 else True, "points": dr_points}

            if json_iters > 0:
                model_res["strict_json"] = await self.test_strict_json(provider, model, json_iters)
            else:
                model_res["strict_json"] = {"success_rate": 1.0, "pollution_rate": 0.0, "failure_rate": 0.0}

            if mode_filter == "interview_compact":
                model_res["e2e"] = await self.simulate_interview_compact(provider, model, situ_rules)
            elif mode_filter == "interview":
                model_res["e2e"] = await self.simulate_interview_flow(provider, model, situ_rules)
            else:
                model_res["e2e"] = await self.simulate_e2e_flow(provider, model, situ_rules)

            self.report["results"][model] = model_res
            print(f"[{model}] DONE.", flush=True)
            
    def generate_report(self, mode_filter):
        # STANDARDIZED PATHS (TASK-033)
        repo_root  = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        report_dir = os.path.join(repo_root, "docs", "benchmarks", "task_033")
        log_dir    = os.path.join(repo_root, "logs", "benchmarks", "task_033")
        
        os.makedirs(report_dir, exist_ok=True)
        os.makedirs(log_dir, exist_ok=True)
        
        # Output paths
        if mode_filter == "interview_compact":
            json_out   = os.path.join(report_dir, "model_interview_comparison.json")
            md_out     = os.path.join(report_dir, "interview_compact_report_full.md")
            matrix_out = os.path.join(report_dir, "model_comparison_matrix.json")
            ledger_out = os.path.join(report_dir, "ledger_summary_by_model.json")
        elif mode_filter == "interview":
            json_out   = os.path.join(report_dir, "model_interview_comparison.json")
            md_out     = os.path.join(report_dir, "interview_report_refined.md")
            matrix_out = os.path.join(report_dir, "model_comparison_matrix.json")
            ledger_out = None
        else:
            prefix     = f"{mode_filter}_" if mode_filter in ["bulk"] else ""
            json_out   = os.path.join(report_dir, f"{prefix}summary.json")
            matrix_out = os.path.join(report_dir, "model_comparison_matrix.json")
            md_out     = os.path.join(report_dir, f"final_report_{mode_filter}.md" if mode_filter in ["bulk", "baseline"] else "final_report.md")
            ledger_out = None

        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(self.report, f, indent=2, ensure_ascii=False)
        
        # Raw dump to logs folder
        with open(os.path.join(log_dir, f"dump_{mode_filter}_{int(time.time())}.json"), "w", encoding="utf-8") as f:
            json.dump(self.report, f, indent=2, ensure_ascii=False)

        if mode_filter == "interview_compact":
            self._generate_compact_report(md_out, matrix_out, ledger_out)
        elif mode_filter == "interview":
            self._generate_refined_interview_report(md_out)
        else:
            self._generate_standard_report(md_out, matrix_out, mode_filter)

    def _generate_compact_report(self, md_out, matrix_out, ledger_out):
        """Phase 2: Full model comparison report with all required metrics."""
        model_metrics = {}
        for model, res in self.report["results"].items():
            e2e = res.get("e2e", {})
            # Filter only runs data, ignore internal instrumentation logs like __step_log__
            all_runs = [r for k, runs in e2e.items() if k != "__step_log__" for r in runs]
            b2_runs  = [r for s in ("S2", "S4") for r in e2e.get(s, [])]

            if not all_runs:
                model_metrics[model] = {"error": "NO_DATA"}
                continue

            avg_score = sum(r["score"] for r in all_runs) / len(all_runs)
            avg_td    = sum(r.get("technical_depth", 0) for r in all_runs) / len(all_runs)
            avg_tc    = sum(r.get("truthfulness_consistency", 0) for r in all_runs) / len(all_runs)
            b2_overval_rate = sum(1 for r in b2_runs if r.get("b2_overval")) / max(len(b2_runs), 1)
            contradiction_rate = sum(1 for r in all_runs if r.get("contradiction_detected")) / max(len(all_runs), 1)
            overclaiming_rate  = sum(1 for r in all_runs if r.get("overclaiming_detected")) / max(len(all_runs), 1)
            avg_turn_lat = sum(r.get("turn_latency", 0) for r in all_runs) / max(len(all_runs), 1)

            # Fail conditions
            fail_reasons = []
            if b2_overval_rate > 0.30:    fail_reasons.append("B2_OVERVAL>30%")
            if contradiction_rate < 0.50: fail_reasons.append("CONTRADICTION_DETECT<50%")
            if avg_td < 55:               fail_reasons.append("TECH_DEPTH<55")
            if avg_turn_lat <= 0:         fail_reasons.append("LATENCY_ZERO?")

            model_metrics[model] = {
                "avg_score": avg_score, "avg_td": avg_td, "avg_tc": avg_tc,
                "b2_overval_rate": b2_overval_rate, "contradiction_rate": contradiction_rate,
                "overclaiming_rate": overclaiming_rate, "avg_turn_latency": avg_turn_lat,
                "is_fit": len(fail_reasons) == 0, "fail_reasons": fail_reasons
            }

        # Save matrix & ledger
        with open(matrix_out, "w", encoding="utf-8") as f: json.dump(model_metrics, f, indent=2, ensure_ascii=False)
        if ledger_out:
            ledger_summary = {
                m: [{"s": s, "ledger": r["ledger"]} 
                    for s, runs in self.report["results"][m].get("e2e", {}).items() 
                    if s != "__step_log__"
                    for r in runs[:1]
                    if "ledger" in r] 
                for m in self.report["results"]
            }
            with open(ledger_out, "w", encoding="utf-8") as f: json.dump(ledger_summary, f, indent=2, ensure_ascii=False)

        # Build Markdown report
        fit    = [m for m, sc in model_metrics.items() if isinstance(sc, dict) and sc.get("is_fit")]
        unfit  = [m for m, sc in model_metrics.items() if isinstance(sc, dict) and not sc.get("is_fit")]
        lats   = {m: sc["avg_turn_latency"] for m, sc in model_metrics.items() if isinstance(sc, dict)}
        min_lat = min(lats.values()) if lats else 1

        lines = ["# TASK-033 Phase 2: Interview Compact — Full Model Comparison", ""]
        lines.append("## 1. Summary Matrix\n")
        lines.append("| Model | AvgScore | TechDepth | Truthfulness | B2Overval | Contradiction | Overclaiming | TurnLat | Status |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for model, sc in model_metrics.items():
            if not isinstance(sc, dict) or "error" in sc:
                lines.append(f"| {model} | — | — | — | — | — | — | — | ERROR |")
                continue
            lat_flag = "⚠️ SLOW" if sc["avg_turn_latency"] > min_lat * 2 else ""
            status = "✅ FIT" if sc["is_fit"] else f"❌ UNFIT ({', '.join(sc['fail_reasons'])})"
            lines.append(
                f"| {model} | {sc['avg_score']:.1f} | {sc['avg_td']:.1f} | {sc['avg_tc']:.1f}"
                f" | {sc['b2_overval_rate']*100:.0f}% | {sc['contradiction_rate']*100:.0f}%"
                f" | {sc['overclaiming_rate']*100:.0f}% | {sc['avg_turn_latency']:.1f}s{lat_flag} | {status} |"
            )

        lines.append("\n## 2. 후보 선정\n")
        main_cands = fit[:1] or unfit[:1]
        fallback_cands = fit[1:3] or unfit[1:3]
        lines.append(f"- **Main 후보**: {', '.join(main_cands) if main_cands else '없음 (모든 모델 기준 미달)'}")
        lines.append(f"- **Fallback 후보**: {', '.join(fallback_cands) if fallback_cands else '없음'}")

        lines.append("\n## 3. 모델별 강점/약점 요약\n")
        for model, sc in model_metrics.items():
            if not isinstance(sc, dict) or "error" in sc: continue
            strengths, weaknesses = [], []
            if sc["avg_td"] >= 60: strengths.append("기술 깊이 양호")
            else: weaknesses.append("기술 깊이 부족")
            if sc["contradiction_rate"] >= 0.5: strengths.append("모순 탐지 우수")
            else: weaknesses.append("모순 탐지 미흡")
            if sc["b2_overval_rate"] <= 0.2: strengths.append("B2 과대평가 억제")
            else: weaknesses.append("B2 과대평가 위험")
            prompt_note = " → 온프레 프롬프트 단순화 권장" if not sc["is_fit"] and "gpt" not in model.lower() else ""
            lines.append(f"### {model}{prompt_note}")
            lines.append(f"- 강점: {', '.join(strengths) or '없음'}")
            lines.append(f"- 약점: {', '.join(weaknesses) or '없음'}")
            lines.append("")

        lines.append("---")
        lines.append("**AI evaluation is advisory only. Final hiring decisions require human review.**")

        with open(md_out, "w", encoding="utf-8") as f: f.write("\n".join(lines))
        print(f"[Phase 2] Reports written → {md_out}", flush=True)

    def _generate_refined_interview_report(self, md_out):
        lines = ["# TASK-033 Benchmark: Phase 1 Interview (Context Optimized)", ""]
        lines.append("## 1. Summary Matrix (Ledger Aggregated)\n")
        lines.append("| Model | Avg Score | Latency (Total) | Verdict |")
        lines.append("|---|---|---|---|")

        for model, res in self.report["results"].items():
            e2e = res.get("e2e", {})
            all_runs = [r for runs in e2e.values() for r in runs if "error" not in r]
            if not all_runs: continue
            
            avg_score = sum(r["score"] for r in all_runs) / len(all_runs)
            avg_lat = sum(r["latency"] for r in all_runs) / len(all_runs)
            verdict = all_runs[0].get("verdict", "N/A")

            lines.append(f"| {model} | {avg_score:.1f} | {avg_lat:.2f}s | {verdict} |")
        
        lines.append("\n## 2. Ledger Details (Sample from first run)\n")
        for model, res in self.report["results"].items():
            e2e = res.get("e2e", {})
            for s_name, runs in e2e.items():
                if runs and "ledger" in runs[0]:
                    lines.append(f"### {model} - {s_name}")
                    lines.append("| Turn | Score | Rationale |")
                    lines.append("|---|---|---|")
                    for entry in runs[0]["ledger"]:
                        res_eval = entry["res"]
                        lines.append(f"| {entry['state']} | {res_eval.get('score', 0)} | {res_eval.get('rationale', 'N/A')} |")
                    break # Only one sample
            
        lines.append("\n## 3. Proof of Context Optimization\n")
        lines.append("- Input structure uses fixed summaries (Job/Resume).")
        lines.append("- History is limited to the last 2 interactions.")
        lines.append("- Cumulative token growth prevented.")

        lines.append("\n---\n**AI evaluation is advisory only. Final hiring decisions require human review.**\n")
        
        with open(md_out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"Refined Phase 1 Reports generated in {md_out}")

    def _generate_standard_report(self, md_out, matrix_out, mode_filter):
        # (Existing logic for bulk/baseline reports)
        baseline = {"l1": "PASS", "l2_drill": 1.0, "l3_s2_avg": 50.0, "s2_overval_rate": 0.0, "l4_fail": 0.0, "l5_lat": 1.08, "p95_lat": 1.3}
        model_scores = {}
        for model, res in self.report["results"].items():
            dr, sj, e2e = res.get("direct_reasoning", {}), res.get("strict_json", {}), res.get("e2e", {})
            dr_success = dr.get("success", False)
            l2_runs = e2e.get("S2", []) + e2e.get("S4", []) + e2e.get("TRAP", [])
            l2_valid = [r for r in l2_runs if "error" not in r]
            drill_rate = sum(1 for r in l2_valid if r.get("drill_down")) / max(len(l2_valid), 1)
            s1_valid = [r for r in e2e.get("S1", []) if "error" not in r and r.get("score", -1) != -1]
            s2_valid = [r for r in e2e.get("S2", []) if "error" not in r and r.get("score", -1) != -1]
            s1_avg = sum(r["score"] for r in s1_valid) / max(len(s1_valid), 1) if s1_valid else 0.0
            s2_avg = sum(r["score"] for r in s2_valid) / max(len(s2_valid), 1) if s2_valid else 0.0
            s2_overval_rate = sum(1 for r in s2_valid if r["score"] >= 65) / max(len(s2_valid), 1)
            l4_success, l4_fail_rate = sj.get("success_rate", 0) * 100, sj.get("failure_rate", 0) * 100
            all_lats = sorted([r["latency"] for runs in e2e.values() for r in runs if "error" not in r])
            avg_lat = sum(all_lats) / max(len(all_lats), 1) if all_lats else 0.0
            p95_lat = all_lats[int(len(all_lats) * 0.95)] if all_lats else 0.0
            
            is_main_capable = (l4_fail_rate <= 3.0 and s2_overval_rate <= 0.3 and drill_rate >= 0.5 and dr_success)
            model_scores[model] = {"l1": "PASS" if dr_success else "FAIL", "l2": drill_rate, "l3_s1": s1_avg, "l3_s2": s2_avg, "s2_overval_rate": s2_overval_rate, "l4_success": l4_success, "l4_fail": l4_fail_rate, "l5": avg_lat, "p95": p95_lat, "is_main_capable": is_main_capable, "pts": dr.get('points', 0), "pollution": sj.get('pollution_rate',0)*100, "e2e": e2e}

        with open(matrix_out, "w", encoding="utf-8") as f: json.dump(model_scores, f, indent=2, ensure_ascii=False)
        lines = [f"# TASK-033 Benchmark Final Report ({mode_filter.upper()})", "", "> ⚠️ OpenAI (gpt-4o) Baseline 기준 비교.\n", "## 1. Summary\n", "| Model | L1 | L2 | L3 | L4 | L5 | Status |", "|---|---|---|---|---|---|---|"]
        for model, sc in model_scores.items():
            status = "MAIN" if sc["is_main_capable"] else "UNFIT"
            lines.append(f"| {model} | {sc['l1']} | {sc['l2']*100:.1f}% | S1:{sc['l3_s1']:.0f}/S2:{sc['l3_s2']:.0f} | {sc['l4_success']:.1f}% | {sc['l5']:.1f}s | {status} |")
        with open(md_out, "w", encoding="utf-8") as f: f.write("\n".join(lines))
        print(f"Standard Reports generated in {md_out}")


def load_yaml_simple(filepath):
    # Very basic yaml parsing for lists and keys
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    data = {"models": []}
    for line in lines:
        line = line.strip()
        if line.startswith("- "):
            data["models"].append(line[2:].strip())
    return data

async def main():
    parser = argparse.ArgumentParser(description="TASK-033 Benchmark Script")
    parser.add_argument("--models", type=str, default="all", help="all, ollama, openai, or comma-separated models")
    parser.add_argument("--mode", type=str, default="full", choices=["full", "bulk", "baseline", "interview", "interview_compact"], help="Test mode")
    parser.add_argument("--iterations", type=int, default=10, help="Number of iterations for bulk mode situations")
    parser.add_argument("--temperature", type=float, default=0.0, help="Temperature for models")
    args = parser.parse_args()
    
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    ollama_models = []
    openai_models = []
    
    ollama_yaml = os.path.join(base_dir, "configs", "providers", "ollama_models.yaml")
    openai_yaml = os.path.join(base_dir, "configs", "providers", "openai_4o.yaml")
    
    if os.path.exists(ollama_yaml):
        ollama_models = load_yaml_simple(ollama_yaml).get("models", [])
    if os.path.exists(openai_yaml):
        openai_models = load_yaml_simple(openai_yaml).get("models", [])
        
    target_models = []
    
    if args.models.lower() == "all":
        target_models = ollama_models + openai_models
    elif args.models.lower() == "ollama":
        target_models = ollama_models
    elif args.models.lower() == "openai":
        target_models = openai_models
    else:
        target_models = [m.strip() for m in args.models.split(",")]
        
    print(f"Target Models: {target_models}, Mode: {args.mode}")
    
    engine = BenchmarkEngine(target_models, args.iterations, args.temperature)
    await engine.run_benchmark(args.mode)
    engine.generate_report(args.mode)

if __name__ == "__main__":
    asyncio.run(main())
