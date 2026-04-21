# 검색 플레이북

코드 매핑은 `catalog-codebook.md`에서 직접 해석하고, `search_rag`는 맥락 정보가 필요할 때만 사용한다. 이 reference는 search_rag 호출 시점과 방법, 그리고 최종 답변 구성을 안내한다.

## 목차

- 검색 Phase
- 랭킹 규칙
- 응답 형식
- 예시 처리 패턴
- 활성 라인업 조회 단계
- 한국어 쿼리 확장
- 가드레일 문구

## 컬렉션 라우팅

search_rag는 `collection` 파라미터로 검색 대상을 선택한다:

- `collection="context"` **(기본값)**: 패밀리, 주의 특성, 치수, 개요 등 맥락 청크만 포함 (88건). 코드 매핑 청크가 제외되어 노이즈가 적다.
- `collection="core"`: 순수 품번 매핑 테이블만 (106건). codebook으로 해결 안 되는 드문 검증 시에만.
- `collection="full"`: 전체 194건. 비권장.

모든 Phase 1, 2, 4 호출은 `collection="context"` (기본값)를 사용한다.

## 안티패턴 (하지 마라)

1. **코드 매핑을 위한 search_rag 호출**
   - 잘못: `search_rag("voltage code R 4V")`
   - 올바름: codebook → `R = 4.0Vdc`

2. **다중 조건을 하나의 쿼리에 합치기**
   - 잘못: `search_rag("0201 X5R 4.7uF 4V M tolerance industrial")`
   - 올바름: 코드 매핑은 codebook으로 한번에 확정, 패밀리는 별도 search_rag 1회

3. **필터 없는 넓은 검색**
   - 잘못: `search_rag("4.7uF capacitor")`
   - 올바름: `search_rag("4.7uF X5R 0201", search_group="dimension_reference")`

4. **같은 정보를 반복 검색**
   - 잘못: search_rag로 사이즈 코드 확인 후 다시 search_rag로 같은 사이즈 치수 검색
   - 올바름: codebook에서 사이즈 코드 확정, 필요 시 dimension_reference 1회로 치수 상세 보충

## 검색 Phase

### Phase 0: 코드 매핑 확정 (search_rag 호출 없음)

**catalog-codebook.md를 직접 읽어서 해결한다.** search_rag를 호출하지 않는다.

대상: 온도특성, 전압, 용량, 편차, 사이즈, 두께 (positions 1-7)

다중 조건이 들어와도 각 position은 독립적이므로 codebook에서 모든 position을 동시에 확정한다. 예시:
- `A` → 온도특성 X5R (codebook 온도특성 코드 표)
- `4V` → 정격전압 코드 R (codebook 정격전압 코드 표)
- `4.8uF` → 표준 명목 4.7uF(475), 5.1uF(515) (codebook E-series 규칙)
- `M` → 편차 +/-20% (codebook 용량 편차 코드 표)
- `L<=690um, W<=390um` → 사이즈 코드 03(0201/0603) (codebook 사이즈 코드 표)

### Phase 1: 패밀리/신뢰성 판단 (조건부 search_rag 1회)

적용처 힌트(산업용, 옥외, 저소음, 저ESL 등)가 있을 때만 search_rag를 **1회** 호출한다. 힌트가 없으면 Normal Standard로 가정하고 이 Phase를 건너뛴다.

쿼리 작성법:
- `search_group="family_reference"` 필터를 반드시 사용해 패밀리 관련 청크만 조회
- 적용처 키워드를 포함한 쿼리 구성

쿼리 패턴:

- `search_rag("high level II outdoor 85 85 1000h reliability", search_group="family_reference")`
- `search_rag("low ESL high speed IC decoupling", search_group="family_reference")`
- `search_rag("low acoustic noise piezo PMIC", search_group="family_reference")`

### Phase 2: 앵커 파트 탐색 (조건부 search_rag 1회)

Phase 0에서 확정된 코드 조합을 사용해 카탈로그 예시 파트를 **1회** 검색한다. 확정된 사이즈+온도특성+전압+용량으로 좁은 쿼리를 구성하면 정확도가 높아진다.

쿼리 패턴 (collection="context" 기본값 사용):

- `search_rag("0201 0603 X5R 4.7uF 4V", top_k=5)`
- `search_rag("0603 1608 X5R 47uF 6.3V", top_k=5)`
- `search_rag("1206 3216 X5R 220uF 6.3V", top_k=5)`

쿼리에 코드 매핑 용어(size code, voltage code 등)를 넣지 않는다. 확정된 코드 값만 넣는다.

### Phase 3: 활성 라인업 확인 (search_rag 아님)

`active_lineup_lookup` 또는 `search_query_database` 도구를 사용한다.

목표:

- 부분 또는 전체 코드 패턴이 `mdh_continous_view_3`에 현재 존재하는지 확인
- 최종 선택을 강제하기 전에 현행 `chip_prod_id` 히트를 표면화

패턴 예시:

- `chip_prod_id = CL32_106_O____`
- `chip_prod_id = %CL32_106_O____%`
- `chip_prod_id = CL03A515MR3____`

처리 규칙:

- 다건 반환 시: 목록을 보여주고 포커스된 후속 질문 1개
- 1건 반환 시: 남은 카탈로그 제약 대비 검증 계속
- 0건 반환 시: 카탈로그 스켈레톤을 유지하고 어떤 미해결 필드를 변경할 수 있는지 질문

### Phase 4: 검증 전용 특성 조회 (요청 시 search_rag 1회)

