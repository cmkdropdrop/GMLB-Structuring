# Crediting Rate, Profitability and Risk

## Why the cap matters

The annual crediting cap determines how much positive reference-fund performance
is transferred to the customer account value. It therefore changes several
cashflows at once:

- future account-value-based fee income;
- the timing and amount of income election, lapse and withdrawal;
- guarantee moneyness and later guarantee claims;
- money-market backing income through the surviving account balance;
- the price of the annual call spread;
- the duration of mortality and longevity exposure.

There is no universal monotonic answer. The effect depends on phase, behaviour,
market state, age/life basis and the hedge structure.

## Growth versus Income

In Growth, a higher cap generally makes continued deferral more attractive
because the policyholder still benefits fully from a larger account value at
income election. It can increase the future income base and may delay election.

In Income, the locked payment has no ratchet. A higher account value can reduce
shortfall claims but does not raise scheduled income. It may therefore increase
the incentive to withdraw or lapse so that the policyholder can realise the
fund value. Conversely, a valuable remaining guarantee can suppress lapse.

This phase asymmetry is why one fixed cap need not be optimal throughout the
life of the portfolio.

## New-business custom-CSM profitability proxy

The repository's standard profitability objective is

$$
\mathrm{CSM}^{\mathrm{proxy}}
=\mathrm{PV}(F)+\mathrm{PV}(O)-\mathrm{PV}(K)-\mathrm{PV}(C),
$$

where $F$ is Fee Income, $O$ Other Income, $K$ Claims and $C$ Costs.

| Leg | Main contents | Typical cap channel |
|---|---|---|
| Fee Income | Product and lifetime-income fees | Higher surviving account value can increase fees |
| Other Income | Money-market backing income, retained hedge gain, MVA/retained margins | Account balance, duration and hedge-leg design |
| Claims | Guarantee shortfalls and other explicit insurer-funded benefits | Higher credit can delay exhaustion; behaviour can offset this |
| Costs | Acquisition/maintenance and complete option-spread cost | Higher cap generally increases hedge cost |

The signed reconciliation is mandatory. A chart must not compare a partial
margin such as fees less guarantee claims and call it CSM. This quantity is a
repository-specific market-consistent insurer-value/profitability proxy. It is
not the IFRS 17 contractual service margin: the repository does not perform
IFRS 17 grouping, initial-recognition, fulfilment-cash-flow, risk-adjustment or
CSM roll-forward calculations.

## Option-spread economics

For annual return $R$ and cap $C$, the customer payoff is

$$
\min\left(\max(R,0),C\right)=\max(R,0)-\max(R-C,0).
$$

The insurer buys the lower call and sells the cap call in the capital market.
Increasing $C$ makes the short call less valuable, so the net spread becomes
more expensive. The base cost also includes the configured fair-value markup
and hedge-reference management fee.

If the cap call is explicitly not sold, performance above the customer cap is a
retained hedge gain. That alternative must be labelled because its cost and
income decomposition differs from the standard sold-spread case.

## Money-market backing income

The customer account is an administrative benefit account, not a direct holding
of the reference fund. The case study assumes customer money is invested in a
money-market backing account. Its pathwise return is insurer Other Income. This
provides a natural partial offset to discount-rate changes, but it is not
reference-fund performance and does not change customer crediting.

## Risk measures in the repository

The portfolio-risk workflow reports market-consistent values and
shock-and-revalue sensitivities, including:

- custom-CSM profitability proxy and its four components;
- guarantee claims and hedge cost;
- fee and backing-income duration;
- lapse and income-election outcomes;
- interest-rate, longevity and selected research stresses;
- differences between statistical Dynamic and Customer-LSMC behaviour in the
  separate behaviour workflow; and
- Management-LSMC cap flexibility under statistical Dynamic customer
  behaviour in the Time-0 management workflow.

The current outputs are not pathwise shareholder-loss VaR/CTE, APRA LAGIC
capital, an APRA prescribed capital amount or a complete IFRS 17 risk
adjustment. Stress results derived from the custom-CSM proxy are labelled as
future-profit-at-risk research sensitivities, not as capital.

## Dynamic-only MLL future-profit-at-risk proxy

