# METHODOLOGY — Generic Index-Linked Lifetime-Income Case Study

This note documents the active modelling path for the independent product in
`../documentation_and_background_info/Produktdesign_Index_Linked_Lifetime_Income_Fallbeispiel.md`.
That product-design document is authoritative for contractual mechanics. The
repository CSVs are authoritative only for the assumptions and statuses
assigned to their rows. AGILE-era code that remains for compatibility is not
part of the active product unless this note explicitly says otherwise.

## 1. Scope and modelling perspectives

The model separates four perspectives that must not be mixed:

1. **Policyholder Account Value and benefits** — annual protected credit,
   fees deducted from Account Value, lifetime income, withdrawals and death
   benefits.
2. **Insurer non-unit cashflows** — collected fees, Guarantee Claims, expenses,
   stochastic overnight-backing income, option/hedge costs, optional retained
   hedge gain and MVA retention.
3. **Market-consistent valuation** — risk-neutral scenarios and pathwise
   money-market discounting.
4. **Simplified Real-World projection** — physical equity premium with the
   documented proxy assumptions, used for outcomes and profitability rather
   than market-consistent liability value.

The Account Value is indexed, not unit-linked. The Reference Fund determines
annual crediting; it is neither a customer securities account nor necessarily
the insurer's backing or hedge portfolio.

## 2. Contractual product baseline

| Feature | Active treatment |
| --- | --- |
| Premium | one single premium; `Account Value_0 = premium` |
| Growth phase | at least one full policy year; no lapse, full surrender, free, partial or excess withdrawal |
| Income election | once per Policy Anniversary; irreversible; automatic contractual backstop at the first anniversary after age 100 |
| Income | Fixed Lifetime Income only, monthly in arrears |
| Reference Fund | CSV-configured Global-Equity share (30% in the shipped base case) and the complementary nominal Australian-government five-year bond sleeve |
| Rebalancing | monthly back to the configured target allocation |
| Crediting | annual point-to-point Total Protection on the complete Reference Fund return |
| Maximum Return | fixed 6% per year; Guaranteed Minimum Cap 0.25% |
| Investment switch | none; the same Reference Fund remains in Growth and Income |
| Growth withdrawals | prohibited, including full surrender/lapse |
| Income withdrawals | Partial/Excess and Full Withdrawal subject to MVA and minimum residual rules |
| Death | positive post-fee Account Value, without MVA; spouse continuation where elected |
| Customer fees | Product Fee 0.30% and Lifetime Income Premium 1.15% per year, subject to the versioned cost input |
| Excluded options | Rising Income, Age Pension+, adviser fee, commencement bonus and customer allocation choice |

Product eligibility is applied before behavioural assumptions. A positive
legacy Growth-lapse or withdrawal assumption therefore cannot create an event
that the generic contract prohibits.

## 3. Reference Fund construction

### 3.1 Global-Equity sleeve

Global Equity is a total-return index already expressed in AUD or treated as
fully AUD hedged. Its simple monthly return is

```text
R_E,m = S_m / S_(m-1) - 1.
```

Distributions are already reflected in the index. No dividend is added again,
and no separate FX process or hedge cost is introduced.

### 3.2 Five-year Australian-government-bond sleeve

The Hull-White scenario state provides the pathwise zero-coupon price

```text
P(t, t + tau) = exp(-tau * z_cc(t, tau)),
```

where `z_cc` is the continuously compounded pathwise zero rate consistent with
the initial Australian curve. During month `m`, the bond bought at the previous
month end ages from five years to `5 - 1/12` years. Its total return is

```text
R_B,m = P(t_m, T_(m-1)) / P(t_(m-1), T_(m-1)) - 1,
T_(m-1) = t_(m-1) + 5.
```

After measurement the sleeve is rolled into a new five-year bond. This combines
carry, price change and roll-down. It is a zero-coupon proxy and contains no
credit spread, default, rating migration or inflation-linked-bond component.

### 3.3 Monthly fund return and annual credit

At each month end the complete simple Reference Fund return is formed first:

```text
R_F,m = 0.30 * R_E,m + 0.70 * R_B,m,
F_m   = F_(m-1) * (1 + R_F,m).
```

This equation implements monthly, not continuous, rebalancing. The annual
point-to-point return between two Policy Anniversaries is

```text
R_F,y = F_Ty / F_T(y-1) - 1.
```

Only then is Total Protection applied:

```text
c_y = min(max(R_F,y, 0), 0.06).
```

