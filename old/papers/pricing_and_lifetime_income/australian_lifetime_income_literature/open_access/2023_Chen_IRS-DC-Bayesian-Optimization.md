https://arxiv.org/pdf/2106.13644
→ https://arxiv.org/pdf/2106.13644
Content-Type: application/pdf

.
1
Intergenerational Risk Sharing in a Defined
Contribution Pension System: Analysis with
Bayesian Optimization
An Chen1†, Motonobu Kanagawa2‡ and Fangyuan Zhang2¶
1
Institute of Insurance Science, University of Ulm, Germany
2Data Science Department, Eurecom, France
Abstract
We study a fully funded, collective defined-contribution (DC) pension system with
multiple overlapping generations. We investigate whether the welfare of participants
can be improved by intergenerational risk sharing (IRS) implemented with a realistic
investment strategy (e.g., no borrowing) and without an outside entity (e.g., share
holders) that helps finance the pension fund. To implement IRS, the pension system uses
an automatic adjustment rule for the indexation of individual accounts, which adapts to
the notional funding ratio of the pension system. The pension system has two parameters
that determine the investment strategy and the strength of the adjustment rule, which are
optimized by expected utility maximization using Bayesian optimization. The volatility
of the retirement benefits and that of the funding ratio are analyzed, and it is shown
that the trade-off between them can be controlled by the optimal adjustment parameter
to attain IRS. Compared with the optimal individual DC benchmark using the life-cycle
strategy, the studied pension system with IRS is shown to improve the welfare of riskaverse participants, when the financial market is volatile.
Key words: Intergenerational Risk Sharing, Defined Contribution, Automatic Adjustment Rule, Bayesian Optimization
1. Introduction
Defined Contribution (DC) pension plans constitute key part of pension systems in
many countries, such as the “401k plan” in the United States and the “personal pensions”
in the United Kingdom. In a DC plan, each participant owns her account, pays fixed
contributions to the account regularly, and the accumulated contributions are invested in
a financial market. The amount of retirement benefits is determined by the market value
of the individual account at the retirement date. By design, DC plans have advantages
over traditional pension schemes such as Pay-As-You-Go (PAYG) and Defined Benefit
(DB) pension plans in terms of the transparency, fairness, portability and sustainability,
which encourage the prevalence of DC plans.
However, DC plans have major issues arising from that each participant bears the
investment risk by herself. One issue is that the participant may not choose a good
investment strategy due to the lack of financial expertise. Indeed, a typical DC plan
participant in reality tends to perform the naive “1/n diversification,” equally dividing
her contributions into the default options provided by the plan (Benartzi and Thaler
† an.chen@uni-ulm.de
‡ motonobu.kanagawa@eurecom.fr
¶ fangyuan.zhang@eurecom.fr (Corresponding)
arXiv:2106.13644v3 [econ.GN] 23 Mar 2023
2 A. Chen, M. Kanagawa and F. Zhang
2001). Optimal investment strategies studied in the literature (e.g., Merton 1971; Cairns
1996; Cairns et al. 2006; Boulier et al. 2001; Vigna and Haberman 2001; Chen and Delong
2015; Menoncin and Vigna 2017) can thus not be easily employed by such participants.
Another major issue of DC plans is the incapability of intergenerational risk sharing
(IRS), which is to diversify non-diversifiable risks within one generation (e.g., those
caused by economic shocks) across different generations. For example, a DC plan participant whose accumulation period overlaps an economic depression faces a financial
risk that cannot be diversified by herself; even if she can choose an optimal utilitymaximizing investment strategy, she may not accumulate enough wealth for retirement.
IRS enables diversifying such non-diversifiable risks by sharing the risks among different
generations. By definition, however, IRS requires the pension scheme to be collective, and
thus individual DC plans cannot implement IRS.
It is well known that carefully-designed collective schemes can implement IRS to
improve the welfare of participants (e.g., Gordon and Varian 1988; Allen and Gale 1997;
Shiller 1999). Gollier (2008) shows that a collective DC pension plan can improve the
welfare of participants compared with an individual benchmark using the optimal lifecycle investment strategy. Similarly, Cui et al. (2011) study a collective DB-based hybrid
pension scheme where both contributions and pension benefits may be adjusted, and show
that it is welfare-improving compared with an optimal individual benchmark. Chen et al.
(2016) consider a three-pillar pension system in which the second pillar is a collective
hybrid plan, and show that there is welfare improvement compared with a corresponding
individual DC benchmark. See Barr and Diamond (2008, Chapter 7) and Beetsma and
Romp (2016) for an overview of IRS and further references.
While the seminal work of Gollier (2008) shows that IRS in a collective DC pension
system is welfare-improving, both his first-best and second-best strategies depend on
rather strong assumptions. The first-best strategy attains IRS by enhancing the risktaking ability of the pension fund, by treating the net present value of the contributions
from all the future generations as part of the fund’s total wealth. Consequently, the
fund can invest more than the fund’s actual wealth, i.e., the fund can perform borrowing
for investment, similar to the life-cycle investment strategy for an individual investor
(Merton 1971). However, borrowing is not realistic for pension funds in reality. On the
other hand, his second-best strategy does not allow borrowing, but assumes the existence
of an outside entity (shareholders) that helps finance the fund. Therefore, it is not clear
whether the welfare-improvement by the second-best strategy can be attained without
the shareholders.
Given these limitations of Gollier’s analyses, one may ask: Can the welfare-improvement
by IRS be attained by a fully funded, collective DC pension system with a realistic
investment strategy (e.g., no borrowing) and without an outside entity that helps finance
the pension fund? Previous related works do not exactly answer this question, as discussed
later in detail. For example, while Chen et al. (2016) show that their collective scheme
with IRS is welfare-improving compared with the corresponding individual DC scheme,
it is assumed that both the collective and individual schemes use the same investment
strategy; therefore, it is not clear whether their IRS is welfare-improving as compared
with the optimal individual investment strategy.
Our main aim is to investigate the above question. To this end, we consider a stylized
model for a fully funded, collective DC pension fund with multiple overlapping generations, which we call the IRS-DC model. As Gollier (2008), each participant pays a fixed
annual contribution to the pension fund, and the fund makes investment on behalf of the
participants. Different from the first-best strategy of Gollier (2008), however, the fund
is not allowed to perform borrowing. Each participant has her own account in the fund,
Intergenerational Risk Sharing in a Defined Contribution Pension System 3
which accumulates her contributions and is indexed to the fund’s investment performance;
the account value at the retirement date determines her pension benefit. The indexation
rate of individual accounts is automatically adjusted to the (notional) funding ratio of
the pension fund by the adjustment rule of Goecke (2013). This automatic adjustment
rule is the device for implementing IRS in our model. In contrast to the second-best
strategy of Gollier (2008), the fund is fully-funded and does not rely on any external
entity to implement IRS.
We analyze how the automatic adjustment rule stabilizes the funding ratio and the
benefits of participants to attain IRS. Analytic expressions are derived for the funding
ratio and benefits. It is shown that there is a trade-off between the stability of the
funding ratio and that of benefits, and that this trade-off is controlled by the strength of
the automatic adjustment rule. That is, benefits can be made more stable by increasing
the volatility of the funding ratio, and vice versa. IRS can be attained by balancing this
trade-off.
Automatic adjustment rules in pension systems have been not only studied in the
literature (e.g., Cui et al. 2011; Chen et al. 2016; Bams et al. 2016; Donnelly 2017) but
also applied to real pension systems in such countries as Sweden and the Netherlands
(OECD 2021, Chapter 2). They are used for improving the sustainability of a pension
fund and for providing stable benefits to participants (e.g., Settergren 2001; Barr and
Diamond 2011). However, a formal analysis is missing for justifying such use of automatic
adjustment rules in collective pension systems. Our analysis thus provides a first step in
this regard.
The IRS-DC model has two parameters, one for the investment strategy and the
other for the automatic adjustment rule. For optimizing these parameters, we define an
expected utility maximization problem that involves the benefits of all the generations
including those in the future, following Gollier (2008). As this optimization problem
cannot be solved analytically, we solve it numerically using Bayesian optimization, a
machine learning approach to optimizing a black-box function (e.g., Shahriari et al. 2016).
As discussed later, the use of Bayesian optimization is our computational contribution,
in line with the recent deployments of machine learning in the insurance literature (e.g.,
Hainaut 2018; Gabrielli 2020; Wüthrich 2020; Scognamiglio 2022; Schnürch and Korn
2022).
To answer the question above, our main finding is that IRS can improve the welfare of
participants without borrowing and shareholders, if the financial market is volatile and
the participants are risk-averse; IRS may not be welfare-improving if this condition is
not satisfied. We compare the welfare of the IRS-DC plan participants and the welfare
of the corresponding individual DC plan participants, where the latter uses the optimal
life-cycle strategy (Merton 1971). Several different settings of the financial market and
the risk aversion of participants are investigated, and the above finding is obtained.
The paper proceeds as follows. Section 2 introduces the IRS-DC pension model, which
is analyzed in Section 3. Section 4 explains the expected utility maximization problem,
how to solve it with Bayesian optimization, and the setup for simulations. Section 5
presents numerical analyses, including the funding ratio process, the individual benefit
accounts of the IRS-DC fund, and the certainty equivalents of the participants. Section 6
concludes. The appendix contains a short tutorial on Bayesian optimization, the proofs
of analytic results, and additional numerical analyses.
4 A. Chen, M. Kanagawa and F. Zhang
Figure 1: Schematic illustration of the pension model. The horizontal axis indicates time
t, and the vertical axis generation identifiers. For each generation, the black and white
circles indicate the time points when that generation joins and retires from the pension
fund, respectively; the orange line indicates the duration of the participation in the fund.
For example, the generation i joins the fund at time t = i − N and retires at t = i. For
each time point, the blue box indicates the current participants of the pension fund, and
black diamonds indicate those participants (only shown for the generations displayed in
the figure). For example, at time t = i − 1, the generations i, i + 1, . . . , i + N − 1 are
participating in the fund.
2. Pension Model
This section describes the IRS-DC pension model. The pension fund contains multiple
overlapping generations, where there are always incoming and outgoing generations. Each
generation pays fixed contributions annually to the pension fund. Before explaining the
details, we summarize below the key features of the pension fund:
(i) The pension fund collectively invests the contributions from different generalizations (participants) in a financial market.
(ii) Each participant maintains her account in the pension fund that records her
accumulated pension rights.
(iii) The growth rate of individual accounts is automatically adjusted based on the
fund’s investment performance and a notional funding ratio, so that intergenerational
risk sharing is implemented.
Section 2.1 describes the IRS-DC pension model in detail. Section 2.2 compares it with
related pension models in the literature.
2.1. Description of the IRS-DC Pension Model
Figure 1 provides a schematic illustration of our pension model. The pension fund
covers N overlapping working generations in each operating year (e.g., N = 40). The
pension fund is fully-funded. For simplicity, we assume that each generation consists of
one hypothetical participant. Let t > 0 denote the time, with the unit being one year.
We assume that the fund starts at time t = 0 with N initial generations.
2.1.1. Generation Identifier
We use an integer i ∈ N as the identity of the generation who retires at time t = i (see
Figure 1). Namely, the generation i joins the fund at time t = i − N and leaves the fund
at time t = i; thus, this generation is in the fund for N years. Using this notation, we
Intergenerational Risk Sharing in a Defined Contribution Pension System 5
can define the set of all the working generations in the fund at any time point t > 0 as
Iw(t) := {i|i = [t] + 1, [t] + 2, . . . , [t] + N},
where [t] denotes the integer part of t (e.g., if t = 3.4 then [t] = 3; if t = 3 then [t] = 3).
2.1.2. Financial Market and Pension Asset Dynamics
We consider a financial market where there exist two investment opportunities: a risky
asset (e.g., a stock) and a risk-free asset (e.g., a bank account or a bond), denoted by S(t)
and F(t), respectively. Specifically, we consider the Black-Scholes market, where S(t) is
driven by a diffusion process with constant drift µ > 0 and volatility σ > 0, while F(t)
develops at a risk-free rate r > 0 such that µ > r:
dS(t) = µS(t)dt + σS(t)dZ(t), S(0) = 1; (2.1)
dF(t) = rF(t)dt, F(0) = 1, (2.2)
where Z(t) is a standard Brownian motion under the real-world probability measure.
Let A(t) denote the asset of the pension fund at time t, with A(0) > 0 being the initial
asset. For simplicity, we assume that the fund invests a constant fraction π ∈ [0, 1] of the
pension asset A(t) in the stock S(t) and the rest 1 − π in the risk-free asset F(t); thus,
we can write the dynamics of the pension asset as
dA(t) = πA(t)
S(t)
dS(t) + (1 − π)A(t)
F(t)
dF(t), π ∈ [0, 1]. (2.3)
We assume that the fund is prohibited from from borrowing (π > 1) and short selling
(π < 0).
At the beginning of each year t = 0, 1, 2 . . . , each working generation pays a constant
amount of contribution, c > 0, to the pension fund. Since there are N working generations, the fund thus receives a total of N c contributions at the beginning of each year.
At the same time, the fund pays a lump-sum benefit to the generation t, who retires at
time t.
The dynamics of the pension asset can thus be written as
dA(t) = A(t)(π(µ − r) + r) dt + A(t)πσ dZ(t), A(0) = A0, t > 0, (2.4)
A(t)+ = A(t) + N c − Bt(t), t = 0, 1, 2, · · · , (2.5)
where (2.4) is obtained by substituting (2.1) and (2.2) into (2.3), A(t)+ := limε→+0 A(t+
ε) denotes the right continuous limit, and Bt(t) is the benefit paid to the generation t
who has just retired and defined in (2.6) and (2.7) below (the double t notation of Bt(t)
is deliberate and its meaning will be clear shortly).
Therefore, the pension asset develops continuously over time t > 0, while there is a
jump at each integer time t = 0, 1, 2, · · · (i.e., at the beginning of each year) when there
are incoming and outgoing cash flows of N c and Bt(t), respectively.
2.1.3. Individual Accounts and Retirement Benefits
Like pure DC and notional DC plans, each participant (generation) in our IRS-DC
pension fund has her individual account, which keeps track of her pension rights. It
records her annual contributions and grows according to the indexation rate (2.11) defined
below. The terminal value of the account at the time of retirement becomes the lump-sum
retirement benefit.
More formally, let Bi(t) denote the individual account of generation i ∈ N at time
t ∈ [i − N, i], which starts from Bi(i − N) = 0 when this generation enters the fund at
6 A. Chen, M. Kanagawa and F. Zhang
time t = i − N. Then we define its dynamics as
Bi(t)+ = Bi(t) + c, t = i − N, i − N + 1, . . . , i − 1, (2.6)
dBi(t) = Bi(t)g(t)dt, i − N 6 t 6 i. (2.7)
where g(t) is the indexation rate at time t, defined in (2.11) below. Namely, the individual
account Bi(t) grows continuously from the entry time t = i − N until retirement at t = i
according to the indexation rate g(t) as (2.7), while the account accumulates the annual
contribution c at the beginning of every year as (2.6). The account value at the time of
retirement t = i, i.e, Bt(t), is the retirement benefit of the generation i; see (2.5).
2.1.4. Indexation Rate and Notional Liability
We now define the indexation rate g(t) that determines the growth rate of individual
accounts as in (2.7), which in turn affects the pension’s asset dynamics in (2.5). To this
end, following Bams et al. (2016) and Donnelly (2017), we first define a notional liability
of the fund as
L(t) := X
i∈Iw(t)
Bi(t), t > 0. (2.8)
That is, we define the notional liability L(t) of the fund at time t as the sum of individual
accounts Bi(t) for the current working generations i ∈ Iw(t).
If there is no cash flow in (2.5), the solution to the asset process (2.4) is given by
stochastic exponential, which is a classic result in financial mathematics (e.g., Karatzas
and Shreve 1991, Chapter 5), as
A(t) = A(0) exp Z t
0
µ˜ds +
Z t
0
σ˜dZ(s)

