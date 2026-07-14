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

## New-business CSM proxy

The standard objective is

$$
\mathrm{CSM}^{\mathrm{proxy}}
=\operatorname{PV}(F)+\operatorname{PV}(O)-\operatorname{PV}(K)-\operatorname{PV}(C),
$$

where $F$ is Fee Income, $O$ Other Income, $K$ Claims and $C$ Costs.

| Leg | Main contents | Typical cap channel |
|---|---|---|
| Fee Income | Product and lifetime-income fees | Higher surviving account value can increase fees |
| Other Income | Money-market backing income, retained hedge gain, MVA/retained margins | Account balance, duration and hedge-leg design |
| Claims | Guarantee shortfalls and other explicit insurer-funded benefits | Higher credit can delay exhaustion; behaviour can offset this |
| Costs | Acquisition/maintenance and complete option-spread cost | Higher cap generally increases hedge cost |

The signed reconciliation is mandatory. A chart must not compare a partial
margin such as fees less guarantee claims and call it CSM.

## Option-spread economics

For annual return $R$ and cap $C$, the customer payoff is

$$
\min\!\left(\max(R,0),C\right)=\max(R,0)-\max(R-C,0).
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

The portfolio-risk workflow reports market-consistent values and shock-and-
revalue sensitivities, including:

- CSM proxy and its four components;
- guarantee claims and hedge cost;
- fee and backing-income duration;
- lapse and income-election outcomes;
- interest-rate, longevity and selected research stresses;
- differences between statistical dynamic and deployed LSMC behaviour.

The current outputs are not pathwise shareholder-loss VaR/CTE, APRA LAGIC
capital or a complete IFRS 17 risk adjustment. Any research capital or cost-of-
capital quantity is labelled as a proxy.

## Dynamic-only MLL capital proxy

The cache-strict capital workflow is
[`run_crediting_rate_capital_analysis.py`](../code/portfolio_simulations/run_crediting_rate_capital_analysis.py).
It deliberately calls only the statistical-Dynamic portfolio reader. Its hard
gates require dynamic Income Election, dynamic post-Election behaviour,
`lsmc_used=false`, the exact Q-market cache and, for `mc_conditional`, the exact
path-congruent hedge-price cache. Missing entries are prepared only by the
authorised precompute runner.

For each fixed cap, common-random-number revaluations apply:

| Module | Revaluation |
|---|---|
| Mortality | permanent $+15\%$ multiplier to annual $q_x$ |
| Longevity | permanent $-20\%$ multiplier to annual $q_x$ |
| Lapse up | permanent $+50\%$ multiplier to ordinary lapse baselines and the performance-sensitive excess-hazard cap |
| Lapse down | permanent $-50\%$ multiplier to ordinary lapse baselines and the performance-sensitive excess-hazard cap |

