# Index-Linked Lifetime-Income Modelling Engine

Research valuation and projection engine for the independent Australian
index-linked lifetime-income case study described in
`../documentation_and_background_info/Produktdesign_Index_Linked_Lifetime_Income_Fallbeispiel.md`.
The case study is not a description of an offered insurance product and the
engine is not a production, accounting, tax, legal or regulatory-capital
system.

The Python package is still named `agile_engine` for repository compatibility.
The active product, however, is
`IndexLinkedLifetimeIncomeProduct`; AGILE-specific classes and functions that
remain in the package are legacy research compatibility only.

## Active product baseline

The active product is funded by one single premium and has two phases:

- **Growth:** the Account Value receives an annual protected credit. Income may
  first be elected at the first Policy Anniversary and only at anniversaries.
  Voluntary withdrawals, partial withdrawals, full surrender and lapse are not
  permitted in this phase.
- **Income:** Fixed Lifetime Income is paid monthly in arrears. The first
  instalment is due one month after election. Payments are funded from Account
  Value while it is available; only the shortfall is a Guarantee Claim. An
  Excess Withdrawal reduces future locked income proportionally. Full
  Withdrawal terminates the income guarantee.

There is no Rising Income, Age Pension+, adviser-service-fee option,
commencement bonus or customer-selected investment allocation in the generic
baseline. The Spouse option may continue the same fixed income to the last
survivor or follow the documented lump-sum death path.

### Contractual reference fund

The customer credit is linked to one synthetic Reference Fund. It is not a
unit-linked customer portfolio and it must not be confused with the insurer's
backing or hedge assets.

For insurer profitability, the administrative crediting frame is instead
backed by the stochastic AUD overnight money-market account. The under-year
DVA option mark remains a customer-liability value and is not treated as a
backing asset. The insurer buys an annual option package on the Reference Fund.
The standard package sells the cap call and retains no performance above the
cap; `--hedge-cap-leg-mode not_sold` keeps that leg and reports the excess
payoff as a separate hedge gain. Neither backing nor hedge cashflows alter
customer Account Value, credited return or Guarantee Claims.

- 50% Global Equity, treated as an AUD-denominated or AUD-hedged total-return
  index;
- 50% nominal Australian-government bonds, represented by a monthly rolling
  five-year zero-coupon-bond sleeve;
- monthly rebalancing back to 50/50;
- no credit spread, default, rating migration, inflation-linked bond, FX,
  transaction-cost or tactical-allocation model.

For month `m`, the engine first forms the complete simple fund return

```text
R_fund,m = 0.50 * R_global,m + 0.50 * R_bond,m
```

and compounds these monthly returns into the Reference Fund index. At the
Policy Anniversary, Total Protection is then applied once to the complete
annual fund return:

```text
credit_y = min(max(R_fund,y, 0), 0.06)
```

The Maximum Return is fixed at 6%. Floor and cap are never applied separately
to the equity and bond sleeves. The same Reference Fund remains in force in
Growth and Income.

### Fee subledger

The Product Fee and Lifetime Income Premium accrue on the positive
administrative Account-Value basis using ACT/365F. Accrual itself is not an
insurer cash inflow. Accrued amounts are posted only:

- after annual crediting at a Policy Anniversary;
- immediately before Full Withdrawal; or
- immediately before a terminating death benefit.

Collected fees are limited to available Account Value and split pro rata when
the balance is insufficient. No fee arrears are carried. Regular income and a
Partial/Excess Withdrawal are not fee-posting events.

## Market models and data

The default market-consistent valuation uses **Heston-Hull-White under the
risk-neutral measure**. The simplified Real-World projection uses
**Black-Scholes-Hull-White under `Measure.REAL_WORLD`**.

The Australian zero curve is the only market data source that is read on an
ongoing basis. Existing equity, Heston, Hull-White and dependence parameters
come from the versioned model-parameter file. No additional volatility surface,
credit-spread curve or physical calibration file is requested.

