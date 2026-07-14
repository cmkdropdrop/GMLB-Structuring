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

1. What is today's capital-adjusted CSM value of the insurer's right to reset
   the cap each year when Policyholders follow the statistical Dynamic
   behaviour model, with CSM/MLL reported as a secondary efficiency measure?
2. What cap policy is attractive when policyholders themselves respond through
   a policyholder-value-maximising LSMC follower?
3. Does the fixed cap selected from a design grid remain attractive after its
   mortality, longevity and lapse capital exposure is recognised?

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
Management-LSMC workflow, the primary finished-candidate objective is

$$
A_{\lambda}(\pi)=J(\pi)-\lambda K_{\mathrm{MLL}}(\pi),
\qquad \lambda=0.06.
$$

$K_{\mathrm{MLL}}$ is the partial mortality/longevity/lapse research capital
proxy. The 6% coefficient is a one-year research capital charge, not a complete
Risk Margin or regulatory calibration. CSM/MLL is reported as the secondary
capital-efficiency measure

$$
R(\pi)=\frac{J(\pi)}{K_{\mathrm{MLL}}(\pi)},
$$

but it does not select the policy. The calculation uses exactly one modelpoint.

### Time-zero capital-adjusted selector

MLL is formed only after complete Time-0 aggregation. Positive-part stress
losses, the maximum of the lapse stresses and the MLL correlation norm make the
capital charge non-additive. The implementation therefore does not pretend that
$A_{\lambda}$ is a one-year Bellman reward. It fits a predeclared finite class
of additive Base/Stress objectives and ranks each finished 14-value payload on
its actual $J-0.06K_{\mathrm{MLL}}$. CSM/MLL is calculated from the same
payload and reported secondarily.

$$
J_{\alpha,q}=(1-\alpha)J_{\mathrm{base}}
+\alpha\sum_s q_sJ_s,
\qquad \alpha\in\{0,0.25,0.50,0.75,1\}.
$$

The directions are mortality, longevity, lapse up, lapse down and a balanced
four-stress basket. One pure-Base objective plus four positive alpha levels for
each of the five directions gives 21 fitted support policies; one
conditional-ratio heuristic is added. A forced best-fixed chain supplies a
common regression anchor. There is no additional minimum-CSM constraint. Best
fixed is the explicit capital-adjusted comparator and is replaced only by a
strictly higher actual $J-0.06K_{\mathrm{MLL}}$. The ratio is not an additional
selection gate.

The separate Dynamic-only
[`run_crediting_rate_capital_analysis.py`](../code/portfolio_simulations/run_crediting_rate_capital_analysis.py)
remains available for a fixed-design CSM-minus-capital-charge screen. It is an
auxiliary fixed-design workflow using the same 6% research charge; it does not
value the annual reset right.

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
Management-LSMC regressions, the finished-candidate capital-adjusted ranking and
all fixed caps. It does not allocate outer folds, reserve paths or run a causal
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
| Dynamic customers / Time-0 Management LSMC | One complete Q sample shared by fitting, candidate ranking and fixed caps | Today's risk-neutral $\mathrm{CSM}-0.06\,\mathrm{MLL}$ valuation, with CSM/MLL reported secondarily; no OOS, forward roll or deployment claim |
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
  support policy, its primary capital-adjusted score and its secondary aggregate
  ratio;
- `management_lsmc_time_zero_action_cell_diagnostics.csv` for the first Time-0
  action cells, explicitly as diagnostics rather than a deployment schedule;
- `management_lsmc_time_zero_regression_diagnostics.csv` for support and
  clipping checks;
- `time_zero_flexibility_comparison.csv`, the value vector, run manifest,
  summary, log and plot.

The summary records one modelpoint, one Q sample, current-curve Time-0
discounting, dynamic customers, no Customer LSMC, no OOS and no forward roll.
It reports absolute CSM and MLL changes, the primary capital-adjusted uplift and
the secondary ratio change. The first action is explanatory state, not an
instruction to deploy that cap.

The Customer-LSMC Stackelberg implementation retains its own policy and
validation outputs. They must not be used to reinterpret the Dynamic Time-0
result.

## Current Time-zero result

Completed run `20260714T084838.270769Z` uses exactly one modelpoint (`ALT4-01`),
4,200 Heston-Hull-White Q paths with market seed 2026, the current Australian
curve and exact path-congruent market and hedge caches. Statistical Dynamic
customer behaviour is active and Customer LSMC is false. The fixed caps and all
23 Management-LSMC chains use the same complete sample.

The completed fit was produced before the final selection-layer correction and
its manifest therefore records the earlier best-fixed CSM floor. All 22 fitted
candidate payloads were nevertheless stored before that screen. The current
$\lambda=6\%$ rule re-ranks those complete payloads by
$J-0.06K_{\mathrm{MLL}}$ without refitting or rerunning a projection. It selects
the pure `base_csm` support policy; the old CSM floor is not part of this final
selection.

The best fixed cap is 0.25%, with CSM AUD 52,151.2701, MLL AUD 25,057.4801,
primary capital-adjusted CSM AUD 50,647.8213 and secondary CSM/MLL 2.0812656.
The selected `base_csm` policy has CSM AUD 103,840.3807, MLL AUD 45,213.1339,
capital-adjusted CSM AUD 101,127.5926 and CSM/MLL 2.2966862. Relative to best
fixed, the primary uplift is AUD 50,479.7713; CSM increases by AUD 51,689.1106,
MLL increases by AUD 20,155.6539 and the secondary ratio improves by 0.2154206.

This is evidence of a possible capital-adjusted and risk-efficiency benefit from
the annual reset right, not a deployment result. The result is the maximum of
the primary $J-0.06K_{\mathrm{MLL}}$ score within the fitted policy class, not a
global optimum, and is in-sample by design. The 6% charge and partial MLL scope
are research assumptions; material regression clipping requires path-count,
basis and capital-proxy sensitivity before a stronger economic conclusion.

For the LSMC-policyholder optimiser, adaptive leader deployment is intentionally
blocked by code pending the additional on-policy and multi-seed validation work
described above. Accordingly, this repository does not currently publish an
optimal first-year adaptive cap or a positive adaptive-cap value claim.

Changing the ESG—for example removing stochastic volatility or stochastic
rates—can be a useful predeclared model-risk experiment if regression support
remains poor. It creates new exact cache identities and must be reported as a
separate sensitivity rather than blended into the base Time-0 result.