Applying floor or cap separately to equity and bonds and then weighting the
credits is prohibited. The same `F` drives both product phases.

## 4. Account Value and state transitions

The projection uses a monthly market and benefit grid. At an anniversary,

```text
AV_after_credit = AV_frame * (1 + c_y).
```

The active event order is:

1. evolve the market scenarios and Reference Fund over the month;
2. accrue Product Fee and Lifetime Income Premium for the actual calendar days
   in the interval;
3. at an anniversary, determine the complete annual fund return and apply the
   annual credit;
4. at an anniversary, post the fee subledger against the credited Account
   Value;
5. apply the expected death decrement for the interval just ended under its
   pre-Election coverage state; a terminating death uses the post-credit,
   post-fee Account Value;
6. for surviving contracts, elect Fixed Lifetime Income where eligible and
   start the next DVA/crediting period;
7. pay the monthly income to covered survivors;
8. in Income only, process Partial/Excess Withdrawal; and
9. in Income only, process Full Withdrawal, first posting accrued fees and then
   applying MVA to post-fee Account Value.

This Expected-Decrement boundary treats deaths allocated to the month ending
at an Anniversary as occurring immediately before the Election instant. A
death after Election belongs to the following interval. This avoids combining
pre-Election Primary mortality with a post-Election spouse/DVA state; an exact
event-time implementation would require a finer life-state model.

Actual Account-Value deductions — collected fees, Account-Value-funded income
and Excess Withdrawal — reduce the future crediting frame proportionally. A
Guarantee Claim does not reduce the frame again.

## 5. Fixed Lifetime Income

The versioned rate card uses age and sex at policy commencement, not at income
start. For spouse income, the younger life supplies the rating age and sex; an
equal-age tie uses the Primary Life. Non-integral ages are linearly
interpolated. The Fixed Income rate after `n` complete Growth years is

```text
g(n) = base_rate(age_0, sex, single_or_spouse)
       + n * fixed_escalator(age_0, sex).
```

The escalator is additive in percentage points. At election time `tau`,

```text
I_annual = AV_post_fee,tau * g(n),
I_month  = I_annual / 12.
```

Locked income then remains nominally constant unless an Excess Withdrawal
reduces it. Positive later credits increase Account Value but do not ratchet
Fixed Income. For a payment month,

```text
income_from_AV = min(AV_before_payment, I_month),
Guarantee_Claim = max(I_month - AV_before_payment, 0).
```

Income continues while the covered life or last survivor remains eligible,
even after Account Value reaches zero. Full Withdrawal is different: it
terminates the guarantee.

## 6. Fee event subledger

Let `A_prod` and `A_lip` denote accrued but unposted fees. For a day fraction
`delta_d` under ACT/365F,

```text
Delta A_prod = product_fee_rate * AV_fee,d * delta_d,
Delta A_lip  = lip_rate         * AV_fee,d * delta_d.
```

The model uses the positive contractual crediting frame as the administrative
fee-base proxy and holds it piecewise constant between monthly grid points.
Calendar days are derived from `commencement_year`; until an ISO commencement
date is present in the model-point schema, a fractional year is deterministically
mapped to the nearest day of that year. Thus the day count is reproducible, but
the daily Account-Value path remains a monthly piecewise-constant proxy.

At a contractual posting event with available Account Value `AV_pre`,

```text
collected = min(AV_pre, A_prod + A_lip),
AV_post   = AV_pre - collected.
```

If Account Value is insufficient, the collected amount is allocated pro rata
between the two balances. Only collected amounts are insurer fee inflows. No
uncollected arrears are carried after an event. If regular income exhausts
Account Value between events, outstanding balances are written off without an
insurer cashflow.

For expected-cashflow mortality and lapse modelling, terminating branches use
their own fee settlement and post-fee benefit base while the survivor branch
retains its subledger until a later event.

## 7. Income withdrawals, MVA and death

Every voluntary withdrawal in Income is an Excess Withdrawal. There is no free
allowance and no separate 95% cap in Income; the minimum transaction and minimum
residual Account Value remain binding. If `G` is the gross Account-Value
deduction and `MVA` the retained adjustment,

```text
cash_to_policyholder = G - MVA,
AV_after             = AV_before - G,
income_after         = income_before * (1 - G / AV_before).
```

The MVA is a ten-year interest-rate and termination-cost proxy derived from the
issue curve, current Hull-White curve and the versioned cost assumptions. It is
bounded so it cannot increase the withdrawal or exceed its base. Full
Withdrawal first settles fees, applies MVA to the remaining Account Value, pays
the surrender benefit and terminates the contract.

