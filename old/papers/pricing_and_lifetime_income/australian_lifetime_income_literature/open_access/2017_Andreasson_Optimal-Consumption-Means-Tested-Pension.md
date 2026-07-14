https://arxiv.org/pdf/1606.08984
→ https://arxiv.org/pdf/1606.08984

# Optimal Consumption, Investment and Housing with Means-tested Public Pension in Retirement

Johan G. Andréasson \*, Pavel V. Shevchenko †, Alex Novikov ‡

June 30, 2016

### Abstract

In this paper, we develop an expected utility model for the retirement behavior in the decumulation phase of Australian retirees with sequential family status subject to consumption, housing, investment, bequest and government provided means-tested Age Pension. We account for mortality risk and risky investment assets, and introduce a health proxy to capture the decreasing level of consumption for older retirees. Then we find optimal housing at retirement, and optimal consumption and optimal risky asset allocation depending on age and wealth. The model is solved numerically as a stochastic control problem, and is calibrated using the maximum likelihood method on empirical data of consumption and housing from the Australian Bureau of Statistics 2009-2010 Survey. The model fits the characteristics of the data well to explain the behavior of Australian retirees. The key findings are the following: first, the optimal policy is highly sensitive to means-tested Age Pension early in retirement but this sensitivity fades with age. Secondly, the allocation to risky assets shows a complex relationship with the means-tested Age Pension that disappears once minimum withdrawal rules are enforced. As a general rule, when wealth decreases the proportion allocated to risky assets increases, due to the Age Pension working as a buffer against investment losses. Finally, couples can be more aggressive with risky allocations due to their longer life expectancy compared with singles.

Keywords: Dynamic programming, Stochastic control, Optimal policy, Retirement, Means-tested age pension, Defined contribution pension

JEL classification: D14 (Household Saving; Personal Finance), D91 (Intertemporal Household Choice; Life Cycle Models and Saving), G11 (Portfolio Choice; Investment Decisions), C61 (Optimization Techniques; Programming Models; Dynamic Analysis)

<sup>\*</sup>School of Mathematical and Physical Sciences, University of Technology, Sydney, Broadway, PO Box 123, NSW 2007, Australia; email: andreasson.johan@uts.edu.au

<sup>&</sup>lt;sup>†</sup>CSIRO, Australia; University of Technology, Sydney, Australia; email: pavel.shevchenko@csiro.au <sup>‡</sup>School of Mathematical and Physical Sciences, University of Technology, Sydney, Australia; email: alex.novikov@uts.edu.au

# 1 Introduction

The global shift from a defined-benefit to a defined-contribution pension system transfers risk from the corporate sector to households, primarily via the investment and withdrawal decision of pension assets. Australia's move has already accumulated superannuation assets of \$2.02 trillion dollars (ASFA, 2015), making Australia the 4th largest pension fund pool in the world. For retirees, the main difference is that instead of being provided a monthly benefit as they were before, they now receive a lump sum at retirement and are responsible for managing this wealth throughout their lives. The retirees face multiple risks including mortality, longevity and investment risks, as well as regulatory risk such as changes in policies and government provided Age Pension entitlements, which are harder to account for. The long term effects of this new pension system are not yet known, and there is limited knowledge amongst retirees and advisors regarding how to consume and manage the assets. This results in confusion for many retirees (Agnew et al., 2013).

Once retired, Australian retirees tend to keep the same proportion of risky assets as before retirement, even though the exposure decreases with age (Spicer et al., 2013). With no labor income these assets are subject to sequencing risk<sup>2</sup> which is difficult to avoid in the decumulation phase, especially early in retirement (Kingston and Fisher, 2014). Conventional recommendations for asset management can no longer apply in this case, as they are highly dependent on wealth level, age, and Age Pension policies.

The Australian retirement system relies on three pillars - the Age Pension, the superannuation guarantee, and private savings. While the former two are mandatory, private savings are voluntary and are comprised of additional savings/assets such as voluntary superannuation contributions, private investments, and dwelling. The superannuation guarantee mandates that employers contribute a certain percentage of the employee's gross earnings to a superannuation fund, with a current contribution rate of 9.5%. The Age Pension is the government managed safety net, which ensures a retiree meeting the age minimum and passing a means-test<sup>3</sup> is entitled to Age Pension. In the means-test, income and assets are evaluated individually, where a certain taper rate reduces the maximum payments once income or assets surpasses set thresholds (which are subject to family status and homeownership). Income from different sources are also treated differently; financial assets are expected to generate income based on a progressive deeming rate, while income streams such as labor and annuity payments are assessed based on their nominal value. The retiree can be qualified for either full, partial, or no Age Pension. The exact amount they qualify for is determined by the smaller outcome of the income and asset tests.

With around 80% of the Australian population aged 65 or older being entitled to full or partial Age Pension, there is an strong need for a model that both captures the characteristics of Australian data and can explain the behavior of retirees. Empirical data indicates that 75% of retired households are homeowners, where the home accounts for 80% of the total wealth in middle-wealth quartiles and almost all of the wealth in

 $<sup>^{1}</sup>$ In Australia, the arrangement for people to accumulate funds for income in retirement is referred to as superannuation.

<sup>&</sup>lt;sup>2</sup>Sequencing risk refers to unfortunate timing of cash flow in the investment portfolio. Drawdown after negative investment returns will have a greater impact on the long term growth of the portfolio compared with drawdown after positive investment returns.

<sup>&</sup>lt;sup>3</sup>Age Pension rates published by Centrelink as of September 2015. (www.humanservices.gov.au/customer/services/centrelink/age-pension)

the lower quartile<sup>4</sup>. Consumption tends to decrease with age and converges towards a consumption floor. It is argued that this decline in consumption is due to declining health of retirees, which reduces their capacity for activity (Clare, 2014; Yogo, 2011), or retirees having fewer resources reserved for consumption due to longevity risk (Milevsky and Huang, 2011). Higgins and Roberts (2011) find that the rate of decline with age is also dependent on wealth, and expenditures tend to converge towards a constant level as the retiree ages. A model that properly captures these characteristics is required to estimate the wealth needed in retirement, and to forecast Age Pension budgets and policy changes from a government perspective.

It is common to model decisions and behavior in retirement using expected utility maximization models based on dynamic programming techniques. Such models stem from the seminal work by Yaari (1964, 1965), which was later extended by Samuelson (1969) and Merton (1969, 1971) who studied the problem in relation to optimal portfolio allocation. Since then, a vast amount of research has been carried out on various extensions and alternative models, where the decumulation phase of life-cycle modeling has been a topic of interest. That said, there is limited research where the Age Pension is based on a means-tested pension function. Research has mainly focused on the effect on the economy from different means-tested policies and the impact on savings (Hubbard et al., 1995; Hurst and Ziliak, 2004; Neumark and Powers, 1997 to name a few).

In Australia, which is a very special case of means-testing, there have been two main approaches to model Age Pension — expected utility maximization via dynamic stochastic programming, or dynamic general equilibrium (DGE) models. The DGE models tend to focus on how policy-changes affect welfare. Using overlapping generations DGE models, Kudrna and Woodland (2011a) and Tran and Woodland (2014) evaluate the effect of the means-tests and taper rate changes on the welfare outcome, while Kudrna and Woodland (2011b) examine the implication of the recent Australian pension reform extended with a housing market which is further extended in Kudrna (2014).

While DGE models tend to analyze the effects on the economy, dynamic stochastic programming models focus on the retiree as an individual. Hulley et al. (2013) investigate the effect of the Age Pension on consumption and investments under constant relative risk aversion (CRRA) utility, while Bateman et al. (2007) compare the effect of modeling optimal consumption and investment with hyperbolic absolute risk aversion (HARA) utility against CRRA. Ding (2013) captures the behavior of Australian retirees with regards to consumption, portfolio allocation, and housing in a semi-analytical HARA utility model. Iskhakov et al. (2015) models the behavior with a HARA utility maximization approach, but with the purpose of investigating how annuity purchases are affected by different preferences and scenarios. The reason HARA is preferred over CRRA in the majority of research is the presence of a consumption floor, which implies a simplified preference for risk as the consumption floor needs to be maintained. This indicates that financial advice is non-scalable with respect to wealth.

In addition to the aforementioned, the most important extensions to traditional utility maximization models from an Australian retirement perspective include housing (Yogo, 2011; Cho and Sane, 2013), bequest (Lockwood, 2014; De Nardi, 2004; Ameriks et al., 2011) and health (Yogo, 2011).

A limiting factor in models is the desire for analytical solutions. For an analytical solution to exist it either constrains the number of stochastic variables allowed, or the

 $<sup>^4</sup>$ Estimated from data (Department of Treasury, 2010), but consistent with Olsberg and Winters (2005)

structure and assumptions of the model. Solving the problem with realistic features therefore require numerical solutions. In addition, most research studies do not involve calibration against empirical data. Tran and Woodland (2014) discuss the selection of model parameters which either match Australian economy rates or are taken from other research in order to ensure that a general equilibrium steady state is achieved, but are not calibrated against data. Calibration in Ding (2013) is based on mean squared error, but residuals are normalized with estimated lifetime wealth. This allows for larger errors in poor households (but improved fit for wealthier households) as the estimated pension received will be rather large in relation to actual wealth. Such normalization may affect the outcome from using said model, especially in forecasting future Age Pension budgets. Ameriks et al. (2011) calibrates a bequest model using maximum likelihood estimation, in order to investigate the bequest motives of the US data by separating precautionary savings from bequest.

The contribution of our paper is a sequential family status model in the retirement stage that takes into consideration stochastic wealth, stochastic family status and mortality risk, and a health status proxy to allow the model to better fit empirical data. It is the first sequential model in retirement modeling to our knowledge. Our model is based on Ding (2013), but can be considered a more realistic extension of his semi-analytical model as we relax prior assumptions of deterministic investment assets and the order of means-tests phases, apply a more strict calibration model and account for mortality risk. We focus on the decumulation phase of the life cycle problem, hence from the point in time the individual retires. The model is set up as a stochastic dynamic programming problem and solved numerically via backward recursion. We calibrate the model with Australian empirical data for consumption and housing, and estimate suitable parameters via the maximum likelihood method.

