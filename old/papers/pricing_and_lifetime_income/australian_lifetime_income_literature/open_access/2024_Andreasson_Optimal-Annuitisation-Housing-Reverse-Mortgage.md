Source URL: https://www.wu.ac.at/fileadmin/wu/d/i/statmath/Research_Seminar/SS_2024/2024_06_Shevchenko.pdf
Note: Freely-available academic document (author's WU Wien research-seminar presentation, 12 June 2024) covering the paper "Optimal annuitisation, housing and reverse mortgage in retirement in the presence of a means-tested public pension" (Andreasson & Shevchenko, European Actuarial Journal 14:871-904, 2024). The published journal article and the SSRN abstract page (abstract_id=3174459) are not open access; this presentation is the freely-available full-text source.

---

Optimal annuitisation, housing and reverse mortgage
in retirement in the presence of
a means-tested public pension

Pavel V. Shevchenko

Actuarial Studies and Business Analytics, Macquarie University Business School, Australia
Centre for Risk Analytics www.mq.edu.au/research/centre-for-financial-risk

12 June 2024
Vienna University of Economics and Business - WU Wien

References (key related work):
- J.G. Andreasson and P.V. Shevchenko (2022). A bias-corrected Least-Squares Monte Carlo for solving multi-period utility models. European Actuarial Journal 12, pp. 349-379.
- J.G. Andreasson and P.V. Shevchenko (2024). Optimal annuitisation, housing and reverse mortgage in retirement in the presence of a means-tested public pension. European Actuarial Journal. DOI: 10.1007/s13385-024-00379-3.
- J.G. Andreasson, P.V. Shevchenko, and A. Novikov (2017), Optimal Consumption, Investment and Housing with Means-tested Public Pension in Retirement. Insurance: Mathematics and Economics 75, 32-47.
- J.G. Andreasson and P.V. Shevchenko (2017). Assessment of Policy Changes to Means-Tested Age Pension Using the Expected Utility Model: Implication for Decisions in Retirement. Risks 5, 47:1-47:21.

== Mathematical Problem Definition ==

Let (Omega, F, {Ft}, P) be a filtered complete probability space and Ft represents the information available up to time t. All processes are adapted to {Ft}.

Notation:
- Controlled state variable X = (Xt), t = t0,...,T
- Control pi = (pi_t), t = t0,...,T
- Random disturbance Z = (Zt), t = t0,...,T
- State variable evolution X_{t+1} = T(Xt, pi_t, Z_{t+1})

Objective: maximise the expected value of the total reward
V_{t0}(x) = sup_pi E[ beta^{T-t0} G_T(X_T) + sum_{t=t0}^{T-1} beta^{t-t0} R_t(X_t, pi_t) | X_{t0} = x ]
where G_T and R_t are functions satisfying integrability conditions and beta is discounting factor.

Solved with backward recursion of the Bellman equation:
V_T(x) = G_T(x)
V_t(x) = sup_{pi_t} { R_t(x, pi_t) + E[ beta V_{t+1}(X_{t+1}) | X_t = x; pi_t ] }
Optimal control: pi*_t(x) = arg sup_{pi_t in A_t} { R_t(x, pi_t) + E[ beta V_{t+1}(X_{t+1}) | X_t = x; pi_t ] }
Numerical methods (LSMC - Longstaff and Schwartz 2001; Tsitsiklis and Van Roy 2001) favoured as state/control dimension grows.

== Motivation ==
- Australia's accumulation benefit pension system is still young, but superannuation assets already accumulated $2.7tn in June 2018 ($3.5tn in March 2024, 4th largest in the world).
- More retirees due to increased life expectancy and ageing population. Currently 15% of population is 65+.
- Age and Service Pension payments will change from 2.9% of GDP in 2015 to 3.6% in 2055.
- Social security and welfare is 38% of taxpayers money in 2018-19 Australian government budget.
- Limited knowledge amongst retirees/advisors to manage funds and Age Pension (Spicer et al., 2013).
- Modelling consumption, bequest, home ownership, and investment is important for retirees and the Australian Pension system.

== Australian superannuation ==
Three pillars - superannuation guarantee, private savings and government provided Age Pension.
- Superannuation guarantee contribution rate: 9% in 2002-03 increasing to 11% in 2023-2024, set to reach 12% in 2025.
- Means-tested Age Pension: subject to income-test and asset-test, entitlement age of 65.5 in 2017 (increased to 67 from 2023).
- Family home is excepted from Age pension asset-test.
- Income-test based on actual income, deemed income and drawdown of allocated pension accounts.
- Allocated pension accounts purchased with superannuation, subject to minimum withdrawal rates.

Minimum drawdown rates by age: Age <=64: 4%; 65-74: 5%; 75-79: 6%; 80-84: 7%; 85-89: 9%; 90-94: 11%; >=95: 14%.

Australian pension system parameters (PRE2015 / 2015 / 2017):
- Full Age Pension singles (PS_max): $22,721 / $22,721 / $22,721
- Full Age Pension couples (PC_max): $34,252 / $34,252 / $34,252
- Income-Test: Drawdown / Deemed / Deemed
- Threshold singles (LS_I): $4264 / $4264 / $4264
- Threshold couples (LC_I): $7592 / $7592 / $7592
- Rate of reduction (income) (varpi_I): $0.5 / $0.5 / $0.5
- Deeming threshold singles (kappa_S): - / $49,200 / $49,200
- Deeming threshold couples (kappa_C): - / $81,600 / $81,600
- Deeming rate below kappa (zeta-): - / 1.75% / 1.75%
- Deeming rate above kappa (zeta+): - / 3.25% / 3.25%
- Asset-Test Threshold homeowners singles (LS,h=1_A): $209,000 / $209,000 / $250,000
- Asset-Test Threshold homeowners couples (LC,h=1_A): $296,500 / $296,500 / $375,000
- Asset-Test Threshold non-homeowners singles (LS,h=0_A): $360,500 / $360,500 / $450,000
- Asset-Test Threshold non-homeowners couples (LC,h=0_A): $448,000 / $448,000 / $575,000
- Rate of reduction (asset) (varpi_A): $0.039 / $0.039 / $0.078
(Study uses Australian pension system rules from 2017 as in Andreasson et al. 2017; note rules revised regularly.)

== Expected Utility Model: Base Model Assumptions ==
- Agent (household) is an expected utility maximiser based on hyperbolic absolute risk aversion (HARA).
- Time-separable additive utility functions for consumption, housing and bequest.
- Start at retirement t = t0 where retiree allocates wealth into housing and an allocated pension account. Lives no longer than terminal time T.
- Starts as either a couple or single. Couples have mortality risk (if one spouse dies, becomes single household).
- All wealth held in an allocated pension account, which does not attract taxes on capital gains.
- Each period retiree receives Age Pension, consumes part of wealth, allocates remaining into risky asset and risk-free asset.

State vector X_t = (W_t, G_t, H):
- W_t = current level of wealth
- G_t = life status in G = {Delta, 0, 1, 2} (dead, died this period, alive single, alive couple)
- H = wealth invested in housing at t0

Control variables:
- alpha_t = proportion drawdown of liquid wealth
- delta_t = proportion liquid wealth allocated to risky assets
- rho = wealth allocated to housing only at time t = t0

Wealth process driven by stochastic return Z_{t+1} ~ iid N(mu, sigma^2), deterministic risk-free rate r:
W_{t+1} = (W_t - alpha_t W_t)( delta_t e^{Z_{t+1}} + (1 - delta_t) e^{r_t} )
s.t. C_t = alpha_t W_t + P_t; W_t + P_t - C_t >= 0; W_{t0} = W - H; H in {0, [H_L, W]}.

Per-period utility:
R_t(W_t, G_t, alpha_t, H) = U_C(C_t, G_t, t) + U_H(H, G_t) if G_t = 1,2; = U_B(W_t, H) if G_t = 0; = 0 if G_t = Delta.
Terminal (t = T): R~(W_T, G_T, H) = U_B(W_T, H) if G_T >= 0; = 0 if G_T = Delta.

Full problem:
V~ := max_rho [ sup_pi E^pi_{t0} [ beta_{t0,T} R~(W_T, G_T, H) + sum_{t=t0}^{T-1} beta_{t0,t} R_t(W_t, G_t, alpha_t, H) ] ]

Consumption utility (utility from consumption exceeding consumption floor):
U_C(C_t, G_t, t) = (1 / (psi^{t-t0} gamma_d)) ( (C_t - cbar_d) / zeta_d )^{gamma_d}, d = C if couple (G_t=2), S if single (G_t=1)
where gamma_d in (-inf, 0) is risk aversion, cbar_d the consumption floor, zeta_d scaling factor, psi in [1,inf) health proxy utility parameter.

Bequest utility:
U_B(W_t, H) = (theta/(1-theta))^{1-gamma_S} ( (theta/(1-theta) a + W_t + H)^{gamma_S} / gamma_S )
where a is threshold for luxury bequest, theta in [0,1) degree of altruism.

Housing utility (flow of services approximated with house value):
U_H(H) = (1/gamma_H) ( lambda_d H / zeta_d )^{gamma_H}
where gamma_H housing risk aversion, lambda_d in [0,1] housing preference proportion of market value.

== Age Pension Formula ==
Over 90% of income comes from allocated pensions; assume wealth in asset test equals allocated pension and drawdown is income.
Combined Age Pension formula:
P_t := f(alpha_t, W_t, t) = max[0, min[ P_d_max, min[ P_A(W_t), P_I(alpha_t W_t, t) ] ]]
Asset test: P_A(W_t) = P_d_max - (W_t - L_d_A) varpi_d_A
Income test: P_I(alpha_t W_t, t) = P_d_max - (alpha_t W_t - M(t) - L_{d,h}_I) varpi_d_I
Income test deduction: M(t) = (W_{t0}/e_{t0})(1 + rtilde)^{t0-t}, where e_{t0} is life expectancy at age t0, rtilde inflation.

New Age Pension policy (calibrated model already outdated):
- From 2015, deemed income used in allocated pension (previously drawdown).
- In 2017, asset-test thresholds 'rebalanced' and taper rate doubled.
Deemed income in pension function:
P_I := P_d_max - ( P_D(W_t) - L_d_I ) varpi_d_I
P_D(W_t) = zeta- min[W_t, kappa_d] + zeta+ max[0, W_t - kappa_d]

== Numerical solution ==
- Discretise wealth state W and house state H on log-equidistant grid, solve recursively with backwards induction.
- Family status state G avoided by weighting reward function with survival probabilities in value function.
- Numerical integration by Gauss-Hermite Quadrature, with 5 nodes.
- Interpolation via shape preserving Piecewise Cubic Hermite Interpolation Polynomial (PCHIP).
- Housing decision variable enough to solve at t = t0.

== Calibration ==
- Data from Australian Bureau of Statistics Household Expenditure Survey (HES) 2009-2010, and Survey of Income and Household (SIH) 2009-2010.
- Only a snapshot; does not offer data of cohorts over time.
- Data aggregated on households in retirement not part of work force, split over single (2,038 data points) and couple households (2,017 data points).
- Calibrate parameters via maximum likelihood estimation on consumption and housing samples.

Calibrated utility parameters (Value / Std. Error):
- gamma_S: -2.77 / 0.12
- gamma_C: -2.29 / 0.14
- gamma_H: -2.58 / 0.19
- theta: 0.54 / 0.03
- a: 26,741 / 1,377
- cbar_S: 11,125 / 1,011
- cbar_C: 18,970 / 1,682
- psi: 1.47 / 0.04
- lambda: 0.037 / 0.006

== Conclusions - Calibrated model ==
- Optimal drawdown is highly sensitive to the means test early in retirement due to number of expected years remaining to receive Age Pension, but decreases with time so optimal consumption becomes approximately linear.
- The Age Pension works as a buffer against investment losses; optimal allocation to risky asset increases rapidly when the asset test binds and suggests 100% risky allocation when full Age Pension is received.
- Optimal housing similar between single and couple households in proportion of wealth, but house value differs due to different wealth levels. High allocation for lower wealth matches characteristics where lower-wealth households tend to have the family home as their only asset.

== Least-Squares Monte Carlo method for model extensions ==
The model should be extended with additional deposit account, stochastic interest rate, housing decisions, reverse mortgage, annuitization, etc. Additional states and stochastic variables make a quadrature based numerical solution computationally infeasible.
- LSMC (Longstaff and Schwartz 2001) is an approximate simulation-and-regression method for solving stochastic control problems.
- Original exogenous LSMC extended in Kharroubi et al. (2014) with endogenous state variables and control randomisation.

Objective: maximise V_{t0}(x) = sup_pi E[ beta^{T-t0} G_T(X_T) + sum_{t=t0}^{T-1} beta^{t-t0} R_t(X_t, pi_t) | X_{t0} = x ]

If state variable not affected by control: approximate conditional expectation Phi_t(X_t) = E[beta V_{t+1}(X_{t+1}) | X_t] by regression with independent variables X_t and response beta V_{t+1}(X_{t+1}); approximation denoted Phi^_t.
If state variable affected by control: use control randomization; Phi_t(X_t, pi_t) = E[beta V_{t+1}(X_{t+1}) | X_t; pi_t] estimated by regression of beta V_{t+1}(X_{t+1}) on X_t and randomised pi_t (Kharroubi et al. 2014).

Arguments for LSMC: does not suffer from curse of dimensionality; no restrictions on dynamics of stochastic processes; parametric estimate in feedback form of control (no grid required).
Arguments against LSMC: approximate method only, substantial errors can pile up over multiple periods; computationally intensive; basis functions difficult to find and highly problem specific.

== LSMC for models with Utility Functions ==
Difficult to fit due to extreme curvature over full sample (extreme heteroskedasticity). Proposed method: regress on transformed value function and adjust for retransformation bias.
Define transformation H^{-1} such that H^{-1}(H(x)) = x. Let L(X_t, pi_t) be vector of basis functions and Lambda_t the corresponding regression coefficients:
E[ H^{-1}(beta V_{t+1}(X_{t+1})) | X_t; pi_t ] = Lambda'_t L(X_t, pi_t)
Ordinary linear regression over M independent Markovian paths:
H^{-1}(beta V_{t+1}(X^m_{t+1})) = Lambda'_t L(X^m_t, pi^m_t) + eps^m_t, eps^m_t ~iid F_t(.), E[eps]=0, var[eps]=sigma^2_t
Lambda^_t = argmin_Lambda sum_m [ H^{-1}(V(t, X^m_t)) - Lambda' L(X^m_t, pi^m_t) ]^2

Duan's Smearing Estimate (Duan, 1983): estimate Phi_t(X_t, pi_t) = E[beta V_{t+1}(X_{t+1}) | X_t; pi_t]:
H_B(Lambda'_t L(X_t, pi_t)) := Phi_t(X_t, pi_t) = integral H(Lambda'_t L(X_t, pi_t) + eps_t) dF_t(eps_t)
Using empirical distribution of residuals: eps^^m_t = H^{-1}(beta V_{t+1}(X^m_{t+1})) - Lambda^'_t L(X^m_t, pi^m_t)
Smearing Estimate: H^_B(Lambda^'_t L(X_t, pi_t)) = (1/M) sum_{m=1}^M H(Lambda^'_t L(X_t, pi_t) + eps^^m_t)

Smearing estimate example: regression ln Y_i = beta' X_i + eps_i, estimate E[Y^gamma/gamma]:
(1/n) sum_i (e^{beta^' X + eps^_i})^gamma / gamma = (e^{beta^' X})^gamma / (n gamma) sum_i e^{eps^_i gamma}

Controlled Heteroskedasticity: model conditional variance var[eps_t | X_t, pi_t] = [Omega(L'_t C(X_t, pi_t))]^2 where Omega(.) is positive function, C(X_t, pi_t) vector of basis functions. Smearing Estimate with Controlled Heteroskedasticity:
H^_B(Lambda^'_t L(X_t, pi_t)) = (1/M) sum_m H( Lambda^'_t L(X_t, pi_t) + Omega(L^'_t C(X_t, pi_t)) eps^^m_t / Omega(L^'_t C(X^m_t, pi^m_t)) )

Algorithm LSMC for exogenous state:
Forward simulation: for t=1..N, for m=1..M: X^m_t := T_t(X^m_{t-1}, z_t) [simulate path]
Backward solution: for t=N..0: if t=N: V^_t(X_t) := R_N(X_t); else if t<N: Lambda^_t := argmin sum_m [ Lambda'_t L(X^m_t) - H^{-1}(beta V^_{t+1}(X^m_{t+1})) ]^2; find bias corrected transformation H_B(Lambda^'_t L(X_t)); Phi^_t(X_t) = H_B(Lambda^'_t L(X_t)); for m=1..M: pi*_t(X^m_t) := arg sup_{pi_t in A} { R_t(X^m_t, pi_t) + Phi^_t(X^m_t) }; V^_t(X^m_t) := R_t(X^m_t, pi*_t(X^m_t)) + beta V^_{t+1}(X^m_{t+1})

Pricing Bermudan option using LSMC - numerical example (M sample paths, 20 repetitions; 'exact' price by Binomial Tree = $4.3862):
- M=1,000: V^(0) 4.4984 (0.032); V^(1) 4.4336 (0.038); V^(2) 4.4054 (0.039)
- M=10,000: V^(0) 4.4616 (0.007); V^(1) 4.4161 (0.007); V^(2) 4.3962 (0.008)
- M=100,000: V^(0) 4.4457 (0.003); V^(1) 4.4048 (0.004); V^(2) 4.3857 (0.004)
(V^(0) = standard LSMC; V^(1) = log transformation without bias correction; V^(2) = log transformation with bias correction using smearing estimate.)

LSMC Algorithm: Endogenous state and random control (discretised Kharroubi et al. 2015 with modifications in forward simulation):
Forward simulation: for t=0..N-1, for m=1..M: X^m_t := Rand in X (State); pi~^m_t := Rand in A (Control); z^m_{t+1} := Rand in Z (Disturbance); X~^m_{t+1} := T_t(X^m_t, pi~^m_t, z^m_{t+1}) (Evolution of state).

Regression surface versus realised value (Kharroubi et al. 2014, two versions):
- Regression surface (VFI, value function iteration): V^_t(X_t) = R_t(X_t, pi*_t(X_t)) + Phi^_t(X_t, pi*_t(X_t))
- Realised value (PFI, policy function iteration): V^_t(X_t) = R_t(X_t, pi*_t(X_t)) + beta V^_{t+1}(X_{t+1})
PFI requires recalculation of sample paths for t+1 to T after each iteration backwards in time.

== Retirement Model Extensions ==
Introduce stochastic real interest rate as a Vasicek process, yearly discretised:
r_{t+1} = rbar + e^{-b}(r_t - rbar) + sqrt( sigma_R^2 / (2b) (1 - e^{-2b}) ) eps_{t+1}, eps_t ~iid N(0,1)
where rbar in R+ long term mean, b in (0,1] speed of adjustment, sigma_R volatility.
Introduce separate taxable deposit account W~_t (pension account does not allow deposits in retirement). Always preferred for spending over liquid wealth.

Model Extension: deposit account. Let nu_t be minimum withdrawal rate. If C_t <= W~_t + P_t + nu_t W_t:
W+_t = W_t(1 - nu_t); W~+_t = W~_t + P_t + nu_t W_t - C_t
otherwise: W+_t = W_t + W~_t + P_t - C_t; W~+_t = 0
subject to W~_t + W_t + P_t - C_t >= 0.

Evolution of wealth accounts over (t, t+1):
W_{t+1} = W+_t ( delta_t e^{Z_{t+1}} + (1 - delta_t) e^{rtilde_{t,t+1}} )
W~_{t+1} = W~+_t (delta_t e^{Z_{t+1}} + (1-delta_t) e^{rtilde_{t,t+1}}) - Theta( W~+_t (delta_t e^{Z_{t+1}} + (1-delta_t) e^{rtilde_{t,t+1}}) - W~+_t )
where Theta(x) calculates tax on deposit account earnings. Cash asset annual growing rate rtilde_{t,t+1} = integral_t^{t+1} r_u du; short rate r_t follows Vasicek: dr_t = b(rbar - r_t)dt + sigma_R dB(t).

== Model Extension 1 - Annuities ==
Retiree can at any time t in {t0,...,T-1} make a (non-reversible) decision to purchase an annuity for amount A_t providing annual lifetime payments y_t (constant in real terms) starting from t+1. New state variable Y_t holds size of annuity payments each period: Y_{t+1} = Y_t + y_t, Y_{t0} = 0.

Evolution of pension W_t and deposit W~_t accounts:
If C_t + A_t <= W~_t + P_t + nu_t W_t + Y_t: W+_t = W_t(1-nu_t); W~+_t = W~_t + P_t + nu_t W_t - C_t + Y_t - A_t
otherwise: W+_t = W_t + W~_t + P_t - C_t + Y_t - A_t; W~+_t = 0
Constraint: W_t + W~_t + P_t + Y_t - C_t - A_t >= 0, with A_t >= 0, C_t > cbar_d.
State vector extended to X_t = (W_t, W~_t, G_t, H_t, r_t, Y_t) to find optimal pi_t = (C_t, delta_t, A_t).

Price of annuity: a_t(y) := sum_{i=t+1}^T {}_i p_t^{1-h} J(t, i, y), where J(t, i, y) is price of inflation linked zero coupon bond at time t with maturity i and face value y, {}_i p_t survival probability from year t to i, h = 0.15 price loading. y_t found by solving A_t = a_t(y_t).

Price of a bond with maturity t':
J(t, t', y) = y E^Q~[ e^{-integral_t^{t'} r_tau d tau} ] := y e^{-r(t,t')(t'-t)}
where Q~ is risk-neutral measure. Vasicek risk-neutral process: dr_t = [b(rbar - r_t) - lambda sigma_R] dt + sigma_R dB~(t), lambda market price of risk.
r(t, t') = (- ln A(t,t') + B(t,t') r_t) / (t' - t), B(t,t') = (1/b)(1 - e^{-b(t'-t)})
A(t,t') = exp[ (B(t,t') - t' + t)( rbar - lambda sigma_R/b - sigma_R^2/(2b^2) ) - (sigma_R^2/(4b)) B(t,t')^2 ]
Parameters estimated by two-stage procedure: real r_t process from spot interest rate data, then market price of risk lambda from term structure of zero coupon bonds.

