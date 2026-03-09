# TASK-010: MediaPipe 기반 시각 분석 구현 실패 및 의존성 충돌 보고서

## 1. 개요
- **작업명**: TASK-010 (Visual Analysis Playground 구현)
- **목표**: MediaPipe FaceMesh 및 Pose를 활용하여 시선, 머리 방향, 자세를 분석하는 API 엔드포인트 구축.
- **결과**: **실패 (환경 복구 후 작업 중단)**
- **사유**: 기존 프로젝트 의존성(`tensorflow==2.20.0`)과 MediaPipe 핵심 요구사항(`protobuf`) 간의 치명적 충돌로 인해 단일 가상환경(`interview_env`) 내 공존 불가능 확인.

---

## 2. 발생한 주요 에러 및 기술적 원인

### 2.1 MediaPipe 로딩 실패 (AttributeError)
- **현상**: `import mediapipe as mp`는 성공하나, `mp.solutions` 접근 시 에러 발생.
- **에러 메시지**: `AttributeError: module 'mediapipe' has no attribute 'solutions'`
- **원인**: MediaPipe는 특정 `protobuf` 버전(주로 3.x)을 선호하지만, 시스템에 더 높은 버전의 `protobuf`가 설치되어 있을 때 내부 라이브러리 로딩이 비정상적으로 중단됨.

### 2.2 Protobuf 버전 충돌 (The Core Conflict)
- **TensorFlow (기존)**: `tensorflow==2.20.0`은 `protobuf>=5.28.0`을 요구함.
- **MediaPipe**: 안정적인 동작을 위해 `protobuf<4`를 요구하는 경우가 많으며, `protobuf` 4.x/5.x 환경에서는 C++ 구현체 충돌이 발생함.
- **결과**: 하나의 venv에 두 패키지를 설치하면 어느 한 쪽의 의존성이 깨지는 **Dependency Hell** 발생.

### 2.3 윈도우 환경 특이 사항 (Hang Issue)
- **현상**: 의존성 해결을 위해 패키지를 강제 다운그레이드(`protobuf==4.25.8`, `tensorflow-cpu==2.13.0`)한 후 MediaPipe를 호출하면 프로세스가 응답 없음(Hang) 상태로 빠짐.
- **분석**: `tensorflow` 삭제/재설치 과정에서 윈도우 파일 잠금 문제로 인해 `site-packages` 내에 `~ensorflow`와 같은 불완전한 임시 디렉토리가 남고, 이것이 런타임에 DLL 로딩 간섭을 일으키는 것으로 보임.

---

## 3. 해결을 위한 시도 과정

### [Attempt 1] 환경 변수 강제 설정
- **내용**: `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` 설정을 통해 C++ 구현체 충돌을 회피하려 함.
- **결과**: 일부 환경에서 `AttributeError`는 해결되었으나, 성능 저하 및 런타임 안정성 보장 불가.

### [Attempt 2] 패키지 버전 고정 (Stability Combo)
- **내용**: 과거 검증 성공 사례인 `protobuf==4.25.8`, `tensorflow-cpu==2.13.0`, `mediapipe==0.10.5` 조합으로 전체 환경을 다운그레이드 시도.
- **결과**: `interview_env` 내의 기존 고버전 패키지들과 충돌하여 전체 가상환경이 파손됨 (복구 완료).

### [Attempt 3] DeepFace 일시적 격리
- **내용**: `DeepFaceEmotionProvider`를 `Mock`으로 대체하여 TensorFlow 의존성을 제거한 상태에서 MediaPipe 단독 검증.
- **결과**: 단독으로는 작동하지만, 결과적으로 전체 프로젝트 기능(감정 분석 + 시선 분석)을 동시에 서비스할 수 없음.

---

## 4. 향후 작업에 대한 제안 (기술적 교훈)

1. **서비스 분리(Microservices)**: 시선 분석(MediaPipe)과 감정 분석(DeepFace/TensorFlow)을 동일한 파이썬 프로세스에서 실행하지 말고, 별도의 서버나 Docker 컨테이너로 분리해야 함.
2. **별도 가상환경 운영**: `interview_env` 외에 시각 분석 전용 `visual_env`를 구축하여 API 호출 시에만 전환하는 방식 고려.
3. **MediaPipe 대체**: `protobuf` 환경에 더 유연한 다른 시각 분석 라이브러리(예: OpenFace, Dlib 등) 검토 필요.

---

## 5. 보관 데이터 상태
- **소스 코드**: 롤백 전 `research/task-010-mediapipe-conflict`와 같은 이름으로 별도 보관 권장.
- **로그**: `logs/freeze_before_task010_env_change.txt`에 안정적인 원본 환경 상태 보존됨.

---
**기록 일시**: 2026-02-10
**기록자**: AntiGravity AI Agent