The paper is structured as follows. In Section 2 we define the model to include the Age Pension means-test and present the corresponding optimal stochastic control problem. Section 3 explains the model calibration process and the assumptions imposed. Section 4 contains a discussion of the results, and concluding remarks are presented in Section 5.

# 2 Model specification

We assume that the agent's goal is to maximize the expected value of utility that is associated with consumption, housing, and bequest. Utility is measured by time-separable additive functions based on commonly used HARA utility functions.

Let $(\Omega, \mathcal{F}, \{\mathcal{F}_t\}_{t\geq 0}, \mathbb{P})$ be a filtered complete probability space and $\mathcal{F}_t$ represents the information available before time t. We assume that all the processes introduced below are well defined and adapted to $\{\mathcal{F}_t\}_{t\geq 0}$ . Denote the value of liquid financial assets as random variable $W_t$ and family status as random variable $G_t$ at the agent's anniversary dates $t = t_0, t_0 + 1, ..., T$ , where $t_0$ is the retirement age and T is the maximum age of the agent beyond which survival is deemed impossible. Realizations of $W_t$ and $G_t$ are denoted as $w_t$ and $g_t$ respectively. The utility received at times t is subject to the agent decision (control) variables $\alpha_t$ (proportion drawdown of liquid assets), $\delta_t$ (proportion liquid assets allocated to risky assets) and the decision variable H (wealth allocated to total housing only at time $t = t_0$ )<sup>5</sup>. Given a current state $x_t = (w_t, g_t)$ we can define a

<sup>&</sup>lt;sup>5</sup>Note that H represents the price of the house at $t_0$ , and not additional wealth invested into housing.

decision rule $\pi_t(x_t) = (\alpha_t(x_t), \delta_t(x_t))$ which is the action at time t and $x_t$ is the value of the state variables before the action. Then a sequence (policy) of decision rules is given by $\pi = (\pi_{t_0}, \pi_{t_0+1}, ..., \pi_{T-1})$ for $t = t_0, t_0 + 1, ..., T - 1$ .

The optimization problem is set to begin at the time of retirement $t=t_0$ when all available wealth is placed in an allocated pension account, and the agent decides how much wealth to allocate into a family home. Taxes after $t_0$ are not considered since earnings in an allocated pension account are tax-free. At the start of each year, t, the agent makes a decision of how much to withdraw from the account, and receives a meanstested Age Pension $P_t$ . The remaining wealth is placed in a stochastic risky portfolio $S_t$ and risk free cash account until t+1, where the agent faces the decision of what proportion $\delta_t$ to allocate in risky assets. The wealth process and consumption are then given as

$$W_{t+1} = [W_t - \alpha_t W_t] \left[ \delta_t e^{Z_{t+1}} + (1 - \delta_t) e^{r_t} \right], \quad W_{t_0} = W - H, \tag{1}$$

$$C_t = \alpha_t W_t + P_t, \tag{2}$$

where $W_t \geq 0$ is the liquid assets at time t before withdrawal. The initial liquid assets $W_{t_0}$ are the remaining wealth after housing allocation at retirement where W is the total wealth at time $t = t_0$ . The housing allocation is constrained with $H \in \{0, [H_L, W]\}$ , where $H_L \geq 0$ is a lower bound of housing, hence wealth can never be negative. We assume that risky asset $S_t$ follows a geometric Brownian motion such that the real log returns of the risky asset $Z_{t+1} = \ln(S_{t+1}/S_t)$ , $t = 0, 1, \ldots$ are independent and identically distributed from a Normal distribution $\mathcal{N}(\mu - \tilde{r}, \sigma)$ with the mean $\mu - \tilde{r}$ and variance $\sigma^2$ , where $\tilde{r}$ is the inflation rate. The real risk free rate $r_t$ (adjusted for inflation) is time dependent but deterministic. The constraints for consumption, where $C_t$ is the consumption and $P_t$ is the Age Pension, show that consumption equals the sum of received Age Pension and drawdown of wealth for the current period. By defining the model in real terms (adjusted for inflation) we can avoid dealing with inflation in consumption, Age Pension and consumption floor to better capture the characteristics of Australian retirees.

The model operates on a household level, where we separate between couple and single retiree households due to the Age Pension treating couples as a single entity. The agents face the risk of family status transitions due to death each period, with the possible states defined as

$$G_t \in \mathcal{G} = \{\Delta, 0, 1, 2\},\tag{3}$$

whether the agent is already dead at time t ( $\Delta$ ), died during (t-1,t] (0), alive at time t in a single household (1) or alive in a couple household (2), subject to survival probabilities. An agent can therefore start off at time $t=t_0$ as either a couple or single household. In case of a couple household, there is a risk each time period that one of the spouses passes away, in which case it is treated as a single household model for the remaining years. $Z_t$ and $G_t$ are assumed to be independent, hence a large investment loss does not affect the death probabilities (though one can argue that it might affect i.e. the ability to pay hospital bills or life quality, which in turn affects death probabilities).

Each period the agent receives utility based on the current state of family status $G_t$ :

$$R_t(W_t, G_t, \alpha_t, H) = \begin{cases} U_C(C_t, G_t, t) + U_H(H, G_t), & \text{if } G_t = 1, 2, \\ U_B(W_t), & \text{if } G_t = 0, \\ 0, & \text{if } G_t = \Delta. \end{cases}$$
(4)

If the retiree currently is a homeowner, then the difference between H and current house value represent the change in housing suggested.

That is if the agent is alive he receives reward based on consumption $U_C$ and housing $U_H$ , if he died during the year the reward comes from the bequest $U_B$ and if he is dead there is no reward. Note that the reward received when the agent is alive depends on whether the state is a couple or single household due to differing utility parameters and Age Pension thresholds. The terminal reward function at t = T is given as

$$\widetilde{R}(W_T, G_T) = \begin{cases} U_B(W_T), & \text{if } G_T \ge 0, \\ 0, & \text{if } G_T = \Delta. \end{cases}$$
(5)

The current model is based on Ding (2013), but with the addition of sequential family status, mortality risk and risky asset, and a different health proxy. The retiree wants to find the policy that maximizes expected utility with respect to the decision for consumption, investment and housing. This is defined as a stochastic control problem

$$\widetilde{V} := \max_{H} \left[ \sup_{\pi} \mathbb{E}_{t_0}^{\pi} \left[ \beta_{t_0, T} \widetilde{R}(W_T, G_T) + \sum_{t=t_0}^{T-1} \beta_{t_0, t} R_t(W_t, G_t, \alpha_t, H) \right] \right], \tag{6}$$