Annuities in the Age pension means tests in 2017:
Annuity income for income test: y_t - a_{t_x}(y_t) / (e_x - t_x), where t_x is annuity purchasing time, e_x life expectancy at t_x.
In asset test, value of annuity assumed equal to original purchase price with linear yearly value decrease until life expectancy age: max( a_{t_x}(y_t) - (a_{t_x}(y_t)/(e_x - t_x))(t - t_x), 0 ).

Annuities means-tests approximation:
Income test: P_I := P_d_max - ( P_D(W_t) + Y_t(1 - Upsilon) - L_d_I ) varpi_d_I, Upsilon = 0.9.
Asset test: P_A := P_d_max - ( W_t + a_t(Y_t) - L_{d,h}_A ) varpi_d_A.

Conclusions - Extension 1 (Annuities):
- It is optimal to annuitise earlier rather than later in retirement (due to the mortality credit). Exception is very poor households.
- Delaying annuitisation leads to less wealth annuitised, but higher annuity payments.
- The means-test decreases the 'demand' for annuities, but does not eliminate it. Retiree with low likelihood to access Age Pension has constant annuitisation rate.
- The mortality credit from the annuity dominates the utility received from bequeathing this wealth. Optimal annuitisation is the same with/out access to a risk-free rate when loading on annuity premium is zero.