The cache-strict MLL future-profit-at-risk workflow is
[`run_crediting_rate_capital_analysis.py`](../code/portfolio_simulations/run_crediting_rate_capital_analysis.py).
It deliberately calls only the statistical-Dynamic portfolio reader. Its hard
gates require dynamic Income Election, dynamic post-Election behaviour,
`lsmc_used=false`, the exact Q-market cache and, for `mc_conditional`, the exact
path-congruent hedge-price cache. Missing entries are prepared only by the
authorised precompute runner.

That runner is the separate fixed-design MLL-FPAR workflow. Its earlier
four-modelpoint and 1,000-path documentation results remain historical
sensitivities; they are not inputs or evidence for the one-modelpoint Time-0
annual-flexibility value below.

The current annual-flexibility valuation is implemented in
[`optimize_crediting_rate_dynamic_behaviour_alt.py`](../code/portfolio_simulations/optimize_crediting_rate_dynamic_behaviour_alt.py).
It applies the same MLL-FPAR definitions to fixed caps and fitted
management-policy candidates. It also hard-requires exactly one modelpoint and
never calls the Customer-LSMC runner. Its LSMC is solely the insurer's
Management LSMC.

For each fixed cap and each fitted management-policy candidate,
common-random-number revaluations apply:

| Module | Revaluation |
|---|---|
| Mortality | permanent 15% increase in annual $q_x$ |
| Longevity | permanent 20% decrease in annual $q_x$ |
| Lapse up | permanent 50% increase in ordinary lapse baselines and the performance-sensitive excess-hazard cap |
| Lapse down | permanent 50% decrease in ordinary lapse baselines and the performance-sensitive excess-hazard cap |

