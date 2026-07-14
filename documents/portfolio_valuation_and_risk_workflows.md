# Portfolio Valuation and Risk Workflows

## Purpose

The portfolio workflows connect portable inputs, exact market scenarios, the
monthly product projector, policyholder behaviour, custom-CSM profitability
components and shock-and-revalue analysis. The central design rule is
separation of duties:

```text
versioned inputs
    -> authorised exact-cache preparation
        -> read-only portfolio valuation
            -> read-only behaviour/risk comparison
                -> generated runs and curated figures
```

No valuation, behaviour or optimisation reader may simulate a replacement
risk-neutral scenario set or estimate a missing conditional-MC hedge price.

## Inputs and portable paths

All defaults are resolved relative to the repository by
[`repository_paths.py`](../code/policy_engine/repository_paths.py). The live
inputs are under `input_data/`:

| Input family | Role |
|---|---|
| `market_data/` | Australian zero curve and the existing model parameter set |
| `cost_assumptions/` | Customer charges, expenses, option markup and hedge-reference fee |
| `dynamic_behaviour/` | Versioned statistical behaviour baselines and coefficients |
| `equity_allocation/` | Product reference-fund equity weight |
| `mc_analysis/` | Predeclared Monte Carlo samples; customer LSMC uses the primary training row as its sole fit/valuation sample |
| `model_points_policyholders/` | Full and proxy representative-insured portfolios |

The Australian curve is the only live market time series. The baseline does not
request a volatility surface, credit-spread term structure or separate physical
calibration dataset.

## Exact market and hedge caches

### Market-path cache

`results/cache/q_market_paths` contains exact monthly Heston–Hull–White Q paths,
pathwise discount factors and the equity/rate state needed to construct the
reference fund. Its content-addressed identity includes the market input bytes,
model/measure, horizon, path count, seed, Heston substeps and market-stress
variant.

### Hedge-price cache

`results/cache/q_hedge_prices` contains annual path-congruent conditional-MC
prices for newly started call spreads. Its identity binds the exact market-path
fingerprint plus the product allocation, cap grid and hedge-pricing fit
configuration. It may reuse one market cache for multiple allocation or cap-grid
specifications, but each such specification has its own hedge entry.

### Sole writer

[`precompute_q_market_and_hedge_cache.py`](../code/portfolio_simulations/precompute_q_market_and_hedge_cache.py)
is the only authorised writer of either directory. For each requested exact
specification it:

1. attempts to load and validate the market entry;
2. simulates and writes it only if that exact entry is missing;
3. stops after the market step when `--market-only` was selected;
4. otherwise attempts to load and validate the congruent hedge surface;
5. builds and writes only a missing exact hedge surface.

Existing valid entries are not overwritten. A cache with a close path count,
nearby horizon, different seed or partial cap grid is not a substitute.

### What changes which key?

| Change | New market cache? | New hedge cache? |
|---|:---:|:---:|
| Market seed, path count, horizon or substeps | Yes | Yes |
| Curve, market parameters or market stress | Yes | Yes |
| Equity allocation | No, if the underlying market specification is unchanged | Yes |
| Cap grid | No | Yes |
| Mortality, longevity or lapse stress | No | No market-driven change |
| Expense or other non-market stress | No | No market-driven change |

With annual `mc_conditional` pricing, `--require-market-cache` and
`--require-hedge-cache` are effective requirements. `moment_matched_bs` must be
chosen explicitly and labelled as a proxy; it is never selected automatically.

## Orchestrated cache preparation

[`run_portfolio_risk_analysis.py`](../code/portfolio_simulations/run_portfolio_risk_analysis.py)
is the recommended end-to-end fixed-cap and risk orchestrator. Before any
reader child starts, it resolves the portfolio horizon and enumerates every
required combination of:

- sample role, path count and market seed (one `training_and_valuation` role for customer LSMC);
- base or market-stress variant;
- model settings and Heston substeps;
- product allocation and requested caps.

