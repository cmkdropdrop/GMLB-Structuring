# Crediting-Rate Optimisation

## Scope and terminology

The optimisation studies annual management discretion over the customer's
Maximum Return. Workflow names call this quantity the **crediting rate**, but
the contractual payoff is a floor-at-zero, cap-at-\(C_y\) annual index credit:

\[
g_y=\min\!\left(\max(R_y^{fund},0),C_y\right),
\qquad C_y\in\mathcal C.
\]

The standard full action grid is
\(\mathcal C=\{0.25\%,1\%,2\%,\ldots,20\%\}\). The LSMC-policyholder runner
also offers a predeclared coarse screening grid for faster research runs. The
6% case-study cap remains the contractual base; optimisation grids are
counterfactual management-action studies and do not reprice all other product
terms to be budget neutral.

There are two distinct optimisation questions:

1. What cap policy maximises insurer CSM proxy when policyholders follow the
   statistical dynamic behaviour model?
2. What cap policy is attractive when policyholders themselves respond through
   a policyholder-value-maximising LSMC follower?
3. Does the fixed cap selected from a design grid remain attractive after its
   mortality, longevity and lapse capital exposure is recognised?

The insurer and policyholder objectives are never blended.

## Insurer objective

At time zero the optimiser maximises

\[
J(\pi)=\mathbb E^{\mathbb Q}\!\left[
PV(F)+PV(O)-PV(K)-PV(C)\mid \pi
\right],
\]

where \(\pi\) maps observable pre-action state to an annual cap and:

| Symbol | CSM leg | Main contents |
|---|---|---|
| \(F\) | Fee Income | Product and lifetime-income fees |
| \(O\) | Other Income | Money-market backing income, MVA/other retained margins and explicitly retained hedge gain where applicable |
| \(K\) | Claims | Guarantee shortfalls and other identified insurer-funded benefits |
| \(C\) | Costs | Acquisition/maintenance expense and the complete option package |

The option package includes fair value, the configured percentage markup on
fair option value and the annual hedge-reference management fee. The standard
hedge buys the zero-strike return call and sells the call at the customer cap in
the capital market. Consequently a higher cap normally costs more. Customer
benefits paid from the account value are not counted again as insurer claims.

The code labels \(J\) as a market-consistent new-business CSM proxy before Risk
Margin. It is not a complete IFRS 17 CSM.

### Capital-aware fixed-design selector

The third question is handled by the Dynamic-only
[`run_crediting_rate_capital_analysis.py`](../code/portfolio_simulations/run_crediting_rate_capital_analysis.py),
not by inserting a non-additive ratio into the annual Bellman recursion. It
revalues each fixed cap under mortality, longevity and permanent lapse-up/down
stresses, adds the explicitly labelled model-point mass-lapse proxy, aggregates
the MLL research capital amount and ranks the supplied grid by

\[
J^{capital\ adjusted}(C)=J(C)-hK_{MLL}(C).
\]

The current hurdle \(h=6\%\) is a one-year capital charge. `J / K_MLL` is a
secondary lifetime value-to-capital diagnostic and is not annualised RAROC. The
runner hard-blocks Policyholder LSMC, auto-prepares missing exact cache entries
through the sole authorised precompute runner, and then launches only strict
Dynamic readers.

This is a candidate-set selector over fixed product designs. A genuinely
capital-aware adaptive policy requires each frozen adaptive candidate and all
fixed comparators to be stress-revalued on separate selection/validation
samples. The annual regression cannot be called globally capital-optimal merely
because a CSM-trained candidate later has an attractive capital ratio.

## Decision timing and information

The management action is annual. At anniversary \(y\), the projector applies
events in this economic order:

1. finish the previous crediting year and apply its protected return;
2. post accrued product and lifetime-income fees;
3. process mortality and contractual survivor treatment;
4. permit an eligible Growth-to-Income election;
5. choose and announce \(C_y\), then purchase the new annual hedge;
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
account value per initial premium as a storage inventory \(A_y\) and writes the
recursion schematically as