| Input | Repository path | Use |
| --- | --- | --- |
| Australian zero curve | `input_market_data/australian_zero_curve.csv` | initial curve, discounting and Hull-White fit |
| Market-model parameters | `input_market_data/model_parameters.csv` | equity, Heston, Hull-White and correlations |
| Cost assumptions | `../input_cost_assumptions/cost_assumptions.csv` | customer fees, expenses, MVA, hedge, capital and shareholder assumptions according to each row's status |
| Dynamic behaviour | `../input_dynamic_behaviour/dynamic_behaviour_baselines.csv` and `dynamic_behaviour_coefficients.csv` | versioned behavioural proxies |
| Policyholder model points | `../input_model_points_policyholders/model_points_policyholders_4_point_proxy.csv` | default four-point proxy for portfolio demographics, premiums, weights and elections; the 48-point file remains an explicit full-grid alternative |

The loaders validate schemas, units and identifiers and retain source paths,
assumption-set IDs and SHA-256 fingerprints. A loaded proxy does not become an
observed or calibrated assumption merely because it is present in a CSV.

Under the simplified Real-World baseline, Global Equity drift is the modelled
short rate plus the existing equity risk premium. The Hull-White rate dynamics
are the same under Real World and Risk Neutral: there is no bond term premium
and no separate market price of rate risk. This is a transparent fixed-proxy
projection, not a calibrated economic forecast.

## Portfolio valuation runner

The portfolio entry point is:

```text
portfolio_simulations/run_portfolio_valuation.py
```

With default paths it reads the repository model points and assumption files
listed above and writes to:

```text
portfolio_simulations/output/portfolio_valuation/
```

The output directory contains:

- `portfolio_summary.csv` -- normalised averages, optional absolute portfolio
  present values and control metrics;
- `model_point_results.csv` -- explicit per-contract, normalised-contribution
  and optional absolute-contribution results per model point;
- `portfolio_aggregation_reconciliation.csv` -- proof that model-point
  contributions reconcile to the reported aggregate;
- optional fair-fee diagnostics, a timestamped run log and PNG charts; and
- `run_manifest.json` -- input provenance, model settings, aggregation rules,
  generated outputs and proxy disclosures.

The portfolio valuation uses one shared risk-neutral scenario set, projects
model points sequentially and retains scalar results rather than full paths.
`contract_weight` is the valuation aggregation weight. `premium_volume_weight`
is a reconciliation control and is not applied a second time. Each source row
is valued independently before these weights are applied. Without an explicit
portfolio contract count or source `exposure_count`, only a portfolio
normalised to one representative contract is available; the runner does not
mislabel model-point source rows as individual policies.

Version 2.1 makes the aggregation basis explicit in the output schema. Former
unprefixed monetary summary fields are replaced by
`normalised_average_<metric>` and, when contract counts exist,
`portfolio_total_<metric>`. Model-point CSV fields analogously use
`per_contract_`, `normalised_contribution_` and `portfolio_contribution_`.

Default portfolio metrics include:

- present value of policyholder benefits;
- present value of future Product Fees and Lifetime Income Premiums;
- present value of Guarantee Claims, expenses, stochastic money-market income,
  optional retained hedge gain, fair option cost, 0.50% purchase markup, 0.30%
  hedge-reference management-fee cost and MVA retained;
- Non-Unit and Total Best Estimate Liability;
- insurer net present value and new-business margin before risk margin; and
- market-consistency and weight controls.

Optional model-point fee solves distinguish two different concepts:

- **fair LIP:** the Lifetime Income Premium for which `PV(Guarantee Claims) -
  PV(LIP) = 0`; and
- **commercial break-even LIP:** the Lifetime Income Premium for which insurer
  net present value before risk margin is zero, including the other modelled
  cashflow components.

These rates are model-implied diagnostics, not recommended customer charges.
A failed numerical bracket is reported as a status rather than silently
extrapolated.

Separate portfolio-level switches solve one common product fee directly against
the aggregated portfolio objective. Individual model-point Fair Fees are never
averaged to obtain that portfolio price.

