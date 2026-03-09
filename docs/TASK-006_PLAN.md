# [Plan] TASK-006 Playground PDF → Text (문서 업로드 API) v1.1

## 1. 배경 및 목적
본 작업은 Playground에서 사용자가 PDF 문서를 업로드하고, 그 내용을 텍스트로 추출하여 반환받는 API의 "최소 골격"을 구축하는 것을 목표로 합니다.
Playground는 실서비스(면접 질문 생성 등) 전 단계에서 다양한 모듈(STT, PDF 파서 등)의 성능과 동작을 빠르게 검증하기 위한 실험 공간입니다.
이번 Phase 2 단계에서는 **텍스트 레이어가 존재하는 PDF** 처리에 집중하며, 고비용 연산(OCR, 레이아웃 분석)은 의도적으로 배제하여 시스템의 경량성과 응답 속도를 확보합니다.

## 2. 요구사항 정의

### 2.1 기능 요구사항
1. **PDF 업로드**: 사용자는 `.pdf` 확장자를 가진 파일을 업로드할 수 있어야 합니다.
2. **텍스트 추출**: 업로드된 PDF 파일에서 텍스트 콘텐츠를 추출해야 합니다.
   - 단, **텍스트 레이어가 있는 PDF만** 지원합니다.
3. **결과 반환**: 추출된 전체 텍스트(`full_text`)와 페이지별 텍스트(`pages`), 메타데이터를 JSON 형태로 반환합니다.
4. **실패 처리**: 암호화된 PDF, 손상된 파일 등에 대해 적절한 에러 메시지를 반환해야 합니다.
   - 텍스트가 없는(이미지 전용) PDF의 경우 `422 Unprocessable Entity`로 명확히 실패 처리합니다.

### 2.2 비기능 요구사항
1. **파일 보안 및 정리**: 업로드된 파일은 작업 완료 즉시 삭제되어야 하며, 로컬 스토리지에 영구 저장되어서는 안 됩니다. (TEMP 처리 원칙 준수)
2. **용량 및 연산 제한 (서버 안정성 강화)**:
   - **파일 크기**: 10MB 이하
   - **페이지 수**: **최대 50페이지** (초과 시 `400 Bad Request` 반환하여 ThreadPool 블로킹 방지)
3. **응답 시간**: 텍스트 추출은 CPU 연산 작업이므로, 처리 시간(`latency_ms`)을 반드시 로그에 남겨 모니터링합니다.
4. **일관성**: 에러 응답 및 로깅 포맷은 TASK-005(STT)와 동일한 구조를 따릅니다.

## 3. API 계약 초안 (스펙)

### 3.1 엔드포인트
- **URL**: `POST /api/v1/playground/pdf-text`
- **Content-Type**: `multipart/form-data`

### 3.2 요청 (Request)
| 필드명 | 타입 | 필수 | 설명 |
| :--- | :--- | :--- | :--- |
| `file` | File | Yes | 분석할 PDF 파일 (`.pdf`, Max 10MB) |

### 3.3 응답 (Response)
RAG 및 인용(Citation) 기능 확장을 고려하여 페이지별 텍스트 정보를 포함합니다.
성공 시 200 OK와 함께 아래 JSON 반환:

```json
{
  "full_text": "추출된 전체 텍스트 내용 합본...",
  "pages": [
    {
      "page_number": 1,
      "text": "1페이지 텍스트 내용..."
    },
    {
      "page_number": 2,
      "text": "2페이지 텍스트 내용..."
    }
  ],
  "metadata": {
    "num_pages": 2,
    "file_size_bytes": 10240,
    "extraction_method": "pypdf"
  }
}
```

### 3.4 주요 에러 시나리오
- **400 Bad Request**:
  - `INVALID_FILE_FORMAT`: `.pdf`가 아닌 파일 업로드 시
  - `FILE_TOO_LARGE`: 용량(10MB) 초과 또는 **페이지 수(50페이지) 초과** 시
  - `ENCRYPTED_PDF`: 암호화되어 읽을 수 없는 PDF
