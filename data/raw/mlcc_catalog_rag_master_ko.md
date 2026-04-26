# Samsung Electro-Mechanics MLCC Catalog - RAG Optimized Knowledge Pack

- Source PDF: `MLCC_2512 (1).pdf`
- Source scope: December 2025 / Part I / Commercial-Industrial
- Goal: MLCC 제품군 선택, part number 해석, 신뢰성 조건 확인, 실장/공정/보관 주의사항 검색, 포장/footprint 정보 retrieval
- Deliverables:
  - `mlcc_catalog_rag_master_ko.md`: 사람이 읽기 쉬운 요약/색인
  - `mlcc_catalog_rag_chunks.jsonl`: vector DB 투입용 chunk JSONL

## 1. 이 패키지를 어떻게 쓰면 좋은가

### 1.1 추천 ingest 방식
- 기본 ingest 단위는 `mlcc_catalog_rag_chunks.jsonl`의 각 line이다.
- 임베딩 대상은 JSONL의 `text` 필드 전체를 사용한다.
- 메타데이터 필터는 `section`, `pages`, `priority`, `title_ko`, `aliases`를 활용한다.
- exact spec/치수/시험 조건이 필요한 경우 `pages` 메타데이터를 함께 반환해서 사람 검증 루프를 두는 것이 좋다.
- `new_product` 섹션의 exact part number는 최종 채택 전 데이터시트 재확인을 권장한다.

### 1.2 추천 metadata schema
- `id`: chunk ID
- `text`: 임베딩/검색용 본문
- `metadata.source_pdf`
- `metadata.pages`
- `metadata.section`
- `metadata.title_ko`
- `metadata.title_en`
- `metadata.summary_ko`
- `metadata.aliases`
- `metadata.priority`
- `metadata.notes` (있는 경우)

## 2. Agent용 빠른 선택 가이드 (catalog description 기반 재구성)

### 2.1 제품군 선택 로직
- **범용 / consumer / general purpose / wide lineup**가 필요하면 -> `Normal Capacitors - Standard`
- **서버 / 네트워크 / 산업 전원 / 습도 신뢰성 강화**가 필요하면 -> `High Level I`
- **옥외 산업용 / 85C 85%RH 1000h / 더 강한 온도변화-습도 신뢰성**이 필요하면 -> `High Level II`
- **PCB 굽힘 크랙 억제 + 소음 저감 + stacked 구조 공간 절감**이 필요하면 -> `MFC`
- **얇은 모듈 / package / solder ball 사이 실장 / 고주파 노이즈 제거**가 필요하면 -> `LSC`
- **보드 굽힘 / 기계 스트레스 / soft termination**이 핵심이면 -> `High Bending Strength`
- **압전 소음 / audible noise / PAM / PMIC / DC-DC** 이슈가 있으면 -> `Low Acoustic Noise`
- **고속 IC 근처 디커플링 / low inductance / 작은 실장 면적 / fewer chips**가 핵심이면 -> `Low ESL`

### 2.2 검색어 정규화 힌트
- `MLCC = Multilayer Ceramic Capacitor = 적층 세라믹 커패시터`
- `C0G = NP0 계열 temperature compensation class`
- `X5R / X6S / X7R / X7S / X7T / Y5V / X8M / X8L`은 모두 Class II dielectric alias로 같이 확장
- `0603/1608`, `0402/1005`, `1206/3216`처럼 inch/mm dual size 표기를 항상 함께 확장
- `Low ESL` 쿼리는 `Reverse`, `3T`, `8T`, `LICC`, `SLIC`로 확장
- `Low Acoustic Noise` 쿼리는 `THMC`, `ANSC`, `ANSC Type-A`, `ANSC Type-B`로 확장
- `High bending` 쿼리는 `soft termination`, `metal epoxy termination`, `bending crack`로 확장
- `Industrial reliability` 쿼리는 `High Level I`, `High Level II`, `humidity test`, `temperature cycle`, `board flex`로 확장

### 2.3 꼭 붙여야 하는 가드레일
- 카탈로그의 **그래프는 예시(sample) 데이터**다. 설계 확정용 universal guarantee로 쓰면 안 된다.
- `new product` 테이블은 **정확한 part-number 채택 전에 데이터시트 재검증**이 필요하다.
- 항공/군수/의료/원자력/자동차 등 고신뢰 응용은 카탈로그의 limitation 문구에 따라 별도 협의가 필요하다.