, (2.9)
where µ >˜ 0 and σ >˜ 0 are constants defined as
µ˜ := π(µ − r) + r −
1
2
π
2σ2
, σ˜ := πσ. (2.10)
Following Goecke (2013, Eq. (5)),1 we then define the indexation rate g(t) as
g(t) = ˜µ + θ ln 
A(t)
L(t)

, t > 0, (2.11)
where θ > 0 is a constant, µ˜ is from (2.10), A(t) is the pension fund’s asset process (2.4)
(2.5), and L(t) is the notional liability (2.8).
Figure 2 provides a schematic illustration of the cash flows in our pension model for
two time points t = i and t = i + 1. In the following, let us take a closer look at the role
of various important factors.
2.1.5. The Role of the Indexation Rate
While we will present a more formal analysis in Section 3, we provide here an intuitive
discussion of how the indexation rate (2.11) works. As defined in (2.7), the indexation
rate g(t) controls the growth rate of individual accounts Bi(t). The first term µ˜ in (2.11)
is the expected annual log return using the same investment strategy π in the financial
market without participating in the pension fund. In the second term, A(t)/L(t) is the
notional funding ratio that quantifies the balance between the asset A(t) and the notional
liability L(t). The second term adjusts the growth rate of individual accounts Bi(t), and
the parameter θ > 0 specifies the strength of the adjustment.
If θ = 0, then individual accounts grow deterministically at the rate µ˜; therefore in
Intergenerational Risk Sharing in a Defined Contribution Pension System 7
Figure 2: Schematic illustration of the cash flows in our pension model for two time
points t = i and t = i + 1. In the blue dotted box, A(t) denotes the pension fund’s asset,
whose dynamics follow (2.4) and (2.5). In the orange dotted box, Bi(t), Bi+1(t), and
Bi+2(t) denote the individual accounts of generations i, i + 1, and i + 2, respectively,
whose dynamics follow (2.6) and (2.7). At time t = i, there is an incoming cash flow
of N c contributions from the N working generations, and an outgoing cash flow of the
retirement benefit Bi(i) for the generation i, who retires at time t = i; see (2.5). This
retirement benefit is determined by the individual account Bi(t), which accumulates the
annual contribution c at the beginning of each year and develops continuously according
to the indexation rate g(t) = ˜µ + θ ln(A(t)/L(t)); see (2.7). On the other hand, the
asset process A(t) develops continuously according to the investment performance of
the portfolio with the constant-mix strategy π; see (2.4). Each “+c” represents the
accumulation of the annual contribution in the individual account: At time t, the amount
c is added to each of Bi+1(t) and Bi+2(t).
this case, the retirement benefits are ex-ante determined, i.e., the pension plan becomes a
defined-benefit plan, thus removing the investment risk of pension participants. However,
it risks the sustainability of the pension fund, as the fund is of a defined-contribution
type by design, and thus there is no way of adjusting the contributions when the fund is
underfunding.
On the other hand, if one sets a large value of θ > 0, then pension participants
bear more investment risks to improve the sustainability of the pension fund. For
P
example, suppose that the pension asset exceeds the notional liability, i.e., A(t) > L(t) =
i∈Iw(t) Bi(t). One can interpret this situation as that the fund yields a high return
in the investment and thus there is a “surplus.” Then the log notional funding ratio
becomes positive, ln(A(t)/L(t)) > 0, and the indexation rate g(t) shall be larger than
µ˜; therefore individual accounts Bi(t) grow faster, reflecting the high investment return.
On the other hand, if A(t) < L(t) = P
i∈Iw(t) Bi(t), which happens when the fund yields
a low return and thus there is a “deficit.” In this case, we have ln(A(t)/L(t)) < 0 and
thus the indexation rate g(t) shall be smaller than µ˜; therefore individual accounts Bi(t)
grow more slowly, reflecting the low investment return.
This argument implies that the adjustment parameter θ should be neither too small
nor too large. One should choose θ appropriately to achieve a good trade-off between the
risks of individual participants and the pension fund. We present a more formal analysis
in Section 3.
8 A. Chen, M. Kanagawa and F. Zhang
2.2. Comparison with Related Pension Models
We compare the IRS-DC model with related pension models in the literature. Goecke
(2013) studies the indexation rate (2.11) for the return smoothing in a self-financing
pension plan. Goecke (2013)’s model consists only of one generation, and there exists no
cash flow of contributions and payments. The earlier work by Baumann and Müller (2008)
considers the indexation rate (2.11) where the risk-free rate r is used instead of µ˜. Our
model is a continuous-time version of the discrete-time model of Bams et al. (2016), which
itself is an extension of the overlapping generations model of Gollier (2008). Bams et al.
(2016) use the indexation rate in (2.11), but do not analytically study its use. Donnelly
(2017) considers a funded collective DC pension plan. Donnelly (2017)’s model consists
of fixed multiple overlapping generations, and there exists no new incoming generation.
Donnelly (2017) uses an automatic adjustment rule similar to Goecke (2013)’s (and thus
ours) but is different in its concrete form.
Cui et al. (2011) consider a funded DB-based hybrid pension system that can adjust
both benefits and contributions. Their pension model does not have individual accounts.
The present value of base benefits and contributions are made equivalent ex-ante but
there is no direct link between one’s actual benefits and contributions. Their model is DBbased in this sense. They use automatic adjustment rules for contributions and retirement
benefits based on the funding ratio. Chen et al. (2016) consider a hybrid pension plan as
their second-pillar pension system, in which there exist individual accounts. They also use
automatic adjustment rules for contributions and individual accounts’ indexation rates.
While the adjustment rules of Cui et al. (2011) and Chen et al. (2016) are conceptually
similar to ours, they are different in their forms. For example, Chen et al. (2016) use
the “tangent hyperbolic adjustment function,” while our adjustment rule is based on the
log notional funding ratio. Moreover, Cui et al. (2011) and Chen et al. (2016) define
the liabilities in a DB manner, taking into account future retirement benefits, while we
define our notional liability in a DC manner, i.e., as the sum of current individual account
values. Again, our liability is notional since the fund does not provide any promise on
retirement benefits.
Automatic adjustment mechanisms have been implemented in real pension systems;
see OECD (2021, Chapter 2) for an overview. Notably, Sweden’s first-pillar notional DC
pension system uses an automatic adjustment rule for the indexation rate of individual
accounts (Settergren 2001). This adjustment mechanism is based on a notional funding
ratio2 and is conceptually similar to other rules discussed here (See e.g., Hagen 2013,
Eqs. (6.2) and (6.3)). The Swedish first-pillar notional DC pension system defines its
notional liability essentially in the same way as (2.8) (Settergren 2001, Eq. (3)).3
3. Analysis
We present an analysis of the IRS-DC pension model in Section 2, focusing on the
role of the indexation rate (2.11) for achieving IRS. In particular, we study how the
adjustment parameter θ in the indexation rate impacts the funding ratio, which measures
the stability of the pension fund, and the retirement benefits of individual participants.
In Section 3.1, we first study the dynamics of the log funding ratio. Based on this, we
analyze the effects of the adjustment parameter on the dynamics of the funding ratio in
Section 3.2, and on the retirement benefit of an individual participant in Section 3.3. In
the latter, we obtain an analytic expression of the retirement benefit in terms of the log
funding ratio and the adjustment parameter. Based on this expression, we compare the
Intergenerational Risk Sharing in a Defined Contribution Pension System 9
retirement benefits of the IRS-DC plan and the corresponding pure DC plan in Section
3.4. This last analysis provides insights into how IRS works in the IRS-DC plan.
3.1. Dynamics of the Log Funding Ratio
We start by analyzing the dynamics of the log funding ratio defined as
ρ(t) := ln 
A(t)
L(t)

