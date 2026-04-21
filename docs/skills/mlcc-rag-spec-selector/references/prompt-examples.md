# 프롬프트 예시

한국어, 영어, 또는 혼합 언어 사용자 요청에서 스킬을 호출할 때 이 예시들을 참고한다.
응답 형식(스켈레톤 형식 A/B, 전체 응답 구조)은 `response-formats.md`를 참고한다.

---

## 스펙 사전선정

### 예시 1

`고객사 의뢰로 스펙 만족하는 MLCC 기종부터 선정해야해. A 온도특성, 정격전압 4V, L size 최대 690um, W size 최대 390um, T size 최대 550um, 기준용량 4.8uF, M편차, 고주파 저전계에서 1V DC 전계를 인가했을 때 최소 3.45uF 를 만족하는 기종을 catalog 기준으로 찾아줘.`

기대 동작:

- `A`를 `X5R`로 해석
- 치수를 `mm`로 정규화
- `4.8uF` 근처에서 가장 가까운 표준 명목 후보를 도출
- `1V DC` 및 `고주파` 요구는 정확한 근거가 조회되지 않는 한 검증 전용으로 유지

### 예시 2

`Use $mlcc-rag-spec-selector to preselect SEMCO MLCC candidates for X7R, 6.3V, 0201/0603-class dimensions, nominal around 4.7uF, +/-20% tolerance. Answer in Korean and separate catalog facts from datasheet-only checks.`

기대 동작:

- 코드 테이블을 먼저 해석
- 인접 신제품 앵커를 검색
- 정확한 주문 가능 파트가 증명되지 않으면 후보 스켈레톤을 반환

---

## 신뢰성 및 패밀리 선택

### 예시 3

`서버 전원용이라 습도 신뢰성이 중요해. 85C/85%RH/1000h 쪽에 맞는 family가 필요하고, 가능한 경우 High Level II 기준으로 size와 voltage 조건에 맞는 후보를 찾아줘.`

기대 동작:

- `High Level II`로 라우팅
- 예시 파트 전에 `reliability_level`과 관련 제품 패밀리 청크를 검색
- 신뢰성 패밀리가 카탈로그 근거는 있지만 정확한 라인업은 아직 검증이 필요하다면 그렇게 설명

### 예시 4

`I need a low acoustic noise MLCC candidate for a PMIC/DC-DC area. Search the catalog and tell me whether Low Acoustic Noise or MFC is the better family anchor for this use case.`

기대 동작:

- 패밀리 설명을 먼저 비교
- 패밀리 결정이 조회된 청크에 근거한 후에만 파트 예시로 이동

---

## 후보 비교

### 예시 5

`4.8uF exact nominal이 카탈로그 표준이 아니면 4.7uF와 5.1uF 후보를 둘 다 비교해줘. 어느 쪽이 catalog-based preselection으로 더 안전한지 이유를 설명하고, exact guarantee는 하지 마.`

기대 동작:

- E-series 명목 로직 사용
- `475` vs `515` 비교
- 최종 표현은 사전선정 수준으로 유지

---

## 품번 스켈레톤 검토

### 예시 6

`CL03A515MR3?N?# 같은 skeleton이 현재 스펙에 맞는지 검토해줘. 각 code가 무엇을 의미하는지 풀어서 설명하고, 확정 불가능한 tail code는 TBD로 유지해줘.`

기대 동작:

- 증명된 필드를 디코딩
- 미해결 8~11번째 코드를 임의로 만들지 않음
- 어떤 청크 유형이 해석을 뒷받침하는지 명시
- 응답 형식은 `response-formats.md`의 형식 A 또는 형식 B 사용

---

## 활성 라인업 대화

### 예시 7

`지금 조건으로 딱 하나로 못 정하면 괜찮아. 일단 부분 코드만 만들어서 현재 흐르는 품목이 있는지 보여줘. 예를 들면 CL32_106_O____ 같은 식으로 검색해서 리스트를 먼저 보고 싶어.`

기대 동작:

- 카탈로그 근거가 가장 강한 부분 패턴을 먼저 도출
- `chip_prod_id`로 활성 라인업 DB 조회 실행
- 단일 선택을 강제하기 전에 반환된 목록을 표시
- 포커스된 후속 질문 1개

### 예시 8

`CL32_106_O____ 패턴으로 현행품을 찾아서 리스트를 보여주고, 그 다음 어떤 조건이 더 필요할지 질문해줘.`

기대 동작:

- 사용자 문자열을 DB용 패턴 요청으로 취급
- 현행품 조회 도구가 있으면 사용
- 추측된 최종 P/N이 아니라 반환된 히트 기반으로 대화를 이어감

---

## 가드레일 검증 요청

### 예시 9

`이 후보가 1V DC 바이어스에서 반드시 3.45uF 이상인지 보장해줘.`

기대 동작:

- 정확한 조회 근거가 없는 한 확정 보증을 거절
- 카탈로그 근거 기반의 주의 문구로 응답
- 해당 요청을 `데이터시트 또는 실측 검증 필요 항목`으로 이동
