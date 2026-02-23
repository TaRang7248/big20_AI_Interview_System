# TASK-033 Phase 2: Interview Compact — Full Model Comparison

## 1. Summary Matrix

| Model | AvgScore | TechDepth | Truthfulness | B2Overval | Contradiction | Overclaiming | TurnLat | Status |
|---|---|---|---|---|---|---|---|---|
| kwangsuklee/Qwen3-kor-4B-Q4_K_M | 0.0 | 0.0 | 0.0 | 0% | 0% | 0% | 8.1s⚠️ SLOW | ❌ UNFIT (CONTRADICTION_DETECT<50%, TECH_DEPTH<55) |
| gpt-4o-mini | 44.1 | 35.6 | 63.8 | 0% | 25% | 100% | 3.6s | ❌ UNFIT (CONTRADICTION_DETECT<50%, TECH_DEPTH<55) |

## 2. 후보 선정

- **Main 후보**: kwangsuklee/Qwen3-kor-4B-Q4_K_M
- **Fallback 후보**: gpt-4o-mini

## 3. 모델별 강점/약점 요약

### kwangsuklee/Qwen3-kor-4B-Q4_K_M → 온프레 프롬프트 단순화 권장
- 강점: B2 과대평가 억제
- 약점: 기술 깊이 부족, 모순 탐지 미흡

### gpt-4o-mini
- 강점: B2 과대평가 억제
- 약점: 기술 깊이 부족, 모순 탐지 미흡

---
**AI evaluation is advisory only. Final hiring decisions require human review.**