# Script Reference

## Public command-line entry points

An editable install from the repository root exposes six command names through
[`pyproject.toml`](../pyproject.toml). One of them is a legacy alias, so these
represent five workflow families:

| Command | Implementation | Intended use |
|---|---|---|
| `precompute-q-cache` | [`precompute_q_market_and_hedge_cache.py`](../code/portfolio_simulations/precompute_q_market_and_hedge_cache.py) | Create or validate exact Q-market and conditional-MC hedge caches |
| `portfolio-risk-analysis` | [`run_portfolio_risk_analysis.py`](../code/portfolio_simulations/run_portfolio_risk_analysis.py) | Recommended end-to-end cap, behaviour and optional stress workflow |
| `crediting-future-profit-risk-analysis` | [`run_crediting_rate_capital_analysis.py`](../code/portfolio_simulations/run_crediting_rate_capital_analysis.py) | Dynamic-only fixed-cap MLL-FPAR research study |
| `crediting-capital-analysis` | [`run_crediting_rate_capital_analysis.py`](../code/portfolio_simulations/run_crediting_rate_capital_analysis.py) | Legacy alias for `crediting-future-profit-risk-analysis`; not a regulatory-capital calculation |
| `optimise-crediting-dynamic` | [`run_crediting_rate_optimisation.py`](../code/portfolio_simulations/run_crediting_rate_optimisation.py) | Prepare exact caches, then run the strict one-modelpoint Dynamic Time-0 custom-CSM reader with secondary MLL-FPAR diagnostics |
| `optimise-crediting-lsmc` | [`run_crediting_rate_optimisation.py`](../code/portfolio_simulations/run_crediting_rate_optimisation.py) | Prepare exact caches, then run the strict combined LSMC-policyholder optimiser |

Use `python -m pip install -e ".[test]"` once from the repository root. Direct
file execution is supported, but direct optimiser files remain strict cache
readers. The installed optimisation commands add the authorised cache-preflight
layer as well as making repository paths and package imports clearer.

## Core workflow scripts

### `precompute_q_market_and_hedge_cache.py`

This is the **only** script authorised to write
`results/cache/q_market_paths` or `results/cache/q_hedge_prices`.

Required run-specific inputs include `--horizon-years` and `--n-paths`; seed,
substeps, market stress, cap grid, allocation and cache roots are explicit or
portable defaults. The runner first validates an exact existing market entry,
creates it only when missing, and then does the same for the path-congruent
hedge surface. `--market-only` deliberately skips hedge preparation.

It does not choose approximate matches and does not overwrite a valid exact
entry. With `--market-only`, it prepares no conditional-MC hedge surface; this
is the appropriate cache boundary when a reader explicitly selects the labelled
`moment_matched_bs` pricing proxy.

### `run_crediting_rate_optimisation.py`

This is the prepare-then-read orchestrator behind both installed optimisation
commands. It parses the selected optimiser's arguments, resolves the model-point
horizon and enumerates the exact samples required by that family. The Dynamic
Time-0 route hard-requires one modelpoint and one complete Q sample; the
Customer-LSMC route retains its separately declared sample roles. For every
distinct path-count/market-seed pair it invokes
`precompute_q_market_and_hedge_cache.py` with the same market inputs, substeps,
cache roots and horizon. With `mc_conditional`, it also supplies the optimiser's
complete cap grid so that the path-congruent hedge surface has the exact
required identity. With explicitly selected `moment_matched_bs`, it requests
only the exact market cache.

The precompute process validates reusable entries and creates only missing
ones. After every cache job succeeds, the orchestrator starts the requested
optimiser in a separate process and enforces `--require-market-cache`; for
`mc_conditional` it also enforces `--require-hedge-cache`. The optimiser itself
never gains cache-write authority. The LSMC command is dispatched through the
Bellman wrapper so that LSMC policyholder behaviour is enforced.

### `run_portfolio_valuation.py`

This is the read-only market-consistent portfolio valuation with statistical
dynamic behaviour. It values every model point on a shared Q scenario set and
aggregates with `contract_weight`.

Important options include:

- model-point, cost, behaviour and market input paths;
- evaluation path count and market/take-up/mortality seeds;
- fixed `--crediting-cap-rate` design override;
- `--hedge-pricing-method` and hedge cap-leg mode;
- market/non-market stress choice;
- optional absolute portfolio contract count and fair-fee calculation;
- output/log/plot controls.

The exact Q market cache is always required. With `mc_conditional`, the exact
hedge cache is also required. Principal outputs are model-point results,
portfolio summary, aggregation reconciliation, run manifest, log and optional
figures.

### `run_crediting_rate_capital_analysis.py`