A terminating death benefit is positive Account Value after the applicable fee
posting and carries no MVA. Under spouse continuation, the first death does not
also pay Account Value; income continues to the surviving spouse and any
positive Account Value is paid only at last-survivor death. The alternative
lump-sum election terminates income on Primary-Life death.

## 8. Mortality methodology and limits

Mortality may be represented through probability weights rather than sampled
death indicators. At each Policy Anniversary, one generational annual
mortality rate `q_x` is fixed for the following Policy Year and converted to
the monthly grid:

```text
q_month = 1 - (1 - q_x)^(1/12).
```

Consequently, outside the terminal year, the twelve monthly survival factors
reconcile exactly to `1 - q_x`. The interval ending when the insured life first
reaches age 115 has death probability one. Monthly cashflow mortality,
survival helpers, life expectancy and the behaviour annuity factor all use
this convention. The behaviour factor values monthly-in-arrears payments on
the same survival curve rather than a separate annual mid-year proxy. A
deliberately shortened valuation horizon reports remaining post-fee Account
Value as `terminal_closeout`; it is not classified as a Death Benefit.

Generational improvements are anchored to the table base year and policy
commencement year. Single-life income and death benefits use Primary-Life
mortality. Last-survivor cover combines the two survival curves under the
independence assumption:

```text
p_last_survivor = p_1 + p_2 - p_1 * p_2.
```

`MortalityTable.gompertz_makeham()` is an illustrative shape proxy only. A
governed valuation must load an approved table through
`MortalityTable.from_qx(...)`, retain table provenance and review improvement,
selection and longevity-stress assumptions. The baseline has no stochastic or
systematic longevity factor and no mortality dependence between spouses.
Single-Life runs use expected decrements. At the low-level API, a standalone
deterministic Joint-Life projection also retains the historical expected-
decrement Joint-/Single-Life split unless pathwise status is requested. The
portfolio Dynamic, LSMC and V00/V01/V10/V11 factor runs force separately
sampled Primary-/Spouse-alive indicators for every arm, using one dedicated
common-random-number mortality seed. This prevents the Behaviour decomposition
from mixing a change in Election/exit policy with a change in mortality
estimator. Divorce/removal, common shock and legal eligibility changes remain
outside the model.

## 9. Policyholder behaviour

The productive assumption loader reads:

- `../input_dynamic_behaviour/dynamic_behaviour_baselines.csv`; and
- `../input_dynamic_behaviour/dynamic_behaviour_coefficients.csv`.

The files contain annual base rates and Cox-style proportional-hazard or
fractional-logit response parameters. Market moneyness and gross paid premium
are covariates. Structural zero and one baselines remain exact, and an annual
hazard is transformed before conversion to a monthly probability.

The generic product applies the following eligibility gates:

- Growth lapse/full surrender is always zero;
- free, partial and excess withdrawals are always zero in Growth;
- Income Take-up is evaluated only at Policy Anniversaries after Credit,
  fee posting and the mortality decrement for the elapsed interval. The
  Dynamic portfolio workflow uses the loaded state-dependent hazard;
  `income_start_year` is used only by the explicit deterministic benchmark;
- Income lapse/full withdrawal and Income Excess Withdrawal may use the loaded
  dynamic assumptions. Income lapse remains possible while the guarantee is
  in force after Account Value exhaustion; and
- the contractual automatic start after age 100 is separate from the 100-%
  statistical baseline band historically named `force_by_year` in the
  Behaviour input. Only the former is reported as a forced contractual start.

For state-dependent Spouse Income, Primary and Spouse life statuses are drawn
and retained separately on each market path. A path on which the Spouse dies
before Election uses the Single-Life fallback rate; after a valid Joint-Life
Election, `p11`, `p10` and `p01` paths retain their own observable state. This
avoids applying a nonlinear Behaviour function to a survivor-state average.
The deterministic benchmark continues to use the historical model-point
Election date so its former Election mechanics remain reproducible. Portfolio
factor runs nevertheless use the same pathwise Joint-Life mortality basis in
V00/V01/V10/V11; only the standalone low-level deterministic API defaults to
the former expected spouse-survival split.

Every shipped behavioural value is labelled `uncalibrated_proxy`. The cited
literature motivates functional form only and does not calibrate the numerical
coefficients. Production use requires portfolio experience, segmentation,
credibility analysis, backtesting and formal governance. LSMC is deliberately
implemented as a separate fitted research policy, not as a statistical
`BehaviourModel` regime.