## Installation and direct API use

```bash
pip install -e .
python portfolio_simulations/run_portfolio_valuation.py
python portfolio_simulations/run_portfolio_valuation.py --fair-lip --commercial-break-even-lip
```

The runner accepts explicit source overrides through `--model-points`,
`--cost-assumptions`, `--dynamic-behaviour`, `--zero-curve` and
`--model-parameters`; matching assumption-set selectors are available for cost
and behaviour inputs. Simulation controls are `--n-paths` (default 2,000),
`--seed` and `--heston-substeps`. `--portfolio-contract-count` changes the
normalised portfolio into an absolute contract-count scale (unless source
`exposure_count` already supplies it), `--output` changes the output directory,
and the `--fair-fee-*` arguments control the optional root brackets and
tolerance. Logging and headless plots are produced by default and can be
controlled with `--log-level` and `--no-plots`.

The same workflow is available through the package modules:

```python
from dataclasses import replace

from agile_engine.cost_assumptions import load_cost_assumptions
from agile_engine.dynamic_behaviour_assumptions import load_dynamic_behaviour_assumptions
from agile_engine.market_assumptions import load_market_assumptions
from agile_engine.model_points import load_policyholder_model_points
from agile_engine.mortality import MortalityTable
from agile_engine.portfolio import value_policyholder_portfolio
from agile_engine.pricing import ValuationSettings
from agile_engine.product import (
    FeeSpec,
    IndexLinkedLifetimeIncomeProduct,
    ReferenceFundSpec,
)
from agile_engine.projection import ProjectionConfig

market = load_market_assumptions()
base_product = IndexLinkedLifetimeIncomeProduct(
    reference_fund=ReferenceFundSpec(),
    fees=FeeSpec(lip_waived_in_income_phase_if_aps=False),
    dividend_yield={
        index: parameters.dividend_yield
        for index, parameters in market.esg.equity.items()
    },
)
portfolio_projection = ProjectionConfig(record_paths=False, heston_cos=False)
costs = load_cost_assumptions(
    product=base_product,
    projection=portfolio_projection,
)
loaded_behaviour = load_dynamic_behaviour_assumptions().behaviour
behaviour = loaded_behaviour
model_points = load_policyholder_model_points(
    expected_market_parameter_set_id=market.parameter_set_id,
    expected_yield_curve_id=market.curve_id,
)
settings = ValuationSettings(
    model="heston_hull_white",
    n_paths=2_000,
    seed=2026,
    heston_substeps=4,
    horizon_years=None,
    projection=costs.projection,
)

result = value_policyholder_portfolio(
    costs.product,
    model_points,
    market.esg,
    MortalityTable.gompertz_makeham(),
    behaviour,
    expenses=costs.expenses,
    settings=settings,
)
```

`MortalityTable.gompertz_makeham()` is an illustrative fallback. A governed
pricing basis should be supplied through `MortalityTable.from_qx(...)`.

## Package layout

| Module | Active purpose |
| --- | --- |
| `agile_engine/product.py` | generic product, fixed Reference Fund, fees, income rate card, MVA and policy validation |
| `agile_engine/esg.py` | BS/Heston/Hull-White scenarios, pathwise discounting, zero-bond and Reference-Fund construction, moment-matched fund volatility |
| `agile_engine/projection.py` | monthly Growth/Income state machine, full-fund crediting, event fee subledger, mortality, behaviour and cashflows |
| `agile_engine/model_points.py` | strict loading and generic mapping of the policyholder model-point CSV |
| `agile_engine/portfolio.py` | shared-scenario portfolio aggregation and optional model-point fair-fee solves |
| `agile_engine/pricing.py` | contract valuation and BEL decomposition |
| `agile_engine/market_assumptions.py` | Australian curve and market-parameter loader |
| `agile_engine/cost_assumptions.py` | cost loader and typed assumption overlay |
| `agile_engine/dynamic_behaviour_assumptions.py` | behaviour loader and provenance |
| `agile_engine/mortality.py` | mortality tables, improvements, stresses and joint-life functions |
| `agile_engine/profitability.py` | simplified Real-World profitability view |
| `agile_engine/capital.py` | non-APRA research capital proxy |

