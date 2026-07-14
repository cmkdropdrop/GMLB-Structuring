https://actuaries.org/app/uploads/2025/07/LIFE_Fung_Ignatieva_Sherris_Paper_Lyon2013.pdf
→ https://actuaries.org/app/uploads/2025/07/LIFE_Fung_Ignatieva_Sherris_Paper_Lyon2013.pdf
Content-Type: application/pdf

Systematic Mortality Risk: An Analysis of
Guaranteed Lifetime Withdrawal Benefits in
Variable Annuities
This version: 9 January 2013
Man Chung Fung a, Katja Ignatieva b, Michael Sherris c
aUniversity of New South Wales Sydney, Australia (m.c.fung@unsw.edu.au)
bUniversity of New South Wales Sydney, Australia (k.ignatieva@unsw.edu.au)
cUniversity of New South Wales Sydney, Australia (m.sherris@unsw.edu.au)
Abstract
Guaranteed lifetime withdrawal benefits (GLWB) embedded in variable annuities
provide a type of life annuity which addresses systematic mortality risk while indirectly protecting the policyholders from the downside risk of fund investment. Using
tractable equity and stochastic mortality model, we evaluate GLWB in a continuous
time framework. The paper provides an extensive study of how different sets of financial and demographic parameters affect the fair guarantee fee being charged, as
well as their effects on the profit and loss distribution if they are different to the true
parameters of the underlying dynamics. We show that parameter risk is significant
since the guarantee is of a very long term nature. We quantify systematic mortality
risk component underlying the guarantee and study how different levels of equity
exposure chosen by the insured affect the exposure of systematic mortality risk for
the guarantee providers. Effectiveness of static hedge of systematic mortality risk is
examined with respect to different levels of equity exposure.
Key words: Variable annuity, guaranteed lifetime withdrawal benefits (GLWB),
systematic mortality risk, parameter risk, model risk, static hedging
1
1 Introduction
Variable annuities (VA), introduced in the 1970s in the US, have proven to be popular
among investors and retirees especially in North America and Japan. VA are insurance
contracts which allow policyholders to invest their retirement savings in the mutual
funds. They are attractive because policyholders’ retirement savings can have certain
exposure to the equity market whereas benefits are based on the performance of
the underlying funds, enhanced by certain tax advantages. In addition to the VA,
policyholders can elect different types of guarantee to protect their retirement savings
by paying various amounts of guarantee fees. Since 1990s, two kinds of embedded
guarantees have been offered in such policies. These include the Guaranteed Minimum
Death Benefits (GMDB) and the Guaranteed Minimum Living Benefits (GMLB), see
Hardy (2003) and Ledlie et al. (2008). There are four types of guarantee that fall into
the category of GMLB:
• Guaranteed Minimum Accumulation Benefits (GMAB)
• Guaranteed Minimum Income Benefits (GMIB)
• Guaranteed Minimum Withdrawal Benefits (GMWB)
• Guaranteed Lifetime Withdrawal Benefits (GLWB)
According to LIMRA 1, the election rates of GLWB, GMIB, GMAB and GMWB in
the fourth quarter of 2011 in the US corresponded to 59%, 26%, 3% and 2%, respectively. The popularity of GLWB can be attributed to its flexibility in a sense that the
policyholder can decide how much he/she wants to withdraw every year, subject to
a limited nominal yearly amount, for the lifetime of the insured and regardless of the
performance of the investment. After the death of the insured, any savings remaining
in the account will be returned to the insured’s beneficiary. GLWB is essentially a life
annuity with flexible features compared to the traditional life annuity contracts.
Being a type of a life annuity with benefit linked to the equity market, insurers
who offer GLWB embedded in variable annuities are subject to several types of risk,
namely, equity risk, interest rate risk, withdrawal risk and, in particular, systematic mortality risk. As opposed to unsystematic mortality risk, which is diversifiable,
systematic mortality risk, a.k.a. longevity risk, cannot be eliminated through diversification. Systematic mortality risk arises due to stochastic, or unpredictable nature
of life expectancy. Insurance providers offering GLWB are subject to systematic mortality risk as the guarantee promises to the insured a stream of income for life, even
if the investment account is depleted. Systematic mortality risk can be addressed by
means of stochastic mortality modeling, which can be approached via the so-called
intensity-based framework, see e.g. Biffis (2005).
1.1 Motivation and Contribution
It has been widely documented that starting with the global financial crisis in 2007-
2008, VA providers have been suffering from unexpected large losses arising due to the
1 http : //www.limra.com/def ault.aspx
2
fact that the benefits secured by different types of guarantee were too generous. High
volatility of equity markets during this period has also exacerbated the difficulty in
managing risks underlying the guarantees because of the unexpectedly high hedging
costs. 2 Guarantees turned out to be inherently difficult to price and manage because
of their long term nature. In particular, guarantees offering lifetime income incorporate systematic mortality risk due to the fact that people live longer than expected.
A prime example is the GLWB.
To our knowledge the existing literature does not study in details the systematic mortality risk underlying the GLWB. Several authors concentrate either on the volatility
risk (Kling et al. (2011)) or briefly discuss mortality risk (Piscopo and Haberman
(2011)) as part of a wider study on guarantees/annuities (Bacinello et al. (2011)and
Ngai and Sherris (2011)). A more detailed analysis of the impact of the systematic
mortality risk on valuation and hedging, as well as its interaction with other risks
underlying the GLWB is required. These issues are addressed in the present paper.
As discussed in Bacinello et al. (2011), there are three steps involved in a reliable
risk management process. First or all, it is risk identification. When looking at the
benefit and the premium component of a guarantee, different sources of risk, whether
hedgeable or not, can be determined. 3 The second step involves risk assessment. Due
to the long term nature and complicated payout of the guarantee, there are likely to
be a range of risks involved. Assessing their interactions is required to provide certain
insights prior to the set up of an adequate risk management program. Risk assessment
can also be useful when determining which sources of risk have larger impact on
pricing and risk management of the guarantee. The third step is the risk management
action. Risk management of the guarantee generally consists of capital reserving and
hedging (Hardy (2003) and Ledlie et al. (2008)). Selecting the appropriate hedge
instruments and determining hedging frequency (in particular, static or dynamics
hedging) are important issues that should be addressed, while taking into account
constraints such as transaction costs and liquidity of the hedge instruments. A reliable
risk management process is of a great importance in case of GLWB, as it is a long
term contract which lasts, on average, for several decades. Also due to its popularity,
VA providers are likely to have a large VA portfolio built up when GLWB is an
underlying guarantee.
In this paper we apply the risk management process described above to analyze equity
and systematic mortality risks underlying the GLWB, as well as their interactions.
Our approach relies on risk measures and the profit and loss (P&L) distribution in
order to identify, assess and partially mitigate financial and demographic risks, which
occur because of the specific design of the guarantee.
One of the main challenges of the present paper is to asses how different sets of
financial and demographic parameters will affect the guarantee fees being charged.
In particular, we are interested in their effects on the P&L distributions, if they are
set to be different from the “true” parameters of the underlying dynamics. Parameter
2 See for instance “A challenging environment”, June 2008 and “A balanced structure?”,
February 2011 in the Risk Magazine.
3 For instance, uncertainty stemming from the behavior of policyholders is an unhedgeable
risk, which requires insurance companies to assess policyholders general past behavior.
3
risk turns out to be significant as GLWB is of a very long term nature, lasting for
the lifetime of the insured in a portfolio. The paper also contributes to the study of
model risk where guarantee providers assume mortality to be deterministic whereas
life expectancy of the insured is stochastic in its nature.
Furthermore, this research paper deals with quantification of the systematic mortality
risk underlying the guarantee using P&L analysis, which turns out to be particularly
useful for determining an appropriate capital reserve required due to unavailability
of hedging instruments to hedge the longevity risk. In particular, we show that different levels of equity exposure chosen by the insured have (in presence of systematic
mortality risk) a great impact on the GLWB from the guarantee providers’ point of
view. Finally, the effectiveness of static hedge of systematic mortality risk is assessed
with respect to different levels of equity exposure.
1.2 Literature Review
An underlying approach chosen in this paper in order address systematic mortality
risk is to model the mortality intensity as a stochastic process. Affine processes have
been proposed to model the mortality intensity as they allow closed form expressions
for important quantities such as survival probabilities. While Dahl and Moller (2006)
suggests a time inhomogeneous square root process, Schrager (2006) and Biffis (2005)
propose multi-factor affine processes which allow to capture the evolution of mortality
intensity for all ages simultaneously. A concise survey of mortality modeling and the
development of longevity market can be found in Cairns et al. (2008).
One of the earliest modeling frameworks that focuses on GLWB is discussed in Holz
et al. (2007), who take into account policyholder’s behavior and different product
features. However, the authors address longevity risk by considering different mortality tables without assuming that the underlying mortality intensity is stochastic.
Piscopo and Haberman (2011) decomposes the value of GLWB into the death and
living benefit and provide sensitive analysis. Authors address mortality risk by taking
into account mortality shocks in an adjusted mortality table. Kling et al. (2011) offer
a detailed pricing and hedging analysis of GLWB focusing on the management of
volatility risk, and ignore systematic mortality risk. Ngai and Sherris (2011) study
a range of life annuity contracts, including GLWB, which are subject to systematic
mortality risk with different static hedging strategies for longevity risk management.
The current paper provides further detailed analysis that have been conducted in the
above mentioned studies, focusing on GLWB.
Papers that investigate the impact of systematic mortality risk on guarantees other
than GLWB include Ballotta and Haberman (2006) who value guaranteed annuity
options (GAOs) and provide sensitivity analysis taking into account the interest rate
risk and the systematic mortality risk. Kling et al. (2012) offer an analysis similar to
Ballotta and Haberman (2006), but considering both, GAOs and guaranteed minimal
income benefits (GMIB), and taking into account different hedging strategies. Ziveyi
et al. (2012) price European options on deferred insurance contracts including pure
endowment and deferred life annuity (i.e. GAO) by solving analytically the pricing
partial differential equation in a presence of systematic mortality risk.
4
1.3 Outline
The remainder of the paper is organized as follows. Section 2 describes general features of GLWB including identification of risks and additional product features, and
addressing the benefit and the premium component of the guarantee. Section 3 specifies continuous time models to capture the underlying equity and systematic mortality
risk, where tractability of the models is considered as paramount since efficient pricing
and risk management is of practical importance given the complicated structure of
the guarantee. Section 4 evaluates GLWB using two approaches, which are shown to
be equivalent. It generalizes the result from pricing of GMWB in Kolkiewicz and Liu
(2012) to the case of GLWB. Sensitivity analysis is conducted in Section 5 showing
quantitatively which sources of risk have larger impact on pricing of GLWB. Section
6 analyzes the impact of different types of risk on the P&L distributions of the guarantee without incorporating any hedge strategies. Different levels of equity exposure,
parameter risk and model risk are considered. Section 7 studies the effectiveness of
static hedge of systematic mortality risk via S-forward with respect to different levels
of equity exposure. Section 8 summarizes the results and provides further concluding
remarks.
2 Features of GLWB
A variable annuity (VA) is an insurance product where a policyholder invests his or her
retirement savings in a mutual fund, which forms an investment account managed by
an insurance company. VAs are attractive because the investment enjoys certain tax
benefits (Cite). While the investment is subject to equity risk, a VA with GLWB rider
guarantees that a capped amount of income can be withdrawn from the account every
year for the lifetime of the policyholder, even if the investment account is depleted
before the policyholder dies. Furthermore, any remaining value in the account will be
returned to the policyholder’s beneficiary. In return, the policyholder is required to
pay guarantee fees every year, which is proportional to the investment account value.
The simplest type of GLWB, which in the following will be referred to as a plain
GLWB attached to a VA, is described in what follows in a continuous time framework.
Let A(0) be the retirement savings invested in a variable annuity at time t = 0. For a
plain GLWB, the guaranteed withdrawal amount, that is, the amount which is allowed
to be withdrawn from the account per unit of time, is determined as g·A(0) where g is
the so called guaranteed withdrawal rate. A typical value of g is 5% for a policyholder
aged 65 at t = 0. The policyholder has the freedom to decide how much to withdraw
per unit of time. However, a penalty may arise if the withdrawal amount is higher
than the guaranteed withdrawal amount allowed by the insurer. The guarantee fee
paid by the policyholder per unit of time is determined as αg · A(t) where αg is the so
called guaranteed fee rate and A(t) is the account value at time t. From the insurer’s
point of view, the liability and the fee structure of a plain GLWB can be described
concisely by two scenarios which are captured in Fig. 1 and 2.
For both scenarios we assume a static withdrawal strategy, where the policyholder
5
Fig. 1. Scenario 1 (liability for the insurer): policyholder dies at the age of 100 years, 20
years after the account value is depleted.
Fig. 2. Scenario 2 (no liability for the insurer): policyholder dies at the age of 100 years,
when the account value is still positive.
receives exactly the guaranteed withdrawal amount per unit of time. An alternative
strategy, proposed in Milevsky and Salisbury (2006), is a dynamic withdrawal, which
leads to an optimal stopping problem and aims to maximize the value of the guarantee.
In Fig. 1, the policyholder dies at the age of 100 years and the account value drops to
zero when the policyholder is 80 years old. The insurance company receives guarantee
fees during the period when the policyholder is aging from 65 to 80. As the account
is depleted and the policyholder is still alive at the age of 80, the insurance company
has to continue paying the guaranteed withdrawal amount during the period when
the policyholder is aging from 80 to 100. In this scenario there is a liability for the
insurer. Another scenario is captured in Fig. 2. Again, the policyholder dies at the
age of 100, however, there is still some positive amount left in the account at the
time of death of the policyholder. In this scenario the insurance company receives the
guarantee fees during the lifetime of the policyholder and there is no liability for the
insurer.
A plain GLWB can be enriched by adding other features such as a roll-up feature
and a step-up (or ratchet) feature. The roll-up feature allows guaranteed withdrawal
6
amount to increase every year by a fixed amount, given the policyholder has not yet
started to withdraw money. The contract which contains a set-up option, allows the
guaranteed withdrawal amount to increase at specified points in time (set-up dates),
if at that point in time the percentage withdrawal rate exceeds the contractually
guaranteed amount. In case of deferred version of the contract, as opposed to immediate withdrawals, the policyholder cannot withdraw money during the deferred
period. The details on different featured embedded in the guarantee can be found in
e.g. Piscopo and Haberman (2011).
From Fig. 1 and Fig. 2 and the discussion above, one may note that GLWB providers
are subject to three types of risk: financial risk, demographic risk and behavioral risk.
Financial risk includes interest rate risk and equity risk. Demographic risk consists
of unsystematic and systematic mortality risk. Different withdrawal behaviors of the
policyholder, which might or might not be rational, constitute the behavioral risk.
In the following sections dealing with the model set-up, valuation, hedging and sensitivity analysis, we assume constant interest rate and constant volatility. The withdrawal rate is assumed to be static and there is not lapse. Finally, payments are
immediate (not deferred), that is, the withdrawals start immediately and there is no
defer period for investment growth. We do not consider possible roll-up or set-up option, but note that the derivations presented below could be easily generalized when
additional features are incorporated in the contract. Furthermore, we focus on systematic mortality risk and believe that our results are robust with respect to other
features which could be possibly incorporated in the model.
3 Model Specification
Tractable continuous-time models are specified to capture equity and systematic mortality risk underling GLWB in variable annuities. Let (Ω, F, P) be a filtered probability
space where P is the real world probability measure. The filtration Ftis constructed
as
Gt = σ{(W1(s), W2(s)) : 0 ≤ s ≤ t}
Ht = σ{1{τˆ≤s} : 0 ≤ s ≤ t}
Ft = Gt ∨ Ht
where Gtis generated by two independent standard Brownian motions, W1 and W2,
which are associated with the uncertainties related to equity and mortality intensity, respectively. The subfiltration Ht represents information set that would indicate
whether the death of a policyholder has occurred before time t. The stopping time
τˆ is interpreted as the remaining lifetime of an insured. For a detailed exposition of
modeling mortality under the intensity-based framework refer to Biffis (2005).
7
3.1 Investment Account Dynamics
In our setup the policyholder can invest his or her retirement savings in an investment
fund that has both, equity and fixed income exposure. Under the real world probability
measure P, we assume that the equity component follows the geometric Brownian
motion
dS(t) = µS(t)dt + σS(t)dW1(t), (3.1)
and the fixed income investment is represented by the money market account B(t)
with dynamics dB(t) = r B(t)dt where the interest rate r is constant. Let δ1(t) and
δ2(t) denote the number of units invested in S(·) and B(·), respectively. The selffinancing investment fund V (·) has the following dynamics
dV (t) = δ1(t)dS(t) + δ2(t)dB(t)
= (µδ1(t)S(t) + rδ2(t)B(t))dt + σδ1(t)S(t)dW1(t)
= (µπ(t) + r(1 − π(t)))V (t)dt + σπ(t)V (t)dW1(t) (3.2)
where the fraction π(·) is defined as π(t) = δ1(t)S(t)
V (t)
, and is interpreted as the proportion of the retirement savings being invested in the equity component. Since shortselling is not allowed, we set 0 ≤ π(·) ≤ 1.
Because of the election of GLWB, the investment account A(·) held by the policyholder is being charged continuously with guarantee fees by the insurer. Typically,
the guarantee fee charged is proportional to the investment account A(·). Recall that
we denote the guarantee fee rate by αg. We consider the case that a policyholder
withdraws a constant amount continuously until death and the withdrawal amount
is proportional to the guarantee base, which is assumed to be the initial investment
A(0). We denote the (static) guarantee withdrawal rate by g, which is so-named because the withdrawals are guaranteed by the insurer regardless of the investment
performance, and define G = g · A(0) to be the withdrawal amount per unit of time.
The investment account of the policyholder satisfies the following dynamics:
dA(t) = (µπ(t) + r(1 − π(t)) − αg)A(t)dt − Gdt + σπ(t)A(t)dW1(t) (3.3)
with A(·) ≥ 0, since the investment account cannot be negative. In the following, we
assume that π(·) is constant, that is, the policyholder invests in a fixed proportion
of his/her retirement savings in the equity and fixed income markets throughout the
investment period. In particular, we consider five cases where π ∈ {0, 0.3, 0.5, 0.7, 1}.
Each value corresponds to a specific risk-preference of the retiree where a larger value
of π indicates that the insured prefers to have a larger equity exposure in his/her
savings, which would result in a higher potential growth but will be subject to higher
volatility as well. By allowing different levels of equity exposure, we will be able to
study the interaction between equity and systematic mortality risk due to the specific
design of the product.
8
3.2 Mortality Model
In order to select an appropriate model for our problem setting, we rely on the following three criteria. First of all, the model should be qualitatively reasonable with
mortality intensity being strictly positive. Moreover, as argued in Cairns et al. (2006)
and Cairns et al. (2008), it is unreasonable to assume that mortality intensity is mean
reverting, even if the mean level is time dependent. 4 The second criterion is tractability. Given the complicated payout structure, a tractable stochastic mortality model
is required for an efficient pricing and risk management of GLWB. In particular, the
model should allow analytical expressions for important quantities, such as survival
probabilities. Further to that, it should be computationally not very burdensome, in
a sense that one should be able to simulate fast and accurate the derived solutions
paths of underlying dynamics. Finally, since the paper focuses on the impact of systematic mortality risk, the ability of the model to be reduced to a simple deterministic
mortality model would provide an accommodating ground to investigate the effect of,
and the difference between, systematic and unsystematic mortality risk underlying
the guarantee.
Given these criteria, we propose a one-factor, non mean-reverting and time homogeneous affine process for modeling the mortality intensity process µx+t(t) of a person
aged x at time t = 0, as follows:
dµx+t(t) = (a + b µx+t(t))dt + σµ
√
µx+t(t) dW2(t), µx(0) > 0. (3.4)
Here, a ̸= 0, b > 0 and σµ represents the volatility of mortality intensity.
In the special case when σµ = a = 0, the model reduces to the well-known constant
Gompertz specification. 5 Hence, we will be able to conveniently compare the impact
of stochastic mortality with that of deterministic mortality in the following sections.
The values of the parameters a, b and σµ are obtained by calibrating the survival
curve implied by the mortality model to the survival curve obtained from real data
as documented in the Australian Life Tables 2005-2007 6, for a person aged 65. The
result is reported in Table 1.
Table 1
Calibrated parameters for the mortality model.
a b σµ µ65(0)
0.001 0.087 0.021 0.01147
The estimated values of the parameters a and σµ indicate that the proposed mortality
intensity process Eq.(3.4) is strictly positive 7 and is non mean-reverting. Modeling
4 Mean reverting behavior of mortality intensity would indicate that if mortality improvements have been faster than anticipated in the past then the potential for further mortality
improvements will be significantly lower in the future.
5 From the Gompertz model µx(0) = yebx, we have µx+t(t) = µx(0)ebt which satisfies
Eq.(3.4) with σµ = a = 0.
6 http : //www.aga.gov.au/publications/#life tables
7
It can be shown that if a ≥ σ
2
µ/2 then the mortality intensity process Eq.(3.4) is strictly
positive, see Filipovic (2009).
9
mortality intensity using a one-factor 8 and time homogeneous affine process can
reduce significantly computational time, since the dynamics allow to exactly simulate
the model and to derive analytical expressions for survival probabilities. Thus, the
proposed model Eq.(3.4) satisfies all criteria stated above.
Since the mortality model proposed is affine and time homogeneous, we have an
analytical expression for the survival probability sPx+t of the remaining lifetime ˆτ of
an individual aged x at time 0. Assuming that the individual is still alive at t > 0
and that σµ > 0, we obtain
sPx+t = E
Q
t
(
e
−
∫ t+s
t
µx+v(v)dv)
= C1(s)e
−C2(s)µx+t(t)
, (3.5)
where
C1(s) =


