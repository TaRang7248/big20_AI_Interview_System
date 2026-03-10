# TASK-034 STT Benchmark Framework Plan

## 1. 개요 (Overview)
본 계획은 GTX 1660 Super (6GB) 환경에서 최적의 한국어 STT 모델을 선정하기 위한 "벤치마크 프레임워크"의 설계 및 구현 방안을 정의합니다. 
최근 LLM 성능 테스트가 종료됨에 따라, 본 프레임워크는 구현뿐만 아니라 `voice_test_collection` 데이터 전체에 대한 전면적인 벤치마크 실행까지 목표로 합니다.
실행 로그 및 평가 결과는 재현 가능하도록 파일 리포트 형태로 기록됩니다.

## 2. 확정된 벤치마크 정책 (Core Policies)

### 2.1 오디오 데이터 로드 및 전처리
1. **데이터 경로 정책**:
   - 상대경로 기반 구현: 기본적으로 `IMH/AI_Interview_System/data/voice_test_collection` 경로를 참조합니다.
   - 실행 시 CLI 인자(argument)를 통해 경로 override(사용자 절대경로 등)를 지원합니다.
2. **오디오 표준화 전략 (Audio Standardization)**: 
   - 원본 오디오 형식(wav, flac, mp3)을 유지한 채, 평가 로드 시점에 `16kHz, mono` 포맷으로 자동 리샘플링하여 전달합니다.

### 2.2 디코딩 및 추론 전략
1. **Decoding 파라미터 통일 전략 (Greedy Search 강제)**: 
   - 모든 모델에 대하여 공정한 비교를 위해 `beam_size=1`, `temperature=0.0`, `language="ko"`를 강제 고정 적용합니다.
2. **워밍업 정책 (Warmup Policy)**: 
   - First Token Latency 측정의 왜곡(초기 모델 로딩 및 VRAM 할당 지연)을 막기 위해, 실제 평가 직전에 1초 미만의 짧은 더미 오디오로 1회 워밍업 추론을 무조건 수행합니다.

### 2.3 GPU 안정성 기준 (GTX 1660 Super 6GB)
1. 모델 인터페이스 로드 전 `torch.cuda.is_available()` 검사를 필수로 수행.
2. STT 추론은 명시적으로 `device="cuda"`를 강제 지정 (CPU fallback 전면 금지).
3. **VRAM 컷오프**: 추론 중 Peak VRAM 측정 시 5.5GB 초과 시나리오에 대해서 해당 모델의 벤치마크를 강제 실패(OOM Skip) 처리합니다.

### 2.4 평가 및 메트릭 기준
1. **정규화 규칙 및 정확도 지표 강화**:
   - **외래어/영어 정규화 금지**: 영어 표현은 영어 단어 그대로 생성해야 합니다.
   - **숫자 정규화 유지**: "이십사 ↔ 24" 변환은 유지하여 동일 의미로 처리.
2. **평가 지표 구성**:
   - 정확도 (Raw CER / WER)
   - 지연 (RTF, First Token Latency)
   - 리소스 (Peak VRAM)
   - **Digit Accuracy Score**: 숫자 표기별도 정확도
   - **Foreign Term Accuracy**: IT 외래어 사전(`it_terms.txt`)을 기준으로 영어 단어 생성 정확성 검증.
3. **최종 선정 알고리즘**:
   - 정확도를 최우선으로 하되, 원활한 운영을 위해 RTF < 1.0, VRAM <= 5.5GB 여부를 Pass/Fail 기준으로 삼아 최종 적합 모델을 추천합니다.

## 3. 구현 설계 구조 (Proposed Changes)

프레임워크는 차후 Stage 3 Multimodal Interface STT 계층으로의 통합을 고려하여, 철저하게 인터페이스 기반으로 설계됩니다. 비즈니스 로직은 `IMH/AI_Interview_System/packages/imh_stt_benchmark/` 하위에 배치되며 실행 진입점은 `scripts/`에 위치합니다.

### `packages/imh_stt_benchmark/`

#### [NEW] `domain.py`
- STT Benchmark 도메인 객체(MetricsResult, TestCase 등) 정의.
- Stage 3에서 실제 STT 엔진이 채택될 수 있도록 표준화된 `STTEngineProtocol` 명세화. 반환 DTO 보장 필드:
  - `raw_text`, `normalized_text`, `inference_time_seconds`, `audio_duration_seconds`, `rtf`, `peak_vram_mb`, `metadata`

#### [NEW] `normalization.py`
- 숫자 정규화 로직 유지 제공.

#### [NEW] `evaluator.py`
- `torch.cuda` 상태 확인 및 통일된 Greedy Search 디코딩 파라미터 할당을 강제 수행합니다.

#### [NEW] `metrics.py`
- `Foreign Term Accuracy` (사전 기반 IT 용어 채점), `Digit Accuracy Score` 등 커스텀 평가 로직 포함.

#### [NEW] `vram_monitor.py`
- STT VRAM Peak 측정 스레드.

#### [NEW] `runner.py`
- 전체 테스트 디렉토리를 순회하는 파이프라인.

### `packages/imh_stt_benchmark/data/`
#### [NEW] `it_terms.txt`
- `Foreign Term Accuracy` 평가 기준 단어 목록 사전 파일. 향후 확장을 위해 외부에 분리함.
- 초기 단어: Python, FastAPI, Redis, Docker, Kubernetes, PostgreSQL, Whisper, ONNX, PyTorch, React, AWS, EC2, S3, RAG, FAISS, CQRS, TTL

### `scripts/`

#### [NEW] `run_stt_benchmark.py`
- 벤치마크 전면 실행 진입점 스크립트. 상대경로를 기본으로 탐색하되 CLI `--data-dir` 인자를 통해 사용자 오버라이드 가능.

## 4. 최종 보고서 산출물
벤치마크 종료 후 다음 내용이 포함된 마크다운 보고서를 출력합니다:
- **모델 간 종합 비교표**: CER, WER, RTF, Peak VRAM.
- **특화 지표 분석표**: 숫자 인식 정확도(Digit Accuracy), 영어 단어 생성 정확도(Foreign Term Accuracy).
- **대표 오인식 사례 分析**: Ground Truth 내 한글 음차 표기 오류 및 환각 사례.
- **GTX 1660 Super 환경 최종 추천 모델 명시**: 단일 모델.
