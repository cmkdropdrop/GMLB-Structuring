# Curated documentation figures

Only small figures reviewed against a completed run manifest belong here.
Large run directories and Q caches remain generated local artefacts under
`results/runs/` and `results/cache/`.

## Current Time-0 CSM and MLL-FPAR flexibility study

The aggregate `time0_crediting_flexibility_csm_fpar` figure and the component
`time0_crediting_flexibility_csm_fpar_component_waterfalls` figure document the
`base_csm` alternative selected by completed full-grid run
`20260714T084838.270769Z`. Detailed payload recovery run
`20260714T151746.544341Z` used the same 4,200 cached Heston-Hull-White Q paths,
market seed 2026, current Australian curve and path-congruent market and hedge
caches. Only the fixed anchor and already selected `base_csm` chain were fitted;
the full 23-chain search was not repeated.

The corrected primary objective is CSM. The best fixed cap remains 0.25% with
CSM AUD 52,151.27; `base_csm` has CSM AUD 103,840.38, an uplift of AUD
51,689.11. The displayed MLL values are now explicitly MLL stressed-CSM
future-profit-at-risk proxies: AUD 25,057.48 fixed and AUD 45,213.13 flexible.
The 6%-penalised CSM sensitivity is AUD 50,647.82 and AUD 101,127.59,
respectively; it is secondary and does not select the policy.

The CSM waterfall attributes the uplift to all nine signed ledger components.
The largest favourable effects are money-market/hedge income (AUD 50,917.84)
and lower guarantee claims (AUD 33,763.91); the main offset is higher option and
hedge costs (AUD 39,444.33). The correlated MLL-FPAR waterfall uses an exact
three-module Shapley allocation: mortality AUD 0, longevity AUD 347.38 and
binding lapse AUD 19,808.27. The adjacent absolute-input panel shows mortality
0, longevity AUD 9,614.37/10,275.19 and binding lapse AUD
20,860.51/41,536.15. Mortality is zero because its signed CSM stress effect is
favourable and clipped before aggregation, not because of correlation. Mass
lapse binds at both endpoints.

This is a Time-0 in-sample profitability valuation, not a deployment study or
global optimum. `regulatory_capital_status` is `not_calculated`: MLL-FPAR is not
an APRA Insurance Risk Charge, Prescribed Capital Amount, Prudential Capital
Requirement, IFRS 17 CSM or Risk Adjustment. The correlation matrix and 6%
penalty are illustrative research assumptions, not APRA requirements.

Report-only run `20260714T163854.089093Z` generated the reviewed PNG/SVG files
and canonical CSVs in 2.1 seconds. Its manifest confirms
`market_cache_loaded=false`, `projection_run=false` and
`management_lsmc_fit=false`. The immutable report bundle is under
`source_data/time0_crediting_flexibility_fpar_report_20260714T163854.089093Z/`;
the original valuation source remains under
`source_data/time0_crediting_flexibility_20260714T151746.544341Z/`.

Promoted files and SHA-256 digests are:

- `time0_crediting_flexibility_csm_fpar.png`:
  `5cfd48b1a7957d8c096d87feec3970c2c6f185556f9b903a2704376e0d25d601`;
- `time0_crediting_flexibility_csm_fpar.svg`:
  `7927374e68e8c6844df4c3e0c7cdce6e4269fdca4981ef4ed209046adec22e95`;
- `time0_crediting_flexibility_csm_fpar_component_waterfalls.png`:
  `de53d4e8b0a974dcdb4a0ff40e1ed98f3644f52cd1416c47f83e4d163c61f033`;
- `time0_crediting_flexibility_csm_fpar_component_waterfalls.svg`:
  `1178ebc5c26bbf1a402cee8c3df56d0511b5461a68cbbb3e13e079d005af2c70`;
- canonical `time_zero_flexibility_comparison.csv`:
  `9448fe7d92f91d28abce7da872a346b687075ace2e5d87e2a7e718b6b55b9fcb`;
- canonical `time_zero_csm_component_comparison.csv`:
  `70301e067161079f523ebee4c54e890fe0e5d044e3938b419c972f241d0ac96b`;
- canonical `time_zero_mll_future_profit_risk_component_comparison.csv`:
  `2186a93cd158e51ed5b5e89684c2b2d3418de85fdf157a59c89d9cb844214825`;
- `report_manifest.json`:
  `f9e579d90bce7dbd757eecce06c39a3d7e3286bf73c1f2131ae07db33396502c`.

## Historical dynamic-behaviour OOS cap study

This earlier four-modelpoint study is retained for historical comparison. It is
superseded for README Section 7 and is not an input to the current one-modelpoint
same-sample Time-0 CSM/MLL-FPAR valuation.

The three `dynamic_*.png` figures are byte-for-byte copies from completed run
`20260713T233802.157326Z`. This is a four-model-point proxy study, not the full
48-point portfolio. It used 4,200 training paths and a distinct
1,260-path benchmark parent sample, split into independent 420-path fixed-cap
selection, adaptive-validation and final-evaluation samples. Market seeds were
2026 for training and 2027 for the benchmark parent; take-up and mortality
seeds for every subsample are recorded in the provenance file.

