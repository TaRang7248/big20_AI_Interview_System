# TASK-034 STT 엔진 선정 및 외국어 인식 최적화 보고서

## 1. 개요
본 과업은 IMH 면접 시스템에 최적화된 로컬 STT 엔진을 선정하고, 특히 기술 면접의 핵심인 영어 전문 용어 인식 성능을 극대화하는 것을 목표로 수행되었다.

## 2. 수행 내역
- **벤치마크 프레임워크 구축**: CER, WER 외에 `foreign_term_accuracy` 및 `digit_accuracy` 메트릭 도입.
- **실사용자 데이터 검증**: 총 55개 테스트 케이스 및 사용자 실제 음성 2종에 대한 정밀 분석 수행.
- **프롬프트 튜닝**: Faster-Whisper의 `initial_prompt` 기능을 활용하여 IT 전문 용어(Docker, Kubernetes 등)의 영문 스펠링 복원율 향상.
- **모델 비교**: Faster-Whisper-v3-turbo (안정성/정확도) vs SenseVoiceSmall (속도) 비교.

## 3. 최종 결론
- **채택 엔진**: **Faster-Whisper-v3-turbo**
- **결정 사유**:
  - 기술 용어의 원문(영문) 복원력이 우수하여 LLM 후처리에 최적화됨.
  - 숫자 인식 정확도가 SenseVoice 대비 압도적으로 높음 (81.2% vs 3.1%).
  - 면접 데이터의 충실도(Fidelity)가 높아 정보 누락 리스크가 낮음.

## 4. 관련 문서
- 세부 분석 보고서: `docs/STT_ENGINE_SELECTION_REPORT.md`
- 최종 벤치마크 결과: `docs/benchmarks/stt/report_202602d_160840.json`

## 5. 최종 상태
- **Status: DONE**
- **Verification: Pass**