## 3. Canonical reference - Part Numbering 핵심 요약

### 3.1 Part number skeleton
예시 형식: `CL 10 A 106 M Q 8 N N N C`

1. **Series code**: `CL = Multilayer Ceramic Capacitors`
2. **Size code**
3. **Dielectric code**
4. **Capacitance code**
5. **Capacitance tolerance code**
6. **Rated voltage code**
7. **Thickness code**
8. **Design code**
9. **Product code or size control code**
10. **Control code**
11. **Packaging code**

### 3.2 Size code map
- `R1 = 008004 / 0201`
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
- `L6 = 0304 / 0610`
- `01 = 0306 / 0816`
- `19 = 0503 / 1209`

### 3.3 Dielectric code map
**Class I (Temperature Compensation)**
- `C = C0G`, operating `-55 ~ +125 °C`, temp coefficient `0 ± 30 ppm/°C`
- `G = X8G`, operating `-55 ~ +150 °C`, temp coefficient `0 ± 30 ppm/°C`

**Class II (High Dielectric Constant)**
- `A = X5R`, `-55 ~ +85 °C`, `±15%`
- `X = X6S`, `-55 ~ +105 °C`, `±22%`
- `W = X6T`, `-55 ~ +105 °C`, `-33 ~ +22%`
- `B = X7R`, `-55 ~ +125 °C`, `±15%`
- `K = X7R(S)`, `-55 ~ +125 °C`, `±15%`  (DC Bias 0.5Vr TCC)
- `Y = X7S`, `-55 ~ +125 °C`, `±22%`
- `Z = X7T`, `-55 ~ +125 °C`, `-33 ~ +22%`
- `F = Y5V`, `-30 ~ +85 °C`, `-82 ~ +22%`
- `M = X8M`, `-55 ~ +150 °C`, `-50 ~ +50%`
- `E = X8L`, `-55 ~ +150 °C`, `-40 ~ +15%`
- `J = JIS-B`, `-25 ~ +85 °C`, `±10%`

### 3.4 Capacitance code rule
- 기본 규칙: **유효숫자 2자리 + zero 개수**
- 예시: `106 = 10 x 10^6 pF = 10,000,000 pF`
- `10 pF 미만`은 `R`이 소수점 역할
- 예시: `1R5 = 1.5 pF`
- E-series nominal capacitance 표는 source chunk `MLCC-003` 참고

### 3.5 Capacitance tolerance code
- `N = ±0.03 pF`
- `A = ±0.05 pF`
- `B = ±0.1 pF`
- `C = ±0.25 pF`
- `H = +0.25 pF`
- `L = -0.25 pF`
- `D = ±0.5 pF`
- `F = ±1 pF` (value < 10 pF), `±1%` (value >= 10 pF)
- `G = ±2%`
- `J = ±5%`
- `U = +5%`
- `V = -5%`
- `K = ±10%`
- `M = ±20%`
- `Z = -20, +80%`

### 3.6 Rated voltage code
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

### 3.7 Design code (핵심만)
- `N`: inner electrode `Ni`, termination `Cu`, plating `Ni/Sn`, feature `Normal`
- `G`: inner electrode `Cu`, termination `Cu`, plating `Ni/Sn`, feature `Normal`
- `S`: inner electrode `Ni`, termination `Metal Epoxy`, plating `Ni/Sn`, feature `Normal`
- `C`: inner electrode `Ni`, termination `Control code`, plating `Ni/Sn`, feature `Normal`
- `L`: inner electrode `Ni`, termination `Cu`, plating `Ni/Sn`, feature `Low profile`
- `Y`: inner electrode `Ni`, termination `Metal Epoxy`, plating `Ni/Sn`, feature `Low profile`
- `Z`, `Q`: `Metal Epoxy`, `Ni/Sn`, feature `Normal`
- `F`, `J`: `Metal Epoxy`, `Ni/Sn`, feature `Low profile`
- `M`: `Molded Frame Capacitor`
- `U`: `Acoustic Noise Suppressed Capacitor`

### 3.8 Product/size control code와 control code
- Product code or size control code:
  - `N = Normal`
  - `4 = Industrial (High Level II)`
  - `L = LICC (Low Inductance Ceramic Capacitor)`
  - `J = SLIC (Super Low Inductance Capacitor)`
  - `S/Q/R/U/Z/9` 등 일부 코드는 size tolerance control table을 따르므로 exact 값은 `MLCC-004` chunk 참고