The dynamic-behaviour files are loaded and hashed in the Dynamic portfolio
manifest. Their Income take-up, lapse and withdrawal functions are evaluated
on the actual path state for Single and Joint Life. For Continue-Income Joint
Life, the separately sampled `p11`, `p10` and `p01` paths retain their own
Account Value, fee and life-status history; the nonlinear response is never
applied to an averaged survivor state. Contractual Growth prohibitions and the
automatic-start gate take precedence over proxy rates. The model-point
`income_start_year` is an explicit deterministic benchmark and one member of
the pre-declared LSMC training-anchor library; it does not constrain the
dynamic Election state transition.

### 9.1 Combined optimal-behaviour policy

The separate research LSMC entry point projects the same contract from issue
and solves an ordered two-stage Multiple-Stopping problem:

```text
Growth: WAIT_FOR_ONE_YEAR | START_INCOME_NOW
Income: CONTINUE_FOR_ONE_YEAR | FULL_WITHDRAWAL_NOW
Terminated: no action
```

The analogy to a Swing right is limited to the Bellman comparison of value
without exercise against immediate action value plus value in the successor
regime. The state dimension is the irreversible contract phase, not an
inventory or a number of interchangeable exercise rights. Election must occur
before Lapse, START and FULL_WITHDRAWAL cannot occur at the same Anniversary,
and there is no gas-price, volume or inventory model.

Both decisions are permitted only at annual Crediting Anniversaries. The
Income/Lapse subproblem is solved first, backwards over annual
`CONTINUE_FOR_ONE_YEAR` versus `FULL_WITHDRAWAL_NOW` decisions. Its training
states use randomized, fold-stratified START dates spanning early, middle,
late, model-point and forced Election. The Lapse target is
`Delta_lapse = Q_lapse - Q_continue`: `Q_lapse` is the existing net Surrender
Benefit after the Projector's fee and MVA logic; `Q_continue` contains every
monthly Policyholder cashflow and transition through the next Anniversary plus
the later realised value under the fold-pure policy. A zero Surrender Benefit
with non-negative continuation and positive remaining guaranteed Income is a
dominated action: it is assigned deterministically to CONTINUE and is not used
to learn an artificial exercise boundary.

The Growth/Election recursion is solved second. `Q_wait` contains the complete
monthly Growth projection through the next Anniversary and the later Growth
value. `Q_start` uses the Projector's full post-credit, post-fee,
post-mortality Election transition and then the already-solved annual Lapse
policy. `START_INCOME_NOW` fixes Income from the rate card and Account Value at
that boundary; its first regular Income payment remains one month later. The
first voluntary Lapse is no earlier than the following Crediting Anniversary.
Growth surrender and all Growth withdrawals remain prohibited.

Partial Withdrawals, Partial-amount grids, Partial-fraction regressions and
under-year voluntary LSMC actions are not part of the combined optimal policy.
The general monthly Projector retains contractual Partial-Withdrawal support
for other behaviour regimes, but an optimal-policy rollout asserts that its
Partial ledger is zero. Regular Fixed Income, monthly mortality, Spouse
mortality, Account-Value exhaustion, Guarantee Claims, daily/monthly fee
posting, Death Benefits and monthly money-market discounting remain in the
canonical Projector and are not annualised or reimplemented in LSMC.

Complete paths, including all action replicas, remain in one fold. Direct
action advantages are fitted by augmented truncated-SVD/Ridge least squares;
Ridge is selected from a fixed grid by out-of-fold decision loss. The action
buffer is based on advantage RMSE. Material missing or unstable regressions do
not silently become WAIT or CONTINUE: they make the fit invalid.

At each annual decision point the estimator tries the compact full basis, then
a linear core basis, then a paired constant-advantage model, and finally local
pooling over adjacent policy years. A fit is deployable only if material
weighted relevant exposure is covered.
Decision points below one millionth of initial exposure may be recorded as
`immaterial_no_fit`; this is the only no-action numerical fallback.

Before the policy is frozen, its cross-fitted training value is compared with
the pre-declared fixed Election library (earliest, year 5, year 10, model-point
date and contractual force, with duplicates removed), each with Continue-only
and annual-Lapse variants. The fully dynamic candidate is retained only when
its paired 95% training lower bound clears the best fixed candidate by one
basis point of premium. Otherwise that fixed candidate is stored explicitly as
the training selection. This uses training paths only.

