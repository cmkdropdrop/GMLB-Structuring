# Modelling Methodology

## Scope

The model is a research implementation for a generic Australian index-linked
lifetime-income contract. It combines a monthly product state machine with
market-consistent valuation, simplified real-world projections, mortality,
statistical or optimal policyholder behaviour, insurer cashflows and annual
crediting-cap control.

The primary profitability measure is the signed new-business CSM proxy

$$
\mathrm{CSM}^{\mathrm{proxy}}
=\mathrm{PV}_{\mathrm{fees}}+\mathrm{PV}_{\mathrm{other}}
-\mathrm{PV}_{\mathrm{claims}}-\mathrm{PV}_{\mathrm{costs}}.
$$

It is not a complete IFRS 17 CSM because the code does not perform grouping,
coverage-unit release, risk adjustment, loss-recovery, reinsurance or general
ledger accounting.

## Risk-neutral economic scenarios

Regular Q valuations use a Heston–Hull–White hybrid:

- stochastic volatility for Australian and Global Equity;
- a Hull–White short-rate process fitted exactly to the input Australian zero
  curve at time zero;
- configured equity/equity and rate/equity correlations;
- risk-neutral equity drift consistent with the chosen total-return indices.

The model consumes only the Australian zero curve and the parameters already in
`model_parameters.csv`. It does not request an external volatility surface or a
separate calibration history.

### Mandatory Q caches

Operational Q valuation never simulates paths inside a reader. Exact monthly
market paths, pathwise discount factors and derived reference-fund paths come
from `results/cache/q_market_paths`. Annual new-issue `mc_conditional` call-spread
prices come from the congruent `results/cache/q_hedge_prices` entry.

Only `precompute_q_market_and_hedge_cache.py` writes either cache. Cache identity
includes market inputs, scenario configuration, path count, seed, horizon,
substeps and market stress. Hedge identity additionally includes the exact
market-path fingerprint, product allocation and cap grid. Non-market mortality,
longevity and expense stresses do not change the market-cache key.

Readers fail on a missing or inconsistent exact entry. An orchestration workflow
may invoke the authorised precompute process for missing entries, but may not
write or approximate a cache itself.

`moment_matched_bs` is an explicit annual hedge-price proxy. It never serves as
a silent fallback from `mc_conditional`. The under-year DVA mark is a separate
moment-matched approximation.

## Simplified real-world scenarios

Real-world projections use Black–Scholes–Hull–White under
`Measure.REAL_WORLD`. Equity drift equals risk-free drift plus the supplied
equity risk premium. The rate process is unchanged from Q because the simplified
baseline introduces neither a bond term premium nor a market price of rate risk.

The reference fund is rebalanced monthly:

$$
R^{\mathrm{fund}}
=0.30R^{\mathrm{global}}+0.70R^{\mathrm{bond}}.
$$

The preferred bond return is obtained from pathwise Hull–White zero-coupon
prices for a rolling five-year constant-maturity position, capturing coupon-like
carry, price movement and roll-down together. A short-rate accumulation is
permitted only as an explicitly labelled technical fallback.

These are simplified proxy projections. They are not calibrated forecasts.

## Product projection

The monthly projector is the single source of contractual cashflow logic. It
tracks policy phase, account value, fee accrual, annual crediting frame, locked
income, mortality state, spouse state, withdrawal eligibility, hedge cost and
insurer/customer cashflow ledgers.

The full combined-fund return is calculated before applying the annual floor or
cap. Customer fund performance is not confused with the insurer's money-market
backing return or hedge P&L.

## Mortality

The base mortality table is an illustrative Gompertz–Makeham construction with
annual improvement. Annual death probabilities are converted to reconciled
monthly conditional probabilities. Expected-decrement projections and pathwise
primary/spouse states use the same basis. Joint life currently assumes
independent lives. See [mortality_modelling.md](mortality_modelling.md).

## Policyholder behaviour

Two primary approaches are supported.

### Statistical dynamic behaviour

Versioned functions model:

- annual income take-up after contractual eligibility;
- ordinary and performance-sensitive lapse in income;
- partial/excess withdrawal frequency and amount;
- full withdrawal as a competing voluntary event.

Signals include age, duration, moneyness and the realised gap between reference
and credited performance. Growth withdrawals remain contractually prohibited.

### Optimal LSMC behaviour

The combined policyholder LSMC treats the contract as an ordered, Swing-like
two-regime stopping problem:

- Growth: `WAIT` or `START_NORMAL_INCOME` at annual dates;
- Income: receive normal Scheduled Income and `CONTINUE`, or
  `FULL_SURRENDER`, at annual dates.

