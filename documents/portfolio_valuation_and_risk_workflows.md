# Portfolio Valuation and Risk Workflows

## Purpose

The portfolio workflows connect portable inputs, exact market scenarios, the
monthly product projector, policyholder behaviour, CSM components and
shock-and-revalue analysis. The central design rule is separation of duties:

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
| `mc_analysis/` | Predeclared evaluation, LSMC training and validation samples |
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
chosen explicitly and labelled as a proxy; it is never an automatic fallback.

## Orchestrated cache preparation

[`run_portfolio_risk_analysis.py`](../code/portfolio_simulations/run_portfolio_risk_analysis.py)
is the recommended end-to-end fixed-cap and risk orchestrator. Before any
reader child starts, it resolves the portfolio horizon and enumerates every
required combination of:

- sample role, path count and market seed;
- base or market-stress variant;
- model settings and Heston substeps;
- product allocation and requested caps.

It then invokes the authorised precompute runner for those exact jobs. The
precompute runner validates reusable entries and computes only missing ones.
Only after successful preflight does the orchestrator launch the Dynamic and
LSMC read-only valuation children.

[`run_crediting_rate_optimisation.py`](../code/portfolio_simulations/run_crediting_rate_optimisation.py)
provides the equivalent boundary for adaptive-cap research. The installed
`optimise-crediting-dynamic` and `optimise-crediting-lsmc` commands first parse
the selected optimiser configuration, derive the exact portfolio horizon and
enumerate its training and independent benchmark path-count/seed pairs. The
orchestrator invokes the sole authorised precompute runner for each exact
sample. With `mc_conditional`, it supplies the complete optimiser cap grid and
prepares the congruent hedge cache; with explicitly selected
`moment_matched_bs`, it prepares the market cache only. It then launches the
strict optimiser reader in a separate process with the cache requirements
enforced; the LSMC route uses the Bellman wrapper that enforces LSMC
policyholder behaviour.

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
| Income | Annual anniversary | Continue; full withdrawal now |

Partial withdrawal and under-year voluntary actions are excluded from this
optimal action set. Fits use whole-path folds. Training, held-out validation and
final evaluation use distinct predeclared sample namespaces. A rejected
candidate is replaced in the actual final rollout by its recorded fixed
validation baseline.

In addition to the standard valuation outputs, the runner writes policyholder
action summaries, regression diagnostics, validation manifests and comparison
tables. Reports must distinguish the fitted candidate from the policy actually
deployed.

## Fixed-cap and behaviour-risk analysis

The risk orchestrator runs Dynamic and deployed LSMC policies for every
requested cap on common final-evaluation market scenarios. The base workflow
focuses on cap and lapse/behaviour exposure. The default cap grid is 4%, 6%, 12%
and 15%; only 6% is the contractual base case.

Optional `--stress-analysis` expands the grid to requested one-factor stresses.
For market stresses, the full stressed Q scenario and hedge caches are prepared
and read. For mortality, longevity or expense stresses, the base market cache
is reused and the non-market assumption is changed in the projection. Permanent
lapse stresses are available only in the separate Dynamic-only capital workflow
below, not in this Dynamic-plus-LSMC orchestrator.

The workflow reports, among other items:

- CSM proxy and its Fee Income, Other Income, Claims and Costs legs;
- guarantee claims, option cost and money-market backing income;
- election timing, phase exposure and voluntary-action diagnostics;
- Dynamic-versus-deployed-LSMC differences;
- cap secants and one-factor shock-and-revalue changes;
- model-point contribution and concentration diagnostics.

Its retained outputs are expected present values and model-point scalars, not a
pathwise shareholder-loss distribution. Therefore the workflow does **not**
produce VaR, TVaR/CTE, APRA LAGIC capital or a complete IFRS 17 Risk Adjustment.
Calling model-point dispersion a tail-loss distribution is incorrect.

When behaviour is refitted under stress, the result includes behavioural
adaptation to the stressed environment. It is not the sensitivity of one frozen
behaviour policy. The run manifest records the interpretation.

## Dynamic-only capital-adjusted fixed-cap analysis

[`run_crediting_rate_capital_analysis.py`](../code/portfolio_simulations/run_crediting_rate_capital_analysis.py)
is the dedicated route when Policyholder LSMC must not run. It hard-gates every
valuation child to `run_portfolio_valuation.py`, Dynamic election and Dynamic
post-Income behaviour, and exact required market and hedge caches. For every
fixed cap it runs common-random-number revaluations for base, mortality,
longevity, permanent lapse-up and permanent lapse-down assumptions.