Training, validation and final evaluation are three independent samples. The
frozen candidate is checked by paired Common-Random-Number 95%
non-inferiority gates for Election-only, Lapse-only and Combined behaviour
against the pre-declared library, with a tolerance of one basis point of
premium. Validation does not tune regressions. If V11 fails, the policy
actually deployed on the evaluation sample is the best pre-declared fixed
validation baseline; candidate value, selected value and fallback reason are
reported separately. Three separately trained policies, using three
pre-declared training-seed triplets, must each pass all gates on the same
validation paths or deploy their recorded fallback, and are each reported on
the same final evaluation paths.
The first seed is the pre-declared primary reporting policy; final evaluation
is never used to select among seeds. The fit-basis fingerprint includes
training scenario content, Cap,
stress, product and policy basis including the pre-declared model-point
benchmark date, mortality, expenses, projection
configuration and LSMC settings. A Cap×stress analysis must therefore refit,
and evidence a distinct fit basis, for every cell.

The V00/V01/V10/V11 report explicitly separates fixed Election/Continue (V00),
fixed Election/annual Lapse (V01), annual Election/Continue (V10) and annual
Election/annual Lapse (V11). It reports paired `V01 - V00` Lapse optionality,
`V10 - V00` Election optionality and `V11 - V00` combined optionality, and
compares V11 with `max(V00, V01, V10)` on identical scenarios and cashflow
definitions.

The annual action frequency is a model convention: it assumes the customer can
elect Income and voluntarily fully withdraw only at the yearly Crediting
Anniversary. Under-year reactions to the Hull-White curve, MVA or Account Value
are not modelled. This restriction does not alter the monthly contract and
cashflow projection inside each annual Bellman step. The resulting fitted LSMC
value is a risk-neutral Policyholder lower bound, not an insurer-profit or CSM
optimisation.

## 10. Market models and measures

### 10.1 Input discipline

`load_market_assumptions()` reads only:

- `input_market_data/australian_zero_curve.csv`; and
- `input_market_data/model_parameters.csv`.

No additional volatility surface, credit curve or physical calibration file is
required by the baseline. The Global Equity total-return index has no separately
added distribution yield.

### 10.2 Risk-neutral valuation

The default valuation model is Heston-Hull-White under `Measure.RISK_NEUTRAL`:

```text
dS_t / S_t = r_t dt + sqrt(v_t) dW_S,t,
dv_t       = kappa(theta - v_t) dt + xi sqrt(v_t) dW_v,t,
```

with one-factor Hull-White rates fitted to the initial Australian curve.
Discount factors are pathwise money-market factors

```text
D(0,t) = exp(-integral_0^t r_s ds).
```

The rolling bond sleeve uses the same pathwise Hull-White term structure.

### 10.3 Simplified Real-World projection

The default Real-World model is Black-Scholes-Hull-White under
`Measure.REAL_WORLD`. Global Equity drift is the pathwise risk-free rate plus
the existing equity risk premium. The rate dynamics are unchanged from the
risk-neutral model: there is no bond term premium or separate market price of
rate risk. Results must be labelled simplified Real-World projections with
fixed proxy assumptions.

### 10.4 Reusable risk-neutral market paths

Large risk-neutral Heston-Hull-White path sets may be created once by
`portfolio_simulations/precompute_q_market_and_hedge_cache.py` and reused by
valuation, behaviour and optimisation runners. The cache key is an exact hash
of the risk-neutral measure and model, ESG configuration, Australian curve and
model-parameter file hashes, horizon, path count, seed, monthly grid, Heston
substeps and named market variant. A different seed, stress, horizon or input
file therefore has a different entry; no nearest-match cache lookup is used.

Each scenario component is stored as a separate non-pickled `.npy` array and
loaded read-only by memory map. The manifest and reconstructed scenario content
fingerprint are revalidated before use. Only the explicit precompute runner may
write cache entries. Valuation and optimisation code only reads an exact entry,
may simulate a missing market entry when that is explicitly permitted, and
never silently overwrites an existing mismatch.

## 11. Annual hedge pricing and intra-year DVA

Annual realised credit uses the simulated complete Reference Fund directly.
The default annual hedge purchase cost is a conditional Monte Carlo value of
the one-year call spread on that **whole** fund. It is not a sum of separately
priced equity and bond options. At each anniversary and cap-grid point the
cache contains the pathwise conditional value

```text
E_Q[D(t,t+1) * (max(R_fund, 0) - max(R_fund - Cap, 0)) | state_t].
```

