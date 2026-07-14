https://summit.sfu.ca/_flysystem/fedora/2025-05/etd23813.pdf
→ https://summit.sfu.ca/_flysystem/fedora/2025-05/etd23813.pdf
Content-Type: application/pdf

Optimal hurdle rate and investment
policies in lifetime pension pools
by
Yingfei Sun
B.Sc., Zhejiang University of Finance & Economics, 2021
Project Submitted in Partial Fulfillment of the
Requirements for the Degree of
Master of Science
in the
Department of Statistics and Actuarial Science
Faculty of Science
© Yingfei Sun 2025
SIMON FRASER UNIVERSITY
Spring 2025
Copyright in this work is held by the author. Please ensure that any reproduction
or re-use is done in accordance with the relevant national copyright legislation.
Declaration of committee
Name: Yingfei Sun
Degree: Master of Science
Thesis title: Optimal hurdle rate and investment policies in
lifetime pension pools
Committee: Chair: Cherie Ng
Lecturer, Statistics and Actuarial Science
Jean-François Bégin
Co-supervisor
Associate Professor, Statistics and Actuarial Science
Barbara Sanders
Co-supervisor
Associate Professor, Statistics and Actuarial Science
Himchan Jeong
Committee Member
Assistant Professor, Statistics and Actuarial Science
Yi Lu
Examiner
Professor, Statistics and Actuarial Science
ii
Abstract
Lifetime pension pools provide retirees with lifelong income by pooling mortality risk and
adjusting benefits based on investment performance and mortality within the pool. Their
benefit structure depends on two design elements: the investment policy and the hurdle rate.
Existing research on asset allocation in these pools is limited, with most studies relying
on simplistic investment strategies. Moreover, the optimal hurdle rate has been largely
overlooked. This study addresses both gaps by simultaneously exploring the optimal hurdle
rate and investment strategies, employing dynamic programming to account for varying
levels of risk aversion. Our results show that the investment policy adjusts dynamically in
response to the pool’s assets and the number of survivors. Higher risk aversion leads to more
conservative allocations and lower hurdle rates, whereas lower risk aversion results in riskier
allocations and higher hurdle rates. Robustness tests confirm these findings across varying
pool sizes, financial conditions, mortality assumptions, and subjective discount rates.
Keywords: lifetime pension pool; hurdle rate; investment policy; dynamic programming.
iii
Acknowledgements
First and foremost, I would like to express my deepest gratitude to my supervisors, Professor
Jean-François Bégin and Professor Barbara Sanders. JF gave me this invaluable opportunity
to study at Simon Fraser University. I still remember the day he interviewed me and the
excitement I felt when I received the offer. Throughout my time at SFU, he has been
a constant source of support, patience, and encouragement. From reading the literature,
designing and coding the models, writing the thesis, to preparing for the final defense, he
has guided me with great dedication. I am truly grateful for his mentorship and unwavering
help whenever I needed it.
I am also sincerely thankful to Barbara, my co-supervisor. Her insights and professional
expertise, particularly in the analysis and interpretation of pension-related results, were
incredibly valuable. I have learned a great deal from her thoughtful feedback and her deep
understanding of the pension field.
I would also like to thank my examining committee members, Dr. Yi Lu and Dr. Himchan
Jeong, for their valuable time, helpful comments, and suggestions that greatly improved my
work. Additionally, I am grateful to Professor Richard Lockhart, Professor Boxin Tang,
and Professor Liangliang Wang, as well as JF, Barbara, and Dr. Lu, for delivering excellent courses that greatly enriched my statistical and actuarial training as well as academic
foundation during my studies.
My heartfelt thanks also go to my peers and friends in the department. Their kindness
and expertise greatly helped me during my transition into actuarial science. Beyond the
department, I am deeply thankful for the support from my friends in Vancouver, Toronto,
and China. Their encouragement and companionship made my graduate journey at SFU
both memorable and fulfilling. I am grateful for all the wonderful memories I made here.
Finally, and most importantly, I would like to thank my family. Their unconditional
love, understanding, and support have been the foundation that allowed me to pursue and
complete my studies.
Hope we can meet each other soon.
iv
Table of contents
Declaration of committee ii
Abstract iii
Acknowledgements iv
Table of contents v
List of tables vii
List of figures viii
1 Introduction 1
2 The assumed data generating process 6
2.1 The financial market . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 6
2.2 The mortality model . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 7
3 Lifetime pension pool designs 9
3.1 Asset value dynamics . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 9
3.2 Change in benefits . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 10
4 Optimal hurdle rate and investment policy 12
4.1 Optimization process . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 12
4.1.1 Problem statement . . . . . . . . . . . . . . . . . . . . . . . . . . . . 12
4.1.2 Utility function definition . . . . . . . . . . . . . . . . . . . . . . . . 13
4.1.3 Solving for the optimal investment policy . . . . . . . . . . . . . . . 15
4.1.4 Solving for the optimal hurdle rate . . . . . . . . . . . . . . . . . . . 18
4.2 Numerical implementation . . . . . . . . . . . . . . . . . . . . . . . . . . . . 20
5 Base case results 22
5.1 Model setting . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 22
5.2 Results for base cases . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 23
5.2.1 Optimal investment policy surfaces . . . . . . . . . . . . . . . . . . . 23
v
5.2.2 Optimal hurdle rate results . . . . . . . . . . . . . . . . . . . . . . . 26
5.2.3 Evolution of key variables over time . . . . . . . . . . . . . . . . . . 30
6 Robustness tests 34
6.1 Changes in the pool size . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 34
6.1.1 Scenarios . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 34
6.1.2 Optimal hurdle rate . . . . . . . . . . . . . . . . . . . . . . . . . . . 34
6.1.3 Mortality experience adjustment . . . . . . . . . . . . . . . . . . . . 35
6.1.4 Benefit levels . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 36
6.2 Changes in the financial market parameters . . . . . . . . . . . . . . . . . . 37
6.2.1 Scenarios . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 37
6.2.2 Optimal hurdle rate . . . . . . . . . . . . . . . . . . . . . . . . . . . 38
6.2.3 Investment experience adjustment . . . . . . . . . . . . . . . . . . . 40
6.2.4 Investment policies and benefit levels . . . . . . . . . . . . . . . . . . 41
6.3 Changes in the mortality parameters . . . . . . . . . . . . . . . . . . . . . . 42
6.3.1 Scenarios . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 42
6.3.2 Optimal hurdle rate . . . . . . . . . . . . . . . . . . . . . . . . . . . 43
6.3.3 Mortality experience adjustment . . . . . . . . . . . . . . . . . . . . 44
6.3.4 Benefit levels . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 45
6.4 Changes in the utility discount rate . . . . . . . . . . . . . . . . . . . . . . . 47
6.4.1 Scenarios . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 47
6.4.2 Optimal hurdle rate . . . . . . . . . . . . . . . . . . . . . . . . . . . 47
6.4.3 Benefit levels . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 48
7 Concluding remarks and future research 50
Bibliography 52
vi
List of tables
Table 5.1 Parameter settings for base case analysis . . . . . . . . . . . . . . . . 23
Table 5.2 Optimal hurdle rate and key metrics for base cases . . . . . . . . . . . 27
Table 6.1 Average investment experience adjustment across cases and scenarios 40
vii
List of figures
Figure 4.1 Relative risk aversion as a function of the benefit level for different
baseline parameter values c with γ = −2 . . . . . . . . . . . . . . . 15
Figure 5.1 Optimal risky asset allocation at time 20 as a function of total asset
value and number of members for c = 0 . . . . . . . . . . . . . . . . 24
Figure 5.2 Optimal risky asset allocation at time 20 as a function of total asset
value and number of members for c = 500 . . . . . . . . . . . . . . 25
Figure 5.3 Optimal risky asset allocation at time 20 as a function of total asset
value and number of members for c = −500 . . . . . . . . . . . . . 26
Figure 5.4 Variance of benefits per member over time . . . . . . . . . . . . . . 28
Figure 5.5 Optimal hurdle rate for c across different γ . . . . . . . . . . . . . . 29
Figure 5.6 Optimal hurdle rate for γ across different c . . . . . . . . . . . . . . 29
Figure 5.7 Evolution of the total asset value for the nine base cases . . . . . . 30
Figure 5.8 Variance of total asset value across time . . . . . . . . . . . . . . . 31
Figure 5.9 Evolution of the benefit per member for the nine base cases . . . . 32
Figure 5.10 Evolution of risky asset allocation for the nine base cases . . . . . . 33
Figure 6.1 Optimal hurdle rate for different pool sizes . . . . . . . . . . . . . . 35
Figure 6.2 Average mortality experience adjustment for different pool sizes . . 36
Figure 6.3 Average benefit levels over time for different pool sizes . . . . . . . 37
Figure 6.4 Variance of benefit levels over time for different pool sizes . . . . . 38
Figure 6.5 Optimal hurdle rate under different market conditions . . . . . . . 39
Figure 6.6 Average benefit levels over time for different financial market scenarios 41
Figure 6.7 Asset allocation for different financial market scenarios . . . . . . . 43
Figure 6.8 Optimal hurdle rate for different mortality parameters . . . . . . . 44
Figure 6.9 Mortality experience adjustment for different mortality parameters 45
Figure 6.10 Average benefit levels for different mortality parameter settings . . 46
Figure 6.11 Optimal hurdle rate for different utility discount rates . . . . . . . . 47
Figure 6.12 Average benefit levels for different utility discount rates . . . . . . . 49
viii
Chapter 1
Introduction
Demographic and economic changes have reshaped the landscape of retirement planning
in recent decades, particularly as members live longer and traditional pension structures
face sustainability challenges. Historically, two main designs have dominated retirement
planning: defined benefit (DB) and defined contribution (DC) pension plans. DB plans
promise a predetermined retirement income based on factors such as salary and years of
service, offering members a stable and predictable income in retirement. However, these
plans have become increasingly difficult to sustain due to rising life expectancy, changing
workforce demographics, and economic pressures such as low-interest rates and market
volatility.
On the other hand, DC plans, which shift the investment risk onto the individual, have
become more prevalent in recent years. These plans are funded by contributions from both
employers and employees, with the retirement benefits depending on investment performance and the individual’s own longevity. While they provide greater flexibility, they also
introduce uncertainty, as retirees bear the risk of market fluctuations and may face challenges in managing their retirement savings, especially as they tend to outlive their assets.
Accordingly, the Organization for Economic Cooperation and Development (OECD)
released a series of recommendations for the good design of DC plans in 2022; one of the
recommendations is to ensure protection against longevity risk in retirement, and several
modern pension designs—like lifetime pension pools—certainly address this suggestion.1
Lifetime pension pools allow retiring individuals to convert a lump sum into income for
life. The pool does not guarantee a specific level of income; instead, the pension payable
varies with the investment and mortality experience of the group. Members, therefore,
collectively share mortality risk, ensuring lifelong income. Unlike DB plans, which offer
guaranteed benefits, lifetime pension pools adjust payouts over time based on investment
1
“DC pension plans should provide some level of lifetime income as a default for the payout phase unless
other pension arrangements already provide for sufficient lifetime pension payments. Lifetime income can be
provided by annuities with guaranteed payments or by non-guaranteed arrangements where longevity risk
is pooled among participants.” (OECD, 2022)
1
performance and the collective longevity experience of the pool. This shared-risk model
provides a middle ground between DB and DC plans, potentially yielding greater retirement
security than DC plans while avoiding the costly guarantees of DB plans. By eliminating
the need for risk capital, lifetime pension pools can deliver higher payouts than individual
withdrawal strategies or retail annuities. However, this flexibility comes with a trade-off—
benefit risk remains with participants, making payout stability a key challenge.
Various arrangements and products fit the broad description of lifetime pension pools in
the literature: group self-annuitization plans (Piggott et al., 2005; Valdez et al., 2006; Qiao
and Sherris, 2013; Hanewald et al., 2013), pooled annuity funds (Stamos, 2008; Donnelly
et al., 2013), annuity overlay funds (Donnelly et al., 2014; Donnelly, 2015), retirement
tontines (Milevsky and Salisbury, 2015, 2016; Fullmer, 2019; Iwry et al., 2020; Chen et al.,
2021), variable annuities (Balter and Werker, 2020; Balter et al., 2020), and variable payout
annuities (Horneff et al., 2010). Note that all these designs can be viewed as implicit or
explicit tontines.2
Operators managing lifetime pension pools face numerous critical decisions that directly
impact the performance and benefit stability of the pool. One of the most significant decisions is the selection of the asset allocation, which can dramatically alter the risk–return
profile of the pool. Additionally, a key assumption in determining the payout is the choice of
the assumed interest rate—commonly referred to as the hurdle rate—which plays a crucial
role in calculating the initial benefits and their adjustments over time. Changes in this rate
can substantially influence the benefit trajectory, affecting both the level of payouts received
by participants and the pool’s ability to manage assets effectively over the long term. This
report seeks to explore the optimal hurdle rate and investment strategies for lifetime pension
pools, employing dynamic programming to account for changing circumstances.
Traditionally, the hurdle rate in lifetime pension pools is set as a fixed value, often
determined based on long-term expected investment returns or standardized discount assumptions. An appropriately chosen hurdle rate is nonetheless crucial: if set too high, current
payouts may be overly generous, risking depletion if actual returns underperform; if set too
low, early consumption will be overly restrained, causing later payouts to increase sharply,
which may not align with members’ consumption needs over their lifetimes. In short, hurdle
rate calibration is pivotal in balancing immediate adequacy with long-term welfare.
Recent studies further illustrated this balance. The OECD (2022) stressed the role of
the hurdle rate in ensuring intergenerational fairness and plan stability. Meanwhile, it also
discussed that hurdle rates can be fixed, based on an external benchmark, or dynamically
adjusted according to market performance. Bégin and Sanders (2024) used a constant hurdle
2
Implicit tontines promise to pay the participants an income for life, but longevity credits are not explicitly
allocated to the participants; explicit tontines explicitly allocate longevity credits to the individual accounts
of participants (see Bernhardt and Donnelly, 2019, for more details).
2
rate aligned with the fund’s expected return, yielding level benefits in expectation but risking
a downward trend if markets fail to meet that target.
Alongside the hurdle rate, lifetime pension pools require a coherent investment policy
that manages how assets are allocated over time. Unlike a conventional DC plan, where participants individually select investments, lifetime pension pools typically invest collectively.
The pool operator must decide what proportion of assets to hold in risky instruments, such
as equities, and in safer assets, such as bonds. Notice, however, that the optimal investment
decisions interact with the hurdle rate: higher or lower expected returns influence how effectively the plan can meet or exceed the benchmark, affecting the subsequent changes to
the benefit payouts. Therefore, these two decisions must be made in tandem.
To address these interconnected decisions—investment allocations and hurdle rate in
our context—we rely on a combination of dynamic and static optimization. Dynamic optimization partitions complex, multi-period problems into stage-wise decisions, each reflecting
newly realized returns or membership changes. In contrast, static optimization focuses on
determining fixed parameters or rules at inception. In our study, the optimization problem
can be split into two stages. For asset allocation, we adopt a dynamic framework to adjust policies over time (the so-called inner optimization problem in our setting). For the
hurdle rate, which remains fixed across time, we solve an outer problem to find the value
that maximizes the expected utility while assuming optimality for the asset allocation. This
combination of fixed hurdle rate and dynamically adjusted asset allocation reflects common
practice in real-world pension plans.
The literature on dynamic optimization, based mainly on dynamic programming, is
well established in the retirement literature. In the DB context, where benefits are prespecified, the main objective is to manage funding risks. The foundational dynamic methods have been developed by many authors, including Haberman and Sung (1994), Chang
(1999), Taylor (2002), Chang et al. (2003), and Haberman and Sung (2005), who examined
optimal contribution strategies that minimize solvency and contribution risks in various
stochastic settings. A related body of work by Josa-Fombellida and Rincón-Zapatero (2001,
2004, 2010) developed stochastic control frameworks aimed at reducing funding volatility,
with further extensions incorporating the utility of terminal surplus in Josa-Fombellida
and Rincón-Zapatero (2008) and Josa-Fombellida et al. (2018). These models typically relied on quadratic or exponential loss functions and emphasized maintaining solvency under
uncertainty.
In DC and other hybrid contexts, such as collective DC (CDC) schemes and target benefit plans (TBPs), the focus of optimization typically moves to utility-based frameworks.
These approaches aimed to strike a balance between maximizing participant welfare and
maintaining long-term fund discipline. For example, Battocchio et al. (2007) analyzed asset
allocation under a constant relative risk aversion (CRRA) utility framework, optimizing
the surplus of a pension fund while accounting for mortality risk. Cui et al. (2011) applied
3
dynamic optimization to an individual DC benchmark using the endogenous gridpoint technique from Carroll (2006). Wang et al. (2018) proposed a continuous-time stochastic control
model for Canadian TBPs, jointly optimizing investment and benefit policies for loss-averse
participants. Zhao and Wang (2022) adopted Cobb–Douglas and Epstein–Zin recursive utilities to better capture intertemporal preferences when optimizing benefit and investment
policies in a TBP context. Baltas et al. (2022) extended the traditional DC model by
incorporating mortality, inflation-linked bonds, and model uncertainty, optimizing under
exponential utility. Finally, Josa-Fombellida and López-Casado (2025) explicitly modelled
dynamic benefit and investment paths in a TBP, maximizing the expected discounted utility of both income and terminal wealth. Collectively, these studies demonstrated that in
more flexible pension arrangements, utility maximization provides an alternative objective
to minimizing risks alone.
For simplicity, several studies employ static optimization to design adjustment rules
or policy parameters that are fixed at inception. For example, Cui et al. (2011) evaluated the welfare impact of intergenerational transfers using fixed risk allocation rules under
value-based generational accounting for CDC schemes. De Jong (2008) and Molenaar and
Ponds (2012) explored fixed policy structures within collective pension arrangements, analyzing outcomes under predetermined asset mixes and funding rules. Bégin (2020) calibrated
volatility-adjusted parameters for benefit smoothing in collective pension plans. Chen et al.
(2023) optimized investment strategy and adjustment strength using expected utility maximization with Bayesian methods. In our context, this literature aligns with our treatment
of the hurdle rate as a fixed policy parameter that must be carefully selected at the outset.
The main objective of this study is to apply a combination of dynamic programming
and static optimization approaches to analyze how lifetime pension pools can effectively
manage two pivotal factors: the hurdle rate, which governs benefit adjustments, and the
investment policy, which determines asset allocation. Specifically, we address the following
questions:
(i) How should the hurdle rate be calibrated to balance immediate benefit adequacy with
the long-term management of pension assets?
(ii) Which investment strategies are optimal given varying risk aversion, market environments, and member demographics?
(iii) How do these policy decisions influence participants’ expected utility and the pension
pool’s ability to deliver stable, lifelong income?
We address these questions by modelling financial returns, mortality risk, and members’
utility within a dynamic framework that integrates the hurdle rate and the asset allocation.
Using the hyperbolic absolute risk aversion (HARA) utility, we capture varying levels of
risk aversion to evaluate how the hurdle rate and investment strategies influence both short4
term payouts and long-term fund sustainability. By maximizing expected utility, we provide
insights into optimizing policy choices under diverse economic and demographic scenarios.
Our results indicate that optimal hurdle rates and investment strategies depend significantly on the pool’s risk preferences, longevity expectations, and financial market conditions. In general, higher risk aversion leads to a more conservative benefit adjustment
strategy, with lower hurdle rates and reduced allocations to risky assets. Conversely, in lowrisk-aversion scenarios, the fund adopts a more aggressive stance, targeting higher hurdle
rates and allocating a greater proportion of assets to equities. Notably, financial market
dynamics play a critical role in shaping investment decisions, while changes in pool size,
mortality assumptions, and subjective discount rates primarily influence benefit trajectory
without altering asset allocation. Our numerical results illustrate how different hurdle rate
calibrations impact long-term fund stability, highlighting the trade-offs between immediate
and future benefits.
This report is organized as follows. Chapter 2 introduces the data generating process,
modelling investment returns with a lognormal distribution and mortality rates with the
Gompertz law. Chapter 3 describes the lifetime pension pool framework, explaining asset
dynamics and benefit adjustments. In Chapter 4, we present the optimization methodology,
detailing the problem formulation, utility function specification, and the solutions for the
optimal investment policy and hurdle rate using dynamic programming. Chapter 5 summarizes the base case results, analyzing how variations in risk aversion parameters influence
pension outcomes. Chapter 6 examines the robustness of these results under different pool
sizes, market conditions, mortality assumptions, and utility discount rates. Concluding remarks and potential extensions are provided in Chapter 7.
5
Chapter 2
The assumed data generating
process
This chapter discusses the data generating process (DGP) used to generate future scenarios,
which is composed of two components: one for investment returns and the evolution of an
investment portfolio, and the other for projecting the number of survivors by modelling
mortality rate for members in the lifetime pension pool. In this report, we assume that
investment returns in the risky asset are lognormally distributed and that the mortality
obeys the Gompertz law.
2.1 The financial market
Financial asset prices are important puzzle pieces for grasping investment risk in lifetime
pension pools. In the real world, all financial assets carry some degree of risk. For simplicity’s
sake, we assume that the pension pool can invest in two types of assets: a risk-free asset and
a risky asset. The former asset is characterized by a constant rate of return, and the latter
asset is modelled using a lognormal model, which is a discrete-time version of the model
used by Black and Scholes (1973) and Merton (1973).
We consider a discrete-time economy on the time span T = {0, 1, ..., T}. The uncertainty
is modelled with the probability space (Ω, F, P) endowed with the filtration F = {Ft}t∈T ,
where P represents the physical measure. The risk-free asset, denoted by P = {Pt}t∈T , is
given by the following equation:
Pt+1 = Pt exp (r), (2.1)
where r represents the constant (annualized) risk-free rate. We also assume that P0 = 1 for
convenience and without loss of generality. The risk-free asset provides a guaranteed return
over time without any uncertainty in this report. Due to the low probability of default, debt
obligations issued by the US or any nation with high credit ratings, like bonds, notes, and
Treasury bills, can be considered risk-free assets.
6
Due to market volatility, risky assets are subject to uncertainty and price fluctuations.
Stocks, commodities, real estate, and foreign exchange are typical classes of risky assets. In
this report, we model the risky asset using a lognormal distribution, and the continuously
compounded returns (returns hereafter) are to be normally distributed.
The reasons for using the lognormal distribution can be explained from both historical
and practical perspectives. Historically, following the Black–Scholes–Merton framework, asset prices are modelled using geometric Brownian motion, which implies that the logarithm
of returns is normally distributed. Practically, the lognormal distribution accurately represents the non-negative nature of asset prices, and the normality of the returns simplifies
mathematical modelling. This report presents another reason for choosing the lognormal
distribution: because returns are normally distributed, we can apply fast Gauss–Hermite
quadrature to approximate expectations involving the risky asset.
We denote the risky asset price process by S = {St}t∈T , and the continuously compounded return from time t to t + 1 is defined as log 
St+1
St

