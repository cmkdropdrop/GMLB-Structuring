# Crediting-Rate Optimisation

## Scope and terminology

The optimisation studies annual management discretion over the customer's
Maximum Return. Workflow names call this quantity the **crediting rate**, but
the contractual payoff is a floor-at-zero, cap-at-$C_y$ annual index credit:

$$
g_y=\min\left(\max\left(R_y^{\mathrm{fund}},0\right),C_y\right),
\qquad C_y\in\mathcal C.
$$

The standard full action grid is `{0.25%, 1%, 2%, ..., 20%}`. The
LSMC-policyholder runner
also offers a predeclared coarse screening grid for faster research runs. The
6% case-study cap remains the contractual base; optimisation grids are
counterfactual management-action studies and do not reprice all other product
terms to be budget neutral.

There are three distinct research questions:

1. What is today's CSM value of the insurer's right to reset the cap each year
   when Policyholders follow the statistical Dynamic behaviour model, with
   MLL future-profit-at-risk (MLL-FPAR) reported as a secondary sensitivity?
2. What cap policy is attractive when policyholders themselves respond through
   a policyholder-value-maximising LSMC follower?
3. Does the fixed cap selected from a design grid remain attractive under
   illustrative mortality, longevity and lapse future-profit stresses?

The insurer and policyholder objectives are never blended.

## Insurer objective

The complete signed CSM proxy is

$$
J(\pi)=\mathbb{E}^{\mathbb{Q}}\left[
\mathrm{PV}(F)+\mathrm{PV}(O)-\mathrm{PV}(K)-\mathrm{PV}(C)\mid \pi
\right],
$$

where $\pi$ maps observable pre-action state to an annual cap and:

| Symbol | CSM leg | Main contents |
|---|---|---|
| $F$ | Fee Income | Product and lifetime-income fees |
| $O$ | Other Income | Money-market backing income, MVA/other retained margins and explicitly retained hedge gain where applicable |
| $K$ | Claims | Guarantee shortfalls and other identified insurer-funded benefits |
| $C$ | Costs | Acquisition/maintenance expense and the complete option package |

The option package includes fair value, the configured percentage markup on
fair option value and the annual hedge-reference management fee. The standard
hedge buys the zero-strike return call and sells the call at the customer cap in
the capital market. Consequently a higher cap normally costs more. Customer
benefits paid from the account value are not counted again as insurer claims.

The code labels $J$ as a market-consistent new-business CSM proxy before Risk
Margin. It is not a complete IFRS 17 CSM. In the current Dynamic-customer
Management-LSMC workflow, $J$ is the primary finished-candidate objective. The
secondary research sensitivity is

$$
S_{\lambda}(\pi)=J(\pi)-\lambda F_{\mathrm{MLL}}(\pi),
\qquad \lambda=0.06.
$$

$F_{\mathrm{MLL}}$ is the partial mortality/longevity/lapse stressed-CSM
future-profit-risk proxy. The 6% coefficient is a dimensionless research
penalty weight, not a capital charge, cost-of-capital rate, Risk Margin or
regulatory calibration. CSM/MLL-FPAR is a secondary proxy-efficiency measure

$$
R(\pi)=\frac{J(\pi)}{F_{\mathrm{MLL}}(\pi)},
$$

but it does not select the policy. The calculation uses exactly one modelpoint.

### Time-zero CSM selector and FPAR diagnostic

MLL-FPAR is formed only after complete Time-0 aggregation. Positive-part stress
losses, the maximum of the lapse stresses and the correlation norm make the
proxy non-additive. The implementation fits a predeclared finite class of
additive Base/Stress objectives and ranks each finished 14-value payload on
actual CSM. MLL-FPAR, $J-0.06F_{\mathrm{MLL}}$ and CSM/MLL-FPAR are calculated
from the same payload and reported secondarily.

$$
J_{\alpha,q}=(1-\alpha)J_{\mathrm{base}}
+\alpha\sum_s q_sJ_s,
\qquad \alpha\in\{0,0.25,0.50,0.75,1\}.
$$

The directions are mortality, longevity, lapse up, lapse down and a balanced
four-stress basket. One pure-Base objective plus four positive alpha levels for
each of the five directions gives 21 fitted support policies; one
conditional-ratio heuristic is added. A forced best-fixed chain supplies a
common regression anchor. There is no additional minimum-CSM constraint. The
highest-CSM fixed cap is the explicit comparator and is replaced only by a
strictly higher actual CSM. Neither the penalised sensitivity nor the ratio is
an additional selection gate.

