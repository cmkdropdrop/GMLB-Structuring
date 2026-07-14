# Input Data Reference

## Principle

All operative defaults live under `input_data/`. No user-specific absolute path
is required. The loaders validate schemas, units, ranges and identifiers and
retain file hashes for run provenance.

## Directory map

| Directory | Files | Use |
|---|---|---|
| `market_data/` | `australian_zero_curve.csv`, `model_parameters.csv` | The only live market-data inputs |
| `cost_assumptions/` | `cost_assumptions.csv` | Customer charges, insurer expenses, option markup and hedge-reference fee |
| `dynamic_behaviour/` | `dynamic_behaviour_baselines.csv`, `dynamic_behaviour_coefficients.csv` | Statistical take-up, lapse and withdrawal proxy |
| `equity_allocation/` | `equity_allocation.csv` | Product-level reference-fund equity weight |
| `mc_analysis/` | `portfolio_analysis.csv` | Named Monte Carlo path counts and seed namespaces used by the different workflows |
| `model_points_policyholders/` | full, four-point and one-point CSVs | Representative insured-person portfolios |

## Market data

The Australian zero curve is the only market series read on every run.
`model_parameters.csv` contains the already supplied equity volatilities,
correlations, Heston/Hull–White parameters and real-world equity risk premia.
The baseline does not request extra price histories, volatility surfaces,
credit-spread curves or calibration files.

Q valuation uses Heston–Hull–White. Simplified real-world projections use
Black–Scholes–Hull–White under `Measure.REAL_WORLD`. In that physical baseline,
the equity drift is risk-free drift plus the supplied equity risk premium and
P/Q rate dynamics are identical because no separate term premium is introduced.

## Reference-fund allocation

`equity_allocation.csv` defines `generic_reference_fund` with 30% equity. The
70% bond share is always derived as one minus the equity weight. This file is a
product input, not a market calibration.

## Cost assumptions

The base set includes customer charges and insurer expenses required by the
case study. Of particular importance:

- option fair-value markup: 0.50% of the fair option-package value;
- hedge-reference management fee: 0.30% per year of hedge notional;
- acquisition and maintenance-expense proxies;
- MVA proxy parameters.

The markup is relative to option fair value, not 50 basis points of notional.
The hedge-reference fee belongs to insurer hedge cost and does not reduce the
customer reference-fund return.

## Behaviour assumptions

Behaviour inputs distinguish contractual constraints from uncalibrated proxy
parameters. Coefficients are used in transparent link functions and include
moneyness/performance terms. They are intended to resemble common dynamic
behaviour modelling practice, but they are not Australian experience rates.

## Monte Carlo samples

`portfolio_analysis.csv` retains disjoint random-number namespaces for workflows
that require separate policy selection and evaluation, in particular adaptive
insurer cap optimisation:

- final evaluation;
- up to three LSMC training samples;
- held-out LSMC validation.

Market, take-up and mortality seeds remain separate. Changing a market seed or
path count requires a distinct Q-market cache; changing non-market mortality or
expense assumptions does not.

The customer-behaviour LSMC is intentionally different. It uses only the
primary LSMC training row as one common exact Q sample for continuation-value
fitting, direct V11 rollout and the paired Dynamic comparison. Legacy
validation/evaluation arguments remain parseable for compatibility but are
normalised to that primary sample; they do not create an OOS gate. Customer-LSMC
runs also require exactly one model point.

## Model-point sets

| File | Intended use |
|---|---|
| `model_points_policyholders.csv` | Full 48-point illustrative portfolio for evidence runs |
| `model_points_policyholders_4_point_proxy.csv` | Small portfolio for development and medium runs |
| `model_points_policyholders_1_point_proxy.csv` | Required representative contract for customer-LSMC runs and fast orchestration checks |

The one-point proxy must not be described as portfolio evidence, even when many
market paths are used. It supports method and product-design sensitivity only.
A model point represents an insured person; `contract_weight` and
`premium_volume_weight` control aggregation.

## Clone-and-run guarantee

Every required CSV in `input_data/` is versioned. Paths are exported from
[`repository_paths.py`](../code/policy_engine/repository_paths.py), so moving or
cloning the repository does not require path edits.