- Control code:
  - `N = Standard`
  - `W = Industrial (High Level I)`

### 3.9 Packaging code (핵심만)
**Cardboard tape (paper)**
- `8/C/H = Normal, 7" reel`
- `J = 1mm pitch, 7" reel`
- `Z = Chip aligned for horizontal, 7" reel`
- `Y = Chip aligned for vertical, 7" reel`
- `O = Normal, 10" reel`
- `3/D/L = Normal, 13" reel`
- `2 = 1mm pitch, 13" reel`
- `7 = Chip aligned for vertical, 13" reel`

**Embossed tape (plastic)**
- `E/G = Normal, 7" reel`
- `R = Chip aligned for horizontal, 7" reel`
- `W = Chip aligned for vertical, 7" reel`
- `S = Normal, 10" reel`
- `F = Normal, 13" reel`

> Thickness code, detailed size-tolerance control table, exact packaging dimensions은 JSONL chunk에서 그대로 보존했다.

## 4. Reliability level 핵심 비교

- **Standard**
  - Application guide: 스마트폰, TV, PC, consumer power 등 / Medical Class I, II / For Consumer device
  - Humidity test: `40 °C, 95%RH, 1Vr, 500h`
  - High temp load: `max temp, 1.0~1.5Vr, 1000h`
  - Board flex: `1mm` (footnote에서 outgoing 2mm bending 언급)
  - Temperature cycling: `5 cycles`

- **High Level I**
  - Application guide: server, network, industrial power / Medical Class III (non-critical)
  - Humidity test: `65 °C, 90%RH, 1Vr, 500h`
  - Board flex: `1mm`
  - Temperature cycling: `5 cycles`

- **High Level II**
  - Application guide: server, network, industrial power / Medical Class III (non-critical)
  - Humidity test: `85 °C, 85%RH, 1Vr, 1000h`
  - Board flex: `2mm` (일부 품목은 3mm 또는 1mm bending guarantee)
  - Temperature cycling: `1000 cycles`

- **AEC-Q200**
  - Application guide: automotive / car infotainment
  - Humidity test: `85 °C, 85%RH, 1Vr and 1.3~1.5V, 1000h`
  - High temp load: `max temp, 2Vr, 1000h`
  - Board flex: `2mm`
  - Temperature cycling: `1000 cycles`

## 5. Source anomaly / validation notes

- `MLCC-013` commercial new product table에는 `CL10A106MA5FZN#`와 `220nF` 조합처럼 **part-number 규칙(page 6)과 표기 용량이 상충해 보이는 행**이 있다. exact 선정 시 datasheet 검증 필요.
- `MLCC-014` industrial new product table에는 `CL32X337MSVN4S#`가 **중복 기재**되어 있다.
- caution/notice의 각 그래프는 **example/sample**이므로 일반화 금지.

## 6. Chunk directory (vector DB ingest index)


### 문서 메타데이터
- **MLCC-000** | pp. 1-3 | 문서 메타데이터, 인터랙티브 가이드, 목차  
  - summary: 문서 제목, 발행 시점(December 2025), 파트 범위(Part I. Commercial/Industrial), interactive PDF 사용법, 전체 목차를 담는다. 설계 지식 자체보다는 문서 메타데이터와 목차용 chunk이다.  
  - aliases: document metadata, interactive user guide, table of contents, December 2025, Commercial Industrial / note: Low-priority metadata chunk; useful mainly for provenance and navigation.

### 개요
- **MLCC-001** | pp. 4-5 | 카탈로그 개요와 제품군 맵  
  - summary: 카탈로그가 다루는 MLCC 제품군을 상위 수준에서 정리한다. Normal Standard, High Level I, High Level II, MFC, LSC, High Bending Strength, Low Acoustic Noise, Low ESL로 분류되며 각 제품군의 대표 적용처와 핵심 가치(공간 절약, 굽힘 내성, 저소음, 저ESL)를 빠르게 파악할 수 있다.  
  - aliases: MLCC overview, product family, Normal Standard, High Level I, High Level II, MFC, LSC, High Bending Strength, Low Acoustic Noise, Low ESL

