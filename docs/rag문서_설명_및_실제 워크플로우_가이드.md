# Samsung MLCC Catalog RAG Skill

이 스킬은 **Samsung Electro-Mechanics MLCC Catalog (December 2025 / Part I / Commercial-Industrial)** 기반 vector DB를 검색해서, 사용자의 자연어 제약조건을 **MLCC 기종 후보 / part-number skeleton / 검증 포인트**로 바꾸는 용도다.

이 스킬의 핵심 목표는 다음 3가지다.

1. 사용자의 자연어 제약을 **카탈로그 코드 체계**로 변환한다.
2. vector DB에서 **필요한 표/규칙/예시 부품**을 단계적으로 검색한다.
3. 카탈로그로 확정 가능한 것과 **데이터시트/실측 검증이 필요한 것**을 명확히 분리한다.

---

## 1. 전제 자료

이 스킬은 아래 2개 파일을 함께 쓴다고 가정한다.

- `mlcc_catalog_rag_chunks.jsonl`
- `mlcc_catalog_rag_master_ko.md`

권장 collection 이름 예시:

- `semco_mlcc_part1_2025`

권장 주요 chunk 그룹:

- `MLCC-002` : size / dielectric / capacitance code
- `MLCC-003` : tolerance / voltage / thickness code
- `MLCC-004` : design / product code / control / packaging
- `MLCC-005` : reliability level 비교
- `MLCC-006 ~ MLCC-012` : 제품군 설명
- `MLCC-013 ~ MLCC-014` : new-product example parts
- `MLCC-020 ~ MLCC-021` : capacitance / DC bias / AC voltage / impedance / aging 가이드
- `MLCC-031` : storage / transport / flow footprint / operating conditions
- `MLCC-032` : disclaimer / limitation

---

## 2. 반드시 지켜야 하는 truth policy

### 2.1 카탈로그로 **확정 가능한 것**

- dielectric / temperature characteristic 코드 해석
- rated voltage code
- capacitance tolerance code
- size code, thickness code
- reliability level 의미
- 제품군 특징과 적용처
- 카탈로그에 표로 적힌 example part number

### 2.2 카탈로그만으로 **확정하면 안 되는 것**

아래는 카탈로그 sample graph 또는 일반 가이드만으로는 exact guarantee를 하면 안 된다.

- 특정 part의 **1V DC bias 실제 유효용량**
- 특정 part의 **고주파 조건 유효용량**
- 특정 part의 **ESR/ESL exact 수치**
- 특정 part의 **정확한 orderable full part number의 tail code(8~11th code)**
- 카탈로그 표에 없는 **정확한 재고형 기종 존재 여부**

이런 항목은 반드시 아래처럼 표현한다.

- `catalog-based preselection`
- `candidate skeleton`
- `needs datasheet validation`
- `needs measured DC-bias/frequency data`

### 2.3 sample graph 사용 규칙

`MLCC-020`, `MLCC-021`의 그래프는 **sample**이다.

따라서 그래프만 보고

- `이 part는 1V에서 반드시 3.45uF 이상이다`
- `이 기종은 주파수 XX에서 exact effective capacitance가 YY다`

처럼 단정하면 안 된다.

가능한 표현 예시:

- `카탈로그는 Class II MLCC의 DC/AC bias에 따라 용량이 감소할 수 있음을 보여준다.`
- `정확한 1V DC bias 유효용량 보장은 개별 데이터시트/측정 데이터가 필요하다.`

---

## 3. 입력 파싱 규칙

사용자 요청에서 아래 항목을 분리한다.

### 3.1 hard constraints

hard constraint는 하나라도 어기면 후보에서 제외한다.

- temperature characteristic / dielectric
- rated voltage
- L max
- W max
- T max
- tolerance
- reliability family가 명시된 경우
- 특수 제품군 요구(MFC/LSC/Low ESL/Low Acoustic/High Bending)가 명시된 경우

### 3.2 soft constraints

soft constraint는 우선순위나 ranking에 반영한다.

- application hint (server, mobile, power, PMIC, DC-DC 등)
- preferred nominal capacitance
- preferred family if implied but not explicit
- packaging preference
- example-anchor proximity (catalog example와의 유사성)

### 3.3 validation-only constraints

카탈로그로는 직접 확정하지 못하고, **후보 선정 후 검증 포인트**로만 남겨야 하는 항목이다.

- high-frequency effective capacitance
- low-field / DC-bias effective capacitance
- ripple / self-heating exact behavior
- surge / ESD robustness exact margin

---

## 4. 단위 정규화 규칙

### 4.1 길이

- `690um -> 0.690 mm`
- `390um -> 0.390 mm`
- `550um -> 0.550 mm`

### 4.2 정전용량