. The dynamics of this asset are
given by the following equation:
St+1 = St exp µ −
σ
2
2
!
+ σ εt+1!, (2.2)
where ε = {εt}t∈T ∗ is a collection of standard normal random variables and T
∗ = T \T is a
set of time indices that excludes the last time step. Due to the lognormality assumption of
the risky asset price, we can show that
log 
St+1
St

∼ N µ −
σ
2
2
, σ2
!
,
where µ is the expected return of the asset, σ is the volatility of the asset’s returns, and
−σ
2/2 is an adjustment term to ensure that the parameter µ represents the actual expected
return of the asset so that Et[St+1] = E[St+1|Ft] = Ste
µ
.
2.2 The mortality model
Mortality risk poses a significant challenge to lifetime pension pools and needs to be modelled. To simulate the number of survivors in the lifetime pension pool at year t, we need to
develop a survival probability curve. In this report, the mortality follows a Gompertz law
of mortality similar to that used in Chapter 2 of Milevsky (2022).
The Gompertz law of mortality was proposed by British mathematician Benjamin Gompertz in 1825 and provided a foundational understanding of the aging process and population mortality dynamics. The main idea of this model is that the natural logarithm of adult
mortality hazard rates (also called the force of mortality in actuarial science) is linear. In
other words, after reaching adulthood, an individual’s risk of death increases exponentially
7
with age. Specifically, the force of mortality for a member aged x is given by
µx =
1
b
e
x−m
b ,
where m represents the modal value (in years) of the future lifetime distribution, and b
represents the dispersion (in years) coefficient. Note that the modal value m is different
from (and actually higher than) the mean lifetime—it is the age at which an individual is
the most likely to die.
Under this modelling framework, we can show that the probability of surviving t years
for a member aged x is
tpx = exp 
e
x−m
b

