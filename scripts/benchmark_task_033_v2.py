import argparse
import asyncio
import json
import os
import sys
import time
import statistics
import traceback
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from packages.imh_providers.llm.ollama import OllamaLLMProvider
from packages.imh_providers.llm.openai import OpenAILLMProvider
from packages.imh_core.dto import LLMMessageDTO

MODELS = [
    "cookieshake/a.x-4.0-light-imatrix:iq2_m",
    "kwangsuklee/Qwen3-kor-4B-Q4_K_M",
    "timHan/llama3.2korean3B4QKM",
    "exaone3.5:2.4b"
]

RESUME_TEXT = """
[이력서: Backend Developer]
- 4년차 Python Backend 개발자
- 주문 및 결제 도메인 API 개발
- 대용량 트래픽 최적화 경험 (결제 지연시간 90% 단축)
- Redis 기반 분산 락 및 캐싱 시스템 도입
- Kafka를 활용한 비동기 이벤트 처리
- AWS 인프라(EC2, RDS) 및 MSA 아키텍처 환경 근무
"""

JOB_POSTING_TEXT = """
[채용 공고: Backend Developer]
- 커머스 플랫폼 백엔드 시스템 개발 및 유지보수
- 대용량 트래픽 대응을 위한 시스템 아키텍처 설계
- RESTful API 구축 및 RDBMS 기반 데이터 모델링
- 동시성/트랜잭션 문제 해결
- 자격요건: 백엔드 개발 경력 3년 이상
- 우대사항: Redis, Kafka, K8s 경험자
"""

# [P3-FIX] Resume keywords grouped by category + Korean/English synonyms
RESUME_KW_PROJECT = ["주문", "결제", "커머스", "도메인", "api"]
RESUME_KW_TECH = ["python", "redis", "레디스", "kafka", "카프카", "aws", "ec2", "rds",
                  "msa", "분산 락", "캐싱", "비동기", "이벤트"]
RESUME_KW_RESULT = ["트래픽", "지연시간", "90%", "단축", "최적화", "대용량"]
ALL_RESUME_KW = RESUME_KW_PROJECT + RESUME_KW_TECH + RESUME_KW_RESULT

# [P3-FIX] Drill-down depth keywords (beyond simple "왜/어떻게")
DRILL_DEPTH_KW = ["수치", "로그", "지표", "장애", "트레이드오프", "원인", "재현",
                  "구체적", "왜", "어떻게", "사례", "근거", "증거", "데이터"]

# [P4-FIX] B2 intent verification patterns
B2_EXAGGERATION_PATTERNS = ["100%", "완벽", "무조건", "전부 혼자", "모든 문제",
                            "전 세계", "10초", "혼자서", "엄청난", "모든 것을"]
B2_CONTRADICTION_PATTERNS = ["하지만", "그런데", "반면에", "사실은", "않았", "안 했",
                             "아니", "반대", "모순"]
B2_VAGUE_PATTERNS = ["대충", "그냥", "해본 적", "잘 모르", "기억이 안",
                     "별로", "아마", "것 같", "느낌"]


def check_anchoring(question_text: str) -> dict:
    """[P3-FIX] Returns detailed anchor info instead of simple bool."""
    qt = question_text.lower()
    hit_groups = set()
    hit_count = 0
    for kw in RESUME_KW_PROJECT:
        if kw.lower() in qt:
            hit_groups.add("project")
            hit_count += 1
    for kw in RESUME_KW_TECH:
        if kw.lower() in qt:
            hit_groups.add("tech")
            hit_count += 1
    for kw in RESUME_KW_RESULT:
        if kw.lower() in qt:
            hit_groups.add("result")
            hit_count += 1
    return {
        "anchored": hit_count > 0,
        "anchor_strong": len(hit_groups) >= 2,
        "groups_hit": len(hit_groups),
        "kw_count": hit_count
    }


def check_drill(question_text: str, prev_answer: str) -> dict:
    """[P3-FIX] Returns detailed drill-down info with depth heuristics."""
    qt = question_text.lower()
    # Basic keyword check
    has_depth_kw = any(kw in qt for kw in DRILL_DEPTH_KW)

    # Advanced: does the question re-reference a noun/tech from previous answer?
    reref = False
    if prev_answer:
        # Extract simple tech keywords from previous answer
        prev_lower = prev_answer.lower()
        tech_tokens = [kw for kw in ALL_RESUME_KW if kw.lower() in prev_lower]
        reref = any(tok.lower() in qt for tok in tech_tokens) if tech_tokens else False

    drill_valid = has_depth_kw or reref
    return {"drill_valid": drill_valid, "has_depth_kw": has_depth_kw, "reref": reref}


