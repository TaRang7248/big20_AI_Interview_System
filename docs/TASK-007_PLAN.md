# TASK-007 Plan: Playground Text → Embedding (Search Query Focus)

## 1. TASK-007 Goal Definition
### 1.1 핵심 목표 (Core Objective)
- **면접 시스템 내 "검색(Retrieval)" 기능의 선행 단계**로서, LLM이 생성한 **"검색용 쿼리(Query Text)"**를 임베딩 벡터로 변환하는 파이프라인을 검증합니다.
- 본 TASK의 결과물인 벡터는 추후 RAG(Retrieval-Augmented Generation) 프로세스에서 지식 베이스 검색을 위한 Key로 사용됩니다.

### 1.2 명시적 제외 사항 (Explicit Non-Goal)
- **면접 대화 전체 임베딩 금지**: 사용자 답변 원문이나 전체 대화 로그를 벡터화하여 저장하는 것은 본 TASK의 목적이 아닙니다. 대화 이력은 JSONB 형태로 별도 관리되므로 벡터화 대상이 아닙니다.
- **상시 임베딩 금지**: 모든 발화에 대해 임베딩을 수행하지 않으며, 시스템이 "검색이 필요하다"고 판단했을 때 생성된 특정 쿼리 문자열에 대해서만 수행합니다.

## 2. Scope 명확화 (Do / Do Not)
### ✅ Do (포함)
- **Query Text → Embedding 변환 검증**: 
  - 단일 문장(Search Query)이 입력되었을 때, 이를 고정된 차원의 벡터(Float List)로 변환하는 흐름을 확인합니다.
- **Pipeline Interface 정의**: 
  - 입력값(Query String)과 출력값(Vector) 사이의 계약(Contract)을 정의합니다.
- **Provider 연결 구조 확인**: 
  - Local 또는 External 임베딩 생성기가 정상적으로 벡터를 반환하는지 Playground 수준에서 테스트합니다.

### 🚫 Do Not (제외)
- **Vector DB 저장 및 인덱싱**: 생성된 벡터를 DB(PGVector 등)에 저장하거나 조회하는 로직은 포함하지 않습니다.
- **RAG 검색 실행**: 벡터를 이용해 유사 문서를 찾는 검색 로직은 구현하지 않습니다.
- **전체 대화 로그 임베딩**: 대화의 문맥(Context) 전체를 임베딩하는 것은 포함하지 않습니다.
- **평가 및 채점 결합**: 답변의 정답 유사도 측정을 위한 임베딩은 본 TASK의 범위가 아닙니다(추후 TASK-010).

## 3. Conceptual Flow (개념적 단계)

### 3.1 전체 흐름 속의 TASK-007 위치
면접 시스템의 대화 흐름과 별도로, **"정보 검색이 필요한 순간"**에만 발생하는 Sub-Flow입니다.

1.  **Conversation Flow (Main)**:
    -   User Input → LLM Analysis → Response Generation
2.  **RAG Flow (Search Triggered)**:
    -   LLM Decision: "Information Needed"
    -   Query Generation: LLM generates a specific search query (e.g., "Python GIL 개념")
    -   **[TASK-007 Scope Start]**
    -   **Embedding Request**: Query Text → Embedding Provider
    -   **Vector Generation**: Provider returns `List[float]`
    -   **[TASK-007 Scope End]**
    -   *(Next Task)* Vector Search → Context Retrieval

### 3.2 내부 처리 단계
1.  **Input**: Search Query Text (String).
2.  **Preprocessing (Minimal)**: 쿼리의 품질을 높이기 위한 불필요한 공백 제거 등.
3.  **Embedding**: Provider를 통한 벡터 변환.
4.  **Output**: Embedding Vector.

## 4. 추상화 및 의존성 관리 (Abstraction Strategy)
### 4.1 Embedding Provider 추상화의 이유
- **모델 교체 유연성**: 
  - 간단한 키워드 매칭 수준에는 가벼운 Local 모델을, 복잡한 의미론적 추론이 필요한 경우 고성능 External 모델을 사용할 수 있도록 인터페이스를 통일해야 합니다.
- **비용 및 보안 관리**: 
  - 보안이 중요한 내부 데이터 검색 시에는 외부 전송 없는 Local 모델을 강제할 수 있어야 합니다.
- **실험 및 검증용 Mocking**: 
  - 개발 단계에서는 실제 모델 로딩 없이 랜덤 벡터를 반환하는 Mock Provider를 통해 빠른 API 테스트를 가능하게 합니다.

### 4.2 전략적 설계 방향
- **Interface**: `embed_query(text: str) -> vector` 형태의 단순한 서명을 가집니다.
- **Implementations**:
  - `MockEmbeddingProvider`: Random Vector 반환 (테스트용).
  - `LocalEmbeddingProvider`: 로컬 리소스 활용 (비용 절감).
  - `ExternalEmbeddingProvider`: API 기반 (고성능).
- 본 TASK에서는 구체적인 라이브러리(LangChain, OpenAI SDK 등)에 종속되지 않는 독자적인 추상 레이어를 설계 목표로 합니다.

## 5. 데이터 관점 (Data Perspective)
### 5.1 Input / Output 정의
- **Input**: 
  - **검색용 쿼리 (Query Text)**
  - 성격: LLM이 정보 검색을 위해 생성한 짧고 명확한 문장. (대화형 문체보다는 명사형/질문형 문장)
- **Output**: 
  - **임베딩 벡터 (Embedding Vector)**
  - 성격: 고정된 차원(Dimension)을 가진 실수 리스트(`List[float]`).

### 5.2 데이터의 휘발성 (Volatility)
- 본 TASK의 결과물인 벡터는 **저장 대상이 아닙니다.**
- 검색(Retrieval) 행위를 위한 일회성 Key로 사용되며, 검색 종료 후에는 메모리에서 해제됩니다.
- "벡터를 어딘가에 저장한다"는 것은 지식 베이스 구축 단계의 이야기이며, 본 TASK(Query Embedding)와는 무관합니다.

## 6. 다음 TASK로의 연결 포인트 (Next Steps)
본 TASK의 결과물(Query Vector)은 다음과 같은 후속 작업을 통해 시스템에 통합됩니다.

- **Vector Storage (Knowledge Base)**: 
  - 사전에 임베딩된 지식(면접 가이드, 기술 문서 등)이 저장된 저장소 구축.
- **Similarity Search (Retriever)**:
  - 본 TASK에서 생성한 Query Vector와 가장 유사한 지식 벡터를 DB에서 조회.
- **Context Injection (Generation)**:
  - 검색된 지식을 LLM의 프롬프트 컨텍스트로 주입하여 답변 정확도 향상.