. (3.1)
Goecke (2013, Proposition A.1) shows that ρ(t) is an Ornstein-Uhlenbeck process under
the assumption that there exists no cash flow. Baumann and Müller (2008, Section 3.1)
obtain a similar result, but again assuming no cash flow. Since our model involves explicit
cash flows as in (2.5), these earlier results are not directly applicable. Nevertheless, we
show here that ρ(t) in our model is also an Ornstein-Uhlenbeck process if the time
t is between integer time points. (Recall that cash flows in our model occur only at
integer time points; see (2.5)). This result, and intermediate derivations, are later used
for deriving further results, so we present them here for completeness.
Let t0 ∈ N be an arbitrary integer time point, which corresponds to the beginning of a
year. Then by (2.4), with A(t0)+ being the initial value after the contributions, the asset
process A(t) for t0 < t < t0 + 1 is written as
A(t) = A(t0)+ exp Z t
t0
µ˜ds +
Z t
t0
σ˜dZ(s)

.
Notice the difference from the previous expression (2.9), which starts from t = 0 and
holds only under the assumption that there exists no cash flow. Similarly, by (2.7), (2.8)
and (2.11), the notional liability L(t) is given as
L(t) = L(t0)+ exp Z t
t0
µ˜ds + θ
Z t
t0
ρ(s)ds

. (3.2)
Then for t0 < t < t0 + 1, the log funding ratio ρ(t) can be expanded as
ρ(t) = ln A(t) − lnL(t)
= ln A(t0)+ +
Z t
t0
µ˜ds +
Z t
t0
σ˜dZ(s) − lnL(t0)+ −
Z t
t0
µ˜ds − θ
Z t
t0
ρ(s)ds (3.3)
= ρ(t0)+ − θ
Z t
t0
ρ(s)ds +
Z t
t0
σ˜dZ(s). (3.4)
The last expression is obtained because the two identical terms R t
t0
µ˜ds in (3.3) are
cancelled out. This is the result of the expected log return µ˜ being used in defining the
indexation rate (2.11), which in turn results in (3.2).
Equation (3.4) indicates that the log funding ratio ρ(t) for t0 < t < t0 + 1 is an
Ornstein-Uhlenbeck process with initial value ρ(t0)+ (e.g., Karatzas and Shreve 1998,
p. 358), which can be written as
ρ(t) = e
−θ(t−t0)
ρ(t0)+ + ˜σ
Z t
t0
e
−θ(t−s)dZ(s), t0 ∈ N, t0 < t < t0 + 1. (3.5)
This expression shows that ρ(t) = ln(A(t)/L(t)) is mean-reverting in the sense that,
irrespective of the value of ρ(t0)+, it tends to 0 (in expectation) as t increases. In other
words, the funding ratio A(t)/L(t) tends to 1 as t increases.
10 A. Chen, M. Kanagawa and F. Zhang
3.2. Effects of the Adjustment Parameter on the Funding Ratio
Based on the expression (3.5), we next study how the adjustment parameter θ affects
the dynamics of the log funding ratio ρ(t). We summarize key observations in the following
proposition, the proof of which can be found in Appendix A.1.
Proposition 1. Let ρ(t) = ln(A(t)/L(t)) be the log funding ratio and θ > 0 be the
adjustment parameter of the indexation rate g(t). Let t0 ∈ N ∪ {0} and t0 < t < t0 + 1.
Then we have the following:
(i) The conditional expectation and variance of ρ(t) given ρ(t0)+ are given by
E[ρ(t) | ρ(t0)+] = e
−θ(t−t0)
ρ(t0)+, (3.6)
V[ρ(t) | ρ(t0)+] = ˜σ
2
Z t
t0
e
−2θ(t−s)
ds, (3.7)
where σ >˜ 0 is the standard deviation of the annual log return in (2.10).
(ii) As θ tends to zero, the conditional expectation of ρ(t) given ρ(t0)+ tends to ρ(t0)+:
lim
θ→+0
E[ρ(t) | ρ(t0)+] = ρ(t0)+, (3.8)
and the conditional variance of ρ(t) given ρ(t0)+ tends to σ˜
2
times t − t0:
lim
θ→+0
V[ρ(t) | ρ(t0)+] = ˜σ
2
(t − t0). (3.9)
(iii) As θ tends to infinity, the conditional expectation and variance of ρ(t) given ρ(t0)+
tend to zero:
lim
θ→∞
E[ρ(t) | ρ(t0)+] = 0, lim
θ→∞
V[ρ(t) | ρ(t0)+] = 0. (3.10)
Proposition 1 shows how the adjustment parameter θ affects the notional funding ratio
A(t)/L(t) and thus the stability of the pension fund. Point (iii) shows that a larger θ lets
A(t)/L(t) approach 1 more quickly and thus makes the fund more stable, while point
(ii) indicates that a smaller θ makes the fund more volatile. Recall that the value of θ
determines how strong the adjustment in the indexation rate g(t) works for the individual
accounts Bi(t); see (2.11). Therefore, a larger θ results in a stronger adjustment of the
individual accounts Bi(t), so that the notional liability L(t) = P
i∈Iw(t) Bi(t) is adjusted
more quickly to match the fund’s asset A(t); this is an intuitive explanation of how a
large θ improves the stability of the pension fund.
While a larger θ may be beneficial for the fund’s stability, it results in a stronger
adjustment of the individual accounts Bi(t), which may make the retirement benefits
volatile. Therefore it is important to understand the effects of θ on the retirement benefits;
we analyze this next.
3.3. Effects of the Adjustment Parameter on the Pension Benefits
We next study how the adjustment parameter θ affects the retirement benefit of each
generation. To this end, we obtain an analytic expression of the retirement benefit in
terms of the log funding ratio, as summarized in the following proposition. The proof can
be found in Appendix A.2.
Proposition 2. Let c > 0 be the annual contribution, µ >˜ 0 and σ >˜ 0 be the mean
and the standard deviation of the annual log return in (2.10), ρ(t) = ln(A(t)/L(t)) be the
log funding ratio, and θ > 0 be the adjustment parameter of the indexation rate g(t) in
Intergenerational Risk Sharing in a Defined Contribution Pension System 11
(2.11). Then for generation i ∈ N, the retirement benefit Bi(i) is given by
Bi(i) =
c
X
N
n=1
exp nµ˜
|{z}
(I)
+ (1 − e
−θ
)
Xn
`=1
ρ(i − `)+
| {z }
(II)
+ ˜σ
Xn
`=1
Z i−`+1
i−`

1 − e
−θ(i−`+1−s)

dZ(s)
| {z }
(III)

.
(3.11)
Proposition 2 enables studying the effects of the adjustment parameter θ on the
retirement benefit Bi(i) of the i-th generation, who retires at time t = i. The expression
(3.11) consists of N terms, in which each term is indexed by n = 1, . . . , N. (Recall that N
is the total number of years each generation contributes to the fund). One can understand
the n-th term in (3.11) as corresponding to the contribution c made at time t = i − n,
i.e., n years before the retirement at time t = i.
We can make the following observations for the exponent of the n-th term in (3.11):
• The term (I) corresponds to the deterministic growth term µ˜ in the indexation rate
g(t); see (2.11).
• The term (II) represents the effects of the fund’s “surplus” or “deficit” in the
last n years before the retirement. One can understand that there is a “surplus”
if Pn
`=1 ρ(i − `)+ > 0; in this case the retirement benefit increases accordingly, as a
redistribution of the surplus. On the other hand, there is a “deficit” if Pn
`=1 ρ(i−`)+ < 0,
and the retirement benefit decreases accordingly; one can understand this as risk sharing
to make the fund sustainable. The adjustment parameter θ determines the strength of
the effects of this term, as we have limθ→+0(1 − e
−θ
) = 0 and limθ→∞(1 − e
−θ
) = 1.
• The term (III) shows the effects of the volatility of the fund’s investment in the last
n years before the retirement; recall the definition of σ˜ = πσ in (2.10). The adjustment
parameter θ controls the influence of this volatility, as we have limθ→+0 (III) = 0 and
limθ→∞ (III) = ˜σ
R i
i−n
dZ(s).
From these observations, one can understand that the adjustment parameter θ determines how strongly the retirement benefit is linked to the fund’s actual investment
performance. For a larger θ, the terms (II) and (III) become more significant, and the
retirement benefit is more directly influenced by the fund’s investment performance. For
a smaller θ, the terms (II) and (III) become less significant, and the retirement benefit
is determined mainly by the deterministic growth term (I). This asymptotic analysis
supports the informal discussion in Section 2.1.5 on the mechanism of the indexation
rate.
One may conclude that a smaller θ may be more beneficial for individual participants,
because it makes the retirement benefits less volatile. However, as discussed in Section
3.2, a smaller θ makes the fund’s operation more volatile, and thus a larger θ is more
desirable for the fund’s sustainability. Therefore, θ should be neither too small nor too
large. We will discuss how to select the adjustment parameter θ (and the investment
strategy π) in Section 4.
12 A. Chen, M. Kanagawa and F. Zhang
3.4. Effects of Intergenerational Risk Sharing
Lastly, we discuss the effects of IRS, by comparing the pension benefits of the IRS-DC
plan and the corresponding pure DC plan. Because our focus is to understand how IRS
works, we assume here that the pure DC plan uses the same investment strategy π as the
IRS-DC plan. (Note that, in our numerical analysis in Section 5, we consider this setting
as well as the setting where the pure DC plan uses the optimal investment strategy.)
Consider two hypothetical individuals from generation i ∈ N, who retire in the year
i. One individual participates in the IRS-DC plan, and receives the retirement benefit
(3.11). The other participates in the pure DC plan using the investment strategy π, and
receives the retirement benefit denoted by Ai(i). It is easy to see that Ai(i) is given by
Ai(i) = c
X
N
n=1
exp nµ˜
|{z}
(I0)
+ ˜σ
Z i
i−n
dZ(s)
| {z }
(II0)

