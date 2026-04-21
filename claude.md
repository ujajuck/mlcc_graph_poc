# 프로젝트 목표

이 프로젝트의 1차 목표는 같은 데이터셋으로 아래 두 파이프라인을 각각 실행하고 비교하는 것이다.

1. Graphify → LightRAG 파이프라인
2. LightRAG 단독 파이프라인

비교 목적:
- 엔티티 및 관계 추출 품질 비교
- 질의응답 품질 비교
- 표가 포함된 Markdown 문서 처리 안정성 비교
- 결과 설명 가능성 비교
- 문서 추가/수정 시 재처리 편의성 비교

이 프로젝트는 최종 제품 구현보다 먼저, 위 두 파이프라인의 탐색적 비교 실험을 수행하는 것을 우선 목표로 한다.

---

# 실험 대상 데이터

입력 데이터는 Markdown(.md) 문서들이다.

문서 종류 예시:
- MLCC 제품사양 문서
- MLCC 설계 문서
- MLCC 고객 요청 사양 문서
- 기타 제품/사양 문서

중요:
- 모든 비교 실험은 반드시 동일한 데이터셋으로 수행한다.
- 파이프라인마다 입력 데이터가 달라지면 안 된다.

---

# 파이프라인 A: Graphify → LightRAG

## 목적
Graphify를 먼저 사용하여 엔티티/관계를 추출하고,
그 결과를 후처리하여 LightRAG에 다시 입력하는 파이프라인을 구성한다.

## 단계

### A-1. Markdown 전처리
- Markdown 표는 반드시 코드로 파싱한다.
- 표를 raw 텍스트 그대로 LLM에 전달하지 않는다.
- 가능하면 표를 key-value 또는 row 기반 구조로 변환한다.

### A-2. Graphify 실행
- 입력: 전처리된 Markdown 문서
- 출력:
  - `graph.json`
  - `graph.html`
  - `GRAPH_REPORT.md`

### A-3. Graphify 결과 후처리
- `graph.json`을 분석한다.
- 엔티티 이름 정규화
- 관계 정리
- 단위 정규화
  - VRAM, RAM 등은 GB 기준 통일
- LightRAG에 넣기 좋은 자연어 triple 또는 문서 형태로 변환한다.

예:
- `Laptop A has VRAM 4GB.`
- `Laptop A has RAM 16GB.`
- `Mabinogi requires minimum VRAM 2GB.`

### A-4. LightRAG 입력 생성
- Graphify 결과를 그대로 넣지 않는다.
- 후처리된 결과를 LightRAG 입력 포맷으로 별도 생성한다.

### A-5. LightRAG 실행
- A-4에서 생성한 입력으로 질의응답 가능 상태를 만든다.

---

# 파이프라인 B: LightRAG 단독

## 목적
원본 Markdown 문서를 LightRAG에 직접 입력하여 질의응답 파이프라인을 구성한다.

## 단계

### B-1. Markdown 전처리
- 파이프라인 A와 동일한 전처리 규칙을 적용한다.
- 표는 반드시 코드로 파싱한다.
- 전처리 정책은 A와 B가 동일해야 한다.

### B-2. LightRAG 입력 구성
- 원본 Markdown 또는 전처리된 문서를 직접 LightRAG에 입력한다.
- Graphify 결과는 사용하지 않는다.

### B-3. LightRAG 실행
- B-2의 입력으로 질의응답 가능 상태를 만든다.

---

# 비교 기준

두 파이프라인은 반드시 아래 기준으로 비교한다.

## 1. 엔티티 추출 품질
- 게임명, 제품명, GPU, VRAM, RAM, OS 등 주요 엔티티가 잘 추출되는가
- 동일 엔티티가 중복 생성되는가
- 표 데이터가 깨지지 않는가

## 2. 관계 추출 품질
- 제품과 스펙의 관계가 올바른가
- 게임과 요구사항의 관계가 올바른가
- 잘못된 관계가 많이 생기는가

## 3. 질의응답 품질
예시 질의:
- 온도특성이 X7R 이고 size가 0603 인 제품 목록
- 전압이 4.5V 이상인 C 특성 기종
- C 가 높아질때 영향을 받는 인자들
- 예외기종의 예외사항

확인 항목:
- 답변 정확성
- 근거 제시 가능성
- 일관성

## 4. 전처리 민감도
- Markdown 표가 많을 때 어느 파이프라인이 덜 깨지는가
- 문서 형식 변화에 얼마나 강한가

## 5. 증분 처리 편의성
- 문서 추가/수정 시 다시 실행하기 쉬운가
- 전체 재처리가 필요한가
- 변경 추적이 쉬운가

---

# 출력물 요구사항

각 파이프라인은 결과를 별도 디렉토리에 저장한다.

예시:
- `output/graphify_to_lightrag/`
- `output/lightrag_only/`

비교 결과는 별도 보고서로 정리한다.

예시:
- `output/comparison/comparison_report.md`

비교 보고서에는 최소한 아래가 있어야 한다.
- 사용한 데이터셋 목록
- 파이프라인별 실행 방식
- 질의별 응답 예시
- 장단점 요약
- 다음 단계 제안

---

# 구현 원칙

## 1. 전처리 일관성
- 두 파이프라인은 동일한 전처리 규칙을 사용한다.
- 비교 실험에서는 전처리 차이로 결과가 왜곡되면 안 된다.

## 2. 수치 처리 원칙
- VRAM, RAM, 저장공간, 가격 등 수치 비교는 가능하면 코드로 처리한다.
- 단위 변환은 deterministic하게 수행한다.
- LLM에게 숫자 계산과 단위 비교를 맡기지 않는다.

## 3. 단계 분리
- Graphify 단계와 LightRAG 단계를 섞지 않는다.
- 파이프라인 A와 B를 명확히 분리한다.

## 4. 비교 가능성 우선
- 완벽한 최종 구조보다, 두 파이프라인을 공정하게 비교할 수 있는 실험 구조를 우선한다.

---

# 권장 디렉토리 구조

data/
  raw/
  processed/

pipeline/
  common/
  graphify_to_lightrag/
  lightrag_only/

output/
  graphify_to_lightrag/
  lightrag_only/
  comparison/

scripts/
  preprocess/
  normalize/
  compare/

docs/

---

# 금지 사항

- 파이프라인 A와 B에 서로 다른 입력 데이터 사용 금지
- Markdown 표를 raw 상태로 LLM에 직접 전달 금지
- Graphify 결과를 후처리 없이 LightRAG에 직접 입력 금지
- 비교 기준 없이 감각적으로 평가 금지
- 수치 비교를 전적으로 LLM에 맡기지 말 것

---

# 작업 우선순위

1. 공통 전처리기 구현
2. Graphify → LightRAG 파이프라인 구현
3. LightRAG 단독 파이프라인 구현
4. 공통 질의셋 준비
5. 비교 실행
6. 비교 보고서 작성