### Part Numbering
- **MLCC-002** | pp. 6 | Part Numbering 기본 구조: series, size, dielectric, capacitance code  
  - summary: 삼성전기 MLCC 부품번호의 1~4번째 필드 해석 규칙이다. Series code(CL), size code(inch/mm 매핑), dielectric code(Class I/Class II), capacitance code(유효숫자 2자리 + zero 개수, 10pF 미만은 R 사용)를 정의한다.  
  - aliases: part number decode, series code, size code, dielectric code, capacitance code, C0G, X5R, X6S, X7R, X7S, X7T, Y5V, X8M, X8L, JIS-B
- **MLCC-003** | pp. 7 | Part Numbering 세부: tolerance, rated voltage, thickness code  
  - summary: 부품번호의 5~7번째 필드 해석 규칙이다. Capacitance tolerance code, rated voltage code, thickness code를 정의하며, thickness code는 사이즈별로 허용 두께와 tolerance가 다르다.  
  - aliases: capacitance tolerance code, rated voltage code, thickness code, E series, E-3, E-6, E-12, E-24, 2.5V, 4V, 6.3V, 10V, 16V, 25V, 35V, 50V, 100V, 200V, 250V, 350V, 500V, 630V, 1kV, 2kV, 3kV
- **MLCC-004** | pp. 8 | Part Numbering 후반부: design code, product/size control, control, packaging  
  - summary: 부품번호의 8~11번째 필드 해석 규칙이다. 내부전극/termination/plating/feature를 표현하는 design code, normal/industrial/LICC/SLIC를 나타내는 product code or size control code, standard vs industrial control code, 탭핑 및 릴 규격을 나타내는 packaging code를 정리한다.  
  - aliases: design code, product code, size control code, control code, packaging code, low profile, metal epoxy, Molded Frame Capacitor, Acoustic Noise Suppressed Capacitor, LICC, SLIC, 7inch reel, 13inch reel

### 신뢰성 등급
- **MLCC-005** | pp. 9 | 신뢰성 등급 설명: Standard, High Level I, High Level II, AEC-Q200 비교  
  - summary: 각 신뢰성 등급별 대표 적용처와 시험 조건을 비교한다. 습도 시험, 고온 부하, 보드 플렉스, 온도 사이클 조건이 Standard → High Level I → High Level II → AEC-Q200 순으로 강화된다.  
  - aliases: reliability level, Standard, High Level I, High Level II, AEC-Q200, humidity test, board flex, temperature cycling, medical class, consumer device

### 제품군
- **MLCC-006** | pp. 10 | Normal Capacitors - Standard  
  - summary: 범용 MLCC 제품군이다. 다양한 사이즈와 넓은 정전용량 범위, 우수한 DC bias 특성, 고속 자동 실장성을 강조한다. 적용처는 컴퓨터, SSD, 디스플레이, 모바일, 태블릿, 네트워크, 서버, 게임콘솔, DC-DC 컨버터 등이다.  
  - aliases: general MLCC, standard MLCC, normal capacitor, wide capacitance range, DC bias, automatic chip placement
- **MLCC-007** | pp. 11 | Normal Capacitors - High Level I / High Level II  
  - summary: 산업용 신뢰성 강화 제품군이다. High Level I은 65°C/90%RH/1Vr/500h 수준의 개선된 습도 신뢰성과 굽힘 강도 검사를 강조하고, High Level II는 85°C/85%RH/1Vr/1000h 수준의 강화된 야외 산업용 신뢰성을 제공한다.  
  - aliases: industrial MLCC, High Level I, High Level II, improved reliability, reinforced reliability, server, network, base station, solar inverter, DC-DC converter
- **MLCC-008** | pp. 12 | Molded Frame Capacitors (MFC)  
  - summary: 몰드 프레임 구조를 사용해 PCB 굽힘에 의한 크랙을 줄이고, 가청 소음을 줄이며, 적층 구조 사용 시 동일 정전용량에서 실장 면적을 절감하는 제품군이다. 고굽힘 응력 전원/DC-DC 적용처에 적합하다.  
  - aliases: MFC, Molded Frame Capacitor, audible noise reduction, bending crack prevention, stacked structure, power, DC-DC converter
- **MLCC-009** | pp. 13 | Land Side Capacitors (LSC)  
  - summary: 얇은 디바이스/모듈용 MLCC이다. 솔더볼 사이에 실장하여 모듈 두께를 줄이거나 실장 면적을 확보할 수 있고, 고속 AP용 전류 공급과 고주파 노이즈 제거에 유리하다. 모바일, 웨어러블, IC 패키지, 모듈 제품에 적합하다.  
  - aliases: LSC, Land Side Capacitor, thin device, thin module, between solder balls, high frequency noise, mobile phone, wearable, IC package