사용자가 DC 바이어스, AC 전압, 임피던스 등 검증 항목을 명시적으로 요청할 때만 호출한다.

쿼리 작성법:
- `search_group="caution_reference"` 필터 사용

쿼리 패턴:

- `search_rag("DC bias characteristics X5R sample", search_group="caution_reference")`
- `search_rag("effective capacitance high frequency low field", search_group="caution_reference")`
- `search_rag("impedance characteristic SRF ESR ESL", search_group="caution_reference")`

## 랭킹 규칙

후보를 아래 순서로 랭킹한다:

1. 모든 하드 제약 충족
2. 정확한 카탈로그 예시 파트 보유
3. 명시된 한계 내 치수 마진 유지
4. 요청 명목 용량에 가장 가까움
5. 의도된 적용처 또는 패밀리 일치
6. 바이어스 및 주파수 거동에 대한 검증 리스크 최소화

탈락 사유는 항상 명시한다:

- `탈락: 전압 불일치`
- `탈락: L 치수 최대치 초과`
- `탈락: 패밀리 불일치`
- `탈락: 해당 옵션에 대한 카탈로그 근거 없음`

## 응답 형식

아래 순서로 섹션을 출력한다:

1. **제약조건 요약** — hard/soft/검증 전용 분류 테이블
2. **스켈레톤 조립 과정** — codebook 기반 코드 매핑 + 후보 스켈레톤. `prompt-examples.md`의 형식 A(트리 다이어그램) 또는 형식 B(번호 주석)를 사용해 각 코드 위치의 의미를 시각적으로 보여준다.
3. **DB 활성 라인업 히트** (조회 실행 시)
4. **검증 필요 항목**

"정확 카탈로그 매칭"이나 "근접 카탈로그 앵커"는 별도 섹션으로 분리하지 않는다.

각 후보 스켈레톤에서 다음을 포함한다:

- 각 position(1-7)별 코드 확정 근거
- 확정 코드 vs 미확정 코드(`_` 또는 TBD)의 구분
- 후보가 복수일 때 우선순위 이유
- 아직 최종 주문 가능 P/N이 아닌 이유

각 DB 조회 단계에서 다음을 포함한다:

- 사용한 `chip_prod_id` 패턴
- 결과 건수 (0건, 1건, 다건)
- 히트 목록이 현재 존재만 증명하는지, 모호성도 해결하는지
- 후속 질문 (있는 경우)

## 예시 처리 패턴

사용자가 아래와 같이 요청할 때:

`A 온도특성, 정격전압 4V, L <= 690 um, W <= 390 um, T <= 550 um, 기준용량 4.8 uF, M편차, 고주파 저전계에서 1V DC 전계를 인가했을 때 최소 3.45 uF`

다음 패턴으로 응답한다:

- `A -> X5R`, `R -> 4.0Vdc`, `M -> +/-20%` 매핑
- 예시 파트 검색 전에 `03 (0201 / 0603)` 사이즈 필터 적용
- 가장 가까운 표준 명목 후보 `475`와 `515` 도출
- `0201 / 0603`, Class II, `4.7 uF` 근처에서 예시 파트 검색
- `1V DC 고주파 >= 3.45 uF` 요구는 조회된 청크가 대상 파트에 대해 직접 증명하지 않는 한 검증 전용으로 유지
- 카탈로그 근거가 뒷받침할 때만 더 높은 표준 명목을 우선 추천

## 활성 라인업 조회 단계

카탈로그 추론으로 부분적이지만 유용한 코드 패밀리가 도출되면, 스켈레톤에서 멈추지 않는다. DB 패턴으로 변환하고 대화형으로 계속 진행한다.

예시:

- 카탈로그 추론 결과: `CL32[온도특성 TBD]106[편차 TBD]O[...]`
- DB 조회 패턴으로 변환: `CL32_106_O____`
- 활성 라인업 DB 조회 도구 실행
- 반환된 목록 표시
- 포커스된 후속 질문: `온도특성은 X5R(A)와 X7R(B) 중 어느 쪽이 필요합니까?`

## 한국어 쿼리 확장

사용자가 한국어로 작성하면, 한국어 표현과 카탈로그용 영문 별칭을 함께 확장한다.

- `온도특성 A` -> `A`, `X5R`, `temperature characteristic`
- `정격전압 4V` -> `4.0Vdc`, `code R`, `rated voltage`
- `기준용량 4.8uF` -> `4.8uF`, `4.7uF`, `5.1uF`, `475`, `515`, `capacitance code`
- `M편차` -> `+/-20%`, `tolerance code M`
- `산업용` -> `industrial`, `High Level I`, `High Level II`
- `현재 흐르는 기종`, `현행품`, `현재 흐르는 품목` -> `active lineup`, `chip_prod_id`, `current DB hits`
- `저소음` -> `Low Acoustic Noise`, `ANSC`, `THMC`
- `저ESL` -> `Low ESL`, `LICC`, `SLIC`, `reverse`, `3T`, `8T`
- `고주파 저전계`, `1V DC`, `직류 바이어스` -> `DC bias`, `AC voltage characteristics`, `effective capacitance`, `sample graph`

## 가드레일 문구

필요 시 아래 문구를 사용한다:

- `정확한 카탈로그 일치 항목이 조회된 근거에 없습니다.`
- `근접 카탈로그 앵커는 실현 가능성 근거이며, 최종 주문 가능 확정이 아닙니다.`
- `권장 사전선정안은 후보 스켈레톤입니다.`
- `1V DC 바이어스 및 주파수 의존 유효용량은 데이터시트 검증이 필요합니다.`