The regression state is limited to information available at that anniversary:
current Global-Equity Heston variance, short rate, one- and five-year
Hull-White zero rates and policy year. Fold-excluding Ridge predictions provide
the value for each path, so a path's realised next-year payoff is never used in
its own fitted target. Non-negativity, zero value at a zero cap, monotonicity in
the cap and a discounted-payoff upper bound are enforced after prediction.
The resulting hedge-price cache is keyed separately by the exact market cache,
scenario and training fingerprints, path count, horizon, equity index and
allocation plus allocation-file hash, five-year rolling-bond convention,
monthly rebalancing, cap grid, fold definition, seed and Ridge setting.

This is a one-year price recomputed conditionally at each anniversary. It is
not a full multi-year forward-start strip bought at issue and it does not use
nested Monte Carlo. All model points using the same market/allocation/cap-grid
configuration share the same surface. `moment_matched_bs` remains an explicit
annual hedge-pricing fallback; it is not the default conditional-MC method.

The intra-year DVA still requires a mark between anniversaries. That separate
customer-liability mark uses a transparent moment-matched Black-Scholes proxy
on the whole Reference Fund.

The equity volatility is the BS volatility or conditional expected Heston
variance. The rolling bond's local diffusion magnitude is the Hull-White
zero-bond loading

```text
sigma_B = B(5) * sigma_r,
B(tau)  = (1 - exp(-a * tau)) / a.
```

For an option horizon `T`, the fund must also be expressed relative to the
`T`-bond numeraire.  With equity weight `w = 0.5`, define

```text
c       = (1-w) B(5),
I_B     = integral_0^T B(s) ds,
I_B2    = integral_0^T B(s)^2 ds.

Var_F(T) = (w sigma_E)^2 T
           + sigma_r^2 [I_B2 - 2 c I_B + c^2 T]
           + 2 rho w sigma_E sigma_r [I_B - c T],

sigma_F(T) = sqrt(Var_F(T) / T).
```

The terms in brackets integrate the forward-rate loading
`B(s) - (1-w)B(5)`.  This both reflects the negative local short-rate loading
of the rolling bond and includes the option-numeraire adjustment.  At `w=1`
the expression reduces to the engine's usual Merton/Hull-White adjustment for
a pure-equity option.
The DVA factor is the zero-bond leg to the next anniversary plus a
Black-Scholes call spread at strikes `1` and `1.06` on the complete fund.
This is a customer-liability value only; it is not the insurer backing asset.

The insurer hedge and backing are recorded separately:

- the administrative crediting frame at each monthly interval start is backed
  by a continuously rolled AUD overnight account. The under-year DVA option
  mark is a customer-liability value and is not treated as a backing asset.
  The monthly cashflow-grid return is the pathwise ratio of Hull-White discount
  factors. This is the daily-roll economic equivalent of accumulating the
  simulated overnight short rate and contains no Reference-Fund return;
- at the start of each crediting year the standard hedge is Long Call at return
  strike 0 minus Short Call at return strike Cap (gross strikes `1` and
  `1 + Cap`);
- `hedge_cap_leg_mode=sold` is the default and leaves no insurer payoff above
  the customer cap. `not_sold` buys only the uncapped long call; the additional
  fair premium is paid and `max(R_reference - Cap, 0)` is recorded as a
  separate insurer hedge gain;
- the insurer pays the full fair option value, plus a purchase markup of 0.50%
  of that fair value and an annual 0.30% management-fee proxy on hedge
  notional. These two fixed inputs are in `cost_assumptions.csv` and never
  reduce customer Account Value or Reference-Fund return; and
- the former volatility-add-on execution proxy remains available for
  compatibility but is zero in the standard cost assumption set, so it is not
  layered on top of the new explicit costs by default.

The user's description of a sold "Put at the Cap" is implemented by economic
effect rather than label: a capped positive-return payoff requires a sold cap
**Call**. Selling a Put at that strike would create a different downside payoff
and would not remove the insurer's upside above the cap.

The DVA mark is **moment matching**, not a calibration to mixed-fund option
quotes. It does not introduce a new volatility input, but it suppresses higher
moments, stochastic-volatility skew and some dynamic dependence. The annual
conditional-MC hedge values retain the simulated one-year distribution but are
still regression estimates rather than executable market quotes. The portfolio
path sets and enforces `ProjectionConfig.heston_cos=False`; retained COS
utilities for legacy equity options are unused. LSMC neither replaces nor
recalibrates the DVA proxy or the annual hedge-pricing regression.

## 12. Cashflow and valuation definitions

Policyholder-facing benefits are reported positive:

