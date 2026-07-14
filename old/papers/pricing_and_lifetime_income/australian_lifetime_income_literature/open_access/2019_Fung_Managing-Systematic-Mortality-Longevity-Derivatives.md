https://www.mdpi.com/2227-9091/7/1/2/pdf
→ https://mdpi-res.com/d_attachment/risks/risks-07-00002/article_deploy/risks-07-00002.pdf?version=1546509042
Content-Type: application/pdf

risks
Article
Managing Systematic Mortality Risk in Life
Annuities: An Application of Longevity Derivatives
Man Chung Fung 1, Katja Ignatieva 2,* and Michael Sherris 3
1 The Commonwealth Scientific and Industrial Research Organisation (CSIRO), North Ryde,
Sydney, NSW 2113, Australia; simon.fung@csiro.au
2 Business School, Risk and Actuarial Studies, Randwick, Sydney, NSW 2052, Australia
3 Risk and Actuarial Studies and Centre of Excellence in Population Ageing Research (CEPAR),
Business School, University of New South Wales, Randwick, Sydney, NSW 2052, Australia;
m.sherris@unsw.edu.au
* Correspondence: k.ignatieva@unsw.edu.au
Received: 27 November 2018; Accepted: 22 December 2018; Published: 3 January 2019
Abstract: This paper assesses the hedge effectiveness of an index-based longevity swap and a longevity
cap for a life annuity portfolio. Although longevity swaps are a natural instrument for hedging
longevity risk, derivatives with non-linear pay-offs, such as longevity caps, provide more effective
downside protection. A tractable stochastic mortality model with age dependent drift and
volatility is developed and analytical formulae for prices of longevity derivatives are derived.
The model is calibrated using Australian mortality data. The hedging of the life annuity portfolio
is comprehensively assessed for a range of assumptions for the longevity risk premium, the term
to maturity of the hedging instruments, as well as the size of the underlying annuity portfolio.
The results compare the risk management benefits and costs of longevity derivatives with linear and
nonlinear payoff structures.
Keywords: longevity risk management; longevity swaps; longevity options; hedge effectiveness
1. Introduction
Securing a comfortable living after retirement is fundamental to the majority of the working
population around the world. A major risk in retirement, however, is the possibility that retirement
savings will be outlived. Products that provide guaranteed lifetime income, such as life annuities,
need to be offered in a cost effective way while maintaining the long run solvency of the provider.
Annuity providers and pension funds need to manage the systematic mortality risk1, associated with
random changes in the underlying mortality intensity, in a life annuity or pension portfolio. Systematic
mortality risk cannot be diversified away with increasing portfolio size, while idiosyncratic mortality
risk, representing the randomness of deaths in a portfolio with fixed mortality intensity, is diversifiable.
Reinsurance has been important in managing longevity risk for annuity and pension providers.
However, there are concerns that reinsurers have a limited risk appetite and are reluctant to take this
“toxic” risk (Blake et al. 2006). In fact, even if they were willing to accept the risk, the reinsurance sector
is not deep enough to absorb the vast scale of longevity risk currently undertaken by annuity providers
and pension funds. It is estimated that pension assets for the 13 largest major pension markets have
reached nearly 30 trillions USD in 2012 (Towers Watson 2013). The sheer size of capital markets and an
1 From an annuity provider’s perspective, longevity risk modelling can lead to a (stochastically) over- or underestimation of
survival probabilities for all annuitants. For this reason longevity risk is also referred to as the systematic mortality risk.
Risks 2019, 7, 2; doi:10.3390/risks7010002 www.mdpi.com/journal/risks
Risks 2019, 7, 2 2 of 25
almost zero correlation between financial and demographic risks, suggests that they will increasingly
take a role in the risk management of longevity risk.
The importance to investigate the benefits of financial assets designed to hedge the longevity risk
has been recognised in Cocco and Gomes (2012). The first generation of capital market solutions
for longevity risk, in the form of mortality and longevity bonds (Blake and Burrows (2001),
Blake et al. (2006) and Bauer et al. (2010))2, gained limited success.
The second generation involving forwards and swaps have attracted increasing interest
(Blake et al. 2013). Index-based instruments aim to mitigate systematic mortality risk, and have the
potential to be less costly and are designed to allow trading as standardised contracts (Blake et al. 2013).
Unlike the bespoke or customized hedging instruments such as reinsurance, they do not cover
idiosyncratic mortality risk and give rise to basis risk (Li and Hardy 2011). Since idiosyncratic
mortality risk is reduced for larger portfolios, portfolio size is an important factor that determines the
hedge effectiveness of index-based instruments.
Longevity derivatives with a linear payoff, including q-forwards and S-forwards, have as
an underlying the mortality and the survival rate, respectively (LLMA 2010a). Their hedge effectiveness
has been considered in Ngai and Sherris (2011), who study the effectiveness of static hedging of
longevity risk in different annuity portfolios. They consider a range of longevity-linked instruments
including q-forwards, longevity bonds, and longevity swaps as hedging instruments to mitigate
longevity risk and demonstrate their benefits in reducing longevity risk. Li and Hardy (2011) also
consider hedging longevity risk with a portfolio of q-forwards. They highlight basis risk as one of the
obstacles in the development of an index-based longevity market.
Longevity derivatives with a nonlinear payoff structure have not received a great deal of attention
to date. Boyer and Stentoft (2013) evaluate European and American type survivor options using
simulations. Yueh et al. (2016) value mortality-linked structured products, developing valuation
models for mortality calls and puts, and exploring the sensitivity to changes in parameter values.
Wang and Yang (2013) propose and price survivor floors under an extension of the Lee-Carter model.
The authors do not consider the hedge effectiveness of longevity options and longevity swaps as
hedging instruments.
Although dynamic hedging has been considered, because of the lack of liquid markets in
longevity risk, static hedging remains the only realistic option for annuity providers. Cairns (2011)
considers q-forwards and a discrete-time delta hedging strategy, and compares it with static hedging.
Cairns et al. (2014) study longevity hedge effectiveness (with correlation between the value of the
hedge and the value of the pension liability as a proxy) in pension plans using stochastic simulations.
The authors only consider static hedging.3 The lack of analytical formulas for pricing q-forwards
and its derivatives, known as “Greeks", can be a significant problem in assessing hedge effectiveness
since simulations within simulations are required for dynamic hedging strategies. The importance
of tractable models has also been emphasised in Luciano et al. (2012), who also consider dynamic
hedging for longevity and interest rate risk. Hari et al. (2008) apply a generalised two-factor Lee-Carter
model to investigate the impact of longevity risk on the solvency of pension annuities.
This paper contributes to the literature by (1) developing pricing analysis of longevity derivatives;
(2) developing a tractable continuous time stochastic mortality model with age dependent drift and
2 Of particular interest is an attempt to issue the EIB longevity bond by the European Investment Bank (EIB) in 2004, which was
underwritten by BNP Paribas. This bond was not well received by investors and could not generate enough demand to be
launched due to its deficiencies, as outlined in Blake et al. (2006).
3 There is a separate strand in the literature that analyses variable annuities with embedded guarantees where the authors
either do not investigate hedge effectiveness (as e.g., in Peng et al. 2012), or perform static hedge. Huang and Kwok (2016)
price and hedge the guaranteed lifelong withdrawal benefit by means of the regression-based Monte Carlo simulations for
stochastic control models; Fung et al. (2014) consider the capital reserve required due to the lack of hedging instruments
to hedge the longevity risk in the guaranteed lifetime withdrawal benefits in variable annuities; Donnelly et al. (2014)
value guaranteed withdrawal benefits with stochastic interest rates and volatility and compute associated hedge ratios;
and Ignatieva et al. (2016) price and hedge guaranteed minimum benefits under regime-switching and stochastic mortality.
Risks 2019, 7, 2 3 of 25
volatility; (3) deriving analytical formulae for prices of longevity derivatives such as a longevity swap
and a cap based on cohort model that captures higher age volatility; (4) analysing hedge effectiveness
using static hedge via a longevity swap and a cap that are chosen as linear and nonlinear products to
compare and assess index-based capital market product management of longevity risk management.
In so doing, the paper extends the existing literature on generalised pricing frameworks for longevity
derivatives. The analysis is based on a hypothetical life annuity portfolio subject to longevity risk.
The paper considers the hedging of longevity risk using a longevity swap and a longevity cap,
a portfolio of S-forwards and longevity caplets respectively, based on a range of different underlying
assumptions for the market price of longevity risk, the term to maturity of hedging instruments, as well
as the size of the underlying annuity portfolio. Our results indicate that the longevity risk premium
is a small contributor to hedge effectiveness of a longevity swap. We also find that longevity caps
focusing on the downside are more cost effective.
The paper is organised as follows. Section 2 specifies the two-factor Gaussian mortality model,
and its parameters are estimated using Australian males mortality data. Section 3 analyses longevity
derivatives, in particular, a longevity swap and a cap, from a pricing perspective. Explicit pricing
formulas are derived under the proposed two-factor Gaussian mortality model. Section 4 examines
various hedging features and hedge effectiveness of a longevity swap and a cap on a hypothetical
life annuity portfolio exposed to longevity risk. Section 5 summarises the results and provides
concluding remarks.
2. Mortality Model
Let (Ω, Ft = Gt ∨ Ht, P) be a filtered probability space where P is the real world probability
measure. The subfiltration Gt contains information about the dynamics of the mortality intensity, or
force of mortality, while death times of individuals are captured by Ht (Biffis 2005). It is assumed that
the interest rate r is constant where B(0, t) = e
−r t denotes the price of a t-year zero coupon bond, and
our focus is on the modelling of stochastic mortality.
2.1. Model Specification
Amongst the affine class of stochastic mortality models (see e.g., Luciano and Vigna 2008), we have
chosen to model the mortality intensity using a Gaussian process. Our choice is motivated by the
fact that various longevity options can be priced analytically if we assume a Gaussian process for the
mortality intensity (this will be demonstrated in Section 3). Closed form expressions for longevity
option prices allow efficient computation of prices, risk statistics, and Greeks (hedge ratios) which are
required to perform the dynamic hedging, that would be computationally demanding to obtain with
Monte Carlo simulations.
Financial and actuarial applications require cohort models of stochastic mortality to capture
improvement trends and correlations between cohorts with different ages at any given time. As a result,
we propose a two-factor Gaussian mortality model which allows non-trivial instantaneous correlation
between the intensity processes of different cohorts. Specifically, we model the mortality intensity
process µx+t(t) of a cohort aged x at time t = 0 as:4
µx(t) = Y1(t) + Y2(t) (1)
satisfying the stochastic differential equation (SDE)
dµx(t) = dY1(t) + dY2(t), (2)
4 For simplicity of notation we replace µx+t(t) by µx(t).
Risks 2019, 7, 2 4 of 25
where
dY1(t) = α1Y1(t) dt + σ1 dW1(t), (3)
dY2(t) = (α x + β) Y2(t) dt + σe
γx
dW2(t), (4)
and dW1dW2 = ρ dt. The solutions of Equations (3) and (4) are given by
Y1(t) = e
α1tY1(0) + σ1
Z t
0
e
α1(t−s)
dW1(s), (5)
Y2(t) = e
(αx+β)tY1(0) + σeγx
Z t
0
e
(αx+β)(t−s)
dW2(s), (6)
respectively. In order to have a parsimonious model, the drift and the diffusion terms of the SDE for
the first factor Y1(t) are independent of the initial age x. As a result, Y1(t) can be viewed as a base
(intensity) process that is common to all ages. The SDE for the second factor Y2(t) depends on the
initial age through the drift and the diffusion terms.5 For positive values of α1 and αx + β, both Y1(t)
and Y2(t), and hence µx(t), will grow exponentially on average. Therefore the model is designed
specifically for capturing mortality intensity at older age, e.g., when age x ≥ 60, which is consistent
with what one would normally be observed in mortality data. Clearly, one needs to follow the “cohort"
direction, that is µx+t(t) as t increases, see Figure 1. Note that the instantaneous correlation between
the intensity processes of different cohorts, that is, for different initial ages x and y, is given by
Corr(dµx(t), dµy(t)) = σ
2
1 + ρσσ1(e
γy + eγx
) + σ
2
e
γ(x+y)
q
σ
2
1 + 2σσ1ρe
γx + σ2e2γx
q
σ
2
1 + 2σσ1ρe
γy + σ
2e
2γy
. (7)
Hence, the two-factor model allows non-trivial correlation structure unless σ1 = 0 or σ = 0.
Moreover, the model is tractable as shown in the following proposition:
Proposition 1. Under the two-factor Gaussian mortality model (Equations (2)–(4)), the (T − t)-year expected
survival probability of a person aged x + t at time t, conditional on filtration Ft, is given by
Sx+t(t, T)
def
= E
P
t