. (3.12)
By comparing (3.11) and (3.12), we can make the following observations:
• The term (I) in (3.11) and the term (I’) in (3.12) are the same.
• The term (II) in (3.11), which represents the effects of the fund’s surplus or deficit,
does not exist in (3.12). This is reasonable, because there is no IRS in the pure DC plan.
• The term (III) in (3.11), which shows the influence of the volatility of the investment,
corresponds to the term (II’) in (3.12). Indeed, the term (III) converges to the term (II’)
as θ → ∞. However, one can see that the term (III) is smaller than the term (II’) for
any fixed value of θ. The smaller volatility in (3.11) is the result of IRS, and is controlled
by the adjustment parameter θ.
This comparison describes how IRS works in the IRS-DC plan: IRS reduces the volatility
of investment returns (term (III) in (3.11)), by letting the individuals share the fund’s
surplus or deficit (term (II) in (3.11)). This effect of IRS is particularly important for
protecting individual participants when the market is turbulent. Our numerical analysis
in Section 5 shows that IRS is beneficial in this way.
4. Optimizing the Investment Strategy and Adjustment Parameter
We describe how to optimize the parameters of the IRS-DC pension model, namely the
investment strategy π and the adjustment parameter θ, so as to maximize the welfare of
pension participants. In Section 4.1, we first introduce an expected utility maximization
problem that involves the welfare of all the generations including those from the future.
Since there is no analytical solution for this maximization problem, we next explain how
to solve it numerically using Bayesian optimization in Section 4.2. We then describe the
setting of simulations in Section 4.3, which will be used later in our numerical analysis.
4.1. Expected Utility Maximization Problem
We consider a hypothetical social planner (fund manager) who decides the investment
strategy π and the adjustment parameter θ for the welfare of all the generations. To
define the utility of this social planner, let Uγ : (0, ∞) → (−∞, ∞) be the constant
Intergenerational Risk Sharing in a Defined Contribution Pension System 13
relative risk aversion (CRRA) utility function:
Uγ(x) := x
1−γ
1 − γ
, γ > 0, (γ 6= 1), (4.1)
where γ > 0 is the level of relative risk aversion. We then define the utility of the social
planner as the sum of discounted utilities of the retirement benefits for all the generations:
X∞
i=1
β
iUγ(Bi(i)), (4.2)
where β > 0 is a discounting factor and Bi(i) is the retirement benefit of the i-th
generation who retires at time t = i; see Figure 2, (2.6) and (2.7).
Lastly, we define our expected utility maximization problem as
max
π,θ
E
"X∞
i=1
β
iUγ(Bi(i))#
subject to 0 6 π 6 1, θ > 0, (4.3)
where the expectation is with respect to the retirement benefits Bi(i) for all generations
i ∈ N. Recall that Bi(i) are path-dependent and depend on the investment strategy π
and the adjustment parameter θ.
We numerically solve the maximization problem (4.3), since neither the expected utility
in (4.3) nor the solution for π and θ are available in closed form. We approximate the
expected utility in (4.3) by Monte Carlo simulations, and optimize π and θ using Bayesian
optimization, as explained next.
4.2. Bayesian Optimization for Expected Utility Maximization
We briefly explain here how we use Bayesian optimization (BO) for solving the expected
utility maximization problem (4.3). For details, see Appendix B and references therein.
BO is a modern machine learning approach for globally optimizing a black-box objective
function, and has been shown to be more efficient than traditional approaches such as
grid search (Shahriari et al. 2016). It has been widely used in applications where the
objective function is computationally expensive to evaluate, such as the optimization of
hyper parameters of a large-scale AI model (Snoek et al. 2012). The current work is the
first attempt to apply BO in optimizing a pension system.
The objective function in (4.3) takes π and θ as an input and outputs the expected
utility:
(π, θ) 7→ f(π, θ) := E
"X∞
i=1
β
iUγ(Bi(i))#
,
where we note again that Bi(i) depends on π and θ. The key idea of BO is to “learn” the
landscape of the objective function f(π, θ) while searching for π and θ that maximizes
the objective function. BO first evaluates the function values f(π, θ) for some initial
candidates of π and θ, and obtains a rough estimate for the landscape of f(π, θ). In the
next step, BO finds π and θ such that the function value f(π, θ) and its uncertainty
are both high, so as to balance the so-called exploitation-exploration trade-off. BO then
evaluates f(π, θ) for these π and θ, and updates the estimate of the landscape of f(π, θ).
BO iterates this learning-optimization procedure. Estimates of the maximizers, (π
∗
, θ∗) =
arg max f(π, θ) are obtained after a sufficient number of iterations (Bull 2011).
The above procedure is called “Bayesian” because the learning of the objective function
is done by a Bayesian nonparametric method (Rasmussen and Williams 2006). The
Bayesian method is used because it can yield both an estimate of the landscape as well
14 A. Chen, M. Kanagawa and F. Zhang
as its uncertainties, which are crucial for the exploitation-exploration trade-off and for
gaining the optimization efficiency. For implementation, we use the R package mlrMBO
(Bischl et al. 2017) in our numerical analysis.
4.3. Simulation Setting
We explain here how we approximate the expected utility in (4.3) by Monte Carlo
simulations, which is necessary for applying Bayesian optimization. Moreover, we describe
the problem setting for our numerical analysis in the next section. First of all, we set the
number of working generations as N = 40, the discounting factor in (4.3) as β = 0.98,
and the annual contribution as c = 1.
4.3.1. Financial Market
We consider three settings for the financial market that represent different market
risks, to investigate when IRS in the IRS-DC model works most effectively. The market
price of risk, a.k.a the Sharpe ratio, is defined by
λ :=
µ − r
σ
(4.4)
where µ and σ are the rate and volatility of the stock, and r is the rate of the risk-free
asset; see Section 2.1.2. The Sharpe ratio quantifies the performance of a risky project in
relation to a risk-free investment. It is one of the most frequently used performance
measures, and we use it to describe different financial markets in our experiments.
Typically, a Sharpe ratio above 0.5 in the long run indicates great investment performance
and is difficult to achieve, while a Sharpe ratio between 0.1 and 0.3 is often considered
reasonable and can be achieved more easily (e.g., Sharpe 1998). Table 1 shows the Sharpe
ratios for different financial markets estimated from historical data.4It shows that high
values of the Sharpe ratio are around 0.3, and low values can be below 0.05.
For the simulation, we consider the following three settings for the financial market,
with different levels of the Sharpe ratio:
Market 1: λ1 =
µ1 − r1
σ1
=
0.065 − 0.02
0.15
= 0.3;
Market 2: λ2 =
µ2 − r2
σ2
=
0.065 − 0.01
0.25
= 0.22;
Market 3: λ3 =
µ3 − r3
σ3
=
0.065 − 0.01
0.5
= 0.11.
We refer to Markets 1, 2, and 3 as M1, M2, and M3 for brevity. We call M1, M2, and M3
the markets with high, intermediate, and low Sharpe ratios, respectively. The calibrated
values from the real world for the longer period (Table 1) justify the use of the chosen
Sharpe ratios in our experiment.
4.3.2. Risk Aversion of the Social Planner
The relative risk aversion γ in the the CRRA utility function (4.1) represents the social
planner’s risk attitude: the social planner becomes more risk-averse if γ is larger. To study
the impacts of γ on the optimal investment strategy π and adjustment parameter θ, we
consider three settings: γ = 3, 5, 10.
4.3.3. Entry Cohorts
The generations with indicators i = 1, . . . , 40 are those who participate in the IRS-DC
plan at time t = 0, and are called entry cohorts. For t < 0, i.e., before participating
Intergenerational Risk Sharing in a Defined Contribution Pension System 15
Table 1: Sharpe ratios of different financial markets estimated by
empirical data for three financial markets from the U.S., Germany and
China. We use the stock market index and the 10-year treasury bond
as surrogates for risky and risk-free assets. We only have access to the
data for the Chinese market after 2003. For each market, the Sharpe
ratio is reported for two periods: from 1992 (or 2003 for China) to 2021,
and from 2003 to 2010, the latter being a period around the financial
crisis.
Country: U.S. Germany China
Stock: S&P 500 DAX SSECI
Bond: 10y T-bond 10y T-bond 10y T-bond
Period: 1992-2021 1992-2021 2003-2021
Sharpe ratio: 0.2827 0.2114 0.0631
Period: 2003-2010 2003-2010 2003-2010
Sharpe ratio: 0.0798 0.3122 0.0485
in the IRS-DC plan, we assume that the entry cohorts participate in a pure DC plan
that applies the optimal life-cycle investment strategy, following Gollier (2008). Namely,
the pure DC plan invests a large amount into the stock when the participant is young
and gradually reduces the amount invested in the stock as the participant approaches
retirement. To be more precise, for a generation i where i = 1, . . . , 40, let Bi(t) be the
individual account of generation i and Yi(t) be the net present value at time t of all the
future contributions of generation i; then the optimal fraction π
ind
i
(t) of generation i’s
wealth to be invested in the stock is given by
π
ind
i
(t) := π
c Bi(t) + Yi(t)
Bi(t)
. (4.5)
See Merton (1971, Eq. 71). Notice that π
c
is the so-called Merton constant defined as
π
c
:=
λ
γσ
, (4.6)
where λ is the Sharpe ratio in (4.4). Note that Yi(t) can be calculated straightforwardly
here, as the interest rate risk is excluded.
For an individual with the CRRA utility function, the life-cycle investment strategy
(4.5) provides the highest expected utility (Merton 1971; Gollier 2008). Hence, the
life-cycle investment strategy and its variants have been popular choices for pure DC
plans (e.g., Booth and Yakoubov 2000; Haberman and Vigna 2002). Note that, when an
individual is young, the discounted future income Yi(t) is much higher than her current
wealth in the account Bi(t), and thus π
ind(t) in (4.5) is much larger than 1. Therefore,
the life-cycle investment strategy (4.5) implies a high-leverage (i.e., borrowing) strategy
when the individual is young5(see Figure 3).
The life-cycle investment strategy is also used in Section 5.5 to make a comparison
between the IRS-DC and the optimal pure DC plans.
16 A. Chen, M. Kanagawa and F. Zhang
(a) Market 1 (b) Market 3
Figure 3: Realizations of the optimal life-cycle investment strategy (4.5) for an individual
who participates in the pure DC plan for her entire working period of 40 years. The left
and right figures are for the Markets 1 and 3, respectively. Three values of the risk
aversion γ = 3, 5, 10 are considered. The vertical axis represents (4.5) and the horizontal
axis the time.
4.3.4. Euler-Maruyama Approximation
For simulating the dynamics of the asset process (2.4), we use the Euler-Maruyama
approximation. Given a finite time horizon T > 0, we divide the interval [0, T] into n
equal time intervals:
[0, T] = [0, ∆, 2∆, · · · , n∆],
where we set the step size as ∆ = 1/12, which corresponds to one month. Then we
simulate the asset process as
A(t + ∆) = A(t) + (π(µ − r) + r)∆ + πσ√
∆Z,
A(t)+ = A(t) + 40c − Bt(t), if t ∈ N ∪ {0},
where Z is a standard normal random variable. The dynamics of the asset process in a
pure DC plan is simulated in a similar way.
The step size ∆ = 1/12 implies that the indexation rate (2.11) is adjusted monthly
according to the funding ratio. This monthly update is more frequent than the annual
cash flows of the fund. This setting reflects the fact that the market values of individual
accounts usually vary more frequently than cash flows in reality. The IRS-DC fund is
assumed to be fully funded at t = 0 implying that the initial value of the notional funding
ratio is one: A(0)/L(0) = 1. (The influence of the initial funding ratio is examined in the
numerical analysis in Section 5.2.)
4.3.5. Time Horizon T
While the expected utility in (4.3) involves the infinite horizon, it is intractable for
simulations and we need to use a finite horizon T. In our numerical analysis, we set
the horizon as T = 80 years. For approximating the expected utility in (4.3), we then
simulate 10,000 paths for the asset process until the horizon T and compute the Monte
Carlo average. Note that, in this setting, the generations i = 41, . . . , 80 are those who
spend their entire working periods in the IRS-DC plan.
4.3.6. Upper Bound of the Adjustment Parameter θ
While the adjustment parameter θ can take an arbitrarily large value in theory, for
numerical optimization of θ we need to set its upper bound. The range of θ is set as
0 < θ 6 1 in our numerical analysis.
Intergenerational Risk Sharing in a Defined Contribution Pension System 17
Table 2: Optimal investment strategy π
∗ and adjustment parameter θ∗
obtained by Bayesian optimization for the 9 different settings, resulting
from the 3 different values of the Sharpe ratio λ and the 3 different
values of the risk aversion γ. For comparison, the Merton constant is
shown for each setting.
λ = 0.3 γ = 3 γ = 5 γ = 10
π
∗
: 0.832 0.519 0.267
θ
∗
: 1 1 1
Merton constant: 0.667 0.4 0.2
λ = 0.22: γ = 3 γ = 5 γ = 10
π
∗
: 0.479 0.334 0.124
θ
∗
: 0.0651 0.0535 0.0237
Merton constant: 0.293 0.176 0.088
λ = 0.11: γ = 3 γ = 5 γ = 10
π
∗
: 0.131 0.06 0.0544
θ
∗
: 0.0835 0.072 0.0000493
Merton constant: 0.073 0.044 0.022
5. Numerical Analysis
This section presents our numerical analysis of the IRS-DC pension model. In Section
5.1, we first discuss the optimal investment strategy and adjustment parameter obtained
by Bayesian optimization. In Section 5.2, we then study the dynamics of the funding
ratio, and discuss how the adjustment parameter θ affects its stability. The stability of
the funding ratio can be understood as the stability of the pension fund’s operation. In
Sections 5.3, 5.4, and 5.5, we focus on the individual accounts in the IRS-DC fund. We
first study the dynamics of individual accounts in Section 5.3, and then the distribution
of retirement benefits in Section 5.4. Lastly, we study the welfare of pension participants
in Section 5.5. Additional numerical analyses on a time-varying investment strategy and
the influence of population structure are reported in Appendix E.
5.1. Optimal Investment Strategy and Adjustment Parameter
As explained in Section 4.3, we consider 9 different settings for the numerical analysis,
resulting from 3 different values for the relative risk aversion (γ = 3, 5, 10) of the social
planner and 3 different values for the Sharpe ratio (λ = 0.3, 0.22, 0.11) of the financial
market. In each setting, we find the optimal investment strategy π and the adjustment
parameter θ by Bayesian optimization, as described in Section 4. We report the resulting
optimal values of π and θ in Table 2. For comparison, we also report the Merton constant
(4.6) for each setting in Table 2, which will be used in the experiment in Section 5.5.
For each value of the Sharpe ratio λ, the optimal π
∗ and θ∗
tend to decrease as the
risk aversion γ increases (with the exception of the case λ = 0.3, where θ
∗
remains
18 A. Chen, M. Kanagawa and F. Zhang
1). Regarding the optimal investment strategy π
∗
, this tendency can be anticipated by
the same tendency in the Merton constant (4.6), which is inversely proportional to the
risk aversion γ. Regarding the optimal adjustment parameter θ
∗
, this tendency can be
expected from the analysis in Section 3.3, where it is shown that a smaller adjustment
parameter θ lowers the volatility of the retirement benefits; thus a higher risk aversion γ
leads to smaller θ
∗
.
For each value of the risk aversion γ, the optimal π
∗ and θ∗
tend to be smaller as the
Sharpe ratio λ becomes smaller (for the cases γ = 3, 5 and λ = 0.22, 0.11, the adjustment
parameter θ
∗
is comparably small). One can understand this tendency in a similar way
as the discussion in the above paragraph, since the Sharpe ratio represents the market
price of risk. Note that θ
∗
is extremely small for γ = 10 and λ = 0.01, which implies the
IRS-DC plan becomes similar to a DB plan, as discussed in Section 3.3; in this case π
∗
is also very small, meaning that the asset is mainly invested in the risk-free asset.
5.2. Funding-Ratio Process
We next study the dynamics of the funding ratio A(t)/L(t), investigating the influences
of the adjustment parameter θ and the initial funding ratio A(0)/L(0).
5.2.1. Influence of the Adjustment Parameter
We first examine the influence of the adjustment parameter θ. We fix the investment
strategy to π = 0.131, which is optimal for Market 3 with γ = 3 (see Table 2). We
consider three values for the adjustment parameter: θ1 = 0.04, θ2 = 0.0835 and θ3 = 0.2,
where θ2 is optimal for Market 3 with γ = 3. For each value of the adjustment parameter,
we simulate the IRS-DC fund 10,000 times in Market 3; the results are summarized in
Figure 4.
Figure 4 (a) shows the mean and standard deviation of the funding ratio A(t)/L(t)
over the 10,000 simulations as a function of time t, for each of the three values of θ. The
standard deviation is the smallest for θ3 = 0.2 and the largest for θ1 = 0.04; therefore
the larger the adjustment parameter, the smaller the standard deviation of the funding
ratio. This observation validates our analysis in Section 3, which indicates that a larger
adjustment parameter θ makes the funding ratio lower. Moreover, the mean of the funding
ratio is close to 1 for θ2 = 0.0835 and θ2 = 0.2, while the mean (and standard deviation)
gradually increase for θ3 = 0.04. This observation is also consistent with the analysis
in Section 3, which implies that a smaller adjustment parameter lets the funding ratio
A(t)/L(t) converge to 1 more slowly.
Figures 4 (b), (c) and (d) show the paths of the funding ratio for three representative
scenarios defined as follows. We pick up the three scenarios from the 10, 000 simulations
that correspond to the top 10%, 50%, and 90% values of the utilities of the social planner
(see (4.2)), and plot the funding ratio processes in these scenarios; these three scenarios
can be interpreted as representing “good”, “medium” and “bad” realizations of the financial
market. The discrepancy between the paths of the funding ratio in these scenarios reduces
as θ increases. This implies that the funding ratio volatility decreases as θ increases, and
is consistent with our analysis in Section 3.
5.2.2. Influence of the Initial Funding Ratio
We next examine the influence of the initial funding ratio A(0)/L(0) on the dynamics
of the funding ratio A(t)/L(t). We consider three cases for the initial funding ratio: (1)
A(0)/L(0) = 0.9, (2) A(0)/L(0) = 1 and (3) A(0)/L(0) = 1.1. We simulate the IRSDC fund 10,000 times for each case and calculate the mean and standard deviation of
A(t)/L(t). Figure 5 shows the results for (a) Market 3 with π = 0.131 and θ = 0.0835,
Intergenerational Risk Sharing in a Defined Contribution Pension System 19
(a) Means and standard deviations for θ1 = 0.04,
θ2 = 0.0835 and θ3 = 0.2. (b) Paths for θ1 = 0.04.
(c) Paths for θ2 = 0.0835. (d) Paths for θ3 = 0.2.
Figure 4: The influence of the adjustment parameter θ on the funding ratio process
A(t)/L(t) in Market 3. Panel (a) shows the mean and standard deviation of the funding
ratio A(t)/L(t) over 10,000 simulations as a function of time t, for π = 0.131 and each
of three values of the adjustment parameter: θ1 = 0.04, θ2 = 0.0835 and θ3 = 0.2. Panel
(b) shows the paths of A(t)/L(t) with θ1 = 0.04 corresponding to the top 10%, 50% and
90% values of the utility of the social planner over the 10,000 simulations. Panels (c) and
(d) show those with θ2 = 0.0835 and θ3 = 0.2, respectively.
which are optimal for γ = 3 in Market 3, and for (b) Market 1 with π = 0.267 and
θ = 1, optimal for γ = 10 in Market 1. Regardless of the initial funding ratio A(0)/L(0),
the mean of the funding ratio A(t)/L(t) converges to 1 as t increases. For Market 3,
where the adjustment parameter θ is small, the mean of the funding ratio converges to 1
slowly; for Market 1, where the adjustment parameter is larger, the mean converges to 1
immediately. Therefore these results suggest that the IRS-DC fund can self-stabilize the
funding ratio to 1, and a larger adjustment parameter θ leads to a quicker stabilization;
again, this is consistent with the analysis in Section 3.
5.3. Dynamics of Individual Accounts
We next study the dynamics of individual accounts in the IRS-DC plan. As for the
analysis in Section 3.4, to study the effects of IRS, each individual account in the IRSDC plan is compared with the corresponding account in a pure DC plan that uses the
same investment strategy π
∗
in Table 2. (A pure DC plan using the optimal life-cycle
investment strategy is compared in Section 5.5.) Since IRS is absent, the dynamics of an
individual account in the pure DC plan is given by the asset process yielding (3.12).
Figure 6 shows arbitrarily chosen paths of the individual accounts from the generation
20 A. Chen, M. Kanagawa and F. Zhang
(a) (b)
Figure 5: The influence of the initial funding ratio A(0)/L(0) on the funding ratio process
A(t)/L(t). Panel (a) shows the mean and standard deviation of A(t)/L(t) in Market 3
over 10,000 simulations, for π = 0.131 and each of three settings of the initial funding
ratio: A(0)/L(0) = 1 (red), A(0)/L(0) = 0.9 (green; under-funded) and A(0)/L(0) = 1.1
(blue; over-funded). Panel (b) shows those in Market 1 with π = 0.267 and θ = 1 and
the same three values of the initial funding ratio.
(a) Market 1. (b) Market 2
(c) Market 3.
Figure 6: Examples of paths of the IRS-DC and pure DC accounts for the generation
i = 41 in the three market settings with risk aversion γ = 10.
i = 41 in the IRS-DC and pure DC plans, for the three market settings and risk aversion
γ = 10. For Market 1, for which the adjustment parameter θ
∗
is large (see Table 2), the
paths of the IRS-DC and DC accounts are similar. In contrast, for Markets 2 and 3, for
which the adjustment parameter θ
∗
is smaller, the IRS-DC account accumulates more
stably than the pure DC account. This observation is consistent with the discussions in
Sections 2.1.5, 3.3 and 3.4, where it is argued that a smaller adjustment parameter θ
reduces the volatility of an IRS-DC account as a result of IRS.
We next quantify the effects of IRS on stabilizing the accumulation of an IRS-DC
Intergenerational Risk Sharing in a Defined Contribution Pension System 21
Table 3: Average IR roughness over 10,000 simulations calculated for each of the IRS-DC
and pure DC accounts, for the three market settings and the three levels of risk aversion.
IR roughness γ = 3 γ = 5 γ = 10
Market 1 IRS-DC 0.937 0.944 0.959
DC 0.732 0.739 0.754
Market 2 IRS-DC 0.993 0.996 1.000
DC 0.731 0.735 0.752
Market 3 IRS-DC 0.991 0.998 1.000
DC 0.737 0.751 0.753
account. To this end, we calculate the increment-ratio-based roughness (IR roughness)
(Bardet et al. 2011), a measure of roughness/smoothness of a stochastic process, for each
path of the IRS-DC and pure DC accounts. The IR roughness takes a value between
0 and 1, and a larger value indicates that the path is smoother; see Appendix C for
details. Table 3 shows the average of the IR roughness over the 10,000 simulations for
each of the IRS-DC and pure DC accounts from the generation i = 41. For all the 9
settings considered, the IRS-DC account has a larger IR roughness than the pure DC
account, which implies that the IRS-DC account is smoother. Therefore, IRS makes the
accumulation of the IRS-DC account more stable than the pure DC account (Recall that
the only difference between the IRS-DC and DC plans here is the existence of IRS).
5.4. Distribution of Retirement Benefits
We next study how IRS affects the distribution of retirement benefits. Figure 7 shows
the histograms of retirement benefits (from the 10,000 simulations) of the IRS-DC and
pure DC accounts for the generation i = 41, for the three market settings and risk
aversion γ = 10. (Results for γ = 3, 5 are shown in Appendix D.1.) For Market 1, for
which the adjustment parameter θ
∗ of the IRS-DC plan is large, the histograms of the
IRS-DC and pure DC retirement benefits are almost identical. On the other hand, for
Markets 2 and 3, for which the adjustment parameter is smaller, the volatility of the
IRS-DC benefits is smaller than the pure DC benefits. In particular, for Market 3, for
which the adjustment parameter is close to 0, the volatility of the IRS-DC benefits is
very small. These observations support the analysis in Sections 3.3 and 3.4 that a smaller
adjustment parameter θ makes the retirement benefits less volatile by IRS. Moreover, our
result is consistent with similar observations made by Bams et al. (2016) and Donnelly
(2017) that a collective DC scheme can reduce the volatility of retirement benefits.
5.5. Welfare of Participants
Lastly, we study how IRS can improve the welfare of the IRS-DC plan participants
in terms of their expected utilities. To this end, we make a comparison with a pure DC
plan that uses the optimal life-cycle investment strategy in (4.5), which yields the highest
expected utility for an individual investor.
For simplicity, we assume that each participant in the IRS-DC plan has the same CRRA
utility Uγ in (4.1) as the social planner. Similarly, to make a comparison straightforward,
we assume that each participant in the pure DC plan has the same CRRA utility. To
22 A. Chen, M. Kanagawa and F. Zhang
(a) Market 1 (b) Market 2
(c) Market 3
Figure 7: Histograms of the retirement benefits (obtained from the 10,000 simulations)
of the IRS-DC and pure DC accounts for the generation i = 41, for the three market
settings and risk aversion γ = 10. In each figure, the red and green histograms are those
of the IRS-DC and pure DC benefits, respectively; the brown part shows the overlap
between the two histograms.
measure the welfare, we calculate the certainty equivalent (CE) for each participant.
That is, for an IRS-DC participant from the generation i with retirement benefit Bi(i),
the CE is defined as the quantity CE(IRS-DC)
i > 0 satisfying
Uγ(CE(IRS-DC)
i
) = E[Uγ(Bi(i))], (5.1)
where we approximate the expectation in the right hand side by the empirical average of
10,000 realizations of Bi(i). The CE of each participant in the pure DC plan is calculated
similarly. Note that, since the utility function is strictly concave, the expected utility is
monotonically increasing with respect to the CE; a higher CE implies a higher expected
utility. We calculate the CEs of the participants in the IRS-DC plan and the pure DC
plans for the generations i = 41, . . . , 80.
Figure 8 shows the CEs of the IRS-DC and pure DC participants for the generations
i = 41, . . . , 80, for the three market settings and risk aversion γ = 10. (Results for γ = 3, 5
are shown in Appendix D.2.) For Market 1, where the Sharpe ratio is high, the pure DC
participants obtain higher welfare than the IRS-DC participants. On the other hand, for
Markets 2 and 3, where the Sharpe ratio is lower, the IRS-DC participants obtain higher
welfare than the pure DC participants. This observation indicates that the IRS-DC plan
can provide higher welfare than the optimal DC plan when the market is more volatile
(in the sense of having a lower Share ratio). Therefore, IRS is expected to be particularly
advantageous in protecting individual participants when the market is turbulent (e.g.,
when there is an economic shock).
While it has been generally known in the literature that IRS is welfare-improving,
there are a few key differences in our contribution. To explain this, we make a comparison
with closely related works. Gollier (2008) shows that IRS is welfare-improving over the
Intergenerational Risk Sharing in a Defined Contribution Pension System 23
optimal life-cycle investment strategy, but his analysis is based on the assumption that
the pension fund can perform borrowing for investment (i.e., the investment strategy π
can be larger 1); this assumption is not realistic for pension funds in reality. Moreover,
his second-best strategy assumes the existence of a “shareholder” that helps finance the
pension fund. Our result above shows that IRS can be welfare-improving even when
borrowing is prohibited for the pension fund (i.e., 0 < π < 1) and without a shareholder.
Cui et al. (2011) show that a hybrid pension plan with IRS can provide higher welfare
than a pure DC plan with an “optimal” investment strategy. However, their “optimal”
individual investment strategy is not allowed to perform borrowing, and therefore it is less
optimal than the optimal life-cycle strategy (4.5), which performs borrowing. Moreover,
Cui et al. (2011) optimize the parameters of the pension fund so as to maximize the
expected utility of one specific entry cohort, not all the generations; they then compare
this entry cohort’s welfare with a pure DC plan participant’s welfare. This way of
optimizing the pension system is not appropriate as it ignores the other generations’
welfare. On the other hand, we show that the IRS-DC plan, which optimizes for all
the generations’ utilities as in (4.3), can improve the welfare over the optimal life-cycle
investment strategy, when the market is volatile.
Bams et al. (2016) consider a similar pension model as ours, but they do not show that
their model can provide higher welfare than individual DC plans. Similarly, Donnelly
(2017) considers a related collective DC plan, but does not compare it with individual
DC plans. Chen et al. (2016) study a three-pillar model in which the second pillar is a
collective DC, DB, or hybrid pension plan, and make a comparison with the corresponding
three-pillar model with the second pillar being an individual DC plan. While they show
that the former yields higher welfare than the latter, they assume that the both plans
use the same investment strategy, with the fraction invested in the stock being π = 0.5;
therefore their individual DC plan is not optimal. Different from these previous works,
we make a comparison with the optimal life-cycle investment strategy. By doing so, we
show that the volatility of the financial market is a key factor that determines whether
IRS is welfare-improving over the optimal life-cycle investment strategy.
6. Concluding Remarks
We have shown that a fully funded collective DC pension system with intergenerational
risk sharing (IRS) can improve the welfare of individual participants, as compared with
individual DC benchmarks using the optimal life-cycle investment strategy, when the
financial market is volatile. Key new findings to the literature include that i) the welfare
improvement can be achieved without relying on borrowing and shareholders, in contrast
to, e.g., Gollier (2008), and that ii) whether IRS improves the welfare depends on the
volatility of the financial market, as measured by the Sharpe ratio. These observations
suggest that a fully funded pension system with a realistic investment strategy (i.e.,
without borrowing) can implement IRS and protect individual participants from a
turbulent market.
Our investigation has been based on a stylized model, which we call the IRS-DC
pension model, that uses an indexation rate of individual accounts as a device for IRS.
This indexation rate, originally introduced by Goecke (2013), is automatically adjusted
according to the notional funding ratio of the pension fund, so as to balance the welfare
of different generations and the sustainability of the pension fund. We have analyzed
the funding ratio process and retirement benefits in the IRS-DC model, and how their
volatility is controlled by the adjustment parameter in the indexation rate. Moreover, we
24 A. Chen, M. Kanagawa and F. Zhang
(a) Market 1. (b) Market 2.
(c) Market 3.
Figure 8: Certainty equivalents of the participants in the IRS-DC and pure DC plans for
the generations i = 41, . . . , 80, for the three market settings and risk aversion γ = 10.
have shown how the adjustment parameter and the investment strategy can be optimized
by using Bayesian optimization, a machine learning method for global optimization.
There are a number of possible future directions. First, as we have shown the effectiveness of the indexation rate of Goecke (2013) as a means for IRS in a collective pension
system, the same indexation rate may be applied to other collective schemes, such as
hybrid pension systems (e.g., Cui et al. 2011; Chen et al. 2016) and notional DC pension
systems (e.g., Settergren 2001), where other forms of automatic adjustment rules are used
for adjusting the individual accounts and/or contributions. This is worth investigating,
as automatic adjustment rules have been used in real pension systems, such as the Dutch
and Swedish pension systems (OECD 2021, Chapter 2).
Second, as Bayesian optimization provides an efficient way of optimizing the parameters
of a pension system, it enables researchers to study optimal pension systems under more
realistic but complex setups. For example, Bayesian optimization may be applied to
optimize the three-pillar pension system of Chen et al. (2016), which involves a number
of parameters, by expected utility maximization; this may enable showing that their
collective scheme is welfare-improving over the optimal individual benchmark using the
life-cycle investment strategy, as we have shown for our collective scheme.
Third, our finding that IRS is welfare-improving in a volatile market is worth further
Intergenerational Risk Sharing in a Defined Contribution Pension System 25
investigation in a more realistic setup of the financial market. While our setup of the
Black-Scholes market (i.e., log-normally distributed stock returns) follows many of related
works (e.g., Cui et al. 2011; Chen et al. 2016), it is known that this setup does not
necessarily hold in reality (e.g., Cont 2001). For example, the log returns of real stocks are
known to have heavy tails, which implies that real financial markets are more volatile than
the Black-Scholes market. Similarly, it is more realistic to assume that the interest rate
is stochastic and time-varying, rather than assuming a constant interest rate. Extending
the current work to these more realistic settings will enable a deeper understanding of
the functionality of the IRS.
Fourth, the discontinuity risk may be discussed for the IRS-DC model. We have implicitly assumed the mandatory participation of individuals by modelling that the population
in each generation remains the same, as in related works (e.g., Gollier 2008; Chen et al.
2016). One could relax this assumption by making the participation voluntary, and study
individuals’ preferences and how they impact the sustainability of the pension fund and
the welfare of different generations (e.g., Beetsma et al. 2012). Because contributions are
not adjusted in the IRS-DC plan by design, it may be anticipated that the IRS-DC plan
is less prone to discontinuity risk than DB-based pension plans. However, if voluntary
participation changes the populations of different generations, the effectiveness of the IRS
may be affected (as suggested by the additional numerical analysis in Appendix E.2). It
will be interesting to investigate whether mandatory participation is necessary for the
IRS-DC plan to maintain effective IRS.
Acknowledgements
We would like to express our gratitude to the editor and the anonymous reviewers
for their time and insightful comments, which helped improve the paper. This work
in part has been supported by the French government, through the 3IA Cote d’Azur
Investment in the Future Project managed by the National Research Agency (ANR) with
the reference number ANR-19-P3IA-0002, and by Deutsche Forschungsgemeinschaft with
Grant number 418318744 of the research project: “Zielrente: die Lösung zur alternden
Gesellschaft in Deutschland”.
Notes
1Our indexation rate corresponds to Goecke (2013, Eq. (5)) with ρtarget = 0.
2The funding ratio in Sweden’s notional DC pension system is notional since both “assets”
and “liabilities” are notional, as it is a PAYG system.
3Since retirees leave the fund immediately after receiving lump-sum benefits, Eq. (5) in
Settergren (2001) does not exist in our case and thus Eq. (3) in Settergren (2001) is equal to
the notional liability in (2.8).
4Since we only have limited access to the data of the Chinese market before 2003, we only
report the Sharpe ratios for periods after 2003 for the Chinese market. We report the Sharpe
ratios for longer and shorter periods, the latter being a period around the financial crisis, to
show that the Sharpe ratio may depend on the period considered.
5Note that (4.5) is a random variable as Bi(t) is a random variable. Therefore (4.5) can
increase in a short horizon of time, but in the long run, it decreases in expectation as t increases,
since as t increases Yi(t) decreases and Bi(t) increases in expectation. For more details on the
life-cycle strategy, we refer to Merton (1971).
26 A. Chen, M. Kanagawa and F. Zhang
REFERENCES
Allen, F. and Gale, D. (1997). Financial markets, intermediaries, and intertemporal smoothing.
Journal of Political Economy, 105(3):523–546.
Bams, D., Schotman, P. C., and Tyagi, M. (2016). Optimal risk sharing in a collective defined
contribution pension system. Netspar Discussion Paper.
Bardet, J.-M., Surgailis, D., et al. (2011). Measuring the roughness of random paths by increment
ratios. Bernoulli, 17(2):749–780.
Barr, N. and Diamond, P. (2008). Reforming Pensions: Principles and Policy Choices. Oxford
University Press.
Barr, N. and Diamond, P. (2011). Improving sweden’s automatic pension adjustment mechanism.
Center for Retirement Research at Boston College, 11.
Baumann, R. T. and Müller, H. H. (2008). Pension funds as institutions for intertemporal risk
transfer. Insurance: Mathematics and Economics, 42(3):1000–1012.
Beetsma, R. and Romp, W. (2016). Intergenerational risk sharing. In Handbook of the Economics
of Population Aging, chapter 6, pages 311–380. Elsevier.
Beetsma, R. M., Romp, W. E., and Vos, S. J. (2012). Voluntary participation and
intergenerational risk sharing in a funded pension system. European Economic Review,
56(6):1310–1324.
Benartzi, S. and Thaler, R. H. (2001). Naive diversification strategies in defined contribution
saving plans. American Economic Review, 91(1):79–98.
Bischl, B., Richter, J., Bossek, J., Horn, D., Thomas, J., and Lang, M. (2017). mlrmbo: A
modular framework for model-based optimization of expensive black-box functions. arXiv
preprint arXiv:1703.03373.
Booth, P. and Yakoubov, Y. (2000). Investment policy for defined-contribution pension scheme
members close to retirement: An analysis of the “lifestyle” concept. North American
Actuarial Journal, 4(2):1–19.
Boulier, J.-F., Huang, S., and Taillard, G. (2001). Optimal management under stochastic interest
rates: the case of a protected defined contribution pension fund. Insurance: Mathematics
and Economics, 28(2):173–189.
Bull, A. D. (2011). Convergence rates of efficient global optimization algorithms. Journal of
Machine Learning Research, 12:2879–2904.
Cairns, A. J. (1996). Continuous-time pension-fund modelling. In Proceedings of the 6th AFIR
International Colloquium, Nuremberg, pages 609–624. Citeseer.
Cairns, A. J., Blake, D., and Dowd, K. (2006). Stochastic lifestyling: Optimal dynamic asset
allocation for defined contribution pension plans. Journal of Economic Dynamics and
Control, 30(5):843–877.
Chen, A. and Delong, Ł. (2015). Optimal investment for a defined-contribution pension scheme
under a regime switching model. ASTIN Bulletin: The Journal of the IAA, 45(2):397–419.
Chen, D. H., Beetsma, R. M., Ponds, E. H., and Romp, W. E. (2016). Intergenerational risksharing through funded pensions and public debt. Journal of Pension Economics &
Finance, 15(2):127–159.
Cont, R. (2001). Empirical properties of asset returns: stylized facts and statistical issues.
Quantitative Finance, 1(2):223.
Cui, J., De Jong, F., and Ponds, E. (2011). Intergenerational risk sharing within funded pension
schemes. Journal of Pension Economics and Finance, 10(1):1–29.
Donnelly, C. (2017). A discussion of a risk-sharing pension plan. Risks, 5(1):12.
Gabrielli, A. (2020). A neural network boosted double overdispersed poisson claims reserving
model. ASTIN Bulletin: The Journal of the IAA, 50(1):25–60.
Goecke, O. (2013). Pension saving schemes with return smoothing mechanism. Insurance:
Mathematics and Economics, 53(3):678–689.
Gollier, C. (2008). Intergenerational risk-sharing and risk-taking of a pension fund. Journal of
Public Economics, 92(5-6):1463–1485.
Gordon, R. H. and Varian, H. R. (1988). Intergenerational risk sharing. Journal of Public
Economics, 37(2):185–202.
Haberman, S. and Vigna, E. (2002). Optimal investment strategies and risk measures in defined
contribution pension schemes. Insurance: Mathematics and Economics, 31(1):35–69.
Intergenerational Risk Sharing in a Defined Contribution Pension System 27
Hagen, J. (2013). A history of the Swedish pension system. Working Paper Series, Center for
Fiscal Studies 2013:7, Uppsala University, Department of Economics.
Hainaut, D. (2018). A neural-network analyzer for mortality forecast. ASTIN Bulletin: The
Journal of the IAA, 48(2):481–508.
Kanagawa, M., Hennig, P., Sejdinovic, D., and Sriperumbudur, B. K. (2018). Gaussian
processes and kernel methods: A review on connections and equivalences. arXiv preprint
arXiv:1807.02582.
Karatzas, I. and Shreve, S. (1998). Brownian Motion and Stochastic Calculus. Springer Science
& Business Media, 2nd edition.
Karatzas, I. and Shreve, S. E. (1991). Brownian motion and stochastic calculus, volume 113.
Springer Science & Business Media.
Li, S., Labit Hardy, H., Sherris, M., and Villegas, A. M. (2022). A managed volatility investment
strategy for pooled annuity products. Risks, 10(6):121.
McKay, M. D., Beckman, R. J., and Conover, W. J. (2000). A comparison of three methods
for selecting values of input variables in the analysis of output from a computer code.
Technometrics, 42(1):55–61.
Menoncin, F. and Vigna, E. (2017). Mean–variance target-based optimisation for defined
contribution pension schemes in a stochastic framework. Insurance: Mathematics and
Economics, 76:172–184.
Merton, R. C. (1971). Optimum consumption and portfolio rules in a continuous-time model.
Journal of Economic Theory, 3(4):373–413.
OECD (2021). Pensions at a Glance 2021: OECD and G20 Indicators.
Olivieri, A., Thirurajah, S., and Ziveyi, J. (2022). Target volatility strategies for group selfannuity portfolios. ASTIN Bulletin: The Journal of the IAA, 52(2):591–617.
Rasmussen, C. and Williams, C. (2006). Gaussian Processes for Machine Learning. MIT Press.
Schnürch, S. and Korn, R. (2022). Point and interval forecasts of death rates using neural
networks. ASTIN Bulletin: The Journal of the IAA, 52(1):333–360.
Scognamiglio, S. (2022). Calibrating the lee-carter and the poisson lee-carter models via neural
networks. ASTIN Bulletin: The Journal of the IAA, 52(2):519–561.
Settergren, O. (2001). The automatic balance mechanism of the Swedish pension system.
Wirtschaftspolitische Blätter, 4.
Shahriari, B., Swersky, K., Wang, Z., Adams, R. P., and De Freitas, N. (2016). Taking the
human out of the loop: A review of Bayesian optimization. Proceedings of the IEEE,
104(1):148–175.
Sharpe, W. F. (1998). The sharpe ratio. Streetwise–the Best of the Journal of Portfolio
Management, pages 169–185.
Shiller, R. J. (1999). Social security and institutions for intergenerational, intragenerational,
and international risk-sharing. In Carnegie-Rochester Conference Series on Public Policy,
volume 50, pages 165–204. Elsevier.
Snoek, J., Larochelle, H., and Adams, R. P. (2012). Practical bayesian optimization of machine
learning algorithms. Advances in Neural Information Processing Systems, 25.
Vigna, E. and Haberman, S. (2001). Optimal investment strategy for defined contribution
pension schemes. Insurance: Mathematics and Economics, 28(2):233–262.
Wüthrich, M. V. (2020). Bias regularization in neural network models for general insurance
pricing. European Actuarial Journal, 10(1):179–202.
28 A. Chen, M. Kanagawa and F. Zhang
Appendix A. Proofs
A.1. Proof of Proposition 1
Proof. The identity (3.6) follows from taking the conditional expectation of (3.5),
using that the Brownian motion Z(s) for t0 < s < t is independent of the conditioning
variable ρ(t0)+ and hence the conditional expectation of Z(s) is zero. Eq. (3.7) follows
by using the Ito Isometry in (3.5):
V[ρ(t) | ρ(t0)+] = ˜σ
2E
"Z t
t0
e
−θ(t−s)dZ(s)
2
#
= ˜σ
2
Z t
t0
e
−2θ(t−s)ds.
Eqs. (3.8) and (3.9) follow by taking the limits in (3.6) and (3.7).
A.2. Proof of Proposition 2
Proof. Let t0 ∈ N be such that i − N 6 t0 6 i − 1. Let ρ(t) = ln(A(t)/L(t)) be the
log notional funding ratio. By (2.6), (2.7) and (2.11), we have
Bi(t0 + 1) (A 1)
= Bi(t0)+ exp µ˜ + θ
Z t0+1
t0
ρ(s)ds