```text
PV_policyholder_benefits
  = PV(income_paid)
  + PV(death_benefits)
  + PV(surrender_benefits)
  + PV(partial_withdrawals)
  + PV(terminal_closeout).
```

For the ordered optimal-behaviour LSMC specifically,
`partial_withdrawals = 0` by construction. Its objective is therefore the
risk-neutral expected present value of Income, Death Benefits, Surrender
Benefits and terminal closeout. CSM, insurer fees, hedge results and Guarantee
Claims are not separate optimisation terms; product mechanics affect the
objective only through actual Policyholder payments and later contract state.

Future fee income is based on collected event cashflows:

```text
PV_future_fees = PV(Product Fees) + PV(Lifetime Income Premiums).
```

The insurer hedge/backing aggregates reconcile exactly once:

```text
Crediting Margin = Money-Market Income + retained Excess Hedge Gain,

Hedge Costs
  = Fair Option Package Cost
  + Option Purchase Markup
  + Hedge-Reference Management-Fee Cost
  + optional legacy Execution Cost.
```

The separate `contract_financing_margin` is used only by the customer-flow
market-consistency identity. It is not added to insurer P&L or BEL. This keeps
the liability reconciliation independent of the insurer's backing choice.

For the gross-of-reinsurance baseline, the Non-Unit Best Estimate Liability is

```text
BEL_nonunit
  = PV(Guarantee Claims)
  + PV(Expenses)
  + PV(Hedge Costs)
  - PV(Product Fees)
  - PV(Lifetime Income Premiums)
  - PV(Crediting Margin)
  - PV(MVA retained).
```

For duration-zero new business,

```text
BEL_total = initial Account Value + BEL_nonunit.
```

The rider guarantee value is

```text
Guarantee Value = PV(Guarantee Claims) - PV(LIP).
```

Insurer net present value before risk margin includes modelled fee, stochastic
overnight-backing and optional excess-hedge inflows less Guarantee Claims,
expenses and hedge costs. Corporate tax,
shareholder hurdle rate, capital earning spread and cost of capital belong to
their named capital/profitability layers and are not extra terms in BEL.

Income paid and Guarantee Claims must not be equated: only income above
available Account Value is a claim. Likewise, fee accrual and fee cashflow must
not be equated. MVA may be shown either gross as a retained offset or net in the
withdrawal benefit, never both.

## 13. Portfolio aggregation and fair-fee diagnostics

`load_policyholder_model_points()` currently accepts the repository's
duration-zero new-business Growth records. It validates premium, Account Value,
phase, Fixed Income, spouse fields, identifiers and source weights. The four
AGILE allocation columns are validated for source integrity but deliberately
ignored; the generic Reference Fund allocation is a product-level CSV input.

`value_policyholder_portfolio()` builds one common risk-neutral scenario set
large enough for all model-point horizons, reuses it for all model points and
optional fee solves, projects sequentially and retains scalar output. This is
plain Monte Carlo with common random numbers and never uses COS. Without an
external policy factory it uses statistical/static Behaviour; the combined
LSMC runner injects one frozen out-of-sample policy through that explicit
factory boundary.

Only in the deterministic validation benchmark is `income_start_year` a fixed
Election input, subject to the earlier contractual automatic-start
anniversary. At the low-level backward-compatibility API, let `s_2(T)` be
spouse survival from issue to that effective anniversary under the same
reconciled monthly mortality basis. Its expected-decrement model-point value
is

```text
V_joint_point = s_2(T) * V(both alive at Election)
              + (1 - s_2(T)) * V(Single-Life fallback).
```

Both conditional low-level benchmark projections have identical pre-Election
cashflows, so the convex combination retains those cashflows once. Portfolio
factor runs retain the same deterministic Election rule for V00/V01 but use
separate pathwise life statuses in all four cells. Dynamic and optimal main
runs use those statuses at every Election and later Behaviour decision. Lives
remain independent; this is not a general couple-state model for
divorce/removal or common mortality shocks.

Every model point is valued before any portfolio weighting. The result keeps
three distinct layers:

```text
per-contract value_i = value_contract(policy_i),
normalised contribution_i = contract_weight_i * per-contract value_i,
absolute contribution_i = represented_contract_count_i * per-contract value_i.
```

Without contract counts, only the normalised weighted-average contract is
available. With `portfolio_contract_count = N`, represented contract count is
`N * contract_weight_i`. The loader also accepts an optional, positive
`exposure_count` column; when present, those source counts determine absolute
contributions directly and must reconcile to `contract_weight`. The number of
CSV rows is never treated as the number of policies. `premium_volume_weight`
remains a control field only.