2γe
1
2
(γ−b)s
(γ − b)(e
γs − 1) + 2γ


2a
σ2
µ
, C2(s) = 2(e
γs − 1)
(γ − b)(e
γs − 1) + 2γ
(3.6)
and γ =
√
b
2 + 2σ2
µ
. For details refer to Dahl and Moller (2006). The density function
of the remaining lifetime can be calculated as
fx+t(s) = −
d
ds sPx+t = −
dC1(s)
ds e
−C2(s)µx+t(t) +
dC2(s)
ds sPx+t µx+t(t) (3.7)
where
dC1(s)
ds = C1(s)
2a(γ − b)
σ
2
µ
(
1
2
−
γe
γs
(γ − b)(e
γs − 1) + 2γ
)
(3.8)
and
dC2(s)
ds =
2γe
γs
(γ − b)(e
γs − 1) + 2γ
(
1 −
1
2
(γ − b)C2(s)
)
. (3.9)
For the case when σµ = 0, the survival probability and the density functions can be
directly calculated to obtain
sPx+t = e
a
b
s+ 1
b (1−e
bs)(µx+t(t)+ a
b )
(3.10)
and
fx+t(s) = sPx+t
(
a
b
(
e
bs − 1
)
+ e
bsµx+t(t)
)
, (3.11)
respectively. Furthermore, by setting a = 0 in Eq.(3.10) and Eq.(3.11) we obtain the
survival probability and the density function of the Gompertz model.
Remark 1 Luciano and Vigna (2008) study a similar model with a = 0 and σµ >
0. However, such specification could be problematic since, as it can be shown from
Eq.(3.10), it holds
lims→∞ sPx+t = e
− 2
γ−b
µx+t(t)
,
8 One may argue that the past mortality data experiences differences between the evolution
of mortality rates for different ages (Cite). However, applying a multi-factor mortality model
to the pricing of GLWB requires substantial computational resources (refer to Section 4)
and hence, we restrict ourselves to a one-factor model instead.
10
that is, the survival probability converges to e
− 2
γ−b
µx+t(t) which only approaches to zero
when σµ = 0. It turns out that if we set a ̸= 0 this problem is not prsent. Furthermore,
the mortality intensity µx+t(t) under such a specification has a non zero probability of
reaching zero when σµ > 0 (regardless of the value of b). Therefore, assuming a ̸= 0,
while σµ > 0, the dynamics specified in Eq.(3.4) produce a more satisfactory stochastic
model for the mortality intensity process.
3.3 Risk-Adjusted Measure
For the purpose of no-arbitrage valuation and hedging, we require the dynamics of
the account process A(t) and the mortality intensity µx+t(t) to be written under the
risk-adjusted measure Q. We define WQ
1
(t) and WQ
2
(t) as
dWQ
1
(t) = µ − r
σ
dt + dW1(t)
dWQ
2
(t) = λ
√
µx+t(t) dt + dW2(t). (3.12)
These are by the Girsarov Theorem, see e.g. Bjork (2009), standard Brownian motions
under the Q measure with µ−r
σ
and λ
√
µx+t(t) representing the market price of equity
risk and systematic mortality risk, respectively. Hence, we can write the investment
account process and the mortality intensity under Q as follows:
dA(t) = (r − αg)A(t)dt − G dt + π σ A(t)dWQ
1
(t) (3.13)
dµx+t(t) = (a + (b − λσµ))µx+t(t)dt + σµ
√
µx+t(t)dWQ
2
(t). (3.14)
By imposing the market price of systematic mortality risk to be λ
√
µx+t(t), the mortality intensity process is still a time homogeneous affine process under Q, as can
be seen from Eq.(3.14). 9 Thus, this specification preserves tractability of the model
when pricing the guarantee under Q. From Eq.(3.13) we observe that the fraction π
invested in the equity market affects merely the volatility of the investment account
process under Q.
Using parameters estimated for the stochastic model in Table 1 and allowing volatility
of mortality σµ to vary, we plot survival probabilities and density functions of the
remaining lifetime of an individual aged 65 in the left and the right panel of Fig.3,
respectively. The estimated parameters produce reasonable survival probabilities and
density functions of the remaining lifetime. In particular, an increase in σµ leads to
an improvement in survival probability under the risk-adjusted measure Q. Hence,
higher volatility of mortality leads not only to higher uncertainty about the timing
of death of an individual, but also to an increase in the survival probability. Similar
figures are obtained when the market price of systematic mortality risk coefficient λ
is varying while all other parameters are fixed to the values specified in Table 1, see
Fig. 4. Negative values of λ indicate a decline in survival probability, while positive
9 The mortality intensity process might become mean reverting when b < λσµ which is not
a favorable, as discussed above.
11
0 5 10 15 20 25 30 35 40 45
0
0.1
0.2
0.3
0.4
0.5
0.6
0.7
0.8
0.9
1
Remaining Lifetime s (year)
Survival Probability s P65
σ
µ
=0.00
σ
µ
=0.011
σ
µ
=0.021
σ
µ
=0.031
σ
µ
=0.041
σ
µ
=0.051
0 5 10 15 20 25 30 35 40 45
0
0.005
0.01
0.015
0.02
0.025
0.03
0.035
0.04
0.045
Remaining Lifetime s (year)
Density f65(s)
σ
µ
=0.00
σ
µ
=0.011
σ
µ
=0.021
σ
µ
=0.031
σ
µ
=0.041
σ
µ
=0.051
Fig. 3. Survival probabilities and densities of the remaining lifetime of an individual aged
65 with different values of σµ. Other parameters are as specified in Table 1 with λ = 0.4.
0 5 10 15 20 25 30 35 40 45
0
0.1
0.2
0.3
0.4
0.5
0.6
0.7
0.8
0.9
1
Remaining Lifetime s (year)
Survival Probability s P65
λ=−0.4
λ=0.0
λ=0.4
λ=0.8
λ=1.2
λ=1.6
0 5 10 15 20 25 30 35 40 45
0
0.005
0.01
0.015
0.02
0.025
0.03
0.035
0.04
0.045
Remaining Lifetime s (year)
Density f65(s)
λ=−0.4
λ=0.0
λ=0.4
λ=0.8
λ=1.2
λ=1.6
Fig. 4. Survival probabilities and densities of the remaining lifetime of an individual aged
65 with different values of λ. Other parameters are as specified in Table 1. The case λ = 0
corresponds to the survival curve under P.
values lead to an improvement in survival probability under the risk-adjusted measure
Q. Thus, under the proposed model specification, a negative value of λ is suitable for
setting the risk premium for a life insurance portfolio while a positive value of λ is
adequate for a life annuity business. 10 Corresponding expected remaining lifetime of
an individual as a function of σµ and λ, given G0, are plotted in the left and right
panel of Fig. 5 respectively. One observes that a linear increase in σµ or λ results
in an exponential increase in the expected remaining lifetime under the stochastic
mortality model.
10 If the longevity market is matured, then λ can be instead obtained via calibration to
market prices of longevity instruments following the no-arbitrage principle, see for instance
Russo et al. (2011).
12
0 0.01 0.02 0.03 0.04 0.05
10
15
20
25
30
35
40
σ
µ
Expected Remaining Lifetime
0 0.5 1 1.5
10
15
20
25
30
35
40
λ
Expected Remaining Lifetime
Fig. 5. Expected remaining lifetime of an individual aged 65 as a function of σµ (left panel)
and λ (right panel), given information G0.
4 Valuation of the GLWB
We generalize the pricing formulation of guaranteed minimum withdraw benefits
(GMWB) in Kolkiewicz and Liu (2012) to the case of GLWB. There are two approaches which suggest to decompose the cashflows involved in the benefit and the
premium structure of GMWB, which are shown to be equivalent in Kolkiewicz and
Liu (2012). The first approach was suggested by Milevsky and Salisbury (2006) while
the second approach was introduced in Aase and Perrson (1994) and Persson (1994)
under the “principle of equivalence under Q”. In the following, we describe both
valuation approaches for the case of GLWB and demonstrate that these are indeed
equivalent at any time t. We focus on plain GLWB with assumptions that policyholders exhibit static withdrawal behavior and withdrawals start immediately without
any defer period.
4.1 First Approach: Policyholder’s Perspective
We recall terminology above, and denote A(0) to be the initial investment, g the
guaranteed withdrawal rate, ˆτ the remaining lifetime of an individual aged x at time
0, ω the maximum age allowed in the model and sPx+t the survival probability of an
individual aged x + t at time t. From a policyholder’s perspective, income from static
withdrawals can be regarded as an immediate life annuity. The no-arbitrage value at
time t, denoted by V
P
1
(t), of an immediate life annuity can be expressed as
V
P
1
(t) = 1{τ>t ˆ } gA(0) ∫ ω−x−t
0
sPx+t e
−rs ds, (4.1)
where 0 ≤ t ≤ ω − x and 1{τ>t ˆ } denotes the indicator function taking value of one if
an individual is still alive at time t, and zero otherwise.
Let A˜(·) be the solution to the SDE (3.3) without the condition that A˜(·) is absorbed
at zero. Since the account value cannot be negative and any remaining amount in
13
the account at the time of death of the policyholder is returned to the policyholder’s
beneficiary, this cash inflow can be regarded as a call option with payoff (A˜(ˆτ ))+. By
the assumption that equity risk and systematic mortality risk are independent, we
can write the no-arbitrage value of this call option payoff at time t as
V
P
2
(t) = 1{τ>t ˆ }
∫ ω−x−t
0
fx+t(s)E
Q
t
(
e
−rs (A˜(t + s))+
)
ds. (4.2)
where fx+t(s) = −
d
ds (sPx+t) is the density function of the remaining lifetime of an
individual aged x + t at time t.
Both, V
P
1
(t) and V
P
2
(t) are cash inflows while the amount in the investment account
A(t) is viewed as a cash outflow to the VA provider. Under the first approach the
value of GLWB, denoted by V
P
(t), is defined as
V
P
(t) = V
P
1
(t) + V
P
2
(t) − 1{τ>t ˆ }A(t), (4.3)
which can be rewritten as
V
P
(t) = 1{τ>t ˆ }
(∫ ω−x−t
0
fx+t(s)
(
gA(0)
r
(
1 − e
−rs
)
+ E
Q
t
(
e
−rs(A˜(t + s))+
))
ds − A(t)
)
,
(4.4)
where integration by part have been applied in order to express Eq.(4.1) in terms
of the remaining lifetime density fx+t(s). To make the guarantee fair to both, the
policyholder and the insurer, at time t = 0 we must have V
P
(0) = 0, that is,
V
P
1
(0) + V
P
2
(0) = A(0). (4.5)
The fair guarantee fee rate, denoted by α
∗
g
, is defined as the guarantee fee rate that
solves Eq.(4.5).
4.2 Second Approach: Insurer’s Perspective
Under the second approach the value of GLWB is defined as the expected discounted
benefits minus the expected discounted premiums. Let ˆu be random variable defined
by
inf{u ≥ 0 | A(u) = 0},
that is, ˆu is the time when account value A(·) is depleted. We can express the expected
discounted benefits V
I
1
(t) as
V
I
1
(t) = 1{τ>t ˆ }
∫ ω−x−t
0
fx+t(s) E
Q
t
(∫ t+s
t+ˆu
gA(0)e
−r(v−t)
1{s>uˆ} dv)ds
= 1{τ>t ˆ }
∫ ω−x−t
0
fx+t(s)
(
gA(0)
r
)
E
Q
t
((
e
−ruˆ − e−rs
)+
)
ds (4.6)
and the expected discounted premiums V
I
2
(t) as
V
I
2
(t) = 1{τ>t ˆ }
∫ ω−x−t
0
fx+t(s) E
Q
t
(∫ t+(ˆu∧s)
t
e
−r(v−t)αg A(v) dv)
ds, (4.7)
14
where x1 ∧x2 = min{x1, x2}. Under the second approach, the value of GLWB at time
t is defined as
V
I
(t) = V
I
1
(t) − V
I
2
(t), (4.8)
and the fair guarantee fee rate can be calculated by solving
V
I
(0) = 0. (4.9)
The second approach follows the principle of equivalence under a risk-adjusted measure Q, see Aase and Perrson (1994) and Persson (1994).
4.3 Equivalence of the Two Valuation Approaches
To show that both approaches are equivalent, we consider the following investment
strategy. Suppose an individual invests an amount A(0) in a mutual fund-type account
held by an insurance company at time t = 0. In the future, the individual receives
cash flow from the account consisting of, firstly, an amount K = k · A(0) per unit of
time and secondly, an amount β · A(t) per unit of time, which is proportional to the
account value. Both amounts are withdrawn continuously until the account is depleted
or individual dies. Finally, any remaining amount in the account will be returned to
the individual’s beneficiary. In order to value the entire cash flow including the initial
investment, we notice that the insurer provides no financial obligation or guarantee
to the above arrangement, that is, the role of the insurer is redundant. Thus, the
no-arbitrage value of the above cash flow must be zero at time t = 0. That is, we have
E
Q
0
(
−A(0) + ∫ uˆ∧τˆ
0
e
−rv(K + βA(v))dv + e−rτˆ
(A˜(ˆτ ))+
)
= 0 (4.10)
where k ≥ 0, β ≥ 0 and A(ˆτ ) is written as (A˜(ˆτ ))+.
Using the fact that ∫ uˆ∧τˆ
0 =
∫ τˆ
0 −
∫ τˆ
uˆ
1{τ>ˆ uˆ} and rearranging the terms in Eq.(4.10), we
obtain
E
Q
0
(
−A(0) + ∫ τˆ
0
K e−rvdv + e
−rτˆ
(A˜(ˆτ ))+
)
= E
Q
0
(∫ τˆ
uˆ
e
−rvK1{τ>ˆ uˆ}dv −
∫ uˆ∧τˆ
0
e
−rvβA(v)dv)
(4.11)
The L.H.S. and R.H.S. of Eq.(4.11) are V
P
(0) and V
I
(0), respectively. Note that the
parameter k can be interpreted as the GLWB guaranteed withdrawal rate g, whereas β
is the guarantee fee rate corresponding to αg. By imposing the principle of equivalence
under Q we note that the R.H.S. of Eq.(4.11) equals zero, which implies that the
L.H.S. of Eq.(4.11) must equal to zero as well. Since the argument does not rely on
whether the remaining lifetime ˆτ is stochastic or deterministic, it is evident that the
equivalence holds for the valuation of GMWB where ˆτ = T = 1/k is deterministic,
assuming static withdrawal behavior. Table 2 reports in the last two columns the fair
guarantee fee rate α
∗
g
computed using two equivalent approaches summarized above.
One observes that for different values of parameters both approaches lead to the same
α
∗
g
, subject to simulation error with finite sample size.
15
Table 2
Fair guarantee fees obtained using two valuation approaches. Other parameters are as
specified in Table 3.
Case r σ g σµ λ Fee (1st App.) Fee (2nd App.)
1. 4% 20% 5.0% 0.04 0.2 0.49% 0.48%
2. 3% 25% 4.5% 0.02 0.0 0.46% 0.45%
3. 5% 15% 5.5% 0.05 0.8 0.50% 0.49%
4. 4% 20% 6.0% 0.00 0.0 0.73% 0.71%
One can easily generalize Eq.(4.10) to any time t ≥ 0. Both approaches defined
through (Eq.(4.5) and (4.9)), can be applied to valuate GLWB for any time t ≥
0. While the first approach is computationally more efficient, the second approach
supports theoretical argument that the market reserve of a payment process is defined
as the expected discounted benefit minus the expected discounted premium under a
risk-adjusted measure, see Dahl and Moller (2006).
Remark 2 For some special cases the equivalence, formulated in Eq.(4.11), can be
verified analytically. Assume that A(t) follows the dynamics in SDE (3.3) and
(1) let k = 0 and β ≥ 0. Eq.(4.11) becomes
A(0) = E
Q
0
(
e
−rτA(τ ) + ∫ τ
0
e
−rsβA(s)ds)
,
where the guarantee fee rate β can be interpreted as a continuous dividend yield,
see e.g., Bjork (2009). In particular, when β = 0, it states that the discounted
asset is a Q-martingale.
(2) let k > 0, β = 0 and σ = 0. In this case we have
dA(t) = (rA(t) − kA(0))dt
which has the solution
A(t) = A(0)e
rt +
kA(0)
r
(
1 − e
rt
)
.
The account A(t) can be interpreted as a money market account where a constant
amount is withdrawn continuously. Solving A(u) = 0 we have u =
1
r
ln k
k−r
. We
can verify Eq.(4.11) by noticing that
E
Q
0
(∫ u∧τˆ
0
e
−rvKdv + e−rτˆ
(A˜(ˆτ ))+
)
=
∫ ω−x
0
fx(s)
(∫ u∧s
0
e
−rvKdv + e−rs(A˜(s))+
)
ds
= A(0)
where the second equality is obtained by considering two cases s ≥ u and s < u
separately.
16
5 Sensitivity Analysis
As discussed in Section 1, risk assessment is important for analyzing the underlying
risks of an insurance product. Sensitivity analysis is one of such assessments where
one can quantify the impact of parameter risk on pricing performance of a product.
Given that the underlying guarantee is a long term contract, the effect of parameter
risk on pricing can be significant. In this section we study the effect on pricing and
the relationship between the fair guarantee fee rate α
∗
g
and several financial and
demographic factors, which include the age of the insured, the equity exposure π, the
interest rate level r, the volatility of mortality σµ and the market price of systematic
mortality risk coefficient λ. Table 3 summarizes parameters for the base case, which
will be used in the following when studying the effect of different risks on the fair
guarantee fee rate α
∗
g
.
Table 3
Parameters for the base case.
r A(0) σ π g a b σµ λ ω
4% 100 25% 0.7 5% 0.001 0.087 0.021 0.4 110
5.1 Sensitivity to Mortality Risk
Fig. 6 shows the impact of volatility of mortality σµ on the fair guarantee fee rate
α
∗
g
for a policyholder aged 65 and 75 (in the left and the right panel, respectively),
with different values of guaranteed withdrawal rate g. One observes that α
∗
g
is approximately an exponential function of σµ, which is consistent with the fact that the
expected remaining lifetime increases exponentially with respect to σµ, see the left
panel of Fig. 5. Values of guaranteed withdrawal rate g have a significant effect on
the fair guaranteed fee rate. When g increases from 5% to 5.5% (a relative increase of
10%), α
∗
g
increases from 0.5% to 0.8% (a relative increase of 60%) for the case when
σµ = 0.021. Thus, it seems to be reasonable for insurance providers to reduce benefits of the guarantee by focusing on g rather than α
∗
g
(since changing the guaranteed
withdrawal rate appears to have smaller impact on the benefits than changing the fair
guaranteed fee rate from a policyholder’s perspective). Furthermore, fair guaranteed
fee rates are significantly lower for a 75-years-old compared to a 65-year-old, assuming
that they have the same amount of retirement savings. This can be explained by the
fact that a 75-year-old has lower probability of exhausting the retirement savings in
the account before he or she dies under the condition that the withdrawal amount per
year is limited. Even if the account is depleted before policyholder dies, the period of
the income guaranteed by the provider for a 75-year-old is likely to be shorter than
in case of a 65-year-old.
Sensitivity of the fair guarantee fee rate to the market price of systematic mortality
risk coefficient λ is similar to the case of volatility of mortality, see Fig. 7. Explanation
for the result can be carried over from the case of volatility of mortality as discussed
above. Thus, Fig. 5, 6 and 7 suggest that the effect of varying parameters related
to systematic mortality risk on pricing can be indicated by the expected remaining
lifetime as a function of the underlying parameters.
17
0 0.01 0.02 0.03 0.04 0.05
0
0.2
0.4
0.6
0.8
1
1.2
1.4
1.6
1.8
2
σ
µ
α
*g (%)
aged 65
g = 4.5%
g = 5%
g = 5.5%
0 0.01 0.02 0.03 0.04 0.05
0
0.2
0.4
0.6
0.8
1
1.2
1.4
1.6
1.8
2
σ
µ
α
*g (%)
aged 75
g = 4.5%
g = 5%
g = 5.5%
Fig. 6. Sensitivity of the fair guarantee fee rate α
∗
g with respect to volatility of mortality
represented by σµ for policyholders aged 65 and 75.
0 0.5 1 1.5
0
0.2
0.4
0.6
0.8
1
1.2
1.4
1.6
1.8
2
λ
α
*g (%)
aged 65
g = 4.5%
g = 5%
g = 5.5%
0 0.5 1 1.5
0
0.2
0.4
0.6
0.8
1
1.2
1.4
1.6
1.8
2
λ
α
*g (%)
aged 75
g = 4.5%
g = 5%
g = 5.5%
Fig. 7. Sensitivity of the fair guarantee fee rate α
∗
g with respect to market price of systematic
mortality coefficient λ for policyholders aged 65 and 75.
5.2 Sensitivity to Financial Risk
Sensitivity of the fair guarantee fee rate with respect to the equity exposure π, represented by the volatility of the investment account π · σ, is shown in Fig. 8 where
σ is set to be 25% and π ∈ {0, 0.3, 0.5, 0.7, 1}. The fair guarantee fee rate appears to
be very sensitive to the equity exposure as α
∗
g
increases rapidly when π (and hence,
π·σ) increases. Positive relationship between α
∗
g
and π·σ is consistent with a financial
theory which suggest that options are more expensive when volatility of underlying
is high. When π is close to zero, α
∗
g
approaches zero as well for g ≤ 5%. The intuition
behind this observation is that in this case there is essentially no liability for the
guarantee provider since the guaranteed withdrawal rate is too low for the case when
π · σ = 0. Numerical experiment indicates that it takes more than 35 years for the
account to drop to zero when π · σ = 0 with g = 5%, and very few policyholders
are still alive by that time. This implies that the income guaranteed by the insurer
when the account is depleted will never be realized for most situations. Similarly to
the case of mortality risk, the fair guarantee fee rate is sensitive to g, as well as to
18
the age of the policyholder.
In contrast to the case of equity exposure and parameters related to mortality risk,
the relationship between the interest rate level r and α
∗
g
is negative, see Fig. 9. It
can be explained by considering Eq.(4.8) and Eq.(4.9) where the fair guarantee fee
rate is defined as the fee rate that makes the expected discounted benefit equals to
the expected discounted premium. As r increases, the present value of the benefit
and the premium decreases. However, since benefit is further away in the future than
premium, the present value of the benefit will drop faster than the present value of
the premium when r is high. As a result, α
∗
g will take lower value in the expected
discounted premium so that the expected discounted benefit and the expected discounted premium become equal.
Another interesting result arising from Fig. 9 is that the fair guarantee fee rate is very
sensitive to interest rates. For instance, when r drops from 2% to 1% for a 65-yearold policyholder while g is set equal 5.5%, α
∗
g
increases from approx. 3% to 7.5%.
This result indicates that it could be a challenging situation for GLWB providers
(who issue the guarantee when interest rate was high, and subsequently interest rate
declines to a very low level where it remains for a prolonged period of time) as fair
guarantee fee rates might be substantially undervalued in this circumstances. 11
0 5 10 15 20 25
0
0.2
0.4
0.6
0.8
1
1.2
1.4
1.6
1.8
2
π ×σ (%)
α
*g (%)
aged 65
g = 4.5%
g = 5%
g = 5.5%
0 5 10 15 20 25
0
0.2
0.4
0.6
0.8
1
1.2
1.4
1.6
1.8
2
π ×σ (%)
α
*g (%)
aged 75
g = 4.5%
g = 5%
g = 5.5%
Fig. 8. Sensitivity of the fair guarantee fee rate α
∗
g with respect to equity exposure π,
represented by volatility of the investment account π · σ, for policyholders aged 65 and 75.
5.3 Sensitivity to Parameter Risk
One of the most important issues related to the long term nature of GLWB, is that the
misspecification of parameters at the inception of the contract would have a significant
impact on pricing, which in turn would affect the realized profit and loss (P&L) for the
guarantee providers. Even if the proposed modeling framework captures effectively
qualitative features of the underlying financial and demographic variables, one would
11 The impact of market variables volatility, including the low interest rate environment in
the US starting with the global financial crisis in 2007-2008, is discussed in “American VA
providers de-risk to combat market volatility”, January 2012, Risk Magazine.
19
1 2 3 4 5 6 7 8
0
1
2
3
4
5
6
7
8
r (%)
α
*g (%)
aged 65
g = 4.5%
g = 5%
g = 5.5%
1 2 3 4 5 6 7 8
0
1
2
3
4
5
6
7
8
r (%)
α
*g (%)
aged 75
g = 4.5%
g = 5%
g = 5.5%
Fig. 9. Sensitivity of the fair guarantee fee rate α
∗
g with respect to interest rate level r for
policyholders aged 65 and 75.
still face a challenge related to the estimation of model parameters. The challenge
arises partly due to the fact that markets for the long term contracts are relatively
illiquid and hence, no reliable market prices required for parameter calibration are
available. However, one could rely on historical data, perhaps combined with expert
judgements, when estimating parameters and pricing a long term contract. Furthermore, given the long term nature of the guarantee, perfect hedging is economically
unviable when taking transaction costs and liquidity into account. This suggests that
the insurance provider must accept certain level of risk as the uncertainties underlying a guarantee cannot be completely eliminated. Therefore, providing sensitivity
analysis for the relative impact of risk inherent in parameter specification (that is, the
risk that parameters estimated at the inception of the contract may not be adequate
for capturing future dynamics of underlying variables described by the model) on
pricing of the guarantee. This is an important step towards understanding the risks
undertaken by guarantee providers who make the decision to issue the guarantee.
In the following we study the impact of different model parameters on pricing of
GLWB. As shown in Fig. 9, the fair guarantee fee rate is extremely sensitive to low
interest rates. This suggests to give first priority to the level of interest when pricing
GLWB, especially in a prolonged period of low interest rate environment. Fig.6 and
Fig.8 suggest that equity exposure π, and hence, volatility of the investment account
π · σ, may have a larger impact on pricing of GLWB than the volatility of mortality
σµ. However, the parameter risk of σµ is non-neglectable, which is illustrated by
considering the following scenario. Suppose that the guarantee provider estimates that
the fund’s volatility corresponds to σ = 20% at the time when guarantee is issued.
However, it turns out in the future that the ”true” parameter value corresponds to
σ = 25%. In this scenario the guarantee provider has mis-specified σ by 5%, with
g = 5%. This leads to an underestimation of the fee rate α
∗
g by approx. 0.2%, see
Fig. 8. On the other hand, such a magnitude of mis-pricing of α
∗
g
corresponds to
underestimation of the volatility of mortality σµ by approx. 0.04 − 0.021 = 0.019 (if
the original estimation of σµ is 0.021 at the inception of the guarantee while the ”true”
parameter value turns out to be σµ = 0.04 in the future), see Fig. 3. This indicates
that, on average, the remaining lifetime increases unexpectedly by approximately
three years, see Fig. 5 and Section 5.1. An underestimation of three years of expected
20
remaining lifetime for a period of 30 to 40 years 12 is possible and the risk of misspecifying σµ cannot be ignored.
Although sensitivity analysis provides us with a quantitative measure for the degree
of impact of parameter risk on pricing, it does not summarize the effect of these
mis-specifications on the P&L distribution, which is discussed in the next section.
6 Profit and Loss Analysis
To better quantify the underlying risks involved in the guarantee, we simulate profit
and loss (P&L) distributions for different situations where no hedging is performed
and the liabilities are funded solely by the guarantee fee charged by the insurer.
We assume that a VA portfolio consists of 1000 policyholders all aged 65 who have
elected GLWB as the only guarantee to protect their investment. Each individual
invests $100 and chooses the same equity exposure π for their retirement savings
investment. A fair guarantee fee is charged according to the valuation result in Section
4. We compute 1000 independent death times by simulating the mortality intensity
process µ65+t.
13 The P&L for each individual is obtained by simulating the account
process A(·). If a policyholder dies before the account is depleted, the profit for the
insurer is determined by the received fee, which grows with an interest rate r. On
the other hand, if a policyholder dies after the account value drops to zero, the fee
charged by the insurer will be used to fund the liability incurred. The surplus/shortfall
is aggregated across all individuals, and discounted to obtain the discounted P&L of
the portfolio. 14 The described procedure constitutes one sample. To obtain summary
statistics for the discounted P&L distribution, 100,000 simulations are performed.
The results reported in Table 4 include the fair guarantee fee rate α
∗
g
; the mean P&L
for the insurer; its standard deviations (Std.dev.); the coefficient of variation (C.V.)
defined as the mean P&L per unit of standard deviation; the Value-at-Risk (VaR)
defined as the q%-quantile of the P&L distribution; and the Expected Shortfall (ES)
determined as the expected loss of portfolio value given that a loss is occurring at
or below the q%-quantile. The confidence level (1 − q)% for the VaR and the ES
corresponds to 99.5%. Parameter values used in the simulations are as specified in
Table 3 except for the guaranteed withdrawal rate g which is set equal to 6%. 15
12 This corresponds approximately to the duration of a VA portfolio with GLWB, assuming
retirees are aged 65 years old when the contract starts.
13 Note that the mortality intensity process is simulated only once. The intensity provides
us with a probability distribution, which can be use to draw 1000 independent death times
from it.
14 We find it convenient to use the discounted P&L rather than P&L, since time of death of
a policyholder is random and there is no fixed maturity for the contract. Therefore, using
discounted P&L allows for more convenient comparison and interpretation of the results at
time t = 0.
15 The reason for increasing g from 5% to 6% for the purpose of P&L simulations is as
follows. When equity exposure π = 0, the guarantee is too generous for the insurer. This
leads to VaR and ES being positive even for a relatively high confidence level 99.5%. For
the purpose of convenience of interpretation of the results, we set g = 6%, which leads to
21
6.1 P&L with or without systematic mortality risk
We first consider interaction between systematic mortality risk and equity exposure
π, and its effect on the P&L. Table 4 reports summary statistics for the discounted
P&L distributions with systematic mortality risk (with s.m.r) or without systematic
mortality risk (no s.m.r.). We first consider the situation when π = 0, that is, the
retirement savings is entirely invested in the money market account with deterministic
growth and since the portfolio is large enough, the unsystematic mortality risk is
diversified away. In the case when π = 0 and no s.m.r., the fee charged is able to almost
exactly (on average) offset the liability, since the fair fee is obtained by the principle of
equivalence under P. Once systematic mortality risk is introduced, the average return,
as well as the risk (determined by the Std.dev.) of selling the guarantee, increases,
which is consistent with the standard risk-return tradeoff argument. Since systematic
mortality risk coefficient λ = 0.4, there is a positive risk premium associated with
the systematic mortality risk, see Fig. 4. C.V. takes its lowest (highest) value of 0.504
(1.375) in a presence of (without) systematic mortality risk and no equity exposure.
Generally, distributions with C.V. < 1 (C.V. > 1) are considered to be low- (high-)
variance. For the case of no systematic mortality risk we observe that C.V. decreases
with increasing equity exposure. This indicates that for the high values of π the mean
return increases faster than the Std.dev., compared to the situation when π is low.
Clearly, VaR and ES increase (in absolute terms) when we move from no s.m.r. to
s.m.r., and when equity exposure level π increases. In addition, one observes that the
effect of systematic mortality risk becomes less pronounced when π increases. This
result suggests that if policyholders choose low exposure to equity risk, the guarantee
provider should be more careful about systematic morality risk, as it becomes a larger
contributor to the overall risk underlying the guarantee.
Table 4
The effect of the presence of systematic mortality risk with respect to different levels of
equity exposure π. Summary statistics are computed using discounted P&L distribution
per dollar received.
Case α
∗
g Mean Std.dev. C.V. VaR0.995 ES0.995
π = 0
no s.m.r. 0.09% 0.0011 0.0008 1.375 -0.0010 -0.0013
with s.m.r. 0.23% 0.0062 0.0123 0.504 -0.0470 -0.0556
π = 0.3
no s.m.r. 0.32% 0.0267 0.0243 1.099 -0.0807 -0.0995
with s.m.r. 0.51% 0.0427 0.0363 1.176 -0.1147 -0.1444
π = 0.5
no s.m.r. 0.62% 0.0590 0.0624 0.946 -0.1595 -0.1863
with s.m.r. 0.85% 0.0807 0.0838 0.963 -0.1988 -0.2369
π = 0.7
no s.m.r. 0.97% 0.1049 0.1318 0.796 -0.2333 -0.2619
with s.m.r. 1.25% 0.1362 0.1717 0.793 -0.2718 -0.3148
π = 1
no s.m.r. 1.60% 0.2136 0.3579 0.597 -0.3236 -0.3532
with s.m.r. 1.88% 0.2520 0.4599 0.548 -0.3628 -0.4047
negative VaR and ES across all equity exposures.
22
6.2 Parameter Risk
Parameter risk constitutes a significant component for the guarantee provider given
that the guarantee is generally of a very long term nature. As specified in Section
5.3, parameter risk refers to the situation when parameter(s) from the model are not
specified/estimated correctly by the guarantee provider. For example, if volatility of
systematic mortality risk σµ is set to be 0.021 at the inception of the contract and
it turns out to be larger in the future, the resulting mis-specification leads to an
inadequate amount of guarantee fee being charged. This is an unfavorable situation
for the guarantee provider, even if some hedging program has been implemented.
Table 5 shows distributional statistics for the discounted P&L when different parameters are assumed to be misspecified. These include financial risk parameters (interest
rate r and fund volatility σ) as well as demographic risk parameters (volatility of
mortality σµ and systematic mortality risk coefficient λ). The first column of Table 5 reports parameters r, σ, σµ and λ (mis-)specified by the guarantee provider at
the initiation of the contract, whereas the ”true” parameters correspond to r = 4%,
σ = 25%, σµ = 0.021 and λ = 0.4, and are indicated in bold letters. The second
column represents the fair guarantee fee rate calculated using the misspecified parameters, with other parameters set to be ”true”. For instance, if σ is estimated to
be 20%, the fair guarantee fee rate is underestimated by 1.25% − 0.97% = 0.28%.
As one would expect, the mean P&L depends on the guarantee fee rate. Overcharging
or undercharging the guarantee fee leads to a substantial increase or decrease in the
mean P&L, respectively. In contrast to the mean P&L, risk measures such as VaR and
ES are relatively insensitive to the fair guarantee fee rate; and the standard deviation
becomes larger when guarantee fee rate increases. This is due to the fact that the P&L
distribution is affected by two factors: the probability of the occurrence of different
scenarios and the cash flow involved in each scenario. A miscalculation of guarantee
fee rate has no impact on the probability of occurrence of different scenarios, but
merely affects the cash flow. As tail risk measures, VaR and ES mostly concern with
scenarios represented in Fig. 1. Due to the fact that the guarantee fee rate has larger
impact on premiums than on liabilities 16 , and for the worst 0.05% scenarios liabilities
are much larger than premiums, overcharging or undercharging the guarantee fee has
only small impact on the left tail of the P&L distribution. As a result, VaR and ES
are relatively robust to misspecification of guarantee fee rate as they represent the
left tail of the P&L distribution.
Contrary to the VaR and the ES, the standard deviation is a measure of dispersion of
the data around its mean. Scenarios represented in Fig. 2 are typical when considering
standard derivation of the P&L distribution, since most samples around the mean
have larger premiums than liabilities. In order to explain why standard deviation
is larger when guarantee fee rate increases, we consider two scenarios assuming no
16 Premiums and liabilities are from an insurer’s prospective. Clearly, premiums (or guarantee fees) depend on the guarantee fee rate directly while liabilities implicitly depend on
the fee rate as the investment account will decrease (increase) slightly faster when the fee
rate is higher (lower).
23
liabilities. The difference of profits of these two scenarios is calculated as
αg
∫ τ
0
(A1(t) − A2(t)) dt. (6.1)
Note that samples in the P&L distribution come from a portfolio with 1000 policyholders and hence, the death time τ in Eq.(6.1) is representative only. Note also that
the difference in profits indicates how ”apart” these two samples are when guarantee
fee rate is αg. Now suppose that the guarantee fee rate is ˆαg instead of αg. For the
same two scenarios the difference of profits become ˆαg
∫ τ
0
(Aˆ
1(t) − Aˆ2(t)) dt. Since the
integrand is the difference of two account values and the value of guarantee fee rate
has only a small effect on the dynamics of A(t), it is reasonable to expect that
∫ τ
0
(A1(t) − A2(t)) dt ≈
∫ τ
0
(Aˆ
1(t) − Aˆ2(t)) dt. (6.2)
As a result, the samples are more “apart” when ˆαg > αg.
Table 5
Parameter risk: distributional statistics for the discounted P&L per dollar received. The
”true” parameters corresponding to r = 4%, σ = 25%, σµ = 0.021 and λ = 0.4, and are
indicated in bold letters.
Case α
∗
g Mean Std.dev. VaR0.995 ES0.995
r
2% 5.70% 0.3619 0.3461 -0.2210 -0.2636
3% 2.40% 0.2344 0.2511 -0.2578 -0.3012
4% 1.25% 0.1362 0.1717 -0.2718 -0.3148
5% 0.70% 0.0731 0.1214 -0.2855 -0.3264
6% 0.39% 0.0326 0.0901 -0.2872 -0.3280
7% 0.20% 0.0055 0.0718 -0.2882 -0.3299
σ
10% 0.48% 0.0446 0.0995 -0.2882 -0.3292
15% 0.70% 0.0731 0.1214 -0.2855 -0.3264
20% 0.97% 0.1058 0.1475 -0.2764 -0.3175
25% 1.25% 0.1362 0.1717 -0.2718 -0.3148
30% 1.50% 0.1607 0.1905 -0.2718 -0.3160
35% 1.90% 0.1962 0.2198 -0.2633 -0.3100
σµ
0.005 1.00% 0.1079 0.1487 -0.2816 -0.3231
0.010 1.08% 0.1175 0.1564 -0.2733 -0.3152
0.015 1.15% 0.1250 0.1633 -0.2751 -0.3212
0.021 1.25% 0.1362 0.1717 -0.2718 -0.3148
0.025 1.36% 0.1472 0.1790 -0.2731 -0.3153
0.030 1.54% 0.1645 0.1939 -0.2699 -0.3131
λ
0.1 1.14% 0.1244 0.1619 -0.2743 -0.3186
0.2 1.16% 0.1263 0.1637 -0.2772 -0.3162
0.3 1.22% 0.1321 0.1684 -0.2759 -0.3188
0.4 1.25% 0.1362 0.1717 -0.2718 -0.3148
0.5 1.30% 0.1412 0.1765 -0.2744 -0.3155
0.6 1.35% 0.1458 0.1785 -0.2686 -0.3129
24
6.3 Model Risk
Model risk relates to the situation when the guarantee provider assumes deterministic
mortality model, that is, ignoring systematic mortality risk. For the implementation
of the deterministic mortality model we impose the conditions a = 0 and σµ = 0 in
Eq.(3.4) while parameter b is estimated as discussed in Section 3.2, where we have
b = 0.106. Table 6 reports the results for the P&L statistics in presence of model risk,
comparing stochastic and deterministic mortality models. One observes that when
equity exposure is small (π ≤ 0.5), the assumption regarding deterministic mortality
leads to an underestimation of the fair guarantee fee rate. As a result, the average
return drops while the VaR and the ES worsen. However, for large equity exposures
(π > 0.5) one observes essentially no difference between deterministic or stochastic
mortality model specification. This can be explained by the fact that for large π,
equity risk dominates systematic mortality risk, which is reflected in the Std.dev.,
VaR and ES in Table 6.
Table 6
Model risk assuming stochastic vs. deterministic mortality model: distributional statistics
for the discounted P&L per dollar received.
Model α
∗
g Mean Std.dev. VaR0.995 ES0.995
π = 0
stochastic 0.23% 0.0062 0.0123 -0.0470 -0.0556
deterministic 0.14% 0.0001 0.0114 -0.0501 -0.0581
π = 0.3
stochastic 0.51% 0.0427 0.0363 -0.1147 -0.1444
deterministic 0.45% 0.0371 0.0345 -0.1166 -0.1507
π = 0.5
stochastic 0.85% 0.0807 0.0838 -0.1988 -0.2369
deterministic 0.82% 0.0786 0.0822 -0.2001 -0.2383
π = 0.7
stochastic 1.25% 0.1362 0.1717 -0.2718 -0.3148
deterministic 1.25% 0.1362 0.1717 -0.2718 -0.3148
π = 1
stochastic 1.88% 0.2520 0.4599 -0.3628 -0.4047
deterministic 1.90% 0.2534 0.4478 -0.3684 -0.4117
7 Static Hedging of Systematic Mortality Risk: A Numerical Example
Several longevity-linked securities proposed in the literature can be applied as hedging instruments for the longevity risk. Here, we consider the so-called S-forward, or
‘survivor’ forward, which has been developed by LLMA (2010). It is a cash settled
contract linked to survival rates of a given population cohort which are ultimately derived from mortality rates. The S-forward is the basic building-block for the longevity
(survivor) swaps, see Dowd (2003), that have already been used extensively by pension
funds and insurance companies to hedge the longevity risk. These longevity swaps can
be regarded as a stream of S-forwards with different maturity dates. The advantage
of using S-forward as our choice of hedging strategy is that there is no initial capital
requirement at the inception of the contract and cash flows only occur at maturity.
Moreover, since the underlying of S-forward is the survival probability of a chosen
population, it is convenient for the problem at hand given that we have an analytical
25
expression for survival probability. Finally, the lack of a matured longevity market
also makes static hedging more realistic compared to the dynamics hedging which
requires liquid longevity-linked instruments. S-forward is an agreement between two
counterparties to exchange at maturity an amount equal to the realized survival rate
of a given population cohort, in return for a fixed survival rate agreed at the inception of the contract, whereas survival rate is calculated from mortality rates. Thus,
S-forward is in fact a swap with only one payment at maturity T where the fixed leg
pays:
N · E
Q
0
(
e
−
∫ T
0
µx+s(s)ds)
(7.1)
while the floating leg pays:
N · e
−
∫ T
0
µx+s(s)ds
, (7.2)
with N denoting the notional amount of the contract. The fixed leg is determined
under the risk-adjusted measure Q and as discussed in Section 3.3. Since there is
a positive risk premium for systematic mortality risk, the systematic mortality risk
hedger who pays fixed leg and receives floating leg, bears implicit cost for entering an
S-forward.
Since the maturity of GLWB is not fixed, we assume in our numerical example that
T = 20, which approximately corresponds to the expected remaining lifetime of a 65-
years old (Fig. 5). To determine an appropriate notional amount N for the contract,
we notice that N should depend on the total investment I (which corresponds to
$100 investment for each of 1000 policyholders: I = 1000 × 100 = 100, 000) of a VA
portfolio. Assuming N to be a linear function of I (N = θ · I), we found that θ ≈ 0.35
provides the most effective hedge in a sense of VaR and ES reduction (in absolute
terms) through our numerical experiment.
Table 7
Static hedging of systematic mortality risk via S-forward. Distributions of discounted P&L
per dollar received.
Case Mean Std.dev. VaR0.995 ES0.995
π = 0
No hedge 0.0062 0.0123 -0.0470 -0.0556
Static hedge 0.0016 0.0111 -0.0283 -0.0313
π = 0.3
No hedge 0.0427 0.0363 -0.1147 -0.1444
Static hedge 0.0382 0.0396 -0.0995 -0.1251
π = 0.5
No hedge 0.0807 0.0838 -0.1988 -0.2369
Static hedge 0.0761 0.0861 -0.1870 -0.2198
π = 0.7
No hedge 0.1362 0.1717 -0.2718 -0.3148
Static hedge 0.1316 0.1737 -0.2591 -0.2968
π = 1
No hedge 0.2520 0.4599 -0.3628 -0.4047
Static hedge 0.2476 0.4615 -0.3491 -0.3866
Table 7 reports the results for the discounted P&L statistics in presence of static hedge
and different levels of equity exposure. We observe that using the simplest form of
static hedge be means of S-forward allows us to reduce VaR and ES (in absolute
terms) considerably. In particular, the improvement (in percentage terms) of the VaR
and the ES is larger when equity exposure is small. Although the average return
becomes lower when the hedging strategy is in place, the risk (determined by the
26
standard deviation) remains nearly unchanged, which suggests that the volatility of
the fund investment has a significant impact on the outcome of the P&L distribution.
Therefore, a guarantee provider should address equity risk carefully in a first place,
prior to considering systematic mortality risk, especially when the equity exposure of
the VA portfolio is large.
8 Conclusion
This paper presents comprehensive analysis for the guaranteed lifetime withdrawal
benefits (GLWB) embedded in variable annuities, which is the most elected guarantee
in the U.S. in 2011. GLWB provides a type of life annuity which addresses systematic mortality risk while protecting the policyholders from the downside risk of fund
investment. It allows a policyholder to decide how much to withdraw every year for
the lifetime, regardless of the performance of the investment. The GLWB guarantee
promises to the insured a stream of income for life, even if the investment account is
depleted. After the death of the insured, any savings remaining in the account will
be returned to the insured’s beneficiary. The paper provides a detailed description of
GLWB, including product features and identification of risks.
The paper considers pricing of the GLWB using two equivalent approaches, assuming
tractable equity and stochastic mortality models. We demonstrate the equivalence of
the two approaches using a numerical example. We further study the effect of various
financial and demographic variables (such as the interest rate r, volatility of a fund
investment σ, volatility of mortality σµ and the market price of systematic mortality
coefficient λ) on the fair guarantee fee rate α
∗
g
charged by the insurer, as well as on
the profit and loss characteristics from the point of view of insurance provider.
The results indicate that the fair guarantee fee increases exponentially with increasing volatility of mortality σµ, or the market price of systematic mortality coefficient
λ, which is due to the fact that the expected remaining lifetime increases with increasing σµ. Furthermore, the fair guarantee fee appears to be positively related, and
highly sensitive to the volatility of the investment account, which is consistent with a
financial theory suggesting that, generally, options are more expensive when volatility
is high. The relationship between α
∗
g
and r is negative and α
∗
g
appears to be highly
sensitive to low interest rates.
The results from studying the P&L distribution from the guarantee provider’s point
of view (and assuming no hedge in place) show that the risk determined via Valueat-Risk (VaR) and expected shortfall (ES) increases with increasing equity exposure.
The VaR and the ES are higher (in absolute terms) when systematic mortality risk
is present in the model, compared to the situation with no systematic mortality
risk. We further show that parameter risk and model risk might result in significant
under- or overestimation of the fair guarantee fee rate α
∗
g
. Finally, a static hedge
procedure implemented using S-forward, allows to reduce VaR and ES, but leads to
a decrease in the average return for the insurer (especially when the equity exposure
is high), suggesting that the equity risk has to be taken care of along with a careful
consideration of a systematic mortality risk.
27
References
Aase, K. K., Perrson, S. A., 1994. Pricing of unit-linked life insurance policies. Scandinavian Actuarial Journal 1, 26–52.
Bacinello, A. R., Millossovich, P., Olivieri, A., Pitacco, E., 2011. Variable annuities: A
unifying valuation approach. Insurance: Mathematics and Economics 49, 285–297.
Ballotta, L., Haberman, S., 2006. The fair valuation problem of guaranteed annuity
options: the stochastic mortality environment case. Insurance: Mathematics and
Economics 38, 195–214.
Biffis, E., 2005. Affine processes for dynamics mortality and actuarial valuations.
Insurance: Mathematics and Economics 37(3), 443–468.
Bjork, T., 2009. Arbitrage Theory in Continuous Time. Oxford University Press.
Cairns, A., Blake, D., Dowd, K., 2006. Pricing death: Framework for the valuation
and securitization of mortality risk. ASTIN Bulletin 36(1), 79–120.
Cairns, A., Blake, D., Dowd, K., 2008. Modellin and management of mortality risk:
a review. Scandinavian Actuarial Journal 2(3), 79–113.
Dahl, M., Moller, T., 2006. Valuation and hedging of life insurance liabilities with
systematic mortality risk. Insurance: Mathematics and Economics 39, 193–217.
Dowd, K., 2003. Survivor bonds: A comment on blake and burrows. Journal of Risk
and Insurance 70(2), 339–348.
Filipovic, D., 2009. Term Structure Models: A Graduate Course. Springer.
Hardy, M., 2003. Investment guarantees: The new science of modelling and risk management for equity-linked life insurance. John Wiley & Sons, Inc., Hoboken, New
Jersey, 2003.
Holz, D., Kling, A., Rub, J., 2007. An analysis of lifelong withdrawal guarantees.
Working paper, ULM University.
Kling, A., Ruez, F., Russ, J., 2011. The impact of stochastic volatility on pricing,
hedging and hedge effectiveness of withdrawal benefit guarantees in variable annuities. ASTIN Bulletin 41 (2), 511–545.
Kling, A., Russ, J., Schilling, K., 2012. Risk analysis of annuity conversion options in
a stochastic mortality environment. Tech. rep., working paper.
Kolkiewicz, A., Liu, Y., 2012. Semi-static hedging for gmwb in variable annuities.
North American Actuarial Journal 16 (1), 112–140.
Ledlie, M., Corry, D., Finkelstein, G., Ritchie, A., Su, K., Wilson, D., 2008. Variable
annuities. British Actuarial Journal 14, 327–389.
LLMA, 2010. Technical note: The S-forward.
Luciano, E., Vigna, E., 2008. Mortality risk via affine stochastic intensities: calibration
and empirical relevance. Belgian Actuarial Bulletin 8(1), 5–16.
Milevsky, M., Salisbury, T., 2006. Financial valuation of guaranteed minimum withdrawal benefits. Insurance: Mathematics and Economics 38, 21–38.
Ngai, A., Sherris, M., 2011. Longevity risk management for life and variable annuities:
the effectiveness of static hedging using longevity bonds and derivatives. Insurance:
Mathematics and Economics 49, 100–114.
Persson, S. A., 1994. Stochastic interest rate in life insurance: The principle of equivalence revisited. Scandinavian Actuarial Journal 2, 97–112.
Piscopo, G., Haberman, S., 2011. The valuation of guaranteed lifelong withdrawal
benefit options in variable annuity contracts and the impact of mortality risk.
North American Actuarial Journal 15 (1), 59–76.
Russo, V., Giacometti, R., Ortobelli, S., Rachev, S., Fabozzi, F., 2011. Calibrat28
ing affine stochastic mortality models using term assurance premiums. Insurance:
mathematics and economics 49, 53–60.
Schrager, D., 2006. Affine stochastic mortality. Insurance: Mathematics and Economics 38, 81–97.
Ziveyi, J., Blackburn, C., Sherris, M., 2012. Pricing european options on deferred
insurance contracts. Tech. rep., submitted, University of New South Wales.
29