- `uF / μF / ㎌ -> uF`
- `nF / ㎋? 오표기 가능성 -> nF 여부 문맥 확인`
- 내부 계산은 `pF` 또는 `uF`로 일관성 있게 변환

### 4.3 전압

- `4V`, `4.0V`, `4Vdc` -> `4.0Vdc`

### 4.4 편차

- `M편차 -> tolerance code M -> ±20%`
- `K편차 -> ±10%`
- `J편차 -> ±5%`

### 4.5 온도특성 문자

문자 하나만 들어오면 dielectric code로 먼저 해석한다.

예:

- `A 온도특성 -> code A -> X5R`
- `B 온도특성 -> X7R`
- `X 온도특성 -> X6S`
- `C 온도특성 -> C0G`

---

## 5. catalog code 해석 규칙

### 5.1 canonical part-number skeleton

기본 형식:

`CL [size] [dielectric] [capacitance] [tolerance] [voltage] [thickness] [design] [product/size control] [control] [packaging]`

예:

`CL 10 A 106 M Q 8 N N N C`

### 5.2 주요 코드 맵

#### dielectric

- `A = X5R`
- `X = X6S`
- `W = X6T`
- `B = X7R`
- `K = X7R(S)`
- `Y = X7S`
- `Z = X7T`
- `F = Y5V`
- `M = X8M`
- `E = X8L`
- `J = JIS-B`
- `C = C0G`
- `G = X8G`

#### rated voltage

- `S = 2.5Vdc`
- `R = 4.0Vdc`
- `Q = 6.3Vdc`
- `P = 10Vdc`
- `O = 16Vdc`
- `A = 25Vdc`
- `L = 35Vdc`
- `B = 50Vdc`
- `C = 100Vdc`
- `D = 200Vdc`
- `E = 250Vdc`
- `F = 350Vdc`
- `G = 500Vdc`
- `H = 630Vdc`
- `I = 1kVdc`
- `J = 2kVdc`
- `K = 3kVdc`

#### tolerance

- `F = ±1%` (10pF 이상)
- `G = ±2%`
- `J = ±5%`
- `K = ±10%`
- `M = ±20%`
- `Z = -20,+80%`

#### 대표 size code

- `02 = 01005 / 0402`
- `03 = 0201 / 0603`
- `05 = 0402 / 1005`
- `10 = 0603 / 1608`
- `21 = 0805 / 2012`
- `31 = 1206 / 3216`
- `32 = 1210 / 3225`
- `42 = 1808 / 4520`
- `43 = 1812 / 4532`
- `55 = 2220 / 5750`
- `L5 = 0204 / 0510`
- `01 = 0306 / 0816`
- `19 = 0503 / 1209`

### 5.3 capacitance code 변환

기본 규칙은 `유효숫자 2자리 + zero 개수`이다.

예:

- `4.7uF = 4,700,000pF = 47 × 10^5 -> 475`
- `5.1uF = 5,100,000pF = 51 × 10^5 -> 515`
- `1.0uF = 1,000,000pF = 10 × 10^5 -> 105`

주의:

- exact nominal이 E-series 밖이면, **자동으로 바꾸지 말고** 먼저 `nearest standard substitution`으로 표기한다.
- 사용자가 exact nominal만 허용하는지 불명확하면, 아래처럼 출력한다.

예:

- `catalog standard nominal around 4.8uF: 4.7uF (475), 5.1uF (515)`

---

## 6. size / thickness 후보 도출 규칙

### 6.1 1차 size filtering

사용자 L/W/T max가 주어지면 먼저 **nominal size code**로 1차 필터링한다.

예:

- `L <= 0.690 mm, W <= 0.390 mm`이면
  - `03 (0201/0603 = 0.60 x 0.30)`는 통과
  - `05 (0402/1005 = 1.00 x 0.50)`는 탈락

### 6.2 thickness filtering

두께는 `MLCC-003`의 thickness code table로 필터링한다.

예:

- `0201/0603`의 thickness code는 `3 = 0.30 ±0.03`
- `T max = 0.550 mm`이면 thickness code `3`는 통과

### 6.3 family-specific dimensions

특수 제품군은 반드시 family-specific dimension table을 우선한다.

- `LSC -> MLCC-009`
- `High Bending Strength -> MLCC-010`
- `Low Acoustic Noise -> MLCC-011`
- `Low ESL -> MLCC-012`
- `MFC -> MLCC-008`

Normal family는 nominal size + thickness code 기반 1차 필터링 후, exact envelope은 datasheet로 재검증한다.

---

## 7. 제품군 선택 규칙

### 7.1 family selection

아래 키워드가 있으면 해당 family를 우선 검색한다.

