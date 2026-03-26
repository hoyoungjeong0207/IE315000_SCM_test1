# SCM Competition Platform — 확장 계획

## 현재 버전 (v1) 요약

| 항목 | 내용 |
|------|------|
| 기간 | Single-period |
| 수요 | 확정적 (deterministic) |
| 조달 | 공급자→시설→고객 단일 경로 |
| 변수 | y, x_sf, x_fc (약 20개) |
| 목적 | 고정비 + 운송비 최소화 |

---

## 확장 로드맵

```
v1 (현재)         v2                  v3
Single-period  →  Multi-period     →  Multi-period
Deterministic     Deterministic       + Spot market
No inventory      + Inventory         + Lease
                  + Price increase    + Flexible lease
```

> v2와 v3는 **순차적으로** 도입. Stochastic demand는 별도 보너스 트랙(v3+)으로 분리.

---

## v2 — Multi-Period + Inventory + Time-varying Cost

### 변경 동기

- Inventory가 single-period에서는 의미 없었음 → multi-period에서 재도입
- 시간에 따른 비용 변화(price increase)로 조달 시점 결정이 중요해짐
- 학생들이 "언제 얼마나 재고를 쌓아둘 것인가"를 전략적으로 판단해야 함

### 문제 구조

**기간:** T = 3 (period 1, 2, 3)

**새로운 파라미터**

| 파라미터 | 설명 |
|----------|------|
| `demand[t][k]` | 기간 t의 고객 k 수요 (기간마다 다름) |
| `cost_sf[t][i][j]` | 기간 t의 공급자 i → 시설 j 단위 운송비 |
| `cost_fc[t][j][k]` | 기간 t의 시설 j → 고객 k 단위 운송비 |
| `holding_cost[j]` | 시설 j의 단위 재고 보유비용 (기간당) |
| `inventory_capacity[j]` | 시설 j의 최대 재고 용량 |
| `price_increase_rate` | 기간별 운송비 상승률 (예: 5%/period) |

**새로운 결정변수**

| 변수 | 설명 |
|------|------|
| `y_Fj` | 시설 j 개설 여부 (기간 무관, 한 번 결정) |
| `x_Si_Fj_t{T}` | 기간 T에 공급자 i → 시설 j 흐름 |
| `x_Fj_Ck_t{T}` | 기간 T에 시설 j → 고객 k 흐름 |
| `I_Fj_t{T}` | 기간 T 말 시설 j의 재고 |

**목적함수 (최소화)**

```
min  Σ_j  f[j] · y[j]
   + Σ_t Σ_{i,j}  cost_sf[t][i][j] · x_sf[t][i][j]
   + Σ_t Σ_{j,k}  cost_fc[t][j][k] · x_fc[t][j][k]
   + Σ_t Σ_j      holding_cost[j]  · I[t][j]
```

**제약조건**

| 번호 | 제약 |
|------|------|
| C1 | 수요 충족: Σ_j x_fc[t][j][k] = demand[t][k] ∀t, k |
| C2 | 재고 균형: I[t-1][j] + Σ_i x_sf[t][i][j] = Σ_k x_fc[t][j][k] + I[t][j] ∀t, j |
| C3 | 시설 용량: Σ_k x_fc[t][j][k] ≤ cap[j] · y[j] ∀t, j |
| C4 | 공급 용량: Σ_j x_sf[t][i][j] ≤ cap_s[i] ∀t, i |
| C5 | 재고 용량: I[t][j] ≤ inv_cap[j] · y[j] ∀t, j |
| C6 | 초기 재고: I[0][j] = 0 ∀j |

**CSV 변수 수 (예상)**

```
y: 3개
x_sf: 2 × 3 × 3 = 18개
x_fc: 3 × 4 × 3 = 36개
I:    3 × 3     =  9개
──────────────────────
합계: 66개
```

**난이도 평가:** ★★★☆☆ — 적절한 도전. 재고 타이밍 전략이 핵심 변수.

---

## v3 — Spot Market + Long-term Lease + Flexible Lease

### 변경 동기

- "장기계약 vs 현물 조달" trade-off는 SCM의 핵심 의사결정
- Spot market: 급한 수요는 프리미엄 비용을 내고 즉시 조달
- Long-term lease: 미리 용량을 계약하면 단가가 저렴하지만 유연성 없음
- Flexible lease: 중간 단가, 일정 범위 내에서 용량 조정 가능

### 추가 구조

#### Spot Market (현물 시장)

- 공급자→시설 경로 없이 **시설→고객 직접 조달** 가능
- 단위 비용 = 정규 운송비 × `spot_premium` (예: 1.8배)
- 변수: `s_Fj_Ck_t{T}` (spot 구매량, ≥ 0)

```
spot_cost[t][j][k] = cost_fc[t][j][k] × spot_premium
```