It then invokes the authorised precompute runner for those exact jobs. The
precompute runner validates reusable entries and computes only missing ones.
Only after successful preflight does the orchestrator launch the Dynamic and
LSMC read-only valuation children.

[`run_crediting_rate_optimisation.py`](../code/portfolio_simulations/run_crediting_rate_optimisation.py)
provides the equivalent boundary for cap-management research. The installed
`optimise-crediting-dynamic` and `optimise-crediting-lsmc` commands first parse
the selected optimiser configuration, derive the exact portfolio horizon and
enumerate the required path-count/seed identities. The Dynamic route
hard-requires exactly one modelpoint before any cache job and prepares one
complete Time-0 Q sample. The orchestrator invokes the sole authorised
precompute runner for each exact sample. With `mc_conditional`, it supplies the
complete optimiser cap grid and prepares the congruent hedge cache; with
explicitly selected `moment_matched_bs`, it prepares the market cache only. It
then launches the strict optimiser reader in a separate process with the cache
requirements enforced; the Customer-LSMC route uses the Bellman wrapper that
enforces LSMC Policyholder behaviour.

Standalone valuation scripts and the direct optimiser implementation files
remain strict readers. If one reports a cache miss, prepare exactly the
specification in its emitted command or use the corresponding orchestrated
console command. Do not relax the cache requirement or change inputs merely to
reach an existing entry.

## Dynamic-behaviour valuation

[`run_portfolio_valuation.py`](../code/portfolio_simulations/run_portfolio_valuation.py)
values each model point as a representative contract on a shared exact Q
scenario set. It applies the versioned dynamic take-up, lapse and withdrawal
functions and aggregates scalar outputs with `contract_weight`.

Unless `--portfolio-contract-count` is supplied, monetary portfolio results are
normalised weighted averages per representative contract. Premium-volume
weights are retained for separate volume views and are not silently used as
contract counts.

Material output families include:

- `model_point_results.csv`;
- `portfolio_summary.csv`;
- `portfolio_aggregation_reconciliation.csv`;
- `run_manifest.json` and `portfolio_valuation.log`;
- optional fair-fee and figure files.

The reconciliation file is part of the numerical contract, not an optional
presentation table.

## LSMC-policyholder valuation

[`run_portfolio_valuation_lsmc.py`](../code/portfolio_simulations/run_portfolio_valuation_lsmc.py)
uses the same product, market, mortality, cost and aggregation mechanics but
replaces statistical voluntary behaviour with one fitted ordered policy:

| Phase | Decision frequency | Current actions |
|---|---|---|
| Growth | Annual anniversary | Wait; start Income now |
| Income | Annual anniversary | Receive normal Scheduled Income and continue; full surrender |

Partial withdrawal and under-year voluntary actions are excluded from this
optimal action set. The customer value is
$\mathbb E_0^Q[\sum_tP(0,t)CF_t]$, using deterministic discount factors from
today's Australian zero curve. The fit is conditional on survival and includes
normal income, Full Surrender and the post-fee account-value closeout at the
finite horizon; actual mortality is restored only for the actuarial/custom-CSM
rollout.

Whole-path folds are internal continuation-value estimators. Fit and rollout
use one common exact Q sample, and the learned V11 rule is deployed directly.
There is no held-out OOS test, validation gate, RMSE exercise buffer or fixed
policy substitution. A material missing regression surface fails the run. The
runner requires exactly one model point for these full-horizon customer-LSMC
calculations.

In addition to the standard valuation outputs, the runner writes policyholder
action summaries, regression diagnostics, same-sample comparison tables and a
manifest that records direct V11 deployment and `oos_*_used=false`.

## Fixed-cap and behaviour-risk analysis

The risk orchestrator runs Dynamic and direct LSMC V11 policies for every
requested cap on one common market sample. The base workflow
focuses on cap and lapse/behaviour exposure. The default cap grid is 4%, 6%, 12%
and 15%; only 6% is the contractual base case.