The first two factors and the lapse up/down factors mirror the repository's
existing Solvency-II-style research defaults. The corresponding European
standard-formula articles specify 15% mortality, 20% longevity and 50% permanent
lapse shocks, but the calculation here is still not a regulatory Solvency II
SCR: [mortality Article 137](https://www.eiopa.europa.eu/rulebook/solvency-ii-single-rulebook/article-5757_en),
[longevity Article 138](https://www.eiopa.europa.eu/rulebook/solvency-ii-single-rulebook/article-5758_en) and
[lapse Article 142](https://www.eiopa.europa.eu/rulebook/solvency-ii-single-rulebook/article-5762_en).

The Australian prudential framework is different. APRA LPS 115 requires an
insurer to determine appropriate mortality, longevity and lapse stress margins
at a 99.5% one-year sufficiency level for its own liabilities. The fixed research
factors in this repository therefore must not be described as APRA capital:
[APRA LPS 115](https://www.apra.gov.au/standards/lps-115).

For signed CSM proxy $J$, each stand-alone amount is

$$
K_i=\left[J_{\mathrm{base}}-J_{\mathrm{stress},i}\right]_+.
$$

The lapse module is the maximum of lapse up, lapse down and a 40% mass-lapse
proxy. The latter is calculated model point by model point from positive CSM
contributions before aggregation, so onerous cells do not offset margins assumed
lost on profitable cells. It is **not** an immediate-surrender revaluation and
does not reproduce surrender cashflows, MVA or event expenses. Both the result
with this proxy and the permanent-lapse-only amount must be disclosed.

The Mortality/Longevity/Lapse submodules use the existing correlation submatrix

$$
\rho_{\mathrm{MLL}}=\begin{pmatrix}
1&-0.25&0\\
-0.25&1&0.25\\
0&0.25&1
\end{pmatrix},\qquad
K_{\mathrm{MLL}}=\sqrt{\mathbf{K}^{\mathsf T}\rho_{\mathrm{MLL}}\mathbf{K}}.
$$

This partial result excludes market, expense, catastrophe, operational,
concentration and tax-absorption effects. Its correct label is **MLL life-risk
capital proxy**, never total SCR, prescribed capital amount or APRA/LAGIC
capital.

## Capital-adjusted objective

A raw ratio is a poor primary optimiser: it is unstable when capital is small,
is not additive across projection years and can be mechanically distorted when
the mass-lapse proxy binds. The primary fixed-cap ranking therefore uses the AUD
economic-value-added proxy

$$
J^{\text{capital-adjusted}}(C)=J(C)-hK_{\mathrm{MLL}}(C),
$$

where the current research hurdle is $h=6\%$. This is a one-year capital
charge, not a full projected Risk Margin. The lifetime efficiency diagnostic
$J/K_{\mathrm{MLL}}$ is reported only when capital exceeds a premium-relative
materiality threshold; no epsilon denominator is introduced.

For product-design discretion relative to the contractual 6% cap,

$$
\Delta^{\mathrm{design}}_{\mathrm{capital}}
=J^{\text{capital-adjusted}}_{\text{selected fixed}}
-J^{\text{capital-adjusted}}_{6\%}.
$$

For annual adaptive discretion, the comparison remains adaptive versus best
fixed. Because capital and ratios are non-additive, they cannot simply replace
annual CSM in the existing Bellman reward. Each frozen candidate must instead be
stress-revalued and selected on separate validation data before one untouched
final evaluation.

## Constant-cap analysis

A controlled constant-cap comparison uses common random numbers, exact cache
keys and the same product/behaviour settings for every cap. Recommended views
are:

1. CSM and component waterfall by cap;
2. hedge cost, guarantee claims and money-market income by cap;
3. election, lapse and withdrawal rates by cap;
4. market and longevity shock changes relative to the base cap;
5. dynamic-function versus deployed-LSMC results on the same evaluation paths.

A cap should not be declared superior from the mean CSM alone if paired Monte
Carlo uncertainty or material risk sensitivities reverse the conclusion.

Completed Dynamic-only run `20260714T054131.308036Z` provides the first MLL
capital screen on the four-point proxy. Between 0.25% and 12%, the MLL proxy
falls from AUD 28,399 to AUD 9,020 and cumulative Dynamic Income lapse falls from
12.30% to 5.09%, while CSM falls from AUD 57,630 to AUD -39,517. The 0.25% cap
still maximises capital-adjusted CSM. Versus 6%, its CSM uplift is AUD 64,327,
its additional MLL capital is AUD 17,626 and its value after the one-year 6%
capital charge is AUD 63,269 per representative contract.

## Flexible-cap value

The economic value of flexibility is the paired OOS difference

$$
\Delta^{\mathrm{flex}}=\mathrm{CSM}^{\mathrm{proxy}}_{\mathrm{adaptive}}
-\mathrm{CSM}^{\mathrm{proxy}}_{\text{best fixed}}.
$$

The best fixed cap is selected on its own sample. The adaptive candidate is
accepted on a separate validation sample and evaluated once on a final sample.
If it fails validation, the deployed policy is the fixed fallback and deployed
flexibility value is zero. A negative rejected candidate is useful model-risk
evidence but is not a deployed loss or a positive value claim.

Do not conflate this annual adaptive value with the positive fixed-design value
above. The completed capital run establishes that the cap changes risk and that
choosing a different fixed cap can add capital-adjusted value relative to 6%.
It does not validate annual state-contingent management discretion.

## Accounting interpretation

Management discretion over future crediting may be relevant to fulfilment-
cashflow and contractual-service assessments if it is substantive and reflected
in the applicable accounting policy. This repository only estimates cashflows
under an assumed management rule. It does not demonstrate IFRS recognition,
group-level CSM or release patterns. Accounting conclusions require separate
contract interpretation and governance.