e
−
R T
t
µx(v)dv
= e
1
2
Γ(t,T)−Θ(t,T)
, (8)
where, using α2 = αx + β and σ2 = σe
γx
,
Θ(t, T) = (e
α1(T−t) − 1)
α1
Y1(t) + (e
α2(T−t) − 1)
α2
Y2(t) and (9)
Γ(t, T) =
2
∑
k=1
σ
2
k
α
2
k

T − t −
2
αk
e
αk(T−t) +
1
2αk
e
2αk(T−t) +
3
2αk

+
2ρσ1σ2
α1α2
 
T − t −
e
α1(T−t) − 1
α1
−
e
α2(T−t) − 1
α2
+
e
(α1+α2)(T−t) − 1
α1 + α2
!
(10)
are the mean and the variance of the integral R T
t
µx(v) dv, which is Gaussian distributed, respectively.
5 We can in fact replace x by x + t in Equation (4). Using x + t will take into account the empirical observation that the
volatility of mortality tends to increase with age x + t (Figures 1 and 2). However, for a Gaussian process the intensity will
have a non-negligible probability of reaching negative values when the volatility of the second factor (σe
γ(x+t)
) becomes
very high, which occurs for example when x + t > 100 (given γ > 0). Using x instead of x + t will also make the results of
Section 3 easy to interpret. For these reasons we assume that the second factor Y2(t) depends on the initial age x only.
Risks 2019, 7, 2 5 of 25
We will use the fact that the integral R T
t
µx(v) dv is Gaussian with known mean and variance to
derive analytical pricing formulas for longevity options in Section 3.
1970
1980
1990
2000
2010
60
70
80
90
100
0
0.1
0.2
0.3
0.4
Year (t)
Age (x)
m (x,t)
Figure 1. Australian male central death rates m(x,t) where t = 1970, 1971, . . . , 2008 and x = 60, 61, . . . , 95.
Proof. Solving Equation (3) to obtain an integral form of Y1(t), we have
Z T
t
Y1(u) du =
Z T
t
Y1(t)e
α1(u−t)
du +
Z T
t
σ1
Z u
t
e
α1(u−v)
dW1(v)du. (11)
The first term in Equation (11) can be simplified to
Z T
t
Y1(t)e
α1(u−t)
du =

e
α1(T−t) − 1

α1
Y1(t).
For the second term, we have
σ1
Z T
t
e
α1u
Z u
t
e
−α1v
dW1(v)du = σ1
Z T
t
Z u
t
e
−α1v
dW1(v)du

1
α1
e
α1u

=
σ1
α1
Z T
t
du

e
α1u
Z u
t
e
−α1v
dW1(v)

−
σ1
α1
Z T
t
e
α1u
du
Z u
t
e
−α1v
dW1(v)

=
σ1
α1
e
α1T
Z T
t
e
−α1u
dW1(u) −
σ1
α1
Z T
t
e
α1u
e
−α1u
dW1(u) = σ1
α1
Z T
t
e
α1(T−u) − 1 dW1(u),
where stochastic integration by parts is applied in the second equality.
To obtain an integral representation for Y2(t), we follow the same steps as above, replacing Y1(t)
by Y2(t) in Equation (11). It is then straightforward to notice that
Z T
t
µx(u) du =
Z T
t
Y1(u) + Y2(u) du (12)
is a Gaussian random variable with mean Θ(t, T) (Equation (9)) and variance Γ(t, T) (Equation (10)).
Equation (8) is obtained by applying the moment generating function of a Gaussian
random variable.
Risks 2019, 7, 2 6 of 25
1970
1980
1990
2000
2010
60
70
80
90
100
−0.1
−0.05
0
0.05
0.1
0.15
Year (t)
Age (x)
∆ m (x,t)
Figure 2. Difference of the central death rates ∆m(x, t) = m(x + 1, t + 1) − m(x, t) where
t = 1970, 1971, · · · , 2007 and x = 60, 61, · · · , 94.
2.2. Parameter Estimation
The discretised process, where the intensity is assumed to be constant over each integer
age and calendar year, is approximated by the central death rates m(x, t) (Wills and Sherris 2011).
Figure 1 displays Australian male6central death rates m(x, t) for years t = 1970, 1971, . . . , 2008
and ages x = 60, 61, . . . , 95. Figure 2 shows the difference of the central death rates
∆m(x, t) = m(x + 1, t + 1) − m(x, t). The variability of ∆m(x, t) is evidently increasing with increasing
age x, which leads to the anticipation that γ > 0. Furthermore, for a fixed age x, there is a slight
improvement in central death rates for more recent years, compared to the past.
The parameters {σ1, σ, γ, ρ}, which determine the volatility of the intensity process, are estimated
as described below using the method of least squares, thus, calibrating the model to the mortality
surface. However, we take advantage of the fact that a Gaussian model is employed where the variance
of the model can be calculated explicitly and thus, we capture the diffusion part of the process by
matching the variance of the model to mortality data. Specifically, the implemented procedure is as
specified below:
1. Using empirical data for ages x = 60, 65, . . . , 90 we evaluate the sample variance of ∆m(x, t)
across time, denoted by Var(∆mx).
2. The model variance Var(∆µx) for age x is given by
Var(∆µx) = Var(σ1∆W1 + σe
γx∆W2)
=

