# PROJECT_STATUS
(IMH AI 모의면접 프로젝트 – ChatGPT 전용 전략 기준 문서)

**중요: 본 문서는 ChatGPT의 전략 설계 및 판단을 위한 전용 문서이다.**
코딩에이전트(안티그래비티)의 직접적인 작업 판단 기준은 `TASK_QUEUE.md`와 `CURRENT_STATE.md`를 따른다.

---

## 1. 프로젝트 전략 및 아키텍처 기준선

### 1.1 프로젝트 목적
정량 평가, 근거 제시, 피드백 제공이 가능한 수준 높은 AI 모의면접 시스템 구축.

### 1.2 핵심 아키텍처 원칙 (Immutable Contracts)
1. **Single Source of Truth**: PostgreSQL이 모든 영속 데이터의 유일한 권위 저장소이다.
2. **Read Optimization Only**: Redis는 런타임 제어 및 데이터 조회 최적화 용도로만 사용하며, PG로의 쓰기(Write-Back)는 금지한다.
3. **Session Engine Authority**: 세션 엔진만이 인터뷰 상태를 판단하고 전이시킬 권한을 가진다.
4. **Snapshot & Freeze**: 공고 발행 시 정책을 동결(Freeze)하며, 세션 시작 시 스냅샷(Snapshot)을 생성하여 평가의 일관성을 보장한다.
5. **CQRS & Boundary Isolation**: Command와 Query 경로를 분리하고, API/Service/Domain 간의 명시적 경계를 유지한다.

---

## 2. 개발 로드맵 및 단계별 성과 (Phase 1 ~ 10 완료)

### Phase 1~4: 분석 및 평가 기반 구축
- 5대 분석 모듈 (STT, LLM, Emotion, Visual, Voice) 통합.
- 루브릭 기반 평가 엔진 및 JSON 리포팅 계층 확정.

### Phase 5~6: 실행 및 서비스 경계 확립
- 세션 엔진 및 공고 정책 엔진 통합.
- 상태 전이(State Contract) 및 스냅샷 계약 고정.
- Service Layer 도입을 통한 CQRS 및 동시성 제어(Fail-Fast) 안정화.

### Phase 7~8: 질문 지능화 및 영속화 고도화
- QBank 및 RAG Fallback 3-Tier 전략 통합.
- PostgreSQL 기반 영속 저장소 전환 및 권위 구조(Authority) 확정.
- TASK-029 (Baseline Alignment): 테이블 네이밍 정렬(sessions->interviews, reports->evaluation_scores), PostgreSQLHistoryRepository 주입 고정, Redis Miss Hydration 구현, Schema Fail-Fast 적용 완료. Live Persistence/Hydration 검증 통과.

### Phase 9~10: 런타임 최적화 및 운영 관측성 확보
- Redis 캐시 계층(Projection, RAG, Candidate, Prompt) 도입.
- 비즈니스 통계(Track A)와 운영 관측(Track B) 계층의 물리적 분리.
- Heavy Query 격리를 위한 MView 전략 수립.

---

## 3. 현재 상태 요약 (Phase 10 감사 완료)

시스템은 운영 가능한 아키텍처 환경을 갖추었으며, 심층 감사를 통해 안정성을 점검 중이다.

- **완료된 단계**: Phase 0 ~ Phase 10 + Baseline Alignment (TASK-029)
- **현재 주요 상태**:
  - **내부 테스트 한정 가능**: 감사 보고서(2026-02-19) 기준 핵심 계약 준수 확인
  - **안정화 작업 진행**: 
    - TASK-030 (Authority First) DONE
    - TASK-031 (Snapshot Immutable) ACTIVE (현재 수행 대상)
    - TASK-032 (tag_code Constraint) BACKLOG
  - PostgreSQL Authority 선행 보장 및 원자성 강화 완료 (TASK-030)
  - Redis Runtime and Cache Layer 및 통계/관측 계층 구축 완료
- **향후 계획**:
  - Phase 10 안정화 패키지(TASK-031~032) 완료 후 외부 운영 가능 상태로 전환
- **보류 사항**:
  - TASK-016 (TTS Provider): 스트리밍 확장 고려를 위해 HOLD 상태 유지.

---

## 4. 향후 확장 전략 (Phase 11+)

- **관리 대시보드**: 구축된 통계/관측 데이터를 소비하는 UI 계층 확장.
- **멀티모달 고도화**: 실시간 스트리밍(WebRTC) 및 TTS 연동.
- **외부 연동**: 기업용 채용 API 서비스 모델로의 확장 여부 검토.

---

## 5. 협업 가이드 (ChatGPT & Project Owner)

1. **판단 기준**: 모든 신규 TASK 설계 시, 본 문서의 '핵심 아키텍처 원칙'을 1순위로 준수한다.
2. **문서 갱신**: 사용자가 전략적 방향을 수정할 때 본 문서를 최우선으로 업데이트한다.
3. **에이전트 지시**: ChatGPT는 본 문서의 전략을 바탕으로 코딩에이전트가 수행할 구체적인 Plan과 TASK를 설계하여 `TASK_QUEUE.md`에 반영한다.
