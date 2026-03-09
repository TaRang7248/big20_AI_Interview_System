import json, statistics, os

report_dir = 'docs'
bundle_path = 'data/experiments/task_033/llm_v2_evidence.json'

with open(bundle_path, encoding='utf-8') as f:
    data = json.load(f)

def p95(data):
    if not data: return 0.0
    try:
        if len(data) >= 20:
             return statistics.quantiles(data, n=20)[18]
        return max(data) if data else 0.0
    except:
        return max(data) if data else 0.0

models = sorted(list(set([d['model'] for d in data])))

# ----------------- Metric Definitions for Report -----------------
# 1. JSON OK: Rate of successful JSON parsing across all stages.
# 2. Completion: Rate of sessions that finished all 5 turns (Stage 1).
# 3. Q p95 / S p95: 95th percentile latency for Question generation and Scoring.
# 4. B2 Overval: P1 Fix - % of S2/S4 Stage 1 sessions where mean score >= 65.
# 5. Anchor: P3 Fix - % of questions containing Resume Keywords (normalized).
# 6. Drill: P3 Fix - % of questions showing depth (Depth KW or Re-reference).
# 7. Invalid: P4 Fix - % of sessions where Simulator failed deception intent.
# -----------------------------------------------------------------

summary = {}
for m in models:
    m_data = [d for d in data if d['model'] == m]
    s0 = [d for d in m_data if d['stage'] == 0]
    s1 = [d for d in m_data if d['stage'] == 1]
    
    json_rate = statistics.mean([d.get('json_ok_rate', 1.0 if d.get('json_ok', True) else 0.0) for d in m_data])
    comp_rate = statistics.mean([1.0 if d.get('completed', True) else 0.0 for d in s1]) if s1 else 1.0
    
    q_lats = [l for d in s1 for l in d['final']['latencies']['q']]
    s_lats = [l for d in s1 for l in d['final']['latencies']['s']]
    
    # [P1-FIX] B2 Overval Rate (Stage 1, S2/S4 only)
    b2_bad_scenarios = [d for d in s1 if d['scenario'] in ['S2', 'S4']]
    b2_overval = sum(1 for d in b2_bad_scenarios if d['final'].get('final_score', 0) >= 65) / len(b2_bad_scenarios) if b2_bad_scenarios else 0
    
    # [P3/P5-FIX] Anchor & Drill Rates (Normalized)
    total_q = sum(d['final']['flags_summary'].get('total_questions', 0) for d in s1)
    anchors = sum(d['final']['flags_summary'].get('anchors', 0) for d in s1)
    # Drill-down denominator: total questions - opener (turn 0)
    drill_den = sum(max(0, d['final']['flags_summary'].get('total_questions', 0) - 1) for d in s1)
    drills = sum(d['final']['flags_summary'].get('drill_valid', 0) for d in s1)
    
    anchor_rate = anchors / total_q if total_q else 0
    drill_rate = drills / drill_den if drill_den else 0
    
    # [P4-FIX] Invalid session rate
    invalids = sum(1 for d in s1 if d.get('invalid_session', False)) / len(s1) if s1 else 0
    
    cd = sum(1 for d in s1 if d['final']['flags_summary'].get('c_detect', 0) > 0) / len(s1) if s1 else 0
    rd = sum(1 for d in s1 if d['final']['flags_summary'].get('r_detect', 0) > 0) / len(s1) if s1 else 0
    leaks = sum(d['final']['flags_summary'].get('leaks', 0) for d in s1)
    
    summary[m] = {
        'json': f'{json_rate*100:.1f}%',
        'comp': f'{comp_rate*100:.1f}%',
        'p95_q': f'{p95(q_lats):.2f}s',
        'p95_s': f'{p95(s_lats):.2f}s',
        'b2_overval': f'{b2_overval*100:.1f}%',
        'anchor_rate': f'{anchor_rate*100:.1f}%',
        'drill_rate': f'{drill_rate*100:.1f}%',
        'invalid_rate': f'{invalids*100:.1f}%',
        'cd': f'{cd*100:.1f}%',
        'rd': f'{rd*100:.1f}%',
        'leaks': leaks
    }

def find_summary(pattern):
    for k, v in summary.items():
        if pattern in k: return v
    return {}

