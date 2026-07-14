# Curated documentation figures

Only small figures reviewed against a completed run manifest belong here.
Large run directories and Q caches remain generated local artefacts under
`results/runs/` and `results/cache/`.

## Current Time-0 capital-adjusted flexibility study

`time0_crediting_flexibility_csm_mll.png` and `.svg` document completed run
`20260714T084838.270769Z`. It uses exactly one modelpoint (`ALT4-01`), 4,200
common Heston-Hull-White Q paths with market seed 2026, the current Australian
curve and exact path-congruent market and hedge caches. Customers follow the
statistical Dynamic behaviour model. Customer LSMC was not fitted or called.

This is today's risk-neutral valuation of the annual cap-reset right, not a
deployment study. The complete Q sample is shared by the Management-LSMC fit,
the finished-candidate ranking and every fixed-cap comparator. There is no OOS
sample, different validation seed, forward roll, strategy replay or bootstrap
gate. Exactly one modelpoint is used throughout.

The completed fit stored all 22 candidate payloads before its original final
screen. The documented selection now maximises the stable, additive-capital
criterion `CSM - lambda * MLL` with `lambda = 6%`; CSM/MLL is reported as the
second success criterion. This post-fit ranking needs neither a new projection
nor a regression refit. Its exact inputs and result are recorded in
`capital_adjusted_reranking_audit.csv`; the earlier pure-ratio audit remains a
secondary diagnostic only.

The best fixed cap is 0.25%, with CSM AUD 52,151.27, MLL AUD 25,057.48,
CSM/MLL 2.08127 and capital-adjusted CSM AUD 50,647.82. The selected fitted
class is `base_csm`. Its Time-0 values are CSM AUD 103,840.38, MLL AUD
45,213.13, CSM/MLL 2.29669 and capital-adjusted CSM AUD 101,127.59. Thus the
ratio rises by 0.21542 and the primary criterion by AUD 50,479.77. Absolute MLL
rises, but more slowly than CSM: MLL/CSM falls from 48.05% to 43.54%.

This is the maximum only within the predeclared 21 Base/Stress fitted policies
plus one conditional-ratio heuristic, not a global management optimum. It is
in-sample by design. MLL covers mortality, longevity and lapse only and is not
total regulatory capital. The 6% lambda is the existing one-year cost-of-
capital rate and remains an explicit modelling choice.

The plot was regenerated after the completed valuation as one direct
visualisation of the Section 7 table. It compares best fixed and annual
management for CSM, MLL, `CSM - 6% * MLL` and CSM/MLL; no full fixed-cap curve
or separate risk-module graphic is included. This changed neither stored paths
nor fitted payloads. The original run manifest and numerical outputs are
preserved under
`source_data/time0_crediting_flexibility_20260714T084838.270769Z/`.

Promoted files and SHA-256 digests are:

- `time0_crediting_flexibility_csm_mll.png`:
  `ee894e010d2e92188157e9aa7b408b99e3eb3d34396a8c590c67f289d0596c7f`;
- `time0_crediting_flexibility_csm_mll.svg`:
  `7dab8e240185393a3ba58a27582f3137e7978e87961dd2befaf6572ed751e0df`;
- `fixed_cap_time_zero_results.csv`:
  `552261bf5a741e0c9daa937f17818b28adeb6dfa9a8edd5dca40c2aacd3d9eb4`;
- `time_zero_capital_adjusted_flexibility_comparison.csv`:
  `8e68741c5b98a0ee23f02d02250411b135ccb903452367b3aa657b56cfee6009`;
- `management_lsmc_policy_class_candidates.csv`:
  `353527b05dfb2c89f542a902f40830737dfdbe449451a1d8a645bfbef333b015`;
- `capital_adjusted_reranking_audit.csv`:
  `fbd4debb3fe8c4c7016205e2f248e85aac5553fce5fb1377985e068611f0cb5a`.

The adjacent record
`time0_crediting_flexibility_20260714T084838.270769Z.provenance.json` contains
the full input, cache, method and curation metadata.

## Historical dynamic-behaviour OOS cap study

This earlier four-modelpoint study is retained for historical comparison. It is
superseded for README Section 7 and is not an input to the current one-modelpoint
same-sample Time-0 capital-adjusted valuation.

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

## Historical fixed-cap Dynamic-only MLL capital study

This earlier four-modelpoint fixed-cap screen is retained as background. Its
CSM-minus-6%-of-MLL ranking is superseded for the current annual-flexibility
question by the one-modelpoint Time-0 CSM/MLL study above.

The three `capital_*.png` figures are byte-for-byte copies from completed run
`20260714T054131.308036Z`. The run used the four-model-point proxy, 1,000 common
Q evaluation paths, market seed 2026, take-up seed 97 and mortality seed 197.
For each of 0.25%, 1%, 6% and 12%, it ran base, mortality +15%, longevity -20%,
lapse-up +50% and lapse-down -50% revaluations. Every child manifest records
`lsmc_used=false`; no Policyholder LSMC runner was called.

The reported MLL amount combines adverse mortality, longevity and the largest
of lapse-up, lapse-down and a 40% model-point positive-CSM mass-lapse proxy. It
is a partial research life-risk capital proxy, not APRA capital or total SCR.
Mass lapse is not a surrender revaluation. The primary objective is CSM less a
one-year 6% charge on this proxy, not a full Risk Margin.

The 0.25% cap was selected on the four-point grid. Its CSM was AUD 57,630.46,
MLL capital AUD 28,398.52 and capital-adjusted CSM AUD 55,926.55. Relative to
the contractual 6% cap it added AUD 64,327.01 of CSM, required AUD 17,626.04
more MLL capital and added AUD 63,269.45 after the one-year capital charge.
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