- `server / network / industrial power / humidity reliability` -> `High Level I` 또는 `High Level II`
- `outdoor / 85C 85%RH 1000h` -> `High Level II`
- `bending / board flex / mechanical stress` -> `High Bending Strength`
- `audible noise / piezo / PAM / PMIC` -> `Low Acoustic Noise`
- `low inductance / high-speed IC / save space by fewer chips` -> `Low ESL`
- `thin module / between solder balls / package` -> `LSC`
- `crack resistance + stacked structure + noise reduction` -> `MFC`
- 아무 특수 조건이 없으면 -> `Normal Standard`

### 7.2 reliability code mapping

- `control code N = Standard`
- `control code W = Industrial (High Level I)`
- `product/size control code 4 = Industrial (High Level II)`

주의:

- exact part-number의 9th/10th code는 제품군/실제 lineup에 따라 달라질 수 있으므로, **직접 evidence가 없으면 placeholder로 남긴다.**

---

## 8. retrieval 절차

이 스킬은 **한 번 검색하고 끝내면 안 된다.**

반드시 아래 순서로 검색한다.

### Step 1. code table retrieval

먼저 `section = part_numbering`만 조회한다.

목표:

- dielectric code
- rated voltage code
- tolerance code
- thickness code
- size code
- product/control code 해석

권장 질의 예시:

- `A X5R dielectric code`
- `R 4.0Vdc rated voltage code`
- `M tolerance code ±20%`
- `0201 0603 thickness code 0.30`
- `size code 0201 0603`

### Step 2. family retrieval

그 다음 `section = product_family`와 `section = reliability_level`을 조회한다.

목표:

- Standard vs High Level I / II 선택
- 특수 family 필요 여부 확인
- application hint 반영

권장 질의 예시:

- `standard MLCC wide lineup`
- `high level I humidity reliability industrial`
- `high level II outdoor industrial 85 85 1000h`
- `low ESL high speed IC`
- `low acoustic noise piezo`

### Step 3. example-part retrieval

그 다음 `section = new_product`를 조회해 **실제 catalog example anchor**를 찾는다.

목표:

- 비슷한 size / capacitance / voltage / dielectric / family의 orderable example 확인
- exact match가 없으면 nearest anchor를 찾고 gap을 설명

권장 질의 예시:

- `0201/0603 4.7uF X5R 4.0V ±20`
- `0201/0603 4.7uF class II`
- `0603/1608 47uF X5R 6.3V`
- `1206/3216 220uF X5R 6.3V`

### Step 4. bias / frequency validation retrieval

사용자가 effective capacitance, high-frequency, low-field, DC bias, AC bias를 요구하면 `section = caution_characteristics`를 조회한다.

목표:

- catalog가 허용하는 validation statement의 범위 확인
- 그래프가 sample임을 인지하고, exact guarantee 금지

권장 질의 예시:

- `DC bias characteristics X5R sample`
- `AC voltage characteristics class II`
- `effective capacitance high frequency low field`
- `impedance characteristic SRF ESR ESL`

### Step 5. final synthesis

최종적으로 아래 4가지를 분리해서 쓴다.

1. `exact catalog matches`
2. `closest catalog anchors`
3. `candidate part-number skeletons`
4. `needs datasheet / measured data`

---

## 9. candidate ranking 규칙

후보는 아래 우선순위로 정렬한다.

1. hard constraints 전부 만족
2. exact catalog example part 존재
3. size margin이 작은 쪽보다 **constraint 안에서 여유 있는 쪽** 우선
4. nominal capacitance가 target과 가장 가까운 쪽
5. application / family 일치
6. bias/frequency validation risk가 낮은 쪽

탈락 사유는 반드시 명시한다.

예:

- `rejected: voltage mismatch`
- `rejected: L dimension exceeds max`
- `rejected: family mismatch`
- `rejected: no catalog evidence for exact X5R 4V option`

---

## 10. 8th~11th code 처리 규칙

8th~11th code는 자주 문제가 된다.

- 8th: design code
- 9th: product code or size control code
- 10th: control code
- 11th: packaging code

이 코드는 **electrical core constraint만으로 자동 확정하면 안 된다.**

아래 조건일 때만 full code를 확정한다.

- catalog example part가 직접 존재
- 또는 별도 datasheet/lineup evidence가 있음

그 외에는 skeleton으로 쓴다.

예:

- `CL03A475MR3?N?#`
- `CL03A515MR3?N?#`

혹은

- `CL03A475MR3[design TBD][product code TBD][control TBD][packaging TBD]`

---

## 11. 출력 템플릿

최종 응답은 아래 형식을 권장한다.

### 11.1 constraints summary

- dielectric / TCC
- rated voltage
- max dimensions
- nominal capacitance target
- tolerance
- effective capacitance requirement
- family/reliability hint

### 11.2 derived code mapping

- dielectric code
- voltage code
- tolerance code
- candidate size code(s)
- candidate thickness code(s)
- candidate capacitance code(s)

### 11.3 exact matches

- exact catalog example part가 있으면 먼저 제시
- 없으면 `none in retrieved catalog`라고 명시

