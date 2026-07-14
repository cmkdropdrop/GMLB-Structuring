# Policyholder Behaviour

## Decisions in scope

The repository concentrates on two forms of behaviour:

- the annual decision to leave Growth and start lifetime income;
- voluntary actions in Income, especially full withdrawal and the amount of an
  excess withdrawal.

Growth-phase withdrawals are prohibited by the product. Mortality is a separate
decrement and is never fitted as voluntary behaviour.

Two alternative models are used: transparent statistical dynamic functions and
policyholder-value-maximising LSMC.

## Statistical dynamic behaviour

The dynamic model is intended to resemble common actuarial behaviour functions:
it starts from a duration-dependent baseline and modifies it through observable
contract states. It is not calibrated to company experience.

### Moneyness

The relevant signal depends on the decision. For income lapse, guarantee
moneyness compares the economic value of remaining guaranteed income with the
cash value available on surrender. The implementation uses a clipped log ratio,
which is stable around one and treats proportional deviations symmetrically.

A high-value guarantee reduces the propensity to surrender. A high account
value relative to the guarantee can increase the attractiveness of extracting
funds, particularly because the fixed income has no ratchet.

### Proportional-hazard response

For a baseline annual probability $p_0$, the model first converts the
probability to an integrated hazard and applies a multiplicative predictor:

$$
h=h_0\exp(\beta_m m+\beta_p z+\beta_{mp}mz+\beta_{MVA}s),
\qquad p=1-e^{-h}.
$$

Here $m$ is clipped log moneyness, $z$ is clipped log premium relative to a
reference premium, and $s$ is an optional MVA signal. Floors and caps limit the
response. Annual probabilities are converted to coherent monthly conditional
probabilities by the projector.

### Performance-sensitive lapse

Income lapse also contains a separate performance cause. The signal is the
positive gap between trailing gross reference-fund performance and the return
credited to the customer. A deadband avoids reacting to immaterial differences.
The excess hazard rises with the gap but is attenuated when the remaining
guarantee is valuable. Ordinary and performance exits are combined as competing
risks so the total probability remains bounded and cause diagnostics reconcile.

This signal uses only the customer reference fund and credited history. It does
not use the insurer's backing return or hedge P&L.

### Income take-up

The baseline take-up schedule is conditional on still being in Growth. Dynamic
take-up applies a state response at each eligible anniversary, subject to:

- the minimum one-year growth period;
- survival to the election time;
- one irreversible election;
- automatic start at the contractual age backstop.

### Excess withdrawal

The model separates event probability from conditional utilisation. A bounded
fractional-logit response changes the conditional withdrawal fraction with
moneyness and related state variables. The projector then applies contractual
minimum transaction, residual account-value, MVA and proportional income-
reduction rules.

### Competing actions

Full withdrawal terminates the contract and guarantee. Partial withdrawal
changes account value and future income but keeps the contract in force. The
monthly state machine applies event eligibility and ensures that no path is
simultaneously counted in mutually exclusive voluntary exits.

## Optimal LSMC behaviour

The optimal model asks which admissible action maximises the policyholder's
risk-neutral discounted benefits within a fitted basis. It replaces statistical
voluntary actions; the two models are not applied on top of one another.

### Action set

| Phase | Decision time | Current actions |
|---|---|---|
| Growth | Policy anniversary | Wait one year; start income now |
| Income | Policy anniversary | Continue one year; full withdrawal now |

Partial withdrawal is deliberately excluded from the current LSMC action set.
This keeps the ordered multiple-stopping problem identifiable and matches the
validated portfolio workflow.

### Backward induction

For each decision date, regression estimates the continuation value conditional
on state observable at that date. Immediate exercise value is evaluated from
the complete contractual cashflow. The selected action is the one with the
larger fitted policyholder value, subject to an exercise buffer based on
regression error.

Growth election and income surrender are fitted as one ordered policy: the value
of waiting in Growth includes the later optimal Income actions. Treating them as
independent options would miss this interaction.

### Cross-fitting and validation

Whole economic paths, not individual rows, are assigned to folds. Fitted values
for a held-out fold must not use that fold in the regression. Training, policy
validation and final evaluation use distinct market, take-up and mortality seed
namespaces.

The candidate is compared with predeclared fixed-behaviour baselines. If a
validation gate fails, the final rollout uses the recorded valid fallback. A
failed candidate must not be labelled as the deployed optimal policy.

### Interpretation

The result is a fitted lower bound within the chosen basis, action frequency and
action set. It is sensitive to path support and regression quality. It does not
prove globally rational behaviour, and Q-optimal exercise should not be
interpreted as an empirical forecast.

## Diagnostics

Publishable behaviour results should include:

- eligible exposures and action frequencies by policy year;
- income-election distribution;
- ordinary and performance lapse causes;
- moneyness distribution at decisions;
- regression rank, condition number, RMSE and held-out fit metrics;
- training/validation/evaluation seed identities;
- candidate and actually deployed policy labels;
- comparison with deterministic or no-voluntary-action controls.

Zero action frequency is not automatically evidence of model stability: it may
reflect economic dominance, insufficient support, an invalid fit or a fallback.

## Inputs and limitations

The statistical parameters in `input_data/dynamic_behaviour/` are versioned
uncalibrated proxies. Low/base/high sets are model-risk sensitivities, not
confidence intervals. The LSMC model likewise depends on simulated state support
and the predeclared basis. Production use would require experience calibration,
governance, stability monitoring and an explicit treatment of customer tax and
advice effects.