The first two factors and the lapse up/down factors mirror the repository's
existing Solvency-II-style research defaults. The corresponding European
standard-formula articles specify 15% mortality, 20% longevity and 50% permanent
lapse shocks, but the calculation here is still not a regulatory Solvency II
SCR: [mortality Article 137](https://www.eiopa.europa.eu/rulebook/solvency-ii-single-rulebook/article-5757_en),
[longevity Article 138](https://www.eiopa.europa.eu/rulebook/solvency-ii-single-rulebook/article-5758_en) and
[lapse Article 142](https://www.eiopa.europa.eu/rulebook/solvency-ii-single-rulebook/article-5762_en).

The Australian prudential framework is different. Under
[APRA LPS 115](https://www.apra.gov.au/standards/lps-115), the Insurance Risk
Charge is based on the reduction in capital base when adjusted policy
liabilities are replaced by appropriately stressed liabilities; it is not a
change in this repository's custom CSM. The adjusted-policy-liability and
capital-base boundary is specified in
[APRA LPS 112](https://www.apra.gov.au/standards/lps-112), while
[APRA LPS 110](https://www.apra.gov.au/standards/lps-110) builds the prescribed
capital amount from insurance, asset, concentration and operational risk,
minus the aggregation benefit and plus the combined-stress adjustment; the PCR
also includes any supervisory adjustment. None of those APRA calculations is
implemented here. The fixed research factors in this repository therefore
must not be described as APRA capital. If APRA classifies the product as
variable-annuity business, LPS 110 Attachment A additionally requires an
APRA-approved method that considers asset and insurance risks simultaneously;
the current workflow is not that method.

For signed custom-CSM proxy $J$, each stand-alone future-profit loss is

$$
R_i=\left[J_{\mathrm{base}}-J_{\mathrm{stress},i}\right]_+.
$$

The result is called **MLL future profit at risk (MLL-FPAR)**. It measures the
positive loss of the repository's custom CSM under the declared mortality,
longevity and lapse stresses. It is neither required capital nor an IFRS 17 CSM
movement. Historical code, files and column names containing `capital` are
compatibility aliases for this same research quantity.

The lapse module is the maximum of lapse up, lapse down and a 40% mass-lapse
proxy. The latter is calculated model point by model point from positive CSM
contributions before aggregation, so onerous cells do not offset margins assumed
lost on profitable cells. It is **not** an immediate-surrender revaluation and
does not reproduce surrender cashflows, MVA or event expenses. Both the result
with this proxy and the permanent-lapse-only amount must be disclosed.

The Time-0 flexibility calculation uses exactly one modelpoint. In that special
case the mass-lapse amount is simply 40% of positive total CSM. If mortality and
longevity are non-adverse and mass lapse is the only binding module, the ratio
therefore has the mechanical ceiling
$\mathrm{CSM}/R_{\mathrm{MLL}}=1/0.40=2.5$. This is a property of the proxy, not
a universal actuarial optimum.

The Mortality/Longevity/Lapse submodules use the existing correlation submatrix

$$
\rho_{\mathrm{MLL}}=\begin{pmatrix}
1&-0.25&0\\
-0.25&1&0.25\\
0&0.25&1
\end{pmatrix},\qquad
R_{\mathrm{MLL}}=\sqrt{\mathbf{R}^{\mathsf T}\rho_{\mathrm{MLL}}\mathbf{R}}.
$$

This is the repository's Solvency-II-style three-module research submatrix; it
is not an APRA-prescribed correlation matrix.

This partial result excludes market, expense, catastrophe, operational,
concentration and tax-absorption effects. Its correct label is **MLL-FPAR
research proxy**, never total SCR, prescribed capital amount, APRA/LAGIC
capital or an IFRS 17 CSM change.

## Time-zero management objective and FPAR sensitivity

The current question is the value today of the contractual right to reset the
crediting cap annually, not the construction or validation of a deployment
strategy. All candidate cashflows are risk-neutral expected values discounted
to Time 0 with the current Australian zero curve. The fixed-cap comparator and
Management LSMC use the same complete cached Q sample. There is no held-out
sample, different OOS seed, forward roll, policy replay or bootstrap gate.

The primary ranking measure is the complete custom CSM

$$
J(\pi).
$$

The following risk-penalised value is reported only as a secondary research
sensitivity:

$$
J_{\mathrm{FPAR}}(\pi)=J(\pi)-\lambda R_{\mathrm{MLL}}(\pi),
\qquad \lambda=0.06.
$$

where $J$ is the complete CSM proxy and $\pi$ is either a fixed cap or a fitted
annual-management candidate. The dimensionless 6% factor is a user-selected
FPAR penalty weight, not a capital charge, cost-of-capital rate, full projected
Risk Margin or APRA requirement. The lifetime diagnostic
$J/R_{\mathrm{MLL}}$ is also secondary. A candidate with immaterial FPAR has no
ratio; the implementation does not manufacture a denominator with an epsilon.

MLL-FPAR is nonlinear because stand-alone losses contain positive parts, the
lapse module contains a maximum and MLL-FPAR contains a correlation norm. The
complete risk-penalised sensitivity therefore cannot be inserted directly as an additive
one-year Bellman reward. Management LSMC fits a finite, predeclared policy class
using additive support objectives

$$
J_{\alpha,q}
=(1-\alpha)J_{\mathrm{base}}+\alpha\sum_s q_sJ_s,
\qquad \alpha\in\{0,0.25,0.50,0.75,1\}.
$$

The stress directions are mortality, longevity, lapse up, lapse down and an
equal-weighted basket of all four. This gives 21 Base/Stress objectives,
including pure Base CSM, plus one conditional-ratio heuristic. Each complete
fitted 14-value Time-0 payload is then evaluated with the actual nonlinear
MLL-FPAR formula. Pure Base CSM selects the result; the FPAR-penalised value and
CSM/MLL-FPAR remain supplementary diagnostics.

To control the regression level error, candidate $j$ is anchored to the direct
best-fixed projection:

$$
\mathbf p_j^{\mathrm{anchored}}
=\mathbf p_{\mathrm{fixed,direct}}
+\left(\mathbf p_{j,\mathrm{LSMC}}
-\mathbf p_{\mathrm{fixed,LSMC}}\right).
$$

There is no additional minimum-CSM constraint. Best fixed remains an explicit
zero-flexibility-value comparator and is replaced only by a strictly higher
custom CSM. Ties are resolved deterministically; no epsilon denominator is
introduced to manufacture a ratio.

## Same-sample fixed-cap comparator

The fixed comparison uses common random numbers, the same statistical Dynamic
customer model, exact cache keys and the complete admissible grid 0.25%, then
1% through 20%. Customer LSMC is absent. The same base and mortality,
longevity, lapse-up and lapse-down projections feed both the fixed-cap and
management comparisons.

In completed run `20260714T084838.270769Z`, the best fixed cell is the lower
grid boundary of 0.25%:

| Fixed cap | Custom CSM (AUD) | MLL-FPAR (AUD) | CSM minus 6% FPAR penalty (AUD) | CSM / MLL-FPAR |
|---:|---:|---:|---:|---:|
| 0.25% | 52,151.27 | 25,057.48 | 50,647.82 | 2.08127 |
| 1% | 43,684.60 | 21,872.82 | 42,372.23 | 1.99721 |
| 6% | -9,798.78 | 9,231.86 | -10,352.69 | -1.06141 |
| 12% | -42,096.49 | 7,308.65 | -42,535.01 | -5.75982 |

The fixed-cap result alone confirms that the crediting choice changes both
profitability and the stressed future-profit-risk profile. The 0.25% cell
maximises custom CSM on the fixed grid; it also happens to maximise the
secondary FPAR-penalised sensitivity. It does not yet value the annual reset
right; that requires the Management-LSMC comparison below.

## Time-zero value of annual reset flexibility

The completed primary run uses exactly one modelpoint (`ALT4-01`), 4,200 common
Heston-Hull-White Q paths, market seed 2026, current-curve discounting and exact
path-congruent hedge prices. Statistical Dynamic customer behaviour is active;
Customer LSMC is false. The fitted policy class is complete and contains 23
Bellman chains: one forced fixed anchor, 21 Base/Stress objectives and one
conditional-ratio heuristic.

The completed fit stored every candidate. Its earlier ratio-only presentation
selected `base_stress_mix_alpha_0.50::balanced_four_stress_csm`; that result is
retained only as a historical objective sensitivity. Ranking the complete
stored table by the current primary custom-CSM objective selects `base_csm`.
That same candidate also leads the secondary 6%-FPAR-penalised sensitivity.
This deterministic selection-layer change does not require a new projection or
regression fit.

The selected candidate's first Time-0 action is 0.25%, the same as best fixed.
Its additional value comes from the right to make later state-dependent annual
choices; no future operating schedule is exported or tested.

| Time-0 alternative | Custom CSM (AUD) | MLL-FPAR (AUD) | CSM minus 6% FPAR penalty (AUD) | CSM / MLL-FPAR | MLL-FPAR / CSM |
|---|---:|---:|---:|---:|---:|
| Best fixed 0.25% | 52,151.27 | 25,057.48 | 50,647.82 | 2.08127 | 48.05% |
| Annual adjustment right: `base_csm` | 103,840.38 | 45,213.13 | 101,127.59 | 2.29669 | 43.54% |
| Difference | **+51,689.11** | +20,155.65 | +50,479.77 | +0.21542 | -4.51 pp |

The primary Time-0 value of flexibility is therefore the custom-CSM increase of
AUD 51,689.11. After applying the secondary 6% FPAR penalty, the corresponding
sensitivity is AUD 50,479.77. CSM/MLL-FPAR rises by 0.21542 and MLL-FPAR/CSM
falls by 4.51 percentage points. Absolute MLL-FPAR nevertheless rises by AUD
20,155.65 because custom CSM rises by AUD 51,689.11. These are profitability
and stressed-future-profit diagnostics; they do not show higher or lower
required capital.

This is an in-sample Time-0 estimate by design. It is the maximum within the
declared fitted policy class, not a global optimum over every possible
management rule. Exactly one illustrative modelpoint is used, so the 40%
positive-CSM mass-lapse proxy can materially influence both measures. Regression
fit, anchoring, path count, stress calibration and the partial scope of
MLL-FPAR are model limitations. Sensitivities are required before treating the
uplift as a robust product-value estimate.

The plot and compact source tables are documented under
[`results/document_figures`](../results/document_figures/README.md).

## Accounting interpretation

Management discretion over future crediting may be relevant to
fulfilment-cashflow and contractual-service assessments if it is substantive
and reflected in the applicable accounting policy. This repository only
estimates cashflows under an assumed management rule. Its custom CSM and
stressed custom-CSM losses are not IFRS 17 CSM balances or movements. It does
not demonstrate IFRS recognition, group-level CSM or release patterns.
Accounting conclusions require separate contract interpretation and
governance.