= (Bi(t0) + c) exp µ˜ + θ
Z t0+1
t0
ρ(s)ds

,
(a)
= (Bi(t0) + c) exp µ˜ + ρ(t0)+ − ρ(t0 + 1) + Z t0+1
t0
σ˜dZ(s)

,
(b)
= (Bi(t0) + c) exp µ˜ + (1 − e
−θ
)ρ(t0)+ −
Z t0+1
t0
e
−θ(t0+1−s)σ˜dZ(s) + Z t0+1
t0
σ˜dZ(s)

,
= (Bi(t0) + c) exp µ˜ + (1 − e
−θ
)ρ(t0)+ + ˜σ
Z t0+1
t0

1 − e
−θ(t0+1−s)

dZ(s)

, (A 2)
where (a) follows from (3.4) and (b) follows from (3.5).
We show a proof by induction. Suppose that, for m ∈ N with 0 < m 6 N − 1, we have
Bi(i − m) = c
X
N
n=m+1
exp (n − m)˜µ + (1 − e
−θ
)
Xn
`=m+1
ρ(i − `)+
+ ˜σ
Xn
`=m+1
Z i−`+1
i−`

1 − e
−θ(i−`+1−s)

dZ(s)

(A 3)
Note that the identity (A 3) holds for m = N −1, since we have by (A 2) and Bi(i−N) = 0
Bi(i − N + 1) = c exp 
µ˜ + (1 − e
−θ
)ρ(i − N)+ + ˜σ
Z i−N+1
i−N

