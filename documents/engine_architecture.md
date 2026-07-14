# Engine Architecture

## Design goals

The repository separates contractual mechanics, economic scenarios, behaviour,
valuation and orchestration. The calculation engine contains no machine-specific
paths: every default is resolved from
[`repository_paths.py`](../code/policy_engine/repository_paths.py).

The operative layers are:

| Layer | Location | Responsibility |
|---|---|---|
| Inputs | `input_data/` | Versioned market, product, cost, behaviour and model-point assumptions |
| Policy engine | `code/policy_engine/` | Reusable product, scenario, projection, valuation and behaviour logic |
| Workflows | `code/portfolio_simulations/` | Sole cache writer, prepare-then-read orchestrators, strict portfolio readers, risk analysis and cap optimisation |
| Tests | `tests/` | Unit, reconciliation, regression and orchestration contracts |
| Results | `results/` | Unversioned caches/runs plus curated versioned documentation figures |
| Documentation | `documents/` | Current English methodology and workflow descriptions |
| Archive | `old/` | Historical AGILE material, legacy reference copies and superseded runners |

## Policy-engine modules

| Module | Main role |
|---|---|
| `product.py` | Product parameters, fee and protection specifications, phases and policy state |
| `curves.py` | Zero curve, discount factors and forward rates |
| `market_assumptions.py` | Strict loader for the Australian curve and model parameters |
| `esg.py` | Black–Scholes, Heston and Hull–White scenario generation under Q or P |
| `scenario_cache.py` | Content-addressed Q-market cache specification, validation and I/O |
| `forward_start_hedge_pricing.py` | Path-congruent conditional-MC hedge-price surface |
| `crediting.py` | Protected-return payoff, DVA marks and analytic proxy pricing |
| `mortality.py` | Mortality, improvements, monthly conversion and joint-life functions |
| `behavior.py` | Statistical take-up, lapse and withdrawal functions |
| `dynamic_behaviour_assumptions.py` | Strict versioned behaviour-assumption loader |
| `optimal_behaviour_lsmc.py` | Combined growth-election and income-action LSMC policy |
| `projection.py` | Monthly contract and insurer-cashflow state machine |
| `pricing.py` | Q valuation and scenario resolution |
| `portfolio.py` | Model-point valuation and weighted aggregation |
| `portfolio_stresses.py` | Named market and non-market stress transforms |
| `profitability.py` | Real-world profitability projections and supporting metrics |
| `capital.py` | Research capital and risk-margin proxies |

## Dependency direction

The monthly projector consumes immutable product, mortality, behaviour and
scenario objects. Valuation modules call the projector; they do not reimplement
contract mechanics. Workflow scripts call public engine APIs and write
auditable manifests. Only the dedicated precompute workflow may write Q caches.

```text
input_data
    -> strict loaders
        -> scenario/product/behaviour objects
            -> monthly projection
                -> contract and portfolio valuation
                    -> risk analysis / cap optimisation
                        -> results and manifests
```

## Workflow authority boundaries

The workflow layer separates orchestration from numerical readers:

| Component | Cache authority |
|---|---|
| `precompute_q_market_and_hedge_cache.py` | Sole writer; validates exact entries and creates only missing market or hedge caches |
| `run_portfolio_risk_analysis.py` | Resolves all fixed-cap/stress cache jobs, invokes the sole writer, then starts read-only valuation children |
| `run_crediting_rate_optimisation.py` | Resolves each optimiser's horizon, samples, seeds and cap grid, invokes the sole writer, then starts the strict optimiser reader |
| Valuation and direct optimiser modules | Exact-cache readers only; they must fail on a missing or inconsistent required entry |

Market-cache identity follows market inputs, model, horizon, path count, seed,
substeps and market stress. A different product equity allocation or cap grid
requires a distinct conditional-MC hedge-cache entry but can reuse the matching
market cache. `mc_conditional` requires both exact cache layers;
`moment_matched_bs` is an explicit labelled proxy and requires only the exact
market paths. Neither mode gives a reader permission to write a cache.

## Portable installation

The root `pyproject.toml` uses a `code/` package layout and installs both
`policy_engine` and `portfolio_simulations`. Direct script execution is also
supported by a small local path bootstrap in the workflow files. The preferred
interface is module or console-script execution after an editable install from
a source checkout. Portability currently means cloning the repository and using
that editable installation: the repository-relative `input_data/` tree is not
bundled into a standalone wheel.

## State and cashflow separation

Customer account-value movements are kept distinct from insurer cashflows.
This prevents customer investment-component payments from being counted again
as insurance claims. The projector records, among other items:

- product and lifetime-income fees;
- money-market backing income and retained hedge gains;
- guarantee claims and other explicitly insurer-funded benefits;
- acquisition, maintenance and hedge costs;
- customer income, death, surrender and partial-withdrawal cashflows;
- in-force, phase, mortality and behaviour diagnostics.

The CSM proxy is reconstructed from the insurer legs and reconciled in every
material reporting workflow.

## Reproducibility

Run manifests bind numerical outputs to input hashes, model version, scenario
fingerprints, cache keys, path counts, seeds, horizon, stress and relevant
projection settings. CSV inputs use LF line endings through `.gitattributes`
because cache identities include exact input bytes.

Generated runs and large caches are ignored by Git. Small figures promoted into
`results/document_figures/` must include provenance linking them to a completed,
validated run.
