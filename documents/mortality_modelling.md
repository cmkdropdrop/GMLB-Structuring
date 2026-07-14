# Mortality Modelling

## Role in the model

Mortality determines the probability that income remains payable, the timing of
death benefits and the exposure to longevity claims. It affects both statistical
and optimal behaviour workflows but is not itself a policyholder decision.

The implementation is concentrated in
[`mortality.py`](../code/policy_engine/mortality.py), with state application in
[`projection.py`](../code/policy_engine/projection.py) and aggregation in
[`portfolio.py`](../code/policy_engine/portfolio.py).

## Base table

The repository uses an illustrative Gompertz–Makeham basis rather than an
external production mortality table. Age-specific force of mortality is
converted to annual death probability and then adjusted by the configured
improvement convention. The terminal basis forces death in the monthly interval
whose end first reaches the terminal age. The terminal sentinel is not
interpolated into earlier ages.

This basis is a transparent research proxy. It is not calibrated to Australian
insured-life, annuitant or company experience.

## Monthly conversion

One annual conditional probability $q_x$ applies to a policy year. The monthly
conditional probability is chosen so that twelve equal monthly exposures
reconcile to the annual probability:

$$
q_x^{(m)}=1-(1-q_x)^{1/12}.
$$

Where age changes within a monthly interval, the projector follows the policy-
year anchoring and terminal-age convention implemented by the table. Survival
and death masses are reconciled at every step.

## Expected and pathwise treatments

Single-life portfolio valuation can use expected decrements: contract cashflows
are multiplied by surviving exposure. Behaviour training and joint-life logic
also use pathwise random life states where decisions depend on who is alive. The
same underlying annual table and monthly conversion are used in both cases.

## Joint life

For a spouse-continuation contract, primary and spouse deaths are modelled as
independent conditional events. Before income election, the primary life is the
insured policyholder and spouse continuation is not yet effective. At election,
the elected life basis determines the income rate and future survivor coverage.

After election, the projector distinguishes four states:

- both alive;
- primary alive only;
- spouse alive only;
- neither alive.

If the primary dies and `continue income` applies, the locked amount continues
for the surviving spouse. If the lump-sum election applies, the account value is
paid and the policy terminates. Last-survivor death ends continuing income.

The current model omits common mortality shocks, dependence, divorce and later
changes to spouse eligibility.

## Stresses

Mortality and longevity stresses alter the mortality basis, not the Q-market
cache key. A longevity stress reduces death probabilities and generally extends
income exposure; a mortality stress increases death probabilities. The exact
profit effect also depends on account value, death benefits, fees, lapse and
spouse state, so sign is checked through full shock-and-revalue rather than
assumed.

## Projection horizon

Valuation resolves a horizon long enough to cover the insured lives and the
contractual terminal-age treatment. Market paths may extend beyond the final
economically active policy year. Years with no surviving or in-force exposure
must not create fitted behaviour or cap decisions.

## Validation controls

The test suite checks:

- decreasing survival and plausible life expectancy;
- annual-to-monthly probability reconciliation;
- forced terminal death without premature interpolation;
- conditional spouse state at income election;
- primary-death lump-sum and continue-income paths;
- income only for covered month-end survivors;
- mortality, longevity and catastrophe stress direction at table level;
- immutability of mortality arrays passed into projections.

## Limitations and production requirements

Production work would require a governed base table, selection factors,
improvement calibration, credibility, underwriting and socioeconomic effects,
joint-life dependence and validation against observed deaths. None of those
inputs should be inferred from the Australian market curve or equity model
parameters.