### 11.4 closest anchors

- retrieved new-product examples
- 어떤 점이 맞고 어떤 점이 다른지 설명

### 11.5 recommended candidate skeletons

- skeleton 1
- skeleton 2
- 선택 이유

### 11.6 unresolved items

- datasheet required
- measured DC bias/frequency data required
- exact tail code required

---

## 12. 예시 워크플로우

사용자 입력 예시:

> A 온도특성, 정격전압 4V, L size 최대 690um, W size 최대 390um, T size 최대 550um, 기준용량 4.8uF, M편차, 고주파 저전계에서 1V DC 전계를 인가하였을 때 최소 3.45uF 를 만족하는 기종을 설계해줘.

### 12.1 정규화

- `A 온도특성 -> dielectric code A -> X5R`
- `정격전압 4V -> voltage code R`
- `M편차 -> tolerance code M -> ±20%`
- `L<=0.690, W<=0.390, T<=0.550 mm`
- `기준용량 4.8uF -> standard nominal not exact; nearest standard candidates 4.7uF(475), 5.1uF(515)`
- `1V DC / high-frequency / low-field minimum 3.45uF -> validation-only constraint`

### 12.2 1차 size 후보

- `03 = 0201/0603 = nominal 0.60 x 0.30` -> 통과
- `02 = 01005/0402 = nominal 0.40 x 0.20` -> 통과 가능하지만 capacitance feasibility는 약함
- `05 = 0402/1005 = nominal 1.00 x 0.50` -> L/W 초과로 탈락

### 12.3 thickness 후보

- `0201/0603 -> thickness code 3 = 0.30 ±0.03` -> 통과
- `01005/0402 -> thickness code 2 = 0.20 ±0.02` -> 통과

### 12.4 catalog anchor 검색 예시

1. `part_numbering`
   - `A X5R dielectric code`
   - `R 4.0V rated voltage code`
   - `M tolerance code`
   - `0201 0603 thickness 0.30`

2. `new_product`
   - `0201/0603 4.7uF class II`
   - `0201/0603 4.7uF X5R 4.0V`
   - `0201/0603 4.7uF X6S 2.5V`

3. `caution_characteristics`
   - `DC bias characteristics X5R 1V`
   - `AC voltage characteristics class II`

### 12.5 catalog-based 해석 예시

retrieved anchor 예시:

- `CL03X475MS3CNW#` : `0201/0603`, `4.7uF`, `X6S`, `2.5V`, `±20%`

이 anchor는 다음을 보여준다.

- `0201/0603`에서 `4.7uF`급 class II가 가능하다는 **anchor evidence**
- 그러나 `X5R`도 아니고 `4.0V`도 아니므로 **exact match는 아님**

따라서 catalog-only 결론 예시:

- `exact catalog orderable match for X5R + 4.0V + 0201/0603 + ~4.8uF was not found in retrieved catalog examples`
- `candidate electrical skeleton`으로는 아래를 제시할 수 있다.
  - `CL03A475MR3?N?#`
  - `CL03A515MR3?N?#`

단,

- `4.7uF(475)`는 nominal이 목표 4.8uF보다 작다.
- `5.1uF(515)`는 standard nominal 관점에서 더 안전한 상향 대체 후보다.
- 어느 쪽이 `1V DC에서 최소 3.45uF`를 만족하는지는 **개별 데이터시트/실측 DC-bias data 없이는 확정 불가**다.

### 12.6 권장 최종 응답 스타일 예시

- `catalog exact match: none`
- `best size candidate: 03 (0201/0603)`
- `best thickness candidate: 3`
- `dielectric code: A (X5R)`
- `voltage code: R (4.0Vdc)`
- `tolerance code: M (±20%)`
- `nominal candidate 1: 475 (4.7uF)`
- `nominal candidate 2: 515 (5.1uF)`
- `recommended preselection: CL03A515MR3?N?#`
- `reason: size/voltage/tolerance target를 맞추면서 4.8uF target 대비 standard higher nominal 쪽이 effective capacitance margin에 유리`
- `must validate: 1V DC bias high-frequency effective capacitance >= 3.45uF, exact tail codes, orderable lineup existence`

---

## 13. 실패 시 대응 규칙

exact match가 없으면 절대 임의의 full part number를 완성하지 말고 아래 중 하나로 응답한다.

- `No exact catalog match found; providing candidate skeletons only.`
- `Catalog supports a preselection, not a final orderable P/N.`
- `Tail codes and bias-effective capacitance must be validated in datasheet/product search.`

---

## 14. 한 줄 운영 규칙

**이 스킬은 “카탈로그 기반 후보 설계”까지는 공격적으로 수행하되, “데이터시트 없이 exact full P/N과 bias-effective capacitance guarantee”는 절대 단정하지 않는다.**