== Model Extension 2 - Flexible housing ==
Australian retirees are 'house rich, but asset poor', and can optimise Age Pension payments by overallocating to the family home. Extend model to flexible housing decisions by scaling housing and access to a reverse mortgage.

Reverse mortgage:
- Loan against the home equity up to an age dependent loan-to-value ratio, no amortisation/interest payments required.
- Starts at 20-25% at age 65, increases 1% per year.
- Multiple access options: lump sum, credit line, tenure, etc.
- Interest and fees accumulate, but capped by house value.
- At death (or sale of home) the loan is paid off, any equity remaining returned.

Retiree can at any time up- or down-scale housing with proportion tau_t in [-1, inf], new house valued H_{t+1} = H_t(1 + tau_t). If tau_t != 0, transaction cost applies to current house value.
Retiree can at any time choose proportion l_t in [0, I(t)] up to loan-to-value threshold L_t as a reverse mortgage from home value, adding to outstanding loan state L_t.
Loan-to-value ratio time dependent: L_t = H_t I(t), I(t) = 0.2 + 0.01(min(85, t) - 65).
Loan value state evolves: L_{t+1} = (L_t I{tau_t=0} + l_t H_t(1 + tau_t)) e^{rtilde_{t,t+1} + phi}.

Costs of any decision reflected in wealth process. Define:
b(l_t, tau_t, L_t, H_t) := l_t H_t(1 + tau_t) - I{tau_t != 0}( H_t(tau_t + eta) + L_t )
representing all changes to wealth from house scaling and reverse mortgage decisions, eta proportional transaction cost.