σ
2
1 + 2σ1σρe
γx + σ2
e
2γx

∆t. (13)
Since the difference between the death rates is computed in yearly terms, we set ∆t = 1.
6 We use Australian males mortality data for illustrative purposes. The model can well be applied to any other mortality data.
Risks 2019, 7, 2 7 of 25
3. The parameters {σ1, σ, γ, ρ} are then estimated by fitting the model variance Var(∆µx) to the
sample variance Var(∆mx) for ages x = 60, 65, . . . , 90 using least squares estimation, that is,
by minimising
90
∑
x=60,65...
(Var(∆µx|σ1, σ, γ, ρ) − Var(∆mx))
2
(14)
with respect to the parameters {σ1, σ, γ, ρ}.
The remaining parameters {α1, α, β, y1, y
65
2
, y
75
2
}, where the initial values Y1(0) and Y2(0) of the
two factors are denoted by y1 and y
x
2
, respectively, are then estimated as described below:7
1. From the central death rates, we obtain empirical survival curves for cohorts aged 65 and 75 in
2008. The survival curve is obtained by setting
Sˆ
x(0, T) =
T
∏v=1
e
−m(x+v−1,0)
(15)
where m(x, t) is the central death rate of an x years old at time t. Here, t = 0 represents the
calendar year 2008.
2. The parameters {α1, α, β, y1, y
65
2
, y
75
2
} are then estimated by fitting the survival curves (Sx(0, T)) of
the model to the empirical survival curves using least squares estimation, that is, by minimising
∑
x=65,75
Tx
∑
j=1

Sˆ
x(0, j) − Sx(0, j)
2
(16)
where T65 = 31 and T75 = 21, with respect to the parameters {α1, α, β, y1, y
65
2
, y
75
2
}.
The estimated parameters are reported in Table 1. Since γ > 0 we observe that the volatility of the
process is higher for older (initial) age x.
Table 1. Estimated model parameters.
Parameters σ1 σ γ ρ α1
Values 0.0022465 0.0000002 0.129832 −0.795875 0.0017508
Parameters α β y1 y
65
2
y
75
2
Values 0.0000615 0.120931 0.0021277 0.0084923 0.0294695
The upper panel of Figure 3 shows the percentiles of the simulated mortality intensity for ages 65
and 75 in the left and the right panel, respectively. One observes that the volatility of the mortality
intensity is higher for a 75 year old compared to a 65 year old. Corresponding survival probabilities are
displayed in the lower panel of Figure 3, together with the 99% confidence bands computed pointwise.
As it is pronounced from the figures, the two-factor Gaussian model specified above, despite its
simplicity, produces reasonable mortality dynamics for ages 65 and 75.
Remark 1.
1. In our model formulation, we specifically address the fact that the mortality intensity processes for different
(initial) ages are increasing as time passed. This is important for the hedging applications considered
7 We calibrate the model for ages 65 and 75 simultaneously to obtain reasonable values for α and β since the drift of the
second factor Y2(t) is age-dependent.
Risks 2019, 7, 2 8 of 25
in Section 4 since the extent of systematic mortality risk in an annuity portfolio is determined by the
randomness of the mortality intensity process.
2. The continuous-time mortality model follows a single cohort through time and the mortality rate at future
ages for the cohort includes both an age effect and a time effect, since the cohort trend is the sum of an age
effect and a time or improvement effect, so that going from age x to x + 1 there is a mortality improvement
implicitly included for the cohort. This model does not aim to fit multiple cohorts since it does not include
an explicit improvement for the same age across time. Most practical applications, such as the hedging
applications studied in Section 4, require single cohort mortality models.
0 5 10 15 20 25 30 35
0
0.5
1
1.5
2
2.5
3
3.5
4
t
µ
x(t)
Age x = 65
0 5 10 15 20 25 30 35
0
0.5
1
1.5
2
2.5
3
3.5
4
t
µ
x(t)
Age x = 75
0 5 10 15 20 25 30 35
0
0.2
0.4
0.6
0.8
1
T
Survival Probability S x (0,T)
Age x = 65
0 5 10 15 20 25 30 35
0
0.2
0.4
0.6
0.8
1
T
Survival Probability S x (0,T)
Age x = 75
5th perc.
25th perc.
50th perc.
75th perc.
95th perc.
5th perc.
25th perc.
50th perc.
75th perc.
95th perc.
99% CI
Mean
99% CI
Mean
Figure 3. Percentiles of the simulated intensity processes µ65(t) and µ75(t) for Australian males aged 65
(upper left panel) and 75 (upper right panel) in 2008, with their corresponding survival probabilities
(the mean and the 99% confidence bands) for a 65 years old (lower left panel) and 75 years old (lower
right panel).
3. Analytical Pricing of Longevity Derivatives
We consider longevity derivatives with different payoff structures including longevity swaps,
longevity caps, and longevity floors. Closed form expressions for prices of these longevity derivatives
are derived under the assumption of the two-factor Gaussian mortality model introduced in Section 2.
These instruments are written on survival probabilities and their properties are analysed from a
pricing perspective.
3.1. Risk-Adjusted Measure
For the purpose of no-arbitrage valuation, we require the dynamics of the factors Y1(t) and Y2(t)
to be written under a risk-adjusted measure. Since the longevity market is still in its development stage
Risks 2019, 7, 2 9 of 25
and hence, incomplete, we assume that a risk-adjusted measure exists but is not unique. To preserve
the tractability of the model, we assume that the processes W˜
1(t) and W˜
2(t) with dynamics
dW˜
1(t) = dW1(t) (17)
dW˜
2(t) = λY2(t)dt + dW2(t) (18)
are standard Brownian motions under a risk-adjusted measure Q. In Equation (18) the term λY2(t)
represents the market price of longevity risk, whereas λ is referred to as the longevity risk premium.
Under Q we can write the factor dynamics as follows:
dY1(t) = α1Y1(t) dt + σ1 dW˜
1(t) (19)
dY2(t) = (αx + β − λσe
γx
) Y2(t) dt + σ2 dW˜
2(t). (20)
As a result, the Gaussian property of the mortality intensity process is preserved under the
measure change. Preserving the structure (for example, an affine structure) of the underlying
process under a change of measure is of importance in financial risk management, as highlighted
in e.g., Luciano et al. (2012), where the dynamic hedging of mortality risk is studied.8 Given
Equations (19) and (20), the corresponding risk-adjusted survival probability is given by
S˜
x+t(t, T)
def = E
Q
t

e
−
R T
t
µx(v) dv
= e
1
2
Γ˜(t,T)−Θ˜ (t,T)
(21)
where α2 = αx + β is replaced by (αx + β − λσe
γx
) in the expressions for Θ˜ (t, T) and Γ˜(t, T),
see Equation (9) and Equation (10), respectively.
Since a liquid longevity market is yet to be developed, we aim to determine a reasonable value
for λ based on the longevity bond announced by BNP Paribas and European Investment Bank (EIB)
in 2004 as proposed in Cairns et al. (2006) and applied in Meyricke and Sherris (2014), see also
Wills and Sherris (2011). The BNP/EIB longevity bond is a 25-year bond with coupon payments linked
to a survivor index based on the realised mortality rates.9 The price of the longevity bond is given by
V(0) =
25
∑
T=1
B(0, T)e
δ TEP
0

e
−
R T
0
µx(v) dv
(22)
where δ is a spread, or an average risk premium per annum10, and the T-year projected survival rate is
assumed to be the T-year survival probability for the Australian males cohort aged 65 as modelled in
Section 2, see Equation (8). Since the BNP/EIB bond is priced based on a yield of 20 basis points below
standard EIB rates (Cairns et al. 2006), we have the spread of δ = 0.002.11
8 For simplicity, we assume that there is no risk adjustment for the first factor Y1 and λ is age-independent. However,
if the market demands a risk premium for the first factor Y1 then one could, similar to the case of Y2, assume that
dW˜
1(t) = λ1Y1(t)dt + dW1(t) and, hence, obtain dY1(t) = (α1 − σ1λ1)Y1(t)dt + σ1dW˜1(t) under the Q measure. In the
following we assume for simplicity and conciseness of discussion that λ1 = 0.
9 The issue price was determined by BNP Paribas using anticipated cash flows based on the 2002-based mortality projections
provided by the UK Government Actuary’s Department.
10 The spread δ depends on the term of the bond and the initial age of the cohort being tracked (Cairns et al. 2006), and δ is
related to but distinct from λ, the longevity risk premium.
11 The reference cohort for the BNP/EIB longevity bond is the England and Wales males aged 65 in 2003. Since the longevity
derivatives market is under-developed in Australia, we assume that the same spread of δ = 0.002 (as in the UK) is applicable
to the Australian males cohort aged 65 in 2008. Note however that sensitivity analyses will be performed in Section 4.
Risks 2019, 7, 2 10 of 25
Under a risk-adjusted measure Q(λ), the price of the longevity bond corresponds to
V
Q()
(0) =
25
∑
T=1
B(0, T) E
Q(λ)
0