- **MLCC-010** | pp. 14 | High Bending Strength Capacitors  
  - summary: soft termination(금속 에폭시 termination 포함)의 연성으로 열/기계적 스트레스를 완화해 PCB 굽힘에 의한 크랙을 줄이는 제품군이다. 모바일, 컴퓨터, SSD, 태블릿, 디스플레이, SMPS, DC-DC 컨버터 등에 적합하다.  
  - aliases: High Bending Strength, soft termination, metal epoxy termination, board bending, mechanical stress, bending crack
- **MLCC-011** | pp. 15 | Low Acoustic Noise Capacitors  
  - summary: 압전 현상으로 인한 MLCC 진동이 기판에 전달되어 발생하는 가청 소음(20Hz~20kHz)을 줄이는 제품군이다. THMC, ANSC Type-A, ANSC Type-B 구조가 소개되며, PAM, PMIC, DC-DC 컨버터에 적용된다.  
  - aliases: Low Acoustic Noise, THMC, ANSC, ANSC Type-A, ANSC Type-B, piezoelectric, audible noise, PAM, PMIC
- **MLCC-012** | pp. 16 | Low ESL Capacitors  
  - summary: 낮은 ESL(Equivalent Series Inductance)로 고속 IC 근처에서 적은 개수로도 빠르고 안정적인 에너지 전달이 가능하도록 설계된 제품군이다. Reverse, 3T, 8T 구조가 소개되며 모바일, 웨어러블, 컴퓨터, IC 패키지에 적합하다.  
  - aliases: Low ESL, ESL, Equivalent Series Inductance, Reverse, 3T, 8T, LICC, SLIC, high speed IC, saved space

### 신제품 소개
- **MLCC-013** | pp. 17 | 신제품 소개 - Commercial MLCC  
  - summary: 상용(Commercial) MLCC의 신규 예시 부품들을 application/type/part number/specification 기준으로 정리한다. Normal, Land Side Capacitor, Low Acoustic Noise ANSC-B 항목이 포함된다. 일부 행은 part number 규칙과 표기 용량이 상충해 보일 수 있으므로 데이터시트 재확인이 필요하다.  
  - aliases: new product, commercial MLCC, for consumer device, Land Side Capacitor, ANSC-B, part number examples / note: The source table appears to contain at least one apparent part-number/capacitance inconsistency; validate exact values against datasheet.
- **MLCC-014** | pp. 17 | 신제품 소개 - Industrial MLCC  
  - summary: 산업용(Industrial) MLCC 신규 예시 부품들을 AI Server > Power / Computing / Network System application별로 정리한다. High Level I, High Level II, High Level I/MFC 타입이 포함되며 일부 항목은 중복 기재가 있다.  
  - aliases: industrial MLCC, AI server, power system, computing system, network system, High Level I, High Level II, MFC / note: Source table includes a duplicated row for CL32X337MSVN4S#.

### 신뢰성 시험
- **MLCC-015** | pp. 18-19 | 신뢰성 시험 조건 1-9: appearance, IR, withstanding voltage, capacitance, Q/Tanδ, TCC, adhesion, bending, solderability  
  - summary: 기본 전기/기계 신뢰성 시험 항목 1~9를 정의한다. 외관, 절연저항, 내전압, 정전용량 측정 조건, Q/Tanδ, 온도특성(TCC), 단자 접착강도, 굽힘강도, 납땜성을 포함한다.  
  - aliases: reliability test 1, insulation resistance, withstanding voltage, Q factor, tan delta, temperature characteristics, adhesive strength, bending strength, solderability
- **MLCC-016** | pp. 20-23 | 신뢰성 시험 조건 10-14 및 비고: soldering heat, vibration, moisture, high temperature, temperature cycle  
  - summary: 납땜열 저항, 진동, 내습, 고온 부하/고온 저항, 온도 사이클 시험과 초기/최종 측정 노트를 정리한다. Class I/II별 허용 변화량과 측정 전 열처리 조건이 포함된다.  
  - aliases: resistance to soldering heat, vibration test, moisture resistance, high temperature resistance, temperature cycle, initial measurement, latter measurement