Evolution of pension W_t and deposit W~_t accounts:
If C_t <= W~_t + P_t + nu_t W_t + b(l_t, tau_t, L_t, H_t): W+_t = W_t(1 - nu_t); W~+_t = W~_t + P_t + nu_t W_t + b(...) - C_t
otherwise: W+_t = W_t + W~_t + P_t + b(...) - C_t; W~+_t = 0.

Bequest function includes house asset after reverse mortgage repaid: U_B(W_t + W~_t, max(H_t - L_t, 0)).
State vector extended to X_t = (W_t, W~_t, G_t, H_t, r_t, L_t) to find optimal pi_t = (C_t, delta_t, tau_t, l_t).
Parameters: cost of selling house eta = 6%, interest rate markup phi = 0.0242; risk-free rate parameters b = 0.64, rbar = 0.013, sigma_R = 0.016.

Constraints on control variables:
- Reverse mortgage bounded above: l_t <= max(0, (L_t - L_t I{tau_t=0}) / (H_t(1 + tau_t))).
- If tau_t != 0, any outstanding reverse mortgage must be paid back in full and a new reverse mortgage is available against the new house value.
- House scaling upper bound: tau_t <= (W_t + W~_t - I{tau != 0}(eta H_t + L_t)) / H_t. Lower bound is -1.
- Budget constraint: b(l_t, tau_t, L_t, H_t) + W_t + W~_t + P_t - C_t >= 0.