Optional `--stress-analysis` expands the grid to requested one-factor stresses.
For market stresses, the full stressed Q scenario and hedge caches are prepared
and read. For mortality, longevity or expense stresses, the base market cache
is reused and the non-market assumption is changed in the projection. Permanent
lapse stresses are available only in the separate Dynamic-only MLL-FPAR
workflow below, not in this Dynamic-plus-LSMC orchestrator.

The workflow reports, among other items:

- custom-CSM profitability proxy and its Fee Income, Other Income, Claims and
  Costs legs;
- guarantee claims, option cost and money-market backing income;
- election timing, phase exposure and voluntary-action diagnostics;
- Dynamic-versus-direct-LSMC differences and time-zero customer optionality;
- cap secants and one-factor shock-and-revalue changes;
- model-point contribution and concentration diagnostics.

Its retained outputs are expected present values and model-point scalars, not a
pathwise shareholder-loss distribution. Therefore the workflow does **not**
produce VaR, TVaR/CTE, APRA LAGIC capital, an APRA prescribed capital amount or
a complete IFRS 17 Risk Adjustment. Its custom CSM is also not an IFRS 17 CSM
balance or movement. Calling model-point dispersion a tail-loss distribution
is incorrect.

When behaviour is refitted under stress, the result includes behavioural
adaptation to the stressed environment. It is not the sensitivity of one frozen
behaviour policy. The run manifest records the interpretation.

## Dynamic-only MLL future-profit-at-risk analysis

[`run_crediting_rate_capital_analysis.py`](../code/portfolio_simulations/run_crediting_rate_capital_analysis.py)
is the implementation behind the canonical
`crediting-future-profit-risk-analysis` command. It is the dedicated route when
Policyholder LSMC must not run. It hard-gates every valuation child to
`run_portfolio_valuation.py`, Dynamic election and Dynamic post-Income
behaviour, and exact required market and hedge caches. For every fixed cap it
runs common-random-number revaluations for base, mortality, longevity,
permanent lapse-up and permanent lapse-down assumptions.

The resulting **MLL future profit at risk (MLL-FPAR)** is the positive loss of
the repository's custom CSM under those stresses. It is a partial research
measure, not APRA LAGIC capital or a complete Solvency II SCR. Mortality and
longevity losses use permanent 15% and -20% mortality-rate shocks. The lapse
module takes the largest adverse permanent 50% up/down shock and a separately
disclosed 40% mass-lapse proxy on positive model-point custom CSM; the three
modules are then aggregated with the documented life-risk correlation matrix.

The command reports the secondary research sensitivity

$\mathrm{CSM}_{\mathrm{FPAR}}=\mathrm{CSM}-\lambda R_{\mathrm{MLL}}$,

with a default dimensionless penalty weight of $\lambda=6\%$. This weight is
not a capital charge, cost-of-capital rate or Risk Margin. The default and
primary fixed-design ranking is custom CSM. Ranking by this penalised value or
by CSM/MLL-FPAR requires the explicit `--objective fpar_penalised_csm` or
`--objective csm_to_fpar` choice. The historic `crediting-capital-analysis`
command, capital-named options and output fields remain compatibility aliases
only.

This evaluates a fixed product-design choice. It does not establish that an
annually adaptive discretionary cap rule has value. Outputs include the full
stress revaluation table, FPAR table, run manifest and diagnostic figures under
the historically named `results/runs/crediting_rate_capital_analysis/`
directory.

