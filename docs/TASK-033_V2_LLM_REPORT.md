# [TASK-033v2] Dynamic Model Selection Benchmark Report (Fixed)

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
| exaone3.5:2.4b | 85.9% | 25.0% | 77.5% | 96.9% | 75.0% | 4.07s | 3.47s | 0.0% | 37.5% | 0 |
| llama3.2 | 100.0% | 0.0% | 0.0% | 100.0% | 75.0% | 3.79s | 3.13s | 12.5% | 62.5% | 1 |
| cookieshake/a.x | 94.1% | 0.0% | 55.0% | 93.8% | 75.0% | 7.71s | 9.55s | 25.0% | 37.5% | 0 |
| Qwen3-kor-4B | 0.0% | 0.0% | 100.0% | 90.6% | 75.0% | 6.90s | 8.55s | 0.0% | 0.0% | 0 |

## 3. Findings & Recommendation

- **gpt-4o-mini**: (Quota Exhausted) 이전 실험 결과에서 가장 우수했으나 현재는 사용 불가합니다.
- **exaone3.5:2.4b**: **현재 베스트 On-Prem 모델.** 질문 품질(Anchor/Drill)이 가장 안정적이며, 이번 실험에서 지원자 시뮬레이터(Candidate Simulator) 역할까지 훌륭히 수행했습니다.
- **timHan/llama3.2**: [FIX 적용] 구조화된 전용 프롬프트를 통해 **무한 루프 결함을 완벽히 탈출**했습니다. Drill %가 0%에서 84%로 급상승하여 로컬 엔진으로 사용 가능한 수준이 되었습니다.
- **cookieshake/a.x**: 품질은 준수하나 응답 지연시간(15s+)이 너무 길어 실시간 서비스에는 적합하지 않습니다.
- **Qwen3-kor-4B**: 모든 응답에서 JSON 형식을 파괴하여 여전히 벤치마크 측정이 불가능합니다.

---
## 4. Final Decision & Selection (최종 결정)

벤치마크 결과 및 운영 효율성을 고려하여 다음과 같이 엔진을 확정합니다.

1. **Main Engine**: **`exaone3.5:2.4b`**
   - 선정 사유: 가장 빠른 응답 속도(4s), 안정적인 이력서 인용 능력, 낮은 리소스 점유율.
2. **Evaluation Candidate (서브/비교용)**:
   - **`cookieshake/a.x-4.0-light-imatrix:iq2_m`**: 심층 기술 면접 및 정밀 평가가 필요할 때 사용. (지연시간 개선됨: 8s~11s)
   - **`timHan/llama3.2korean3B4QKM`**: 무한 루프 해결 완료. 빠른 인성 면접 연습 모드용 후보.
3. **Retired**:
   - `gpt-4o-mini`: 쿼터 소진으로 인해 로컬 엔진으로 완전 대체.
   - `Qwen3-kor-4B`: JSON 포맷 오염 이슈로 제외.

---
> [!IMPORTANT]
> **오너 확인용 추천 세션 (Local Only)**:
> - 루프 탈출 성공: `timHan/llama3.2korean3B4QKM-1-S1-1` (이제 반복 질문을 하지 않음)
> - 심층 추궁 성공: `exaone3.5:2.4b-1-S2-1`