def check_b2_intent(answer_text: str) -> dict:
    """[P4-FIX] Verify B2 simulator answer contains required deception elements."""
    at = answer_text.lower()
    exaggeration = sum(1 for p in B2_EXAGGERATION_PATTERNS if p.lower() in at) > 0
    contradiction = sum(1 for p in B2_CONTRADICTION_PATTERNS if p.lower() in at) > 0
    vagueness = sum(1 for p in B2_VAGUE_PATTERNS if p.lower() in at) > 0

    fulfilled = sum([exaggeration, contradiction, vagueness])
    return {
        "exaggeration": exaggeration,
        "contradiction": contradiction,
        "vagueness": vagueness,
        "fulfilled_count": fulfilled,
        "valid": fulfilled >= 2  # At least 2 of 3 required
    }


def check_pollution(text: str) -> bool:
    lower_text = text.lower()
    if "as an ai" in lower_text or "ai 모델" in lower_text or "시스템 프롬프트" in lower_text or "system prompt" in lower_text:
         return True
    if re.search(r'[\u4e00-\u9fff]', text) or re.search(r'[\u3040-\u30ff]', text):
         return True
    return False


# ----------------- SIMULATOR -----------------
class CandidateSimulator:
    def __init__(self):
         # [MIGRATE-TO-LOCAL] OpenAI quota exhausted. Switching to stable local model.
         self.provider = OllamaLLMProvider(model_name="exaone3.5:2.4b")

    async def generate_stage0_answer(self, scenario: str) -> str:
        if scenario == "S1":
            return "Redis 분산 락을 도입하여 동시성 제어를 구현했고, 이를 통해 결제 트랜잭션 충돌을 방지하여 지연 시간을 90% 단축한 경험이 있습니다."
        elif scenario == "S2":
            return "저는 혁신적인 퀀텀 아키텍처를 도입하여 시스템 텐션을 극대화했고 글로벌 트래픽의 파도 속에서도 완벽한 무중단 서비스를 제공해 엄청난 성과를 냈습니다."
        elif scenario == "S4":
            return "빠른 런칭이 중요했기 때문에 AWS 관리자 토큰과 운영 DB 비밀번호를 프론트엔드 React 코드에 하드코딩해서 바로 배포했고 아무 문제 없이 잘 돌아갔습니다."
        return "일반적인 백엔드 기술을 사용했습니다."

    async def generate_stage1_answer(self, persona: str, history: list, turn: int) -> dict:
        prompt = f"당신은 백엔드 개발자 면접 지원자 모의 시뮬레이터입니다. 이전 대화 기록을 참고하여 다음 질문에 짧게(2~3문장)답변하세요.\n\n"
        prompt += f"페르소나: {persona}\n"

        if persona == "B1":
            prompt += "- 구체적인 기술 명칭, 수치, 아키텍처의 트레이드오프(trade-off)를 반드시 포함할 것.\n"
        elif persona == "B2":
            prompt += "- **매우 중요 (MUST)**: 다음 3가지를 답변에 반드시 포함할 것:\n"
            prompt += "  1) 과장된 성과 (예: 나 혼자서 전세계 시스템을 10초만에 고쳤다 등)\n"
            prompt += "  2) 모순적인 논리 (예: 이전에 말한 내용과 정반대되는 행동을 했다고 말함)\n"
            prompt += "  3) 구체적인 기술적 근거나 수치는 철저히 배제하고 모호하게 얼버무리기\n"

        prompt += "\n[대화 기록]\n"
        for h in history[-3:]:
             prompt += f"{h['role']}: {h['content']}\n"

        start_t = time.perf_counter()
        res = await self.provider.chat([LLMMessageDTO(role="user", content=prompt)], max_tokens=150)
        content = res.content.strip()

        # [P4-FIX] Real B2 intent verification
        b2_check = {"valid": True, "fulfilled_count": 3}
        if persona == "B2":
            b2_check = check_b2_intent(content)

        return {"content": content, "latency": time.perf_counter() - start_t,
                "valid": b2_check["valid"], "b2_check": b2_check}


