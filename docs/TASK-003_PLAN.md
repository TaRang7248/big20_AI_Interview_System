# TASK-003 Plan: Provider 인터페이스 정의 + Mock 구현

## A. 현 상태 확인

### 1. Core 구성 요소 (TASK-002 완료)
- **[문서 근거: CURRENT_STATE.md]**: `packages/imh_core` 패키지가 생성되어 있으며 `config`, `errors`, `dto` 모듈을 포함합니다.
- **[문서 근거: TASK-002_PLAN.md]**: `imh_core`는 의존성 방향의 최하단에 위치하며, Provider 계층이 이를 참조합니다.

### 2. Provider 계층 위치 (Boundary)
- **위치**: `packages/imh_providers/`
- **[문서 근거: 00_AGENT_PLAYBOOK.md]**: "1.3 모듈/폴더 구조 원칙" 및 "6. 확정된 폴더 / 모듈 구조"에 따라 `packages/` 아래에 위치합니다.

---

## B. Provider 책임 범위 정의

### 1. 추상화 대상 (Target)

| Provider 유형 | 추상화 대상 (기술 스택) | 책임 | 근거/비고 |
| :--- | :--- | :--- | :--- |
| **STTProvider** | Faster-Whisper (GPU) | 오디오 파일을 텍스트로 변환 (Transcribe) | **[문서 근거: CURRENT_STATE.md]** |
| **LLMProvider** | GPT-4o, Qwen3-4B, etc. | 프롬프트/대화 히스토리를 기반으로 텍스트 응답 생성 | **[문서 근거: CURRENT_STATE.md]** |
| **EmotionProvider** | DeepFace (CPU) | 이미지/프레임에서 감정(Emotion) 상태 추출 | **[문서 근거: CURRENT_STATE.md]** |
| **VisualProvider** | MediaPipe (CPU) | 영상에서 시선(Gaze), 행동 패턴 분석 | **[문서 근거: CURRENT_STATE.md]** |
| **VoiceProvider** | Parselmouth (CPU) | 음성 파형에서 Tone, Pitch, Jitter 등 분석 | **[문서 근거: CURRENT_STATE.md]** |

### 2. 확장성 고려 사항 (Phase 2~5)
- **[Phase 1 (Current)]**:
    - 기본 인터페이스 정의 및 Connectivity 검증.
    - **[가정]**: 로컬 개발 환경(No-GPU) 지원을 위한 Mock 구현체 우선 제공.
- **[Phase 2 (On-Premise Migration)]**:
    - **[가정]**: `MockProvider` -> `LocalModelProvider` 교체 시 인터페이스 변경 없이 Config 교체만으로 동작해야 함.
- **[Phase 5 (Playground)]**:
    - **[가정]**: 다양한 모델(API vs Local)을 런타임에 비교할 수 있도록, 동일 인터페이스 하의 다형성(Polymorphism) 보장 필요.

---

## C. Provider 인터페이스 설계 (계약)

### 1. 공통 설계 원칙
- **DTO 사용 (강제)**: 모든 입출력 데이터는 `packages/imh_core/dto.py`에 정의된(또는 확장된) Pydantic 모델을 사용한다.
    - `str`, `dict` 등의 Raw 타입 반환 금지.
- **에러 처리**: `packages/imh_core/errors.py`의 `IMHBaseError`를 상속받은 `ProviderError` 계열로 wrapping하여 throw한다.

### 2. 인터페이스 후보 목록 (Interfaces)

> **참고**: 아래 메서드 시그니처는 개념적 정의이며, 실제 구현 시 `async/await`가 추가될 수 있습니다.

#### 1) `ISTTProvider` (STT)
- **[문서 근거: CURRENT_STATE.md]**
- **메서드**:
    - `transcribe(audio_file_path: str) -> TranscriptDTO`
    - (*TranscriptDTO: text, confidence, language, segments 등*)

#### 2) `ILLMProvider` (LLM)
- **[문서 근거: CURRENT_STATE.md]**
- **DTO 설계**:
    - `LLMMessageDTO`: `{role: str, content: str}` (기존 List[Dict] 대체)
    - `LLMResponseDTO`: `{content: str, token_usage: Optional[dict], finish_reason: str}`
- **메서드**:
    - `chat(messages: List[LLMMessageDTO], system_prompt: Optional[str]) -> LLMResponseDTO`

#### 3) `IEmotionProvider` (Emotion)
- **[문서 근거: CURRENT_STATE.md]**
- **메서드**:
    - `analyze_face(image_path: str) -> EmotionResultDTO`
    - (*EmotionResultDTO: dominant_emotion, scores 등*)

#### 4) `IVisualProvider` (Visual)
- **[문서 근거: CURRENT_STATE.md]**
- **메서드**:
    - `analyze_frame(image_path: str) -> VisualResultDTO`
    - (*VisualResultDTO: gaze_vector, pose_landmarks 등*)

#### 5) `IVoiceProvider` (Voice)
- **[문서 근거: CURRENT_STATE.md]**
- **메서드**:
    - `analyze_audio(audio_path: str) -> VoiceResultDTO`
    - (*VoiceResultDTO: pitch, jitter, shimmer 등*)