1 − e
−θ(i−N+1−s)

dZ(s)

.
Intergenerational Risk Sharing in a Defined Contribution Pension System 29
By using (A 2) with t0 = i − m , the assumption (A 3) implies that
Bi(i − m + 1) =
(Bi(i − m) + c) exp µ˜ + (1 − e
−θ
)ρ(i − m)+ + ˜σ
Z i−m+1
i−m

1 − e
−θ(i−m+1−s)

dZ(s)

=

c
X
N
n=m+1
exp (n − m)˜µ + (1 − e
−θ
)
Xn
`=m+1
ρ(i − `)+
+ ˜σ
Xn
`=m+1
Z i−`+1
i−`

1 − e
−θ(i−`+1−s)

dZ(s)

+ c

× exp µ˜ + (1 − e
−θ
)ρ(i − m)+ + ˜σ
Z i−m+1
i−m

1 − e
−θ(i−m+1−s)

dZ(s)

= c
X
N
n=m
exp (n − m + 1)˜µ + (1 − e
−θ
)
Xn
`=m
ρ(i − `)+
+ ˜σ
Xn
`=m
Z i−`+1
i−`

1 − e
−θ(i−`+1−s)

dZ(s)

,
which is the same expression as (A 3) with m being replaced by m − 1. Therefore, by
induction, (A 3) holds with m = 0, which is (3.11). This completes the proof.
Appendix B. Tutorial on Bayesian optimization
We provide here a short tutorial on Bayesian optimization (BO). For further details
and references, see e.g. Shahriari et al. (2016).
Let Ω be a parameter set and f : Ω → R be the objective function to be maximized. In
our problem, this parameter set is Ω = [0, 1] × [0, 1] and each x := (π, θ) ∈ Ω represents
a pair of the investment strategy π and adjustment parameter θ. We define the objective
function as the certainty equivalent (CE) of the expected utility in (4.3) with input
parameters x = (π, θ):
f(x) := f(π, θ) := CE(π, θ), (B 1)
where CE(π, θ) > 0 is such that Uγ(CE(π, θ)) = E
"X∞
t=1
β
tUγ(Bt(t))#
.
Note that the expected utility is a function of x = (π, θ), as the payment Bt(t) depends
on π and θ. Since the CRRA utility function Uγ is strictly monotonically increasing with
respect to its argument, the maximizer of the certainty equivalent is the same as the
maximizer of the expected utility:
arg max
(π,θ)∈Ω
CE(π, θ) = arg max
(π,θ)∈Ω
E
"X∞
t=1
β
tUγ(B(t))#
.
Thus, the maximization of the expected utility can be equivalently formulated as the
maximization of the objective function (B 1).
In our study, the expected utility is approximated by the Monte Carlo average of 10,000
simulations of the asset process A(t) (and thus the resulting Bt(t)) for t = 1, . . . , T := 80.
Therefore, each evaluation of f(x) for a given x = (π, θ) involves 10,000 simulations over
30 A. Chen, M. Kanagawa and F. Zhang
80 years on monthly basis, which is computationally expensive. If A(t) 6 0 happens at
any t > 0 for any of 10,000 simulations of the financial market, we set the objective
function value to its minimum: i.e., f(x) = 0.
B.1. Procedure of Bayesian optimization.
First, we generate initial design points x1, . . . , xninit for some ninit ∈ N, and evaluate
the function values f(x1), . . . , f(xninit ) on these points. One can generate these initial
points randomly (e.g, uniform sampling on Ω) or deterministically (e.g., grid points). In
our study, we use the design given by Latin hypercube sampling (McKay et al. 2000) on
Ω with ninit = 10.
Below we use the notation Dn := {(xi, f(xi))}
n
i=1 ⊂ Ω × R to write the collection
of points x1, . . . , xn and the resulting function values f(x1), . . . , f(xn). Dn can be
understood as “data” or “observations” about f after n-time evaluations of the function.
We also denote by α(x; Dn) the acquisition function, whose concrete form will be
introduced later in Section B.3. The acquisition function α(x; Dn) is a function of x ∈ Ω
and defined from Dn.
BO iterates the following procedure for n = ninit + 1, ninit + 2, . . . , M, where M is the
total number of function evaluations.
(i) Compute xn+1 ∈ arg maxx∈Ω α(x; Dn),
(ii) Simulate f(xn+1), and augment the data Dn+1 := Dn ∪ {(xn+1, f(xn+1))}.
An estimate of the optimal parameters is then given as the maximizer from the evaluated
inputs x1, . . . , xM:
x
∗ ∈ arg max {f(x) | x ∈ {x1, . . . , xM}}
The acquisition function α(x; Dn) determines the next point xn+1 to evaluate the
objective function f. Note that the computational cost of solving maxx∈Ω α(x; Dn) is
negligible compared to the computational cost of evaluating f(xn+1), as α(x; Dn) can be
evaluated cheaply.
The acquisition function is designed so as to balance the exploitation and exploration.
Exploitation is a strategy to search for in a region near the current maximizer in
x
∗
n
:= arg max{f(x) | x ∈ {x1, . . . , xn}}; exploration is to search for in a region far
from the evaluated points x1, . . . , xn. This exploration-exploitation trade-off is enabled
by the learning and uncertainty quantification of the response surface of f from the data
Dn. This is done by Gaussian process regression, which we will explain next.
B.2. Gaussian process regression
Gaussian process regression (Rasmussen and Williams 2006) is a Bayesian nonparametric method for learning (or approximating) an unknown function f : Ω → R
from its finite observations (data) Dn = {(xi, f(xi))}
n
i=1. Recall that Bayesian inference
in general proceeds as follows: a) define a prior distribution for the quantity of interest, b)
collect observations (data) related to that quantity, and c) update the prior distribution
to the posterior distribution using the observed data, applying Bayes’ rule. In Gaussian
process regression, the quantity of interest is the unknown function f, and a’) one defines
a prior distribution of f as a Gaussian process (or Gaussian random field), b’) collects
data Dn = {(xi, f(xi))}
n
i=1, and c’) updates the prior Gaussian process to the posterior
Gaussian process, applying Bayes’ rule. See Figure 9 for illustrations of Gaussian process
regression.
Intergenerational Risk Sharing in a Defined Contribution Pension System 31
Figure 9: Illustrations of Gaussian process regression, adapted from Kanagawa et al.
(2018, Figure 1). Left: The green curves are 5 sample paths from the prior Gaussian
process (B 2) using the Matérn kernel (B 3) with h = 1. The thick black line is the
prior mean function m(x) = 0. Right: the three points are noise-perturbed observations
(xi, yi)
3
i=1, where yi = f
∗
(xi) + εi with f
∗ being the ground-truth function and εi being
an independent zero-mean Gaussian noise with variance σ
2
:= 0.01. The thick black
curve is the posterior mean function mn(x) in (B 5) and the two thin black curves are
the posterior standard deviation function σn(x) = p
kn(x, x) in (B 7), in which K−1
n
is
replaced by (Kn + σ
2
I)
−1 and fn := (y1, y2, y3)>. (These modifications are theoretically
justified; see e.g. Kanagawa et al. (2018) and references therein for details.) The green
curves are 5 sample paths from the posterior Gaussian process (B 4)
B.2.1. Prior Gaussian Process
A Gaussian process is completely specified by its mean function m : Ω → R and
covariance function k : Ω × Ω. We write f ∼ GP(m, k) to mean that f is a sample path
of the Gaussian process with mean function m and covariance function k. Then we have
m(x) = E[f(x)], x ∈ Ω and k(x, x0) = E[(f(x) − m(x))(f(x
0
) − m(x
0
))], x, x0 ∈ Ω. By
specifying m and k, we implicitly specify the corresponding Gaussian process.
For simplicity, we consider a Gaussian process with the zero-mean function (i.e.,
m(x) = 0, ∀x ∈ Ω) for our prior distribution of the objective function f:
f ∼ GP(0, k). (B 2)
What we need is to specify the covariance function k. By doing so, we can express our
assumption or knowledge regarding key properties of the objective function f, such as
its smoothness and structure.
Popular choices of covariance kernels include square-exponential kernel k(x, x0) =
exp(−kx − x
0k2/h) with h > 0 and Matérn kernels. In our study we use the so-called
Matérn-5/2 kernel of the form
k(x, x0) = 1 +
√
5kx − x
0k
h
+
5kx − x
0k2
3h
2
!
exp −
√
5kx − x
0k
h
!
(B 3)
where h > 0 is a scale parameter.6 Roughly, this kernel leads to f ∼ GP(0, k) that is
almost surely twice differentiable (e.g., Kanagawa et al. 2018, Section 4.4). Thus, with
this kernel we essentially assume this degree of smoothness for the objective function,
and this is our prior assumption.
32 A. Chen, M. Kanagawa and F. Zhang
B.2.2. Posterior Gaussian Process
The use of a Gaussian process as a prior leads to an analytic expression of the resulting
posterior distribution. Given data Dn = {(xi, f(xi))}
n
i=1, the posterior distribution of f
is also given as a Gaussian process
f|Dn ∼ GP(mn, kn), (B 4)
where mn : Ω → R is the posterior mean function and kn : Ω × Ω → R is the posterior
covariance function, given by
mn(x) = E[f(x)|Dn] = f
>
n K−1n kn(x), x ∈ Ω, (B 5)
kn(x, x0) = E[(f(x) − mn(x))(f(x
0
) − mn(x))|Dn]
= k(x, x0) − kn(x)
>K−1
n kn(x
0
), x, x0 ∈ Ω, (B 6)
where fn := (f(x1), . . . , f(xn))>, kn(x) := (k(x, x1), . . . , k(x, xn))> ∈ R
n and Kn :=
(k(xi, xj ))n
i,j=1 ∈ R
n×n. For the detail of the above derivation, see Rasmussen and
Williams (2006).
The posterior mean function mn in (B 5) is an approximation of the objective function
f based on the data Dn. It works as a computationally cheaper surrogate model of f.
On the other hand, the posterior standard deviation
σn(x) := p
kn(x, x) = pE[(f(x) − mn(x))2|Dn] (B 7)
quantifies the uncertainty about the unknown function value f(x). These mn and σn are
the building blocks of the acquisition function, as we will see next.
B.3. Acquisition function
We now introduce the concrete form acquisition function α(x; Dn). There are many
acquisition functions proposed in the literature; see Shahriari et al. (2016, Section IV).
Most popular ones include the EI (Expected Improvement), GP-UCB (Gaussian Process
Upper Confidence Bound), and ES (Entropy Search). In this paper, we use the EI
acquisition function, which is standard and theoretically well studied (Bull 2011). Let
f
∗
n
:= max
i=1,...,n
f(xi), x∗
n ∈ arg max{f(x) | x ∈ {x1, . . . , xn}}.
be the maximum and the maximizer of the objective function f(x) over the currently
evaluated inputs x1, . . . , xn. The EI acquisition function α(x; Dn) at x is defined as the
expected improvement of the function value f(x) over the current maximum f
∗
n
, where
the expectation is with respect to the posterior Gaussian process (B 4):
a(x; Dn) := Ef∼GP(mn,kn)[max(f(x) − f
∗
n
, 0)]
= σn(x)φ

