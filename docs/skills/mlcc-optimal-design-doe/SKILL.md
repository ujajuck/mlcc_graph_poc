---
name: mlcc-optimal-design-doe
description: Reference LOT 기반 MLCC 최적설계(DOE) 및 신뢰성 시뮬레이션 스킬. 사용자가 `lot_id 기준으로 최적설계 돌려줘`, `DOE 범위 잡아서 돌려줘`, `신뢰성 시뮬레이션 돌려줘`, `여러 설계값으로 신뢰성 비교해줘`, `후보 3번에서 cast_dsgn_thk만 바꿔서 다시 돌려봐` 같은 요청을 할 때 사용한다. 자율 반복 최적화나 타겟+신뢰성 동시 수렴은 `mlcc-convergence-search`를 사용한다.
---

# MLCC 최적설계(DOE) 및 신뢰성 시뮬레이션

Reference LOT을 기준으로 최적설계(DOE)와 신뢰성 시뮬레이션을 실행한다. 이 skill은 **입력 수집 → tool 호출 → 결과 비교 → 재시뮬레이션** 흐름을 처리한다.

## 사전 조건

이 스킬은 lot_id 검증이 완료된 상태를 전제로 한다.
- 세션 상태에 lot_id가 있고 검증 완료 상태이면 바로 진행한다.
- lot_id가 없거나 아직 검증되지 않았으면 **mlcc-lot-validation**을 먼저 실행한다.

## 핵심 개념

| 개념 | 설명 | 예시 |
|------|------|------|
| **chip_prod_id** | 제품 기종 코드 | `CL32A106KOY8NNE` (15~16자, CL로 시작) |
| **lot_id** | 제조 LOT 식별자 | `AKB45A2` (짧은 영숫자) |

## 세션 상태 읽기/쓰기

> 필드 정의와 타입/단위는 `../session-state.md`를 참고한다.

**읽는 필드** (이전 스킬에서 전달됨):
- `lot_id`, `chip_prod_id` ← mlcc-lot-validation 출력

**쓰는 필드** (이 스킬이 갱신):
- `targets` — 사용자로부터 수집 후 기록
- `params` — DOE 탐색 범위 또는 재실행 단일값 기록
- `top_candidates` — optimal_design 결과 기록
- `halt_voltage`, `halt_temperature` — 사용자 확인 후 기록, 세션 내 유지
- `final_design` — 사용자가 후보를 확정하면 기록 → mlcc-design-dispatch가 읽음

**상태 초기화 규칙**: 새 lot_id가 들어오면 targets, params, top_candidates를 초기화한다. halt 조건은 유지한다.

**다음 단계**: 사용자가 후보를 확정하면 final_design을 기록하고 mlcc-design-dispatch로 진행한다.

## 실행 원칙

- tool 호출이 실패하거나 결과가 0건이어도 즉시 포기하지 않는다. 파라미터 범위를 변경하거나, 다른 조건으로 재시도하거나, 사용자에게 대안을 제시한다.
- 사용자가 "다시 해봐", "다른 방법으로", "범위 바꿔서" 등 재시도를 요청하면 반드시 응한다. 이미 시도한 조건을 변경하여 최소 2~3회는 다른 접근을 시도한다.
- **tool이 에러를 반환하면 절대 성공한 것처럼 응답하지 마라.** 에러 원인을 파악하고 재실행하라.

## Tool 입출력 계약 요약

전체 계약은 `references/tool-contracts.md`에 있다. 아래는 혼동하기 쉬운 핵심 주의사항만 요약한다.

- `optimal_design`의 params는 **list**, `reliability_simulation`의 params는 **scalar**. 절대 혼동하지 마라.
- `halt_voltage/halt_temperature`: **기본값(5)을 쓰지 마라.** 사용자에게 반드시 한 번 확인받아라.
- `fully_satisfied_versions`가 **한 개라도** 있으면 시뮬레이션 진행 가능.

## 패턴 라우팅

| 요청 유형 | 패턴 |
|---|---|
| "최적설계 돌려줘" / "DOE 범위 잡아서" | **최적설계 패턴** |
| "신뢰성 시뮬레이션 돌려줘" | **신뢰성 패턴** |
| "후보 3번에서 cast_dsgn_thk만 바꿔서 다시" | 최적설계 패턴 (rerun) |
| "후보 3번으로 신뢰성 돌려봐" | 신뢰성 패턴 (기존 후보 활용) |

자율 반복, 수렴 탐색 요청 → `mlcc-convergence-search` 스킬 사용.

## 보충 Reference 문서

- `references/tool-contracts.md`: tool 입출력 상세 (optimal_design, reliability_simulation, search_rag)
- `references/pattern-optimal.md`: 최적설계 params 리스트 생성법, rerun 규칙
- `references/pattern-reliability.md`: halt 조건 확인 절차, 설계값 경로
- `references/prompt-examples.md`: 예시 파일 인덱스
  - `references/examples-lot-doe.md`: 최적설계 DOE, 재실행 예시 (Examples 1-7)
  - `references/examples-reliability.md`: 신뢰성 시뮬레이션 예시 (Examples 8-13)

### 최적설계 패턴

> 실행 전 `references/pattern-optimal.md`와 `references/tool-contracts.md`를 반드시 참고한다. 예시: `references/examples-lot-doe.md` Example 6~7.

targets 5개(scalar) 수집 → params 10개(**list**) 수집 → `optimal_design` 호출 → 공정검사표준 검증 → top 5 제시 → 필요 시 override 재실행. params 리스트 생성법(범위·포인트 수)과 rerun 규칙은 `pattern-optimal.md`에 있다.

### 신뢰성 패턴

> 실행 전 `references/pattern-reliability.md`와 `references/tool-contracts.md`를 반드시 참고한다. 예시: `references/examples-reliability.md` Example 8~10.

params는 **scalar** (`optimal_design`의 list와 다름). halt_voltage/halt_temperature는 **기본값(5) 사용 금지** — 반드시 사용자에게 먼저 확인한다. 설계값 확보 경로(직접 입력/후보 활용/ref lot 기준)와 반복 비교 호출 방법은 `pattern-reliability.md`에 있다.

## 대화 규칙

- targets는 5개이므로 빠진 값만 한 번에 묻는다.
- params는 약 10개이므로 너무 길면 두세 묶음으로 나눠 묻되, 이미 있는 값은 제외한다.
- 질문은 항상 "지금 실행을 위해 무엇이 빠졌는지" 기준으로만 한다.
- 결과를 보여줄 때는 각 후보의 번호, 핵심 설계값, 예측 결과, target과의 차이를 함께 요약한다.
- 세션 상태에 이미 기록된 값(lot_id, targets, params, top_candidates)은 다시 묻지 않는다. 사용자가 변경을 명시할 때만 해당 필드만 교체한다.

## 실패 처리

- `optimal_design` 실행 실패 시 payload를 추측 수정하지 말고, tool 오류 메시지 기준으로 부족/잘못된 필드만 바로잡아 재시도한다.
- 존재하지 않는 후보 번호 참조 시 현재 보이는 번호 범위를 다시 안내한다.
- 공정검사표준 RAG 검색 실패 시 `공정검사표준 미확인` 표시를 달고 결과를 제시한다. 표준 확인 실패가 시뮬레이션 자체를 차단하지는 않는다.
- 시뮬레이션 결과가 기대에 못 미칠 때는 파라미터 범위를 변경하거나 다른 lot으로 전환하여 재시도를 제안한다.