---

## D. Provider 선택 및 주입 전략 (설계)

이 섹션은 구현 대상이 아닌 **설계 의사결정**입니다.

### 1. 결정 주체 (Decision Source)
- **Config**: `packages/imh_core/config.py` 내 `PROVIDER_TYPE` (예: "MOCK", "OPENAI", "LOCAL") 설정값에 따라 결정한다.
- **[가정]**: 환경변수 `IMH_PROVIDER_TYPE` 설정을 통해 제어한다.

### 2. 주입 방식 (Injection Mechanism)
- **Factory Pattern**: 각 패키지(예: `imh_providers/llm/`)의 `__init__.py` 또는 `factory.py`에서 `get_provider()` 함수를 노출한다.
- **동작 방식**:
    1.  App 실행 시 `get_llm_provider()` 호출.
    2.  Config를 확인.
    3.  `if config.PROVIDER_TYPE == "MOCK": return MockLLMProvider()`
    4.  그 외의 경우 적절한 구현체 반환.
- **장점**: 호출부(Service Layer)는 구체적인 클래스(`MockLLMProvider`)를 몰라도 되며, 인터페이스(`ILLMProvider`)에만 의존하게 된다.

---

## E. Mock Provider 설계

### 1. Mock의 목적
- **GPU 의존성 제거**: 개발자 로컬 PC(MacBook Air 등)에서 무거운 모델 로딩 없이 로직 개발 가능.
- **API 비용 절감**: 유료 LLM API 호출 없이 테스트 가능.
- **테스트 결정성(Determinism)**: 항상 동일한 입력에 동일한 출력을 보장하여 테스트 안정성 확보.

### 2. Mock 동작 전략
- **Fixed/Dummy Response**: 유효한 형식의 고정 더미 데이터(DTO)를 반환한다.
- **Latency Simulation (Optional)**:
    - 기본값: **0ms** (즉시 반환).
    - 설정 기반: `config.MOCK_LATENCY_MS` 값이 설정된 경우에만 `asyncio.sleep()`을 수행한다.
    - 목적: UI 로딩 상태 테스트 시에만 제한적으로 사용하며, CI/CD 테스트 속도를 저하시키지 않는다.

---

## F. 패키지 / 폴더 배치 설계안

### 1. 배치안 (Domain-based Grouping) - **추천**
도메인별로 폴더를 나누고, 그 안에 Interface(base)와 구현체(mock, impl)를 모으는 구조.

```text
packages/imh_providers/
├── __init__.py
├── stt/
│   ├── __init__.py
│   ├── base.py    # ISTTProvider (Abstract Base Class)
│   └── mock.py    # MockSTTProvider
├── llm/
│   ├── __init__.py
│   ├── base.py
│   └── mock.py
├── emotion/
│   ├── __init__.py
│   ├── base.py
│   └── mock.py
├── visual/
│   ├── __init__.py
│   ├── base.py
│   └── mock.py
└── voice/
    ├── __init__.py
    ├── base.py
    └── mock.py
```

---

## G. 승인 기준 (Definition of Done)

### 1. Plan 승인 기준 (Plan DoD)
- [ ] **책임 범위**: 각 Provider의 역할이 `CURRENT_STATE.md`와 일치하는가?
- [ ] **인터페이스 정합성**: 모든 입출력이 DTO 기반으로 정의되었는가? (Raw 타입 반환 없음)
- [ ] **에러/로깅**: `imh_core`의 에러 체계를 따르는가?
- [ ] **Mock 전략**: Latency 설정이 옵션(Default 0)으로 명시되었는가?
- [ ] **패키지 배치**: 도메인별 응집도가 높은 구조인가?
- [ ] **구분 명확화**: 문서 근거와 가정(Assumption)이 명확히 분리되었는가?

### 2. Implement 단계 DoD (예고)
- [ ] `packages/imh_providers` 하위에 5개 도메인 디렉토리 생성 완료.
- [ ] 각 도메인별 `base.py` (Interface) 및 `mock.py` (Mock Implementation) 구현 완료.
- [ ] `get_provider()` 팩토리 함수(또는 이에 준하는 주입 메커니즘) 초안 작성.
- [ ] 검증 스크립트(`scripts/verify_task_003.py`) 실행 시 모든 Mock Provider가 정상적인 DTO를 반환함.

---

## H. Implement 단계 예고 (Artifacts)

승인 시 아래 파일들이 생성됩니다. (수정: 없음, 모두 신규 생성)

1.  `packages/imh_providers/__init__.py`
2.  `packages/imh_providers/stt/base.py`, `packages/imh_providers/stt/mock.py`
3.  `packages/imh_providers/llm/base.py`, `packages/imh_providers/llm/mock.py`
4.  `packages/imh_providers/emotion/base.py`, `packages/imh_providers/emotion/mock.py`
5.  `packages/imh_providers/visual/base.py`, `packages/imh_providers/visual/mock.py`
6.  `packages/imh_providers/voice/base.py`, `packages/imh_providers/voice/mock.py`
7.  `scripts/verify_task_003.py` (검증용)