mn(x) − f
∗
n
σn(x)

| {z }
Exploration
+ (mn(x) − f
∗
n
)Φ

mn(x) − f
∗
n
σn(x)

| {z }
Exploitation
, (B 8)
where φ : R → [0, ∞) is the probability density function of a standard Gaussian random
variable, and Φ : R → [0, 1] is its cumulative distribution function: Φ(y) := R y
−∞ φ(s)ds,
y ∈ R.
The first term in (B 8) represents the exploration, as it becomes large when σn(x),
which represents the uncertainty about the function value f(x), is large. This is typically
the case when x is far from already evaluated locations x1, . . . , xn. The second in (B 8)
represents the exploitation, as it becomes large when mn(x) − f
∗
n
is large and σn(x) is
Intergenerational Risk Sharing in a Defined Contribution Pension System 33
Figure 10: Demonstration of Bayesian optimization with γ = 10 (see Section B.4).The
points represent the values of (π, θ) evaluated by Bayesian optimization. The green
points are the initial 10 points given by Latin hypercube sampling. The red point is the
maximizer found by Bayesian optimization after 100 evaluations, and the blue points
(largely overlapping the red point) are the 10 second-best points.
small. This is typically the case when x is near the current maximizer x
∗
n
. Thus, the
EI acquisition function naturally balances the exploration-exploitation trade-off, and the
next point xn+1 ∈ arg maxx∈Ω α(x; Dn) achieves such a balance.
B.4. Demonstration
Figure 10 shows an example of points x = (π, θ) evaluated by BO for γ = 10. The
green points are the ninit = 10 initial design points x1, . . . , xninit generated by Latin
hypercube sampling. The total number of evaluated points is M = 100. The red point is
the maximizer x
∗
M, and the blue points are the 10 other second-best parameters (largely
overlapping with the red point). For a comparison, we show 10 × 10 grid points.
Appendix C. IR-roughness Measure
To describe the IR-roughness measure (Bardet et al. 2011), we suppose that the path
of each individual account is represented by a function h : [0, Te] → R, where Te = 40 is
its terminal time. Note that T˜ is the terminal time for one generation but is different
from the terminal time for the operation of the pension fund T. Discretizing the domain
to n − 1 ∈ N intervals, the first-order IR-roughness is defined as
R
1,n(h) := 1
n − 1
nX−2
j=0