This is the prepare-then-read Dynamic-only MLL future-profit-at-risk
orchestrator behind the canonical `crediting-future-profit-risk-analysis`
command. For every cap it invokes the authorised precompute runner to validate
or create only the exact required base market and hedge caches, then launches
`run_portfolio_valuation.py` for base, mortality, longevity, lapse-up and
lapse-down revaluations. Non-market stresses must preserve the base cache keys.

The command hard-codes dynamic Income Election and post-Election behaviour and
rejects any child output with `lsmc_used=true`. It never calls
`run_portfolio_valuation_lsmc.py`. Outputs include the reconciled stressed
custom-CSM values, stand-alone future-profit losses, permanent and approximate
mass-lapse amounts, correlated MLL-FPAR, FPAR-penalised CSM sensitivity,
CSM/MLL-FPAR ratio, selection result, manifest and plots.

The default and primary ranking is custom CSM. The explicit
`--objective fpar_penalised_csm` and `--objective csm_to_fpar` choices rank by
secondary research sensitivities instead. The dimensionless 6% factor in the
first sensitivity is an FPAR penalty weight, not a capital charge,
cost-of-capital rate or full Risk Margin. The MLL-FPAR amount is partial and
the mass-lapse leg is a model-point positive-value proxy rather than a
revaluation. `crediting-capital-analysis`, the old option names and
capital-named output columns remain compatibility aliases only.