- **422 Unprocessable Entity**:
  - `NO_TEXT_FOUND`: 정상 PDF이나 텍스트 레이어가 없어 추출된 내용이 없는 경우 (OCR 미지원 안내 포함)
- **500 Internal Server Error**:
  - `PDF_PROCESSING_ERROR`: 파싱 중 알 수 없는 예외 발생

## 4. 처리 흐름 (Sequence)

1. **요청 수신 (Controller)**:
   - `request_id` 생성 및 진입 로그 기록.
   - 1차 검증: 확장자 확인.

2. **임시 저장 (Temp Handler)**:
   - `tempfile`을 사용하여 임시 경로에 파일 저장 (Chunk 단위 쓰기).
   - 용량 제한(10MB) 체크 → 초과 시 즉시 삭제 및 400 에러.

3. **텍스트 추출 (Service/Provider)**:
   - `pypdf.PdfReader` 로드.
   - **2차 검증**: `len(reader.pages)` 체크 → **50페이지 초과 시 중단 및 400 에러**.
   - 암호화 여부 체크.
   - 페이지별 텍스트 추출 반복.
   - 추출된 텍스트가 공란인지 확인 → 전체 공란이면 `NO_TEXT_FOUND` (422) 발생.

4. **로깅 (Logging)**:
   - **필수 로그 항목**: `latency_ms`, `total_chars`, `num_pages`
   - 예: `PDF Extraction Success. Pages: 5, Chars: 3500, Time: 120ms [RequestID: ...]`

5. **결과 반환 및 정리 (Cleanup)**:
   - DTO 매핑 반환.
   - `finally` 블록에서 임시 파일 삭제 및 삭제 로그 기록.

## 5. 테스트 및 검증 계획

### 5.1 최소 수용 기준 (Acceptance Criteria)
- [ ] Swagger UI에서 PDF 업로드 시 `full_text`와 `pages` 배열이 모두 포함된 응답을 받는다.
- [ ] 51페이지 이상의 PDF 업로드 시 `FILE_TOO_LARGE` 에러가 발생한다.
- [ ] 이미지로만 구성된 PDF 업로드 시 `NO_TEXT_FOUND` (422) 에러가 발생한다.
- [ ] 서버 로그 파일에 처리 시간(ms), 글자 수, 페이지 수가 정확히 기록된다.

## 6. 범위 제외 (Non-Goals) 및 향후 로드맵
- **OCR(광학 문자 인식) 미지원**:
  - 본 Task에서는 `tesseract` 등의 OCR 엔진을 사용하지 않습니다.
  - 스캔된 문서나 이미지 PDF 처리는 **Phase 2 범위 밖**으로 정의합니다.
  - *향후 계획*: 필요 시 별도 Task(예: `TASK-0xx OCR Integration`)를 통해 LlamaParse 또는 Vision API 연동을 검토합니다.
- **복잡한 레이아웃 분석**: 표(Table), 다단 등은 단순 텍스트로 나열(Plain Text)하며 구조적 분석은 수행하지 않습니다.
- **파일 영구 저장**: 원본 및 추출 텍스트의 DB 저장은 수행하지 않습니다.

---

### [사용자 승인 필요 항목 체크리스트]
작업을 진행하기 위해 아래 항목들에 대한 승인을 요청합니다.
1. [ ] **라이브러리**: `pypdf` 사용을 확정하시겠습니까? (순수 파이썬 라이브러리)
2. [ ] **안정성 제약**: 최대 50페이지 제한 및 10MB 용량 제한 정책에 동의하십니까?
3. [ ] **범위**: 이미지 PDF(OCR) 미지원 및 `NO_TEXT_FOUND`(422) 처리 정책에 동의하십니까?
4. [ ] **구조**: 유연성 확보를 위한 `IPDFProvider` 인터페이스 도입에 동의하십니까?
