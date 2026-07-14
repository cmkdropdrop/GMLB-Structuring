# Script Reference

## Public command-line entry points

An editable install from the repository root exposes five commands through
[`pyproject.toml`](../pyproject.toml):

| Command | Implementation | Intended use |
|---|---|---|
| `precompute-q-cache` | [`precompute_q_market_and_hedge_cache.py`](../code/portfolio_simulations/precompute_q_market_and_hedge_cache.py) | Create or validate exact Q-market and conditional-MC hedge caches |
| `portfolio-risk-analysis` | [`run_portfolio_risk_analysis.py`](../code/portfolio_simulations/run_portfolio_risk_analysis.py) | Recommended end-to-end cap, behaviour and optional stress workflow |
| `crediting-capital-analysis` | [`run_crediting_rate_capital_analysis.py`](../code/portfolio_simulations/run_crediting_rate_capital_analysis.py) | Dynamic-only fixed-cap MLL capital and capital-adjusted profitability study |
| `optimise-crediting-dynamic` | [`run_crediting_rate_optimisation.py`](../code/portfolio_simulations/run_crediting_rate_optimisation.py) | Prepare exact caches, then run the strict Dynamic-policyholder optimiser |
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
horizon and enumerates the exact training and independent benchmark samples.
For every distinct path-count/market-seed pair it invokes
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

This is the prepare-then-read Dynamic-only capital orchestrator. For every cap
it invokes the authorised precompute runner to validate or create only the
exact required base market and hedge caches, then launches
`run_portfolio_valuation.py` for base, mortality, longevity, lapse-up and
lapse-down revaluations. Non-market stresses must preserve the base cache keys.

The command hard-codes dynamic Income Election and post-Election behaviour and
rejects any child output with `lsmc_used=true`. It never calls
`run_portfolio_valuation_lsmc.py`. Outputs include the reconciled stress CSMs,
stand-alone losses, permanent and approximate mass-lapse amounts, correlated
MLL life-risk capital proxy, capital-adjusted CSM, secondary CSM/capital ratio,
selection result, manifest and plots.

The default ranking is $\mathrm{CSM}-0.06K_{\mathrm{MLL}}$. This is a one-year research
capital charge, not a full Risk Margin. The MLL amount is partial and the
mass-lapse leg is a model-point positive-value proxy rather than a revaluation; the
runner must not be used or described as an APRA capital calculation.

### `run_portfolio_valuation_lsmc.py`

This is the read-only portfolio valuation with the combined policyholder LSMC.
It fits annual Growth `WAIT`/`START_INCOME_NOW` and annual Income
`CONTINUE`/`FULL_WITHDRAWAL_NOW` decisions. Partial withdrawal is not part of
the current optimal action set.

The runner has separate training, validation and final evaluation paths/seeds,
whole-path cross-fitting, ridge/exercise-buffer controls and optional multiple
training seeds. It writes regression/action diagnostics and records whether the
candidate or a valid fallback was actually deployed. A paired Dynamic benchmark
is produced by default unless explicitly disabled.

Use this runner directly when one fixed cap and detailed LSMC validation are the
subject. Use the risk orchestrator for a multi-cap comparison with automatic
cache preparation.

### `run_portfolio_risk_analysis.py`

This is the primary portfolio orchestrator. For each cap and optional stress it:

1. resolves exact evaluation, LSMC training and validation specifications;
2. invokes the authorised precompute runner for missing exact Q/hedge entries;
3. runs Dynamic and LSMC valuations serially within each cap/stress pair;
4. schedules independent pairs with bounded worker/BLAS concurrency;
5. validates source, cache, sample and aggregation consistency;
6. writes aggregate CSV, manifest, report and optional plots to a new timestamped
   run directory.

The default is a base-only 4%, 6%, 12% and 15% cap comparison on the four-point
proxy with one worker. The one-point file is reserved for explicit smoke tests,
while the full 48-point portfolio remains an explicit production-style choice.
`--stress-analysis` is required to add the selected shock-and-revalue grid.

The outputs are expected values and model-point diagnostics, not a pathwise
loss distribution or regulatory capital calculation.

### `optimize_crediting_rate_dynamic_behaviour_alt.py`

This is the strict cache-reader implementation used by the canonical
Dynamic-behaviour cap command. It uses a gas-storage LSMC formulation with
account value per initial premium as an endogenous inventory grid. Node
continuation fits use an intercept, ATM one-year call value, reference-fund
level and overnight rate. Each action-Q target is the realised annual CSM
components plus the next value interpolated at that same path's realised next
account value; no separate conditional-mean reward or transition regression is
used.

Action-Q fitting and frozen deployment use the identical compact six-column
basis: intercept, standardised ATM call, fund level, short rate, account value
and squared account value. There is no surrogate projection to a larger basis.
Complete market paths retain one immutable outer-fold assignment through the
full backward recursion, including scaling, inventory grids, continuation and
Q fits.

The workflow separates control-randomisation training, fixed-cap selection,
adaptive validation and final evaluation. The adaptive policy is deployed only
when its validation uplift is greater than 1.96 paired standard errors and all
operational diagnostics pass. Otherwise the fixed fallback is deployed and the
deployed flexibility value is zero.

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
| One fixed cap with detailed optimal-policyholder validation | `run_portfolio_valuation_lsmc.py` |
| Dynamic versus deployed LSMC across caps and optional stresses | `portfolio-risk-analysis` |
| Fixed caps under Dynamic mortality/longevity/lapse capital | `crediting-capital-analysis` |
| Adaptive cap under statistical Dynamic behaviour | `optimise-crediting-dynamic` |
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
5. Keep training, fixed selection, validation and final evaluation seeds
   distinct.
6. Read the deployed-policy fields, not only the candidate/Bellman fields.
7. Check the CSM and portfolio aggregation reconciliations before interpreting
   a result.
8. Treat one-point and small-path runs as smoke tests, not evidence.
9. Promote a figure to `results/document_figures/` only from a completed,
   current-source, provenance-backed run.

For full workflow and cache semantics, see
[portfolio valuation and risk workflows](portfolio_valuation_and_risk_workflows.md).
For the control equations and validation gates, see
[crediting-rate optimisation](crediting_rate_optimisation.md).
