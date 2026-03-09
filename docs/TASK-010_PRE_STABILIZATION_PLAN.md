# PRE_TASK-010_STABILIZATION_PLAN: 선행 안정화 및 환경 정합성 회복 계획

본 문서는 TASK-010(Visual 분석) 착수 전, 기존 기능의 결함을 제거하고 프로젝트 환경의 안전한 기준선(Baseline)을 확립하기 위한 선행 안정화 계획서입니다.

## A. 목적 및 범위
- **목적**: TASK-008(Emotion) 분석 엔드포인트에서 발견된 회귀 버그를 수정하여 시스템의 신뢰성을 회복한다.
- **범위**: 
  - `IMH/api/playground.py` 내 `analyze_emotion` 엔드포인트의 제어 흐름 로직 수정.
  - TASK-001부터 TASK-009까지의 전체 기능에 대한 재검증(Regression Test).
  - **주의**: 본 작업은 TASK-010 구현을 포함하지 않으며, 오직 기존 기능의 복구 및 안정화에 집중한다.

## B. 금지 사항
- **MediaPipe 및 TASK-010 관련**: 어떠한 MediaPipe 설치 시도, 구현, 의존성 테스트도 금지한다.
- **환경 변경 금지**: 패키지의 신규 설치, 삭제, 버전 변경(Upgrade/Downgrade)을 절대로 수행하지 않는다. 오직 파이썬 소스 코드의 로직만 수정한다.
- **코드 수정 시점**: 본 계획서에 대한 사용자의 명시적 승인 전까지는 어떠한 코드 수정도 수행하지 않는다.

## C. 안전 백업 규칙 (구현 전 단계 수행)
코드 수정 단계에 진입하기 전, 현재의 안전한 환경 상태를 보존하기 위해 다음 작업을 선행한다.
1. **의존성 스냅샷**: 다음 명령을 통해 현재 패키지 상태를 기록한다.
   - `C:\big20\big20_AI_Interview_System\interview_env\Scripts\python.exe -m pip freeze > docs/env_snapshot_20260210.txt`
2. **코드 백업**: 변경 대상 파일(`IMH/api/playground.py`)의 변경 전 상태를 확인하고, 에이전트의 작업 기록에 명확히 남긴다.

## D. 수정 설계 (Logic Level)
- **에러 원인**: `finally` 블록에서 예외 변수 `e`를 조건 없이 참조하여 에러가 발생하지 않은 정상 흐름에서도 `UnboundLocalError`가 유발됨.
- **수정 원칙**:
  - `finally` 블록 내부에서 예외 객체(`e`)를 직접 참조하지 않도록 제어 흐름을 분리한다.
  - **리소스 정리 보장**: 성공 여부와 관계없이 사용된 임시 파일(`temp_file_path`)이 반드시 삭제되도록 `finally` 블록의 본래 목적(Cleanup)을 달성한다.
  - **로깅 정교화**: 예외 발생 시에는 `logger.exception` 또는 예외 객체가 존재하는 스코프 내에서 로깅을 수행하여 정밀한 에러 추적을 보장한다.
  - **결과 무결성**: 로직 수정 후에도 Emotion 분석 결과 DTO의 규격 및 응답 형식은 기존 설계를 무조건 유지한다.

## E. 검증 계획 (체크리스트)
수정 후 다음 검증을 순차적으로 수행하여 정합성을 증명한다.

| 검증 항목 | 실행 방법 (절대 경로 필수) | 기대 결과 | 확인 포인트 |
| :--- | :--- | :--- | :--- |
| **1. TASK-008 복구 확인** | `...python.exe scripts\verify_task_008.py` | PASS (Exit code 0) | `UnboundLocalError` 소멸 및 정상 응답 |
| **2. 전체 기능 재검증** | `...python.exe`를 사용하여 `scripts\` 내 `verify_task_001~009` 순차 실행 | 전체 PASS | 기존 DONE 상태 기능의 영향 없음 확인 |
| **3. 리소스 정리 확인** | 테스트 실행 후 `%TEMP%` 경로 확인 (에이전트 판단) | 임시 파일 잔류 없음 | `finally` 블록의 정상 동작 증빙 |
| **4. 로깅 정책 준수** | `logs/runtime/runtime.log` 및 `agent.log` 확인 | 예외 발생 시 스택트레이스 기록 | `logger.exception` 사용 적절성 확인 |

## F. 완료 기준 (Definition of Done)
1. `scripts/verify_task_008.py`가 에러 없이 성공적으로 실행됨.
2. TASK-001부터 TASK-009까지의 모든 검증 스크립트가 `interview_env` 환경에서 PASS됨.
3. 수정 사항이 의존성 변경 없이 오직 `playground.py`의 로직 수정에 한정됨.
4. 본 계획서 및 최종 검증 결과 보고서가 `docs/` 폴더에 최신화됨.

---
**작업 환경**: `C:\big20\big20_AI_Interview_System\interview_env` (Fixed)
**실행 도구**: `interview_env\Scripts\python.exe` (Fixed)