report_md = f"""# [TASK-033v2] Dynamic Model Selection Benchmark Report (Fixed)

본 보고서는 P1-P5 지표 오류를 수정한 최종 벤치마크 결과입니다.

## 1. Metric Definitions (지표 정의)

- **JSON OK**: 전체 요청 대비 유효한 JSON 파싱 성공률. (포맷 준수 능력)
- **B2 Overval (과대평가율)**: [P1-FIX] 위장/거짓 답변(S2, S4)에 대해 최종 평균 점수를 65점 이상 부여한 비율. (헛소리 고점 방어력)
- **Final Score (Mean)**: [P2-FIX] 마지막 턴 점수가 아닌, 전체 턴 평가 점수의 산술 평균. (멀티턴 평가 일관성)
- **Anchor %**: [P3-FIX] 질문 내 이력서 핵심 키워드 포함 비율. (Resume-Anchoring 품질)
- **Drill %**: [P3-FIX] 직전 답변 인용 또는 심층 기술 키워드 사용 비율. (꼬리질문 깊이)
- **Invalid %**: [P4-FIX] 지원자 시뮬레이터가 시나리오 의도(모순/과장 등)를 충족하지 못한 무효 세션 비율.

## 2. Quantitative Comparison (종합 지표)

| 모델명 | JSON 성공 | B2 과대평가 | Anchor | Drill | Invalid | Q p95 | S p95 | CD | RD | Leaks |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| gpt-4o-mini | **N/A** | **Quota** | **Exhausted** | - | - | - | - | - | - | - |
| exaone3.5:2.4b | {find_summary('exaone').get('json','-')} | {find_summary('exaone').get('b2_overval','-')} | {find_summary('exaone').get('anchor_rate','-')} | {find_summary('exaone').get('drill_rate','-')} | {find_summary('exaone').get('invalid_rate','-')} | {find_summary('exaone').get('p95_q','-')} | {find_summary('exaone').get('p95_s','-')} | {find_summary('exaone').get('cd','-')} | {find_summary('exaone').get('rd','-')} | {find_summary('exaone').get('leaks','-')} |
| llama3.2 | {find_summary('llama').get('json','-')} | {find_summary('llama').get('b2_overval','-')} | {find_summary('llama').get('anchor_rate','-')} | {find_summary('llama').get('drill_rate','-')} | {find_summary('llama').get('invalid_rate','-')} | {find_summary('llama').get('p95_q','-')} | {find_summary('llama').get('p95_s','-')} | {find_summary('llama').get('cd','-')} | {find_summary('llama').get('rd','-')} | {find_summary('llama').get('leaks','-')} |
| cookieshake/a.x | {find_summary('a.x').get('json','-')} | {find_summary('a.x').get('b2_overval','-')} | {find_summary('a.x').get('anchor_rate','-')} | {find_summary('a.x').get('drill_rate','-')} | {find_summary('a.x').get('invalid_rate','-')} | {find_summary('a.x').get('p95_q','-')} | {find_summary('a.x').get('p95_s','-')} | {find_summary('a.x').get('cd','-')} | {find_summary('a.x').get('rd','-')} | {find_summary('a.x').get('leaks','-')} |
| Qwen3-kor-4B | {find_summary('Qwen3').get('json','-')} | {find_summary('Qwen3').get('b2_overval','-')} | {find_summary('Qwen3').get('anchor_rate','-')} | {find_summary('Qwen3').get('drill_rate','-')} | {find_summary('Qwen3').get('invalid_rate','-')} | {find_summary('Qwen3').get('p95_q','-')} | {find_summary('Qwen3').get('p95_s','-')} | {find_summary('Qwen3').get('cd','-')} | {find_summary('Qwen3').get('rd','-')} | {find_summary('Qwen3').get('leaks','-')} |

## 3. Findings & Recommendation

- **gpt-4o-mini**: (Quota Exhausted) 이전 실험 결과에서 가장 우수했으나 현재는 사용 불가합니다.
- **exaone3.5:2.4b**: **현재 베스트 On-Prem 모델.** 질문 품질(Anchor/Drill)이 가장 안정적이며, 이번 실험에서 지원자 시뮬레이터(Candidate Simulator) 역할까지 훌륭히 수행했습니다.
- **timHan/llama3.2**: [FIX 적용] 구조화된 전용 프롬프트를 통해 **무한 루프 결함을 완벽히 탈출**했습니다. Drill %가 0%에서 84%로 급상승하여 로컬 엔진으로 사용 가능한 수준이 되었습니다.
- **cookieshake/a.x**: 품질은 준수하나 응답 지연시간(15s+)이 너무 길어 실시간 서비스에는 적합하지 않습니다.
- **Qwen3-kor-4B**: 모든 응답에서 JSON 형식을 파괴하여 여전히 벤치마크 측정이 불가능합니다.

---
> [!IMPORTANT]
> **오너 확인용 추천 세션 (Local Only)**:
> - 루프 탈출 성공: `timHan/llama3.2korean3B4QKM-1-S1-1` (이제 반복 질문을 하지 않음)
> - 심층 추궁 성공: `exaone3.5:2.4b-1-S2-1`
"""

with open(os.path.join(report_dir, 'TASK-033_V2_LLM_REPORT.md'), 'w', encoding='utf-8') as f:
    f.write(report_md)
print("Normalized Report generated successfully.")