### 포장/릴/박스
- **MLCC-017** | pp. 24-25 | 패키징 사양 1: quantity, taping overview, cardboard tape  
  - summary: MLCC 탭핑 패키징의 기본 구성, 리드/빈 구간 길이, 사이즈별 reel 수량, cardboard(paper) tape의 4mm pitch 및 1mm/2mm pitch 치수를 정리한다.  
  - aliases: packaging quantity, taping, paper tape, cardboard tape, pitch, carrier tape, cover tape, reel quantity
- **MLCC-018** | pp. 26-27 | 패키징 사양 2: embossed tape, reel size, cover tape peel-off force  
  - summary: embossed(plastic) tape 치수, reel size(7, 10, 13 inch), cover tape peel-off force와 측정법(IEC 60286-3 기반)을 정리한다.  
  - aliases: embossed tape, plastic tape, reel size, 7 inch reel, 10 inch reel, 13 inch reel, peel-off force, IEC 60286-3
- **MLCC-019** | pp. 28-29 | 패키징 사양 3: box package와 chip weight  
  - summary: 라벨 항목, 7인치/13인치 inner/outer box 규격, chip weight(사이즈, 두께, 유전체에 따른 mg/pc 대표값)를 정리한다.  
  - aliases: box package, packaging label, chip weight, inner box, outer box, 7 inch box, 13 inch box

### 제품 특성/주의
- **MLCC-020** | pp. 30-31 | 제품 특성 데이터 1: capacitance, DF/Q, insulation resistance, aging  
  - summary: 정전용량 측정 조건, DF/Q 의미, ALC 사용 권장, Class II의 DC/AC 전압 의존성, 절연저항 측정 시점, aging 특성을 정리한다.  
  - aliases: product characteristic, capacitance measurement, DF, dissipation factor, Q factor, ALC, insulation resistance, aging
- **MLCC-021** | pp. 32-34 | 제품 특성 데이터 2: TCC, self-heating, DC/AC voltage characteristics, impedance  
  - summary: 온도 특성(TCC), bias TCC, self-heating 한계, DC bias와 AC voltage에 따른 Class II 용량 변화, SRF/ESL/ESR를 포함한 임피던스 특성을 설명한다.  
  - aliases: TCC, temperature characteristic, bias TCC, self-heating, ripple current, DC bias, AC voltage characteristic, impedance, ESL, ESR, SRF

### 전기/기계 주의
- **MLCC-022** | pp. 35 | 전기/기계 주의 1: derating과 applied voltage  
  - summary: derated MLCC의 온도-전압 derating 개념과 실제 인가전압 제한 규칙을 정리한다. DC, AC, DC+AC, DC+pulse 조건에서 rated voltage를 넘지 않도록 설계해야 한다.  
  - aliases: derating, derated MLCC, applied voltage, rated voltage, DC+AC, pulse voltage, surge voltage, static electricity
- **MLCC-023** | pp. 36 | 전기/기계 주의 2: EOS, vibration, shock, piezo-electric phenomenon  
  - summary: 전기적 과부하(EOS), surge/ESD, 진동, 낙하 충격, 압전 현상에 따른 리스크를 정리한다. 저용량 MLCC의 ESD 민감도, surge overshoot, 기계 충격에 따른 크랙 발생 가능성을 강조한다.  
  - aliases: EOS, electrical overstress, surge, ESD, vibration, shock, piezo-electric phenomenon, audible noise

### 실장
- **MLCC-024** | pp. 37-38 | 실장 주의 1: mounting position, cutout/screw vicinity, pre-mounting, pick-and-place  
  - summary: PCB 굽힘 응력 방향에 대한 실장 방향, 컷아웃/나사 주변 피해야 할 배치, 장착 전 점검 사항, pick-and-place head pressure/board support/nozzle maintenance 주의를 정리한다.  
  - aliases: mounting position, cutout, screw hole, pick and place, mounting head pressure, support pin, suction nozzle

### 납땜/세정/측정
- **MLCC-025** | pp. 39-40 | 실장 주의 2: reflow soldering profile, peak temperature, flux/solder amount  
  - summary: reflow soldering 방법 분류, 권장 온도 프로파일, reflow 횟수 제한, peak temperature 유지, 자연 냉각, solder paste 과다/과소에 따른 크랙/접속 불량 위험과 land pattern 고려사항을 정리한다.  
  - aliases: reflow soldering, reflow profile, peak temperature, cooling, solder paste, too much solder, not enough solder, land pattern