Two optional Lifetime Income Premium solves are distinct:

1. **Fair LIP:** solve `Guarantee Value = 0`.
2. **Commercial break-even LIP:** solve `Insurer NPV before risk margin = 0`.

Both reuse the same market scenarios. The charged-minus-fair spread in basis
points, per-contract NBM and the normalised or absolute insurer-NPV contribution
show which model points contribute more or less value under the stated
assumptions. A missing root bracket is reported explicitly and is not converted
into an extrapolated fee.

For a product-wide charge, the workflow can additionally solve a common
portfolio Fair LIP or common commercial break-even LIP directly against the
weighted aggregate objective. The objective values reported at the solver
bounds are on a normalised average-contract basis; multiplying the objective by
an available total contract count changes its scale but not its root.
Individual model-point rates are diagnostics and are never averaged to
manufacture a portfolio price.

The runner is `portfolio_simulations/run_portfolio_valuation.py`. Its default
output directory is `portfolio_simulations/output/portfolio_valuation/`. It
writes the portfolio summary, explicit model-point results, an aggregation
reconciliation, optional fee diagnostics, a run log, a provenance manifest and
headless PNG charts unless plotting is disabled.

## 14. Cost layers and provenance

`load_cost_assumptions()` reads
`../input_cost_assumptions/cost_assumptions.csv`. The following layers remain
separate:

- Product Fee and LIP are customer Account-Value deductions and collected
  insurer inflows;
- acquisition, commission and maintenance are insurer expenses and do not
  reduce Account Value again;
- the option purchase markup is 0.50% of fair option value and the hedge-
  reference management fee is 0.30% p.a. of hedge notional;
- the volatility add-on is a legacy package-repricing proxy, not a cash fee
  rate, and is zero in the standard assumptions;
- MVA loadings affect only relevant withdrawal cashflows;
- cost of capital affects the Risk Margin proxy; and
- hurdle rate, corporate tax and capital earning spread affect shareholder
  profitability.

Rows marked `include_in_base_case=false` or `data_required` are exclusions or
missing-data markers, not calibrated zero costs. All runners should retain
assumption-set identifiers, paths, effective dates, SHA-256 hashes, scenario
settings and transformation notes in provenance.

## 15. Model boundaries and legacy code

The active implementation remains a research baseline. Material limits are:

1. The bond sleeve is a fixed five-year zero-coupon proxy with monthly
   rebalancing and no credit, inflation or transaction-cost model.
2. The fixed 6% cap is a product convention, not an observed cap calibrated to
   executable mixed-fund hedge quotes.
3. The intra-year DVA uses whole-fund moment matching. Annual conditional-MC
   hedge prices use cross-fitted regressions on simulated one-year payoffs.
   Both remain proxies requiring validation against the administrative formula
   and executable market quotes.
4. The 0.30% hedge-reference management fee is a fixed annual notional-cost
   proxy. It does not reduce the customer Reference-Fund return or the option
   payoff path. No separate hedge-fund NAV or fee term structure is calibrated.
   An annual option cost is treated as sunk after purchase: no intra-year
   unwind or recovery is recognised after death, lapse or withdrawal, and an
   unsold-cap gain is recognised only on the active remaining notional at
   settlement. This is a conservative hedge-P&L simplification.
5. Fee day counts are calendar-exact under ACT/365F, but the administrative fee
   base is piecewise constant on the monthly grid and commencement dates are
   derived from fractional years.
6. The shipped mortality and behaviour bases are proxies. Systematic mortality,
   dependence between lives and Australian experience calibration are absent.
7. Current portfolio loading is for duration-zero new business, not a complete
   in-force-state migration.
8. Personal tax/withholding, adviser fees, reinsurance, FX, tactical allocation
   and customer-Reference-Fund internal fees are excluded from the baseline.
9. `capital.py` is a research capital proxy, not APRA/LAGIC prescribed capital.
10. Portfolio arrays are not streamed or distributed; production scale requires
   batching, online aggregation and convergence controls.

`AgileProduct` remains an import alias for compatibility. Legacy
`InvestmentOption`, `CapSchedule`, Partial Protection, Age Pension+, Rising
Income, COS utilities, LSMC source, example runners and historical outputs may
remain in the repository. They do not alter the active generic product and are
not used by the portfolio runner unless explicitly invoked in legacy research
code. `tests/` and `../Code based on Papers/` are not runtime data sources.