The separate Dynamic-only
[`run_crediting_rate_capital_analysis.py`](../code/portfolio_simulations/run_crediting_rate_capital_analysis.py)
remains available under a legacy filename for a fixed-design CSM-minus-FPAR-
penalty screen. It is an auxiliary fixed-design workflow using the same 6%
research weight; it does not calculate regulatory capital or value the annual
reset right.

### Regulatory boundary

Every new Time-0 report records `regulatory_capital_status=not_calculated` and
leaves APRA Insurance Risk Charge, Prescribed Capital Amount and Prudential
Capital Requirement at null. APRA [LPS 115](https://www.apra.gov.au/standards/lps-115)
uses the reduction in a fund's capital base when adjusted policy liabilities
are replaced by stressed policy liabilities, not a change in this repository's
custom CSM. [LPS 112](https://www.apra.gov.au/standards/lps-112) introduces the
RFBEL/termination-value and options/asymmetry requirements for adjusted policy
liabilities, while [LPS 110](https://www.apra.gov.au/standards/lps-110) adds the
remaining fund-level capital modules. Those fund balance-sheet, tax,
reinsurance and calibration inputs are absent here. The MLL correlation matrix
is therefore an illustrative research assumption, not an APRA-prescribed
correlation table.

Recognised IFRS 17 CSM is also not shocked here. The custom $J$ measure is a
product profitability formula; AASB 17 CSM is unearned profit within the
insurance-contract carrying amount and follows the standard's fulfilment-
cashflow adjustment mechanics.

## Decision timing and information

The management action is annual. At anniversary $y$, the projector applies
events in this economic order:

1. finish the previous crediting year and apply its protected return;
2. post accrued product and lifetime-income fees;
3. process mortality and contractual survivor treatment;
4. permit an eligible Growth-to-Income election;
5. choose and announce $C_y$, then purchase the new annual hedge;
6. process eligible same-anniversary Income actions;
7. continue the monthly projection.

The control regression may use only state known before step 5. The newly
announced cap can affect a same-anniversary action after it has been announced,
but it cannot leak into the pre-action feature vector.

Typical control state includes the short rate, reference-fund level, stochastic
variance, prior caps, trailing performance, in-force exposure, Growth/Income
mix, account value, locked income, surrender value and guarantee moneyness.
Every deployable policy is a function of current state; it is not an ex-post
pathwise maximum.

## Dynamic-behaviour optimiser

[`optimize_crediting_rate_dynamic_behaviour_alt.py`](../code/portfolio_simulations/optimize_crediting_rate_dynamic_behaviour_alt.py)
is the strict cache-reader implementation behind the installed
`optimise-crediting-dynamic` command. It keeps the statistical behaviour
functions active throughout the monthly projector. Income take-up,
ordinary/performance lapse and withdrawal therefore respond to projected
account value, moneyness and realised performance history. There is no separate
policyholder value-function regression in this workflow.

### Gas-storage formulation

The insurer problem has an endogenous state: today's cap changes the account
value and behaviour states used by later decisions. The implementation treats
account value per initial premium as a storage inventory $A_y$ and writes the
recursion schematically as

$$
V_y(A_y,X_y)=\max_{c\in\mathcal C}
\left(r_y(A_y,X_y,c)+
\mathbb{E}^{\mathbb{Q}}\left[
V_{y+1}(A_{y+1},X_{y+1})\mid A_y,X_y,c
\right]\right).
$$

Here $X_y$ is exogenous market/portfolio state and the monthly projector
generates both the realised one-year insurer reward $r_y$ and realised next
inventory $A_{y+1}$. Control-randomised cap histories, including a
persistent-exploration subset, provide state/action support.

Account value is placed on an adaptive quantile grid. At each node the
continuation regression uses a constant, the ATM one-year call value
$H_y^{\mathrm{ATM}}$, the reference-fund level $S_y$ and the overnight rate
$r_y$:

$$
\phi(X_y)=\left(1,H_y^{\mathrm{ATM}},S_y,r_y\right).
$$

The action-Q regression is fitted directly to the pathwise Bellman target

$$
Y_{i,y}^{c}=r_{i,y}^{c}
+\widehat V_{y+1}\left(A_{i,y+1}^{c},X_{i,y+1}\right),
$$

where the next-year grid value is interpolated at that path's **realised** next
account value. There is no separate regression for the conditional mean reward
or account-value transition. This avoids evaluating a nonlinear continuation
surface at a conditional-mean inventory, which would introduce a Jensen-type
approximation.

The Time-0 action-Q fits use the six-column direct-Q basis, where
$z_H$, $z_S$, $z_r$ and $z_A$ are the standardised call, fund, rate and
inventory features:

$$
\left(1,z_H,z_S,z_r,z_A,z_A^2\right).
$$

There is no second projection onto a larger rollout basis and no rollout
argmax.
Values are interpolated between inventory nodes; the inter-node difference is
the discrete shadow value of one additional unit of account value. Component
envelopes and local action masks prevent an unstable regression from
manufacturing negative claims/costs or forcing every state to use one globally
failed action.

The public Dynamic workflow uses one complete cached Q sample for the
Management-LSMC regressions, the finished-candidate CSM ranking and all fixed
caps. It does not allocate outer folds, reserve paths or run a causal
forward rollout. All future cashflows are discounted to Time 0 with the current
curve. The result is today's risk-neutral expected value within the declared
fitted policy class, not an OOS or deployment-performance estimate.

Every annual projection uses statistical Dynamic Policyholder behaviour.
Customer LSMC is never called. The reader and its cache-preparation orchestrator
both reject anything other than exactly one modelpoint; the orchestrator checks
this before starting any precompute job.

## LSMC-policyholder Stackelberg optimiser

[`optimize_crediting_rate_bellman.py`](../code/portfolio_simulations/optimize_crediting_rate_bellman.py)
is the strict cache-reader LSMC-policyholder entry point. It delegates to
[`optimize_crediting_rate_lsmc.py`](../code/portfolio_simulations/optimize_crediting_rate_lsmc.py),
which fits separate follower and leader objectives.

### Policyholder follower

For a supplied cap environment, the follower maximises the risk-neutral present
value of policyholder cashflows. Its current ordered annual action set is:

| Phase | Actions |
|---|---|
| Growth | `WAIT_FOR_ONE_YEAR`, `START_INCOME_NOW` |
| Income | `CONTINUE_FOR_ONE_YEAR`, `FULL_WITHDRAWAL_NOW` |

Partial withdrawal is excluded from the current optimal action set. Statistical
lapse and withdrawal functions are replaced, not layered on top of the LSMC
actions. Whole economic paths are allocated to folds so continuation values for
a held-out fold do not use that fold's outcomes.

The follower solves an ordered multiple-stopping problem. Waiting in Growth
includes the value of later Income actions; fitting election and surrender as
independent options would omit that interaction.

### Insurer leader

The leader fits cap-specific insurer action values after the follower response.
The fast default screens a coarse cap grid with a cap-randomised follower and
performs fresh cap-specific follower fits for the leading fixed-cap finalists.
The full grid and full finalist refit remain explicit options.

The cap-randomised response surface is currently a **validation-only research
candidate**. Although the combined follower action layer is present, the runner
deliberately prevents adaptive deployment until joint leader/follower on-policy
iteration and the complete three-seed Election/Income/combined validation
contract have been implemented. The deployable result is therefore the
prevalidated best fixed cap when the primary behaviour mode is LSMC.

## Sample semantics

The two optimiser families now have deliberately different sample semantics.

| Workflow | Samples | Interpretation |
|---|---|---|
| Dynamic customers / Time-0 Management LSMC | One complete Q sample shared by fitting, candidate ranking and fixed caps | Today's risk-neutral CSM valuation, with MLL-FPAR and penalised-score sensitivities reported secondarily; no OOS, forward roll, deployment or regulatory-capital claim |
| Customer-LSMC Stackelberg research | Its separately documented training and benchmark roles | Follower/leader research subject to that workflow's deployment restrictions |

For the current Dynamic workflow, using the same sample is the requested
estimand rather than a validation shortcut. Its output records `oos_used=false`,
`forward_roll_used=false`, `deployment_strategy_output=false` and
`model_point_count=1`. The first Time-0 action-cell diagnostics explain the
valuation but are not an operating schedule or recommendation.

## Exact Q-cache contract

Optimisation is market-consistent and read-only with respect to Q caches.
The Dynamic Time-0 workflow requires one exact market entry for its one complete
sample. Other workflows require a separate exact entry whenever their path
count, market seed, horizon, substeps, market stress or market inputs differ.
Conditional-MC hedge pricing additionally requires the exact market-path
fingerprint, allocation and complete cap grid.

Only
[`precompute_q_market_and_hedge_cache.py`](../code/portfolio_simulations/precompute_q_market_and_hedge_cache.py)
may create entries below `results/cache/q_market_paths` and
`results/cache/q_hedge_prices`. `mc_conditional` never falls back silently to
Black–Scholes. `moment_matched_bs` is an explicit proxy choice; the under-year
DVA mark remains a separate moment-matched approximation.

Changing mortality, longevity or expense assumptions does not change the
market-cache key. Changing the market seed, path count, horizon, market stress
or market inputs does. Changing the allocation or cap grid requires a new hedge
cache even when the market cache can be reused.

The installed `optimise-crediting-dynamic` and `optimise-crediting-lsmc`
commands route through
[`run_crediting_rate_optimisation.py`](../code/portfolio_simulations/run_crediting_rate_optimisation.py).
That orchestrator derives the exact horizon, required path counts, seeds and cap
grid from the forwarded optimiser arguments. For the Dynamic route it first
hard-checks exactly one modelpoint and then prepares only the single
`(n_paths, seed)` Time-0 sample. It invokes the sole authorised precompute runner
for each required exact sample and starts the strict reader only after all
entries validate successfully. For `mc_conditional` it enforces both cache
requirements; for explicitly selected `moment_matched_bs` it prepares only the
market cache and labels pricing as a proxy. Direct execution of either optimiser
implementation file never creates or repairs a cache. The Customer-LSMC console
route enters through the Bellman wrapper and therefore cannot silently switch
to statistical Dynamic Policyholder behaviour.

## Outputs and interpretation

The Dynamic Time-0 reader writes:

- `fixed_cap_time_zero_results.csv` for the complete fixed grid;
- `management_lsmc_time_zero_policy_class_candidates.csv` for every finished
  support policy, its primary CSM and secondary FPAR diagnostics; new runs also
  retain all 14 anchored unscaled value-vector fields so a
  later objective sensitivity cannot detach a winner from its component data;
- `management_lsmc_time_zero_action_cell_diagnostics.csv` for the first Time-0
  action cells, explicitly as diagnostics rather than a deployment schedule;
- `management_lsmc_time_zero_regression_diagnostics.csv` for support and
  clipping checks;
- `time_zero_flexibility_comparison.csv` for the aggregate best-fixed versus
  flexible comparison;
- `time_zero_csm_component_comparison.csv` for the nine signed CSM cashflow
  components, the four CSM formula subtotals and their exact flexibility
  impacts;
- `time_zero_mll_future_profit_risk_component_comparison.csv` for Base/Stress
  CSMs, all lapse candidates, the binding lapse module, correlated MLL-FPAR and
  an exact three-module Shapley allocation of the proxy change; the old
  `time_zero_mll_component_comparison.csv` name remains a compatibility copy;
- the value vector, run manifest, summary, log and two plots.  The first plot
  shows the aggregate CSM/MLL-FPAR comparison.  The second is component-focused: a
  CSM waterfall bridges best fixed to flexible through all nine signed
  cashflow changes; an MLL-FPAR waterfall bridges the correlated proxy through
  Mortality, Longevity and binding-Lapse Shapley effects; and a supporting bar
  chart shows the absolute standalone Mortality, Longevity and binding-Lapse
  inputs at both endpoints.

The summary records one modelpoint, one Q sample, current-curve Time-0
discounting, dynamic customers, no Customer LSMC, no OOS and no forward roll.
It reports the primary CSM change plus absolute MLL-FPAR, penalised-sensitivity
and ratio changes. The first action is explanatory state, not an
instruction to deploy that cap.  CSM component impacts are directly additive.
Raw MLL module changes are not additive because the lapse amount is a maximum
and final MLL-FPAR is a correlated norm. Its waterfall therefore uses the exact
three-player Shapley allocation over all six module-change orders; the three
effects sum to the change in correlated MLL-FPAR without an order-dependent residual.

`--candidate-policy-class NAME` is a targeted payload-recovery mode. It fits the
fixed anchor and only the named additive policy class, skips the conditional-
ratio heuristic and all other candidate chains, and marks the resulting grid as
incomplete. It is intended only when a completed full-grid run has already
established the candidate selection. `--report-from-run RUN_DIR` is still
lighter: it reads the completed comparison and component CSVs, adds canonical
FPAR/status fields, and regenerates the aggregate and waterfall graphics
without market loading, projection or an LSMC fit.

The Customer-LSMC Stackelberg implementation retains its own policy and
validation outputs. They must not be used to reinterpret the Dynamic Time-0
result.

## Current Time-zero result

Completed full-grid run `20260714T084838.270769Z` uses exactly one modelpoint
(`ALT4-01`), 4,200 Heston-Hull-White Q paths with market seed 2026, the current
Australian curve and exact path-congruent market and hedge caches. Statistical
Dynamic customer behaviour is active and Customer LSMC is false. The fixed caps
and all 23 Management-LSMC chains use the same complete sample.

The completed fit was produced before the final selection-layer correction and
its manifest therefore records the earlier best-fixed CSM floor. Aggregate CSM
and MLL-FPAR scores for all 22 fitted candidates were stored before that
screen. Pure CSM ranking selects the `base_csm` support policy and the 0.25%
fixed cap. These endpoints also won under the earlier 6%-penalised sensitivity,
so the corrected selection needs no refit or projection rerun.

The original artefacts did not contain the complete 14-value payload of the
subsequently selected `base_csm` policy: their standalone value-vector JSON
belonged to the earlier balanced-stress candidate. Targeted recovery run
`20260714T151746.544341Z` therefore used the identical cached Q sample and fit
only the fixed anchor and `base_csm` chain. It completed in 99.6 seconds instead
of repeating the 766-second full search. Its recovered CSM and MLL-FPAR equal
the parent candidate values exactly. Report-only run `20260714T152213.374326Z`
then generated the reviewed PNG/SVG files in 2.3 seconds without valuation work.

The best fixed cap is 0.25%, with primary CSM AUD 52,151.2701, MLL-FPAR AUD
25,057.4801, secondary risk-penalised CSM AUD 50,647.8213 and CSM/MLL-FPAR
2.0812656. The selected `base_csm` policy has CSM AUD 103,840.3807, MLL-FPAR
AUD 45,213.1339, risk-penalised CSM AUD 101,127.5926 and CSM/MLL-FPAR
2.2966862. Relative to best fixed, the primary CSM uplift is AUD 51,689.1106;
MLL-FPAR increases by AUD 20,155.6539, the secondary penalised score by AUD
50,479.7713 and the ratio by 0.2154206.

The CSM uplift reconciles through the nine signed ledger changes. Product fees
contribute AUD 1,344.3244, LIP fees AUD 5,153.2436, money-market/hedge income
AUD 50,917.8438, retained MVA AUD 50.3130 and lower guarantee claims AUD
33,763.9078. Additional operating expenses reduce CSM by AUD 96.1875 and
additional option/hedge costs by AUD 39,444.3346; APS and other insurer-funded
benefits are unchanged. In the current sold-cap-leg configuration retained
above-cap hedge gain is zero, so the money-market/hedge-income movement is the
money-market backing-income effect.

For MLL-FPAR, the raw longevity loss increases from AUD 9,614.3727 to AUD
10,275.1919 and binding lapse from AUD 20,860.5080 to AUD 41,536.1523. The
mass-lapse proxy binds at both endpoints; lapse-down falls from AUD 3,969.2963
to zero and lapse-up remains zero. Exact three-player Shapley attribution assigns
AUD 0 to mortality, AUD 347.3806 to longevity and AUD 19,808.2733 to lapse.
These effects include correlation and diversification and sum to the AUD
20,155.6539 change in correlated MLL-FPAR within numerical tolerance.

Mortality is zero after the adverse positive-part, not because of the
correlation matrix. Its signed base-minus-stressed CSM effect is AUD −6,694.31
for fixed and AUD −6,487.52 for flexibility, so mortality is favourable for
this modelpoint and is clipped to zero before aggregation. The non-zero
longevity effects arise because longevity reduces CSM. The correlation matrix
is an illustrative research assumption, not an APRA-prescribed matrix.

This is evidence of a possible CSM and proxy-risk-efficiency benefit from the
annual reset right, not a deployment or capital result. The result is the
maximum CSM within the fitted policy class, not a global optimum, and is
in-sample by design. The 6% penalty and partial MLL-FPAR scope are research
assumptions; material regression clipping requires path-count, basis and proxy
sensitivity before a stronger economic conclusion.

For the LSMC-policyholder optimiser, adaptive leader deployment is intentionally
blocked by code pending the additional on-policy and multi-seed validation work
described above. Accordingly, this repository does not currently publish an
optimal first-year adaptive cap or a positive adaptive-cap value claim.

Changing the ESG—for example removing stochastic volatility or stochastic
rates—can be a useful predeclared model-risk experiment if regression support
remains poor. It creates new exact cache identities and must be reported as a
separate sensitivity rather than blended into the base Time-0 result.
