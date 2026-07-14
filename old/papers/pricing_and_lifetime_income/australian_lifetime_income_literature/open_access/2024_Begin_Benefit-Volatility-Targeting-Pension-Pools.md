https://www.actuaries.org/app/uploads/2025/06/AFIRERM_Paper_Begin_Benefit_Volatility_Targeting_Strategies_Lifetime_Pension_Pools.pdf
→ https://www.actuaries.org/app/uploads/2025/06/AFIRERM_Paper_Begin_Benefit_Volatility_Targeting_Strategies_Lifetime_Pension_Pools.pdf
Content-Type: application/pdf

Insurance Mathematics and Economics 118 (2024) 72–94
Available online 6 June 2024
0167-6687/© 2024 The Author(s). Published by Elsevier B.V. This is an open access article under the CC BY-NC license (http://creativecommons.org/licenses/bync/4.0/).
Contents lists available at ScienceDirect
Insurance: Mathematics and Economics
journal homepage: www.elsevier.com/locate/ime
Benefit volatility-targeting strategies in lifetime pension pools ✩
Jean-François Bégin ∗, Barbara Sanders
Department of Statistics and Actuarial Science, Simon Fraser University, 8888 University Drive, Burnaby, British Columbia, V5A 1S6, Canada
A R T I C L E I N F O A B S T R A C T
JEL classification:
G22
G11
J11
Keywords:
Pooled annuity
Investment risk
Longevity risk
Investment-linked annuity benefits
Mortality credits
Lifetime pension pools—also known as group self-annuitization plans, pooled annuity funds, and retirement
tontines in the literature—allow retirees to convert a lump sum into lifelong income, with payouts linked to
investment performance and the collective mortality experience of the pool. Existing literature on these pools
has predominantly examined basic investment strategies like constant allocations and investments solely in riskfree assets. Recent studies, however, proposed volatility targeting, aiming to enhance risk-adjusted returns and
minimize downside risk. Yet they only considered investment risk in the volatility target, neglecting the impact
of mortality risk on the strategy. This study thus aims to address this gap by investigating volatility-targeting
strategies for both investment and mortality risks, offering a solution that keeps the risk associated with benefit variation as constant as possible through time. Specifically, we derive a new asset allocation strategy that
targets both investment and mortality risks, and we provide insights about it. Practical investigations of the strategy demonstrate the effectiveness and robustness of the new dynamic volatility-targeting approach, ultimately
leading to enhanced lifetime pension benefits.
1. Introduction
As the prevalence of guaranteed pension arrangements decreases worldwide, there is a growing expectation that flexible retirement schemes
like lifetime pension pools will gain popularity. Lifetime pension pools allow retiring individuals to convert a lump sum into income for life. Unlike
traditional pension plans, these pools do not provide a fixed or guaranteed level of income. Instead, the pension payouts are contingent upon the
performance of the underlying investments and the collective mortality experience of the pool members.
Various arrangements, products, and monikers fit the broad description of lifetime pension pools in the literature: group self-annuitization (GSA)
plans (Piggott et al., 2005; Valdez et al., 2006; Qiao and Sherris, 2013; Hanewald et al., 2013), pooled annuity funds (Stamos, 2008; Donnelly et
al., 2013), annuity overlay funds (Donnelly et al., 2014; Donnelly, 2015), retirement tontines (Milevsky and Salisbury, 2015, 2016; Chen and Rach,
2019; Fullmer, 2019; Iwry et al., 2020; Gemmo et al., 2020; Weinert and Gründl, 2021; Chen et al., 2021), variable annuities (Balter and Werker,
2020; Balter et al., 2020; Dees et al., 2021), and variable payout annuities (Horneff et al., 2010; Boyle et al., 2015). Note that all these designs can
be viewed as implicit or explicit tontines.1
The design of these pools has primarily been examined within the context of elementary investment strategies, like constant, static allocations
and investment strategies that only involve risk-free assets. Yet other cutting-edge strategies might improve the risk–reward profile of the pool
✩ The authors would like to thank the editors and two anonymous referees for their valuable suggestions and comments on the research project. Bégin wishes to
acknowledge the financial support of Natural Sciences and Engineering Research Council of Canada (Grant No. RGPIN-2018-04337) and the Canadian Institute of
Actuaries (Grant No. AC-ARG-23-01). Bégin and Sanders also acknowledge the financial support of Simon Fraser University. This research was enabled in part by
support provided by the Digital Research Alliance of Canada (www.alliancecan.ca).
* Corresponding author.
E-mail addresses: jbegin@sfu.ca (J.-F. Bégin), bsanders@sfu.ca (B. Sanders). 1 Implicit tontines promise to pay the participants an income for life, but longevity credits are not explicitly allocated to the participants; explicit tontines explicitly
allocate longevity credits to the individual accounts of participants (see Bernhardt and Donnelly, 2019, for more details).
https://doi.org/10.1016/j.insmatheco.2024.05.006
Received 21 December 2023; Received in revised form 23 May 2024; Accepted 24 May 2024
Insurance Mathematics and Economics 118 (2024) 72–94
73
J.-F. Bégin and B. Sanders
assets and, in turn, yield better benefits for members. Recently, Olivieri et al. (2022) and Li et al. (2022) proposed a volatility-targeting approach
for lifetime pension pools.2 Broadly speaking, the main aim of volatility targeting is to manage a portfolio’s risk exposure in such a way that its
volatility is as close to the target as possible. It is argued that this strategy can improve the portfolio returns—increase the average and reduce the
likelihood of downside risk—because of the well-documented negative relationship between returns and volatility (i.e., Black’s leverage effect). Put
simply, as volatility increases, returns are expected to be negative, thus justifying a smaller allocation to the risky asset. When volatility decreases,
on the other hand, returns are expected to be positive, meaning that it is beneficial to invest more aggressively in the risky asset.
Olivieri et al. (2022) and Li et al. (2022) provide guidance on adjusting the asset allocation strategy to target some volatility levels in the context
of lifetime pension pools, improving the investment performance while reducing volatility and downside risk. The conclusions of the two articles
are similar as they both find that it is beneficial to target volatility. Their methodology, however, only considers investment risk in the volatility
target, exposing the pool to uncontrolled mortality risk that can become quite large as pool members get older.3 As these lifetime pension pools
become more popular, understanding how to simultaneously cope with both investment and mortality risks is of paramount importance for the
sustainability of these arrangements, especially because members bear all the risks.
In this research, we investigate volatility targeting of the total benefit adjustment—including both investment and mortality risk—so that the
risk associated with benefit variation is kept as constant as possible through time. This article offers two contributions to the existing body of
literature: one of a theoretical nature and the other applied. On the one hand, we derive an asset allocation strategy that considers both investment
and mortality risks at the same time. This derivation is based on simple assumptions used to proxy the benefit volatility, consistent with the idea
that the actual data generating process is unknown to the pool operator and she needs to use approximations to identify the volatility. Specifically,
we assume that the number of survivors in the pool is given by a binomial distribution with a survival probability based on past information and
that future volatility is obtained via a nonparametric heterogeneous autoregressive (HAR) model based on high-frequency returns.4 The HAR model
is selected because it is simple to use and produces reliable volatility forecasts.
On the other hand, we investigate the implementation of the volatility-targeting strategy. This assessment relies on a state-of-the-art data
generating process—different than the model used by the pool operator to determine the asset allocation. The risk-free rate of return relies on a
three-factor Vasicek (1977) model in the spirit of Babbs and Nowman (1999). Risky asset returns are modelled via an affine continuous-time twofactor stochastic volatility model that extends the double Heston model of Christoffersen et al. (2009) by allowing for jumps. This model captures
many of the well-known stylized facts in finance. Systematic longevity risk is captured by a Plat (2009) variant of the well-known Cairns et al.
(2006) model which allows for the addition of a nonparametric baseline age effect as well as random future improvements modelled via two period
effects. This age–period–cohort (APC) model is able to capture past and future variations in life expectancies. Idiosyncratic mortality risk is also
accounted for.
Based on random investment and mortality scenarios, we find that the new dynamic volatility-targeting strategy performs well and provides a
steady stream of benefits. The volatility-targeting strategy substantially reduces benefit risk by cutting the risky asset allocation when the benefit
volatility—either stemming from the risky asset volatility or mortality-induced risk—is high. Multiple tests show that the results are robust to the
inclusion of death benefits, smaller pool sizes, and different exogenous volatility targets. We also consider some practical limitations that might
hinder the applicability of the volatility-targeting strategy presented in the study. Specifically, we investigate the impact of leverage constraints,
brokerage fees, and rebalancing frequencies. The bulk of our results is robust to these changes in our assumptions.
The remainder of the article is organized as follows. Section 2 presents the assumed data generating process used to model financial asset returns
and mortality scenarios. The design of the stylized lifetime pension pool under consideration is explained in Section 3. Section 4 describes the process
used by the pool operator to target benefit volatility. The implementation of the strategy is assessed in Section 5. Section 6 investigates practical
limitations of the volatility-targeting strategy. Section 7 concludes, while proofs of the various propositions and additional results are provided in
the supplementary material.
2. The assumed data generating process
This study relies on two different sets of models: a first set of models that allows us to generate future realizations of the real world—the assumed
data generating process—and a second set that is used by the pool operator to target volatility. It is important to stress at this stage that we do
not assume the operator would know the true generating process, and having two sets of models capture this important dimension in our problem.
Indeed, understanding the world requires more complicated equations and models while end-users commonly rely on simpler, ad hoc representations
of the reality.
This section covers the first set of assumed data generating processes, whereas Section 4 provides details on the second set.
2 The literature on volatility targeting goes back more than two decades and is overwhelmingly positive (see, e.g., Fleming et al., 2001; Hallerbach, 2012;
Hocquard et al., 2013; Moreira and Muir, 2017; Doan et al., 2018; Harvey et al., 2018). The latter studies have demonstrated enhanced Sharpe ratios, reduced
maximum drawdowns, and a more consistent risk profile across a diverse range of risk assets and over different time periods. Some recent papers by Liu et al.
(2019), Bongaerts et al. (2020), and Mylnikov (2021), however, identified biases in some of these studies—the use of future information in defining the strategy
benchmark and the use of risk-adjusted return measures to gauge the profitability of the strategy, among others. Note that our implementation of the strategy does
not suffer from these two biases as we do not rely on future information, and we do not use risk-adjusted return measures. 3 Both articles also considered ad hoc methods to reduce the allocation for older members, without providing a solution that is consistent with the actual mortality
risk profile of the pool. 4 Being able to accurately forecast volatility is of paramount importance for volatility targeting. Over the years, many parametric models were proposed to forecast
volatility in the literature, like the autoregressive conditional heteroscedasticity (ARCH) model of Engle (1982), the generalized ARCH model of Bollerslev (1986),
and exponentially weighted moving average-based models. These models were used by Mylnikov (2021) and Olivieri et al. (2022) in the context of volatility
targeting, among others. Some other approaches—so-called nonparametric models—rely on realized volatility (i.e., sum of squared intraday high-frequency returns
taken over a day). These powerful approaches, pioneered by Corsi (2009), use HAR models to forecast volatility (see Andersen et al., 2007; Busch et al., 2011; Corsi
and Renò, 2012; Audrino and Knaus, 2016, for other contributions on the topic). In the context of volatility targeting, Li et al. (2022) used realized volatility to
forecast volatility.
Insurance Mathematics and Economics 118 (2024) 72–94
74
J.-F. Bégin and B. Sanders
2.1. A model for financial asset returns
Financial asset returns and prices are important puzzle pieces to grasp investment risk in lifetime pension pools. For simplicity’s sake, we assume
that the pool can invest in two assets: a risk-free asset and a risky asset. The risk-free rate of return is modelled using a three-factor Vasicek (1977)
term structure model in the spirit of Babbs and Nowman (1999), whereas the risky asset is modelled using an affine continuous-time two-factor
stochastic volatility model that extends the double Heston model of Christoffersen et al. (2009) by allowing for jumps. This state-of-the-art model
captures many of the important stylized facts of (risk-free) interest rate and stock markets (see, e.g., Litterman and Scheinkman, 1991; Cont, 2001,
for a discussion on important stylized facts). The interest rate term structure has many factors, capturing the level, slope, and curvature. The risky
asset model has more than one volatility factor, allowing for more flexible variance dynamics; it also permits for jumps in both prices and its
variance—a much-needed feature in asset price modelling (see, e.g. Bates, 1996; Eraker et al., 2003).
Mathematically speaking, we consider a continuous-time economy on the time span  = [0, 𝑇 ]. The uncertainty is modelled with the probability
space (Ω,,ℙ) endowed with the filtration 𝔽 = {𝑡
}
𝑡∈ (to be formally defined later), where ℙ represents the physical (real-world) measure. The
risk-free asset dynamics, assumed to be the money market account and denoted by 𝑃 = {𝑃𝑡
}
𝑡∈ , is given by the following equation:
𝑑𝑃𝑡
𝑃𝑡
= 𝑟𝑡 𝑑𝑡, (1)
where the short rate at time 𝑡 is defined by
𝑟𝑡 = 𝜃𝑟 + 𝑥1,𝑡 + 𝑥2,𝑡 + 𝑥3,𝑡, (2)
and
𝑑𝑥1,𝑡 = − 𝜁𝑥1 𝑥1,𝑡 𝑑𝑡 + 𝜎𝑥1 𝑑𝑊𝑥1,𝑡, (3)
𝑑𝑥2,𝑡 = − 𝜁𝑥2 𝑥2,𝑡 𝑑𝑡 + 𝜎𝑥2 𝑑𝑊𝑥2,𝑡, (4)
𝑑𝑥3,𝑡 = − 𝜁𝑥3 𝑥3,𝑡 𝑑𝑡 + 𝜎𝑥3 𝑑𝑊𝑥3,𝑡, (5)
for which the vector [
𝑊𝑥1 𝑊𝑥2 𝑊𝑥3
]⊤
is a three-dimensional standard Brownian motion with
𝑑⟨𝑊𝑥1,𝑊𝑥2⟩𝑡 = 𝜌𝑥1,𝑥2 𝑑𝑡, 𝑑⟨𝑊𝑥1,𝑊𝑥3⟩𝑡 = 𝜌𝑥1,𝑥3 𝑑𝑡, and 𝑑⟨𝑊𝑥2,𝑊𝑥3⟩𝑡 = 𝜌𝑥2,𝑥3 𝑑𝑡
under the physical measure. We also assume that 𝑃0 = 1 for convenience and without loss of generality.
We denote the risky asset price process by 𝑆 = {𝑆𝑡
}
𝑡∈ , and the dynamics of this asset are given by the following stochastic differential equations
(SDEs):
𝑑𝑆𝑡
𝑆𝑡−
= (𝑟𝑡 + 𝜉
)
𝑑𝑡 +
√
𝑉1,𝑡− 𝑑𝑊𝑆1,𝑡 +
√
𝑉2,𝑡 𝑑𝑊𝑆2,𝑡 + 𝑑𝐽𝑆,𝑡, (6)
𝑑𝑉1,𝑡 =𝜁𝑉1
(
𝜃𝑉1 − 𝑉1,𝑡−
)
𝑑𝑡 + 𝜎𝑉1
√
𝑉1,𝑡− 𝑑𝑊𝑉1,𝑡 + 𝑑𝐽𝑉1,𝑡, (7)
𝑑𝑉2,𝑡 =𝜁𝑉2
(
𝜃𝑉2 − 𝑉2,𝑡)𝑑𝑡 + 𝜎𝑉2
√
𝑉2,𝑡 𝑑𝑊𝑉2,𝑡, (8)
where the vector [
𝑊𝑆1 𝑊𝑆2 𝑊𝑉1 𝑊𝑉2
]⊤
is a four-dimensional standard Brownian motion under the physical measure with
𝑑⟨𝑊𝑆1,𝑊𝑉1⟩𝑡 = 𝜌𝑆1,𝑉1 𝑑𝑡 and 𝑑⟨𝑊𝑆2,𝑊𝑉2⟩𝑡 = 𝜌𝑆2,𝑉2 𝑑𝑡,
while the remaining pairs of Brownian motions are independent of each other. This assumption allows our risky asset returns to be correlated with
the variance dynamics, capturing the well-known leverage effect. The drift coefficient of the risky asset dynamics contains the short rate 𝑟𝑡 defined
in Equation (2) and a constant, deterministic equity risk premium parameter 𝜉 for simplicity’s sake. Note that the equity risk premium parameter
needs to be strictly positive—investors require a higher expected return for investing in risky assets due to the greater risk of volatility and potential
losses.
Both volatility factor processes allow for mean reversion and square-root diffusion; parameters 𝜁𝑉1 and 𝜁𝑉2 control the speed of mean reversion,
and parameters 𝜃𝑉1 and 𝜃𝑉2 are the long-run values of the first and second volatility processes, respectively. The volatility of the variance parameters
are denoted by 𝜎𝑉1 and 𝜎𝑉2 for the first and second processes, respectively.5
The risky asset jump component is defined as a compound Poisson process; that is,
𝐽𝑆,𝑡 =
∑𝑁𝑡
𝑛=1
𝑍𝑆,𝑛,
where the timing of the jumps is modelled by a Poisson process {
𝑁𝑡
}
𝑡∈ with a constant intensity 𝜆. The size of these jumps, 𝑍𝑆,𝑛, is independent
and identically distributed (iid) and normally distributed with mean 𝛼 and variance 𝛿2.
6
5 The two processes 𝑉1 and 𝑉2 are guaranteed to stay positive, as it is commonly the case with square-root diffusions. Note that if the Feller condition is not
satisfied—which is commonly the case in practice—then the processes can reach zero. If this happens, then the variance will instantly move away from zero because
the diffusive term will be larger than zero at that instant. 6 Similar return jump processes have been used by Bates (1996), Bakshi et al. (1997), Duffie et al. (2000), Pan (2002), Eraker et al. (2003), Johannes et al. (2009),
Bégin (2020), among others.
Insurance Mathematics and Economics 118 (2024) 72–94
75
J.-F. Bégin and B. Sanders
Regarding variance jumps, these are also governed by a compound Poisson process
𝐽𝑉 ,𝑡 =
∑𝑁𝑡
𝑛=1
𝑍𝑉 ,𝑛,
where jumps happen in both the asset price and the variance at the same time; that is, the Poisson process {
𝑁𝑡
}
𝑡∈ representing the number of
jumps is the same in both Equations (6) and (7).7 Variance jump sizes {
𝑍𝑉 ,𝑛}∞
𝑛=1 are iid and exponentially distributed with mean 𝜈.
8
The risk-free asset model is estimated using the term structure of daily US yields between 1990–2021 from the Federal Reserve System’s H.15
reports. Similar to Babbs and Nowman (1999), the model is estimated using a filtering technique based on the well-known Kalman (1960) filter.
Section SM.A of the Supplementary Material reports additional details on the data, the estimation methodology, and the estimated parameters.
The risky asset model is estimated using Standard & Poors 500 stock index data between 1990–2021. The estimation relies on a bootstrap particle
filter in the spirit of Gordon et al. (1993) as recently implemented by Bégin et al. (2020) and Amaya et al. (2022). More details on the data, the
estimation methodology, and the estimated parameters are available in Section SM.B of the Supplementary Material.
2.2. The mortality model
Longevity and mortality are key risks for lifetime pension pools. Guided by common sense, adding more members to a pool has a positive effect
in terms of diversification (see, e.g., Bernhardt and Donnelly, 2021). Yet the potential for mortality improvements adds additional risk to the mix,
reducing benefit payments for pool members.
To capture these important dimensions, we model both systematic longevity and idiosyncratic mortality risks. We propose using a stochastic
mortality model that accounts for improvements in the spirit of Lee and Carter (1992) and Cairns et al. (2006). Specifically, we use a continuoustime version of a two-factor APC model that relies on the CBD-X framework (see, e.g., Dowd et al., 2020; Bégin et al., 2023b). The model produces
plausible forecasts that are consistent with historical and biological trends.
2.2.1. Systematic longevity risk
In this study, we rely on the following dynamics for the time-𝑡 central death rate for age 𝑥:
log (𝑚𝑥,𝑡)
=𝛼⌊𝑥⌋ + 𝜅1,𝑡 + 𝜅2,𝑡 (
⌊𝑥⌋ − 𝑥̄
)
(9)
where ⌊𝑥⌋ denotes the greatest integer less than or equal to 𝑥 and 𝑥̄ represents the (constant) average of the ages used in the sample. This model is
a Plat (2009) variant of the well-known Cairns et al. (2006) model which allows for the addition of a nonparametric baseline age effect, 𝛼⌊𝑥⌋.
9 We
assume that the baseline age effect is constant over integer ages to mimic the behaviour of typical discrete-time models.
Once the age effect is accounted for, the remainder of the log death rates is explained by a linear function of age. The first period effect 𝜅1,𝑡
picks up the time changes in the mortality level, and the second period effect 𝜅2,𝑡 captures changes in the slope of the log-mortality curve from the
baseline. It is well known that this assumption is justified for relatively older ages but not for younger ages (Cairns et al., 2006).
Following Plat (2009), we assume that the first period effect is modelled by a random walk and the second period effect by a mean-reverting
(autoregressive) model with no drift, which are given by the following SDEs in continuous time:
𝑑𝜅1,𝑡 =𝜃𝜅1 𝑑𝑡 + 𝜎𝜅1 𝑑𝑊𝜅1,𝑡, (10)
𝑑𝜅2,𝑡 = − 𝜁𝜅2 𝜅2,𝑡 𝑑𝑡 + 𝜎𝜅2 𝑑𝑊𝜅2,𝑡, (11)
where 𝜃𝜅1 is the drift of the random walk, 𝜁𝜅2 is the speed of mean reversion, and 𝜎𝜅1 and 𝜎𝜅2 are variance parameters for the first and second period
effects, respectively. Moreover, [
𝑊𝜅1 𝑊𝜅2
]⊤
is a two-dimensional standard Brownian motion with 𝑑⟨𝑊𝜅1,𝑊𝜅2⟩𝑡 = 𝜌𝜅1,𝜅2 𝑑𝑡 under the physical
measure. All mortality-related Brownian motions are mutually independent of those introduced in Section 2.1.
10,11
The model is estimated using a filtering technique based on the Kalman (1960) filter (see Fung et al., 2017; Bégin et al., 2023b, for applications of
filtering methods in the estimation of mortality modelling). We rely on US data from 1970 to 2021 for both females and males (combined) extracted
from the Human Mortality Database. We consider ages from 65 to 104 in the estimation. More details on the estimation methodology, the data, and
the results are available in Section SM.C.1 of the Supplementary Material.
7 Many studies reported co-jumps in asset price and variance dynamics over the past 20 years, thus justifying our use of the same Poisson process to generate
jumps in both processes (see, e.g., Pan, 2002; Eraker et al., 2003; Eraker, 2004; Jacod and Todorov, 2009; Bandi and Renò, 2016, for more details). 8 Bates (2000), Duffie et al. (2000), Pan (2002), Eraker et al. (2003), and Todorov and Tauchen (2011) provide evidence for the presence of positive jumps in the
variance process. 9 In his paper, Plat (2009) considers a third period effect in addition to a cohort effect in his model. As we only consider older ages, this third effect is not needed
here.
10 The filtration 𝔽 is constructed from the sigma-fields
𝑡 = 𝜎
({
𝑊𝑥1 ,𝑠,𝑊𝑥2,𝑠,𝑊𝑥3,𝑠,𝑊𝑆1 ,𝑠,𝑊𝑆2 ,𝑠, 𝐽𝑆,𝑠,𝑊𝑉1,𝑠,𝑊𝑉2,𝑠, 𝐽𝑉 ,𝑠,𝑊𝜅1,𝑠,𝑊𝜅2,𝑠}
0≤𝑠≤𝑡
)
, 𝑡 ∈  ,
containing the past and present Brownian motions and jump components. It is the model filtration generated by the various stochastic processes defined in this
section.
11 Appendix A extends these simple dynamics and considers a long-memory model for the period effects in the spirit of Zhou and Li (2023).
Insurance Mathematics and Economics 118 (2024) 72–94
76
J.-F. Bégin and B. Sanders
2.2.2. Idiosyncratic mortality risk
Once death rates are generated from Equation (9), we can recover survival probabilities using the following relationship:
𝑠𝑝𝑥,𝑡 = exp
⎛
⎜
⎜
⎝
−
𝑠
∫
0
𝑚𝑥+𝑢,𝑡+𝑢 𝑑𝑢
⎞
⎟
⎟
⎠
. (12)
These ex post survival probabilities can be used to generate pool members’ survival and death in the context of our data generating process.12
Specifically, we model idiosyncratic mortality risk via Bernoulli random variables as typically done in the literature. For an individual aged 𝑥 who
is alive at time 𝑡, we assume that they survive until time 𝑡 + 𝑠 with probability 𝑠𝑝𝑥,𝑡 and die with probability 1 − 𝑠𝑝𝑥,𝑡.
3. Lifetime pension pool design
3.1. Benefits and fund dynamics of lifetime pension pools
We select a very simple structure for the dynamics of our lifetime pension pool. The pool operation is similar to that explained in Piggott et al.
(2005), Qiao and Sherris (2013), and Olivieri et al. (2022) in the context of GSA plans. It is also reminiscent of the benefit update rule used by the
College Retirement Equities Fund in the US and the University of British Columbia Faculty Pension Plan in Canada.
Each member brings an initial capital amount of 𝐾 at inception. The total pool fund then amounts to 𝐹0 = 𝐿0 𝐾 at time 0, where 𝐿0 is the initial
number of members joining the plan at inception. For simplicity, let us assume that all members joining have the same age at inception and that
they are part of the same population which share similar mortality experience.
Through time, the lifetime pension pool fund changes based on investment returns, the benefits paid out to survivors, and potential death
benefits. The non-guaranteed benefits, which are paid to survivors at the beginning of each period in our framework, are a function of the mortality
and investment experience. In all generality, we assume that members receive 𝑚 payments each year, as long as they are alive.
Using typical actuarial notation, let 𝑎̈
(𝑚)
𝑥,𝑡 denote the actuarial value at time 𝑡 of a whole life annuity due making 𝑚 payments per year of ℎ = 1
𝑚
dollars to a member aged 𝑥 using the valuation basis applicable at time 𝑡 such that
𝑎̈
(𝑚)
𝑥,𝑡 = Eℙ
[
∑∞
𝑠=0
ℎ𝑠ℎ𝑝𝑥,𝑡 𝑒−𝑦𝑠ℎ
|
|
|
|
|
𝑡
]
, (13)
where 𝑦 is the (continuously compounded) hurdle rate used to compute the annuity price.13 The hurdle rate significantly impacts the annual benefits
paid to retirees as shown below—a lower hurdle rate reduces the current benefit but increases the likelihood of future benefit increases, and vice
versa.14
The total benefit amount paid by the lifetime pension pool at time 𝑡 is
𝐵𝑡 = ℎ
𝐹𝑡
𝑎̈
(𝑚)
𝑥,𝑡
𝟏{𝐿𝑡≥1},
where 𝟏{𝐿𝑡≥1} is the indicator function worth 1 if there is at least one member left in the pool, and zero otherwise. Each surviving member’s benefit
amount is therefore given by
𝑏𝑡 = 𝐵𝑡
𝐿𝑡
(14)
at time 𝑡 as long as the pool size is strictly positive.
We also include the possibility for a death benefit, similar to Olivieri et al. (2022). Indeed, as suggested by many (see Brown, 2009, and references
therein), individuals have bequest preferences. Specifically, we assume that each of the 𝐿𝑡−ℎ − 𝐿𝑡 members who died between 𝑡 − ℎ and 𝑡 receives a
fraction
𝛾
1
𝐿𝑡−ℎ
of the fund value 𝐹𝑡− at the end of the period, where 𝛾 is a proportion of the decedent’s fund value paid to their estate after the member’s death,
and 𝐿𝑡−ℎ is the number of survivors at time 𝑡 − ℎ. Just like living benefits, the amount of death benefits is not guaranteed. Additionally, while
death benefits fulfil members’ desires for passing on their assets, they concurrently diminish the potential for the lifetime pension pool to achieve an
optimal pooling effect: the entire death benefit is retained by the pool when 𝛾 = 0, leading to the consolidation of individual longevity risks within
the fund, whereas no mortality credits remain when 𝛾 = 1. We therefore expect 𝛾 to be strictly less than one.
The pool can invest in the two assets introduced above—the risky asset 𝑆 and the risk-free asset 𝑃 .
15 The allocation can be changed through
time; specifically, a proportion 𝜔𝑡 is invested in the risky asset and 1 − 𝜔𝑡 in the risk-free asset at the beginning of the period [𝑡 − ℎ,𝑡), meaning that
the fund dynamics can be described as follows:
12 These are realized survival probabilities—not ex ante or expected probabilities—because we are explaining our data generating process here, and not the process
used by the pool operator to understand risk. This important distinction will be further explained in Section 4. 13 The annuity price of Equation (13) is calculated in semi-closed-form solution for the model of Section 2.2. See Section SM.C.2 of the Supplementary Material,
Bégin et al. (2023a), and Bégin et al. (2024) for more details. 14 In this study, we employ a constant hurdle rate that is consistent with the long-term expected returns on the investment portfolio, leading to a level expected
benefit stream. A different hurdle rate could change the expected benefit stream by building potential for inflation protection, among others (Bégin and Sanders,
2023). 15 In a robustness test, we consider long-term zero-coupon bonds as an alternative risk-free asset instead of the money market account. For more details on this
test, refer to Section SM.E of the Supplementary Material.
Insurance Mathematics and Economics 118 (2024) 72–94
77
J.-F. Bégin and B. Sanders
𝐹𝑡 =
(
𝐹𝑡−ℎ − 𝐵𝑡−ℎ
) (
𝜔𝑡
𝑆𝑡
𝑆𝑡−ℎ
+ (1 − 𝜔𝑡
) 𝑃𝑡
𝑃𝑡−ℎ
)
⏟⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏟⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏟
𝐹𝑡−
(
1 − 𝛾
𝐿𝑡−ℎ − 𝐿𝑡
𝐿𝑡−ℎ
)
. (15)
As 𝐿𝑡−ℎ −𝐿𝑡 represents the number of decedents between time 𝑡−ℎ and 𝑡, the term −𝛾 𝐹𝑡− 𝐿𝑡−ℎ−𝐿𝑡
𝐿𝑡−ℎ
is negative when members die (and nil otherwise)
and denotes an outflow for the lifetime pension pool fund.
3.2. Benefit adjustments
Equation (15) is a roll-forward of the pool’s fund using actual benefit and death payments as well as investment returns. Assuming that there is
at least one member in the pool at time 𝑡 − ℎ, Equation (15) can be expressed as a function of the surviving members’ benefit amount at time 𝑡 − ℎ:
𝐹𝑡 =𝑚 𝑏𝑡−ℎ 𝐿𝑡−ℎ
(
𝑎̈
(𝑚)
𝑥−ℎ,𝑡−ℎ − ℎ
) (
𝜔𝑡
𝑆𝑡
𝑆𝑡−ℎ
+ (1 − 𝜔𝑡
) 𝑃𝑡
𝑃𝑡−ℎ
) (1 − 𝛾
𝐿𝑡−ℎ − 𝐿𝑡
𝐿𝑡−ℎ
)
=𝑚 𝑏𝑡−ℎ 𝐿𝑡−ℎ 𝑒−𝑦ℎ ℎ𝑝𝑥−ℎ,𝑡−ℎ
⎛
⎜
⎜
⎝
𝑎̈
(𝑚)
𝑥−ℎ,𝑡−ℎ − ℎ
𝑒−𝑦ℎ ℎ𝑝𝑥−ℎ,𝑡−ℎ
⎞
⎟
⎟
⎠
(
𝜔𝑡
𝑆𝑡
𝑆𝑡−ℎ
+ (1 − 𝜔𝑡
) 𝑃𝑡
𝑃𝑡−ℎ
) (1 − 𝛾
𝐿𝑡−ℎ − 𝐿𝑡
𝐿𝑡−ℎ
)
.
We can also express the fund value at time 𝑡 in a prospective fashion:
𝐹𝑡 =𝑚 𝑏𝑡 𝐿𝑡 𝑎̈
(𝑚)
𝑥,𝑡 = 𝑚 𝜂𝑡 𝑏𝑡−ℎ 𝐿𝑡 𝑎̈
(𝑚)
𝑥,𝑡 ,
where 𝜂𝑡 is the time-𝑡 adjustment factor informed by the experience of the pool as long as members are still in the pool (i.e., 𝐿𝑡 ≥ 1).
Equating the retrospective and prospective values for 𝐹𝑡 and assuming the same adjustment is applied to all surviving members’ benefits at time
𝑡 gives
𝜂𝑡 =
(
𝜔𝑡
𝑆𝑡
𝑆𝑡−ℎ
+ (1 − 𝜔𝑡
) 𝑃𝑡
𝑃𝑡−ℎ
)
𝑒−𝑦ℎ
⏟⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏟⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏟
𝐼𝑡
𝐿𝑡−ℎ ℎ𝑝𝑥−ℎ,𝑡−ℎ
𝐿𝑡
𝟏{𝐿𝑡≥1}
⏟⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏟⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏟
𝑀𝑡
𝑎̈
(𝑚)
𝑥−ℎ,𝑡−ℎ − ℎ
𝑎̈
(𝑚)
𝑥,𝑡 𝑒−𝑦ℎ ℎ𝑝𝑥−ℎ,𝑡−ℎ
⏟⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏟⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏟
𝐶𝑡
(
1 − 𝛾
𝐿𝑡−ℎ − 𝐿𝑡
𝐿𝑡−ℎ
)
⏟⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏟⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏞⏟
𝐷𝑡
, (16)
where 𝐼𝑡 is the time-𝑡 investment experience adjustment (IEA) factor, 𝑀𝑡 is the time-𝑡 mortality experience adjustment (MEA) factor, 𝐶𝑡 is the time-𝑡
changed expectation adjustment (CEA) factor, and 𝐷𝑡 is the time-𝑡 death benefit experience adjustment (DBEA) factor.16
3.3. Analysis of benefit volatility with static risky asset allocation
To illustrate the benefit update rule and its impact on the benefit volatility in a simple context, we first assume that the asset allocation stays
constant; that is, 𝜔𝑡 = 𝜔 for all 𝑡. We consider 𝐿0 = 1,000 members at inception, all aged 𝑥 = 65 years old; each member deposits 𝐾 = $1,000,000
in the pool and then receives benefits at the beginning of each month (i.e., 𝑚 = 12). The fund is invested in both risky and risk-free assets so that
the unconditional annualized volatility of the investment portfolio is about 10%.17 The pool uses a hurdle rate of 7.53% that is consistent with the
expected long-run rate of return on the fund. This creates streams of benefits that are, in expectation, level. We do not consider death benefits in
this first illustration (i.e., 𝛾 = 0).
We generate 100,000 investment and mortality scenarios based on the data generating process of Section 2. The top panel of Fig. 1 reports
the annualized volatility of the pool’s benefit adjustment. For the first 25 years or so, the benefit adjustment’s volatility is about 10% and is only
minimally impacted by the MEA and CEA. Indeed, virtually all of the adjustments are related to investment risk, as reported in the bottom panel of
Fig. 1. After 25 years, however, the contribution of the mortality experience adjustment rises, and when members reach about 100 years old, the
MEA becomes the most important contributor to the total benefit adjustment volatility. By the time members reach the age of 110—about 50 years
after inception—the benefit adjustment volatility is almost exclusively impacted by the MEA. Note that the volatility of the CEA increases over time,
too, but impacts the benefit volatility to some lesser extent.
4. Benefit volatility targeting
In this section, we explain the process in which the proportion invested in the risky asset is adjusted to target a given benefit adjustment volatility
level. Indeed, the proportion 𝜔𝑡 can be controlled by the pool operator such that
Varℙ [
𝜂𝑡
|
|𝑡−ℎ
]
= 𝜎2
∗ ℎ, (17)
where 𝜎∗ is the (annualized) exogenous volatility target. By changing its exposure to the risky asset, the pool can control the size of the benefit
fluctuations. Note that the proposed update rule for 𝜔𝑡 is different than Olivieri et al. (2022) and Li et al. (2022), who only considered the volatility
of the investment adjustment factor instead of the whole benefit payment.
In this study, the pool operator is not privy to the (assumed) data generating process—the models of Section 2—and needs to devise practical
means to obtain the variance on the left side of Equation (17) via coarse assumptions and proxies. Specifically, she assumes that:
16 Using common actuarial notation, we know that 𝑎̈
(𝑚)
𝑥−ℎ = ℎ + 𝑒−𝑦ℎℎ𝑝𝑥−ℎ𝑎̈
(𝑚)
𝑥 when mortality is deterministic (see, e.g., Piggott et al., 2005). This relationship,
however, is not satisfied for stochastic mortality models, meaning that 𝐶𝑡 will only equal one if there are no changes to future mortality expectations. 17 Investing 56.8% of the pool’s assets in the risky asset and the rest in the risk-free asset yields an unconditional annualized volatility of about 10%.
Insurance Mathematics and Economics 118 (2024) 72–94
78
J.-F. Bégin and B. Sanders
Fig. 1. Annualized volatility of the benefit adjustments and its constituents for a static allocation in the risky asset. Notes: This figure shows the annualized
volatility of the benefit adjustments (top panel) as well as its constituents (bottom panel) between ages 65 and 110; that is, the investment experience adjustment
(IEA), the mortality experience adjustment (MEA), and the changed expectation adjustment (CEA). The pool has 1,000 members at inception. It invests 56.8% of its
assets in the risky asset, and the remainder in the risk-free asset; this corresponds to an unconditional annualized volatility of about 10%. The simulation begins in
January 2022. This example does not include death benefits (i.e., 𝛾 = 0), so there is no adjustment related to this component.
– The mortality table is static and based on time 𝑡−ℎ information. In other words, the CEA adjustment factor is assumed to be one and the survival
probability over the next period is given by ℎ𝑝̃𝑥−ℎ,𝑡−ℎ = Eℙ [
ℎ𝑝𝑥−ℎ,𝑡−ℎ |
|𝑡−ℎ
]
.
– The number of pool members at time 𝑡 conditional on information at time 𝑡−ℎ is given by a binomial distribution with size parameter 𝐿𝑡−ℎ and
probability parameter ℎ𝑝̃𝑥−ℎ,𝑡−ℎ.
– The time-𝑡 risk-free asset price 𝑃𝑡 based on the information at time 𝑡 − ℎ is given by
𝑃𝑡 = 𝑃𝑡−ℎ 𝑒𝑟̂𝑡ℎ,
where 𝑟̂𝑡 is proxied by the three-month zero-coupon bond yield observed at time 𝑡 − ℎ.
– The time-𝑡 risky asset price 𝑆𝑡 based on the information at time 𝑡 − ℎ is given by
𝑆𝑡 = 𝑆𝑡−ℎ 𝑒𝜀𝑡 , (18)
where 𝜀𝑡 is normally distributed with mean parameter (
𝑟̂𝑡 + ̂
𝜉 − 𝜎̂ 2
𝑡
2
)
ℎ and variance parameter 𝜎̂ 2
𝑡 ℎ. Parameter ̂
𝜉 is set to the (annualized)
sample average equity risk premium based on the risky asset returns. Parameter 𝜎̂ 2
𝑡 is obtained via nonparametric volatility forecasting methods
based on high-frequency returns and information up to time 𝑡 − ℎ (see Section 4.1 for more details).
Let 𝐼̃
𝑡, 𝑀̃ 𝑡, 𝐶̃𝑡, and 𝐷̃𝑡 be the pool operator’s proxies for 𝐼𝑡, 𝑀𝑡, 𝐶𝑡, and 𝐷𝑡, respectively. As a result of the pool operator’s exogenous target 𝜎2
∗,
we have that
𝜎2
∗ ℎ = Var [
𝐼̃
𝑡 𝑀̃ 𝑡 𝐶̃𝑡 𝐷̃𝑡
|
|𝐿𝑡−ℎ, ℎ𝑝̃𝑥−ℎ,𝑡−ℎ, ̂𝑟𝑡, ̂𝜎𝑡
]
= E[𝐼̃2
𝑡
|
|
|
𝑟̂𝑡, ̂𝜎𝑡
]
E
[
𝑀̃ 2
𝑡 𝐷̃ 2𝑡
|
|
|
𝐿𝑡−ℎ, ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
]
− E[𝐼̃
𝑡
|
|
|
𝑟̂𝑡, ̂𝜎𝑡
]2
E
[
𝑀̃ 𝑡 𝐷̃
𝑡
|
|
|
𝐿𝑡−ℎ, ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
]2
(19)
because 𝐶̃
𝑡 = 1 and both 𝑀̃ 𝑡 and 𝐷̃𝑡 are correlated as they depend on 𝐿𝑡.
4.1. Moments of the investment adjustment factor
For the variance related to investment returns, we use a volatility-forecasting methodology that relies on realized volatility and high-frequency
returns. Corsi (2009) showed that a simple HAR model combined with realized volatility statistics produces excellent forecasting performance.18
The basic HAR framework of Corsi has been extended in many directions over the past decade (see, e.g., Andersen et al., 2007; Busch et al., 2011;
Corsi and Renò, 2012, among others).
In this study, we rely on a simple implementation similar to that of Corsi (2009) and Corsi and Renò (2012) which includes the realized volatility
and the leverage effect via the inclusion of negative returns over different horizons. Specifically, we have that
18 The volatility forecasting step is important because it could also significantly improve portfolio returns (see, e.g., Mylnikov, 2021).
Insurance Mathematics and Economics 118 (2024) 72–94
79
J.-F. Bégin and B. Sanders
Table 1
Heterogeneous autoregressive model parameters for volatility forecasts.
Parameter Estimate Standard error
𝜒 0.0292 (0.0011)
𝛽(d) 0.2142 (0.0141)
𝛽(w) 0.3240 (0.0205)
𝛽(m) 0.2110 (0.0163)
𝛾(d) -0.6902 (0.0803)
𝛾(w) -1.6248 (0.2692)
𝛾(m) 2.0637 (0.5531)
Error variance 0.0018
𝑅2 0.6353
Notes: This table reports the parameters of the HAR model used at the inception of the pool. These linear regression parameters are obtained by using the
least squares method. Note that these parameters are updated along each future
path, meaning that new path-specific information is incorporated in the estimates, which are reestimated for all scenarios and each month.
𝜎̂𝑡 =𝜒 + 𝛽(d) RVol(1)
𝑡−ℎ + 𝛽(w) RVol(5)𝑡−ℎ + 𝛽(m) RVol(21)𝑡−ℎ + 𝛾(d)
𝑟
(1)
𝑡−ℎ + 𝛾(w)
𝑟
(5)
𝑡−ℎ + 𝛾(m)
𝑟
(21)
𝑡−ℎ + 𝜖𝑡,
where
– the dependent variable 𝜎̂𝑡 is the (annualized) volatility between time 𝑡 − ℎ and 𝑡, which is proxied by the total realized volatility between time
𝑡 − ℎ and 𝑡,
– the regressors RVol(1)
𝑡−ℎ, RVol(5)𝑡−ℎ, and RVol(21)𝑡−ℎ are the (annualized) past day, week, and month realized volatilities—proxies for the square root
of the quadratic variation of the risky asset price process—respectively, defined as
RVol(𝑞)
𝑡−ℎ =
√√√√
1
𝑞
∑𝑞−1
𝑖=0
RV𝑡−ℎ−𝑖∕252,
and RV𝑡 is the daily realized variance for the day ending at time 𝑡,
– the regressors 𝑟
(d)
𝑡−ℎ, 𝑟
(w)
𝑡−ℎ, and 𝑟
(m)
𝑡−ℎ are the past day, week, and month leverage effect—proxied by the negative part of the observed returns—
respectively, defined as
𝑟
(𝑞)
𝑡−ℎ = min (
0,
1
𝑞
∑𝑞−1
𝑖=0
log( 𝑆𝑡−ℎ−𝑞∕252
𝑆𝑡−ℎ−(𝑞+1)∕252 ))
,
and
– the unobserved random variable 𝜖𝑡 adds noise to the linear relationship between the dependent variable and regressors.19
This model works well and produces reliable estimates of the future volatility. Table 1 reports the parameters of the HAR model used at the inception
of the pool. These linear regression parameters are obtained by using the least squares method; they are consistent with those obtained in other
studies in the literature and with financial intuition. The future volatility is positively related to the last day, week, and month’s volatility (i.e., 𝛽(d),
𝛽(w), and 𝛽(m) are positive). Recent negative returns tend to increase the future volatility; yet more distant negative returns make the future volatility
lower, which is consistent with arguments of mean reversion—a well-known stylized fact of market volatility.20 The coefficient of determination
obtained from the HAR model is very high, with a value of about 64%, leading to reliable volatility forecasts. Note that these parameters are updated
along each future path, meaning that new information is incorporated in the estimates after inception.21
Once the value of 𝜎̂𝑡 is found, we can then use it to calculate the first two moments of 𝐼̃
𝑡. Using the approximation of Equation (18), we obtain
the moments as follows.
Proposition 1. The first two moments of the investment experience adjustment approximation are given by
E
[
𝐼̃
𝑡
|
| 𝑟̂𝑡, ̂𝜎𝑡
]
=𝑒
(
𝑟̂𝑡−𝑦
)
ℎ
(
𝜔𝑡
(
𝑒
̂
𝜉ℎ − 1)
+ 1),
E
[
𝐼̃2
𝑡
|
|
|
𝑟̂𝑡, ̂𝜎𝑡
]
=𝑒2
(
𝑟̂𝑡−𝑦
)
ℎ
(
𝜔2
𝑡
(
𝑒
(
2 ̂𝜉+𝜎̂ 2
𝑡
)
ℎ − 2𝑒
̂
𝜉ℎ + 1)
+ 𝜔𝑡
(
2𝑒
̂
𝜉ℎ − 2)
+ 1).
Proof. See Section SM.D.1 of the Supplementary Material. □
19 The realized variance estimates are computed from high-frequency returns observed every five minutes throughout each day; these returns are obtained via
Tick Data. This study relies on estimates computed using the subsampling methodology of Zhang et al. (2005) from S&P 500 intraday returns. The leverage effect
variables are computed from daily returns obtained from Compustat. 20 Negative returns are typically tied to increases in the spot volatility—a stylized fact known as Black’s leverage effect in finance. Yet, over longer horizons, past
increases in volatility tend to also be accompanied by future decreases via mean reversion of the volatility process. 21 After inception, the estimates of Table 1 vary at each time step and based on each path’s information—mimicking the process used by the pool operator to
update the model parameters based on the most recent data available.
Insurance Mathematics and Economics 118 (2024) 72–94
80
J.-F. Bégin and B. Sanders
4.2. Moments of the mortality and death benefit adjustment factors
In our setting, we assume that the pool operator has access to a static mortality table that includes a mortality improvement scale to capture
mortality improvement—consistent with the data used to estimate the data generating process and the information available at time 𝑡 − ℎ along
each path. This information is used to compute the moments of the mortality and death benefit adjustment factors. Indeed, the product of 𝑀̃ 𝑡 and
𝐷̃
𝑡 can be simplified:
𝑀̃ 𝑡 𝐷̃
𝑡 =
(𝐿𝑡−ℎ
𝐿𝑡 ℎ𝑝̃𝑥−ℎ,𝑡−ℎ (1 − 𝛾) + ℎ𝑝̃𝑥−ℎ,𝑡−ℎ 𝛾
)
𝟏{𝐿𝑡≥1},
which involves the reciprocal of 𝐿𝑡. The first two moments associated with this random variable can be expressed via generalized hypergeometric
functions.
Proposition 2. The first two moments of the mortality and death benefit experience adjustment approximations are given by:
E
[
𝑀̃ 𝑡 𝐷̃
𝑡
|
|
|
𝐿𝑡−ℎ, ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
]
=𝐿2
𝑡−ℎ ℎ𝑝̃
2
𝑥−ℎ,𝑡−ℎ (1−𝛾)
(
1−ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
)𝐿𝑡−ℎ−1
3𝐹2
(
{1, 1, 1−𝐿𝑡−ℎ}, {2, 2}; −ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
1 − ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
)
+ ℎ𝑝̃𝑥−ℎ,𝑡−ℎ 𝛾
(
1 − (1−ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
)𝐿𝑡−ℎ
)
,
E
[
𝑀̃ 2
𝑡 𝐷̃ 2𝑡
|
|
|
𝐿𝑡−ℎ, ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
]
=𝐿3
𝑡−ℎ ℎ𝑝̃
3
𝑥−ℎ,𝑡−ℎ (1−𝛾)
2 (
1−ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
)𝐿𝑡−ℎ−1
4𝐹3
(
{1, 1, 1, 1−𝐿𝑡−ℎ}, {2, 2, 2}; −ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
1 − ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
)
+ 2𝐿2
𝑡−ℎ ℎ𝑝̃
3
𝑥−ℎ,𝑡−ℎ (1−𝛾) 𝛾
(
1−ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
)𝐿𝑡−ℎ−1
3𝐹2
(
{1, 1, 1−𝐿𝑡−ℎ}, {2, 2}; −ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
1 − ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
)
+ ℎ𝑝̃
2
𝑥−ℎ,𝑡−ℎ 𝛾2
(
1 − (1−ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
)𝐿𝑡−ℎ
)
,
where 𝑝𝐹𝑞 ({𝑎1, ..., 𝑎𝑝}, {𝑏1, ..., 𝑏𝑞}; 𝑧) is the generalized hypergeometric function (see Andrews et al., 1999, for more details on this function).
Proof. See Section SM.D.2 of the Supplementary Material. □
4.3. Volatility-targeting-based allocation
Based on Propositions 1 and 2, the pool operator can now solve Equation (19) in closed form using her coarse assumptions.
Proposition 3. Based on the information available to the pool operator, Equation (19) yields the following volatility-targeting allocation:
𝜔𝑡 =
{ −𝑏+
√
𝑏2−4𝑎𝑐
2𝑎 if 𝑏2 ≥ 4𝑎𝑐
0 otherwise , (20)
where
𝑎 = E[
𝑀̃ 2
𝑡 𝐷̃ 2𝑡
|
|
|
𝐿𝑡−ℎ, ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
]
(
𝑒
(
2 ̂𝜉+𝜎̂ 2
𝑡
)
ℎ − 2𝑒
̂
𝜉ℎ + 1)
− E[
𝑀̃ 𝑡 𝐷̃
𝑡
|
|
|
𝐿𝑡−ℎ, ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
]2 (
𝑒2 ̂
𝜉ℎ − 2𝑒
̂
𝜉ℎ + 1)
,
𝑏 = E[𝑀̃ 2
𝑡 𝐷̃ 2𝑡
|
|
|
𝐿𝑡−ℎ, ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
](
2𝑒
̂
𝜉ℎ − 2)
− E[𝑀̃ 𝑡 𝐷̃
𝑡
|
|
|
𝐿𝑡−ℎ, ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
]2 (
2𝑒
̂
𝜉ℎ − 2)
,
𝑐 = E[𝑀̃ 2
𝑡 𝐷̃ 2𝑡
|
|
|
𝐿𝑡−ℎ, ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
]
− E[𝑀̃ 𝑡 𝐷̃
𝑡
|
|
|
𝐿𝑡−ℎ, ℎ𝑝̃𝑥−ℎ,𝑡−ℎ
]2
− 𝜎2
∗ ℎ 𝑒2
(
𝑦−𝑟̂𝑡
)
ℎ.
Proof. See Section SM.D.3 of the Supplementary Material. □
Generally speaking, the quadratic equation has two roots; in our application, when these roots are real, one tends to be positive and the other
negative. We only focus on the positive root because we wish to capture the equity risk premium; indeed, a negative allocation—shorting the risky
asset to buy the risk-free asset—would give a negative return, on average, and lead to an inefficient allocation.
It is also possible that the quadratic equation has no real solution, in which case we set 𝜔𝑡 to zero. This happens in cases when it is impossible
to reduce the allocation to match perfectly the target volatility because the risk associated with mortality is larger than the target. In other words,
when the target cannot be reached, then the second best option for the pool operator is to choose her allocation so that it minimizes the level of
benefit risk.
Fig. 2 shows the impact of the forecast annualized volatility 𝜎̂𝑡, the pool size, and the survival probability on the risky asset allocation of
Equation (20) for a fixed volatility target. As expected, the allocation increases when the forecast volatility is lower—a common relationship in the
context of volatility targeting. The size of the pool impacts the allocation when the survival probability tends to be lower: as the survival probability
is lower for older individuals, we observe a lower allocation to the risky asset for a smaller pool with older members (which already has significant
volatility due to mortality) than for a larger pool with the same members (where the mortality risk has been diversified).
5. Implementation of the strategy
This section presents the results in simple contexts—with and without death benefits. We also consider some robustness tests by changing the
exogenous volatility target and the size of the pool at inception.
Insurance Mathematics and Economics 118 (2024) 72–94
81
J.-F. Bégin and B. Sanders
Fig. 2. Risky asset allocation as a function of the forecast annualized volatility, the pool size, and the survival probability. Notes: This figure shows the
impact of the forecast annualized volatility, the pool size, and the survival probability on the risky asset allocation of Equation (20) for a fixed (annualized) volatility
target of 10%. We consider pool sizes of 250 (top panel), 500 (middle panel), and 1000 members (bottom panel) as well as survival probabilities of 0.91 (solid line),
0.95 (dashed line), and 0.99 (dotted line).
5.1. Comparison with static allocations
Similar to Section 3.3, we consider a pool of 1,000 members at inception, all aged 𝑥 = 65 years old. They each deposit 𝐾 = $1,000,000 in the
pool and receive monthly benefits at the beginning of each month. The fund is invested, again, in both risky and risk-free assets. The allocation to
the risky asset changes every month based on the rule set forth in Proposition 3; the exogenous volatility target 𝜎∗ is set to 10%. The hurdle rate
is set to the same value used in Section 3.3—a value consistent with the expected long-run rate of the fund return under the static case. We do not
consider death benefits in this illustration (i.e., 𝛾 = 0).
For each scenario, we compute the fund value, risky asset allocation, benefits, and their associated adjustments (IEA, MEA, CEA, and DBEA)
recursively for the static strategy and the volatility-targeting strategy also called dynamic allocation throughout this article. Fig. 3 provides a visual
representation of these variables for a representative scenario. The fund value (top-left panel of Fig. 3) naturally decreases over time as benefits are
disbursed to members, aligning with our expectations. The top-right panel of Fig. 3 illustrates how the allocation to the risky asset fluctuates based
on factors such as the pool size, survival probability, and forecast volatility of the risky asset for the next month. Notably, the allocation decreases
when the pool size and survival probability are low or when the forecast volatility is high, as previously discussed in Fig. 2. During the initial 30
years, changes in volatility predominantly influence the allocation. However, as time progresses beyond this period, the allocation to the risky asset
tends to decrease, coinciding with the ageing of the pool and its members.
The annualized benefits (middle-left panel of Fig. 3), expressed in thousands of dollars throughout this article, exhibit variations driven by
investment returns, idiosyncratic mortality within the pool, and systematic longevity resulting from changed expectation in the population. The
investment experience adjustments (middle-right panel of Fig. 3) are directly influenced by the asset allocation. Notably, the IEA tends to display
greater stability when the allocation to the risky asset decreases, and conversely, it becomes more volatile with increased allocation to the risky
asset. This outcome notably chops the tails of the distribution—a by-product of the reduced risky asset allocation during periods of heightened
market volatility.
The mortality experience adjustments and the changed expectation adjustments to a lesser extent (bottom-left and bottom-right panels of Fig. 3,
respectively) grow in magnitude over time as the pool ages. This development is expected because older members are statistically more likely to die,
intensifying the uncertainty surrounding mortality gains for surviving members. The MEA and CEA are identical in both dynamic and static asset
allocation cases.
Building on the intuition of Fig. 3, we now turn to summaries of our 100,000 scenarios. Fig. 4 reports the funnels of doubt for the risky asset
allocation, defined as average values (solid lines) as well as 5th and 95th percentiles (dashed lines) of the monthly distribution of 𝜔𝑡. We consider,
again, static and dynamic allocation strategies. On the one hand, the static allocation leads to a constant weight of 56.8% for all scenarios by design.
The dynamic allocation strategy, on the other hand, displays a certain level of uncertainty. The average allocation for the dynamic strategy is higher
than the static allocation during the first 30 years (i.e., 69.7% versus 57.3%), leading to additional returns, on average. During this period, there
are also sizeable variations in the allocation: the 5th and 95th percentiles of the risky asset allocation are 38.1% and 116.8%, respectively. Then,
after the initial 30 years, the average allocation obtained from the dynamic strategy decreases because of the increased risk in the MEA and CEA;
the funnel also becomes narrower around the mean value, to finally reach a risky asset allocation of zero in all scenarios.
Insurance Mathematics and Economics 118 (2024) 72–94
82
J.-F. Bégin and B. Sanders
Fig. 3. Illustrative example of the fund value, risky asset allocation, benefits, and benefit adjustment constituents for a given scenario. Notes: This figure
shows an illustrative example of the fund value, risky asset allocation, (annualized) benefits in thousands of dollars, and adjustment constituents for a given scenario.
IEA stands for investment experience adjustment, MEA for mortality experience adjustment, and CEA for changed expectation adjustment. In this scenario, the death
benefit parameter 𝛾 is set to zero, so DBEA is nil.
Fig. 4. Risky asset allocation funnels of doubt for dynamic and static asset allocation. Notes: This figure shows funnels of doubt for the risky asset allocation
𝜔𝑡. We consider dynamic and static allocation along with the basic setting of Section 5. Average values (solid lines) as well as 10th and 90th percentiles (dashed
lines) are reported. Note that the static allocation strategy is constant through time, hence leading to a degenerate funnel at 56.8%.
Fig. 5 presents funnels of doubt for annualized benefits. Consistent with a higher average risky asset allocation when using a dynamic strategy,
the average benefit is higher than that of the static strategy. Indeed, the static allocation leads to a level average as discussed in Section 3.3, whereas
the dynamic allocation average benefit increases for the first 30–35 years. Furthermore, the 5th and 95th percentiles of the volatility-targeting
strategy’s benefit distribution consistently surpass those of the static strategy, resulting in superior benefits, generally speaking. This outcome is a
direct consequence of the strategy’s design, which involves reducing the allocation to the risky asset during periods of heightened volatility. This, in
turn, lowers the likelihood of significant drawdowns and improves the left tail of the benefit distribution.
Panel A of Table 2 complements the information presented in Fig. 5 by offering a detailed view of the annualized benefit distribution for specific
ages (i.e., 75, 85, 95, and 105 years old); it provides a comprehensive set of summary statistics and key percentiles for these age groups and for
the two strategies. Across all scenarios, the benefits derived from dynamic volatility-targeting allocations consistently outperform those of static
allocations. For instance, at age 75, the dynamic allocation yields larger benefits in 88.2% of the scenarios. This trend continues, with 95.0% at age
85 and 97.5% at age 95.
As we approach the end of the time horizon, the average benefit of the dynamic allocation strategy experiences a decline. This reduction
can be attributed to the fact that, in virtually all cases, the risky asset allocation approaches zero towards the end of the investment horizon.
Insurance Mathematics and Economics 118 (2024) 72–94
83
J.-F. Bégin and B. Sanders
Fig. 5. Annualized benefits funnels of doubt for dynamic and static asset allocations. Notes: This figure reports funnels of doubt for the annualized benefits in
thousands of dollars. We consider dynamic and static allocation strategies along with the basic setting of Section 5. Average values (solid lines) as well as 5th and
95th percentiles (dashed lines) are reported.
Table 2
Summary statistics of benefits and benefit adjustments.
Panel A: Summary statistics of benefits
75 85 95 105
Dynamic Static Dynamic Static Dynamic Static Dynamic Static
Average 123.7 104.4 159.4 114.4 235.7 146.7 359.7 269.9
Standard deviation 51.6 36.1 124.7 78.2 335.2 187.9 1046.1 775.5
5th percentile 58.3 53.3 39.7 32.0 24.2 17.1 10.7 8.3
25th percentile 86.8 78.9 78.3 61.5 67.3 46.1 44.4 34.3
Median 114.5 100.2 125.8 95.0 135.7 90.3 120.0 91.5
75th percentile 150.3 125.5 200.3 144.7 277.4 176.5 323.9 245.0
95th percentile 220.8 169.8 392.3 261.4 758.0 454.8 1363.8 1015.8
Proportion (%) 88.2 11.8 95.0 5.0 97.5 2.5 79.6 20.4
Panel B: Summary statistics of benefit adjustments
75 85 95 105
Dynamic Static Dynamic Static Dynamic Static Dynamic Static
Average 1.001 1.000 1.002 1.001 1.002 1.001 1.004 1.009
Standard deviation 0.107 0.100 0.107 0.102 0.107 0.109 0.326 0.343
5th percentile 0.950 0.951 0.950 0.951 0.950 0.949 0.953 0.930
25th percentile 0.983 0.984 0.983 0.984 0.982 0.982 0.966 0.964
Median 1.003 1.001 1.003 1.002 1.002 1.001 0.976 0.987
75th percentile 1.022 1.017 1.022 1.018 1.022 1.020 1.004 1.021
95th percentile 1.049 1.045 1.050 1.047 1.051 1.051 1.138 1.149
Proportion (%) 56.3 43.7 56.5 43.5 54.7 45.3 41.1 58.9
Notes: This table reports summary statistics of benefits and monthly benefit adjustments for four ages
of interest (75, 85, 95, and 105 years old) and for the two allocation strategies. We consider the basic
setting of Section 5. The proportion value for the dynamic case reports the proportion of scenarios with
a higher value of benefit (or benefit adjustment) for the dynamic strategy when compared to the static
case. The proportion value for the static case is the opposite.
Consequently, the portfolio’s returns fall below the hurdle rate, resulting in relatively minor benefit reductions, on average. This decrease in returns
is accompanied by a reduction in risk, particularly evident in the left tail of the benefit distribution. For instance, the 5th percentile of annualized
benefits for members aged 105 is $10,700 with the dynamic strategy, compared to $8,300 with the static strategy. Furthermore, it is worth noting
that in 79.6% of the scenarios, the dynamic allocation strategy yields higher benefits for members aged 105. This underscores the effectiveness of
the dynamic approach in achieving favourable outcomes, even in the later stages of the investment horizon.
The top panel of Fig. 6 and Panel B of Table 2 provide insights into monthly benefit adjustments. During the initial 30 years, both the average
and median benefit adjustments are notably higher for the dynamic strategy, contributing to the observed steady increase in the average benefits in
Fig. 5. In general, the dynamic strategy exhibits larger adjustments when compared to the static approach. However, beyond the initial 35 years,
the dynamic allocation tends to yield lower average adjustments compared to the static approach—traded for a thinner left tail of the adjustment
distribution. This effectively reduces the severity of drastic decreases, resulting in an overall lower risk profile for this strategy.
Insurance Mathematics and Economics 118 (2024) 72–94
84
J.-F. Bégin and B. Sanders
Fig. 6. Benefit adjustment funnels of doubt and annualized volatility of the benefit adjustments for dynamic and static asset allocations. Notes: The top
panel of this figure shows funnels of doubt for the benefit adjustments, whereas the bottom panel reports the annualized volatility of the benefit adjustments. We
consider dynamic and static allocation strategies along with the basic setting of Section 5. Average values (solid lines) as well as 5th and 95th percentiles (dashed
lines) are reported in the top panel.
The annualized benefit adjustment volatility is depicted in the bottom panel of Fig. 6. In general, for both methods, it remains in the neighbourhood of the 10% target during the initial 30 years. However, the dynamic strategy distinguishes itself from the static strategy by maintaining
the overall adjustment volatility close to 10% for an additional five years, achieved through a reduction in the allocation to the risky asset during
this period as illustrated in Fig. 4. Beyond the initial 35 years, the mortality-related adjustments—MEA and CEA—tend to increase, resulting in
challenges for sustaining the benefit adjustment volatility near its target. That being said, it is still systematically lower than that implied by the
static strategy, thus leading to less variability in the benefit stream.
5.2. Implications of death benefits
In the previous subsection, we established a baseline scenario by setting the death benefit parameter 𝛾 to zero. In the current analysis, we
explore the influence of varying this parameter on the dynamic strategy’s outcomes. The left panels of Fig. 7 show the annualized benefits funnels of
doubt for a death benefit parameter of 25% (top panel) and 75% (bottom panel).22 The dynamic strategy’s superiority in terms of generating higher
benefits holds true even when death benefits are introduced: the funnels of doubt generated from the dynamic allocation systematically outperform
those of the static strategy. This conclusion is further supported by Table 3: the stream obtained with the dynamic strategy leads to more benefits.
Furthermore, in about 90% of the scenarios, the dynamic allocation improves the benefits obtained by members, and this for all ages considered in
the table.
The right panels of Fig. 7 present monthly benefit adjustments funnels of doubt.23 Similar to what we observed in Fig. 6, the dynamic allocation
leads to higher average adjustments for the initial 30–35 years. Beyond this period, the adjustments for the dynamic allocation are slightly lower
than those obtained with the static strategy, but the risk—especially in the left tail of the benefit adjustments—is greatly reduced, contributing to
more stable outcomes.
5.3. Impact of the exogenous volatility target
The volatility target could influence the results presented in Section 5.1, so we assess the repercussions of changing this assumption. We consider
two distinct volatility targets: 13% and 16%.
Fig. 8 mirrors Fig. 4 and shows funnels of doubt for the risky asset allocation. Indeed, these funnels of doubt closely resemble those presented in
the baseline case of Section 5.1. Yet the allocation to the risky asset tends to increase as we raise the target. For instance, the 95th percentile of the
risky asset allocation in the dynamic case when the target is 13% (16%) is about 160% (200%).
The combination of increased allocations to the risky asset and the timing of these changes—smaller allocation when volatility is high and vice
versa—lead to notable enhancements in the benefit streams, as shown in Table 4.
24 Once again, the dynamic strategy consistently delivers robust
benefit streams that outperform those generated by the static allocation strategy in approximately 90% of the scenarios.
22 In this application, we maintain a constant hurdle rate of 7.53%, which results in declining benefits in the static case. It is important to recognize that the overall
behaviour of the benefit stream could exhibit an upward trend by using a lower hurdle rate as done in Olivieri et al. (2022), and our findings remain robust to
changes in this assumption. 23 See Table SM.5 of the Supplementary Material for more details on the monthly benefit adjustments with non-zero death benefits. 24 The interested reader can refer to summary statistics about the benefit adjustments with different volatility targets in Table SM.6 of the Supplementary Material.
Insurance Mathematics and Economics 118 (2024) 72–94
85
J.-F. Bégin and B. Sanders
Table 3
Summary statistics of benefits with death benefits.
Panel A: Summary statistics of benefits for a death benefit parameter of 25%
75 85 95 105
Dynamic Static Dynamic Static Dynamic Static Dynamic Static
Average 117.5 99.1 134.4 96.2 147.0 90.4 124.3 82.1
Standard deviation 49.1 34.2 105.0 65.6 209.1 115.1 353.5 222.2
5th percentile 55.3 50.6 33.5 27.0 15.1 10.5 3.7 2.7
25th percentile 82.5 74.9 66.0 51.8 42.1 28.6 15.4 11.0
Median 108.8 95.1 106.1 79.9 84.7 55.8 41.9 29.2
75th percentile 142.7 119.1 168.9 121.6 172.9 108.9 113.3 77.0
95th percentile 209.7 161.1 330.4 219.9 471.7 280.6 469.4 308.6
Proportion (%) 88.2 11.8 95.1 4.9 97.7 2.3 88.0 12.0
Panel B: Summary statistics of benefits for a death benefit parameter of 75%
75 85 95 105
Dynamic Static Dynamic Static Dynamic Static Dynamic Static
Average 106.0 89.3 95.4 68.0 57.2 34.6 15.9 8.4
Standard deviation 44.3 30.8 74.6 46.3 82.3 44.4 48.8 23.5
5th percentile 49.9 45.7 23.8 19.1 5.7 4.0 0.4 0.2
25th percentile 74.3 67.5 46.8 36.7 16.1 10.8 1.7 1.0
Median 98.1 85.7 75.4 56.5 32.7 21.3 4.9 2.8
75th percentile 128.7 107.3 120.0 86.1 67.0 41.6 13.9 7.7
95th percentile 189.2 145.1 234.4 155.4 184.5 108.0 59.8 31.5
Proportion (%) 88.3 11.7 95.2 4.8 97.9 2.1 98.2 1.8
Notes: This table reports summary statistics of benefits in thousands of dollars for four ages of interest (75, 85,
95, and 105 years old) and for the two allocation strategies. We consider the basic setting of Section 5 as well as
death benefit parameters of 25% (Panel A) and 75% (Panel B). The proportion value for the dynamic case reports
the proportion of scenarios with a higher value of benefit for the dynamic strategy when compared to the static
case. The proportion value for the static case is the opposite.
Fig. 7. Annualized benefits and benefit adjustments funnels of doubt for dynamic and static asset allocations with death benefits. Notes: This figure reports
funnels of doubt for the annualized benefits in thousands of dollars and benefit adjustments. We consider dynamic and static allocation strategies along with the
basic setting of Section 5 and two different death benefit parameters (25% and 75%). Average values (solid lines) as well as 5th and 95th percentiles (dashed lines)
are reported.
Note that these additional returns, stemming from the heightened allocation to the risky asset, contribute significantly to the benefit streams.
Yet they are oftentimes based on highly leveraged positions that might not be possible in real applications. Section 6.1 will comment on this issue.
Insurance Mathematics and Economics 118 (2024) 72–94
86
J.-F. Bégin and B. Sanders
Fig. 8. Risky asset allocation funnels of doubt for dynamic and static asset allocation with different volatility targets. Notes: This figure shows funnels of
doubt for the risky asset allocation 𝜔𝑡. We consider dynamic and static allocation along with the basic setting of Section 5 and two different volatility targets: 13%
(left panel) and 16% (right panel). Average values (solid lines) as well as 5th and 95th percentiles (dashed lines) are reported. Note that the static allocation strategy
is constant through time, hence leading to degenerate funnels.
Table 4
Summary statistics of benefits with different volatility targets.
Panel A: Summary statistics of benefits for a volatility target of 13%
75 85 95 105
Dynamic Static Dynamic Static Dynamic Static Dynamic Static
Average 146.5 116.8 200.1 128.2 314.3 164.7 510.3 304.3
Standard deviation 78.8 50.4 193.9 103.0 545.6 241.3 1743.1 991.4
5th percentile 54.9 48.9 36.4 27.6 22.4 14.3 10.4 6.8
25th percentile 91.2 80.9 81.7 60.5 70.9 43.8 48.9 31.7
Median 129.3 109.4 143.4 100.4 156.8 92.4 143.1 90.2
75th percentile 182.6 144.7 248.9 163.3 349.4 192.8 421.1 258.8
95th percentile 295.6 209.9 552.5 321.5 1087.6 541.0 1953.6 1159.9
Proportion (%) 88.0 12.0 95.0 5.0 97.6 2.4 87.5 12.5
Panel B: Summary statistics of benefits for a volatility target of 16%
75 85 95 105
Dynamic Static Dynamic Static Dynamic Static Dynamic Static
Average 172.6 129.6 250.7 142.7 420.2 184.1 735.3 342.5
Standard deviation 115.7 67.9 300.8 134.9 907.1 313.0 3025.3 1283.7
5th percentile 50.5 43.7 32.0 22.7 19.4 11.2 9.2 5.2
25th percentile 94.0 81.5 82.6 57.7 71.5 39.9 50.8 27.8
Median 143.6 117.3 159.7 103.9 175.1 91.8 163.5 86.5
75th percentile 218.2 164.4 304.6 181.5 430.9 206.8 530.9 266.8
95th percentile 390.0 256.6 768.3 392.5 1548.8 643.6 2797.6 1314.1
Proportion (%) 87.8 12.2 94.8 5.2 97.6 2.4 91.6 8.4
Notes: This table reports summary statistics of benefits in thousands of dollars for four ages of interest
(75, 85, 95, and 105 years old) and for the two allocation strategies. We consider the basic setting of
Section 5 and two different volatility targets: 13% (Panel A) and 16% (Panel B). The proportion value
for the dynamic case reports the proportion of scenarios with a higher value of benefit for the dynamic
strategy when compared to the static case. The proportion value for the static case is the opposite.
5.4. Pool sizes and impact on investment strategies
As depicted in Fig. 2, the size of the pool can impact the risky asset allocation: a smaller pool increases the volatility stemming from mortalityrelated adjustments, consequently leading to a decrease in the allocation to the risky asset, generally speaking. We now assess the importance of
this assumption.
Fig. 9 presents funnels of doubt for risky asset allocation distributions; the funnels are similar to those presented in Fig. 4, with one notable
distinction: the decrease in the allocation is more pronounced for smaller pools. In particular, when dealing with pool sizes of 250 and 500 members
at inception, the risky asset allocation diminishes to zero in all scenarios when members reach the ages of 100 and 103 years, respectively. This
contrasts with the baseline case of Section 5.1, which involves 1,000 members, where the allocation reaches zero at the age of 107. The general
decrease in the allocation is a by-product of the increased benefit adjustment volatility for small pools.
The benefits tend to be generally larger under the dynamic strategy and during the first 30 years; as in the baseline case, the dynamic allocation
leads to benefits that are larger in about 90% of the scenarios (see Table 5 for more details). After this period, however, benefits can become lower
when using the dynamic strategy due to the low allocation to the risky asset. For a pool of 500 members at inception, the outcomes still seem better
for the dynamic strategy at these higher ages. For very small pools of 250 members at inception, however, the benefits are comparable for both
strategies—neither better nor worse.25 It is therefore recommended to be careful when setting up lifetime pension pools with so few members at
the start.
25 After 30 years, a pool with an initial size of 250 members has about 35 members left, which is a very low number in this context.
Insurance Mathematics and Economics 118 (2024) 72–94
87
J.-F. Bégin and B. Sanders
Fig. 9. Risky asset allocation funnels of doubt for dynamic and static asset allocation and for different pool sizes at inception. Notes: This figure shows
funnels of doubt for the risky asset allocation 𝜔𝑡. We consider dynamic and static allocation along with the basic setting of Section 5 and two different pool sizes at
inception: 250 members (left panel) and 500 members (right panel). Average values (solid lines) as well as 5th and 95th percentiles (dashed lines) are reported. Note
that the static allocation strategy is constant through time, hence leading to degenerate funnels.
Table 5
Summary statistics of benefits for pool sizes of 250 and 500 members at inception.
Panel A: Summary statistics of benefits for a pool size of 250 members at inception
75 85 95 105
Dynamic Static Dynamic Static Dynamic Static Dynamic Static
Average 123.4 104.4 158.4 114.8 223.7 150.9 263.9 262.0
Standard deviation 51.5 36.2 123.6 78.8 311.1 194.6 797.9 764.2
5th percentile 58.2 53.3 39.5 31.9 23.2 16.9 7.2 7.1
25th percentile 86.7 78.8 77.9 61.6 64.3 46.6 30.7 30.6
Median 114.2 100.2 125.1 95.3 130.1 91.9 85.1 84.7
75th percentile 149.9 125.4 199.0 145.1 264.5 181.2 233.7 232.3
95th percentile 220.2 170.0 388.5 263.2 716.8 471.4 997.6 992.4
Proportion (%) 88.0 12.0 94.7 5.3 95.0 5.0 49.1 50.9
Panel B: Summary statistics of benefits for a pool size of 500 members at inception
75 85 95 105
Dynamic Static Dynamic Static Dynamic Static Dynamic Static
Average 123.5 104.3 159.2 114.6 232.6 148.4 329.2 283.0
Standard deviation 51.6 36.1 124.3 78.4 327.4 190.2 1006.6 889.9
5th percentile 58.2 53.3 39.7 32.0 23.8 16.9 9.3 8.1
25th percentile 86.7 78.8 78.3 61.5 66.7 46.4 39.1 34.0
Median 114.3 100.1 125.7 95.2 133.8 90.6 107.1 92.8
75th percentile 150.1 125.4 200.2 145.0 273.7 178.1 291.0 251.6
95th percentile 220.4 169.7 391.1 262.6 746.5 464.5 1241.9 1071.2
Proportion (%) 88.1 11.9 94.9 5.1 97.1 2.9 65.5 34.5
Notes: This table reports summary statistics of benefits in thousands of dollars for four ages of interest (75, 85,
95, and 105 years old) and for the two allocation strategies. We consider the basic setting of Section 5 and two
initial pool sizes: 250 members (Panel A) and 500 members (Panel B). The proportion value for the dynamic
case reports the proportion of scenarios with a higher value of benefit for the dynamic strategy when compared
to the static case. The proportion value for the static case is the opposite.
6. Limitations in practical situations
This section investigates and assesses the impact of three practical limitations of the dynamic volatility-targeting allocation introduced above:
leverage constraints, brokerage fees, and rebalancing frequencies.
6.1. Leverage constraints
Leverage refers to the use of borrowed capital by financial institutions and investors to enhance their returns. As evidenced by Fig. 4, we know
that such leverage is used in the dynamic strategy as the risky asset allocation is sometimes above one (e.g., the 95th percentile of the risky asset
allocation distribution is above one for ages 65 to 98).
In practice, certain pool operators may face restrictions on the amount of borrowed capital they can employ: some might have soft restrictions
(i.e., allowed to use some leverage) or strict restrictions (i.e., no leverage whatsoever). Accordingly, we investigate the impact of having a cap on
the allocation to the risky asset as it might impact our results in a non-trivial way. Specifically, in this study, we modify the weight of Equation (20)
by taking the minimum of the computed allocation and the limit.
We explore the effects of two distinct limits imposed on risky asset allocations: 100% and 150%. New risky asset allocation funnels of doubt for
these two limits are presented in Fig. 10: the left panel reports the results for a limit of 100% and the right panel for a limit of 150%. Applying this
limit impacts the right tail of the risky asset allocation distribution; for instance, when the limit is set to 100%, we observe a narrower funnel of
doubt driven by the 95th percentile being lower than that of Fig. 4. When the limit is 150%, on the other hand, we only see minimal changes in the
allocations as less than 1% of the optimal weights were above 1.5 in the baseline case.
Insurance Mathematics and Economics 118 (2024) 72–94
88
J.-F. Bégin and B. Sanders
Fig. 10. Risky asset allocation funnels of doubt for dynamic and static asset allocation and with leverage constraints. Notes: This figure shows funnels of
doubt for the risky asset allocation 𝜔𝑡. We consider dynamic and static allocation along with the basic setting of Section 5 and two different leverage limit levels:
100% (left panel) and 150% (right panel). Average values (solid lines) as well as 5th and 95th percentiles (dashed lines) are reported. Note that the static allocation
strategy is constant through time, hence leading to degenerate funnels.
Fig. 11. Annualized benefits funnels of doubt for dynamic and static asset allocations and with leverage constraints. Notes: This figure reports funnels of
doubt for the annualized benefits. We consider dynamic and static allocation strategies along with the basic setting of Section 5 and two different leverage constraint
levels: 100% (top panels) and 150% (bottom panels). Average values (solid lines) as well as 5th and 95th percentiles (dashed lines) are reported.
Fig. 11 provides insight into the annualized benefits; for a leverage limit level of 100%, the annualized benefits appear slightly lower when
compared to those presented in Fig. 5. The dynamic asset allocation strategy leads, nonetheless, to higher benefits in most cases. Conversely, when
the limit is 150% (right panels), the funnels of doubt closely resemble those presented in Fig. 5, reaffirming that most allocations were already
below 150% in the baseline case.
The results of Fig. 11 are further supported by Table 6: a limit of 100% marginally impacts the superiority of the dynamic strategy, whereas a
limit of 150% does not impact the results from the baseline case of Section 5.
6.2. Brokerage fees
Brokerage fees represent charges or commissions levied by financial intermediaries for facilitating the execution of securities transactions on
behalf of investors. Brokerage fees, while a standard aspect of investment transactions, can influence an investor’s overall returns and should be
carefully considered when formulating investment strategies. For instance, in the context of the volatility-targeting strategy, such commissions and
fees could negatively impact the benefits if the allocation were to change too often.
The specific fee structure and rates associated with brokerage services can vary significantly across different brokerage firms and jurisdictions.
This study relies on a very simple fee structure that is proportional to the size of the transaction. Let 𝜐 be the brokerage fee. The time-𝑡 broker fee’s
dollar amount is therefore given by
𝜐 ×
|
|
|
|
(
𝐹𝑡−ℎ − 𝐵𝑡−ℎ
)
𝜔𝑡
𝑆𝑡
𝑆𝑡−ℎ
− (𝐹𝑡 − 𝐵𝑡
)
𝜔𝑡+ℎ
|
|
|
|
,
which captures the (absolute value of the) difference between the end of period amount invested in the risky asset and the new dollar amount
position after benefit distribution. Note that we apply these fees to both dynamic and static strategies.26
26 Even with a static strategy, the pool operator needs to rebalance to keep the allocation holdings static.
Insurance Mathematics and Economics 118 (2024) 72–94
89
J.-F. Bégin and B. Sanders
Table 6
Summary statistics of benefits with leverage constraints.
Panel A: Summary statistics of benefits with a risky asset allocation limit of 100%
75 85 95 105
Dynamic Static Dynamic Static Dynamic Static Dynamic Static
Average 120.7 104.4 151.9 114.4 220.4 146.7 335.4 269.9
Standard deviation 48.6 36.1 115.8 78.2 307.2 187.9 964.8 775.5
5th percentile 58.0 53.3 39.0 32.0 23.3 17.1 10.2 8.3
25th percentile 85.9 78.9 76.0 61.5 64.3 46.1 42.1 34.3
Median 112.4 100.2 121.1 95.0 128.7 90.3 113.2 91.5
75th percentile 146.3 125.5 191.4 144.7 260.6 176.5 303.2 245.0
95th percentile 211.8 169.8 368.5 261.4 705.6 454.8 1271.3 1015.8
Proportion (%) 87.7 12.3 94.6 5.4 97.2 2.8 75.6 24.4
Panel B: Summary statistics of benefits with a risky asset allocation limit of 150%
75 85 95 105
Dynamic Static Dynamic Static Dynamic Static Dynamic Static
Average 123.6 104.4 159.3 114.4 235.5 146.7 359.4 269.9
Standard deviation 51.6 36.1 124.5 78.2 334.9 187.9 1045.4 775.5
5th percentile 58.3 53.3 39.7 32.0 24.2 17.1 10.6 8.3
25th percentile 86.8 78.9 78.3 61.5 67.2 46.1 44.4 34.3
Median 114.5 100.2 125.8 95.0 135.6 90.3 119.8 91.5
75th percentile 150.2 125.5 200.1 144.7 277.2 176.5 323.6 245.0
95th percentile 220.6 169.8 392.1 261.4 757.4 454.8 1363.2 1015.8
Proportion (%) 88.2 11.8 95.0 5.0 97.5 2.5 79.6 20.4
Notes: This table reports summary statistics of benefits in thousands of dollars for four ages of interest
(75, 85, 95, and 105 years old) and for the two allocation strategies. We consider the basic setting of
Section 5 and leverage limit levels of 100% (Panel A) and 150% (Panel B). The proportion value for the
dynamic case reports the proportion of scenarios with a higher value of benefit for the dynamic strategy
when compared to the static case. The proportion value for the static case is the opposite.
This study considers two different broker fee levels: 10 basis points (bps) and 50 bps. The first case is inspired from the results of Di Maggio et
al. (2022) who found the average broker fee to be roughly 13 bps relative to the value of transactions. The second is an extreme case, allowing us
to quantify the impact of very high broker fees.
The left panel of Fig. 12 and Panel A of Table 7 provide insights into the annualized benefits when the broker fee is set to 10 bps. The impact of
such a brokerage fee on the static strategy is relatively modest overall. In contrast, its impact on the dynamic strategy is more noticeable, resulting
in a funnel of doubt that is slightly lower than that of Fig. 5, with reduction in the annualized benefits between $3,000 and $15,000, on average.
Yet the dynamic strategy still yields significantly higher benefits when compared to the static allocation approach, and this for the majority of the
scenarios.
When the broker fee is increased to 50 bps (right panel of Fig. 12 and Panel B of Table 7), the effects of the commission become more pronounced,
leading to reductions in annualized benefits. For the first 35 years, the dynamic strategy still continues to deliver higher average benefits than the
static strategy even with very high broker fees, but this trend reverses for members older than 100 years old. This is also true for most percentiles
in Table 7.
It is worth emphasizing that a 10 bps broker fee aligns more closely with empirical observations (see, e.g., Di Maggio et al., 2022), and that 50
bps—an extreme fee—would still see benefit improvements for most of the members’ lifetime. However, one should be careful as high brokerage
fees can definitely impact the viability and success of lifetime pension pools.
6.3. Rebalancing frequency
The last practical concern we investigate in this study is the rebalancing frequency—the frequency at which an investment portfolio is adjusted.
To simplify the presentation and our calculations, we also consistently change the frequency at which the benefits are paid to preserve the consistency
between the volatility target of Equation (19) and the allocation of Equation (20).27 Specifically, in addition to the monthly case considered above,
we consider five values of 𝑚 in this analysis: 1 (annual frequency), 2 (semiannual frequency), 6 (bimonthly frequency), 26 (biweekly frequency),
and 52 (weekly frequency).
Table 8 presents a summary of various statistics for the five additional values of 𝑚. Notably, the average benefits are systematically higher
for all ages and frequencies under consideration. However, at the annual frequency, and particularly as the pool approaches termination, certain
percentiles of the benefit distribution are lower when employing the dynamic strategy. Nonetheless, the dynamic allocation strategy continues to
deliver robust benefits until members approach 100 years of age. For all other frequencies higher than annual, the benefit streams consistently
demonstrate superior performance when employing the dynamic strategy. The proportion of paths resulting in higher benefits is overall greater
when utilizing the dynamic allocation method.
The effectiveness of the dynamic strategy appears to be closely tied to the rebalancing frequency, with significant improvements as the frequency increases. The average (annualized) benefit across the entire period exhibits a clear upward trend in relation to the rebalancing frequency,
27 It would be possible to decouple these two operations, but this is more involved. We leave this interesting question for future research.
Insurance Mathematics and Economics 118 (2024) 72–94
90
J.-F. Bégin and B. Sanders
Fig. 12. Annualized benefits funnels of doubt for dynamic and static asset allocations and with brokerage fees. Notes: This figure reports funnels of doubt
for the annualized benefits. We consider dynamic and static allocation strategies along with the basic setting of Section 5 and two different commission levels: 10
basis points (left panel) and 50 basis points (right panel). Average values (solid lines) as well as 5th and 95th percentiles (dashed lines) are reported.
Table 7
Summary statistics of benefits with brokerage fees.
Panel A: Summary statistics of benefits with a broker fee of 10 bps
75 85 95 105
Dynamic Static Dynamic Static Dynamic Static Dynamic Static
Average 121.0 104.0 152.8 113.6 221.2 145.3 334.0 266.1
Standard deviation 50.3 35.9 119.0 77.7 313.7 186.0 969.0 765.0
5th percentile 57.3 53.1 38.3 31.7 22.9 16.9 9.9 8.2
25th percentile 85.1 78.6 75.3 61.1 63.4 45.6 41.4 33.8
Median 112.1 99.9 120.7 94.4 127.6 89.4 111.5 90.3
75th percentile 147.0 125.0 191.9 143.7 260.5 174.7 300.8 241.6
95th percentile 215.7 169.2 375.2 259.8 710.9 450.3 1265.1 1001.6
Proportion (%) 85.3 14.7 92.8 7.2 95.8 4.2 74.5 25.5
Panel B: Summary statistics of benefits with a broker fee of 50 bps
75 85 95 105
Dynamic Static Dynamic Static Dynamic Static Dynamic Static
Average 111.0 102.5 128.7 110.6 171.6 139.5 248.1 251.7
Standard deviation 45.3 35.5 99.0 75.7 240.8 178.8 713.8 724.1
5th percentile 53.4 52.2 32.9 30.8 18.1 16.2 7.5 7.7
25th percentile 78.7 77.4 64.2 59.4 49.8 43.8 31.1 31.9
Median 103.0 98.4 102.2 91.8 99.7 85.8 83.5 85.3
75th percentile 134.5 123.3 161.8 139.9 202.5 167.7 224.3 228.5
95th percentile 196.3 166.9 313.4 253.1 549.8 432.5 939.9 947.7
Proportion (%) 68.4 31.6 74.9 25.1 77.7 22.3 46.9 53.1
Notes: This table reports summary statistics of benefits in thousands of dollars for four ages of interest
(75, 85, 95, and 105 years old) and for the two allocation strategies. We consider the basic setting of
Section 5 and two different commission levels: 10 basis points (Panel A) and 50 basis points (Panel B).
The proportion value for the dynamic case reports the proportion of scenarios with a higher value of
benefit for the dynamic strategy when compared to the static case. The proportion value for the static
case is the opposite.
starting at $152,900 for an annual frequency and rising to $372,100 for a weekly frequency. Examin