\[
V_y(A_y,X_y)=\max_{c\in\mathcal C}
\left\{r_y(A_y,X_y,c)+
\mathbb E^{\mathbb Q}\!\left[
V_{y+1}(A_{y+1},X_{y+1})\mid A_y,X_y,c
\right]\right\}.
\]

Here \(X_y\) is exogenous market/portfolio state and the monthly projector
generates both the realised one-year insurer reward \(r_y\) and realised next
inventory \(A_{y+1}\). Control-randomised cap histories, including a
persistent-exploration subset, provide state/action support.

Account value is placed on an adaptive quantile grid. At each node the
continuation regression uses the compact economic basis

\[
\phi(X_y)=\{1,\ \text{ATM one-year call},\
\text{reference-fund level},\ \text{overnight rate}\}.
\]

The action-Q regression is fitted directly to the pathwise Bellman target

\[
Y_{i,y}^{c}=r_{i,y}^{c}
+\widehat V_{y+1}\!\left(A_{i,y+1}^{c},X_{i,y+1}\right),
\]

where the next-year grid value is interpolated at that path's **realised** next
account value. There is no separate regression for the conditional mean reward
or account-value transition. This avoids evaluating a nonlinear continuation
surface at a conditional-mean inventory, which would introduce a Jensen-type
approximation.

Both fit and frozen deployment use the same six-column direct-Q basis

\[
\{1,\ z(\text{ATM call}),\ z(\text{fund level}),\ z(r),\ z(A),\ z(A)^2\}.
\]

There is no second projection onto a larger rollout basis and no second argmax.
Values are interpolated between inventory nodes; the inter-node difference is
the discrete shadow value of one additional unit of account value. Component
envelopes and local action masks prevent an unstable regression from
manufacturing negative claims/costs or forcing every state to use one globally
failed action.

Each complete market path receives one immutable outer-fold identity for the
entire backward chain. A held-out path is excluded from every scaling, grid,
continuation and action-Q fit at every policy year; it cannot leave and later
re-enter the training set through the recursion. Final policy value comes from
a causal forward rollout, not from the in-sample Bellman estimate.

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

## Sample separation and deployment

Both optimisation families distinguish four roles:

| Sample | Permitted use | Prohibited use |
|---|---|---|
| Control-randomisation training | Fit reward, transition, continuation and policy regressions | Publish its fitted value as OOS performance |
| Fixed-cap selection | Select the fixed comparator from the declared grid | Tune the adaptive validation gate |
| Adaptive validation | Decide whether the fitted adaptive policy can replace the fixed comparator | Repair the policy using final-evaluation outcomes |
| Final evaluation | Estimate the performance of the policy already selected on validation | Select caps, features, regularisation or fallback |

Within a sample, common random numbers make the adaptive-minus-fixed difference
paired. Let \(\Delta_i\) be that pathwise/paired portfolio difference. The
validation rule requires operational diagnostics to pass and

\[
\overline{\Delta}_{val}>1.96\,
SE(\Delta_{val}).
\]

The dynamic optimiser also requires an executable locally masked policy and a
converged causal rollout. The LSMC-family gate additionally requires stable
insurer regressions and a policyholder validation result that is not inferior
to the declared Continue control. Structural deployment restrictions override
an otherwise positive statistical gate.

If any required gate fails, the selected fixed cap is deployed on the final
sample. In that case:

\[
\Delta^{flex}_{deployed}=0.
\]

The rejected adaptive candidate may still be reported as a diagnostic, but it
must be labelled rejected and cannot support a claim that flexibility created
value.

## Exact Q-cache contract

