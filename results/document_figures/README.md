# Curated documentation figures

Only small figures reviewed against a completed run manifest belong here.
Large run directories and Q caches remain generated local artefacts under
`results/runs/` and `results/cache/`.

## Dynamic-behaviour cap study

The three `dynamic_*.png` figures are byte-for-byte copies from completed run
`20260713T233802.157326Z`. This is a four-model-point proxy study, not the full
48-point portfolio. It used 4,200 training paths and a distinct
1,260-path benchmark parent sample, split into independent 420-path fixed-cap
selection, adaptive-validation and final-evaluation samples. Market seeds were
2026 for training and 2027 for the benchmark parent; take-up and mortality
seeds for every subsample are recorded in the provenance file.

The adaptive research candidate failed the predeclared validation gate. Its
validation CSM delta versus the selected fixed cap was AUD -4,934.469384680989
with paired SE AUD 304.797851917518. On the untouched final-evaluation sample,
the candidate delta was AUD -5,079.886300697593 with paired SE
AUD 264.76277974853014. The deployed policy is therefore the fixed 0.25% cap,
whose paired delta against itself is zero. These figures are not evidence of a
positive value from annual cap flexibility.

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

## Portfolio risk and behaviour study

The three `risk_*.png` figures come from completed run
`20260714T002637.233689Z`. They compare Dynamic V11 with the validated deployed
annual-action LSMC fallback. All four cap cells used a fallback: 0.25%, 1% and
6% used `earliest|continue_only`, while 12% used
`V00_model_point_fixed_continue`. No accepted LSMC candidate is shown.

This is a four-model-point, base-only development study. It used 1,000
evaluation paths, 4,000 training paths, 1,000 validation paths and one
predeclared training seed. The explicit stress grid was not run. Results must
not be interpreted as a full-portfolio calibration, a stress study or a
pathwise VaR/TVaR/CTE analysis.

At the contractual 6% cap, CSM was AUD -6,696.55357557183 under Dynamic V11
and AUD -22,010.838525358064 under the validated LSMC fallback. Across the cap
grid, call-spread costs increased materially: for Dynamic V11 from
AUD 12,755.273071925712 at 0.25% to AUD 208,453.77757959758 at 12%, and for the
LSMC fallback from AUD 10,466.440847954998 to AUD 206,192.9929005082.

The curated set is deliberately limited to:

- `risk_behaviour_comparison_by_cap.png`: Income-Election timing and
  post-Election behaviour;
- `risk_csm_value_drivers_by_cap.png`: reconciled CSM and selected value
  drivers; and
- `risk_valuation_exposures_by_cap.png`: premium-normalised guarantee, BEL,
  CSM, fee-coverage and hedge-cost exposures.

All seven run figures were visually reviewed. The selected PNGs were
regenerated deterministically from the validated root CSV after a plot-only
legend-classification fix; numerical tables, manifests and valuation artifacts
were unchanged. Exact hashes, seeds, fallback mappings and limitations are in
`risk_run_20260714T002637.233689Z.provenance.json`. Compact source data are in
`source_data/risk_run_20260714T002637.233689Z/`.

When a figure is replaced, update its SHA-256 digest and all numerical claims
in the adjacent provenance file.

## Dynamic-only MLL capital study

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