## Model boundaries

All results must be labelled as simplified projections or model-based
market-consistent values, as applicable. Material boundaries include:

- the five-year zero-coupon bond sleeve is a fixed proxy for nominal Australian
  government bonds;
- the Real-World rate model has no bond term premium or separate price of rate
  risk;
- Global Equity is treated as an AUD return index or fully AUD hedged;
- mortality uses a generational annual-`q_x` basis and the shipped
  Gompertz-Makeham table is illustrative, not a governed pricing table.
  Single-Life values use expected decrements. Portfolio Dynamic/LSMC runs and
  all V00/V01/V10/V11 factor arms sample separate Joint-Life status indicators
  from the same rates and mortality seed; only the standalone low-level
  deterministic API retains the historical expected-decrement fallback by
  default. Annual `q_x` is reconciled to twelve constant-force monthly
  decrements and terminated no later than age 115;
- dynamic behaviour schedules and coefficients are explicitly
  `uncalibrated_proxy`; contractual eligibility overrides them, so they cannot
  create Growth lapse or Growth withdrawals. Dynamic Take-up is evaluated
  only from current-Anniversary state. The model-point `income_start_year` is
  retained only for the explicit deterministic validation benchmark;
- state-dependent Joint-Life runs carry separate pathwise Primary/Spouse life
  statuses. Election and post-Election behaviour therefore act on the actual
  `p11`, `p10` or `p01` path state rather than on a nonlinear function of an
  averaged survivor state. The deterministic Election benchmark retains its
  former Election-date rule, while portfolio factor comparisons use the same
  pathwise mortality basis in every arm. Lives are independent;
  divorce/removal, common shocks and legal eligibility changes are not
  modelled;
- the intra-year DVA and hedge-package value use a Black-Scholes call-spread
  proxy with the complete Reference Fund volatility obtained by joint
  equity/Hull-White moment matching. This is not a calibration to mixed-fund
  option quotes and does not reproduce the full Heston distribution;
- insurer hedge cost is explicit: fair annual package value plus 0.50% of fair
  value and 0.30% p.a. of hedge notional. The former volatility-spread proxy is
  retained but zero in the standard cost CSV to avoid double counting;
- the Money-Market return is derived only from the simulated Hull-White
  overnight-rate integral and is applied to the administrative crediting frame
  at the monthly interval start. It never uses Reference-Fund performance or
  the under-year DVA option mark;
- annual hedge purchases are a conservative cash-cost proxy: no intra-year
  option unwind/recovery is booked after termination, and retained excess in
  `not_sold` is settled only on the active remaining notional;
- the statistical Dynamic portfolio path rejects COS and does not use LSMC.
  The separate optimal-behaviour runner trains a combined Income-Election and
  Full-Withdrawal policy on independent paths and freezes it for out-of-sample
  evaluation;
- current model-point loading supports the repository's duration-zero
  new-business Growth records, not a general in-force conversion;
- MVA, hedge execution, expenses, capital and shareholder values retain the
  source classifications and proxy limitations from their CSV rows;
- reinsurance, policyholder tax/withholding, adviser fees, systematic
  mortality, operational administration details and APRA/LAGIC capital are not
  calibrated parts of the baseline; and
- projection arrays are not a production-scale distributed portfolio engine.

## Legacy compatibility

`AgileProduct` is retained as an alias of the generic product class so older
imports do not fail immediately. Four AGILE investment-option enums, legacy cap
schedules, Partial-Protection/COS utilities, Age Pension+ structures, old
example runners and historical analysis outputs may also remain in the
repository. They do not define the active generic product and are not used by
the portfolio runner unless explicitly invoked by legacy research code.

The directories `tests/` and `../Code based on Papers/` are not runtime input
sources for the portfolio valuation.

See `METHODOLOGY.md` for equations, cashflow definitions and the precise proxy
interpretation.