e
−
R T
0
µx(v) dv
. (23)
Fixing the interest rate to r = 4%, we find the longevity risk premium λ, such that the risk-adjusted
bond price V
Q()
(0) matches the market bond price V(0) as close as possible. For example, for λ = 8.5
the model price corresponds to V
Q()
(0) = 11.9068, which matches very closely the market bond
price of V(0) = 11.9045. For more details on the above procedure refer to Meyricke and Sherris (2014).
In the following we assume that the risk-adjusted measure Q is determined by a unique value of λ.
Moreover, for simplicity of notation we will use Q to represent Q().
Figure 4 shows the risk-adjusted survival probabilities for Australian males aged 65 with respect
to different values of the longevity risk premium λ. As one observes from the figure, a larger (positive)
value of λ leads to an improvement in survival probability, while a smaller values of λ indicate
a decline in survival probability under the risk-adjusted measure Q.
0 5 10 15 20 25 30 35
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
Horizon T
Survival Probability S 65(0,T)
λ = 0
λ = 4.5
λ = 8.5
λ = 12.5
Figure 4. Risk-adjusted survival probability with respect to different longevity risk premiums λ.
3.2. Longevity Swaps
A longevity swap involves counterparties swapping fixed payments for payments linked to
the number of survivors in a reference population in a given time period, and can be thought of as
a portfolio of S-forwards, see Dowd (2003). An S-forward, or ‘survivor’ forward, has been developed
by LLMA (2010b). Longevity swaps can be regarded as a stream of S-forwards with different maturity
dates. One of the advantages of using S-forwards is that there is no initial capital requirement at the
inception of the contract and cash flows occur only at maturity.
Consider an annuity provider who has an obligation to pay an amount dependent on the
number of survivors, and hence, survival probability of a cohort at time T. If longevity risk is present,
the survival probability is stochastic. In order to protect himself from a larger-than-expected survival
probability, the provider can enter into an S-forward contract paying a fixed amount K ∈ (0, 1) and
receiving an amount equal to the realised survival probability exp {− R T
0
µx(v) dv} at time T. In doing
so, the survival probability that the provider is exposed to is certain, and corresponds to some fixed
Risks 2019, 7, 2 11 of 25
value K. If the contract is priced in such a way that there is no upfront cost at the inception, it must
hold that
B(0, T) E
Q
0

e
−
R T
0
µx(v) dv − K(T)

= 0 (24)
under the risk-adjusted measure Q. Thus, the fixed amount can be identified to be the risk-adjusted
survival probability, that is,
K(T) = E
Q
0

e
−
R T
0
µx(v) dv
. (25)
Assuming that there is a positive longevity risk premium, the longevity risk hedger who pays the
fixed leg and receives the floating leg bears the cost for entering an S-forward.12 Following terminology
in Biffis et al. (2014), the amount K(T) = S˜
x(0, T) can be referred to as the swap rate of an S-forward
with maturity T. In general, the mark-to-market price process F(t) of an S-forward with fixed leg K
(not necessarily K(T) as in Equation (25)) is given by
F(t) = B(t, T)E
Q
t

e
−
R T
0
µx(v) dv − K

= B(t, T)E
Q
t

e
−
R t
0
µx(v) dve−
R T
t
µx(v) dv − K

= B(t, T)

S¯
x(0, t) S˜x+t(t, T) − K

(26)
for t ∈ [0, T]. The quantity
S¯
x(0, t) = e
−
R t
0
µx(v) dv|Ft
(27)
is the realised survival probability, or the survivor index for the cohort, which is observable given Ft.
The term S¯
x(0, t) S˜x+t(t, T) that appears in Equation (26) has a natural interpretation.
Given information F0 at time t = 0, this term becomes S˜
x(0, T), which is the risk-adjusted survival
probability. As time moves on and more information Ft, with t ∈ (0, T), is revealed, the term
S¯
x(0, t) S˜
x+t(t, T) is a product of the realised survival probability of the first t years, and the
risk-adjusted survival probability in the next (T − t) years. At maturity T, this product becomes
the realised survival probability up to time T. In order words, one can think of S¯
x(0, t) S˜
x+t(t, T) as
the T-year risk-adjusted survival probability with information known up to time t.
The price process F(t) in Equation (26) depends on the swap rate S˜
x+t(t, T) of an S-forward
written on the same cohort that is now aged (x + t) at time t, with time to maturity (T − t). If a liquid
longevity market was developed, the swap rate S˜
x+t(t, T) could be obtained from market data.
As S¯
x(0, t) is observable at time t, the mark-to-market price process of an S-forward could be considered
model-independent. However, since a longevity market is still in its development stage, market swap
rates are not available and a model-based risk-adjusted survival probability S˜
x+t(t, T) has to be used
instead. An analytical formula for the mark-to-market price of an S-forward can be obtained if the
risk-adjusted survival probability is expressed in a closed-form, which can be performed, for example,
under the two-factor Gaussian mortality model.
Since a longevity swap is constructed as a portfolio of S-forwards, the price of a longevity swap is
simply the sum of the individual S-forward prices.
3.3. Longevity Caps
A longevity cap, which is a portfolio of longevity caplets, provides a similar hedge to a longevity
swap but is an option-type instrument. Consider again a scenario described in Section 3.2 where
12 The risk-adjusted survival probability will be larger than the “best estimate" P-survival probability if a positive market price
of longevity risk is demanded, see Figure 4.
Risks 2019, 7, 2 12 of 25
an annuity provider aims to hedge against larger-than-expected T-year survival probability of
a particular cohort. Alternatively to hedging with an S-forward, the provider can enter into a long
position of a longevity caplet with payoff at time T corresponding to
max ne
−
R T
0
µx(v) dv − K

, 0o(28)
where K ∈ (0, 1) is the strike price.13 If the realised survival probability is larger than K, the hedger
receives an amount exp {− R T
0
µx(v) dv} − K

from the longevity caplet. This payment can be
regarded as a compensation for the increased payments that the provider has to make in the annuity
portfolio, due to the larger-than-expected survival probability. There is no cash outflow if the realised
survival probability is smaller than or equal to K. In other words, the longevity caplet allows the
provider to “cap" its longevity exposure at K with no downside risk. Since a longevity caplet has
a non-negative payoff, it comes at a cost. The price of a longevity caplet
C`(t; T, K) = B(t, T)E
Q
t

e
−
R T
0
µx(v) dv − K
+

(29)
under the two-factor Gaussian mortality model is obtained in the following Proposition.
Proposition 2. Under the two-factor Gaussian mortality model (Equations (2)–(4)) the price at time t of a
longevity caplet C`(t; T, K), with maturity T and strike K, is given by
C`(t; T, K) = S¯
t S˜t B(t, T) Φ
q
Γ˜(t, T) − d

− KB(t, T)Φ (−d) (30)
where S¯
t = S¯x(0, t) is the realised survival probability observable at time t, S˜t = S˜x+t(t, T) is the risk-adjusted
survival probability in the next (T − t) years, d = √
1
Γ˜(t,T)

ln {K/(S¯
tS˜t)} + 1
2
Γ˜(t, T)

and Φ(·) denotes the
cumulative distribution function of a standard Gaussian random variable.
Proof. Under the risk-adjusted measure Q, we have, from Proposition (1), that
L
def = −
Z T
t
µx(v)dv ∼ N(−Θ˜ (t, T), Γ˜(t, T)). (31)
Using the simplified notation Θ˜ = Θ˜ (t, T), Γ˜ = Γ˜(t, T) we can write
C`(t; T, K) = B(t, T)E
Q
t

(S¯
t e
L − K)+

= B(t, T)
Z ∞
−∞
1
√
2πΓ˜
e
− 1
2

`+Θ˜ √
Γ˜
2 
S¯
t e
` − K
+
d`
= B(t, T)
Z ∞
ln K/S¯
t+Θ˜
√
Γ˜
1
√
2π
e
− 1
2
`
2

S¯
t e
`
√
Γ˜−Θ˜ − K

d`
= B(t, T)
 
S¯
t e
1
2
Γ˜−Θ˜
Z ∞
ln K/S¯
t+Θ˜
√
Γ˜
1
√
2π
e
− 1
2

