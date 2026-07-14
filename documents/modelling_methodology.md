# Modelling Methodology

## Scope

The model is a research implementation for a generic Australian index-linked
lifetime-income contract. It combines a monthly product state machine with
market-consistent valuation, simplified real-world projections, mortality,
statistical or optimal policyholder behaviour, insurer cashflows and annual
crediting-cap control.

The primary profitability measure is the signed new-business CSM proxy

$$
\mathrm{CSM}^{proxy}
=PV(\text{Fee Income})+PV(\text{Other Income})
-PV(\text{Claims})-PV(\text{Costs}).
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
R^{fund}=0.30R^{global\ equity}+0.70R^{5y\ government\ bond}.
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

The combined policyholder LSMC treats the contract as an ordered multiple-action
problem:

- Growth: `WAIT` or `START_INCOME_NOW` at annual dates;
- Income: `CONTINUE` or `FULL_WITHDRAWAL_NOW` at annual dates.

Partial withdrawal is not in the current optimal action set. Fits use complete
path folds, held-out validation and an independently evaluated deployed policy.
The approach gives a fitted lower bound within the specified basis/action set;
it is not proof of a global optimum.

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

The risk workflow compares the dynamic-function and deployed LSMC policies on
the same Q scenarios for predeclared caps. Optional shocks are recomputed under
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
must identify its sample, cache fingerprints, assumptions and whether a fitted
policy passed validation.