Optimisation is market-consistent and read-only with respect to Q caches.
Training, fixed-cap selection, validation and evaluation require their own exact
market entries whenever path count, market seed, horizon, substeps, market
stress or market inputs differ. Conditional-MC hedge pricing additionally
requires the exact market-path fingerprint, allocation and complete cap grid.

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
That orchestrator derives the exact horizon, sample path counts, seeds and cap
grid from the forwarded optimiser arguments. It invokes the sole authorised
precompute runner for each exact sample and starts the strict reader only after
all required entries validate successfully. For `mc_conditional` it enforces
both cache requirements; for explicitly selected `moment_matched_bs` it
prepares and requires only the market cache. Direct execution of either
optimiser implementation file never creates or repairs a cache. The LSMC
console route enters through the Bellman wrapper and therefore cannot silently
switch to statistical dynamic policyholder behaviour.

## Outputs and interpretation

Each optimiser writes a run manifest, `optimization_summary.json`, fixed-cap
checks, policy-by-year files, regression/validation diagnostics, a detailed
`run.log` and plots under its generated `results/runs/` directory. The summary
distinguishes at least:

- raw Bellman or response-surface estimates;
- the adaptive candidate and its validation result;
- the policy actually deployed on final evaluation;
- the best fixed comparator and paired standard error;
- CSM legs and reconciliation gaps;
- cache and sample fingerprints.

The first-year cap should be quoted only from the deployed-policy field. The
primary flexibility result is the paired deployed-minus-best-fixed final
evaluation result, not the highest in-sample action value.

Model simplifications, feature sets, regularisation and validation gates must
be predeclared or justified independently of final-sample outcomes. A simpler
ESG may be studied as model risk, but neither model choice nor cache identity may
be changed after inspecting final performance to manufacture a desired sign for
the flexibility result.

## Current validation status

Dynamic-only capital run `20260714T054131.308036Z` is the current fixed-design
MLL screen. It used 1,000 common evaluation paths, the four-model-point proxy,
the cap grid 0.25%, 1%, 6% and 12%, exact base market/hedge caches and no
Policyholder LSMC. MLL capital was AUD 28,398.52, 25,157.55, 10,772.47 and
9,020.14 respectively. Capital-adjusted CSM retained 0.25% as the selected
grid point: AUD 55,926.55 versus AUD -7,342.90 at the contractual 6% cap.

Relative to 6%, the selected fixed design gains AUD 64,327.01 of CSM while
requiring AUD 17,626.04 more MLL capital. After the one-year 6% charge, the
fixed-design choice value is AUD 63,269.45 per representative contract. The
0.25% and 1% lapse modules are driven by the non-revalued mass-lapse proxy; the
permanent-lapse-only MLL amounts are separately reported. This result therefore
supports a risk/profit trade-off and a positive value of fixed design choice,
not a positive value of annual adaptive discretion.

Dynamic-optimisation run `20260713T233802.157326Z` is a completed current-source
four-model-point proxy study with disjoint training, fixed-selection,
adaptive-validation and final-evaluation samples. The best admissible fixed cap
was the 0.25% lower grid boundary, with a final-evaluation CSM proxy of
AUD 60,125.16 (MC SE AUD 2,481.71). The adaptive candidate failed the held-out
validation gate: its paired delta was AUD -4,934.47 (SE AUD 304.80). On the
untouched final sample its research-only delta was AUD -5,079.89 (SE
AUD 264.76). The deployed policy is therefore the fixed 0.25% fallback and the
validated flexibility value is exactly zero. The figures and compact source
tables are promoted under `results/document_figures/` with hashes and sample
provenance; they do not support a positive flexibility-value claim.

For the LSMC-policyholder optimiser, adaptive leader deployment is intentionally
blocked by code pending the additional on-policy and multi-seed validation work
described above. Accordingly, this repository does not currently publish an
optimal first-year adaptive cap or a positive adaptive-cap value claim.

Changing the ESG—for example removing stochastic volatility or stochastic
rates—can be a useful predeclared model-risk experiment if LSMC support remains
poor. It creates new exact cache identities and must not be chosen after looking
at final-evaluation performance merely to rescue a failed policy.