The resulting mortality/longevity/lapse capital is a partial research proxy,
not APRA LAGIC capital or a complete Solvency II SCR. Mortality and longevity
losses use permanent 15% and -20% mortality-rate shocks. The lapse module takes
the largest adverse permanent 50% up/down shock and a separately disclosed 40%
mass-lapse proxy on positive model-point CSM; the three modules are then
aggregated with the documented life-risk correlation matrix. The primary
selection measure is

$\mathrm{CSM}^{\text{capital-adjusted}}=\mathrm{CSM}-hK_{\mathrm{MLL}}$.

This evaluates a fixed product-design choice. It does not establish that an
annually adaptive discretionary cap rule has value. Outputs include the full
stress revaluation table, capital table, run manifest and three diagnostic
figures under `results/runs/crediting_rate_capital_analysis/`.

## Run directories and provenance

Generated outputs belong under `results/runs/<workflow>/`. Workflows that may
be rerun create UTC timestamp subdirectories and do not overwrite completed
runs. Large generated results and caches are ignored by Git.

Every evidence-quality run should retain:

- source/model version and input hashes;
- market- and hedge-cache keys/fingerprints;
- path counts, all seed namespaces and horizon;
- cap grid, behaviour mode, action set and stress definition;
- training/validation/evaluation separation;
- candidate, validation decision and deployed-policy label;
- aggregation basis and CSM reconciliation;
- runtime status and logs.

`results/document_figures/` is reserved for a small set of reviewed figures
promoted from completed runs. A promoted figure should have a nearby documented
provenance link to its completed run manifest and must not be copied from a
smoke, interrupted, rejected or source-mismatched run. The curated Dynamic-
behaviour cap study records a completed current-source optimisation run.
Completed base-only portfolio-risk run `20260714T002637.233689Z` supplies the
separate four-model-point cap and behaviour comparison. It uses 1,000 evaluation
paths, 4,000 LSMC training paths, 1,000 LSMC validation paths and one training
seed per cap. All four V11 candidates were rejected, so every published LSMC
series is explicitly the validated deployed fallback. The run did not execute a
market, longevity, expense or mortality stress grid; its exposure ratios are
development sensitivities rather than regulatory capital. Curated hashes and
compact source tables are under `results/document_figures/`.

## Quick workflows

Install from the repository root:

```powershell
python -m pip install -e ".[test]"
```

Run the recommended four-point base cap/behaviour comparison; exact missing
caches are prepared first:

```powershell
portfolio-risk-analysis --model-points input_data/model_points_policyholders/model_points_policyholders_4_point_proxy.csv --crediting-rates 4% 6% 12% 15% --require-market-cache --require-hedge-cache
```

Add the standard market/longevity shock set explicitly:

```powershell
portfolio-risk-analysis --model-points input_data/model_points_policyholders/model_points_policyholders_4_point_proxy.csv --crediting-rates 4% 6% 12% 15% --stress-analysis --stress-scenarios interest_up interest_down longevity --require-market-cache --require-hedge-cache
```

Run the Dynamic-only mortality/longevity/lapse capital comparison without
triggering Policyholder LSMC:

```powershell
crediting-capital-analysis --model-points input_data/model_points_policyholders/model_points_policyholders_4_point_proxy.csv --cap-grid 0.0025,0.01,0.06,0.12 --baseline-cap 0.06
```

Run either adaptive-cap family through its prepare-then-read console command:

```powershell
optimise-crediting-dynamic --model-points input_data/model_points_policyholders/model_points_policyholders_4_point_proxy.csv
optimise-crediting-lsmc --model-points input_data/model_points_policyholders/model_points_policyholders_4_point_proxy.csv
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
3. the four CSM legs reconcile to the reported signed objective;
4. the portfolio aggregation reconciliation is within tolerance;
5. the Dynamic and LSMC comparison uses common final scenarios;
6. the reported LSMC label is the policy actually deployed after validation;
7. the final sample was not used for policy or hyperparameter selection;
8. Monte Carlo uncertainty and the proxy/non-regulatory boundaries are stated;
9. any promoted chart carries the run and cache provenance needed to reproduce
   it.