The customer objective is formed at time zero,

$$
V_0=\mathbb E_0^Q\!\left[\sum_t P(0,t)\,CF_t^{\mathrm{customer}}\right],
$$

where every $P(0,t)$ comes from the current Australian zero curve. Realised
future short-rate discount paths do not enter this customer objective. Customer
cashflows are normal income, Full-Surrender proceeds and the post-fee account
value closeout at the finite projection horizon. There is no additional
guarantee tail after that horizon.

The fit is conditional on survival: mortality and death benefits are zero in
the backward induction, so Full Surrender is the only voluntary terminating
action. The configured mortality basis is restored for the subsequent
actuarial and CSM rollout. Partial Withdrawal is not in the optimal action set.
At an Income anniversary the regular monthly amount due under the projector's
event order is common to both alternatives; the decision is whether to continue
normal income for the coming annual period or surrender the remaining contract.

Complete-path folds estimate conditional continuation values. They are an
internal regression device, not a separate OOS acceptance test. The fitted V11
rule is deployed directly on the same exact Q sample, with no validation gate,
RMSE exercise buffer or fixed-policy substitution. A missing material decision
surface fails the run. Customer-LSMC runs use exactly one model point to keep
this full-horizon recursion tractable. The approach maximises the fitted value
within its state basis and action grid; it is not proof of a global optimum.

See [policyholder_behaviour.md](policyholder_behaviour.md).

## Insurer hedge and option cost

The standard annual hedge is a capital-market bull call spread: long the 0%
return call and short the call at the announced cap. The upper option is sold to
the market, not to the customer. A higher cap reduces the value received for the
short call and therefore increases net hedge cost.

Hedge cost includes fair option value, the explicit fair-value markup and the
hedge-reference management fee. The cost is assigned to the control year in
which the new annual hedge is purchased.

## CSM proxy cashflows

| Component | Included cashflows |
|---|---|
| Fee Income | Product fee, lifetime-income premium |
| Other Income | Money-market backing income, retained hedge gain where applicable, MVA and other explicitly retained margins |
| Claims | Guarantee shortfall claims and separately identified insurer-funded benefits |
| Costs | Acquisition/maintenance expenses and complete option/hedge costs |

Account-value-funded income, death benefits, surrender benefits and partial
withdrawals are customer investment-component payments and are not deducted
again. The implementation must reconcile the reported CSM to its four signed
components within numerical tolerance.

## Portfolio aggregation

Each model point is projected as a representative contract on common market
paths. Scalar values are aggregated using `contract_weight`. When no absolute
contract count is supplied, monetary results are labelled weighted averages per
representative contract. Premium-volume weights are retained for distinct
volume analyses and are not silently substituted for contract weights.

## Risk analysis

The risk workflow compares the dynamic-function and directly fitted LSMC V11
policies on one common exact Q sample for each predeclared cap. There is no
separate customer-LSMC validation or evaluation sample. Optional shocks are recomputed under
exact stress-specific caches for market stresses. Non-market stresses reuse the
base market cache. Stress outputs from this workflow are shock-and-revalue research
sensitivities, not regulatory capital or a pathwise VaR/CTE model.

When behaviour is refitted under a stress, the result measures a stressed
behavioural response, not the sensitivity of one frozen policy. Reports must
state which interpretation is used.

## Crediting-cap optimisation

The insurer may set the cap annually, subject to the 0.25% minimum. Separate
optimisers study statistical dynamic behaviour and optimal policyholder LSMC.
Both maximise the same CSM proxy and use pre-action state only.

Training, fixed-policy selection, adaptive validation and final evaluation are
disjoint. A flexible policy is deployed only when its paired validation uplift
over the selected best fixed cap clears the predeclared uncertainty and
materiality gates. Final evaluation is never used to select or repair a policy.
If validation fails, the deployed result is the fixed fallback and its
flexibility value is exactly zero; a rejected adaptive candidate may be shown
only as a diagnostic.

See [crediting_rate_optimisation.md](crediting_rate_optimisation.md).

## Model-risk boundaries

Material limitations include the proxy mortality and behaviour bases, aggregate
state compression in insurer optimisation, absence of policyholder tax and
reinsurance, independent joint-life mortality, the simplified physical rate
model and the research nature of capital/IFRS measures. Every published chart
must identify its sample, cache fingerprints and assumptions. Customer-LSMC
outputs must record structural validity and direct V11 deployment; adaptive
crediting-cap policies must separately record whether their own validation gate
was passed.