1 − e
t
b
 ;
see Bowers et al. (1997) for more details.
We further assume that the limiting—ultimate—age is set to ω = 121, which should be
biologically consistent with empirical observations. In other words, we assume that no one
can reach 121 years old, or
ω−xpx = 0 for all x ∈ {0, ..., 120}.
This also means that the last possible payment is received at age 120.
Once survival probabilities are obtained from the Gompertz law of mortality, we can use
them to generate pool members’ survival and death in the context of our DGP. Specifically,
we model idiosyncratic mortality risk via Bernoulli random variables as typically done in
the literature. For an individual aged x and still alive, we assume that they survive until
time t with probability tpx and die with probability 1 − tpx.
In our framework, another important quantity related to mortality is the price of a unit
annuity due. This is a type of annuity where payments of one are made at the beginning
of each period. The value of the annuity due captures both the discounted value of future
cash flows and the probability of survival for each period, which reflects the mortality risk.
Using typical actuarial notation, let a¨x,h denote the actuarial present value of an annuity
due with annual payments of one unit for a member aged x, such that
a¨x,h =
X∞
t=0
tpx e
−h t
, (2.3)
where h is the (continuously compounded) hurdle rate assumed to compute the annuity
price.
8
Chapter 3
Lifetime pension pool designs
This chapter describes the stylized design of the lifetime pension pool proposed in this study
and discusses the dynamics of the future assets and benefit adjustments by incorporating
the investment returns and mortality scenarios. The scheme ensures that the total assets
align with the present value of future liabilities at each time step and that the benefit
dynamics distribute experience gains and losses among the surviving members, reflecting
the shared nature of the risks involved.
3.1 Asset value dynamics
We select a simple structure for the dynamics of our lifetime pension pool. The operation
of the scheme shares similarities with the designs proposed in Piggott et al. (2005) and
Qiao and Sherris (2013) in the context of group self-annuitization plans as well as with
pooled annuity funds (Stamos, 2008; Donnelly et al., 2013) and variable annuities (Balter
and Werker, 2020; Balter et al., 2020).
We use Lt to represent the set of survivors at time t; that is, k ∈ Ltif the k
th member
is alive at the beginning of year t. Moreover, the scheme’s number of members at time t is
denoted by Lt = card(Lt). Since we assume no new entrants to the pool, the membership
can only decrease due to mortality. We further assume that every member has the same age
x at inception and that the scheme pays benefits at the beginning of each year.
Based on the assumptions mentioned above, we have that each surviving member k has
an investment (entitlement) amount at time t given by
a
(k)
t = b
(k)
t a¨x+t,h,
where h is the hurdle rate assumed throughout the period and b
(k)
t
is the k
th member’s
benefit at time t, t ∈ T ∗ and T = ω − x. Since all members are of the same age and receive
the same benefit (due to the homogeneous nature of the pool and the lack of new entrants),
we can simplify the notation by using at and bt to replace a
(k)
t
and b
(k)
t
for all k ∈ Lt.
9
The total asset value at time t—before benefits are dispersed—is given by
At = Lt at = Lt bt a¨x+t,h.
After paying the benefits at the beginning of the year, the remaining assets are invested
until the next period. The asset value at time t + 1, just before the payment of benefits at
that time, is
At+1 = (At − Lt bt) exp r
PF
t+1
= Lt bt (¨ax+t,h − 1) exp r
PF
t+1
, (3.1)
where r
PF
t+1 is the continuously compounded rate of return on the asset portfolio during the
period t to t + 1. Equation (3.1) can be further simplified by using a well-known recursion
identity for annuity due prices:
a¨x+t,h = 1 + px+t e
−h
a¨x+t+1,h,
where px+tis the probability that an individual aged x+t survives to age x+t+1. Applying
this recursion to a¨x+t,h in Equation (3.1), we have
At+1 = Lt bt a¨x+t+1,h px+t exp r
PF
t+1 − h

.
According to Section 2.1, we assume that the pool can invest in the two assets introduced
above—the risky asset S and the risk-free asset P. The allocation can be changed through
time; specifically, a proportion ϕtis invested in the risky asset and 1 − ϕtin the risk-free
asset at time t until time t+ 1, meaning that the fund dynamics can be described as follows:
r
PF
t+1 = log 
ϕt
St+1
St
+ (1 − ϕt)
Pt+1
Pt

.
3.2 Change in benefits
Based on the new asset value At+1, the future benefits need to be adjusted. Following the
current literature on non-guaranteed schemes, we update the benefit per member at time
t + 1 according to the following rule:
bt+1 = αt+1 bt,
where αt+1 is an adjustment factor informed by the members’ experience, including both
mortality and investment performance.
10
To derive αt+1, we set the total asset value at time t + 1 equal to the total liability (the
present value of future benefits) at that time:
At+1 = Lt+1 bt+1 a¨x+t+1,h,
leading to
bt+1 =
 
At+1
Lt+1 bt a¨x+t+1,h !
bt
=


Lt bt a¨x+t+1,h px+t exp r
PF
t+1 − h

Lt+1 bt a¨x+t+1,h

 bt