수요 충족 제약 변경:
```
Σ_j x_fc[t][j][k] + Σ_j s_fc[t][j][k] = demand[t][k]
```

#### Long-term Lease (장기계약)

- 시작 전 용량을 기간 전체에 걸쳐 계약
- 변수: `L_Si_Fj` (계약 용량, ≥ 0, 연속형)
- 비용: `lease_cost_per_unit` (총 계약 용량에 비례, 선불)
- 제약: `x_sf[t][i][j] ≤ L[i][j]` ∀t (계약 용량 초과 불가)
- 계약 없이 조달하려면 spot premium 지불

#### Flexible Lease (유연 계약)

- 기간마다 용량을 조정할 수 있는 계약
- 변수: `FL_Si_Fj_t{T}` (기간 t의 유연 계약 용량)
- 비용: `flex_lease_cost` (장기계약보다 비싸고, spot보다 저렴)
- 제약: `|FL[t][i][j] - FL[t-1][i][j]| ≤ flex_adjust_limit` (조정 한도)

**비용 구조 요약**

```
조달 방식         단가       유연성      불확실성 대응
──────────────────────────────────────────────────
Long-term lease   낮음       없음        어려움
Flexible lease    중간       부분        가능
Spot market       높음(×1.8) 완전        쉬움
```

**CSV 변수 수 (예상, v2 기반)**

```
기존 v2 변수:             66개
spot s_Fj_Ck_t:   3×4×3 = 36개
lease L_Si_Fj:    2×3   =  6개
flex FL_Si_Fj_t:  2×3×3 = 18개
──────────────────────────────
합계:                    126개
```

**난이도 평가:** ★★★★☆ — 전략적 판단 요구. 솔버 없이도 휴리스틱으로 접근 가능.

---

## 보너스 트랙 — Stochastic Demand (v3+)

> **별도 심화 문제**로 분리. 일반 경쟁과 동시에 진행하지 말 것.

### 구조

- 수요 시나리오 S = {Low, Medium, High}, 각 확률 p[s]
- 1단계(here-and-now): y, L 결정 (시나리오 관측 전)
- 2단계(wait-and-see): x_sf, x_fc, I, spot 결정 (시나리오별)

**목적함수**

```
min  고정비 + 계약비
   + Σ_s p[s] · (운송비 + 재고비 + spot비)[s]
```

**CSV 변수 수:** 1단계 변수 + 2단계 변수 × 3 시나리오 → 약 300개+

**난이도 평가:** ★★★★★ — 대학원 수준. 반드시 솔버(PuLP 등) 사용 필요.

---

## 플랫폼 수정 계획

### v2 전환 시 수정 파일

| 파일 | 변경 내용 |
|------|----------|
| `config.py` | T=3 기간, 기간별 demand/cost 추가, holding_cost/inv_cap 재도입 |
| `parser.py` | 변수명 패턴에 `_t{T}` 기간 suffix 추가 |
| `feasibility.py` | C2 재고 균형 추가, 모든 제약에 기간 루프 추가 |
| `scoring.py` | holding cost 항 재도입, 기간 루프 추가 |
| `app.py` | Problem 탭 수요 테이블을 기간별로 표시, 네트워크 그림에 재고 노드 추가 |
| `sample/` | example CSV 업데이트 |

### v3 전환 시 추가 파일

| 파일 | 변경 내용 |
|------|----------|
| `config.py` | spot_premium, lease_cost, flex_limit 파라미터 추가 |
| `parser.py` | `s_`, `L_`, `FL_` 변수 패턴 추가 |
| `feasibility.py` | 수요 충족 제약에 spot 항 추가, lease 용량 제약 추가 |
| `scoring.py` | lease 선불 비용, spot 비용 항 추가 |

---

## 구현 우선순위

```
[즉시] v1 안정화 및 테스트
  ↓
[다음] v2 구현
       - config.py 기간/비용 데이터 설계 (가장 중요)
       - parser.py 변수명 패턴 확장
       - feasibility.py 재고 균형 제약 추가
  ↓
[이후] v3 구현
       - spot market 먼저 (단순)
       - long-term lease 다음
       - flexible lease 마지막
  ↓
[심화] Stochastic 별도 보너스 문제
```

---

## 결정이 필요한 사항

| 항목 | 선택지 | 추천 |
|------|--------|------|
| 기간 수 (T) | 2, 3, 4 | **T = 3** |
| 시설 개설 결정 | 기간마다 / 최초 1회 | **최초 1회** (단순화) |
| Spot market 범위 | 모든 경로 / 일부만 | **시설→고객만** |
| Flexible lease 조정 한도 | 고정 % / 절대량 | **절대량** (투명성) |
| Stochastic 도입 | v3와 동시 / 별도 | **별도 보너스** |