that can be solved with dynamic programming by using backward induction of the Bellman equation. $\mathbb{E}_{t_0}^{\pi}[\cdot]$ is the expectation conditional on information at time $t = t_0$ if we use policy $\pi$ up to t = T - 1. The policy $\pi$ contains the control variables for each time period and $\beta_{t,t'}$ is the discounting from t to t'.

The subjective discount rate $\beta_{t,t'}$ is a proxy for personal impatience between time t and t', and set in relation to the real interest rate so that

$$\beta_{t,t'} = e^{-\sum_{i=t}^{t'} r_i}.\tag{7}$$

This assumption suggests that optimal consumption rates would be constant over time for HARA utility in the absence of mortality risk and risky investments <sup>6</sup>.

# 2.1 Consumption preferences

We assume that the HARA utility comes from consumption exceeding the consumption floor, weighted with a time dependent health status proxy. The utility function for consumption is defined as

$$U_C(C_t, G_t, t) = \frac{1}{\psi^{t - t_0} \gamma_d} \left( \frac{C_t - \bar{c}_d}{\zeta_d} \right)^{\gamma_d}, \quad d = \begin{cases} C, & \text{if } G_t = 2 \text{ (couple)}, \\ S, & \text{if } G_t = 1 \text{ (single)}, \end{cases}$$
(8)

where $\gamma_d \in (-\infty, 0)$ is the risk aversion and $\bar{c}_d$ is the consumption floor parameters. The scaling factor $\zeta_d$ normalizes the utility a couple receives in relation to a single household<sup>7</sup>. The utility parameters $\gamma_d$ , $\bar{c}_d$ and $\zeta_d$ are subject to family state $G_t$ , hence will have different values for couple and single households. Note that the consumption for any period is based on the pension $P_t$ received in the same period, and the drawdown $\alpha_t$ from the liquid assets $W_t$ as given by equation (2). The proportion of wealth drawn down can be positive or negative, with a negative value indicating that part of the pension

 $<sup>^6</sup>$ This can easily be shown with simple calculus.

<sup>&</sup>lt;sup>7</sup>If single and couple households had the same risk aversion and no scaling factor was used, the solution would suggest similar consumption for both. This effect comes from the consumption smoothing properties of life cycle models, hence needs to be adjusted as a couple household's utility is for two people. It would otherwise cause problems in the calibration stage.

received is saved for future consumption. As consumption tends to converge towards a consumption floor as the retiree ages despite wealth status, we define a health proxy to control the slope of the decline. Let $\psi \in [1, \infty)$ be the utility parameter for the slope where the difference between current time t and time of retirement $t_0$ determines the power of the parameter. This allows the initial time $t = t_0$ to not be affected by a health proxy, and as the retiree ages the slope of the proxy decreases to allow consumption to converge over age and wealth groups. This decreasing convex health proxy has a better fit to empirical data, compared with survival probabilities as used in Ding (2013) which is decreasing but concave.

### 2.2 Bequest preferences

We adopt the bequest function in Lockwood (2014) which is a re-parameterized version of De Nardi (2004), as the parameters are slightly more intuitive. The utility is received from *luxury* bequest, hence the home is not included in the bequest<sup>8</sup> and is not considered for such a purpose at the time of purchase. The utility function is then defined as

$$U_B(W_t) = \left(\frac{\theta}{1-\theta}\right)^{1-\gamma_S} \frac{\left(\frac{\theta}{1-\theta}a + W_t\right)^{\gamma_S}}{\gamma_S},\tag{9}$$

where $W_t$ is the liquid assets available for bequest, $\gamma_{\rm S}$ the risk aversion parameters of bequest utility (which is considered to be the same as consumption risk aversion for singles, since a couple is expected to become a single household before bequeathing assets)<sup>9</sup> and the two parameters $\theta \in [0,1)$ and $a \in \mathbb{R}^+$ . The threshold for luxury bequest, a, is the threshold up to where the retiree leaves no bequest<sup>10</sup>. If a=0 then consumption and bequest are homothetic. The degree of altruism, $\theta$ , controls the preference of bequest over consumption. Low values of $\theta$ reflect that retirees prefer consumption over bequest, while higher values decrease the marginal utility of bequest. As $\theta \to 1$ the bequest motive approaches a linear function with a constant marginal utility of $\frac{dU_B}{dW_t} = a^{\gamma-1}$ .

# 2.3 Housing preferences

Housing differs from other assets in that it provides a flow of services in terms of the preference (utility) of owning a house compared with renting, in addition to its residual value. We apply the assumption that the utility is linked to the house value as in Ding (2013) and Cho and Sane (2013). The utility from owning a home is defined as

$$U_H(H, G_t) = \frac{1}{\gamma_H} \left( \frac{\lambda_d H}{\zeta_d} \right)^{\gamma_H}, \tag{10}$$

where $\gamma_{\rm H}$ is the the risk aversion parameter for housing (allowed to be different from risk aversion for consumption and bequest), $\zeta_d$ is the same scaling factor as in equation (8),

<sup>&</sup>lt;sup>8</sup>As housing is both a necessity and bequest it cannot be treated the same as other bequest (Ding et al., 2014), since the intentional bequest component is difficult to separate. By using luxury bequest the model can better explain inequalities between wealth percentiles as wealthier retirees tend to bequeath a larger proportion of their assets. Previous research finds support for luxury bequest such as De Nardi et al. (2010) and Lockwood (2014).

<sup>&</sup>lt;sup>9</sup>In case couple households have a different risk aversion towards bequest it will be absorbed by adjusting the ratio of single and couple risk aversion.

<sup>&</sup>lt;sup>10</sup>There is strong empirical evidence that wealthy retirees leave a larger proportion of their wealth as bequest compared with less wealthy (Ameriks et al. (2011), Hurd and Smith (2002), Ding (2013)).

H > 0 is the market value of the family home at time of purchase $t_0$ and $\lambda_d \in (0, 1]$ is the preference of housing defined as a proportion of the market value.

Note the house value H is not indexed with time. The retiree decides how much of his wealth to allocate to housing at the time of retirement $t_0$ , which remains constant afterwards. We do not consider the house to be a liquid asset, rather a proxy for the utility received by being a homeowner. Our assumptions reflect the housing behavior of Australian retirees. Most Australian households do not convert housing assets to liquid assets in order to cover expenses in retirement, with the exception of certain events (such as death of a spouse or move to an Aged Care facility) (Olsberg and Winters, 2005). Wealthier retirees prefer to invest more in the family home as wealth increases, but with a decreasing marginal utility since the percentage allocation decreases consistent with the utility model used.

### 2.4 Age Pension function

We assume that all liquid assets are converted into an allocated pension account at the time of retirement, as for the year of our data sample over 90% of income came from allocated pensions. This type of account has the advantage that earnings on assets are tax free and allows for an yearly income test deduction. The Age Pension received is modeled with respect to the current liquid assets. The account value is used in the asset test, and the drawdown from this account is the income generated for the income test. Based on these assumptions, the Age Pension function can be defined as:

$$P_t := f(\alpha_t, W_t, t) = \max\left[0, \min\left[P_{\text{max}}, \min\left[P_{\text{A}}(W_t), P_{\text{I}}(\alpha_t W_t, t)\right]\right]\right],\tag{11}$$

where

$$P_{A}(W_{t}) = P_{\text{max}}^{d} - (W_{t} - L_{A}^{d,h}) \varpi_{A}^{d},$$
(12)

$$P_{\mathrm{I}}(\alpha_t W_t, t) = P_{\mathrm{max}}^d - (\alpha_t W_t - M(t) - L_{\mathrm{I}}^d) \varpi_{\mathrm{I}}^d.$$
(13)

Here, $P_{\text{max}}^d$ is the full Age Pension, $L^d$ is the threshold for the asset and income test respectively (as indicated by subscript) and $\varpi^d$ the taper rate for assets/income exceeding the thresholds, and superscript d is a categorical index indicating couple or single household status as defined in equation (8). The variables are subject to whether it is a single or couple household, and the threshold for the asset test is also subject to whether the household is a homeowner or not $h = \{0, 1\}$ (see Table 1 for parameterization of the function). The function M(t) is an income test deduction set when the wealth is converted into an allocated pension account 11, defined as:

$$M(t) = \frac{W_{t_0}}{e_{t_0}} (1 + \tilde{r})^{t_0 - t}, \tag{14}$$

where $e_{t_0}$ is the lifetime expected at age $t_0$ and $\tilde{r}$ the inflation. As the model is defined in real terms, the future income test deductions must discount inflation.

<sup>&</sup>lt;sup>11</sup>Income streams commenced after 1<sup>st</sup> January 2015 may no longer include an income test deduction. Income is now determined by a deeming rate applied to assets. See Australian government department of Families and Affairs (2016) regarding this function.

### 2.5 Solution as a stochastic control problem

To solve the optimal stochastic problem of maximizing expected utility with respect to the decision policy, given by equation (6), we follow the theory and notation specified in Bäuerle and Rieder (2011) to define the dynamic programming problem.

The starting point is the basic model where the wealth $W_t$ and family status $G_t$ are stochastic, and the terminal time T (time beyond which survival is deemed to be impossible) is fixed. The problem is defined as follows

- Denote a state vector as $X_t = (W_t, G_t) \in \mathcal{W} \times \mathcal{G}$ where $W_t \in \mathcal{W} = \mathbb{R}^+$ denotes the current level of wealth and $G_t \in \mathcal{G} = \{\Delta, 0, 1, 2\}$ whether the agent is dead, died this period, alive in a single household or alive in a couple household. The stages are sequential hence an agent that starts out as a couple becomes single when one spouse dies.
- Denote an action space of $(\alpha_t, \delta_t) \in \mathcal{A} = (-\infty, 1] \times [0, 1]$ for $t = t_0, ..., T 1$ where $\alpha_t \in (-\infty, 1]$ denotes the proportion of wealth consumed and $\delta_t \in [0, 1]$ is the percentage of wealth allocated in the risky asset. The upper boundary of 1 indicates that drawdown cannot be larger than our total wealth, hence borrowing is not allowed. Negative values for drawdown are allowed however as they represent savings from Age Pension into wealth.
- Denote an admissible space of state-action combination as $D_t(x_t) = \{\pi_t(x_t) \in \mathcal{A} \mid \alpha_t \geq \frac{\overline{c}_d P_t}{w_t}\}$ which contains the possible actions for the current state, and indicates that withdrawals must be large enough to cover the consumption floor, net of Age Pension received.
- The transition function $T_t(W_t, \alpha_t, \delta_t, z_{t+1}) := W_{t+1} = W_t(1 \alpha_t) \times (\delta_t e^{z_{t+1}} + (1 \delta_t)e^{r_t})$ where $z_{t+1}$ is the realization of the log return on the stochastic investment portfolio over (t, t+1]. We assume the agent is small and cannot influence asset price.
- Denote the stochastic transitional kernel as $Q_t(dx'|x, \pi_t(x))$ which represents the probability of reaching a state in $dx' = (dw_{t+1}, g_{t+1})$ at time t+1 if action $\pi_t(x)$ is applied in state x at time t. Since the transition function is based on the stochastic risky return $Z_{t+1}$ , which is Markovian, the transition probability for wealth $W_{t+1}$ is determined by the distribution of the risky return, where $Z_{t+1} \stackrel{i.i.d}{\sim} \mathcal{N}(\mu \tilde{r}, \sigma^2)$ with the probability density function denoted as $f_{\mathcal{N}}(z)$ . Let $q(g_{t+1}, g_t)$ denote $\Pr[G_{t+1} = g_{t+1} \mid G_t = g_t]$ . Since both state variables depend on exogenous and independent probabilities, we have

$$Q_{t}(dx'|x, \pi_{t}(x), \pi)$$

$$= \Pr[W_{t+1} \in dw_{t+1}, G_{t+1} = g_{t+1} \mid X_{t} = x_{t}]$$

$$= \Pr[T_{t}(W_{t}, \alpha_{t}, \delta_{t}, Z_{t+1}) \in dw_{t+1}, G_{t+1} = g_{t+1} \mid W_{t} = w_{t}, G_{t} = g_{t}]$$

$$= \Pr[T_{t}(W_{t}, \alpha_{t}, \delta_{t}, Z_{t+1}) \in dw_{t+1} \mid W_{t} = w_{t}] \times q(g_{t+1}, g_{t}).$$
(15)

The probabilities for family status are defined as

$$q(2,2) = p_t^{\mathcal{C}}, \quad q(1,2) = 1 - p_t^{\mathcal{C}},$$

$$q(1,1) = p_t^{\mathcal{S}}, \quad q(0,1) = 1 - p_t^{\mathcal{S}},$$

$$q(\Delta,0) = q(\Delta,\Delta) = 1,$$
(16)

where $p_t^{\text{C}}$ is the probability of surviving one more year as couples or $p_t^{\text{S}}$ as singles. All other transition probabilities for family status have probability 0.

- The reward function depends on the $G_t$ state as defined in equation (4). If the agent is alive he receives a reward based on consumption, if he died during the year the reward comes from bequest, and if he is dead there is no reward. Note that the reward when alive depends on the Age Pension received and the consumption floor, which differs for couples and singles.
- The terminal reward function is defined in equation (5).
- The discount factor is defined in equation (7) earlier, with $\beta_{t,t+1} \in (0,1]$ .

The optimal value function can now be stated as in equation (17) at starting time $t_0$ . The value function can be split into the stochastic control problem with respect to $\alpha_t$ and $\delta_t$ , and the decision problem for H at $t=t_0$ due to the time-separable additive preferences of the utility functions. A solution for the stochastic control problem is given by a backward recursion Bellman equation

$$V_{t}(W_{t}, G_{t}) = \sup_{\pi_{t}(x_{t}) \in D_{t}(x_{t})} \left\{ R_{t}(W_{t}, G_{t}, \alpha_{t}, H) + \beta_{t, t+1} \mathbb{E}_{t}^{\pi} \left[ V_{t+1}(W_{t+1}, G_{t+1}) \mid W_{t}, G_{t} \right] \right\},$$

$$(17)$$

where $\mathbb{E}_t^{\pi}[\cdot]$ is calculated using the stochastic transition kernel $Q(\cdot)$ given in equation (15)

$$\mathbb{E}_{t}^{\pi} \left[ V_{t+1}(W_{t+1}, G_{t+1}) \mid W_{t}, G_{t} \right] = \sum_{g_{t+1} \in \mathcal{G}} \int_{-\infty}^{\infty} V_{t+1}(W_{t+1}, G_{t+1}) f_{\mathcal{N}}(z_{t+1}) dz \times q(g_{t+1}, g_{t}).$$
(18)

It is shown in Appendix A that the problem can be simplified if we introduce an alternative reward function without the housing utility

$$\overline{R}_{t}(W_{t}, G_{t}, \alpha_{t}) = \begin{cases}
U_{C}(C_{t}, G_{t}, t), & \text{if } G_{t} = 1, 2, \\
U_{B}(W_{t}), & \text{if } G_{t} = 0, \\
0, & \text{if } G_{t} = \Delta,
\end{cases}$$
(19)

where the corresponding Bellman equation becomes

$$\overline{V}_{t}(W_{t}, G_{t}) = \sup_{\pi_{t}(x_{t}) \in D_{t}(x_{t})} \left\{ \overline{R}_{t}(W_{t}, G_{t}, \alpha_{t}) + \beta_{t, t+1} \mathbb{E}_{t}^{\pi} \left[ \overline{V}_{t+1}(W_{t+1}, G_{t+1}) \mid W_{t}, G_{t} \right] \right\} 
= \sup_{\pi_{t}(x_{t}) \in D_{t}(x_{t})} \left\{ \overline{R}_{t}(W_{t}, G_{t}, \alpha_{t}) + \sum_{g_{t+1} \in \mathcal{G}} \int_{-\infty}^{\infty} \overline{V}_{t+1}(T_{t}(W_{t}, \alpha_{t}, \delta_{t}, z_{t+1}), g_{t+1}) f_{\mathcal{N}}(z_{t+1}) dz \times q(g_{t+1}, g_{t}) \right\},$$
(20)

and the terminal condition at time t = T is

$$\overline{V}_T(W_T, G_T) = \widetilde{R}_T(W_T, G_T). \tag{21}$$

This allows us to avoid the house value being a state variable, effectively eliminating one dimension and allowing the problem to be solved as

$$\widetilde{V} = \max_{H \in [0, W]} \left[ \overline{H}_{t_0}(H, G_{t_0}) + \overline{V}_{t_0}(W - H, G_{t_0}) \right],$$
(22)

where $\overline{H}_t(H, G_t)$ is the summation of housing utility weighted with survival probabilities at time t given as

$$\overline{H}_{t}(H, G_{t}) = \begin{cases}
\sum_{i=t}^{T-1} \beta_{t,i} \left[ {}_{t}p_{i}^{C} U_{H}(H, G_{t} = 2) & \text{if } G_{t} = 2, \\
+ {}_{t}p_{i-1}^{C} (1 - p_{i-1}^{C}) \overline{H}_{t}(H, G_{t} = 1) \right], \\
\sum_{i=t}^{T-1} \beta_{t,i} {}_{t}p_{i}^{S} U_{H}(H, G_{t} = 1), & \text{if } G_{t} = 1, \\
0, & \text{if } G_{t} = 0, \Delta,
\end{cases}$$
(23)

where $_tp_{t'}^d$ denotes the probability of surviving from year t to year t' for singles (d = S) or couples (d = C). The validity of the problem setup and existence of optimal policies is implied by the integrability assumption and structure assumption<sup>12</sup>.

### 2.6 Numerical implementation

The model is solved numerically. By discretizing the wealth state on a grid of log-equidistant grid points $W_0, ..., W_k$ for each year $t = t_0, ..., T$ we solve the Bellman equation for value function $\overline{V}$ (equation (20)) recursively with backward induction. The lower bound of the grid $W_0$ is set to \$1 as the utility for \$0 does not exist and the upper bound $W_k$ is determined by the maximum wealth in the dataset and the risky asset. We use $W_k = \hat{W}_{\max} e^{(T-t_0)\mu+5\sqrt{T-t_0}\sigma}$ where $\hat{W}_{\max}$ is the largest wealth sample to find a conservative upper bound. This means that no extrapolation is needed when integrating risky returns and so values close to the upper bound have no material effect on the range $[W_0, \hat{W}_{\max}]$ actually used in the solution. For each grid point in the wealth state we find an optimal drawdown proportion $\alpha_t$ and risky asset allocation $\delta_t$ with a 2-dimensional optimization.

The value function $\overline{V}$ is interpolated between grid points based on the shape preserving Piecewise Cubic Hermite Interpolation Polynomial (PCHIP) method, which preserves the monotonicity and concavity of the value function (Kahaner et al., 1988). The need to interpolate arises from the integration of the stochastic return. Since the value function is only available at predefined grid points, any values in between needs to be interpolated. If traditional cubic splines were to be used there is a high chance of the function overshooting a point, hence the solution could return a local rather than global maximum. Linear interpolation requires a much higher grid density at lower values due to the steep derivative in these regions, hence PCHIP is preferred. In general, given a function f(x) and state x between two grid points $x_k \leq x \leq x_{k+1}$ the interpolant P(x) of f(x) for the kth interval is calculated as

$$P(x) = \frac{3h_k(x - x_k)^2 - 2(x - x_k)^3}{h_k^3} f(x_{k+1}) + \frac{h_k^3 - 3h_k(x - x_k)^2 + 2(x - x_k)^3}{h_k^3} f(x_k) + \frac{(x - x_k)^2(x - x_k - h_x)}{h_k^2} d_{k+1} + \frac{(x - x_k)(x - x_k - h_k)^2}{h_k^2} d_k,$$
(24)

where $h_k = x_{k+1} - x_k$ and the slope d of the interpolant depends on the first divided difference $\Delta_k = (f(x_{k+1}) - f(x_k))/h_k$ . If $\Delta_k$ and $\Delta_{k-1}$ are of opposite polarity then

<sup>&</sup>lt;sup>12</sup>Bäuerle and Rieder (2011) shows the integrability assumption holds if the reward and terminal function are bounded from above and satisfies $\mathbb{E} Z_n < \infty$ for all n where $Z_n$ is the disturbance term. A power utility function with $\gamma < 0$ has an upper bound of 0, and a log-normal random variable has a finite expected value, hence the integrability assumption is satisfied.

 $d_k = 0$ , otherwise $d_k$ is given by

$$\frac{3h_k + 3_{k-1}}{d_k} = \frac{2h_k + h_{k-1}}{\Delta_{k-1}} + \frac{h_k + 2h_{k-1}}{\Delta_k}.$$
 (25)

In addition to this, the conditions $P(x_k) = f(x_k)$ , $P(x_{k+1}) = f(x_{k+1})$ , $P'(x_k) = d_k$ and $P'(x_{k+1}) = d_{k+1}$ must hold true.

The expectation with respect to the stochastic return in equation (20) is calculated with Gauss-Hermite quadrature

$$\int_{-\infty}^{\infty} e^{-x^2} f(x) dx \approx \sum_{i=1}^{M} w(x_i) f(x_i), \tag{26}$$

where $w(x_i)$ is the weight and $x_i$ is the node at which to evaluate the value function, which gives an exact result if f(x) is any polynomial up to the order 2M-1. For details on how to find the weights and nodes see a textbook on numerical integration, such as Kahaner et al. (1988). The expectation is then calculated as

$$\int_{-\infty}^{\infty} \overline{V}_{t+1}(T_t(W_t, \alpha_t, \delta_t, z), G_{t+1}) f_{\mathcal{N}}(z) dz$$

$$= \int_{-\infty}^{\infty} \frac{e^{-x^2}}{\sqrt{\pi}} \overline{V}_{t+1}(T_t(W_t, \alpha_t, \delta_t, \sqrt{2}\sigma x + \mu), G_{t+1}) dx$$

$$\approx \sum_{i=1}^{M} \frac{w(x_i)}{\sqrt{\pi}} \overline{V}_{t+1}(T_t(W_t, \alpha_t, \delta_t, \sqrt{2}\sigma x_i + \mu), G_{t+1}),$$
(27)

using M = 5 nodes<sup>13</sup>. To speed up calculations, a temporary vector is created each year where the expectation of the value function is calculated for each grid point. By doing this prior to finding the optimal control we avoid repeating the numerical integration during the optimization as it is now enough to interpolate.

Finally, once the backward induction has reached $t = t_0$ the initial wealth $W_0$ can be determined by optimizing the allocation between housing and liquid assets in equation (22). The optimal path for a retiree can then be derived by following the optimal drawdown and risky allocation from the policy that corresponds with our wealth grid point for each time t and keep repeating until the terminal condition at t = T.

We performed tests with additional number of nodes for the Gauss-Hermite quadrature and larger bounds for $W_k$ to ensure the accuracy of our numerical solution. In addition to this a forward Monte Carlo simulation with random policies was generated to verify optimality of the solution.

# 3 Calibration

We calibrate the model using a similar approach and the same data as Ding (2013), but with maximum likelihood estimation instead of mean squared errors in order to estimate utility parameters.

<sup>&</sup>lt;sup>13</sup>Solving the Bellman equation with 5, 10 or 25 nodes resulted in negligible differences, hence 5 nodes were chosen to reduce calculation time.

The calibration is rather computationally expensive. Each time new parameters are suggested the model needs to be solved 4 times (each combination of single/couple households and homeowner/non-homeowner), and the model output needs to be generated from the wealth, age and homeowner data given in each sample. The model output is then compared with the sample data for consumption and housing to estimate the fit of the model as in Section 3.4 before the next iteration begin.

The calibration is carried out in two steps. First, a suitable starting point is identified by searching globally. Each utility parameter is assigned a realistic range of values where 3 different values are selected, hence 1,000 iterations are carried out. Once a starting point is identified, the parameters are optimized further using the Nelder-Mead Simplex algorithm until further improvements of the log likelihood function are negligible.

### 3.1 Dataset

For the dataset we use the Household Expenditure Survey (HES) 2009-2010 and the Survey of Income and Household (SIH) 2009-2010 from Australian Bureau of Statistics (Australian Bureau of Statistics, 2011). This dataset has a limitation in that data is only collected for private households, hence retirees within assisted care facilities are excluded. Out-of-pocket health expenses are included, but any costs associated with private facilities are not. Furthermore, we do not generalize between households with or without dependents and treat them as one group, even if consumption in reality might differ.

The samples are filtered by labor status ('not in work force') and the age requirement for Age Pension to find eligible retirees, where the age of a couple household is based on the youngest spouse. The data is then aggregated for each sample to reflect total expenditure (excluding mortgage payments), family home value, and wealth. In order to clean the data from possible reporting errors, we remove samples that received no Age Pension despite being entitled to a material portion, as well as any samples with expenditure less than \$3,000 per year or larger than assets available (liquid assets and Age Pension). Since the model is restricted to no borrowing any entries with negative wealth are removed as well. This resulted in 2,017 samples for couple households and 2,038 samples for single households.

# 3.2 Assumptions

In order to ensure a realistic calibration, some assumptions and constraints are needed. We impose the following:

- For samples with age older than the entitlement age, we assume that the wealth at retirement equals the wealth of the sample, in order to calculate the income test deduction M(t).
- We assume that households are aware of their life expectancy hence can take this into consideration for decisions.
- A potential home owner is required to have sufficient funds for an initial down payment on a home. As the first wealth quartile in the dataset are unlikely to be home owners, a lower threshold for housing is set to \$30,000 to make this consistent with the data. A retiree with wealth below this level can therefore not be a homeowner.

The following constraints have been imposed on the utility parameters to ensure meaningful variables, rather than over-fitting the model to the sample data. That said, none of the constraints were binding for the parameters once the calibration finished.

- $\bar{c}_d \in [0, P_{\text{max}}]$ , which ensures that the consumption floor does not violate budget constraints for poor households. In other words, the necessary spending cannot be higher than future income in case of no accumulated wealth.
- $\gamma_d < 0$ , since the utility function is discontinuous at $\gamma_d = 0$ and positive values indicate risk seeking behavior.
- $\theta \geq 0$ , preference of bequest over consumption must be positive as we do not allow negative bequest.
- $a \geq 0$ , threshold for luxury bequest must be positive.
- $\lambda_d \geq 0$ , utility parameter from being a homeowner cannot be negative, as otherwise the optimization might suggest that selling a house the retiree does not own while still receiving utility is optimal.

### 3.2.1 Survival probabilities

The sequential model introduces two extra dimensions to the calibration; the age of the second person in a couple household, and the age difference between the spouses. In addition to this, survival probabilities differ between females and males, which would require additional parallel solutions to the model. If the age difference in couples were considered this would be very computationally expensive and unrealistic for calibration. We therefore generalize survival probabilities for single and couple households into a single unisex dimension.

In order to estimate the unisex survival probability, the ratio of male to females alive (estimated from the cumulative probability to be alive) is used as weights. The estimated ratios match the empirical data proportions of males and females alive at any age t in Australian Bureau of Statistics (2011), and can be used as a proxy for survival probabilities to avoid the gender variable. The unisex probability of surviving one more year at age t is defined as

$$p_t^{S} = 1 - \frac{q_t^{M} \times {}_{t} p_0^{M} + q_t^{F} \times {}_{t} p_0^{F}}{{}_{t} p_0^{M} + {}_{t} p_0^{F}}, \tag{28}$$

where superscript indicates a single unisex household (S), male (M) or female (F) probabilities, and $_tp_0$ is the probability of surviving from birth (year 0) to age t. The actual mortality probabilities are taken from Life Tables published in Australian Bureau of Statistics (2012).

The assumptions for couple households are different since we already know that both spouses are alive, hence no weighting of male to females ratios are necessary. The events of independent deaths of each spouse are non-mutually exclusive, however, we treat them as if they were mutually exclusive to follow the model assumptions. We do not expect both spouses to die the same year due to the low probability of this occurring and the effect it would have on the solution is minimal. The probability of surviving one more year as a couple at time t is therefore defined as

$$p_t^{\rm C} = 1 - \left(q_t^{\rm M} + q_t^{\rm F}\right).$$
 (29)

### 3.2.2 Portfolio composition and returns

The expected return and volatility have an important effect on the model calibration. To make the wealth process as realistic as possible, we estimate a typical portfolio composition of Self-Managed Super Fund (SMSF) accounts and then use this typical composition with longer term financial data to find portfolio return. This way we can use the actual portfolio returns in the calibration, rather than returns based on the optimal allocation control parameter (which most likely will not be a correct representation for the average retiree).

In order to estimate the typical portfolio composition we use SMSF data for each financial year from 2008 to $2014^{14}$ , from which we calculate actual investment returns on SMSF accounts. The average operating expense ratio reported by ATO for the same period as the SMSF data is $0.83\%^{15}$ . The portfolio is assumed to be based on a set of risky assets approximated with S&P/ASX 200 Total Return which includes dividends, and a risk free asset approximated with the deposit interest rate. The portfolio weight (proportion risky assets) $\delta$ is then estimated with least square regression by regressing the average SMSF account returns for each year against the returns of S&P/ASX 200 Total Return and the deposite rate. We find $\delta$ to be 43.7% with a significance level of 1%. This $\delta$ is used as a proxy for risky asset allocation during calibration of the model.

To estimate the long term returns we take the 20 year average log-returns prior to 2010 of S&P/ASX 200 Total Return. The returns are then adjusted to real returns by deducting inflation ( $\tilde{r} = 2.9\%$ ) and for operating expenses. The final estimates give $r_t = 0.005$ and $Z_t \sim \mathcal{N}(0.056, 0.133)$ which are used in equation (1).

### 3.3 Parameters

The parameters for the Age Pension are shown in Table 1, and taken for the year 2010 to match the data. A retiree is eligible for Age Pension at age 65 (male) or 63 (female). We set the scaling factor for couple households to $\zeta = 1.3$ , which is in line with the results in Fernández-Villaverde and Krueger (2007) who review research in controlling for family size and the resulting economy of scale. In addition to this, we set T = 100.

| <b>Table 1:</b> Age Pension rates published by Centrelink as at January 2010 | 0 |
|------------------------------------------------------------------------------|---|
|------------------------------------------------------------------------------|---|

| | Single | Couple |
|-------------------------------------------------|-----------|-----------|
| Full Age Pension Rate $(P_{\text{max}}^d)$ | \$17,456 | \$26,099 |
| Income Test | | |
| Threshold $(L_{\rm I}^d)$ | \$3,692 | \$6,448 |
| Rate of Reduction $(\varpi_{\mathrm{I}}^d)$ | \$0.5 | \$0.5 |
| Asset Test | | |
| Threshold: Homeowners $(L_{\rm I}^{d,h=1})$ | \$178,000 | \$252,500 |
| Threshold: Non-homeowners $(L_{\rm I}^{d,h=0})$ | \$307,000 | \$381,500 |
| Rate of Reduction $(\varpi^d_{\mathrm{A}})$ | \$0.039 | \$0.039 |

<sup>&</sup>lt;sup>14</sup>Data contains individual account balances, earnings and drawdowns each year for Self-Managed Super Fund accounts, taken from a dataset provided by Australian Taxation Office to CSIRO-Monash superannuation research cluster (not publicly available).

<sup>&</sup>lt;sup>15</sup>Data is taken from 'Australian Taxation Office Reports SMSFs: A statistical overview' for the years 2008-09, 2009-10, 2010-11, 2011-12 and 2012-13

### 3.4 Calibration model

Calibration of the model on the sample data is performed with the maximum likelihood method. The sample data is split into vectors of single (d = S) and couple (d = C) households for consumption $(\mathbf{c}^d)$ and housing $(\mathbf{h}^d)$ . Denote total data as $\mathcal{D} = \{\mathbf{c}^S, \mathbf{c}^C, \mathbf{h}^S, \mathbf{h}^C\}$ . The statistical models are assumed to be $c_i^d = \tilde{c}_i^d(\Theta)e^{\epsilon_i^d}$ and $h_i^d = \tilde{h}_i^d(\Theta)e^{\epsilon_i^d}$ , where $c_i^d$ and $h_i^d$ are sample i from the corresponding dataset, $\tilde{c}_i^d(\Theta)$ and $\tilde{h}_i^d(\Theta)$ are the optimal consumption and housing respectively from the model based on wealth and age corresponding to sample i and the utility model parameters vector is

$$\Theta^{\top} = ( \gamma_{S} \quad \gamma_{C} \quad \gamma_{H} \quad \theta \quad a \quad \overline{c}_{S} \quad \overline{c}_{C} \quad \psi \quad \lambda ).$$
 (30)

Finally, $\epsilon_i^d \sim \mathcal{N}(0, \sigma_\epsilon^d)$ and $\varepsilon_i^d \sim \mathcal{N}(0, \sigma_\epsilon^d)$ are the independent non-standardized error terms (residuals).

The log likelihood function of N independent identically distributed samples $\mathbf{x} = (x_1, x_2, ..., x_N)$ from a log-normal distribution such that $\ln x_i \sim \mathcal{N}(\ln \mu, \sigma)$ is

$$\mathcal{L}_{\mathbf{x}}(\mu,\sigma) \propto -\frac{N}{2} \ln\left(2\pi\sigma^2\right) - \frac{1}{2\sigma^2} \sum_{i=1}^{N} \left(\ln x_i - \ln \mu\right)^2. \tag{31}$$

The maximum likelihood estimates of parameters $\Theta$ and $\boldsymbol{\sigma} = \{\sigma_{\epsilon}^{S}, \sigma_{\epsilon}^{C}, \sigma_{\epsilon}^{S}, \sigma_{\epsilon}^{C}\}$ are obtained by maximizing the total log likelihood

$$\mathcal{L}_{\mathbf{c}^{\mathrm{S}}}(\widetilde{\mathbf{c}}^{\mathrm{S}}(\Theta), \sigma_{\epsilon}^{\mathrm{S}}) + \mathcal{L}_{\mathbf{c}^{\mathrm{C}}}(\widetilde{\mathbf{c}}^{\mathrm{C}}(\Theta), \sigma_{\epsilon}^{\mathrm{C}}) + \mathcal{L}_{\mathbf{h}^{\mathrm{S}}}(\widetilde{\mathbf{h}}^{\mathrm{S}}(\Theta), \sigma_{\epsilon}^{\mathrm{S}}) + \mathcal{L}_{\mathbf{h}^{\mathrm{C}}}(\widetilde{\mathbf{h}}^{\mathrm{C}}(\Theta), \sigma_{\epsilon}^{\mathrm{C}}), \tag{32}$$

with respect to $(\Theta, \sigma)$ .

Other distributions such as skew-t lead to some slight improvement in residual fitting, but since it is not very significant it has not been included in this paper.

# 3.5 Calibrated parameters

Our estimated parameters (see Table 2) are in line with related literature. The risk aversion is slightly lower than Ding (2013) who estimated $\gamma = -3$ , while the consumption floor is well under the full Age Pension rates but in line with the authors findings. This can be compared with Ameriks et al. (2011) where the consumption floor is only \$5,750 USD (the average social security payment), hence in relative terms our estimates are higher.

**Table 2:** Calibrated parameters with standard errors

| | $\gamma_{ m S}$ | $\gamma_{ m C}$ | $\gamma_{ m H}$ | $\theta$ | a | $\overline{c}_{\mathrm{S}}$ | $\overline{c}_{\mathrm{C}}$ | $\psi$ | λ |
|------------|-----------------|-----------------|-----------------|----------|--------|-----------------------------|-----------------------------|--------|-------|
| Value | -1.98 | - 1.78 | -1.87 | 0.96 | 20 726 | 10 122 | 15 702 | 1.18 | 0.044 |
| Std. Error | 0.38 | 0.37 | 0.37 | 0.01 | 208 | 1 648 | 1 826 | 0.03 | 0.009 |

The calibrated health proxy parameter $\psi=1.18$ indicates that the preferences for consumption which exceed the consumption floor decreases with a factor of $\psi^{(\gamma_d-1)/2}$ , hence 0.61 for singles and 0.63 for couples each year due to declining health. To put this into perspective it equals a decrease of \$1,320 per year for the median single household between age 65-75, and \$2,312 for the median couple household. Bernicke (2005) conducted a US study on empirical retirement data and found that the difference in

consumption for the same age span was 26.4%, and Higgins and Roberts (2011) find a 20-30% drop in median levels where the decrease is larger for wealthier households, which confirms our results. Clare (2014) finds an average decrease of 10% for households with a comfortable lifestyle (roughly 300% higher than our consumption floor) and 2% for a modest lifestyle (roughly 100% higher than our consumption floor) between the ages 70 to 90. Our calibrated model suggests similar decreases in expenditure, and captures the characteristics of larger declines for wealthier households.

Finally, $\theta$ implies little sensitivity of consumption to wealth, consistent with an explanation that additional wealth is being saved for a bequest. This is very similar to Ding (2013) ( $\theta = 0.956$ ), which indicates that a sequential model does not affect bequest motives. That said, our model cannot separate whether this is due to precautionary savings or indeed clear bequest motives.

### 4 Results

The calibration output indicates that the model fits the empirical behavior, and the statistical model is well chosen as the residuals have an acceptable Quantile-Quantile fit. The assumption that consumption and housing residuals are independent is confirmed as well. That said, due to the limitations in the data used for calibration (see Section 3.1) the result should only be considered for healthy households in the post retirement phase. This is because the survey sample tends to be of better health than what might be true in reality, as retirees with bad health are more likely to live in an assisted care facility.

### 4.1 Optimal Consumption

The optimal consumption curve in relation to wealth differs from the one in traditional utility models, where the deviations can be explained by the Age Pension means-test parameters (Figure 1). Traditionally, consumption is a smooth, concave and monotone function of wealth for risk averse agents. Generally this is true for drawdown outside the upper thresholds of the means-test where no Age Pension is received, but as the means-test binds the optimal drawdown policy changes slightly to anticipate the Age Pension received (which equals the area between the dashed and solid curve). Note that the drawdown curves in relation to the Age Pension thresholds are very similar between single and couple households. The rate of drawdown in relation to wealth decreases faster at the point where the retiree goes from full Age Pension to partial Age Pension due to the income test binding. This is effectively sacrificing current utility from consumption in order to receive additional future utility from consumption or bequest by adding Age Pension to liquid assets. This effect decreases with age however, as the sum of expected future Age Pension decreases due to mortality risk increasing, decreased consumption over one period will have a larger relative marginal utility loss.

The most obvious effect of the Age Pension means-test on optimal drawdown can be seen between ages 75-85. The optimal drawdown curve almost perfectly follows the lower threshold of the income test, and continues where the income and asset tests intersect. Such behavior would maximize the Age Pension received for less wealthy households, until the curve tapers off into the asset test zone to avoid increased consumption.

As the retiree ages, the consumption in relation to wealth flattens out even further to match the effect of declining health. At this point the optimal consumption shows almost no regard to the means-test, and converges towards the expected result from

### Optimal Consumption for Single Households

![](_page_17_Figure_1.jpeg)

Figure 1: Optimal drawdown ( $\alpha_t w_t$ ) and consumption in relation to wealth for the single non-homeowner case. The shaded zones show whether the asset or income test is binding and leading to partial Age Pension, or if the retiree would receive full/no Age Pension. The graphs illustrate the different drawdown and consumption curves for ages t = 65, 75 and 85 years.

a utility model without means-tested Age Pension. For very low levels of wealth the drawdown curve disappears to negative territory, indicating that part of the Age Pension shall be saved as desired consumption can be fully covered by the Age Pension received.

An interesting result of this is the sequence of the means-test phases. Ding (2013) suggests that retirees go through the Age Pension in phases in the order of no pension, partial pension due to assets test, partial pension due to income test, and full pension. This is not necessarily true, especially when behavior such as higher consumption early in retirement and wealth accumulation for wealthier households are considered.

It can be seen in Figure 3 that phases tend to vary for different expected wealth and drawdown paths from $t_0$ to T, where wealth grows with the expected return between

### Optimal Consumption for Couple Households

![](_page_18_Figure_1.jpeg)

Figure 2: Optimal drawdown $(\alpha_t w_t)$ and consumption in relation to wealth for the couple non-homeowner case. The shaded zones show whether the asset or income test is binding and leading to partial Age Pension, or if the retiree would receive full/no Age Pension. The graphs illustrate the different drawdown and consumption curves for ages t = 65, 75 and 85 years.

each periods. Less wealthy households ( $W_{t_0} = \$100,000$ ) tend to stay on full pension as the wealth is too low to grow to the asset test threshold, despite lower consumption with age. Wealthier households ( $W_{t_0} = \$400,000$ ) however tend to accumulate enough wealth so that the asset test binds after a period of full Age Pension. Early in retirement it is possible to switch between phases, where risky returns can increase wealth so that the asset test binds, which in turn leads to a higher drawdown amount and binding of the income test.

### Stages of means-test for Single Household

![](_page_19_Figure_1.jpeg)

**Figure 3:** Phases in means-testing for expected wealth evolution and optimal draw-down paths given starting wealth $W_{t_0}$ . Each rectangle corresponds to whether the means-test binds or if full Age Pension is received for the year.

### 4.2 Optimal risky asset allocation

The exposure to risky assets in the portfolio is highly dependent on wealth and age. In general, the percentage allocation tends to increase with age for less wealthy households but decrease for wealthier ones. The increase in less wealthy households is contrary to traditional investment advice, which suggests that the allocation of risky assets should be reduced with age. The effect can be seen in Figure 4. This confirms the findings of Iskhakov et al. (2015) (as long as the consumption floor is less than the Age Pension) and Ding (2013) who show that when bequest is considered a luxury, the optimal allocation of risky assets increases with age, implying higher allocation to risky asset throughout retirement. Only when bequest is not considered in a utility maximization model is decreasing the exposure with age indeed optimal (Blake et al., 2014).

The contour chart shows a complex relationship with the means-test and Age Pension. Exposure tend to be more aggressive when the asset test is binding, as potential losses will be partly offset by increased Age Pension payments, hence Age Pension and risky assets are negatively correlated. The local maxima (dark area) in the middle corresponds with where this offset effect is the greatest (this will disappear if minimum withdrawals are enforced as studied in Section 4.4). The relative decrease vertically towards full pension is due to the buffer is no longer proportional, as larger losses cannot be compensated with more than full Age Pension. As the mortality risk increases, the expected buffer over the remaining life decreases hence allocation decreases horizontally towards old age. The downward slope in the local maxima is because of the optimal drawdown rules. Since drawdown decreases with age the risk of significantly decreasing wealth decreases as well, resulting in lower levels of buffer against losses being accepted. When no Age Pension is received from the income test, there is a higher allocation to risky assets the closer to partial pension we get. As with the asset test, this is due to losses being offset by Age Pension. The maximum increase is therefore on the threshold between no and partial Age Pension, as this is where the buffer has the greatest effect. Hulley et al. (2013) finds that risky allocation is much higher when the asset test is binding due to the steeper taper rate, and slightly lower (but still higher than the benchmark) for the income test. The effect of the Age Pension acting as a safety net to investment is further implied as lower wealth suggests full exposure to risky assets. These characteristics become clear in Figure 5.

In addition to the effects from the Age Pension, a few general conclusions can be derived:

- As wealth increases, allocation decreases. A loss of wealth has more negative marginal utility than the equivalent gain has positive utility. The difference increases with larger wealth.
- As the retiree ages, the (mortality risk) weight increases towards bequest where the marginal utility decreases quickly with increased wealth, but with a smaller negative derivative. This means that preserving capital becomes more important with age as wealth increases.
- Couples tend to be more aggressive with risky assets. One factor is the slightly lower risk aversion compared with singles, but since mortality risk is also lower the couple has a higher chance of recovering negative asset shocks, meaning they have more to gain from higher risk exposure.

![](_page_20_Figure_5.jpeg)

**Figure 4:** Optimal allocation in risky assets for single non-homeowners. The horizontal lines (from bottom up) show the threshold a, the threshold for partial Age Pension due to asset test, and the threshold for no Age Pension due to asset test.

![](_page_21_Figure_0.jpeg)

**Figure 5:** Optimal allocation in risky assets for single non-homeowners, given a fixed wealth. The wealth levels correspond to full pension, the lower threshold of the asset test, partial pension due to asset test, upper threshold of the asset test and no pension.

# 4.3 Optimal housing allocation

The literature is inconclusive regarding whether retirees allocate more assets into housing in order to be eligible for either full or partial Age Pension. We find no evidence that the model considers means-test levels for optimal allocation of net assets into housing, such as whether the asset test binds or not at $t_0$ . This would show up as kinks in Figure 6 where the wealth equals the asset test thresholds.

The risk aversion for housing falls between the risk aversion of singles and couples. The different curves for optimal housing is then due to marginal utility of housing in relation to the marginal utility of consumption. As wealth increases, the risk aversion for couples favors housing more in relation to consumption than single households do. In addition, liquid assets for couples tend to be higher hence results in a higher dollar value allocated into housing than for single households.

### 4.4 Forced minimum withdrawals

Allocated pension accounts impose minimal withdrawal rates based on age (Table 3). It can be argued that this should be enforced in the calibration model, however we have intentionally left it out for the following three reasons:

- Forced withdrawal does not necessarily affect the level of consumption, but it does affect whether the consumption consists of drawdown of the wealth or Age Pension

# Optimal housing per total wealth 7 6 6 6 1 2 1 Single household Couple household Wealth (\$100,000)

**Figure 6:** Optimal allocation of total wealth into housing for single and couple households.

received. A retiree that is forced to withdraw a larger amount of wealth than is optimal will effectively replace part of the Age Pension with own funds, but consume a similar dollar amount.

- In response to the global financial crisis of 2007-08, the government provided pension drawdown relief by reducing the withdrawal rates by 50% between 2008-11 and 25% between 2011-13. As the data set is taken from 2009-2010, these lower withdrawal rates applied.
- The benefit (income deduction) of an allocated pension account is no longer available for new accounts after 1<sup>st</sup> of January 2015, hence new retirees might opt for a different kind of account. These accounts might not have forced minimal withdrawals.

**Table 3:** Minimum withdrawal rates for allocated pension accounts for the year 2013 and onwards.

| Age | $\leq 64$ | 65-74 | 75-79 | 80-84 | 85-89 | 90-94 | 95 <u>&lt;</u> |
|---------------|-----------|-------|-------|-------|-------|-------|----------------|
| Min. drawdown | 4% | 5% | 6% | 7% | 9% | 11% | 14% |

The minimum drawdown rules do however have an effect on the optimal results that needs to be brought to attention. First, minimum drawdown limits the assets from increasing with age due to decreased consumption. The retiree can still get switching cases between partial pension due to asset test and income test early in retirement, but this voids the case where the asset test can bind at older age as in Figure 3. It could potentially happen in case of very high risky returns, but it is not a scenario that is expected. Secondly, it limits the freedom for planning drawdown and risky asset allocation to optimize the Age Pension received. It is still possible to some extent, but it is less available as the wealth level increases. This effect can easily be seen with optimal

risky asset allocation (Figure 7) compared with when no rules withdrawal are enforced (Figure 4). The allocation tends to follow the general rules where allocation decreases with wealth, increases with age for less wealthy households and but decreases for wealthier households. The exception is the increase for wealthy households until age 80-85, which is due to mortality risk shifting the weight towards bequest as the retiree ages where this age corresponds to the tipping point.

![](_page_23_Figure_1.jpeg)

Figure 7: Optimal allocation in risky assets for single non-homeowners with forced minimum withdrawal. The horizontal lines (from bottom up) show the threshold a, the threshold for partial Age Pension due to asset test, and the threshold for no Age Pension due to asset test.

## 5 Conclusions

In this paper we develop a sequential expected utility model for the decumulation phase of Australian retirees. The model can be considered a more realistic extension to Ding (2013) where we introduce stochastic wealth, stochastic family status and a health status proxy, and relax prior assumptions of the order of means-tests phases. The model is defined as a stochastic control problem where we solve for optimal consumption, optimal risky asset allocation, and optimal housing. We solve the problem numerically using dynamic programming, and calibrate the utility parameters against data from Australian Bureau of Statistics (2011) using the maximum likelihood method.

We find that the model explains the general behavior of Australian retirees, such as the declining consumption due to age (health), and can suggest optimal policy for consumption and risky asset allocation with respect to means-tested Age Pension. The optimal policy is found to be highly sensitive to the means-test early in retirement, hence the retiree can plan ahead to take advantage of Age Pension. The effect fades however with age, as the expected future Age Pension decreases due to increased mortality risk. The possibility to plan drawdown and risky asset allocation with respect to Age Pension is however limited when minimum withdrawal rules are enforced - especially for wealthier households.

Since the family status is sequential, it is of interest to understand the differences between single households and couple households. In general, we find that the two behave very similar with respect to wealth drawdown, allocation to risky assets and allocation to housing. The main difference is that couples can accept higher investment risk due to lower mortality risk, and tend to favor owning a home slightly more than single households.

The means-test is often assumed to go through different phases sequentially. We find that this is only true if minimum withdrawal rules are enforced. If not, it's likely that households accumulate wealth later in retirement due to decreased consumption, hence a retiree can go from receiving full Age Pension to partial due to the asset test.

The model lends itself to applications on both macro and micro scale. It can be used to forecast future Age Pension needs, implications of policy changes (or new financial products) in retirement behavior, and on a financial planning level once individual risk preferences have been estimated. It can easily be extended to suit the defined contribution pension system of other countries, or future changes in the Australia Superannuation.

# Acknowledgment

This research was supported by the CSIRO-Monash Superannuation Research Cluster, a collaboration among CSIRO, Monash University, Griffith University, the University of Western Australia, the University of Warwick, and stakeholders of the retirement system in the interest of better outcomes for all. Alex Novikov acknowledges the support of the Australian Research Councils Discovery Projects funding scheme (DP130103315). We thank Xiaolin Luo for valuable discussions and comments.

# A Separation of Housing utility

Consider the value function in equation (6), which shows the optimal expected value function conditional on information at time $t = t_0$ if we use policy $\pi$ up to t = T - 1. The following shows that utility for housing can be separated into a decision problem for H at time $t = t_0$ separate from the consumption and bequest utility, in order to avoid having house value as a state variable (thereby avoiding an additional dimension). The following is for a single household, but the approach is valid for couple households as well.

Introduce an alternative reward function without the housing utility

$$\overline{R}_{t}(W_{t}, G_{t}, \alpha_{t}) = \begin{cases}
U_{C}(C_{t}, G_{t}, t), & \text{if } G_{t} = 1, 2, \\
U_{B}(W_{t}), & \text{if } G_{t} = 0, \\
0, & \text{if } G_{t} = \Delta.
\end{cases}$$
(A.1)

Since $\mathbb{E}^\pi_{t_0}$ is condition on the wealth process and family status, and utility is time-separably

additive, we have

$$\begin{split} \widetilde{V} &= \max_{H} \left[ \sup_{\pi} \mathbb{E}_{t_{0}}^{\pi} \left[ \beta_{t_{0},T} \widetilde{R}(W_{T},G_{T}) + \sum_{t=t_{0}}^{T-1} \beta_{t_{0},t} R_{t}(W_{t},G_{t},\alpha_{t},H) \mid W_{t_{0}},G_{t_{0}} \right] \right] \\ &= \max_{H} \left[ \sup_{\pi} \mathbb{E}_{t_{0}}^{\pi} \left[ \iota_{0} p_{T-1}^{S} \beta_{t_{0},T} \widetilde{R}(W_{T},G_{T}=1) \right. \right. \\ &+ \sum_{t=t_{0}}^{T-1} \beta_{t_{0},t} \left( \iota_{0} p_{t}^{S} \left( U_{C}(C_{t},G_{t}=1,t) + U_{H}(H,G_{t}=1) \right) + \iota_{0} p_{t-1}^{S} (1 - p_{t-1}^{S}) U_{B}(W_{t}) \right) \mid W_{t_{0}} \right] \\ &= \max_{H} \left[ \sup_{\pi} \mathbb{E}_{t_{0}}^{\pi} \left[ \iota_{0} p_{T-1}^{S} \beta_{t_{0},T} \widetilde{R}(W_{T},G_{T}=1) \right. \\ &+ \sum_{t=t_{0}}^{T-1} \beta_{t_{0},t} \left( \iota_{0} p_{t}^{S} \left( U_{C}(C_{t},G_{t}=1,t) \right) + \iota_{0} p_{t-1}^{S} (1 - p_{t-1}^{S}) U_{B}(W_{t}) \right) \mid W_{t_{0}} \right] \\ &+ \mathbb{E}_{t_{0}}^{\pi} \left[ \sum_{t=t_{0}}^{T-1} \beta_{t_{0},t} \iota_{0} p_{t}^{S} U_{H}(H,G_{t}=1) \mid W_{t_{0}} \right] \\ &= \max_{H} \left[ \sup_{\pi} \mathbb{E}_{t_{0}}^{\pi} \left[ \beta_{t_{0},T} \widetilde{R}(W_{T},G_{T}) + \sum_{t=t_{0}}^{T-1} \beta_{t_{0},t} \overline{R}_{t}(W_{t},G_{t},\alpha_{t}) \mid W_{t_{0}}, G_{t_{0}} \right] \\ &+ \sum_{t=t_{0}}^{T-1} \beta_{t_{0},t} \iota_{0} p_{t}^{S} U_{H}(H,G_{t}=1) \right]. \end{split} \tag{A.2}$$

Define a new value function $\overline{V}$ from reward function $\overline{R}$ 

$$\overline{V}(W_{t_0}, G_{t_0}) = \sup_{\pi} \mathbb{E}_{t_0}^{\pi} \left[ \beta_{t_0, T} \widetilde{R}(W_T, G_T) + \sum_{t=t_0}^{T-1} \beta_{t_0, t} \overline{R}_t(W_t, G_t, \alpha_t) \right], \tag{A.3}$$

and we have

$$\widetilde{V} = \max_{H} \left[ \overline{V}(W - H, G_{t_0}) + \sum_{t=t_0}^{T-1} \beta_{t_0, t} \,_{t_0} p_t^{S} \, U_H(H, G_t = 1) \right]. \tag{A.4}$$

The decision for allocation to housing is made from total wealth, and the remaining liquid assets after the house value has been subtracted are then available for the stochastic control problem to optimize consumption and investments.

The separation of housing can also be proven with recursion on the value function in the Bellman equation in a similar manner.

### References

Agnew, Julie, Hazel Bateman, and Susan Thorp (2013), "Superannuation Knowledge and plan behaviour." The Finsia Journal of Applied Finance, 45–50.

Ameriks, John, Andrew Caplin, Steven Laufer, and Stijn Van Nieuwerburgh (2011), "The Joy of Giving or Assisted Living? Using Strategic Surveys to Separate Public Care Aversion from Bequest Motives." *The Journal of Finance*, 66, 519–561.

- ASFA (2015), "Superannuation Statistics." URL http://www.superannuation.asn.au/ArticleDocuments/129/SuperStats-August2015.pdf.aspx.
- Australian Bureau of Statistics (2011), "Household Expenditure Survey and Survey of Income and Housing Curf Data." URL http://www.abs.gov.au/ausstats/abs@.nsf/mf/6503.0.
- Australian Bureau of Statistics (2012), "Life Tables, States, Territories and Australia, 2009-2011." URL http://www.abs.gov.au/AUSSTATS/abs@.nsf/DetailsPage/3302.0.55.0012009-2011.
- Australian government department of Families, Community Services, Housing and Indigenous Affairs (2016), "Guides to Social Policy Law." URL http://guides.dss.gov.au/guide-social-security-law.
- Bateman, Hazel, Susan Thorp, and Geoffrey Kingston (2007), "Financial engineering for Australian annuitants." In *Retirement Provision in Scary Markets*, 123–144, Oxford University Press.
- Bäuerle, Nicole and Ulrich Rieder (2011), Markov Decision Processes with Applications to Finance. Universitext, Springer Berlin Heidelberg, Berlin, Heidelberg.
- Bernicke, Ty (2005), "Reality Retirement Planning: A New Paradigm for an Old Science." *Journal of Financial Planning*, 0605, 1–8.
- Blake, David, Douglas Wright, and Yumeng Zhang (2014), "Age-dependent investing: Optimal funding and investment strategies in defined contribution pension plans when members are rational life cycle financial planners." *Journal of Economic Dynamics and Control*, 38, 105–124.
- Cho, Sang-wook Stanley and Renuka Sane (2013), "Means-Tested Age Pensions and Homeownership: Is there a link?" *Macroeconomic Dynamics*, 17, 1281–1310.
- Clare, R. (2014), "Spending patterns of older retirees: New ASFA Retirement Standard." Technical Report September quarter 2014, ASFA Research and Resource Centre.
- De Nardi, Maria Cristina (2004), "Wealth inequality and intergenerational links." Review of Economic Studies, 71, 743–768.
- De Nardi, Mariacristina, Eric French, and John B. Jones (2010), "Why Do the Elderly Save? The Role of Medical Expenses." *Journal of Political Economy*, 118, 39–75.
- Department of Treasury (2010), "Australia to 2050: future challenges." Technical Report January, URL http://www.voced.edu.au/content/ngv10852.
- Ding, Jie (2013), "Modelling Post-Retirement Finances in the Presence of a Bequest Motive, Housing and Public Pension." SSRN Electronic Journal.
- Ding, Jie, Geoffrey Kingston, and Sachi Purcal (2014), "Dynamic asset allocation when bequests are luxury goods." *Journal of Economic Dynamics and Control*, 38, 65–71.
- Fernández-Villaverde, Jesús and Dirk Krueger (2007), "Consumption over the Life Cycle: Facts from Consumer Expenditure Survey Data." Review of Economics and Statistics, 89, 552–565.
- Higgins, Tim and Steven Roberts (2011), "Variability in expenditure preferences among elderly Australians." Australian National University, presented at the 19th Annual Colloquium of Superannuation Researchers, 1–28.
- Hubbard, R. Glenn, Jonathan Skinner, and Stephen P. Zeldes (1995), "Precautionary Saving and Social Insurance." *Journal of Political Economy*, 103, 360.
- Hulley, Hardy, Rebecca Mckibbin, Andreas Pedersen, and Susan Thorp (2013), "Means-Tested Public Pensions, Portfolio Choice and Decumulation in Retirement." *Economic Record*, 89, 31–51.
- Hurd, Michael and James Smith (2002), "Expected Bequests and Their Distribution." Technical Report No. 9142, National Bureau of Economic Research, Cambridge, MA.

- Hurst, Erik and James Ziliak (2004), "Do Welfare Asset Limits Affect Household Saving? Evidence from Welfare Reform." Technical report, National Bureau of Economic Research, Cambridge, MA.
- Iskhakov, Fedor, Susan Thorp, and Hazel Bateman (2015), "Optimal Annuity Purchases for Australian Retirees." *Economic Record*, 91, 139–154.
- Kahaner, David, Cleve B. Moler, Stephen Nash, and George E. Forsythe (1988), "Numerical methods and software."
- Kingston, Geoffrey and Lance Fisher (2014), "Down the Retirement Risk Zone with Gun and Camera." Economic Papers: A journal of applied economics and policy, 33, 153–162.
- Kudrna, George (2014), "Means Testing of Australia's Age Pension : A Numerical Analysis with an OLG Model."
- Kudrna, George and Alan Woodland (2011a), "An inter-temporal general equilibrium analysis of the Australian age pension means test." *Journal of Macroeconomics*, 33, 61–79.
- Kudrna, George and Alan D. Woodland (2011b), "Implications of the 2009 Age Pension Reform in Australia: A Dynamic General Equilibrium Analysis." *Economic Record*, 87, 183–201.
- Lockwood, Lee M. (2014), "Incidental bequests: Bequest motives and the choice to self-insure late-life risks." Working Paper 20745, National Bureau of Economic Research.
- Merton, Robert C (1969), "Lifetime Portfolio Selection Under Uncertainty: The Continuous Time Case." Review of Economics and Statistics, 51, 247–257.
- Merton, Robert C (1971), "Optimum consumption and portfolio rules in a continuous-time model." Journal of Economic Theory, 3, 373–413.
- Milevsky, Moshe A and Huaxiong Huang (2011), "Risk Management Spending Retirement on Planet Vulcan: The Impact of Longevity Risk Aversion on Optimal Withdrawal Rates." *Risk Management*, 24–38.
- Neumark, David and Elizabeth Powers (1997), "The Effect of Means-Tested Income Support for the Elderly on Pre-Retirement Saving: Evidence from the SSI Program in the U.S." Technical report, National Bureau of Economic Research, Cambridge, MA.
- Olsberg, Diana and Mark Winters (2005), "Ageing in place: intergenerational and intrafamilial housing transfers and shifts in later life."
- Samuelson, Pa (1969), "Lifetime portfolio selection by dynamic stochastic programming." The Review of Economics and Statistics, 51, 239–246.
- Spicer, Alexandra, Olena Stavrunova, and Susan Thorp (2013), "How Portfolios Evolve After Retirement: Evidence from Australia." CAMA Working Papers 2013-40, Centre for Applied Macroeconomic Analysis, Crawford School of Public Policy, The Australian National University.
- Tran, Chung and Alan Woodland (2014), "Trade-offs in means tested pension design." *Journal of Economic Dynamics and Control*, 47, 72–93.
- Yaari, Menahem E. (1964), "On the consumer's lifetime allocation process."
- Yaari, Menahem E. (1965), "Uncertain Lifetime, Life Insurance, and the Theory of the Consumer." The Review of Economic Studies, 32, 137.
- Yogo, Motohiro (2011), "Portfolio Choice in Retirement: Health Risk and the Demand for Annuities, Housing, and Risky Assets." SSRN Electronic Journal.