# big20_AI_Interview_System
빅데이터20기 Kingterview팀 파이널 프로젝트: **멀티모달 AI 모의면접 시스템**

본 레포지토리는 기존 공용 레포지토리에서 `AI_Interview_System` 파트를 분리하여 독립적으로 구축한 전용 저장소입니다. 정량 평가, 근거 제시, 실시간 피드백이 가능한 수준 높은 AI 모의면접 솔루션을 지향합니다.

---

## 🚀 프로젝트 개요
- **목적**: 지원자의 음성, 영상, 텍스트를 실시간으로 분석하여 루브릭 기반의 객관적인 면접 결과를 산출합니다.
- **핵심 기술**: 
  - **Multimodal**: 음성 인식(STT), 시선/감정 분석(DeepFace, MediaPipe), 음성 특징 분석(Parselmouth)
  - **Intelligence**: RAG 기반 질문 생성, LLM(Exaone, Llama 3.2 등) 기반 정량 평가 파이프라인
  - **Architecture**: PostgreSQL(Source of Truth), Redis(Runtime/Cache), SSE(Real-time Projection)

## 📁 주요 폴더 구조
- `app/`: 백엔드 API 서버 (FastAPI 기반)
- `frontend/`: React 기반 관리자 및 지원자 인터페이스
- `packages/`: 핵심 비즈니스 로직 모듈 (imh_core, imh_session, imh_eval 등)
- `scripts/`: DB 초기화, 시스템 검증 및 테스트 자동화 스크립트
- `docs/`: 프로젝트 아키텍처, 전략 문서, 개발 로그 및 벤치마크 리포트

## ⚙️ 실행 환경 및 설정
- **Python**: 3.10.11
- **가상환경**: `C:\big20\big20_AI_Interview_System\interview_env` (venv)
- **DB**: PostgreSQL (영속 저장소), Redis (런타임 캐시)
- **주요 설정**: `.env` 파일을 프로젝트 루트에서 관리합니다.

## 📄 문서 가이드
에이전트 및 개발자는 작업 시작 전 아래 문서를 반드시 숙지해야 합니다.
1. [CURRENT_STATE.md](docs/CURRENT_STATE.md): 시스템의 최신 개발 상태 및 기술 스택
2. [PROJECT_STATUS.md](docs/PROJECT_STATUS.md): 프로젝트 로드맵 및 아키텍처 원칙
3. [00_AGENT_PLAYBOOK.md](docs/00_AGENT_PLAYBOOK.md): 코딩 에이전트 운영 프로토콜 및 통제 규정

---
© 2026 BigData 20th Kingterview Team. All rights reserved.