`−
√
Γ˜
2
d` − K
Z ∞
ln K/S¯
t+Θ √
Γ˜
1
√
2π
e
− 1
2
`
2
d`
!
.
Equation (30) follows using properties of Φ(·) and noticing that S˜
t = e
1
2
Γ˜−Θ˜
, that is,
Θ˜ = 1
2
Γ˜ − ln S˜
t
.
13 The payoff of a longevity caplet is similar to the payoff of the option embedded in the principal-at-risk bond described in
Biffis and Blake (2014).
Risks 2019, 7, 2 13 of 25
Similar to an S-forward, the price of a longevity caplet depends on the product term
S¯
x(0,t) S˜
x+t(t, T). In particular, a longevity caplet is said to be out-of-the-money if K > S¯x(0,t) S˜x+t(t, T);
at-the-money if K = S¯
x(0, t) S˜x+t(t, T); and in-the-money if K < S¯x(0, t) S˜x+t(t, T).
Following the result of Proposition 2, the two-factor Gaussian mortality model leads to the price
of a longevity caplet that is a function of the following variables:
• realised survival probability S¯
x(0, t) of the first t years;
• risk-adjusted survival probability S˜
x+t(t, T) in the next T − t years;
• interest rate r;
• strike price K;
• time to maturity (T − t); and
• standard deviation q
Γ˜(t, T), which is a function of the time to maturity and the model parameters.
Since the quantity exp n−
R T
0
µx(v) dvois log-normally distributed under the two-factor Gaussian
mortality model, Equation (30) resembles the Black-Scholes formula for option pricing where the
underlying stock price follows a geometric Brownian motion. In our setup, the stock price at time t is
replaced by the T-year risk-adjusted survival probability S¯
x(0, t) Sx+t(t, T) with information available
up to time t. While the stock is traded and can be modelled directly using market data, the underlying
of a longevity caplet is the survival probability which is not tradable but can be determined as an
output from the dynamics of mortality intensity. As a result, the role of the stock price volatility in the
Black-Scholes formula is played by the standard deviation of the integral of the mortality intensity
R T
t
µx(v) dv. Since the integral R T
t
µx(v) dv captures the whole history of the mortality intensity
µx(t) from t to T under Q, one can interpret the standard deviation qΓ˜(t, T) as the volatility of the
risk-adjusted aggregated longevity risk of a cohort aged x + t at time t, for the period from t to T.
The left panel of Figure 5 shows caplet prices for a cohort aged x = 65, using parameters as
specified in Table 1, as a function of time to maturity T and strike K. We set r = 0.04, λ = 8.5 and t = 0
such that S¯
x(0, 0) = 1. A lower strike price indicates that the buyer of a caplet is willing to pay more to
secure a better protection against a larger-than-expected survival probability. On the other hand, when
the time to maturity T is increasing, the underlying survival probability is likely to take smaller values,
which leads to a higher probability for the caplet to become out-of-the-money at maturity for a fixed K,
see Equation (28). Consequently, for a fixed K the caplet price decreases with increasing T.
0.1
0.2
0.3
0.4
0.5
10
15
20
25
30
0
0.1
0.2
0.3
0.4
0.5
Time to Maturity (T) Strike (K)
Cl (0 ; T , K)
0 2 4 6 8 10 12 14
0.02
0.025
0.03
0.035
0.04
0.045
0.05
λ
Caplet Price
Figure 5. Caplet price as a function of (left panel) T and K and (right panel) λ where K = 0.4 and
T = 20.
The right panel of Figure 5 illustrates the effect of the longevity risk premium λ on the caplet
price. The price of a caplet increases with increasing λ. As shown in Figure 4, a larger value of λ will
Risks 2019, 7, 2 14 of 25
lead to an improvement in survival probability under Q. Thus, a higher caplet price is observed since
the underlying survival probability is larger (on average) under Q when λ increases, see Equation (29).
Since longevity cap is constructed as a portfolio of longevity caplets, it can be priced as a sum of
individual caplet prices, see also Section 4.1.2.
4. Managing Longevity Risk in a Hypothetical Life Annuity Portfolio
Hedging features of a longevity swap and cap are examined for a hypothetical life annuity
portfolio subject to longevity risk. Factors considered include the longevity risk premium, the term to
maturity of hedging instruments and the size of the underlying annuity portfolio.
4.1. Setup
We consider a hypothetical life annuity portfolio that consists of a cohort aged x = 65. The size
of the portfolio that corresponds to the number of policyholders, is denoted by n. The underlying
mortality intensity for the cohort follows the two-factor Gaussian mortality model described in
Section 2, and the model parameters are specified in Table 1. We assume that there is no loading for
the annuity policy and expenses are not included.
Further, we assume a single premium, whole life annuity of $1 per year payable in arrears
conditional on the survival of the annuitant to the payment dates. The fair value, or the premium, of
the annuity evaluated at t = 0 is given by
ax =
ω−x
∑
T=1
B(0, T) S˜
x(0, T) (32)
where r = 4% and ω = 110 is the maximum age allowed in the mortality model. The life annuity
provider, thus, receives a total premium, denoted by A, for the whole portfolio corresponding to the
sum of individual premiums:
A = n ax. (33)
This is the present value of the asset held by the annuity provider at t = 0. Since the promised
annuity cashflows depend on the death times of annuitants in the portfolio, the present value of
the liability is subject to randomness caused by the stochastic dynamics of the mortality intensity.
The present value of the liability for each policyholder, denoted by Lk, is determined by the death time
τk of the policyholder, and is given by
Lk =
bτk c
∑
T=1
B(0, T) (34)
for a simulated τk, with bqc denoting the next smaller integer of a real number q. The present value of
the liability L for the whole portfolio is obtained as a sum of individual liabilities:
L =
n
∑
k=1
Lk. (35)
The algorithm for simulating death times of annuitants, which requires a single simulated path
for the mortality intensity of the cohort, is summarised in Appendix A. The discounted surplus
distribution (Dno) of an unhedged annuity portfolio is obtained by setting
Dno = A − L. (36)
The impact of longevity risk is captured by simulating the discounted surplus distribution where
each sample is determined by the realised mortality intensity of a cohort. Since traditional pricing
Risks 2019, 7, 2 15 of 25
and risk management of life annuity relies on diversification effect, or the law of large numbers,
we consider the discounted surplus distribution per policy
Dno/n. (37)
Figure 6 shows the discounted surplus distribution per policy without longevity risk (i.e. when
setting σ1 = σ = 0) with different portfolio sizes, varying from n = 2000 to 8000. As expected,
the distribution is centred around zero as there is no loading assumed in the pricing algorithm, while
the standard deviation diminishes as the number of policies increases.
In the following we consider a longevity swap and a cap as hedging instruments. These are
index-based instruments where the payoffs depend on the survivor index, or the realised survival
probability (Equation (27)), which is in turn determined by the realised mortality intensity. We do not
consider basis risk14 but due to a finite portfolio size, the actual proportion of survivors, n−Nt
n
, where
Nt denotes the number of deaths experienced by a cohort during the period [0, t], will be in general
similar, but not identical, to the survivor index (Appendix A). As a result, the static hedge will be
able to reduce systematic mortality risk, whereas the idiosyncratic mortality risk component will be
retained by the annuity provider.
−0.5 0 0.5
0
1
2
3
4
5
6
7
8
9
$
Density
Discounted Surplus Distribution Per Policy 
n = 2000
n = 4000
n = 6000
n = 8000
Figure 6. Discounted surplus distribution per policy without longevity risk with different portfolio
size (n).
4.1.1. A Swap-Hedged Annuity Portfolio
For an annuity portfolio hedged by an index-based longevity swap, payments from the swap
n

e
−
R T
0
µx(v) dv − K(T)

(38)
at time T ∈ {1, ..., Tˆ } depend on the realised mortality intensity, where Tˆ denotes the term to maturity
of the longevity swap. The number of policyholders n acts as the notional amount of the swap contract
14 If basis risk is present, we need to distinguish between the mortality intensity for the population (µ
I
x
) and mortality intensity
for the cohort (µx) underlying the annuity portfolio, see Biffis et al. (2014).
Risks 2019, 7, 2 16 of 25
so that the quantity n exp{− R T
0
µx(v) dv} represents the number of survivors implied by the realised
mortality intensity at time T. We fix the strike of a swap to the risk-adjusted survival probability,
that is,
K(T) = S˜
x(0, T) = E
Q
0

e
−
R T
0
µx(v) dv
(39)
such that the price of a swap is zero at t = 0, see Section 3.2. The discounted surplus distribution of
a swap-hedged annuity portfolio can be expressed as
Dswap = A − L + Fswap (40)
where
Fswap = n
Tˆ
∑
T=1
B(0, T)

e
−
R T
0
µx(v) dv − S˜
x(0, T)

(41)
is the (random) discounted cashflow coming from a long position in the longevity swap.
The discounted surplus distribution per policy of a swap-hedged annuity portfolio is determined
by Dswap/n.
4.1.2. A Cap-Hedged Annuity Portfolio
For an annuity portfolio hedged by an index-based longevity cap, the cashflows
n max ne
−
R T
0
µx(v) dv − K(T)

, 0o(42)
at T ∈ {1, ..., Tˆ } are payments from a long position in the longevity cap. We set
K(T) = Sx(0, T) = E
P
0

e
−
R T
0
µx(v) dv
(43)
such that the strike for a longevity caplet is the “best estimated" survival probability given F0.
15
The discounted surplus distribution of a cap-hedged annuity portfolio is given by
Dcap = A − L + Fcap − Ccap (44)
where
Fcap = n
Tˆ
∑
T=1
B(0, T) max ne
−
R T
0
µx(v) dv − Sx(0, T)