=
αt+1
z }| {
Lt px+t
Lt+1 
| {z }
MEAt+1
exp r
PF
t+1 − h

| {z }
IEAt+1
bt, (3.2)
where the adjustment factor αt+1 has two components: MEAt+1 is related to the mortality
experience adjustment and IEAt+1 is associated with the investment experience adjustment.
The former component adjusts for the difference between the expected number of survivors and the actual number. If the actual number of survivors Lt+1 is less than the expected
number Lt px+t, then MEAt+1 > 1, leading to an increase in benefits per surviving member;
if more members survive than expected, MEAt+1 < 1, reducing the benefits per member to
maintain the financial balance of the pool.
The latter component adjusts for the actual investment performance relative to the
hurdle rate h. If the actual return r
PF
t+1 exceeds the hurdle rate, IEAt+1 > 1, leading to
higher benefits; if the investment return is below the hurdle rate, IEAt+1 < 1, resulting
in lower benefits. This adjustment scheme ensures that the balance of the pool remains
self-sustaining by adjusting benefits to reflect the real-time performance of both mortality
and investment experiences.
11
Chapter 4
Optimal hurdle rate and
investment policy
This chapter explains how to find optimal values for the hurdle rate h and the proportion
invested in the risky asset ϕt for each t ∈ T ∗.
4.1 Optimization process
4.1.1 Problem statement
The proportion invested in the risky asset ϕt can be adjusted from time to time—every year
in this study—and the hurdle rate h remains constant during the whole period as described
in Chapter 3. To find optimal values for these two quantities, we consider an expected utility
objective for the entire pension pool:
max
h∈[h, h]

 max
ϕ∈[0, 1]T
E0


X
T
t=0
e
−δ t X
k∈Lt
U

b
(k)
t




 , (4.1)
where ϕ = {ϕt}
T −1
t=0 with 0 ≤ ϕt ≤ 1, h is predetermined hurdle rate with h ≤ h ≤ h,
δ is the subjective discount rate, and T is the horizon set to the maximum possible age
assumed in Chapter 2 minus the members’ age at inception.1 Moreover, U(·) is the utility
function which can be chosen according to the needs of the pool designer and members.
Consistent with the previous section, we assume that every member in the pool has the
same risk preference, characterized by the same utility function parameters, and has the
same benefit payment; that is, b
(k)
t = bt for all k ∈ Lt
. Therefore, the expected utility value
1We restrict the hurdle rate to realistic values between h and h; these bounds could be set by the regulator,
for instance.
12
for the pension pool is
max
h∈[h, h]
"
max
ϕ∈[0, 1]T
E0
"X
T
t=0
e
−δ t U (bt) Lt
## . (4.2)
as Lt = card(Lt). The objective of this problem is to maximize the expected discounted
utility of the pension pool members by optimizing the investment policy ϕ and the hurdle
rate h; that is, find the policy that yields the highest level of satisfaction, considering the
associated risks over the investment horizon. This formulation allows us to aggregate the
utility across all surviving members at each time period, weighted by their survival and
discounted to present value using the subjective discount rate δ.
The problem of Equations (4.1) and (4.2) is broken down into two stages: an inner
maximization in which the optimal investment policy is determined for each time t, and an
outer problem that finds the optimal hurdle rate h maximizing the expected utility.
4.1.2 Utility function definition
Utility functions represent the preferences of individuals or groups over a set of goods
or outcomes. In the context of pension fund management, utility functions quantify how
members value different levels of wealth or consumption, balancing the trade-off between
risk and return.
Selecting an appropriate utility function to derive the optimal investment policy and
hurdle rate for the lifetime pension pool is crucial, as it captures the risk preferences and
satisfaction levels of the pool’s members regarding different financial outcomes.
We choose the HARA utility function in this study, similar to that used in Chapter 1
of Ingersoll (1987). The HARA class of utility functions encompasses various risk aversion
behaviours by suitable adjustments of its parameters. The HARA utility function is defined
as
U(b) = 1 − γ
γ

a b
1 − γ
+ c
γ
, (4.3)
where γ is the risk aversion parameter such that γ ̸= 1, a is a positive scaling parameter,
and c adjusts for the potential for changing relative risk aversion in the utility function.
This utility is defined over the domain a b
(1−γ) + c > 0.
2
The absolute risk aversion (ARA) function of the HARA utility is
ARA(b) = −
U
′′(b)
U′(b)
= a

a b
1 − γ
+ c
−1
,
2We assume that the utility of consumption for values of benefit b lower than −
c(1−γ)
a when γ < 1 is
given by 1−γ
γ
ϵ
γ
, where ϵ > 0 is a small constant that is close to zero.
13
and the relative risk aversion (RRA) is
RRA(b) = ARA(b) b = a b 
a b
1 − γ
+ c
−1
.
When γ < 1 and finite, the individual is risk-averse with decreasing absolute risk aversion.
This means that as the benefit b increases, the individual becomes less risk-averse. When
γ > 1 and finite, on the other hand, the individual has increasing absolute risk aversion,
willing to take more risk as the benefit level decreases. When γ tends to positive or negative
infinity, the individual has constant absolute risk aversion. In the context of the lifetime
pension pool, we focus on cases where γ < 1 and finite, which reflects a decreasing absolute
risk aversion.
The scaling parameter a affects the sensitivity of utility to changes in benefits. It must
be positive to ensure an increasing utility with a rising level of benefit.
The adjustment parameter c acts as a benefit threshold or baseline level influencing
the RRA. It can be positive, negative, or zero. Under the condition that γ < 1, the term
a b
(1−γ) + c significantly influences how risk aversion changes with the benefit level b. Indeed,
parameter c determines how the RRA is impacted.
Figure 4.1 shows how RRA varies with benefit level b for different c values, keeping
γ = −2 fixed. The key takeaways from the figure are:
• When c > 0, we have that a b
(1−γ) + c remains positive for all levels of benefits. As b
increases, the RRA rises. Eventually, as b becomes very large, RRA tends to approach
the constant level 1 − γ.
• When c = 0, we have that a b
(1−γ)
directly shapes both ARA and RRA. The RRA stays
constant at 1 − γ for all values of b. This case is also reminiscent of the well-known
CRRA utility function. Indeed, CRRA utility is a special case within the HARA class,
widely used due to its simplicity. It assumes that the relative risk aversion is constant
and depends solely on the parameter 1 − γ.
3
• When c < 0, there exists a critical threshold where a b
(1−γ) + c = 0. For benefit levels
near this threshold, RRA can become very high, making the pool extremely riskaverse to avoid falling below the critical benefit level. As the benefit level b grows,
RRA decreases toward its long-run limit of 1 − γ.
3Under CRRA, the proportion of benefit an individual is willing to risk remains the same regardless of
benefit level. In contrast, the HARA utility function allows for both absolute and relative risk aversion to
change with the benefit, offering more flexibility in modelling diverse risk preferences.
14
0
2
4
6
0e+00 1e+05 2e+05 3e+05
Benefit level
Relative risk aversion
c = −500 c = 0 c = 500
Figure 4.1: Relative risk aversion as a function of the benefit level for different
baseline parameter values c with γ = −2.
Notes: This figure illustrates the effect of different baseline parameter values c on the relative risk aversion.
The solid lines represent the RRA values for each c, while variations across benefit levels are observed. The
color scheme distinguishes different c values, with c = −500 (blue), c = 0 (grey), and c = 500 (pink).
4.1.3 Solving for the optimal investment policy
We seek to solve the inner optimization problem from Equation (4.2) via dynamic programming to determine the optimal investment policy ϕt at each time t. Dynamic programming
breaks down a complex optimization problem into a series of simpler subproblems, solving
each one optimally from the last to the first period and aggregating the results to find the
overall optimal solution. This approach is similar to the methodology used in Carroll (2006)
and in Appendix A of Cui et al. (2011).
At time t, let Ut(At, Lt, ϕt) denote the expected discounted sum of future utilities from
t through T, conditioning the maximum solution from t + 1 to T, given the current states
At and Lt and an immediate choice ϕt. Specifically,
Ut(At, Lt, ϕt) = U (bt) Lt + max
ϕt+1∈[0,1]
h
e
−δ Et
[Ut+1(At+1, Lt+1, ϕt+1)]i, (4.4)
15
where U (bt) Lt
is the utility of the benefits received at time t, and the last term captures
optimal decision from time t + 1 onward. Hence, Ut measures the expected utility from t to
T if we fix ϕt now and then continue optimally in future periods.
To identify the optimal choice of ϕt at each state At and Lt, we introduce the value
function
Vt(At, Lt) = max
ϕt∈[0,1]
Ut(At, Lt, ϕt). (4.5)
Thus, Vtis the maximum possible expected discounted utility from time t onward, after
choosing the best ϕt.
The value function can be written recursively as
Vt(At, Lt) = max
ϕt∈[0,1]
[Ut(At, Lt, ϕt)]
= max
ϕt∈[0,1]
h
U (bt) Lt + e
−δ Et
[Vt+1(At+1, Lt+1)] i
= max
ϕt∈[0,1] "
U
 
At
Lt a¨x+t,h !
Lt + e
−δ Et
[Vt+1(At+1, Lt+1)]#.
At the final period T = ω − x, the annuity factor simplifies to a¨x+T,h = 1 for all h since
there are no future payments beyond T. Therefore, the value function at time T becomes
VT (AT , LT ) = U

AT
LT

LT .
Then, we proceed backward in time, starting with t = T − 1 and going back to time 0.
From the fact that
At+1 = At
 
1 −
1
a¨x+t,h ! 
ϕt
St+1
St
+ (1 − ϕt)
Pt+1
Pt

,
we have
Vt(At, Lt)
= max
ϕt∈[0,1] "
U
 
At
Lt a¨x+t,h !
Lt + e
−δ Et
[Vt+1(At+1, Lt+1)]#
= max
ϕt∈[0,1] "
U
 
At
Lt a¨x+t,h !
Lt + e
−δ Et
"
Vt+1 At − Lt
At
Lt a¨x+t,h !
exp r
PF
t+1
, Lt+1!##
= max
ϕt∈[0,1] "
U
 
At
Lt a¨x+t,h !
Lt
+e
−δ Et
"
Vt+1 At
 
1 −
1
a¨x+t,h ! 
ϕt
St+1
St
+ (1 − ϕt)
Pt+1
Pt

, Lt+1!## .
16
This expectation involves two random variables: the risky asset price St+1 and the
number of survivors Lt+1 given by lognormal and binomial random variables, respectively,
as per the assumptions in Chapter 2:
St+1 ∼ Lognormal log(St) + µ, σ2

,
Lt+1 ∼ Binomial (Lt, px+t),
where the log of risky asset return log 
St+1
St

∼ N µ −
σ
2
2
, σ2

, and px+tis the survival
probability from age x + t to x + t + 1.
Now we solve for the time-t optimal investment policy ϕ
∗
t
for a given At and Lt while
holding the hurdle rate h fixed. The first-order condition with respect to ϕtis given by
0 =
∂
∂ϕt
Ut(At, Lt, ϕt)




ϕt=ϕ
∗
t
=
∂
∂ϕt
U
 
At
Lt a¨x+t,h !
Lt





ϕt=ϕ
∗
t
+
∂
∂ϕt
e
−δEt
[Vt+1(At+1, Lt+1)]





ϕt=ϕ
∗
t
=
∂
∂ϕt
e
−δEt
[Vt+1(At+1, Lt+1)]




ϕt=ϕ
∗
t
= e
−δ Et
"
V
′
t+1 
At
 
1 −
1
a¨x+t,h ! 
ϕ
∗
t
St+1
St
+ (1 − ϕ
∗
t
)
Pt+1
Pt

, Lt+1! 
St+1
St
−
Pt+1
Pt
#
× At
 
1 −
1
a¨x+t,h !
(4.6)
which is true for all t. We can simplify it as
⇒ 0 = Et
"
V
′
t+1 
At
 
1−
1
a¨x+t,h ! 
ϕ
∗
t
St+1
St
+(1−ϕ
∗
t
)
Pt+1
Pt

, Lt+1! 
St+1
St
−
Pt+1
Pt
#
, (4.7)
where V
′
t+1 is the first-order derivative of Vt+1 with respect to the first argument.
We can obtain a simpler expression for V
′
t+1(At+1, Lt+1) in Equation (4.7) by using the
envelope theorem, which means we differentiate Vt+1(At+1, Lt+1) with respect to At+1 while
treating ϕt+1 as fixed at its optimal value ϕ
∗
t+1. This theorem helps us avoid accounting for
how ϕ
∗
t+1 changes with At+1. Instead, we only need to consider the direct effect of At+1 on
utility. Specifically,
V
′
t+1(At+1, Lt+1)
=
∂
∂At+1
Vt+1(At+1, Lt+1)
=
∂
∂At+1
Ut+1(At+1, Lt+1, ϕt+1)




ϕt+1=ϕ
∗
t+1
17
=
∂
∂At+1
U
 
At+1
Lt+1 a¨x+t+1,h !
Lt+1





ϕt+1=ϕ
∗
t+1
+
∂
∂At+1
e
−δ Et+1 [Vt+2 (At+2, Lt+2)]





ϕt+1=ϕ
∗
t+1
= U
′
 
At+1
Lt+1 a¨x+t+1,h !
1
a¨x+t+1,h
+


∂
∂ϕt+1
e
−δ Et+1 [Vt+2 (At+2, Lt+2)]





ϕt+1=ϕ
∗
t+1


| {z }
=0 from the first order condition of Equation (4.6)


∂
∂At+1
ϕt+1





ϕt+1=ϕ
∗
t+1


= U
′
 
At+1
Lt+1 a¨x+t+1,h !
1
a¨x+t+1,h
, (4.8)
where U
′
(·) is the first-order derivative of U.
4 Using the result of Equation (4.8) to simplify
Equation (4.7) leads to
0 = Et





a
1 − γ


At

1−
1
a¨x+t,h  ϕ
∗
t
St+1
St
+(1−ϕ
∗
t
)
Pt+1
Pt

Lt+1 a¨x+t+1,h

+c


γ−1

St+1
St
−
Pt+1
Pt



 . (4.9)
The expectation above cannot be solved in closed form due to the complexity introduced by the two random variables St+1 and Lt+1. Gauss–Hermite quadratures are used to
recover a numerical expression for the integral implied in Equation (4.9). More details on
the implementation are given in Section 4.2.
Following Carroll (2006) and Cui et al. (2011), we build discrete grids of At defined
over {At,j}
J
j=1 and Lt over {Lt,k}
K
k=1, which represent possible values of the two state
variables. These grids are uniformly defined for all time steps t ∈ T ∗, where ω represents
the maximum attainable age and x is the initial age of the members. For each point in the
grid, we numerically solve Equation (4.9) to determine the optimal allocation at each time
t, ϕ
∗
t
, as a function of At and Lt, and for a given hurdle rate h. This approach allows us to
obtain a time-dependent optimal policy for each possible combination of state variables.
4.1.4 Solving for the optimal hurdle rate
Having determined the optimal investment policy ϕ
∗
t
for a given hurdle rate h, we now address the outer problem of finding the optimal h that maximizes the overall expected utility
of the pension pool in Equation (4.1). The optimization of h involves a meta-optimization
process:
4The first-order derivative of the utility function can be easily calculated:
U
′
(b) = a

a b
1 − γ
+ c
γ−1
.
18
1. Initialize hurdle rate. We start by selecting a candidate hurdle rate h0 within a
realistic range [h, h]. These bounds may be set by regulatory constraints or practical
considerations.
2. Compute optimal investment policy. Using the method described in Subsection 4.1.3, we compute the optimal investment policy ϕ
∗
t
for each time t and state
variables At and Lt from time T − 1 to 0, given the selected hurdle rate h0.
3. Use the forward simulation step to find the expected utility. We perform forward simulations to evaluate the performance of the pension pool under the computed
policies.
(i) We start by generating economic and demographic scenarios through simulations
of processes S and L, respectively. Risky asset returns are simulated based on
the assumed lognormal distribution, and the binomial distribution is used to
generate survivor counts.
(ii) Then, we update the fund value after distributing benefits, At+1, and the benefit
per member, bt+1, based on paths we generated from the last step:
At+1 = (At − Lt bt)

ϕ
∗
t
St+1
St
+ (1 − ϕ
∗
t
)
Pt+1
Pt

= At
 
1 −
1
a¨x+t,h ! 
ϕ
∗
t
St+1
St
+ (1 − ϕ
∗
t
)
Pt+1
Pt

,
where ϕ
∗
t
is obtained at each time by searching the precomputed grid based on
the current At and Lt. Since the state variables At and Lt may not exactly match
the grid points, we use linear interpolation to estimate ϕ
∗
t
for intermediate values
of At and Lt.
After that, the benefit per member is updated using
bt+1 =
At+1
Lt+1 a¨x+t+1,h
.
(iii) Since we have bt at each time t, we calculate the utility derived from the benefit
stream bt from time 0 to T, and then accumulate the total expected utility over
the pool’s horizon:
EUh =
X
T
t=0
e
−δ t 1 − γ
γ

a bt
1 − γ
+ c
γ
Lt.
19
Given that the process is simulated N times, the average expected utility can be
expressed as:
AEUh =
1
N
X
N
n=1
X
T
t=0
e
−δ t 1 − γ
γ

a bt,n
1 − γ
+ c
γ
Lt,n.
4. Finally, we can optimize the hurdle rate. By repeating steps 3(i) to (iii) for different
values of h while keeping the other parameters fixed, we search for the value of h
that maximizes AEUh. This is done using Brent’s method, which is well-suited for
one-dimensional optimization. We also ensure that the hurdle rate is between h and
h.
Through this meta-optimization process, we determine the optimal hurdle rate h
∗
that,
in conjunction with the optimal investment policies ϕ
∗ = {ϕ∗
t }
T −1
t=0 , maximizes the expected
utility of the pension pool members. This approach ensures that the pension scheme is
designed to align with the members’ risk preferences and provides sustainable benefits over
time.
4.2 Numerical implementation
Equation (4.9) contains two random variables, St+1 and Lt+1, from the data generating
assumption described in Chapter 2. Specifically, we have:
0 = Et[ft(St+1, Lt+1)]
= Et
"
ft
 
St exp µ −
σ
2
2
!
+ σ εt+1!, Lt+1!# ,
where the function ftis defined as
ft(S, L) =


a
1 − γ


At

1 −
1
a¨x+t,h  ϕt
S
St
+ (1 − ϕt)
Pt+1
Pt

La¨x+t+1,h

 + c


γ−1

S
St
−
Pt+1
Pt

,
the random variable εt+1 follows a standard normal distribution and Lt+1 is the possible
number of survivors at time t + 1 with Ltindependent Bernoulli trials and the constant
probability of survival of px+t. Thus,
0 = Et[f(St+1, Lt+1)]
=
X
Lt
l=0
 Z ∞
−∞
ft
 
St exp µ −
σ
2
2
!
+ σ εt+1!, l!
1
√
2π
exp 
−
ε
2
t+1
2
!
dεt+1!
×
 
Lt
l
!
p
l
x+t
(1 − px+t)
Lt−l
.
20
To evaluate the integral over εt+1 requires numerical quadrature methods, which approximate integrals by weighted sums of function evaluations at specified points within the
domain of integration. This technique allows us to transform a complicated integral into a
finite sum, making the problem computationally tractable.
There are various quadrature rules, each tailored to different types of integrals and
probability distributions. Common methods include Newton–Cotes formulas (such as the
trapezoidal and Simpson’s rules) and Gaussian quadrature. Gaussian quadrature rules are
particularly powerful because they place evaluation points and weights optimally for polynomials up to a certain degree, resulting in highly accurate approximations with fewer nodes
compared to many other methods.
Considering that the integral involves a normally distributed random variable and its
infinite domain, we choose Gauss–Hermite quadrature, which is used to approximate the
value of integrals that have the following structure:
Z ∞
−∞
e
−x
2
f(x) dx.
By replacing εt+1 =
√
2z above, we can approximate the value of integrals of Equation (4.9)
by
0 = Et[ft(St+1, Lt+1)]
=
X
Lt
l=0
Xn
i=1
f

St e
µ− σ
2
2 +
√
2σ zi
, l
1
√
π
wi
 
Lt
l
!
p
l
x+t
(1 − px+t)
Lt−l
,
where n is the number of integration points, the points zi are the roots of the physicists’
version of the Hermite polynomial Hn(z) as discussed in Liu and Pierce (1994), and the
associated weights wi for each point zi are given by
wi =
2
n−1 n!
√
π
n2H2
n−1
(zi)
.
By selecting an appropriate number of nodes n, we achieve a balance between computational efficiency and accuracy.
21
Chapter 5
Base case results
This chapter presents results for the base cases under different combinations of risk aversion
parameter γ and baseline parameter c for the HARA utility function. The goal is to evaluate
the optimal hurdle rate h
∗ and corresponding investment policy ϕ∗ across varying levels of
risk preferences and baseline benefit levels, revealing how these parameters jointly shape
pension pool dynamics.
5.1 Model setting
To analyze the impact of different levels of risk aversion and baseline benefit thresholds on
the lifetime pension pool, we fix a set of base parameters while varying γ and c. Table 5.1
summarizes the utility function parameters, population and pool characteristics, and asset
parameters for the baseline environment. We then run 100,000 simulations to capture a
broad distribution of potential outcomes, and we employ 20 Gauss–Hermite quadrature
points wherever numerical integration is required. For the lower and upper bound of the
hurdle rate, we assume h = −0.10 and h = 0.10.
We select three values for the risk aversion parameter, γ, to represent different investor
profiles. When γ = −2, individuals show moderate risk aversion and thus a greater willingness to invest in the risky asset. As γ moves to −4, they become more cautious, lowering the
share of assets allocated to volatile investment instruments. In the extreme case of γ = −6,
the pool adopts a highly conservative stance, significantly reducing its exposure to risk.
The baseline parameter c also plays a key role by adjusting how relative risk aversion
behaves at different benefit levels. Specifically, c = −500 imposes a conservative outlook
when benefits are low, pushing individuals to guard against downside risk. A neutral point
occurs at c = 0, where the utility function shows constant relative risk aversion, resulting
in a steady investment ratio across asset levels. Finally, c = 500 raises the willingness to
take risk at lower benefit levels, allowing for a more aggressive pursuit of returns when the
fund dips.
22
Table 5.1: Parameter settings for base case analysis.
Panel A: Utility function parameters
Parameter Value Description
γ −2, −4, −6 Risk aversion parameter
c −500, 0, 500 Benefit threshold or baseline level
a 1 Scaling parameter, determines sensitivity of utility to benefit
δ 0.05 Subjective discount rate
Panel B: Population and pool parameters
Parameter Value Description
L0 500 Initial number of members in the pool
m 85 Modal value of the Gompertz law of mortality
b 10 Dispersion coefficient of the Gompertz law of mortality
x 65 Age of each member at inception
Panel C: Asset parameters
Parameter Value Description
A0 1,000,000 × L0 Initial total fund size
r 0.02 Continuously compounded risk-free rate
µ 0.06 Expected return of the risky asset
σ 0.15 Volatility (standard deviation of returns) for risky asset
Notes: This table lists the parameters for the base cases, providing a baseline for our subsequent analysis.
We examine nine combinations of γ and c, keeping all other settings constant.
Other parameters define the life expectancy distribution, the initial size of the pool,
and the financial market assumptions. First, under the Gompertz mortality law, m = 85
indicates a modal age at death of 85 years, and b = 10 reflects moderate dispersion around
this mode. The asset side starts with a total fund A0 = 1,000,000 × L0, divided between
a risk-free asset growing at r = 0.02 and a risky asset with expected return µ = 0.06
and volatility σ = 0.15. These financial parameters set a realistic scenario in which the
pool seeks to balance stable returns with the potential gains of riskier investments. Finally,
the subjective discount rate δ = 0.05 gives a moderate weighting to future consumption,
aligning with typical assumptions about time preference.
Our analysis uses the parameter configuration in Table 5.1 to examine three critical
aspects: how the risk aversion parameter γ affects investment allocations, how the baseline threshold c modifies risk sensitivity, and the interaction between these parameters in
determining financial outcomes.
5.2 Results for base cases
5.2.1 Optimal investment policy surfaces
To gain insight into the optimal investment policy ϕ, we show the solution grids of ϕ
∗
t at a
specific time point t = 20. For each combination of risk aversion and baseline parameters,
the investment policy is determined conditional on the corresponding optimal hurdle rate,
which will be presented in Section 5.2.2. We present three three-dimensional surface plots
23
corresponding to different values of the baseline parameter c in {−500, 0, 500}, while varying
the risk aversion parameter γ across {−2, −4, −6}. These surfaces illustrate the relationship between the proportion of assets allocated to the risky asset ϕ
∗
20 as a function of the
number of surviving members L20 and the total fund value A20. We choose time t = 20
as a representative time point because the allocation pattern remains qualitatively similar
across different time steps. This allows us to illustrate the fundamental effects of parameter
variations without redundant visualizations.
Each plot consists of three layers: the top surface in blue represents γ = −2, the middle
surface in dark gray represents γ = −4, and the bottom surface in light gray represents
γ = −6. These plots align with our analysis of the relationship between γ and risk allocation
in Section 5.1 and applies consistently to all three figures.
Figure 5.1: Optimal risky asset allocation at time 20 as a function of total asset
value and number of members for c = 0.
Notes: Each surface corresponds to a different level of risk aversion (from the top with γ = −2 to the bottom
with γ = −6), illustrating how the allocation strategy changes with varying risk preferences.
Figure 5.1 confirms that when c = 0, the allocation remains nearly constant for any
combination of A20 and L20. In the HARA framework, setting c = 0 yields a utility function
with CRRA, meaning the proportion of assets in the risky portfolio does not change with
wealth level. This naturally leads to a flat surface.
For Figures 5.2 and 5.3, we adjust the total asset range to from 0 to 200 million (instead
of the larger range used in Figure 5.1) to highlight changes in the marginal region where the
24
impact of c is more visually apparent. Beyond 200 million, the allocation patterns remain
stable and similar to Figure 5.1.
Figure 5.2: Optimal risky asset allocation at time 20 as a function of total asset
value and number of members for c = 500.
Notes: See the caption of Figure 5.2.
When c = 500, we observe that the risky asset allocation increases as A20 decreases,
particularly when the asset value falls below 50 million. This result aligns with the properties
of the HARA utility function, where a positive c leads to a decreasing RRA as the benefit
decreases. As a result, when assets are small, the pool exhibits less risk-averse behaviour,
allocating a larger proportion to the risky asset. We also see that as long as the number of
members L20 remains large, changes in ϕ20 occur gradually. However, when there are fewer
survivors, the surface can bend steeply, allowing ϕ20 to shift sharply toward 1 in low-asset
scenarios, where more aggressive investment is used to improve potential future payouts
despite the higher associated risk.
Conversely, when c = −500, we see a more conservative allocation strategy, particularly
for lower asset values. In this setting, the pool becomes highly risk-averse when assets
decrease below 100 million, as the negative baseline parameter increases the RRA at low
benefit levels. This results in a more cautious approach to investment, reducing exposure to
the risky asset in order to avoid potential losses. The pattern of slower change for larger L20
and more abrupt shifts near the edges (low membership) still applies: with few survivors,
the allocation may fluctuate sharply to near zero, reflecting a protective retraction.
All three surfaces align with the theoretical properties of HARA utility, where changes in
c shift relative risk aversion at different asset levels. A positive c promotes risk-taking during
25
Figure 5.3: Optimal risky asset allocation at time 20 as a function of total asset
value and number of members for c = −500.
Notes: See the caption of Figure 5.2.
low-asset scenarios, while a negative c encourages a safety-first approach. Under c = 0, the
utility function reduces to CRRA, resulting in a consistently flat allocation surface.
5.2.2 Optimal hurdle rate results
The results for the nine base cases, combining different levels of the risk aversion parameter
γ and the baseline c, are summarized in Table 5.2. For each combination, the optimal hurdle
rate h
∗
, the corresponding certainty-equivalent consumption (CEC), and the average benefit
level are presented.
When comparing cases with the same baseline c but different values of γ, we see that
lower risk aversion leads to higher hurdle rates, thereby raising weighted average benefits.
As γ moves to −4 and −6, the pool becomes more cautious, adopting lower hurdle rates
and settling for reduced benefit levels.
Looking within each γ block as c varies from −500 to 500, we generally observe more
aggressive hurdle rates—and therefore higher benefit levels—for larger c. However, an especially conservative setting does not necessarily prevent generous outcomes. For example,
Case 7 with γ = −6 and c = −500 starts with a low hurdle rate and modest initial benefits but ends up with a relatively high weighted average. In this case, the conservative
payout structure preserves assets early on. As membership declines and investment returns
accumulate, the remaining survivors receive enhanced mortality credits, lifting the overall
benefit level.
26
Table 5.2: Optimal hurdle rate and key metrics for base cases.
Risk Optimal hurdle Weighted average Certainty-equivalent
Case aversion Baseline rate benefit level consumption
1 –2 –500 3.5074% 84,069 76,184
2 –2 0 3.5601% 84,398 76,418
3 –2 500 3.6039% 84,816 76,645
4 –4 –500 2.3548% 77,409 71,187
5 –4 0 2.8412% 77,151 71,981
6 –4 500 2.9624% 77,442 72,312
7 –6 –500 0.7715% 76,015 65,239
8 –6 0 1.7651% 75,125 68,344
9 –6 500 2.3393% 74,893 69,847
Notes: This table summarizes the optimal hurdle rate and key financial metrics for different combinations
of risk aversion parameter γ and baseline c. The benefit level refers to the average benefit weighted by
survival probability over the pool’s time horizon. The certainty-equivalent consumption (CEC) is derived
from inverting the expected utility values.
These patterns highlight the interplay of γ and c. Highly risk-averse investors exhibit
sharp changes in hurdle rates and benefits when c shifts, reflecting a strong sensitivity to
any baseline adjustment. At moderate risk aversion, changing c still matters but is tempered
by the pool’s willingness to maintain a certain level of investment risk.
The CEC measure offers a risk-adjusted perspective of benefit adequacy over time.
Unlike the weighted average benefit, which captures per-capita payouts weighted by survival
likelihood, CEC reflects overall consumption value under risk preferences. Across all cases,
CEC increases with lower risk aversion and higher hurdle rates, highlighting the tradeoff between benefit stability and long-term upside. Conservative strategies yield lower but
more secure CEC values, emphasizing sustainability, while more aggressive approaches offer
enhanced long-term consumption at greater volatility.
After comparing the cases in Table 5.2, we further examine how the variance of benefit
payments evolves over time under these same base cases. Figure 5.4 plots the variance of
benefits per member at each time point, separating results by γ while showing distinct lines
for c = −500, c = 0, and c = 500.
The left panel of Figure 5.4 shows that under γ = −2, the pool’s more aggressive
hurdle rates lead to the highest overall variance, especially near the end of the horizon
when membership is low and any market swings or shortfalls strongly affect individual
payouts. Stepping to γ = −4 in the middle panel moderates these variances, though a
late-stage uptick remains visible. The γ = −6 case (right panel) reveals a different pattern:
although early variances stay relatively low, the gap between c = −500 and c = 500 widens
significantly in the final years.
Referring again to Table 5.2, we see that, for γ = −6, the difference in hurdle rates across
baselines can exceed 1.5%, much larger than the 0.1% range when γ = −2. A smaller hurdle
rate holds benefits down initially, but if actual returns exceed this conservative target later
on, benefits can surge dramatically for the remaining survivors, causing a spike in variance.
27
0.0e+00
5.0e+09
1.0e+10
1.5e+10
0 10 20 30 40
Time
Variance of benefits
c = − 500 c = 0 c = 500
γ = −2
0.0e+00
5.0e+09
1.0e+10
1.5e+10
0 10 20 30 40
Time
Variance of benefits
c = − 500 c = 0 c = 500
γ = −4
0.0e+00
5.0e+09
1.0e+10
1.5e+10
0 10 20 30 40
Time
Variance of benefits
c = − 500 c = 0 c = 500
γ = −6
Figure 5.4: Variance of benefits per member over time.
Notes: Each panel corresponds to a different γ: the left panel with γ = −2, the middle panel with γ = −4,
and the right panel with γ = −6. The lines within a panel represent distinct baselines c from −500 to 500.
Thus, the interplay of γ and c not only sets average benefit levels but also shapes how
unstable those benefits can become over the pool’s final years.
We now broaden our analysis beyond the nine discrete base cases to explore how the
optimal hurdle rate h
∗
changes over a wider range of γ and c. Figure 5.5 focuses on varying
γ while fixing each baseline at −500, 0, and 500, and Figure 5.6 holds γ at −2, −4, and
−6, while allowing c to span from −500 to 500. These two plots provide a clearer picture of
how risk preferences and baseline thresholds jointly affect the fund’s return targets in more
continuous settings.
In Figure 5.5, we vary γ while each curve corresponds to one of the three baseline values
c ∈ {−500, 0, 500}. As risk aversion becomes less negative (moving toward −2), the pool
selects higher hurdle rates, whereas a strongly negative γ forces more modest hurdle rates.
At high risk aversion, a positive baseline still elevates h
∗
, but once γ approaches −2, the
three curves converge, suggesting that the baseline parameter plays a less significant role in
determining the hurdle rate when risk aversion is low.
In Figure 5.6, we reverse the roles and sweep c from −500 to 500 for each γ. All three lines
slope upward, but the one for γ = −2 rises more gently, meaning moderate risk aversion is
less sensitive to baseline shifts. When γ = −6, the curve exhibits a larger jump, consistent
with the stronger reactions of highly risk-averse investors to any opportunity for higher
returns.
Together, these extended plots reinforce the relationships observed in Table 5.2 and
Figure 5.4. As γ and c vary, the optimal hurdle rate shifts accordingly, governing how
aggressive or conservative the pension pool’s investment and benefit strategies become.
28
−0.02
0.00
0.02
−12 −8 −4
γ
Optimal hurdle rate
c = − 500 c = 0 c = 500
Figure 5.5: Optimal hurdle rate for c across different γ.
Notes: Each line corresponds to a baseline level c from −500 to 500, while γ spans a broader range than the
base cases.
0.01
0.02
0.03
−500 −250 0 250 500
c
Optimal hurdle rate
γ = −2 γ = − 4 γ = − 6
Figure 5.6: Optimal hurdle rate for γ across different c.
Notes: Each line represents one level of risk aversion γ ∈ {−2, −4, −6}, with c extending from −500 to 500.
29
5.2.3 Evolution of key variables over time
This section examines the evolution of key financial variables in lifetime pension pools under
different risk aversion γ and baseline c settings: the total asset value At, the benefit per
member bt, and the risky asset allocation ϕt. By comparing these variables across the nine
base cases, we can see how varying preferences shape the financial sustainability of the pool
and the investment policy over time.
0e+00
2e+08
4e+08
6e+08
0 10 20 30 40
Time
Total asset
Case 1: γ = −2 , c = − 500
0e+00
2e+08
4e+08
6e+08
0 10 20 30 40
Time
Total asset
Case 2: γ = −2 , c = 0
0e+00
2e+08
4e+08
6e+08
0 10 20 30 40
Time
Total asset
Case 3: γ = −2 , c = 500
0e+00
2e+08
4e+08
6e+08
0 10 20 30 40
Time
Total asset
Case 4: γ = −4 , c = − 500
0e+00
2e+08
4e+08
6e+08
0 10 20 30 40
Time
Total asset
Case 5: γ = −4 , c = 0
0e+00
2e+08
4e+08
6e+08
0 10 20 30 40
Time
Total asset
Case 6: γ = −4 , c = 500
0e+00
2e+08
4e+08
6e+08
0 10 20 30 40
Time
Total asset
Case 7: γ = −6 , c = − 500
0e+00
2e+08
4e+08
6e+08
0 10 20 30 40
Time
Total asset
Case 8: γ = −6 , c = 0
0e+00
2e+08
4e+08
6e+08
0 10 20 30 40
Time
Total asset
Case 9: γ = −6 , c = 500
Quantile 10th 25th Median 75th 90th
Figure 5.7: Evolution of the total asset value for the nine base cases.
Notes: Each plot represents a unique combination of risk aversion and baseline benefit threshold. The lines
represent different quantiles of the simulated paths.
For Figure 5.7, looking from top to bottom (i.e., changing γ), we see that lower risk
aversion leads to wider dispersion in total assets. This happens because a less risk-averse
pool invests more in the risky asset, exposing itself to greater market fluctuations. As γ
moves to −6, the pool becomes increasingly conservative, resulting in a narrower spread
among the quantiles.
30
0e+00
2e+15
4e+15
6e+15
8e+15
0 10 20 30 40
Time
Variance of asset
c = −500 c = 0 c = 500
γ = −2
0e+00
2e+15
4e+15
6e+15
8e+15
0 10 20 30 40
Time
Variance of asset
c = −500 c = 0 c = 500
γ = −4
0e+00
2e+15
4e+15
6e+15
8e+15
0 10 20 30 40
Time
Variance of asset
c = −500 c = 0 c = 500
γ = −6
Figure 5.8: Variance of the total asset value for the nine base cases.
Notes: Each panel corresponds to a different γ: the left panel with γ = −2, the middle panel with γ = −4,
and the right panel with γ = −6. The lines within a panel represent distinct baselines c from −500 to 500.
When we examine the plots from left (i.e., c = −500) to right (i.e., c = 500), the influence
of baseline benefit c on the distribution of total assets is harder to detect in Figure 5.7, as
the quantile bands appear visually similar. To better capture this effect, Figure 5.8 presents
the variance of total assets over time for each risk aversion level. We observe that a positive
baseline often encourages a more aggressive investment strategy, which amplifies the range
of outcomes in later years. In contrast, when c = −500, the pool tends to protect assets in
a conservative manner, making the decline in total assets smoother and less variable. This
effect is most pronounced when γ = −2, where risk-taking behaviour is more responsive to
changes in c.
Figure 5.9 shows the evolution of the benefit per member over time, focusing on comparing the rows first, we notice that when γ = −2, benefits fluctuate more widely over
time, reflecting the aggressive stance toward risky assets. By contrast, as γ becomes more
negative (down to −6), the pool prioritizes stability at the early stage but shows increasing
dispersion later.
Regarding the baseline parameter, a higher c tends to lift benefits early on and introduce
more stable increases in later years. This happens because a positive baseline encourages
higher allocations to the risky asset, which can lead to bigger payoffs if markets perform
well. On the other hand, a negative baseline lowers initial benefits but may still show some
late variability if investment returns outperform expectations in a shrinking pool. These
patterns align with Figure 5.4, which shows the variance of benefit levels over time.
Connecting these observations withth the hurdle rate results in Table 5.2, we see that a
larger hurdle rate often aligns with higher or more volatile benefits. This is because choosing
a higher h
∗
sets a more ambitious return target, which raises initial benefit levels but exposes
31
0e+00
1e+05
2e+05
3e+05
0 10 20 30 40
Time
Benefit
Case 1: γ = −2 , c = − 500
0e+00
1e+05
2e+05
3e+05
0 10 20 30 40
Time
Benefit
Case 2: γ = −2 , c = 0
0e+00
1e+05
2e+05
3e+05
0 10 20 30 40
Time
Benefit
Case 3: γ = −2 , c = 500
0e+00
1e+05
2e+05
3e+05
0 10 20 30 40
Time
Benefit
Case 4: γ = −4 , c = − 500
0e+00
1e+05
2e+05
3e+05
0 10 20 30 40
Time
Benefit
Case 5: γ = −4 , c = 0
0e+00
1e+05
2e+05
3e+05
0 10 20 30 40
Time
Benefit
Case 6: γ = −4 , c = 500
0e+00
1e+05
2e+05
3e+05
0 10 20 30 40
Time
Benefit
Case 7: γ = −6 , c = − 500
0e+00
1e+05
2e+05
3e+05
0 10 20 30 40
Time
Benefit
Case 8: γ = −6 , c = 0
0e+00
1e+05
2e+05
3e+05
0 10 20 30 40
Time
Benefit
Case 9: γ = −6 , c = 500
Quantile 10th 25th Median 75th 90th
Figure 5.9: Evolution of the benefit per member for the nine base cases.
Notes: See caption of Figure 5.7.
the pool to greater swings if market performance falters. Conversely, a lower h
∗ produces
more cautious payouts at the start, giving the fund additional time to grow steadily before
boosting benefits in later years.
Figure 5.10 reports the risky asset allocation for different values of risk aversion and
baseline parameters. The plot shows that lower risk aversion allows the pool to maintain its
share in the risky asset over time, and become volatile toward the end of the horizon when
membership is small. Higher risk aversion dampens these swings, keeping the allocation
more consistent.
A positive baseline of c = 500 pushes the allocation higher in later years, reflecting
a willingness to take on greater market risk for potential gains. A negative baseline of
c = −500, however, keeps the pool in a cautious stance, leading to smaller changes in
allocation as time goes on. This difference is most apparent when γ = −2, where investment
policy responds sharply to changes in the baseline threshold.
32
0.52
0.56
0.60
0.64
0.68
0 10 20 30 40
Time
Allocation
Case 1: γ = −2 , c = −500
0.52
0.56
0.60
0.64
0.68
0 10 20 30 40
Time
Allocation
Case 2: γ = − 2 , c = 0
0.52
0.56
0.60
0.64
0.68
0 10 20 30 40
Time
Allocation
Case 3: γ = −2 , c = 500
0.30
0.35
0.40
0.45
0 10 20 30 40
Time
Allocation
Case 4: γ = −4 , c = −500
0.30
0.35
0.40
0.45
0 10 20 30 40
Time
Allocation
Case 5: γ = − 4 , c = 0
0.30
0.35
0.40
0.45
0 10 20 30 40
Time
Allocation
Case 6: γ = −4 , c = 500
0.20
0.25
0.30
0.35
0 10 20 30 40
Time
Allocation
Case 7: γ = −6 , c = −500
0.20
0.25
0.30
0.35
0 10 20 30 40
Time
Allocation
Case 8: γ = − 6 , c = 0
0.20
0.25
0.30
0.35
0 10 20 30 40
Time
Allocation
Case 9: γ = −6 , c = 500
Quantile 10th 25th Median 75th 90th
Figure 5.10: Evolution of risky asset allocation for the nine base cases.
Notes: See caption of Figure 5.7.
Taken together, these figures underscore the interplay between risk aversion and the
baseline parameter. When both are positioned toward more aggressive values—γ = −2 and
c = 500 in our context—the pool experiences higher volatility in both assets and benefits.
Conversely, a conservative combination—γ = −6 and c = −500 in this case—keeps outcomes
more stable at the early stage, at the cost of potentially lower payoffs and larger fluctuation
later.
33
Chapter 6
Robustness tests
In earlier chapters, we focused on a baseline configuration of the pension pool, assuming
a particular pool size, financial market parameters, mortality assumptions, and subjective
discount rates. However, real-world conditions may deviate significantly from this baseline.
The present chapter provides a detailed robustness analysis by altering these key inputs.
We aim to assess how each variation impacts the model’s optimal hurdle rate, the MEA,
the IEA, and other financial metrics, especially benefit levels and allocation to risky assets.
6.1 Changes in the pool size
6.1.1 Scenarios
We first examine how altering the initial number of participants L0 affects model outcomes,
comparing
– The base case of 500 members.
– A smaller pool of 100 members.
– A larger pool of 1000 members.
6.1.2 Optimal hurdle rate
Figure 6.1 shows that larger pools consistently select higher hurdle rates, while smaller
pools adopt more conservative targets. This is because larger pools benefit from risk diversification, mitigating the impact of individual mortality. In contrast, smaller pools face
greater demographic uncertainty, leading to more cautious payouts to ensure long-term
sustainability.
Across all scenarios, the optimal hurdle rate increases with higher baseline benefits c,
as the fund must generate sufficient returns to sustain payouts. However, the gap between
different pool sizes is most pronounced when risk aversion is high (i.e., γ = −6) as stability
takes precedence over return maximization. By contrast, the gap is quite narrow under lower
34
γ = − 2 γ = − 4 γ = −6
−500 0 500 −500 0 500 −500 0 500
−0.02
0.00
0.02
Baseline c
Optimal hurdle rate
Scenario Base case Smaller pool Larger pool
Figure 6.1: Optimal hurdle rate for different pool sizes.
Notes: Each panel corresponds to a risk aversion level γ of −2, −4, and −6 from left to right. The x-axis
is the baseline c, and lines indicate different pool size scenarios: the base case of 500 members in blue, the
small pool of 100 members in pink, and the large pool of 1000 members in purple.
risk aversion (i.e., γ = −2) as the emphasis shifts toward return-seeking behaviour, making
even smaller pools more willing to adopt higher hurdle rates.
6.1.3 Mortality experience adjustment
The benefit adjustment rule, shown in Equation 3.2, is defined as the product of a mortality
experience adjustment (MEA) and an investment experience adjustment (IEA). The MEA
modifies the benefit level over time based on deviations between actual and expected survivor counts. Since changes in pool size directly impact mortality dynamics, the MEA will
vary accordingly, while the IEA remains unaffected. Therefore, we focus only on the MEA
in this section.
Figure 6.2 compares the average realized MEA across the three pool-size scenarios. Initially, all scenarios remain near MEA = 1, indicating that average actual survivor counts
closely align with expectations. Over time, the MEA gradually increases as deviations accumulate and the realized number of survivors begins to fall below the projected values. The
larger pool with 1000 initial members experiences this shift more slowly due to better risk
diversification. In contrast, the smaller pool with only 100 members sees sharper fluctuations
in survivor outcomes, leading to a more pronounced rise in MEA in later periods.
35
1.00
1.01
1.02
1.03
0 10 20 30
Time
MEA
Scenario Base case Smaller pool Larger pool
Figure 6.2: Average mortality experience adjustment for different pool sizes.
Notes: Each line represents a different initial pool size: the base case of 500 members in blue, the small pool
of 100 members in pink, and the large pool of 1000 members in purple.
6.1.4 Benefit levels
In analyzing the impact of pool size on the financial stability of the pool, we focus specifically
on the benefit level bt and its behaviour over time. While other financial metrics, such as the
risky asset allocation ϕt and total fund value At provide insights into investment strategies
and fund sustainability, btis the most directly relevant metric for members as it reflects the
actual payouts they receive. Moreover, the influence of pool size on benefit variability is the
most pronounced, making it the primary factor of interest in this comparison.
Figure 6.3 compares the evolution of average benefit levels for different pool sizes. The
smaller pool starts with lower benefits but exhibits a pronounced increase later, with the
most significant spike occurring under high risk aversion (i.e., γ = −6). This arises from
more conservative investment strategies at earlier stages, which leave extra capacity for
benefit growth once membership declines. In contrast, the larger pool begins at a higher
benefit level and follows a steadier path over time. Additionally, while the smaller pool’s
benefits start declining around age 90, the larger pool continues to increase until about age
95, demonstrating its stronger capacity to sustain benefits longer.
Figure 6.4 further illustrates the variance of benefit levels over time. The smaller pool
generally exhibits greater variance, except for two low-risk aversion cases (Cases 2 and
3), where its preference for higher benefits makes the effect of a smaller membership less
pronounced. The difference in variance is especially notable under γ = −6, where strong
36
0e+00
1e+05
2e+05
3e+05
0 10 20 30 40
Time
Benefit level
Case 1: γ = −2 , c = − 500
0e+00
1e+05
2e+05
3e+05
0 10 20 30 40
Time
Benefit level
Case 2: γ = −2 , c = 0
0e+00
1e+05
2e+05
3e+05
0 10 20 30 40
Time
Benefit level
Case 3: γ = −2 , c = 500
0e+00
1e+05
2e+05
3e+05
0 10 20 30 40
Time
Benefit level
Case 4: γ = −4 , c = − 500
0e+00
1e+05
2e+05
3e+05
0 10 20 30 40
Time
Benefit level
Case 5: γ = −4 , c = 0
0e+00
1e+05
2e+05
3e+05
0 10 20 30 40
Time
Benefit level
Case 6: γ = −4 , c = 500
0e+00
1e+05
2e+05
3e+05
0 10 20 30 40
Time
Benefit level
Case 7: γ = −6 , c = − 500
0e+00
1e+05
2e+05
3e+05
0 10 20 30 40
Time
Benefit level
Case 8: γ = −6 , c = 0
0e+00
1e+05
2e+05
3e+05
0 10 20 30 40
Time
Benefit level
Case 9: γ = −6 , c = 500
Scenario Base case Smaller pool Larger pool
Figure 6.3: Average benefit levels over time for different pool sizes.
Notes: Each panel represents a unique combination of risk aversion and benefit baseline. The lines represent
the benefit averages of the different scenarios: the base case of 500 members in blue, the small pool of 100
members in pink, and the large pool of 1000 members in purple.
risk aversion leads to a wide dispersion of potential benefit outcomes in the smaller pool.
Meanwhile, the larger pool maintains much lower variance, illustrating better risk pooling
and more stable outcomes. This comparison underscores how a larger pool size enhances
financial stability and mitigates benefit volatility.
6.2 Changes in the financial market parameters
6.2.1 Scenarios
Next, we explore how different expected return and volatility parameters µ and σ for the
risky asset shape model outcomes to reflect different financial market situations. Specifically:
– The base case with µ = 0.06 and σ = 0.15.
37
0e+00
1e+10
2e+10
3e+10
4e+10
0 10 20 30 40
Time
Variance
Case 1: γ = −2 , c = −500
0e+00
1e+10
2e+10
3e+10
4e+10
0 10 20 30 40
Time
Variance
Case 2: γ = −2 , c = 0
0e+00
1e+10
2e+10
3e+10
4e+10
0 10 20 30 40
Time
Variance
Case 3: γ = −2 , c = 500
0e+00
1e+10
2e+10
3e+10
4e+10
0 10 20 30 40
Time
Variance
Case 4: γ = −4 , c = −500
0e+00
1e+10
2e+10
3e+10
4e+10
0 10 20 30 40
Time
Variance
Case 5: γ = −4 , c = 0
0e+00
1e+10
2e+10
3e+10
4e+10
0 10 20 30 40
Time
Variance
Case 6: γ = −4 , c = 500
0e+00
1e+10
2e+10
3e+10
4e+10
0 10 20 30 40
Time
Variance
Case 7: γ = −6 , c = −500
0e+00
1e+10
2e+10
3e+10
4e+10
0 10 20 30 40
Time
Variance
Case 8: γ = −6 , c = 0
0e+00
1e+10
2e+10
3e+10
4e+10
0 10 20 30 40
Time
Variance
Case 9: γ = −6 , c = 500
Scenario Base case Smaller pool Larger pool
Figure 6.4: Variance of benefit levels over time for different pool sizes.
Notes: Each panel represents a unique combination of risk aversion and benefit baseline. The lines represent
the variance of the benefit of the different scenarios: the base case of 500 members in blue, the small pool of
100 members in pink, and the large pool of 1000 members in purple.
– A high-return scenario with µ = 0.10 and σ = 0.15.
– A low-return scenario with µ = 0.04 and σ = 0.15.
– A high-volatility scenario with µ = 0.06 and σ = 0.30.
– A low-volatility scenario with µ = 0.06 and σ = 0.075.
6.2.2 Optimal hurdle rate
As shown in Figure 6.5, a more favourable market in terms of higher return or lower volatility
leads to a higher hurdle rate, particularly for moderate risk aversion parameter γ. In these
scenarios, the pool can justify discounting future liabilities at a higher rate, thereby allowing
larger immediate benefit payouts. Conversely, weaker average returns or high volatility result
38
γ = −2 γ = −4 γ = − 6
−500 0 500 −500 0 500 −500 0 500
0.02
0.04
0.06
Baseline c
Optimal hurdle rate
Scenario Base case High return Low return High volatility Low volatility
Figure 6.5: Optimal hurdle rate under different market conditions.
Notes: Each panel investigates a risk aversion level γ. The x-axis represents the baseline benefit threshold
c, and lines correspond to different financial market scenarios: the base case with µ = 0.06 and σ = 0.15,
the high-return scenario with µ = 0.10 and σ = 0.15, the low-return scenario with µ = 0.04 and σ = 0.15,
the high-volatility scenario with µ = 0.06 and σ = 0.30, and the low-volatility scenario with µ = 0.06 and
σ = 0.075.
in a lower hurdle rate, ensuring more modest present benefits to maintain sustainability
under uncertain or less attractive market conditions.
A notable finding is that lower average returns or high volatility result in nearly identical
hurdle rates across all parameter settings. This similarity can be attributed to their equal
Sharpe ratios—measuring return per unit of risk. Specifically, their overall risk-adjusted
returns are the same under both scenarios (Sharpe ratio of 0.133, assuming a risk-free rate
of 2%), leading to similar investment strategies.
On the other hand, the high-return scenario and the low-volatility scenario also share
the same Sharpe ratio (0.533), yet their hurdle rates only converge under high risk aversion
(γ = −6). This suggests that while the Sharpe ratio plays an important role in determining
investment strategies, it does not fully explain the observed behaviour. Additional factors
may be influencing this pattern, particularly the role of the IEA, which accounts for deviations between actual and expected investment returns. The impact of IEA will be explored
in the following subsection to provide a more complete explanation of these findings.
39
6.2.3 Investment experience adjustment
Different asset dynamics lead to variations in the IEA, which is a key factor in adjusting
benefit levels for the next period. The IEA results across cases and scenarios are summarized
in Table 6.1.
Table 6.1: Average investment experience adjustment across cases and scenarios
Risk Base High Low High Low
Case aversion Baseline case return return volatility volatility
1 –2 –500 1.0083 1.0439 0.9965 0.9964 1.0113
2 –2 0 1.0083 1.0420 0.9963 0.9963 1.0111
3 –2 500 1.0085 1.0414 0.9962 0.9962 1.0110
4 –4 –500 1.0103 1.0379 1.0026 1.0025 1.0208
5 –4 0 1.0060 1.0319 0.9995 0.9995 1.0161
6 –4 500 1.0054 1.0316 0.9987 0.9987 1.0150
7 –6 –500 1.0223 1.0410 1.0169 1.0169 1.0398
8 –6 0 1.0126 1.0296 1.0084 1.0083 1.0281
9 –6 500 1.0075 1.0247 1.0032 1.0031 1.0219
Notes: This table presents the average IEA for different combinations of risk aversion γ and benefit baseline
c across five financial market scenarios: the base case with µ = 0.06 and σ = 0.15, the high-return scenario
with µ = 0.10 and σ = 0.15, the low-return scenario with µ = 0.04 and σ = 0.15, the high-volatility scenario
with µ = 0.06 and σ = 0.30, and the low-volatility scenario with µ = 0.06 and σ = 0.075.
Table 6.1 shows that higher returns or lower volatility lead to the highest average IEA
values, indicating strong investment performance above the hurdle rate. Conversely, lower
returns or higher volatility exhibit the lowest average IEA values, reflecting frequent underperformance and a reduced ability to sustain benefit increases. For instance, in Case 3
(γ = −2, c = 500), the IEA under the high-return scenario is 1.0414, while under the lowreturn and the high-volatility scenarios, it remains around 0.9962. This supports the idea
that favourable or stable market conditions increase the likelihood of the IEA exceeding 1,
leading to benefits surpassing their expected trajectory.
A key observation from the previous subsection was that the optimal hurdle rates for the
low-return scenario and the high-volatility scenario are nearly identical across all parameter
settings. Table 6.1 explains why: their IEA values are also closely aligned, meaning that
despite different sources of risk (low returns or high fluctuations), their overall impact on
investment performance and benefit adjustments is equivalent.
Meanwhile, although higher average returns or lower volatility scenarios also share the
same Sharpe ratio, their IEA values differ significantly in low and moderate risk-aversion
cases. Only under high risk aversion (γ = −6) do their IEA values converge. This occurs because high risk aversion discourages aggressive asset allocation, leading to more conservative
investment strategies even in a favorable return environment. As a result, the high-return
scenario yields more limited exposure to both upside potential and downside risk, aligning
its outcomes more closely with those of the low-volatility scenario. This pattern is consistent
with the behaviour of hurdle rates, which also become similar across these two scenarios
only when the pool prioritizes stability under high risk aversion.
40
Overall, while the Sharpe ratio provides the basis for understanding investment decisions, the IEA further explains why the less favourable and the high-volatility scenarios
remain closely linked across all risk settings, whereas more favourable and the low-volatility
scenarios only align when risk aversion is extreme.
6.2.4 Investment policies and benefit levels
Among the various scenarios explored, only changes in the dynamics of the financial market
directly alter both the pool’s investment policies and the benefit levels. Unlike modifications
to pool size, mortality parameters, or utility discount rates, adjustments in the market
environment shift the fundamental risk–return profile, thereby impacting both investment
decisions and the evolution of benefits.
0e+00
2e+05
4e+05
6e+05
0 10 20 30 40
Time
Benefit level
Case 1: γ = −2 , c = − 500
0e+00
2e+05
4e+05
6e+05
0 10 20 30 40
Time
Benefit level
Case 2: γ = −2 , c = 0
0e+00
2e+05
4e+05
6e+05
0 10 20 30 40
Time
Benefit level
Case 3: γ = −2 , c = 500
0e+00
2e+05
4e+05
6e+05
0 10 20 30 40
Time
Benefit level
Case 4: γ = −4 , c = − 500
0e+00
2e+05
4e+05
6e+05
0 10 20 30 40
Time
Benefit level
Case 5: γ = −4 , c = 0
0e+00
2e+05
4e+05
6e+05
0 10 20 30 40
Time
Benefit level
Case 6: γ = −4 , c = 500
0e+00
2e+05
4e+05
6e+05
0 10 20 30 40
Time
Benefit level
Case 7: γ = −6 , c = − 500
0e+00
2e+05
4e+05
6e+05
0 10 20 30 40
Time
Benefit level
Case 8: γ = −6 , c = 0
0e+00
2e+05
4e+05
6e+05
0 10 20 30 40
Time
Benefit level
Case 9: γ = −6 , c = 500
Scenario Base case High return Low return High volatility Low volatility
Figure 6.6: Average benefit levels over time for different financial market scenarios.
Notes: Each panel represents a unique combination of risk aversion and baseline parameter. The lines show
the benefit averages for: the base case with µ = 0.06 and σ = 0.15, the high-return scenario with µ = 0.10
and σ = 0.15, the low-return scenario with µ = 0.04 and σ = 0.15, the high-volatility scenario with µ = 0.06
and σ = 0.30, and the low-volatility scenario with µ = 0.06 and σ = 0.075.
41
Figure 6.6 presents the average benefit trajectories for the different market conditions.
A higher expected return produces substantially larger average benefit payouts, especially
under moderate or high risk aversion (γ = −2 or −4), as the pool takes on more risk to capitalize on potential gains. This aggressive asset allocation leads to higher benefits but also
introduces greater variability, reflecting increased exposure to market fluctuations. In contrast, under extreme risk aversion (γ = −6), the investment strategy becomes significantly
more conservative, limiting the pool’s responsiveness to return differences. As a result, the
benefit trajectories for the high-return and low-volatility scenarios converge—despite their
different sources of advantage—because both environments provide a stable performance
backdrop, and the cautious strategy under high risk aversion reduces the model’s sensitivity to distinctions in return or volatility. This convergence underscores how strong risk
aversion dampens the impact of favorable market conditions on benefit outcomes.
Meanwhile, lower expected returns and higher volatility give rise to nearly identical
benefit paths across all risk settings, consistent with their matching Sharpe ratios and IEA
values. This suggests that whether risk arises from persistently low returns or frequent large
fluctuations, the overall impact on benefit levels remains similar if the risk–return tradeoff
is the same.
Figure 6.7 shows how these potential market conditions influence the allocation to the
risky asset. Among all scenarios, the low-volatility environment prompts the pool to adopt
the highest allocation in risky assets—reaching or remaining near 100%—since reduced
uncertainty lowers the perceived downside risk. Higher expected returns yield the secondhighest allocation, as the pool seeks to capitalize on potential gains. As risk aversion decreases (from γ = −6 to γ = −2), the risky allocation under the high-return scenario
grows more pronounced. Conversely, under the low-return or high-volatility case, the pool
maintains a more conservative stance with reduced exposure to risky assets.
These results highlight the unique role of financial market dynamics among our robustness tests: only changes to expected returns or volatility affect both investment policy and
benefit levels. In scenarios featuring low volatility or high returns, the plan allocates aggressively to risky assets, often resulting in higher or more volatile payouts. Meanwhile,
weaker returns or greater volatility produce more cautious allocations and modest benefit
trajectories.
6.3 Changes in the mortality parameters
6.3.1 Scenarios
This section examines the impact of different mortality parameter settings on the pension plan’s financial outcomes. We modify the Gompertz parameters m and b to simulate
varying lifespan expectations and mortality distributions, while keeping other assumptions
unchanged. Specifically, we consider:
42
0.00
0.25
0.50
0.75
1.00
0 10 20 30 40
Time
Allocation
Case 1: γ = −2 , c = −500
0.00
0.25
0.50
0.75
1.00
0 10 20 30 40
Time
Allocation
Case 2: γ = −2 , c = 0
0.00
0.25
0.50
0.75
1.00
0 10 20 30 40
Time
Allocation
Case 3: γ = −2 , c = 500
0.00
0.25
0.50
0.75
1.00
0 10 20 30 40
Time
Allocation
Case 4: γ = −4 , c = −500
0.00
0.25
0.50
0.75
1.00
0 10 20 30 40
Time
Allocation
Case 5: γ = −4 , c = 0
0.00
0.25
0.50
0.75
1.00
0 10 20 30 40
Time
Allocation
Case 6: γ = −4 , c = 500
0.00
0.25
0.50
0.75
1.00
0 10 20 30 40
Time
Allocation
Case 7: γ = −6 , c = −500
0.00
0.25
0.50
0.75
1.00
0 10 20 30 40
Time
Allocation
Case 8: γ = −6 , c = 0
0.00
0.25
0.50
0.75
1.00
0 10 20 30 40
Time
Allocation
Case 9: γ = −6 , c = 500
Scenario Base case High return Low return High volatility Low volatility
Figure 6.7: Asset allocation for different financial market scenarios.
Notes: Each panel represents a unique combination of risk aversion and baseline benefit parameter. The lines
show the allocation to risky assets for: the base case with µ = 0.06 and σ = 0.15, the more favourable with
µ = 0.10 and σ = 0.15, the less favourable return scenario with µ = 0.04 and σ = 0.15, the high-volatility
scenario with µ = 0.06 and σ = 0.30, and the low-volatility scenario with µ = 0.06 and σ = 0.075.
– The base case with m = 85 and b = 10 (life expectancy of 82.79 years).
– A shorter lifespan scenario with m = 80 and b = 10 (life expectancy of 79.18 years).
– A longer lifespan scenario with m = 90 and b = 10 (life expectancy of 86.75 years).
– A greater dispersion scenario with m = 85 and b = 20 (life expectancy of 86.74 years).
6.3.2 Optimal hurdle rate
Figure 6.8 illustrates how different mortality settings influence the optimal hurdle rate.
When lifespan is shorter, the pool tends to adopt a lower hurdle rate, particularly under
high risk aversion (i.e., γ = −6). Although a shorter expected lifespan leads to higher
annual payouts for survivors due to lower annuity factors, the overall payment horizon is
43
γ = −2 γ = −4 γ = − 6
−500 0 500 −500 0 500 −500 0 500
0.01
0.02
0.03
Baseline c
Optimal hurdle rate
Scenario Base case Shorter lifespan Longer lifespan Greater dispersion
Figure 6.8: Optimal hurdle rate for different mortality parameters.
Notes: Each panel corresponds to a risk aversion level γ. The lines represent varied Gompertz parameters:
the base case with m = 85 and b = 10, a shorter lifespan scenario with m = 80 and b = 10, a longer lifespan
scenario with m = 90 and b = 10, and a greater dispersion scenario with m = 85 and b = 20.
reduced. This results in a lower optimal hurdle rate, especially when stability is prioritized.
In contrast, under lower risk aversion, the deviation from the baseline is minimal, as the
pool is more tolerant of volatility in benefits.
By comparison, longer lifespans or greater mortality dispersion extend or introduce uncertainty into the payout period. These scenarios generally lead to higher hurdle rates to
ensure sufficient funding across a prolonged retirement horizon. This effect is more pronounced under low or moderate risk aversion. However, when risk aversion is high and
baseline benefits are low (e.g., γ = −6, c = −500), the hurdle rate may dip slightly below
the baseline, reflecting a stronger emphasis on maintaining stable payouts rather than pursuing higher returns. Overall, these findings highlight how longevity risk shapes hurdle rate
selection, requiring the pool to balance long-term benefit levels with predictability.
6.3.3 Mortality experience adjustment
Mortality parameter changes affect the MEA, which adjusts benefit levels based on deviations between actual and expected survivors, while the IEA remains unchanged. A shorter
lifespan accelerates the decline in the number of members, while a longer lifespan or a
greater dispersion alters the timing and magnitude of survivor deviations.
44
1.00
1.01
1.02
1.03
0 10 20 30 40 50
Time
MEA
Scenario Base case Shorter lifespan Longer lifespan Greater dispersion
Figure 6.9: Mortality experience adjustment for different mortality parameters.
Notes: This figure reports the average MEA for: the base case with m = 85 and b = 10, a shorter lifespan
scenario with m = 80 and b = 10, a longer lifespan scenario with m = 90 and b = 10, and a greater dispersion
scenario with m = 85 and b = 20.
As shown in Figure 6.9, the average MEA remains stable initially but rises as membership deviates from expectations. A shorter lifespan leads to the fastest increase, reflecting
survivor depletion. A longer lifespan delays this effect, since participants remain in the pool
longer, slowing the divergence from expected mortality. Greater dispersion postpones the
rise in the MEA even further, as some members die earlier while others survive significantly
longer, causing the pool’s actual mortality pattern to align with its expectation for a longer
period.
6.3.4 Benefit levels
Since we observe no changes in the investment strategies on account of changes in mortality 