Conclusions - Extension 2 (Flexible housing):
- The proportion reverse mortgage increases with house value and decreases with wealth (confirms empirical results in Chiang and Tsai (2016)).
- The proportion increases with age; never reaches the LVR (loan-to-value ratio).
- It is never optimal to downsize housing, even when overallocated, unless certain events are incurring significant costs.
- Scaling housing is more costly than reverse mortgages for accessing part of home equity. A reverse mortgage allows the retiree to still receive utility from the larger home.
- Only marginal effect on initial housing allocation with the additional control variables.

== Presenter ==
Prof Pavel Shevchenko, Department of Actuarial Studies and Business Analytics, Macquarie University, Australia. Centre for Risk Analytics; Risk Analytics Lab. email: pavel.shevchenko@mq.edu.au

== References ==
- Chiang, Shu Ling and Ming Shann Tsai (2016), "Analyzing an elder's desire for a reverse mortgage using an economic model that considers house bequest motivation, random death time and stochastic house price." International Review of Economics and Finance, 42, 202-219.
- Duan, Naihua (1983), "Smearing estimate: A Nonparametric retransformation method." Journal of the American Statistical Association, 78, 605-610.
- Kharroubi, Idris, Nicolas Langrene, and H Pham (2014), "A numerical algorithm for fully nonlinear HJB equations: an approach by control randomization." Monte Carlo Methods and Applications, 20, 145-165.
- Kharroubi, Idris, Nicolas Langrene, and Huyen Pham (2015), "Discrete time approximation of fully nonlinear HJB equations via BSDEs with nonpositive jumps." The Annals of Applied Probability, 25, 2301-2338.
- Longstaff, Francis A and Eduardo S Schwartz (2001), "Valuing American Options by Simulation: A Simple Least-Squares Approach." Review of Financial Studies, 14, 113-147.
- Spicer, Alexandra, Olena Stavrunova, and Susan Thorp (2013), "How Portfolios Evolve After Retirement: Evidence from Australia." CAMA Working Papers 2013-40.
- United Nations (2013), World Population Prospects: The 2012 Revision.