- **MLCC-026** | pp. 41-43 | 실장 주의 3: flow soldering, soldering iron, spot heater, re-work, cleaning, electrical probe  
  - summary: flow soldering 프로파일, 수동 납땜/spot heater 조건, re-work 시 solder fillet 확인, 세정 시 초음파/고압 리스크, 전기 측정 프로브 사용 시 PCB 지지 필요성을 정리한다.  
  - aliases: flow soldering, soldering iron, spot heater, re-work, cleaning, ultrasonic cleaning, test probe, support pin

### 조립/취급
- **MLCC-027** | pp. 44-45 | 조립/취급 주의: PCB cropping, assembly handling, leaded components, connector, screw fastening  
  - summary: PCB 분리 시 bending/twisting 금지, 보드 한 손 취급 금지, 뒷면 부품 실장 시 노즐 위치와 보드 지지, 리드 부품 삽입, 소켓/커넥터 체결, screw fastening 시 보드 굽힘 방지 규칙을 정리한다.  
  - aliases: PCB cropping, bending, twisting, assembly handling, leaded component, connector, socket, fastening screw

### 공정 재료
- **MLCC-028** | pp. 46 | 공정 재료 주의: adhesive selection과 flux  
  - summary: 접착제 요구 특성, 도포량/경화 조건, 절연저항 및 수축응력 영향, flux의 halogen 함량(0.1% max)과 산성 flux 위험을 정리한다.  
  - aliases: adhesive selection, adhesive curing, insulation resistance, contractile stress, flux, halogen content, acidic flux

### 설계
- **MLCC-029** | pp. 47 | 설계 주의: coating, circuit design, PCB design, system evaluation  
  - summary: 코팅 수지의 열팽창/수축에 따른 크랙 리스크, fuse 등 safety design 필요성, PCB 재질에 따른 thermal stress, 실제 시스템에서의 surge/capacitance/termination shape 평가 필요성을 정리한다.  
  - aliases: coating, silicone resin, circuit design, PCB design, system evaluation, surge resistance, safety circuit, fuse

### Footprint
- **MLCC-030** | pp. 48 | Reflow footprint land dimension  
  - summary: reflow 실장용 권장 land dimension 테이블이다. chip size와 chip tolerance에 따라 a, b, c, (a+2b) min/max, Wmin/Wmax를 제시한다.  
  - aliases: reflow footprint, land dimension, a b c, Wmin, Wmax, 0201, 0402, 0603, 1005, 1608, 2012, 3216, 3225, 4532, 5750

### Footprint/보관/운용
- **MLCC-031** | pp. 49-50 | Flow footprint, storage environment, operation, transport, waste, notice  
  - summary: flow solder용 footprint, 보관 온도/습도(0~40°C, RH 0~70%), shelf life 6개월, 부식성 환경 금지, 장비 동작 조건, 운송 충격 주의, 폐기 및 일반 notice를 정리한다.  
  - aliases: flow footprint, storage environment, shelf life, corrosive environment, operating temperature, transportation, waste treatment, notice

### 면책/제한/거점
- **MLCC-032** | pp. 51-53 | 면책/사용 제한과 글로벌 판매 거점  
  - summary: 사양 변경/검증 책임, 고신뢰 응용의 사전 협의 필요성, 고위험 응용 목록, 글로벌 sales office와 manufacturing site 정보를 정리한다.  
  - aliases: disclaimer, limitation of use, high reliability application, medical equipment, aerospace, automotive, sales office, manufacturing site, global network

## 7. JSONL text composition rule

각 JSONL line의 `text` 필드는 아래 순서로 구성되어 있다.

1. 제목 (한글/영문)
2. section 이름
3. 페이지 범위
4. 한국어 요약
5. notes (있는 경우)
6. aliases
7. source-normalized text

즉, **사람이 읽어도 맥락이 보이고, embedding 모델도 제목-요약-원문을 함께 보도록** 설계했다.

## 8. 권장 retrieval 전략

- 1차 retrieval: semantic search on `text`
- 2차 rerank: query intent와 `section`, `priority`, `aliases` 일치도 반영
- exact numeric query (예: `0805 thickness code F`, `moisture resistance 40C 95%RH 500h`, `0201 land dimension`)는 해당 section chunk를 우선 랭크
- final answer generation 단계에서는 `pages`를 함께 표시하고, exact selection은 datasheet 확인 루프를 두는 것을 권장