, 0o(45)
is the (random) discounted cashflow from holding the longevity cap and
Ccap = n
Tˆ
∑
T=1
C` (0; T, Sx(0, T)) (46)
is the price of the longevity cap. The discounted surplus distribution per policy of a cap-hedged
annuity portfolio is given by Dcap/n.
4.2. Results
Hedging results are summarised by means of summary statistics that include mean, standard
deviation (std. dev.), skewness, as well as Value-at-Risk (VaR) and Expected Shortfall (ES) of the
discounted surplus distribution per policy of an unhedged, a swap-hedged, and a cap-hedged annuity
15 For a longevity swap, the risk-adjusted survival probability is used as a strike price so that the price of a longevity swap is
zero at inception. In contrast, a longevity cap has non-zero price and Sx(0, T) is the most natural choice for a strike.
Risks 2019, 7, 2 17 of 25
portfolio. Skewness is included since the payoff of a longevity cap is nonlinear and the resulting
distribution of a cap-hedged annuity portfolio is not symmetric. VaR is defined as the q-quantile of
the discounted surplus distribution per policy. ES is defined as the expected loss of the discounted
surplus distribution per policy given the loss is at or below the q-quantile. We fix q = 0.01 so that
the confidence interval for VaR and ES corresponds to 99%. We use 20,000 simulations to obtain
the distribution for the discounted surplus.16 Hedge effectiveness is examined with respect to (w.r.t.)
different assumptions underlying the longevity risk premium (λ), the term to maturity of hedging
instruments (Tˆ) and the portfolio size (n). Parameters for the base case are as specified in Table 2.
Table 2. Parameters for the base case.
Parameters λ Tˆ(Years) n
Values 8.5 30 4000
4.2.1. Hedging Features w.r.t. Longevity Risk Premium
The longevity risk premium λ is one of the factors that determines prices of longevity derivatives
and life annuity policies. Since payoffs of a longevity swap, a cap and a life annuity are contingent
on the same underlying mortality intensity of a cohort, all these products are priced using the
same λ. Figure 7 and Table 3 illustrate the effect of changing λ on the distributions of an unhedged,
a swap-hedged and a cap-hedged annuity portfolio. The degree of longevity risk can be quantified by
the standard deviation, the VaR and the ES of the distributions. We observe that increasing λ leads
to the shift of the distribution to the right, resulting in a higher average surplus. On the other hand,
changing λ has no impact on the standard deviation and the skewness of the distribution.
For an unhedged annuity portfolio, a higher λ leads to higher premium for the life annuity
policy since the annuity price is determined by the risk-adjusted survival probability S˜
x(0, T),
see Equation (32). In other words, an increase in the annuity price compensates the provider for
the longevity risk undertaken when selling life annuity policies. There is also a trade-off between
risk premium and affordability. Setting a higher premium will clearly improve the risk and return of
an annuity business. It might, however, reduce the interest of potential policyholders. An empirical
relationship between implied longevity and annuity prices is studied in Chigodaev et al. (2014).
16 To plot the densities of the surplus distributions (Figures 6–9), we used MATLAB’s ksdensity function, which implements
the kernel density estimation method, with default optimal bandwidth.
Risks 2019, 7, 2 18 of 25
−1.5 −1 −0.5 0 0.5 1 1.5
0
1
2
3
4
5
6
λ = 0
no hedge
swap
cap
−1.5 −1 −0.5 0 0.5 1 1.5
0
1
2
3
4
5
6
λ = 4.5
no hedge
swap
cap
−1.5 −1 −0.5 0 0.5 1 1.5
0
1
2
3
4
5
6
λ = 8.5
no hedge
swap
cap
−1.5 −1 −0.5 0 0.5 1 1.5
0
1
2
3
4
5
6
λ = 12.5
no hedge
swap
cap
Figure 7. Effect of the longevity risk premium λ on the discounted surplus distribution per policy.
Table 3. Hedging features of a longevity swap and cap w.r.t. longevity risk premium λ.
Mean Std. dev. Skewness VaR0.99 ES0.99
λ = 0
No hedge −0.0059 0.3614 −0.3553 −0.9385 −1.1185
Swap-hedged −0.0086 0.0718 −0.3704 −0.1870 −0.2277
Cap-hedged −0.0067 0.2031 0.9864 −0.3200 −0.3584
λ = 4.5
No hedge 0.1536 0.3614 −0.3552 −0.7795 −0.9588
Swap-hedged 0.0051 0.0718 −0.3721 −0.1730 −0.2140
Cap-hedged 0.0701 0.2031 0.9867 −0.2435 −0.2815
λ = 8.5
No hedge 0.2995 0.3614 −0.3553 −0.6335 −0.8131
Swap-hedged 0.0207 0.0718 −0.3699 −0.1575 −0.1984
Cap-hedged 0.1224 0.2031 0.9864 −0.1910 −0.2293
λ = 12.5
No hedge 0.4492 0.3614 −0.3553 −0.4835 −0.6633
Swap-hedged 0.0401 0.0718 −0.3697 −0.1380 −0.1790
Cap-hedged 0.1637 0.2031 0.9863 −0.1500 −0.1879
When a life annuity portfolio is hedged using a longevity swap, the standard deviation and
the absolute values of the VaR and the ES are reduced substantially. The higher return obtained by
charging a larger longevity risk premium in life annuity policies is offset by an increased price paid
implicitly in the swap contract (since S˜
x(0, T) ≥ Sx(0, T) in Equation (41)). It turns out that as λ
increases an extra return earned in the annuity portfolio and the higher implicit cost of the longevity
swap nearly offset each other on average. The net effect is that a swap-hedged annuity portfolio
Risks 2019, 7, 2 19 of 25
remains to a great extent unaffected by the assumption on λ, leading only to a very minor increase
in the mean of the distribution. This minor increase can even be reduced if we assume a longer term
to maturity Tˆ of hedging duration. For instance, if Tˆ = 40 instead of 30, the mean of the distribution
for the swap-hedged portfolio becomes −0.0088, −0.0087, −0.0086, −0.0084, which corresponds to the
case of λ = 0, 4.5, 8.5, 12.5, respectively. The results for Tˆ = 30 are displayed in Table 3.
For a cap-hedged annuity portfolio, the discounted surplus distribution is positively skewed since
a longevity cap allows an annuity provider to get exposure to the upside potential when policyholders
live shorter than expected. Compared to an unhedged portfolio, the standard deviation and the
absolute values of the VaR and the ES are also reduced but the reduction is smaller compared
to a swap-hedged portfolio. When λ increases, we observe that the mean of the distribution
for a cap-hedged portfolio increases faster than for a swap-hedged portfolio but slower than for
an unhedged portfolio. It can be explained by noticing that when the survival probability of a cohort is
overestimated, that is, when annuitants turn out to live shorter than expected, holding a longevity cap
has no effect (besides paying the price of a cap for longevity protection at the inception of the contract)
while there is a cash outflow when holding a longevity swap, see Equations (41) and (45).
In the longevity risk literature, the VaR and the ES are of a particular importance as they are
the main factors determining the capital reserve when dealing with exposure to longevity risk
(Meyricke and Sherris (2014)). As shown in Table 3, the difference between a swap-hedged and
a cap-hedged portfolio in terms of the VaR and the ES becomes smaller when λ increases. In fact,
for λ ≥ 17.5, a longevity cap becomes more effective in reducing the tail risk of an annuity portfolio
compared to a longevity swap.17 This result suggests that a longevity cap, besides being able to capture
the upside potential, can be a more effective hedging instrument than a longevity swap in terms of
reducing the VaR and the ES when the demanded longevity risk premium λ is large, assuming the
annuity and the longevity hedging instruments are priced using the same λ.
4.2.2. Hedging Features w.r.t. Term to Maturity
Table 4 and Figure 8 summarize hedging results with respect to the term to maturity of hedging
instruments. Due to the long-term nature of the contracts, the hedges are ineffective for Tˆ ≤ 10 years
and the standard deviations are reduced only by around 5% − 10% for both instruments. The lower
left panel of Figure 3 shows that there is little randomness around the realised survival probability for
the first few years for a cohort aged 65, and consequently the hedges are insignificant when Tˆ is short.
The difference in hedge effectiveness between Tˆ = 30 and Tˆ = 40 for both instruments is also
insignificant. In fact, the longevity risk underlying the annuity portfolio becomes small after 30 years
since the majority of annuitants are already deceased before reaching the age of 95. In our model
setup the chance, on average, for a 65 year old to live up to 95 is around 6% (Figure 4 with λ = 0)
and, hence, only around 4000 × 6% = 240 policies will still be in-force after 30 years. Much of the risk
left is attributed to idiosyncratic mortality risk, and hedging longevity risk for a small portfolio using
index-based instruments is of limited use.
For a swap-hedged portfolio, the standard deviation is reduced significantly when Tˆ > 20 years.
The mean surplus, on the other hand, drops to nearly zero since there is a higher cost implied for the
hedge with increasing number of S-forwards involved to form the swap as Tˆ increases.
Similar hedging features with respect to Tˆ are observed for a longevity cap. However,
the skewness of the distribution of a cap-hedged portfolio increases with increasing Tˆ. It can be
explained by noticing that while a longevity cap is able to capture the upside potential (when
policyholders live shorter than expected) regardless of Tˆ, it provides a better longevity risk protection
17 Given λ = 17.5, the VaR and the ES for a swap-hedged portfolio are −0.1079 and −0.1488, respectively. For a cap-hedged
portfolio they become −0.1047 and −0.1428, respectively.
Risks 2019, 7, 2 20 of 25
(when policyholders live longer than expected) in case Tˆ is larger. As a result, the distribution of a
cap-hedged portfolio becomes more asymmetric when Tˆ increases.
−1.5 −1 −0.5 0 0.5 1 1.5
0
1
2
3
4
5
6
Term = 10 years
no hedge
swap
cap
−1.5 −1 −0.5 0 0.5 1 1.5
0
1
2
3
4
5
6
Term = 20 years
no hedge
swap
cap
−1.5 −1 −0.5 0 0.5 1 1.5
0
1
2
3
4
5
6
Term = 30 years
no hedge
swap
cap
−1.5 −1 −0.5 0 0.5 1 1.5
0
1
2
3
4
5
6
Term = 40 years
no hedge
swap
cap
Figure 8. Effect of the term to maturity Tˆ of the hedging instruments on the discounted surplus
distribution per policy.
Table 4. Hedging features of a longevity swap and cap w.r.t. term to maturity Tˆ.
Mean Std. Dev. Skewness VaR0.99 ES0.99
Tˆ = 10 Years
No hedge 0.2995 0.3614 −0.3553 −0.6335 −0.8131
Swap-hedged 0.2835 0.3262 −0.4693 −0.5840 −0.7608
Cap-hedged 0.2907 0.3427 −0.3517 −0.5960 −0.7717
Tˆ = 20 Years
No hedge 0.2995 0.3614 −0.3553 −0.6335 −0.8131
Swap-hedged 0.1745 0.1908 −0.8593 −0.3755 −0.5159
Cap-hedged 0.2247 0.2679 0.0864 −0.4050 −0.5399
Tˆ = 30 Years
No hedge 0.2995 0.3614 −0.3553 −0.6335 −0.8131
Swap-hedged 0.0207 0.0718 −0.3699 −0.1575 −0.1984
Cap-hedged 0.1224 0.2031 0.9864 −0.1910 −0.2293
Tˆ = 40 Years
No hedge 0.2995 0.3614 −0.3553 −0.6335 −0.8131
Swap-hedged −0.0086 0.0667 0.0384 −0.1605 −0.1850
Cap-hedged 0.1005 0.1972 1.0637 −0.1890 −0.2151
4.2.3. Hedging Features w.r.t. Portfolio Size
Table 5 and Figure 9 demonstrate hedging features of a longevity swap and a cap with changing
portfolio size n. We observe a decrease in standard deviation, as well as the VaR and the ES (in absolute
terms) when portfolio size increases. Compared to an unhedged portfolio, the reduction in the standard
Risks 2019, 7, 2 21 of 25
deviation and the risk measures is larger for a swap-hedged portfolio, compared to a cap-hedged
portfolio. Recall that idiosyncratic mortality risk becomes significant when n is small. We quantify
the effect of the portfolio size on hedge effectiveness by introducing the measure of longevity risk
reduction R, defined in terms of the variance of the discounted surplus per policy, that is,
R = 1 −
Var(D¯ ∗)
Var(D¯ )
, (47)
where Var(D¯ ∗) and Var(D¯ ) represent the variances of the discounted surplus distribution per policy
for a hedged and an unhedged annuity portfolio, respectively. The results are reported in Table 6.
Li and Hardy (2011) consider hedging longevity risk using a portfolio of q-forwards and find
the longevity risk reduction of 77.6% and 69.6% for portfolio size of 10,000 and 3000, respectively.
In contrast to Li and Hardy (2011), we do not consider basis risk and the result of using longevity
swap as a hedging instrument leads to a greater risk reduction. Overall, our results indicate that
hedge effectiveness for an index-based longevity swap and a cap diminishes with decreasing n
since idiosyncratic mortality risk cannot be effectively diversified away for a small portfolio size.
Even though a longevity cap is less effective in reducing the variance, part of the dispersion is
attributed to its ability of capturing the upside of the distribution when survival probability of a cohort
is overestimated. From Table 5 we also observe that the distribution becomes more positively skewed
for a cap-hedged portfolio when n increases, which is a consequence of having a larger exposure to
longevity risk with increasing number of policyholders in the portfolio.
Table 5. Hedging features of a longevity swap and cap w.r.t. different portfolio size (n).
Mean Std.dev. Skewness VaR0.99 ES0.99
n = 2000
No hedge 0.2993 0.3679 −0.3357 −0.6530 −0.8277
Swap-hedged 0.0206 0.0980 −0.1243 −0.2100 −0.2596
Cap-hedged 0.1222 0.2141 0.8556 −0.2395 −0.2870
n = 4000
No hedge 0.2995 0.3614 −0.3553 −0.6335 −0.8131
Swap-hedged 0.0207 0.0718 −0.3699 −0.1575 −0.1984
Cap-hedged 0.1224 0.2031 0.9864 −0.1910 −0.2293
n = 6000
No hedge 0.2991 0.3598 −0.3615 −0.6435 −0.8147
Swap-hedged 0.0204 0.0604 −0.6155 −0.1340 −0.1762
Cap-hedged 0.1220 0.1999 1.0432 −0.1690 −0.2116
n = 8000
No hedge 0.2987 0.3592 −0.3627 −0.6395 −0.8180
Swap-hedged 0.0200 0.0542 −0.7624 −0.1210 −0.1644
Cap-hedged 0.1216 0.1984 1.0702 −0.1630 −0.2016
Risks 2019, 7, 2 22 of 25
−1.5 −1 −0.5 0 0.5 1 1.5
0
1
2
3
4
5
6
7
8
n = 2000
no hedge
swap
cap
−1.5 −1 −0.5 0 0.5 1 1.5
0
1
2
3
4
5
6
7
8
n = 4000
no hedge
swap
cap
−1.5 −1 −0.5 0 0.5 1 1.5
0
1
2
3
4
5
6
7
8
n = 6000
no hedge
swap
cap
−1.5 −1 −0.5 0 0.5 1 1.5
0
1
2
3
4
5
6
7
8
n = 8000
no hedge
swap
cap
Figure 9. Effect of the portfolio size n on the discounted surplus distribution per policy.
Table 6. Longevity risk reduction R of a longevity swap and cap w.r.t. different portfolio size (n).
n 2000 4000 6000 8000
Rswap 92.9% 96.0% 97.1% 97.7%
Rcap 66.1% 68.4% 69.1% 69.4%
5. Conclusions
Life and pension annuities are the most important types of post-retirement products offered by
annuity providers to help secure lifelong incomes for the rising number of retirees. While interest
rate risk can be managed effectively in the financial markets, longevity risk is a major concern
for annuity providers as there are only limited choices available to mitigate the long-term risk.
Development of effective financial instruments for longevity risk in capital markets is arguably the
best solution available.
Two types of longevity derivatives, a longevity swap and a cap, are analysed in this paper from
a pricing and hedging perspective. We apply a tractable Gaussian mortality model to capture the
longevity risk, and derive explicit formulas for important quantities such as survival probabilities
and prices of longevity derivatives. Hedge effectiveness and features of an index-based longevity
swap and a cap used as hedging instruments are examined using a hypothetical life annuity portfolio
exposed to longevity risk.
Our results suggest that the longevity risk premium λ is a small contributor to hedge effectiveness
of a longevity swap since a higher annuity price is partially offset by an increased cost of hedging
when λ is taken into account. It is shown that a longevity cap, while being able to capture the upside
potential when survival probabilities are overestimated, can be more effective in reducing longevity
tail risk compared to a longevity swap, provided that λ is large enough. The term to maturity Tˆ is
Risks 2019, 7, 2 23 of 25
an important factor in determining hedge effectiveness. However, the difference in hedge effectiveness
is only marginal when Tˆ increases from 30 to 40 years for an annuity portfolio consisting of a single
cohort aged 65 initially. This is due to the fact that only a small number of policies will still be in-force
after a long period of time (30 to 40 years), and index-based instruments turn out to be ineffective when
idiosyncratic mortality risk becomes a larger contributor to the overall risk, compared to systematic
mortality risk. The effect of the portfolio size n on hedge effectiveness is quantified and compared
with the result obtained in Li and Hardy (2011), where population basis risk is taken into account.
In addition, we find that the skewness of the surplus distribution of a cap-hedged portfolio is sensitive
to the term to maturity and the portfolio size, and, as a result, the difference between a longevity swap
and a cap when used as hedging instruments becomes more pronounced for larger Tˆ and n.
As discussed in Biffis and Blake (2014), developing a liquid longevity market requires reliable
and well-designed financial instruments that can attract sufficient amount of interests from both
buyers and sellers. Besides a longevity swap, which is so far a common longevity hedging choice
for annuity providers, option-type instruments such as longevity caps can provide hedging features
that linear products cannot offer. A longevity cap is shown to have alternative hedging properties
compared to a swap, and this option-type instrument would also appeal to certain classes of investors
interested in receiving premiums by selling a longevity insurance. Further research on the design of
longevity-linked instruments from the perspectives of buyers and sellers would provide a further step
towards the development of an active longevity market.
Author Contributions: Conceptualization, M.C.F.; Formal analysis, M.C.F.; Methodology, K.I. and M.S.; Software,
M.C.F.; Supervision, K.I. and M.S.; Validation, M.C.F., K.I. and M.S.; Writing-review & editing, K.I. and M.S.
Funding: This research received no external funding.
Conflicts of Interest: The authors declare no conflict of interest.
Appendix A
To simulate death times of annuitants, we notice that once a sample of the mortality intensity
is obtained, the Cox process becomes an inhomogeneous Poisson process and the first jump times,
which are interpreted as death times, can be simulated as follows (see e.g., Brigo and Mercurio (2007)):
1. Simulate the mortality intensity µx(t) from t = 0 to t = ω − x.
2. Generate a standard exponential random variable ξ. For example, using an inverse transform
method, we have ξ = − ln (1 − u) where u ∼ Uniform(0, 1).
3. Set the death time τ to be the smallest T such that ξ ≤
R T
0
µx(s) ds. If ξ >
R ω−x
0
µx(s) ds then set
τ = ω − x.
4. Repeat step (2) and (3) to obtain another death time.
The payoff of an index-based hedging instrument depends on the realised survival probability,
the quantity exp{− R t
0
µx(v) dv}. The payoff of a customised instrument, on the other hand, depends
on the proportion of survivors, n−Nt
n
, underlying an annuity portfolio where the number of deaths, Nt,
is obtained by counting the number of simulated death times that are smaller than t. Note that
e
−
R t
0
µx(v) dv ≈
n − Nt
n
(A1)
and the accuracy of the approximation improves when n increases.
References
Bauer, Daniel, Matthias Borger, and Jochen Russ. 2010. On the pricing of longevity-linked securities. Insurance:
Mathematics and Economics 46: 139–49. [CrossRef]
Biffis, Enrico. 2005. Affine processes for dynamics mortality and actuarial valuations. Insurance: Mathematics and
Economics 37: 443–68. [CrossRef]
Risks 2019, 7, 2 24 of 25
Biffis, Enrico, and David Blake. 2014. Keeping some skin in the game: How to start a capital market in longevity
risk transfers. North American Actuarial Journal 18: 14–21. [CrossRef]
Biffis, Enrico, David Blake, Lorenzo Pitotti, and Ariel Sun. 2014. The cost of counterparty risk and collateralization
in longevity swaps. Journal of Risk and Insurance 83: 387–419. [CrossRef]
Blake, David, and William Burrows. 2001. Survivor bonds: Helping to hedge mortality risk. Journal of Risk and
Insurance 68: 339–48. [CrossRef]
Blake, David, Andrew Cairns, Guy Coughlan, Kevin Dowd, and Richard MacMinn. 2013. The new life market.
Journal of Risk and Insurance 80: 501–57. [CrossRef]
Blake, David, Andrew J. G. Cairns, and Kevin Dowd. 2006. Living with mortality: Longevity bonds and other
mortality-linked securities. British Actuarial Journal 12: 153–228. [CrossRef]
Blake, David, Andrew Cairns, Kevin Dowd, and Richard MacMinn. 2006. Longevity bonds: Financial engineering,
valuation and hedging. Journal of Risk and Insurance 73: 647–72. [CrossRef]
Boyer, Martin, and Lars Stentoft. 2013. If we can simulate it, we can insure it: An application to longevity risk
management. Insurance: Mathematics and Economics 52: 35–45. [CrossRef]
Brigo, Damiano, and Fabio Mercurio. 2007. Interest Rate Models, 2nd ed. Berlin: Springer.
Cairns, Andrew. 2011. Modelling and mangement of longevity risk: Approximations to survivor functions and
dynamic hedging. Insurance: Mathematics and Economics 49: 438–53.
Cairns, Andrew, David Blake, and Kevin Dowd. 2006. A two-factor model for stochastic mortality with parameter
uncertainty: Theory and calibration. Journal of Risk and Insurance 73: 687–718. [CrossRef]
Cairns, Andrew, Kevin Dowd, David Blake, and Guy Coughlan. 2014. Longevity hedge effectiveness:
A decomposition. Quantitative Finance 14: 217–35. [CrossRef]
Chigodaev, Alexander, Moshe A. Milevsky, and Tom S. Salisbury. 2014. How Long Does the Market Think You Will
Live? Implying Longevity From Annuity Prices. Technical Report; Toronto: IFID Center.
Cocco, João F. and Francisco J. Gomes. 2012. Longevity risk, retirement savings, and financial innovation. Journal
of Financial Economics 103: 507–29. [CrossRef]
Donnelly, Ryan, Sebastian Jaimungal, and Dmitri H. Rubisov. 2014. Valuing guaranteed withdrawal benefits with
stochastic interest rates and volatility. Quantitative Finance 14: 369–82. [CrossRef]
Dowd, Kevin. 2003. Survivor bonds: A comment on Blake and Burrows. Journal of Risk and Insurance 70: 339–48.
[CrossRef]
Fung, Man Chung, Katja Ignatieva, and Michael Sherris. 2014. Systematic mortality risk: An analysis of
guarantee lifetime withdrawal benefits in variable annuities. Insurance: Mathematics and Economics 58:
103–15. [CrossRef]
Towers Watson. 2013. Global Pension Assets Study. Technical Report. Available online: http://www.towerswatson.
com (accessed on 27 November 2018).
Hari, Norbert, Anja De Waegenaere, Bertrand Melenberg, and Theo E. Nijman. 2008. Longevity risk in portfolios
of pension annuities. Insurance: Mathematics and Economics 42: 505–19. [CrossRef]
Huang, Yao Tung, and Yue Kuen Kwok. 2016. Regression-based monte carlo methods for stochastic control
models: Variable annuities with lifelong guarantees. Quantitative Finance 16: 905–28. [CrossRef]
Ignatieva, Katja, Andrew Song, and Jonathan Ziveyi. 2016. Pricing and hedging of guaranteed minimum benefits
under regime-switching and stochastic mortality. Insurance: Mathematics and Economics 70: 286–300.
Li, Johnny, and Mary R. Hardy. 2011. Measuring basis risk in longevity hedges. North American Actuarial
Journal 15: 177–200. [CrossRef]
LLMA. 2010a. Longevity pricing framework. Available online: http://docplayer.net/51341950-Longevity-pricingframework.html (accessed on 27 November 2018).
LLMA. 2010b. Technical Note: The S-Forward. London: Life and Longevity Markets Association (LLMA).
Luciano, Elisa, Luca Regis, and Elena Vigna. 2012. Delta-Gamma hedging of mortality and interest rate risk.
Insurance: Mathematics and Economics 50: 402–12. [CrossRef]
Luciano, Elisa, and Elena Vigna. 2008. Mortality risk via affine stochastic intensities: Calibration and empirical
relevance. Belgian Actuarial Bulletin 8: 5–16.
Meyricke, Ramona, and Michael Sherris. 2014. Longevity risk, cost of capital and hedging for life insurers under
solvency II. Insurance: Mathematics and Economics 55: 147–55. [CrossRef]
Risks 2019, 7, 2 25 of 25
Ngai, Andrew, and Michael Sherris. 2011. Longevity risk management for life and variable annuities:
The effectiveness of static hedging using longevity bonds and derivatives. Insurance: Mathematics and
Economics 49: 100–14. [CrossRef]
Peng, Jingjiang, Kwai Sun Leung, and Yue Kuen Kwok. 2012. Pricing guaranteed minimum withdrawal benefits
under stochastic interest rates. Quantitative Finance 12: 993–41. [CrossRef]
Wang, Chou-Wen, and Sharon S. Yang. 2013. Pricing survivor derivatives with cohort mortality dependence
under the Lee-Carter framework. Journal of Risk and Insurance 80: 1027–56. [CrossRef]
Wills, Samuel, and Michael Sherris. 2011. Integrating Financial and Demographic Longevity Risk Models: An Australian
Model for Financial Applications. UNSW Australian School of Business Research Paper No. 2008ACTL05.
Sydney: UNSW.
Yueh, Meng-Lan, Hsin-Yu Chiu, and Shou-Hsun Tsai. 2016. Valuations of mortality-linked structured products.
The Journal of Derivatives 24: 66–87. [CrossRef]
c 2019 by the authors. Licensee MDPI, Basel, Switzerland. This article is an open access
article distributed under the terms and conditions of the Creative Commons Attribution
(CC BY) license (http://creativecommons.org/licenses/by/4.0/).