h(Tej+1
n
) − h(Te j
n
) + h(Tej+2
n
) − h(Tej+1
n
)






h(Tej+1
n
) − h(Te j
n
)


 +



h(Tej+2
n
) − h(Tej+1
n
)



. (C 1)
By the triangle inequality, the numerator in the sum is less than or equal to the
denominator, and thus R1,n(h) takes values between 0 and 1. When the signs of the
two increments h(Te(j + 1)/n)−h(T j/n e ) and h(Te(j + 2)/n)−h(Te(j + 1)/n) are the same,
the numerator equals the denominator; when those signs are different, the numerator is
smaller than the denominator. As such, R1,n(h) reflects the sign changes of the function
h and thus quantifies its roughness. Intuitively, R1,n(h) is close to 0 when h is rough, and
34 A. Chen, M. Kanagawa and F. Zhang
is close to 1 when h is smooth. In fact, Bardet et al. (2011) show that, for a sufficiently
smooth h, R1,n(h) converges to 1 as n → ∞.
Appendix D. Supplementary Numerical Results
We show here additional numerical results not included in the main body of the paper.
D.1. Distribution of Retirement Benefits
Figure 11 shows the histograms of the retirement benefits of the IRS-DC and pure DC
plan participants for two settings of the risk aversion, γ = 3, 5; see Section 5.4 for details.
D.2. Welfare of Participants
Figure 12 shows the certainty equivalents of the IRS-DC and pure DC participants for
the generations i = 41, . . . , 80 for two settings of the risk aversion, γ = 3, 5; see Section
5.5 for details.
Appendix E. Additional Numerical Analyses
We report the results of additional numerical experiments on a path-dependent stochastic investment strategy in Appendix E.1 and on the calibration of the population structure
in Appendix E.2.
E.1. Time-varying Investment Strategy
In the main body of the paper, we consider a constant-mixed strategy that invests
a constant fraction π ∈ (0, 1) of its asset in the stock for the IRS-DC fund. Here we
relax this assumption by considering a time-varying investment strategy π(t) ∈ (0, 1)
that continuously changes with time t according to the fund’s investment performance.
Specifically, we consider the funding-ratio-linked investment strategy studied in Goecke
(2013, Eq.(4)). For constants π0 ∈ (0, 1) and a > 0, the fraction π(t) to be invested in
the stock at time t > 0 is defined as
π(t) := π0 +
a
σ
ln 
A(t)
L(t)

, (E 1)
where A(t) and L(t) are the fund’s asset and liability, respectively. We set π(t) = 0 if
π(t) < 0 and π(t) = 1 if π(t) > 1. In this case, the indexation rate g(t) becomes
g(t) := µ(t) + θ ln 
A(t)
L(t)

, where µ(t) := (µ − r)π(t) + r −
1
2
σ
2π(t)2
.
Note that σ(t) := σπ(t) represents the volatility of the fund’s asset.
We optimize the parameters π0, a and θ using Bayesian optimization (where the range
of each parameter is [0,1] and the number of iterations is 100), focusing on the risk
aversion γ = 10 in Market 1 (high Sharpe ratio) and Market 3 (low Sharpe ratio). The
results are:
Market 1: π
∗
0 = 0.2711; a
∗ = 0.0118 θ∗ = 0.9995,
Market 3: π
∗
0 = 0.0304; a
∗ = 0.0669 θ∗ = 0.0001.
Figure 13 describes the mean and standard deviation of π(t) over 10,000 simulations as
a function of t, as well as the corresponding constant mixed strategy π
∗
. It also shows
the paths of π(t) for three representative scenarios defined in the same way as Section
Intergenerational Risk Sharing in a Defined Contribution Pension System 35
(a) Market 1: γ = 3 (b) Market 2: γ = 3
(c) Market 3: γ = 3 (d) Market 1: γ = 5
(e) Market 2: γ = 5 (f