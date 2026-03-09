# TASK-032: LLM & Evaluation E2E Integration Plan (Final Version)

## 1. 평가 멱등성(Idempotency) 보장 방식
*   **선택 옵션**: **옵션 A (DB Unique + Upsert/On-Conflict)**
*   **선택 근거**: 현재 시스템 아키텍처는 "PostgreSQL Authority" 원칙(TASK-030)을 따르고 있습니다. `evaluation_scores` 테이블에 `session_id` 컬럼이 추가되어(또는 report_id와 분리되어) 있으므로, DB 레벨의 제약 조건이나 트랜잭션 내 존재 여부 체크(`INSERT ... ON CONFLICT DO NOTHING` 등)를 구현하는 것이 가장 안정적이고 직관적인 결착 방식입니다.

## 2. 평가 트리거 방식 (동기/비동기)
*   **선택 옵션**: **옵션 A (동기 실행)**
*   **선택 근거**: 본 TASK의 최우선 목적은 로컬 환경에서의 완전한 "E2E 검증 및 동작 확인"입니다. 답변 제출(`submit_chat`) 엔드포인트에서 엔진이 `COMPLETED` 상태를 반환할 때, `RubricEvaluator`를 동기로 즉시 실행시킨 후 응답을 내려주면, 클라이언트(UI)가 결과 화면(`/result`)으로 넘어갔을 때 즉시 반영된 결과를 확인할 수 있어 검증이 직관적이고 꼬임이 없습니다.

## 3. UI 매핑 스펙 및 Fallback 규칙
*   **선택 옵션**: **옵션 A (tag_code 기반 합산 + 누락 fallback)**
*   **선택 근거**: 기존 루브릭 엔진(`packages/imh_eval/engine.py`)이 명확한 4개 카테고리(`capability.knowledge`, `problem_solving`, `communication`, `attitude`)를 산출하도록 설계되어 있습니다. 
    *   **매핑 룰**: 
        *   `tech_score`: `capability.knowledge` * 20
        *   `problem_score`: `capability.problem_solving` * 20
        *   `comm_score`: `capability.communication` * 20
        *   `nonverbal_score`: `capability.attitude` * 20
        *   `decision`: 4개 점수 평균(또는 total_score) >= 70 이면 `PASS`
    *   **Fallback 규칙**: LLM 에러나 구조화 실패 등으로 특정 분야의 `tag_code` 점수가 누락된 경우, 해당 점수는 `0`으로 고정하고, `summary` 텍스트 최하단에 "[시스템 메시지] 일부 평가 항목 생성이 누락되었습니다."를 명시하여 UI 크래시(NaN 등)를 방지합니다.

## 4. 질문 생성 Tier 표기 및 책임 경계
*   **수정된 문구**:
    *   **Tier 1**: **"LLM (+RAG) 생성 (컨텍스트/후보를 사용한 LLM 동적 질문 생성)"**
    *   **Tier 2**: "Static QBank 후보 선택 (정적 질문 풀 필터링)"
    *   **Tier 3**: "Emergency Fallback (하드코딩 긴급 질문)"
*   **근거**: 질문의 최종 확정 주체는 'Engine'이며, RAG나 Cache는 그 생성 과정의 재료(Context Layer)에 불과함을 명확히 하여 아키텍처 오해를 방지합니다.

## 5. 레거시 API 라우트 처리 스펙
*   **수정된 문구**:
    *   **라우트 유지**: `GET /interviews`, `POST /interviews`, `POST /interviews/{id}/chat`, `GET /interviews/{id}/result` 등 프론트엔드가 의존하는 API 명세는 그대로 유지합니다.
    *   **내부 로직 변경**: `IMH/api/interviews.py` 내부의 SQL을 직접 호출하는 로직(특히 random 값 생성 로직)들을 **제거**하고, 그 자리에 `SessionService`, `RubricEvaluator`, `PostgreSQLHistoryRepository` 등의 정식 패키지 호출 코드로 **대체**하여 결착합니다.

---

## 6. 핵심 요약 및 진행 프로세스
본 Plan은 메인 모델(Ollama/OpenAI) 벤치마킹을 다음 과제(TASK-033)로 미루고, "모든 톱니바퀴가 E2E로 처음 끝까지 맞물려 돌아가는 상태"를 만드는 데 집중합니다. 개발 중 어떠한 경우에도 랜덤 점수나 더미 데이터로 도피하지 않으며, 실패 시엔 '빈 결과(Empty fallback)'를 정직하게 UI에 표출하는 방식으로 개발됩니다.