This is not an APRA calculation. [APRA LPS 115](https://www.apra.gov.au/standards/lps-115)
bases the Insurance Risk Charge on the capital-base effect of stressed adjusted
policy liabilities, [APRA LPS 112](https://www.apra.gov.au/standards/lps-112)
defines the adjusted-policy-liability/capital-base boundary, and
[APRA LPS 110](https://www.apra.gov.au/standards/lps-110) specifies the broader
prescribed-capital and Prudential Capital Requirement framework. The repository
does not calculate those quantities, nor does it calculate an IFRS 17 CSM.

## Time-zero value of annual cap flexibility

[`optimize_crediting_rate_dynamic_behaviour_alt.py`](../code/portfolio_simulations/optimize_crediting_rate_dynamic_behaviour_alt.py)
is the strict reader for the current annual-flexibility question. It uses
exactly one modelpoint, statistical Dynamic customers and Management LSMC. It
does not invoke Customer LSMC.

The fixed caps, Management-LSMC regressions and finished-candidate ranking use
one complete exact Q sample. Cashflows are discounted to Time 0 with the current
curve. There is no path reservation, OOS seed, forward roll, deployment gate or
strategy replay. The primary final score is custom CSM. The quantities
$\mathrm{CSM}-0.06\,\mathrm{MLL\mbox{-}FPAR}$ and CSM/MLL-FPAR are secondary
research sensitivities and do not select the policy. Twenty-one additive
Base/Stress objectives plus one conditional-ratio heuristic generate the
finite fitted policy class, while a forced best-fixed chain supplies the
regression anchor. Best fixed is the explicit comparator under custom CSM and
there is no additional CSM constraint.

For the documented one-modelpoint run with 4,200 Q paths and market seed 2026,
the custom-CSM selector chooses `base_csm`: custom CSM AUD 103,840.3807,
MLL-FPAR AUD 45,213.1339, secondary 6%-FPAR-penalised CSM AUD 101,127.5926 and
CSM/MLL-FPAR 2.2966862. The best fixed comparator is 0.25%, with custom CSM AUD
52,151.2701, MLL-FPAR AUD 25,057.4801, secondary penalised CSM AUD 50,647.8213
and CSM/MLL-FPAR 2.0812656. Both use the current curve and the same complete
sample. The primary flexibility uplift is AUD 51,689.1106 in custom CSM; the
secondary 6%-penalised sensitivity is AUD 50,479.7713.

The output is a present-value estimate of the contractual annual reset right,
not an operating policy. It includes the fixed grid, policy-class candidates,
primary custom-CSM and secondary MLL-FPAR metrics, Time-0 action-cell and
regression diagnostics, comparison table, manifest and plots. The current
one-modelpoint result and limitations are documented in
[`crediting_rate_profitability_and_capital.md`](crediting_rate_profitability_and_capital.md).

## Run directories and provenance

Generated outputs belong under `results/runs/<workflow>/`. Workflows that may
be rerun create UTC timestamp subdirectories and do not overwrite completed
runs. Large generated results and caches are ignored by Git.

Every documented run should retain:

- source/model version and input hashes;
- market- and hedge-cache keys/fingerprints;
- path counts, active seed namespaces and horizon;
- cap grid, behaviour mode, action set and stress definition;
- sample semantics and whether any OOS validation/evaluation was used;
- the fitted candidate label and, only where the workflow deploys a policy, the
  deployed-policy label;
- aggregation basis and custom-CSM reconciliation;
- runtime status and logs.

`results/document_figures/` is reserved for a small set of reviewed figures
promoted from completed runs. A promoted figure should have a nearby documented
provenance link to its completed run manifest and must not be copied from a
smoke, interrupted, rejected or source-mismatched run. The current curated
Dynamic Time-0 study preserves the completed fit manifest, uses custom CSM as
the primary selector and documents the $\lambda=6\%$ MLL-FPAR penalty
separately as a secondary sensitivity; it is not labelled as a deployment run.
The current base-only customer-LSMC diagnostic uses one model point (`ALT4-01`),
20,000 common paths, market seed 12026 and Caps 0.25%, 0.5%, 1%, 2%, 4%, 6%, 8%
and 12%. Every displayed cell directly deploys a structurally valid V11 rule;
no separate policy-selection test or fixed-rule substitution is used. Time-zero
customer optionality relative to the best fixed START-plus-CONTINUE reference
is zero through 2%, AUD 34.06 at 4%, AUD 3,684.45 at 6%, AUD 13,426.51 at 8%
and AUD 66,949.93 at 12%. Because the analysis contains one example insured
person, it is method evidence and a design sensitivity, not portfolio evidence
or regulatory capital.

## Quick workflows

Install from the repository root:

```powershell
python -m pip install -e ".[test]"
```

Run the customer-LSMC base cap/behaviour comparison; exact missing
caches are prepared first:

```powershell
portfolio-risk-analysis --model-points input_data/model_points_policyholders/model_points_policyholders_1_point_proxy.csv --crediting-rates 0.25% 0.5% 1% 2% 4% 6% 8% 12% --n-train 20000 --market-cache-root AGILE_Modelling_Engine/portfolio_simulations/cache/q_market_paths --hedge-cache-root AGILE_Modelling_Engine/portfolio_simulations/cache/q_hedge_prices --no-stress-analysis --require-market-cache --require-hedge-cache
```

Add the standard market/longevity shock set explicitly:

```powershell
portfolio-risk-analysis --model-points input_data/model_points_policyholders/model_points_policyholders_1_point_proxy.csv --crediting-rates 0.25% 0.5% 1% 2% 4% 6% 8% 12% --market-cache-root AGILE_Modelling_Engine/portfolio_simulations/cache/q_market_paths --hedge-cache-root AGILE_Modelling_Engine/portfolio_simulations/cache/q_hedge_prices --stress-analysis --stress-scenarios interest_up interest_down longevity --require-market-cache --require-hedge-cache
```

Run the Dynamic-only mortality/longevity/lapse MLL-FPAR comparison without
triggering Policyholder LSMC:

```powershell
crediting-future-profit-risk-analysis --model-points input_data/model_points_policyholders/model_points_policyholders_1_point_proxy.csv --cap-grid 0.0025,0.01,0.06,0.12 --baseline-cap 0.06
```

`crediting-capital-analysis` remains an equivalent legacy command name. Its
name does not change the output classification: the result is MLL-FPAR, not
regulatory capital.

Run either cap-management family through its prepare-then-read console command:

```powershell
optimise-crediting-dynamic --model-points input_data/model_points_policyholders/model_points_policyholders_1_point_proxy.csv --n-paths 4200 --seed 2026 --require-market-cache --require-hedge-cache
optimise-crediting-lsmc --model-points input_data/model_points_policyholders/model_points_policyholders_1_point_proxy.csv
```

Those commands derive every required cache identity from the forwarded
optimiser arguments. Direct execution of
`optimize_crediting_rate_dynamic_behaviour_alt.py` or
`optimize_crediting_rate_bellman.py` does not prepare caches.

Manual cache preparation is appropriate only when the exact specification is
known. The precompute interface requires the exact horizon, paths, seed and cap
grid:

```powershell
precompute-q-cache --horizon-years 53 --n-paths 2000 --seed 2026 --cap-grid "0.06"
```

The numbers in that one-cap command are an example for one specification, not
a universal cache. A reader will reject it if any required identity field
differs.

## Evidence checklist

Before interpreting or promoting a result, confirm that:

1. the run completed and its source hash matches the code being described;
2. every Q and `mc_conditional` hedge input came from an exact validated cache;
3. the four custom-CSM legs reconcile to the reported signed objective;
4. the portfolio aggregation reconciliation is within tolerance;
5. the Dynamic and customer-LSMC comparison uses the recorded common sample;
6. direct V11 deployment, structural validity and the absence of external
   policy selection or fixed-rule substitution are recorded;
7. the Dynamic Management-LSMC output records one modelpoint, one complete
   Time-0 Q sample, primary custom-CSM selection, secondary
   $\mathrm{CSM}-0.06\,\mathrm{MLL\mbox{-}FPAR}$ and CSM/MLL-FPAR reporting,
   and no OOS, forward roll or deployment output;
8. Monte Carlo uncertainty and the proxy/non-regulatory boundaries are stated;
9. any promoted chart carries the run and cache provenance needed to reproduce
   it.