The adaptive research candidate was below the selected fixed cap by
AUD 4,934.469384680989 on the declared validation sample, with paired SE
AUD 304.797851917518. On the untouched final-evaluation sample, the difference
was AUD 5,079.886300697593, with paired SE AUD 264.76277974853014. The selected
policy therefore remains the fixed 0.25% cap, whose paired delta against itself
is zero. These figures are not evidence of positive value from annual cap
flexibility.

The curated set is deliberately limited to:

- `dynamic_adaptive_policy_validation.png`: candidate, comparator and validated
  deployment on identical final random draws;
- `dynamic_fixed_cap_pv_decomposition.png`: selected CSM value drivers across
  the fixed-cap grid, including rising option/hedge costs; and
- `dynamic_lapse_response_by_fixed_cap.png`: the directly projected statistical
  lapse response to the crediting cap.

Exact sample definitions, hashes and numerical claims are in
`dynamic_run_20260713T233802.157326Z.provenance.json`. Compact source tables and
the completed run metadata are copied under
`source_data/dynamic_run_20260713T233802.157326Z/`.

## Customer-LSMC crediting-cap study

This study concerns optimal customer behaviour. Customer LSMC is not used in
the current Time-0 Management-LSMC flexibility calculation above.

The two retained `customer_lsmc_*.png` figures use one validated result grid with
20,000 common Q paths and the single model point `ALT4-01` for caps 0.25%, 0.5%,
1%, 2%, 4%, 6%, 8% and 12%. All cells share the same market-cache key, scenario
fingerprint, inputs and seeds. The explicit stress grid was not run.

The curated set is deliberately limited to:

- `customer_lsmc_phase_values_by_cap.png`: benefits before and after Election,
  phase exposure, fees, margins and guarantee claims; and
- `customer_lsmc_csm_value_drivers_by_cap.png`: reconciled CSM, income, claims,
  call-spread costs and the Dynamic/V11 difference.

The PNGs were rendered from the unified, numerically sorted
`portfolio_risk_by_crediting_cap.csv`. Both use the existing plot function;
the sensitivity table was recalculated on the denser neighbour grid rather than
concatenated. Plot rendering did not change numerical tables, caches or action
rules. Both images were visually reviewed. On the common Policyholder-
benefit PV basis, V11 exceeds Dynamic behaviour at every displayed cap; the
increase narrows from AUD 55,349.65 at 0.25% to AUD 5,011.08 at 12%.

Exact hashes, seeds, method flags and interpretation limits are in
`customer_lsmc_crediting_cap_grid.provenance.json`. Compact unified source data
are in `source_data/customer_lsmc_crediting_cap_grid/`.

When a figure is replaced, update its SHA-256 digest and all numerical claims
in the adjacent provenance file.

## Historical fixed-cap Dynamic-only MLL-FPAR study

This earlier four-modelpoint fixed-cap screen is retained as background. Its
CSM-minus-6%-of-MLL ranking is superseded for the current annual-flexibility
question by the one-modelpoint Time-0 CSM/MLL-FPAR study above.

The three `capital_*.png` figures are byte-for-byte copies from completed run
`20260714T054131.308036Z`. The run used the four-model-point proxy, 1,000 common
Q evaluation paths, market seed 2026, take-up seed 97 and mortality seed 197.
For each of 0.25%, 1%, 6% and 12%, it ran base, mortality +15%, longevity -20%,
lapse-up +50% and lapse-down -50% revaluations. Every child manifest records
`lsmc_used=false`; no Policyholder LSMC runner was called.

The legacy report called its stressed-CSM amount “MLL capital”. Canonically it
is an MLL-FPAR research proxy combining adverse mortality, longevity and the
largest of lapse-up, lapse-down and a 40% model-point positive-CSM mass-lapse
proxy. It is not APRA capital or total SCR. Mass lapse is not a surrender
revaluation. The 6% deduction is a research penalty, not a capital charge or
full Risk Margin.

The 0.25% cap was selected on the four-point grid. Its CSM was AUD 57,630.46,
MLL-FPAR AUD 28,398.52 and risk-penalised CSM AUD 55,926.55. Relative to
the contractual 6% cap it added AUD 64,327.01 of CSM, had AUD 17,626.04
more MLL-FPAR and added AUD 63,269.45 after the 6% research penalty.
This is a fixed-design comparison and does not establish positive value from
annual adaptive discretion.

Promoted files and SHA-256 digests are:

- `capital_csm_and_mll_by_cap.png`:
  `dc42b094edbd74084bacb04e2ebef0f9b0e1389293380d58021cdb286a3b0713`;
- `capital_mll_modules_by_cap.png`:
  `55d374e7fb8292ed6241c6f09cee181067cf773b8a7274167714a9598bc332e6`;
- `capital_dynamic_lapse_by_cap.png`:
  `dd4cd238f27d94cd5fe4e215778b62356b87921b91bd67eec58d75e282d87f55`;
- `crediting_capital_results.csv`:
  `e85888330cb620fbb90c94aced80f15ae5fdc68ff1728a4dff869d61f87b34ee`;
- `dynamic_stress_revaluations_by_crediting_cap.csv`:
  `37977640b1fcc6562b86663a1c20df1d5b6d217f49c3f609e92079745aad8e46`.

The compact tables and copied run manifest are under
`source_data/capital_run_20260714T054131.308036Z/`; the adjacent provenance
record is `capital_run_20260714T054131.308036Z.provenance.json`.