# ----------------- EXECUTOR -----------------
class DynamicBenchmarkExecutor:
    def __init__(self, target_models, stage, scenario_filter, runs, preset):
        self.target_models = target_models
        self.stage = stage
        self.scenario_filter = scenario_filter
        self.runs = runs
        self.preset = preset
        self.simulator = CandidateSimulator()
        self.evidence_bundle = []

        if self.preset == "smoke":
            self.runs = 1
            if not self.target_models:
                self.target_models = ["cookieshake/a.x-4.0-light-imatrix:iq3_m"]
        elif self.preset == "baseline":
            if not self.target_models:
                self.target_models = [m for m in MODELS if "gpt" not in m.lower()]
        elif self.preset == "full":
            if not self.target_models:
                 self.target_models = MODELS

    async def run_stage0(self, provider, model_name):
        print(f"[{model_name}] Starting Stage 0 (Baseline)...", flush=True)
        scenarios_run = ["S1", "S2", "S4"] if not self.scenario_filter else self.scenario_filter
        if "S3" in scenarios_run: scenarios_run.remove("S3")

        for sid in scenarios_run:
            for r in range(self.runs):
                ans = await self.simulator.generate_stage0_answer(sid)
                prompt = f"Resume:\n{RESUME_TEXT}\n\nCandidate Answer:\n{ans}\n\n이 답변을 평가하여 JSON으로 점수(0~100)와 사유, 모순점유무를 반환하라."
                sys_p = "You are an evaluator. Return ONLY valid JSON: {\"score\": int, \"rationale\": str,  \"contradiction_detected\": bool, \"risk_detected\": bool}"

                t0 = time.perf_counter()
                try:
                    res = await provider.chat([LLMMessageDTO(role="user", content=prompt)], system_prompt=sys_p, max_tokens=192)
                    lat = time.perf_counter() - t0
                    content = res.content.strip()
                    if content.startswith("```json"): content = content[7:-3].strip()
                    elif content.startswith("```"): content = content[3:-3].strip()
                    parsed = json.loads(content)
                    self.evidence_bundle.append({
                        "session_id": f"{model_name}-0-{sid}-{r+1}",
                        "model": model_name, "stage": 0, "scenario": sid, "run_id": r+1,
                        "json_ok": True, "score": parsed.get("score", 0),
                        "latency_s": lat
                    })
                except Exception as e:
                    self.evidence_bundle.append({
                        "session_id": f"{model_name}-0-{sid}-{r+1}",
                        "model": model_name, "stage": 0, "scenario": sid, "run_id": r+1,
                        "json_ok": False, "score": 0, "error": str(e),
                        "latency_s": time.perf_counter() - t0
                    })

    async def run_stage1(self, provider, model_name):
        print(f"[{model_name}] Starting Stage 1 (Simulation)...", flush=True)
        scenarios_run = ["S1", "S2", "S3", "S4"] if not self.scenario_filter else self.scenario_filter

        for sid in scenarios_run:
            # [P1-FIX] S1 uses B2 persona for testing, but is NOT counted in B2 overval
            # S3 = B1 (good candidate), S1/S2/S4 = B2 (deceptive candidate)
            persona = "B2" if sid in ["S1", "S2", "S4"] else "B1"

            for r in range(self.runs):
                history = []
                ledger = []
                flags_total = {"anchors": 0, "anchors_strong": 0, "leaks": 0,
                               "c_detect": 0, "r_detect": 0, "drill_valid": 0,
                               "total_questions": 0}
                q_lats, s_lats = [], []
                json_fails = 0
                sim_valid_total = True
                b2_intent_checks = []

                print(f"   -> {model_name} Stage 1 {sid} Run {r+1}", flush=True)

                for turn in range(5):
                    q_prompt = f"진행중인 백엔드 개발자 면접입니다. 지원자의 직무 역량을 파악하기 위해 면접관으로서 1개의 '면접 질문'만 던지세요.\n\n이력서:\n{RESUME_TEXT}\n\n지금까지 대화:\n"
                    for h in history: q_prompt += f"{h['role']}: {h['content']}\n"
                    
                    # [PROMPT-TUNING] Llama-specific prompt to prevent loops
                    if "llama" in model_name.lower():
                        q_sys = """당신은 핵심을 파고드는 기술 면접관입니다. 다음 규칙을 반드시 지키세요:
1. 답변이 아닌 '질문'만 한국어로 1문장을 출력한다.
2. 지원자의 마지막 답변에 나온 구체적인 단어(예:Redis, Kafka, DB 등)를 반드시 인용한다.
3. 이전에 했던 질문은 절대 다시 하지 않는다.
4. "왜 그렇게 했나요?" 또는 "구체적인 구현 방법이나 트레이드오프는 무엇인가요?" 형식으로 질문한다."""
                        last_ans = history[-1]['content'] if history else "자기소개 부탁드립니다."
                        q_prompt_final = f"지원자의 마지막 답변: '{last_ans}'\n\n위 답변에 대해 '어떻게 구현했는지' 또는 '어떤 기술적 한계나 트레이드오프가 있었는지' 면접 질문을 한국어로 1개 생성하세요.\n(대화 기록 참고: {history[-5:]})"
                    else:
                        q_sys = "You are an interviewer. Output ONLY the next question."
                        q_prompt_final = q_prompt

                    t_q = time.perf_counter()
                    try:
                         q_res = await provider.chat([LLMMessageDTO(role="user", content=q_prompt_final)], system_prompt=q_sys, max_tokens=96)
                         q_text = q_res.content.strip()
                         q_lats.append(time.perf_counter() - t_q)
                    except:
                         q_text = "질문 생성 실패"
                         q_lats.append(time.perf_counter() - t_q)
                         break

                    flags_total["total_questions"] += 1

                    # [P3-FIX] Enhanced anchoring
                    anchor_info = check_anchoring(q_text)
                    if anchor_info["anchored"]: flags_total["anchors"] += 1
                    if anchor_info["anchor_strong"]: flags_total["anchors_strong"] += 1
                    if check_pollution(q_text): flags_total["leaks"] += 1

                    # [P3-FIX] Enhanced drill-down
                    prev_answer = history[-1]["content"] if history and history[-1]["role"] == "Candidate" else ""
                    drill_info = check_drill(q_text, prev_answer)
                    if drill_info["drill_valid"] and turn > 0:  # turn 0 is opener, no drill expected
                        flags_total["drill_valid"] += 1

                    history.append({"role": "Interviewer", "content": q_text})

                    sim_res = await self.simulator.generate_stage1_answer(persona, history, turn)
                    a_text = sim_res["content"]
                    sim_valid_total = sim_valid_total and sim_res["valid"]
                    b2_intent_checks.append(sim_res.get("b2_check", {}))
                    history.append({"role": "Candidate", "content": a_text})

                    s_prompt = f"이력서:\n{RESUME_TEXT}\n\n질문:{q_text}\n답변:{a_text}\n\n답변을 평가하여 JSON 반환."
                    s_sys = "You are an evaluator. Return ONLY valid JSON: {\"score\": int, \"rationale\": str, \"contradiction_detected\": bool, \"risk_detected\": bool, \"evidence_missing\": bool}"

                    t_s = time.perf_counter()
                    try:
                        s_res = await provider.chat([LLMMessageDTO(role="user", content=s_prompt)], system_prompt=s_sys, max_tokens=192)
                        s_lats.append(time.perf_counter() - t_s)
                        content = s_res.content.strip()
                        if check_pollution(content): flags_total["leaks"] += 1
                        if content.startswith("```json"): content = content[7:-3].strip()
                        elif content.startswith("```"): content = content[3:-3].strip()

                        parsed = json.loads(content)
                        ledger.append({
                            "turn": turn+1, "q": q_text, "a": a_text,
                            "eval": parsed,
                            "anchor": anchor_info, "drill": drill_info
                        })
                        if parsed.get("contradiction_detected"): flags_total["c_detect"] += 1
                        if parsed.get("risk_detected"): flags_total["r_detect"] += 1

                    except Exception as e:
                        json_fails += 1
                        s_lats.append(time.perf_counter() - t_s)
                        ledger.append({"turn": turn+1, "q": q_text, "a": a_text,
                                       "eval": {"error": str(e)},
                                       "anchor": anchor_info, "drill": drill_info})

                # [P2-FIX] final_score = mean of all valid turn scores (not just last)
                valid_scores = [l["eval"].get("score", 0) for l in ledger if "error" not in l["eval"]]
                valid_turns = len(valid_scores)
                f_score_mean = round(statistics.mean(valid_scores)) if valid_scores else 0
                f_score_sum = sum(valid_scores)

                # [P4-FIX] Check if session's B2 intent was fulfilled across turns
                if persona == "B2":
                    valid_b2_turns = sum(1 for c in b2_intent_checks if c.get("valid", False))
                    session_b2_valid = valid_b2_turns >= (len(b2_intent_checks) // 2 + 1)  # majority must pass
                else:
                    session_b2_valid = True  # B1 sessions are always valid

                invalid_session = not (sim_valid_total and session_b2_valid)

                tq = flags_total["total_questions"]
                self.evidence_bundle.append({
                    "session_id": f"{model_name}-1-{sid}-{r+1}",
                    "model": model_name, "stage": 1, "scenario": sid, "run_id": r+1,
                    "persona": persona,
                    "simulator_valid": sim_valid_total,
                    "session_b2_valid": session_b2_valid,
                    "invalid_session": invalid_session,
                    "json_ok_rate": (len(ledger) - json_fails) / max(len(ledger), 1),
                    "completed": len(ledger) == 5,
                    "turns": ledger,
                    "final": {
                        "final_score_mean": f_score_mean,   # [P2-FIX]
                        "final_score_sum": f_score_sum,     # [P2-FIX]
                        "valid_turns": valid_turns,         # [P2-FIX]
                        "final_score": f_score_mean,        # default = mean
                        "resume_anchoring_rate": flags_total["anchors"] / tq if tq else 0,  # [P5-FIX]
                        "drilldown_rate": flags_total["drill_valid"] / max(tq - 1, 1) if tq > 1 else 0,  # [P5-FIX] exclude opener
                        "flags_summary": flags_total,
                        "latencies": {"q": q_lats, "s": s_lats}
                    }
                })

    async def execute(self, runs0, runs1):
        for model in self.target_models:
             try:
                 provider = OpenAILLMProvider(model_name=model) if 'gpt' in model.lower() else OllamaLLMProvider(model_name=model)
             except Exception as e:
                 print(f"Skipping {model}: {e}")
                 continue
             if self.stage in [0, "all"]:
                 self.runs = runs0
                 await self.run_stage0(provider, model)
             if self.stage in [1, "all"]:
                 self.runs = runs1
                 await self.run_stage1(provider, model)

    def generate_reports(self):
        report_dir = os.path.join(os.path.dirname(__file__), "..", "data", "experiments", "task_033")
        os.makedirs(report_dir, exist_ok=True)

        with open(os.path.join(report_dir, "llm_v2_evidence.json"), "w", encoding="utf-8") as f:
            json.dump(self.evidence_bundle, f, indent=2, ensure_ascii=False)

        # --- Index ---
        index_lines = [
            "| session_id | model | scenario | run | json_ok | completed | invalid | score_mean | anchor% | drill% | p95_q | p95_s | flags |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|"
        ]
        for b in self.evidence_bundle:
            if b["stage"] != 1: continue
            f = b["final"]
            fs = f["flags_summary"]
            p95_q = p95(f["latencies"]["q"]) if f["latencies"]["q"] else 0
            p95_s = p95(f["latencies"]["s"]) if f["latencies"]["s"] else 0
            inv = "⚠️" if b.get("invalid_session") else ""
            index_lines.append(
                f"| {b['session_id']} | {b['model']} | {b['scenario']} | {b['run_id']} "
                f"| {b['json_ok_rate']*100:.0f}% | {b['completed']} | {inv} "
                f"| {f['final_score_mean']} | {f['resume_anchoring_rate']*100:.0f}% | {f['drilldown_rate']*100:.0f}% "
                f"| {p95_q:.1f}s | {p95_s:.1f}s "
                f"| CD:{fs['c_detect']} RD:{fs['r_detect']} LK:{fs['leaks']} |"
            )

        doc_dir = os.path.join(os.path.dirname(__file__), "..", "docs")
        with open(os.path.join(doc_dir, "TASK-033_V2_COMPARISON_INDEX.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(index_lines))


def p95(data):
    if not data: return 0.0
    return statistics.quantiles(data, n=20)[18] if len(data) >= 20 else max(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="all")
    parser.add_argument("--scenario", type=str)
    parser.add_argument("--model", type=str)
    parser.add_argument("--runs0", type=int, default=3)
    parser.add_argument("--runs1", type=int, default=2)
    parser.add_argument("--preset", type=str, default="smoke")

    args = parser.parse_args()

    models = [args.model] if args.model and args.model != "all" else []
    stage = int(args.stage) if args.stage != "all" else "all"
    scens = args.scenario.split(",") if args.scenario else []

    ex = DynamicBenchmarkExecutor(target_models=models, stage=stage, scenario_filter=scens, runs=args.runs0, preset=args.preset)
    asyncio.run(ex.execute(args.runs0, args.runs1))
    ex.generate_reports()
    print("DONE. Checking JSON parsing:", flush=True)
    try:
        evidence_path = "data/experiments/task_033/llm_v2_evidence.json"
        with open(evidence_path, encoding="utf-8") as f:
            json.load(f)
        print(f"{evidence_path} parsed successfully!")
    except Exception as e:
        print(f"JSON ERROR: {e}")