The runner must not be used or described as an APRA capital calculation. APRA's
actual boundary is set out in [LPS 115](https://www.apra.gov.au/standards/lps-115)
for the Insurance Risk Charge, [LPS 112](https://www.apra.gov.au/standards/lps-112)
for adjusted policy liabilities and capital base, and
[LPS 110](https://www.apra.gov.au/standards/lps-110) for the prescribed-capital
and Prudential Capital Requirement framework. The runner also does not
calculate an IFRS 17 CSM; its custom CSM is a repository profitability proxy.

### `run_portfolio_valuation_lsmc.py`

This is the read-only portfolio valuation with the combined policyholder LSMC.
It fits annual Growth `WAIT`/`START_NORMAL_INCOME` and annual Income normal
Scheduled Income plus `CONTINUE`/`FULL_SURRENDER` decisions. The implementation
retains the internal transition labels `START_INCOME_NOW` and
`FULL_WITHDRAWAL_NOW`. Partial withdrawal is not part of the current optimal
action set. It requires exactly one model point.

The customer objective is the Q-expectation of income, surrender and finite
terminal-closeout cashflows discounted by today's Australian zero curve. The
fit contains no mortality or death benefit; configured mortality is restored
for actuarial and custom-CSM rollout. Whole-path cross-fitting estimates
continuation values inside one exact Q sample. The V11 rule is deployed directly on that
same sample: there is no separate validation/evaluation sample, policy-selection
gate, RMSE exercise buffer or fixed-policy substitution. Legacy sample flags
remain parseable
but are normalised to `--n-train` and the active training seeds.

The runner writes regression/action diagnostics, same-sample comparisons and
explicit `oos_validation_used=false` / `oos_evaluation_used=false` manifest
fields. A paired Dynamic benchmark is produced by default unless disabled.

Use this runner directly when one fixed cap and detailed LSMC diagnostics are
the subject. Use the risk orchestrator for a multi-cap comparison with automatic
cache preparation.

### `run_portfolio_risk_analysis.py`

This is the primary portfolio orchestrator. For each cap and optional stress it:

1. resolves the single exact training-and-valuation sample;
2. invokes the authorised precompute runner for missing exact Q/hedge entries;
3. runs Dynamic and LSMC valuations serially within each cap/stress pair;
4. schedules independent pairs with bounded worker/BLAS concurrency;
5. validates source, cache, sample and aggregation consistency;
6. writes aggregate CSV, manifest, report and optional plots to a new timestamped
   run directory.

The default is a base-only 4%, 6%, 12% and 15% cap comparison on the one-point
proxy with one worker. The runner rejects multi-model-point input for the
customer-LSMC workflow. Such output is an illustrative method/design
sensitivity, not evidence about the full 48-point portfolio.
`--stress-analysis` is required to add the selected shock-and-revalue grid.

The outputs are expected values and model-point diagnostics, not a pathwise
loss distribution or regulatory capital calculation.

### `optimize_crediting_rate_dynamic_behaviour_alt.py`

This is the strict cache-reader implementation used by the canonical
Dynamic-behaviour cap command. It values today the insurer's right to reset the
annual cap under statistical Dynamic Policyholder behaviour. It hard-requires
exactly one modelpoint and never calls Customer LSMC. Future cashflows are
risk-neutral expected values discounted to Time 0 with the current curve.

The gas-storage formulation uses account value per initial premium as an
endogenous inventory grid. Node continuation fits use an intercept, ATM
one-year call value, reference-fund level and overnight rate. Each action-Q
target is the realised annual 14-value Base/Stress custom-CSM payload plus the
next value interpolated at that same path's realised next account value. The
six-column action basis adds account value and squared account value.

Because MLL-FPAR is non-additive, the runner fits 21 predeclared additive
Base/Stress support policies plus one conditional-ratio heuristic, then ranks
the finished fixed-anchored payloads on the primary Time-0 custom-CSM score.
$\mathrm{CSM}-0.06\,R_{\mathrm{MLL}}$ and CSM/MLL-FPAR are secondary reported
sensitivities and do not select the policy. There is no additional CSM
constraint; best fixed is the explicit comparator under custom CSM. One
complete Q sample is shared by fitting, candidate ranking and fixed caps; no
OOS sample, forward roll, deployment gate or future policy schedule is
produced.

The standard hedge is the sold bull call spread. The current cap affects
statistical behaviour through account value, guarantee moneyness and realised
performance history; it is not inserted as an undocumented direct lapse
coefficient.

### `optimize_crediting_rate_bellman.py`

This small strict cache-reader entry point enforces LSMC policyholder behaviour
and delegates to
[`optimize_crediting_rate_lsmc.py`](../code/portfolio_simulations/optimize_crediting_rate_lsmc.py).
Use the wrapper when the policyholder response must be LSMC; use the
implementation module only for advanced research configuration.

The implementation fits an ordered policyholder follower and an insurer cap
leader. Its fast default screens a coarse cap grid, then performs fresh
cap-specific follower fits for selected fixed-cap finalists. The full action
grid and broader comparators are opt-in.

The cap-randomised adaptive response surface is currently diagnostic only. Code
blocks its deployment until joint leader/follower on-policy iteration and the
complete three-seed component validation contract are implemented. A reported
deployed result is therefore the validated fixed-cap follower, not the raw
adaptive response-surface candidate.

## Internal files

[`optimize_crediting_rate_lsmc.py`](../code/portfolio_simulations/optimize_crediting_rate_lsmc.py)
is active because the public Bellman entry point delegates to it, but it is an
advanced implementation module rather than a separate recommended workflow.

Files beginning with `_` are implementation helpers, not public commands:

- `_mc_analysis_inputs.py` strictly loads the predeclared Monte Carlo sample
  table;
- `_run_layout.py` centralises child output-directory conventions;
- `_run_logging.py` provides consistent console/log formatting.

## Which script should I use?

| Question | Start here |
|---|---|
| One fixed cap with statistical Dynamic behaviour | `run_portfolio_valuation.py` |
| One fixed cap with direct optimal-policyholder diagnostics | `run_portfolio_valuation_lsmc.py` |
| Dynamic versus direct LSMC V11 across caps and optional stresses | `portfolio-risk-analysis` |
| Fixed caps under Dynamic mortality/longevity/lapse MLL-FPAR | `crediting-future-profit-risk-analysis` |
| Time-0 custom-CSM value of annual cap flexibility under statistical Dynamic behaviour, with 6%-FPAR penalty and CSM/MLL-FPAR reported secondarily | `optimise-crediting-dynamic` |
| LSMC-follower cap research | `optimise-crediting-lsmc` |
| Prepare one known exact cache specification | `precompute-q-cache` |
| Debug an optimiser against already prepared exact caches | Direct optimiser implementation file |

## Common execution rules

1. Run from a cloned repository without editing absolute paths; portable defaults
   come from `repository_paths.py`.
2. Prefer the installed optimisation commands when missing exact caches may
   need preparation; direct optimiser files are readers only.
3. For Q valuation, never bypass exact market-cache validation.
4. For `mc_conditional`, never omit the congruent hedge cache or replace it with
   an implicit Black–Scholes estimate.
5. For Dynamic-customer Management LSMC, use exactly one modelpoint and the one
   complete Time-0 sample recorded in the manifest; do not reinterpret its
   action-cell diagnostics as a deployment rule.
6. For the separate Customer-LSMC/Stackelberg route, follow its own declared
   sample and deployment restrictions.
7. Check the custom-CSM and portfolio aggregation reconciliations before
   interpreting a result; do not reinterpret custom CSM as IFRS 17 CSM or
   MLL-FPAR as required capital.
8. Treat one-point customer-LSMC runs as method/design sensitivities, not
   portfolio evidence, regardless of path count.
9. Promote a figure to `results/document_figures/` only from a completed,
   current-source, provenance-backed run.

For full workflow and cache semantics, see
[portfolio valuation and risk workflows](portfolio_valuation_and_risk_workflows.md).
For the control equations and validation gates, see
[crediting-rate optimisation](crediting_rate_optimisation.md).
