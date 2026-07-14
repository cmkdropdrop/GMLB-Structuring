https://openaccess.city.ac.uk/id/eprint/4038/1/Valuation_of_guaranteed_Final_version_Haberman_Piscopo.pdf
→ https://openaccess.city.ac.uk/id/eprint/4038/1/Valuation_of_guaranteed_Final_version_Haberman_Piscopo.pdf
Content-Type: application/pdf

 
Copyright and Reuse: Copyright and Moral Rights remain with the author(s) and/or
copyright holders. Copies of full items can be used for personal research or study,
educational, or not-for-profit purposes without prior permission or charge, unless otherwise
indicated, provided that the authors, title and full bibliographic details are credited, a
hyperlink and/or URL is given for the original metadata page and the content is not changed
in any way. For full details of reuse please refer to City Research Online policy.
City Research Online: http://openaccess.city.ac.uk/ publications@citystgeorges.ac.uk
Citation: Piscopo, G. & Haberman, S. (2011). The valuation of guaranteed 
lifelong withdrawal benefit options in variable annuity contracts and the impact of 
mortality risk. North American Actuarial Journal, 15(1), pp. 59-76. doi: 
10.1080/10920277.2011.10597609 
This is the accepted version of the paper.
This version of the publication may differ from the final published version. To cite 
this item please consult the publisher's version.
Permanent repository link: https://openaccess.city.ac.uk/id/eprint/4038/
Link to published version: https://doi.org/10.1080/10920277.2011.10597609
City Research Online
City St George’s, University of London
1
The valuation of Guaranteed Lifelong Withdrawal Benefit Options in 
Variable Annuity contracts and the impact of mortality risk
 Haberman S.*, Piscopo G.**1
Abstract
In the light of the growing importance of the Variable Annuities market, in this paper we introduce 
a theoretical model for the pricing and valuation of Guaranteed Lifelong Withdrawal Benefit 
Options (GLWB) embedded in Variable Annuity products. As the name suggests, this option offers 
a lifelong withdrawal guarantee; therefore, there is no limit on the total amount that is withdrawn 
over the term of the policy, because if the account value becomes zero while the insured is still alive 
he continues to receive the guaranteed amount annually until death. Any remaining account value 
at the time of death is paid to the beneficiary as a death benefit We offer a specific framework to 
value the GLWB in a market consistent manner under the hypothesis of a static withdrawal strategy,
according to which the withdrawal amount is always equal to the guaranteed amount. The valuation 
approach is based on the decomposition of the product into living and death benefits. The model 
makes use of the standard no-arbitrage models of mathematical finance, that extend the BlackScholes framework to insurance contracts, assuming the fund follows a Geometric Brownian 
Motion and the insurance fee is paid, on an ongoing basis, as a proportion of the assets. We 
develop a sensitivity analysis, which shows how the value of the product varies with the key 
parameters, including the age of the policyholder at the inception of the contract, the guaranteed 
rate, the risk free rate and the fund volatility. We calculate the fair fee, using Monte Carlo 
simulations under different scenarios. We give special attention to the impact of mortality risk on 
the value of the option, using a flexible model of mortality dynamics, which allows for the possible 
perturbations by mortality shock of the standard mortality tables used by practitioners. Moreover, 
we evaluate the introduction of roll-up and step-up options and the effect of the decision to delay 
withdrawing. Empirical analyses are performed and numerical results are provided.
Keywords: Guaranteed Lifelong Withdrawal Benefit option, mortality risk, sensitivity analysis, 
stochastic mortality model, Variable Annuity.
JEL classification: G22
 
* Professor of Actuarial Science and Deputy Dean of Cass Business School, City University, 106 Bunhill Row London 
EC1Y 8TZ, UK. Internet address: s.haberman@city.ac.uk
** Dipartimento di Matematica e Statistica, Facoltà di Economia Università degli Studi di Napoli “FedericoII”, via 
Chintia, Complesso Monte S.Angelo 80126 Napoli- Italy. Internet addresses: Gabriella.Piscopo.1@city.ac.uk, 
gabriella.piscopo@unina.it
2
1. Introduction
Variable Annuities (VA) were introduced in the 1970s in the United States. This market has 
increased considerably in size in the past decade, when bullish financial markets and low interest 
rates have tempted investors to look for higher returns. VA, whose benefits are based on the 
performance of an underlying fund, are very attractive, because they provide a participation in the 
stock market and also a partial protection against the downside movements of interest rates or the 
equity market. The typical VA is a unit-linked deferred annuity contract. Since the 1990s, two kinds 
of embedded guarantees have been offered in such policies (see Hanif et al (2007)): the Guaranteed 
Minimum Death Benefit (GMDB) and the Guaranteed Minimum Living Benefit (GMLB). There 
are three main products which guarantee some living benefits: the two earliest forms, the
Guaranteed Minimum Accumulation Benefit (GMAB) and the Guaranteed Minimum Income 
Benefit (GMIB), offer the policyholder a guaranteed minimum at the maturity T of the contract; 
however, with the GMIB, this guarantee only applies if the account value is annuitized at time T. In
2002, a new type of GMLB was issued: the Guaranteed Minimum Withdrawal Benefit (GMWB), 
which gives the insured the possibility to withdraw a pre-specified amount annually, even if the 
account value has fallen below this amount. In 2004, each of the 15 largest Variable Annuity 
providers in the US offered this guarantee and 69% of the Variable Annuities sold included a 
GMWB option (Lehman Brothers (2005)); in 2007 the percentage was 86% (see Ledlie at al. 
(2007)).
In this paper, we analyze the latest GMWB option: the Guaranteed Minimum Withdrawal Benefit 
for Life or Guaranteed Lifelong Withdrawal Benefit option (GLWB). As the name suggests, it 
offers a lifelong withdrawal guarantee; therefore, there is no limit to the total amount that is 
withdrawn over the term of the policy, because, if the account value becomes zero while the insured 
is still alive, he can continue to withdraw the guaranteed amount annually until death. The first VA 
with a withdrawal benefit guaranteed for the life was introduced in the US market in 2003. Since 
3
2006, nine out of ten VA products have offered guaranteed living benefits; GLWB options captured 
some GMIB markets and represented the 35% of the whole market in early 2006 (see Advantage 
Compendium 2008). Despite these developments, until now, the actuarial literature has tended to 
focus on GMWBs, paying little attention to the differences with the GLWB options. In this regard, 
our purpose is to offer a specific framework to value the GLWB in a market consistent manner
under the hypothesis of a static withdrawal strategy and describe the impact of the main risk factors
over time, especially the impact of mortality risk. Our work uses the standard no-arbitrage models
of mathematical finance, in line with the tradition of Boyle and Schwartz (1977) that extended the 
Black-Scholes framework to insurance contracts. The main difference is that, for the options
embedded in VA products, the fee is deducted on an ongoing basis as a proportion of the market 
value of the underlying assets, while in the Black and Scholes approach the option premium is paid 
up-front.
Our approach follows the recent actuarial literature on the valuation of VA products: Ballotta and
Haberman (2003); Bauer et al. (2008);, Chen et al. (2008), Coleman et al. (2006); Holz et al (2006),
Liu (2010), Milevsky and Posner (2001), Milevsky and Promislow (2001), Milevsky and Salisbury
(2002), Milevsky and Salisbury (2006). We consider a static strategy in which the policyholder 
withdraws the guaranteed amount each year. Milevsky and Salisbury (2006) highlight that “most, if 
not all, insurance companies assume this type of behavior on the part of policyholders”. There are 
some important reasons for our making this choice. First of all, VAs providers can influence the 
behavior of policyholders through imposing penalty charges on the amount of withdrawal that 
exceeds the guaranteed amount. In addition, we have to consider that these options are being 
introduced in pension plans, in order to ensure a constant income during retirement and provide 
protection against market downside risk. Moreover, the value of a lifetime GMWB is only slightly 
higher to an arbitrageur with optimal behavior than it is to the more simplistic deterministic 
withdrawal behavior of a typical investor (Xiong et al. 2010). Under the static hypothesis, we 
decompose the payoff into life benefits and death benefits and offer a valuation formula. The 
sensitivity of the price of the product to changes in the key parameters is analyzed. The aim of this 
work is to offer a guideline for the insurance companies to price and manage this new product, 
which is affected by financial and mortality risk due the long maturity. In particular, we study the 
impact of mortality risk on the value of a GLWB using a stochastic approach, which we believe is 
necessary in order to avoid underestimation or overestimation of the expected present value of 
insurance and annuity contracts. Indeed, recently unanticipated changes over time in the mortality 
4
rates have been observed. In this note, we propose a simplified version of the stochastic model 
suggested by Cox and Lin (2005) and developed by Ballotta et al (2006). We present an application
using Italian data.
The remainder of the paper is organized as follows. In section 2, we describe the product. Section 3 
develops the model for the pricing of a GLWB option. In section 4, we carry out a sensitivity 
analysis, in which we analyze the effects of changes in the parameters of the pricing model on the 
GLWB value. In Section 5, we study the impact of mortality risk on the value of the contract using 
a simulation-based stochastic mortality model. Concluding remarks are offered in section 6.
 2. Product description
The GLWB is the latest variant of the GMWB option recently introduced in US, Asia and Europe.
Products with a GMWB option give the policyholder the possibility to withdraw annually a certain 
percentage g of the single premium W0,that is invested in one or several mutual funds. The 
guarantee consists of the entitlement to withdraw amounts until an amount equal to the premium
paid even if the account value falls to zero. Instead, if the account value does not vanish, at maturity 
the policyholder can take out or annuitize any remaining funds. Products with a GLWB option 
offer a lifelong guarantee: the maximum amount to be withdrawn is specified but the total amount is 
not limited and the insured can annually request a portion of the premium paid while he is still 
alive, even if the fund value drops to zero. Any remaining account value at the time of death is paid 
to the beneficiary as a death benefit. The insurer charges a fee for this guarantee, which is usually a 
pre-specified annual percentage of the account value. 
Many additional features can be added to this base contract:
- in the case of a Roll-up option, the annual guaranteed withdrawal amount is increased by a fixed 
percentage every year during a certain time period but only if the policyholder has not started 
withdrawing money. Therefore, Roll-ups are commonly used as a disincentive to withdraw during 
the first years;
- when the contract contains a Step-up option, at pre-specified points in time (step-up dates), the 
guaranteed annual withdrawal amount is increased if, at the step up date, the percentage g of the 
account value exceeds the contractual guaranteed amount G=gW0. Therefore, Step-ups occur if the 
fund has a high performance and the account value has not been decreased too greatly by previous 
withdrawals;
5
- in the case of a deferred version of the contract, the policyholder cannot withdraw money during 
the deferment period; however, at the end of this period, if the fund value has fallen below the 
guaranteed amount, the VA provider has to add enough money to the fund in order to reproduce the 
guaranteed level.
In order to explain the operation of GMWB and GLWB options, we provide a simple numerical 
example. Let Wt the market value of the underling fund at time t and let 100 the initial investment, 
so W0=100. In a typical GMWB contract without Roll-up or Step-up the amount guaranteed is gW0.
Let g, the guaranteed rate, be equal to 7% and then G, the guaranteed amount, is equal to 7 in this 
particular case, given the single premium. The guarantee continues until the amount of 100 has been 
withdrawn, so the minimum period is 100/7=14.28 years. The withdrawal dates are fixed by the 
contract and between two dates the guaranteed amount G is equal to 0. If during this period Wt
collapses to zero the investor will withdraw 7 per year until T=14.28. Instead, if the account value 
does not vanish, at the expiration date the policyholder can take out or annuitize any remaining 
funds. Moreover, in any given year, the policyholder is entitled to withdraw an amount less than 7 
and thereby extend the life of the guarantee or an amount greater than 7 and hence reduce it. 
In a typical GLWB contract, there is no limit for the total amount that is withdrawn over the term of 
the policy, because, if the account value becomes zero while the insured is still alive, he will 
continue to withdraw 7 until death. Any remaining account value at the time of death is paid to the 
beneficiary as a death benefit. If the policyholder withdraws an amount less or greater than 7, this 
does not have an effect on the life of guarantee but does have an effect on the death benefit which is 
linked to the account value.
3. The model 
Let Г be the future lifetime random variable expressed in continuous time, 
F (t) x
be its cdf and
f (t) x
be its pdf ; therefore, for an individual aged x the probability of death before time t is 






          
t
Fxt P t
t qx t px
x s ds
0
( ) ( ) 1 1 exp ( ) (1)
where µ denotes the force of mortality.
6
Let us introduce two probability spaces 
 
' '
, ,P
and 
 
'' ''
, ,P
, where 
'

and 
''

are the σalgebras containing respectively the financial events and the demographic events. It is reasonable to 
assume the independence of the randomness in mortality and that in interest rates, and so we denote 
the space
,,P
generated by the proceeding two spaces. Let 
P
be the real probability measure. 
Let Wt be the fund value at time t, where the single premium paid by the policyholder is invested. 
Following the standard assumptions in the literature and considering a static withdrawal strategy,
we model the evolution of the fund as: 
0 0
( )

  

   
W
dWt Wtdt Gdt WtdZt
 (2)
where Zt is a standard Brownian motion, µ is the drift rate, σ is the fund volatility, δ is the insurance 
fee paid ongoing as fraction of assets, Gis the withdrawal from the fund at time t and is equal to 
the guaranteed amount. Equation (2) holds while Wt>0.
This dynamic model for the underlying investment is consistent with the actuarial literature on 
pricing insurance guarantees (Chen and Forsyth (2008), Gerber and Shiu (2003), Milevsky and 
Salisbury (2006), Windcliff et al. (2001)). Following the literature, we assume that exists a risk 
neutral probability space 
 F  Q t t
, , ,   0
, with a filtration 
  Ft t0
and a risk neutral measure, under 
which payment streams can be valued as expected discounted value using the risk-neutral valuation 
formula (c.f. Bingham and Kiesel (2004)); existence of this measure implies the existence of an 
arbitrage free market. If we consider this new space, the evolution of the fund is:
Q
t Wtdt Gdt WtdZt dW r
~
 (  )  
 (3)
where r is the risk free rate and 
t
r
Z Zt
Q
t

 
 
~
is a Brownian motion under Q.
The GLWB offers a lifelong guarantee: the maximum amount to be withdrawn is specified but the 
total amount is not limited and the insured can annually request a portion of the premium paid while
he is still alive, even if the fund value drops to zero. Any remaining account value at the time of 
death is paid to the beneficiary as death benefit.
7
We consider a simple form of product, without a Roll-up option, Step-up or deferred period. Let V0 
be the discounted value at t=0 of the GLWB; it is the sum of the discounted values of the living and 
death benefits:
V0  LB0  DB0
 (4)
LB0 is the well-known discounted value of a life annuity; DB0 can be calculated considering the 
payoff that the beneficiary will receive at the random time of death τ:
 ;0 DB
 Max W
 (5)
Since the time of maturity is stochastic and τ and Wτ are independent, the discounted value at t=0
of the death benefit is given by the following conditional expectation :
  

 DB E E e DB r
0 
 (6)
Conditioning on τ = T, the death benefit can be calculated by Ito’s lemma as in Milevsky and 
Salisbury (2006); the solution to equation 5 is:
















  
      
max ;0
0
)
2
(
0
)
2
(
2 2
DB e G e dt
T
T Z t Z
T
T  t

  

 
 (7)
Using a standard technique in the literature, the no-arbitrage time-zero value of the death benefit
occurring at time T is:
























    
      
( ) ( ) max ;0
0
~
)
2
(
0
~
)
2
(
0 0 0
2 2
DB T E DB E e G e dt
T
r T Z r t Z
Q
T
Q T  t

 


  (8)
where the expectation is taken under the risk neutral measure Q. 
If we consider both the expectations in the equation (6), we obtain:
DB f t E DB dt t
Q
x
x
( ) ( ) 0
0
0 



 (9)
In the discrete case we have:
8
 t
x
t
Q DB  t px qx tE DB





0
0 0
 (10)
for a policyholder aged x at inception of the contract. Thus, the discounted value at t=0 of the death 
benefit is a weighted average of the values of ω-x+1 different death benefits, where the weight for 
year t is the deferred probability of death in year t, i.e. the probability of survival until t and death 
between t and t+1.
The policyholder is also entitled to withdraw the guaranteed amount each year while he is alive; 
therefore, the actual value of the GLWB option if the policyholder assumes a static strategy is:
 



 
x
t
t
Q
t x
rt V t px gW e q E DB

0
0 0 /1 0
( ) (11) 
where 
t /1 qx

t px qxt
is the deferred probability of death.
4. Numerical results and sensitivity analysis
In this section, we carry out a sensitivity analysis, in which we analyze the relationship between the 
GLWB value and- the age of policyholder at the inception of the contract; - the rate g; - the risk free 
rate r; - the fund volatility σ. Finally, we evaluate the impact of the roll-up and step-up options on 
the GLWB.
Initially, we price a simple form of GLWB, without a Roll-up option, Step-up option or deferred 
period. The amount invested in the fund at t=0 is W0=100; the policyholder receives the amount 
guaranteed gW0 while he is alive; moreover, at the date of death the beneficiary will receive any 
remaining account value. We offer an evaluation of GLWB for the Italian market and, for this 
reason, we consider a mortality table based on the experience of the Italian male population: the 
SIM2002. The maximum age considered is 110. Figure 1 shows the deferred probabilities of death 
for policyholders aged 50, 60, 70 and 80, where 
qxt t px
is the probability for a policyholder aged 
x
to survive to time
t and die between t and 
t 1
Figure 1 shows an unusual feature in that each curve has two modes; this bimodal feature can be found 
also in a recent life table for Belgian males (see Pitacco et al. (2009)).
9
Figure 1: the deferred probabilities of death
We calculate the GLWB value for different policyholders with ages from 50 to 80 at inception.
Since this product has not been introduced yet in Italy, we refer to typical parameter values from the 
US market. Thus,we set g=4%, r=5%, σ=20% and δ=0.70 b.p. Currently, the typical GMWB for a 
life rider fee ranges from 0.6%-0.9% (Xiong et al., 2010); the guaranteed rate increases with the age 
of policyholder at the inception of the contract and usually it is equal to 4% for a policyholder aged 
50-59 and 5% for a policyholder aged 60-69. Finally, according to Morningstar Principia Pro, the 
average of the sub-account volatility for the universe of variable annuity products is 18%, the 25th
percentile is 16% and the 90th percentile is 25%.
In order to study the way in which the GLWB value varies when the age of policyholder at the 
inception of the contract increases, we decompose the product into the sum of the living benefit and
the death benefit and observe their relationship with age at inception. In the following, we refer to 
the value of death benefit, living benefit and GLWB value as the discounted value at the inception 
of the contract of death benefit, living benefit and GLWB option. Given the guaranteed rate, as the 
age at inception increases, the value of living benefit decreases while that of the death benefit 
increases, because the number of possible withdrawals decreases and the death benefit is discounted 
for a shorter period. The overall effect is represented in Figure 2: as age increases, the discounted
value of the GLWB decreases, in line with the hypothesis being considered. For this reason, VA 
providers are able to offer higher guaranteed rates to older policyholders. 
10
Figure 2: the discounted values at t=0 of the GLWB and of the death and living benefits.
For younger policyholders, the living benefit is of greater importance; we note that the number of 
withdrawals is high, the account value at the time of death is relatively small because the amount 
withdrawn deducted from the fund value is significant and the death benefit is discounted for a long 
period. Instead, as the age of the policyholder at the inception of the contract increases, the living 
benefit becomes less significant and the death benefit becomes more significant.
Next, we continue the analysis and consider the relation between the GLWB value for policyholders 
with different ages at inception and the parameters g, r and σ.
As the rate of guaranteed withdrawal increases, there are two effects: for each age at inception, on
the one hand, the actual value of the living benefit increases because the amount withdrawn 
increases; on the other hand, the amount of the death benefit decreases because the amount 
deducted from the fund increases (see Figure 3).
.
11
Figure 3: the relation between g and the discounted value of the living benefit (LH) and death benefit (RH) 
Overall, the relation between the GLWB value and the guaranteed rate of withdrawal is shown in 
Figure 4. The relationship between g and the value of the living benefit prevails at each age so that
as g increases the product becomes more attractive. However, the impact is stronger for younger 
policyholders, for whom the living benefit is of greater importance, while for older policyholders 
the influence of g is moderate. Taking into account this consideration, from the point of view of VA
providers, the guaranteed rate offered to older customers should be used as a key feature to make
the product more attractive without having a strong influence on the payoff,
Figure 4: the relation between the GLWB value and g
The third step of our sensitivity analysis is the study of the relation between the GLWB value and 
the risk free rate r. As r increases, the discounted value of each withdrawal decreases; so the value 
of the living benefit decreases at each time point. Instead, the value of the death benefit increases,
(see Figure 5). In fact, the risk free rate influences both the evolution of the fund and the discounted 
value of the death benefit and there is a “balancing out effect” Further, there is a third effect: in eq. 
8 the term in brackets increases as r increases. 
12
Figure 5: the relation between r and the discounted value of the living benefit (LH) and death benefit (RH) 
Overall, the relation between the GLWB value and the risk free rate is shown in Figure 6: as the risk 
free rate increases, the GLWB value decreases and the impact is stronger for younger policyholders, 
who hold the product for longer period. In particular, they gain more advantage from reductions in 
the risk free rate.
Figure 6: the relation between the GLWB value and r
The fourth step of the sensitivity analysis is the study of the relation between the GLWB and σ.
Figures 7 shows the results. 
13
Figure 7: the relation between σ and the discounted value of the death benefit (LH) and the GLWB (RH)
As the fund volatility increases, assuming that there are no step-up options, the value of the living 
benefit does not change because the withdrawals do not depend on the fund value while the value of 
the death benefit increases (see equations 2 and 5). In particular, this effect is stronger for younger 
policyholder because they hold the product for a longer period during which the fund value evolves.
Consequently, as the volatility increases the curve is raised and is raised more for younger 
policyholders, so that if volatility is low, then age has a significant impact on the DB value, while if 
volatility is high, age has much less influence on the DB value. Overall, the GLWB value increases
with age at inception when volatility is low, but decreases with age when it is high. This effect 
occurs because GLWB is the sum of death benefits and living benefits, and the latter are not
influenced by volatility and their value is a decreasing function of age. When volatility is low, the 
death benefit increases consistently with age and so it compensates for the decreasing trend in the 
living benefit; instead, when volatility is high the increase in the death benefit is less marked and it 
is not sufficient to compensate for the decrease in the living benefit.
Until now, we have considered a given charge; however, VA providers price the GLWB option 
requiring different fees. In order to offer a realistic market consistent valuation, we calculate the fair 
insurance fee based on the pricing model developed in the previous section. As in Piscopo (2009),
giving the value of the other parameters, the fair insurance fee can be obtained by equating the 
single premium 
0
to the value at time 0 of the all future cash flows.
14
We consider a policyholder aged 60 at the inception of the contract; we carry out Monte Carlo 
simulations under different scenarios, generating for each of them 10,000 paths of evolution of the 
fund. Once the interest rate, the volatility and the guaranteed rate have been fixed, we search for the 
fair value of the fee using an iterative procedure: if the time-zero cost of the whole product turns out 
to be higher than
0
then we increase the fee in order to decrease the cost in order to get closer to 
the value of
0
; and vice-versa, if the time-zero cost of the whole product turns out to be smaller 
than 
0
. Table 1 displays the fair insurance fee under different guaranteed rate and sub-account
volatility:
g/σ 16% 18% 20%
4% 36,97 48,25 59,99
5% 68,14 85,32 102,77
6% 126,4 151,61 176,76
Table 1: The impact of the guaranteed rate and sub-account volatility on the fair insurance fee for a policyholder aged 60.
As expected, given the guaranteed rate, the fair fee increases with increases in the volatility, 
because guarantees are more expensive when volatility increases, and, given the volatility, the fair 
fee increases with increases in the guaranteed rate, because the product is more valuable to the 
policyholder.
We conclude this section with a consideration of the valuation of roll-up and step-up options. 
In the case of a Roll-up option, the annual guaranteed withdrawal amount is compounded at the 
roll-up rate during a certain time period but only if the policyholder has not started withdrawing 
money. The valuation of this option needs to consider the interaction of different factors. On the one 
hand, a roll-up rate greater than the risk free rate leads to an increase in the discounted value of 
future guaranteed withdrawals if they are postponed. On the other hand, the insurer becomes older 
during the deferment period and the expected number of withdrawals until death decreases with a 
consequential effect on both the living and death benefits. In the light of this consideration, it is not 
possible to provide general statements regarding the profitability of the option, since it is necessary 
to evaluate, on a case by case basis, the product in line with the chosen values of the key 
parameters: the roll-up rate, the deferment period, the expectancy of life of the policyholder and so 
on. By way of an example, we modify the basic contract analyzed above by introducing different 
roll-up options. As in the previous analysis, we set g=4%, r=5%, σ=20% and δ=0.70 b.p. We 
compare DB, LB and GLWB values between contract 1, which guarantees lifelong withdrawals of 
4% of the initial premium without offer a roll-up, and contracts 2 and 3, which provide an annual 
15
increase of the guaranteed withdrawal amount of 7% as long as no withdrawals are made for 5 and 
10 years respectively (the so-called waiting period). Figures 8-9 show the results for different ages 
at inception. If the policyholder decides to delay the withdrawals, the value of the death benefits 
provided by contracts 2 and 3 is greater than that provided by contract 1 during the waiting period 
and is lower afterwards. Further, we need to take into account the interaction of this effect with the 
probability of death: a younger policyholder is less likely to die during the waiting period, when the 
death benefit is higher, than an older policyholder. As regards the living benefits, contracts 2 and 3 
provide greater guaranteed withdrawal after the waiting period, but during the waiting period there 
are no withdrawals. The probability of survival is higher during the waiting period and 
consequently the first set of cash flows has a greater weight in the valuation formula. Overall, in the 
example provided, contracts 2 and 3 are less valuable than contract 1.
 
Figure 8: Living benefit (LH) and death benefit (RH) without and with Roll-up Option
16
Figure 9: GLWB value without and with Roll-up Option
A similar discussion applies to the case of Step-up options. When the contract contains a Step-up
option, at pre-specified points in time (step-up dates), the guaranteed annual withdrawal amount is 
increased if the percentage g of the account value exceeds the contractual guaranteed amount. The 
policyholder can start to withdraw immediately or decide to delay the withdrawals. As previously, 
we consider a specific example and compare DB, LB and GLWB values between contract 1 and 
contract 4, which provides an annual Step-up option, with and without a deferment period. Figures 
10-11 show the results for different ages at inception. If the policyholder does not decide to delay 
the withdrawals, the value of the living benefit increases with respect to the product without a stepup, because the step-up option provides a floor equal to the guaranteed amount and also a 
potentially higher return. The option is more valuable for younger insureds than for older ones, 
because they can profit from it for a longer period. In contrast, the value of the death benefit 
decreases because the amount withdrawn becomes significant. Overall, in this example, the step-up
option makes the GLWB more valuable for younger policyholders. In the case where the insured 
decides to delay the withdrawals by 5 or 10 years, the valuation is similar to the Roll-up, with the 
difference that in the Step-up case the guaranteed amounts after the waiting period are not constant 
but depend on the fund performance. 
Figure 10: Living benefit (LH) and death benefit (RH) without and with Step-up Option
17
Figure 11: GLWB value without and with Step-up Option
As previously, it is not possible to outline general statements on the profitability of the option, since 
it is necessary to evaluate, on a case by case basis, the products according to the values of the 
parameters selected. In particular, in the case of the step-up option, the volatility of the fund account 
influences considerably the profitability of the products, since the cash flows are strongly dependent 
on the fund performance. 
5. The impact of mortality risk on the GLWB value: a stochastic approach
In the previous section, we have considered the price of the GLWB taking into account a fixed prespecified mortality table, viz. SIM2002. Recently, it has become evident that a stochastic mortality 
approach is necessary in order to avoid underestimation or overestimation of the expected present 
value of life insurance contracts with a significant mortality component (see Olivieri (2001), Pitacco 
(2004), Pitacco et al (2009)). In this section, we propose a simplified version of the stochastic 
model suggested by Cox and Lin (2005) and developed by Ballotta et al (2006). 
Our approach starts with the survival table used before and develops an adjusted mortality table, 
which takes into account possible mortality shocks. In this regard, the number of survivors at age 
x+t, l(x+t), is approximately distributed as a normal random variable with mean equal to l(x) tpx and 
variance equal to l(x) tpx(1- tpx). However, the latest actuarial literature highlights the feature that 
the empirical data show perturbations in the survival probabilities due to random shocks. Cox and 
Lin (2005) express the mortality improvement shock 
t

as a percentage of the force of mortality 
 xt
. Without considering shocks in mortality, the survival probability for an age 
x
at year 
t
is 
pxt
with
exp( ) pxt  xt
18
under certain assumptions. Accordingly, we simulate the survival probabilities adjusted for shocks 
as follows:
1 (1 )
' exp( )
t t
x t x t x t
p p
 





  
 (12)
Ballotta et al (2006) assume that εt follows a beta distribution with parameter a and b and the sign of 
the shocks depends on the random number k(t) simulated from the uniform distribution U(0,1). In 
particular, they set:
ε(t) if k(t) < c 
- ε(t) if k(t) ≥ c (13)
where c is a parameter which depends on the user’s expectation of the future mortality trend. 
The importance of assigning a random sign to εt is that, in this way, the model captures not only the 
long period variations in mortality rates, but also the short period fluctuations due to exceptional 
circumstances. 
In our application, by way of an illustration, we consider two contrasting cases for the value of c: c 
= 1 and c = 0. In the first case, there will be improvements in life expectancy at each date; in other 
words, all shocks are expected to be positive. Conversely, in the second case further improvements 
of an already high expectancy of life are impossible and all shocks are expected to be negative. In 
our application, we simulate the value of p’x for a policyholder aged x = 50 at inception of the 
contract under the two different hypotheses and then we calculate the expected number of survivors 
l’(x+t+1) as follows:
l'(x t 1)  l(x t) p'(x t)
 (14)
We are then able to calculate the other mortality functions that we need.
In order to analyze the impact of different variations in mortality probabilities, we carry out the 
following calculation procedures: we fix a = 0.5 and b = 4.5, so that shocks have expected value 
equal to 0.10 and standard deviation equal to 0.12. This hypothesis is consistent with the mean and 
standard deviation of annual percentage mortality improvements experienced by Italian males aged 
from 50 to 75 between the years 1955, 1965, 1975, 1985, 1995 and 2005. We simulate 10.000 paths 
of evolution of mortality using the Monte Carlo method and consider the alternative hypotheses c = 
19
0 and c = 1. Then, we calculate the price of the GLWB option and compare the results under the 
different scenarios. 
At first, we report the results relating to only one path simulated under the hypothesis c=0 and c=1, 
in order to reflect upon the impact of an improvement or a worsening on the deferred probabilities 
of death; afterwards, we show more general results of our simulations.
In figure 12, we compare the unadjusted survival function for a policyholder aged 50 based on 
SIM2002 mortality table with those simulated under the hypothesis c = 1 and c = 0 for a particular 
path. In the first case, we expect that there will be only improvements in life expectancy and, 
consequently, the adjusted function lies above the unadjusted survival function. Instead, in the 
second case we expect there will be only deteriorations and the adjusted function lies below the 
unadjusted survival function.
Figure 12: The simulated effects of improvements and worsening on the survival functions (c=1: mortality 
improving; c=0, mortality deteriorating)
In order to quantify the impact of mortality risk on the GLWB value we have to consider the 
projected deferred probabilities of death
qxt t px
, i.e. the probability for a policyholder aged 
x
to 
survive at year 
t and die between t and 
t 1
. In Figure 13, we compare the unadjusted mortality 
probability 
q50t t p50
for 
t 1,,60
and the adjusted probabilities under the hypotheses c = 1 and c 
= 0 for a particular single simulated path of mortality; polynomial smoothed functions are also 
shown in order to identify the general shape of the curves. We have to keep in mind that the 
probability function changes because of two different effects: if c = 1 the survival probability 
increases and the mortality probability decreases at every time point; in contrast, if c=0, the 
mortality probability increases and the survival probability decreases. The consequences are that, 
under the hypothesis c=0, the adjusted probability function is translated so that the left tail becomes 
fatter and the right tail less fat than for the unadjusted probability function. In contrast, if c=1, the
20
adjusted probability function is translated so that the left tail becomes less fat and the right tail more 
fat than for the unadjusted probability function. 
Figure 13: The simulated effects of improvements and worsening on the deferred mortality probability functions
(c=1: mortality improving; c=0, mortality deteriorating)
We have simulated 10,000 values of εt for each t from a beta distribution, and then we have 
calculated the 50th and the 95th percentiles of the adjusted mortality pdf and have re-priced the 
GLWB, taking into account both the living and death benefits. The results for different ages at 
inception are shown in Figures 14-15. . 
Figure 14: Living benefit (LH) and death benefit (RH) under different mortality hypothesis (c=1: mortality 
improving; c=0, mortality deteriorating)
21
Figure 15: GLWB value under different mortality hypothesis (c=1: mortality improving; c=0, mortality 
deteriorating)
Under the assumption that c=0, the probability of survival at each date is lower than for the 
unadjusted probability function; and so, because the number of withdrawals decreases, the adjusted
curve of the value of the living benefit lies below that of the unadjusted living benefit as shown in 
Figure 14. In contrast, under the assumption c=1, the probability of survival at each date is higher 
than for the unadjusted probability function; and so, the curve for the value of the living benefit lies 
above that for the unadjusted living benefit. The reverse effect influences the death benefit. Under 
the assumption of improvements in life expectancy, the death benefit decreases at each age for two 
reasons: on the one hand, it is received further off in the future and so it has to be discounted for a 
longer period; on the other hand, as the policyholder lives longer, the number of withdrawals 
increases and consequently the amount of fund available at the time of death decreases.Overall, the 
former effect regarding the living benefit prevails over the latter regarding the death benefit and the 
GLWB value increases as the life expectancy increases. The effect of mortality risk on the GLWB 
is described in Figure 15, where the simulated option values at the 50th and 95th percentiles are 
reported under the assumptions c=0 and c=1 . We highlight that, as the age of the policyholder at 
inception of the contract decreases, the impact of mortality risk on GLWB increases.
6. Conclusion
In this paper, we have described the latest financial innovation introduced in the VA market: the
GLWB Option. We have dealt with the problem of valuation of this option and we have developed
a theoretical model for its pricing. We have taken a static approach that assumes individual 
22
investors behave passively in utilizing the embedded guarantee. This hypothesis is plausible 
because the insurer can induce the policyholder to adopt this behavior by introducing a penalty 
charge on the amount of withdrawal that exceeds the guaranteed amount. Moreover, these options 
are being introduced in pension plans, in order to ensure a constant income during the retirement 
and provide protection against market downside risk. In the light of these considerations, our aim 
has not been to offer a policyholder behavioural analysis but rather to provide a conceptual 
valuation scheme of the product and offer some initial estimates for the fair fee. The model has been 
illustrated with numerical results and a sensitivity analysis, which have shown how the value of the 
option varies with the key parameters, including the age of the policyholder at the inception of the 
contract, the guaranteed rate, the risk free rate and the fund volatility. We have considered the basic 
form of the product as well as more sophisticated guarantees, such as the roll-up and step-up option. 
Despite a common belief to the contrary, we have shown that these features do not always make the 
GLWB more valuable; however, we have highlighted the necessity to evaluate, on a case by case 
basis, the products according to the values of the key parameters such as the roll-up rate, the 
deferment period, the frequency of step-up dates, the life expectancy of the policyholder and the 
evolution of the financial market because of the complex interaction of both financial and 
demographic factors. Our results are case sensitive and the choice of parameter assumptions is 
fundamental. Behind a more realistic quantification of impact of different risk sources, our aim has 
been to offer a general framework for valuating GLWB options.
Owing to the long time horizon of their commitment, GLWB providers are exposed to important 
financial and mortality risk. In this paper,we have given special attention to the study of the impact 
of mortality on the value of the GLWB. Useful instruments for controlling mortality risk are the 
projected mortality tables, which can be produced with different stochastic models. In this regard, 
we have chosen the Cox-Lin model (2005) as one which includes a stochastic mortality trend as 
well as shocks. The mortality model that we consider has the potential of both future mortality 
improvement and deterioration and it is useful to offer a complete description of the potential 
impact of mortality risk on the product under consideration. In order to understand in which way the 
GLWB value varies when there is an improvement or a worsening in life expectancy, we have 
decomposed the product into the sum of the living benefit and the death benefit and have observed 
the impact of mortality shocks on them. Our results show that the product is sensitive to mortality 
risk. Since the fluctuation in the GLWB value depends on the interaction of the factors considered 
in the paper, it is necessary to implement a simulation approach to measure and manage mortality 
23
risk. We highlight the importance of the choice of the model and parameter assumptions, while not 
necessarily trying to identify the most correct mortality model and financial assumption.
In the light of the analysis conducted here, we identify areas where there is scope for further work. 
One problem left open is the definition of an efficient risk management strategy for the GLWB 
option. The valuation formula shows that this product is affected by financial risk, due to the 
changes in the fund value and in the level of interest rates over time, and by mortality risk. The 
hedging of financial risk is difficult because of the long maturity of these contracts. Also, our study 
highlights that the mispricing due to neglecting mortality improvements or worsening is noticeable.
An integrated analysis of the interaction of demographic and financial risk would be an important 
step to deliver a more detailed scheme to identify, measure and manage global risks for GLWB 
providers 
References
Advantage Compendium, Ltd, 2008. A Look at Annuity and Securities GLWBs.
Ballotta L., Esposito G., Haberman S. 2006. Modelling the fair value of annuities contracts: the 
impact of interest rate risk and mortality risk. Actuarial Research Paper, No.176, Cass Business 
School.
Ballotta L., Haberman S. 2003. Valuation of guaranteed annuity conversion options, Insurance: 
Mathematics and Economics 33:, 87-108.
Ballotta L., Haberman S. 2006. The fair valuation problem of guaranteed annuity options: The 
stochastic mortality environment case, Insurance: Mathematics and Economics 38: 195-214.
Bauer D., Kling A., Russ J. 2008 A universal pricing framework for guaranteed minimum benefits 
in variable annuities. ASTIN Bulletin 38:621-651.
Bingham N.H., Kiesel R. 2004. Risk-Neutral Valuation. Springer, London 
Boyle P.P, Schwartz E. 1977. Equilibrium prices of guarantees under equity-linked contracts. 
Journal of Risk and Insurance 44(2):639-680
24
Chen Z., Forsyth P.A. 2008. A numerical scheme for the impulse control formulation for pricing 
variable annuities with a Guaranteed Minimum Withdrawal Benefit (GMWB). Numerische 
Mathematik,109(4): 535-569
Chen Z., Vetzal K., Forsyth P.A. 2008. The effect of modelling parameters on the value of GMWB 
guarantees. Insurance: Mathematics and Economics 43:165-173.
Coleman T.F., Li Y., Patron M. 2006. Hedging guarantees in variable annuities under both equity 
and interest rate risks. Insurance: Mathematics and Economics 38:215-228
Cox S.H., Lin Y. 2005. Securitization of mortality risk in life annuities. Journal of Risk and 
Insurance 72:227-252.
Gerber H.U., Shiu E. 2003. Pricing dynamic investment fund protection. North American Actuarial 
Journal 4(2):60-77
Haberman S., Piscopo G. 2008. Mortality risk and the valuation of annuities with guaranteed 
minimum death benefit options: application to the Italian population. Actuarial Research Paper No. 
187, Cass Business School.
Hanif F., Finkelstein G., Corrigan J., Hocking J. 2007. Life Insurance, global variable annuities. 
Published by Morgan Stanley Research in co-operation with Milliman.
Holz D., Kling A., Rub J. GMWB for life. 2006. An analysis of lifelong withdrawal guarantees. 
Working Paper ULM University.
Ledlie M.C., Corry D.P., Finkelstein G.S., Ritchie A.J., Su K., Wilson D.C.E. 2007. Variable 
annuities. British Actuarial Journal 14 (2): 327-389
Leheman Brothers. Variable Annuity Living Benefit Guarantees: Over Complex, Over Popular and 
Over Here? 2005. European Insurance 22 
Liu Y. 2010. Pricing and Hedging the Guaranteed Minimum Withdrawal Benefits in Variable 
Annuities. Electronic Theses and Dissertation, University of Waterloo,
http://uwspace.uwaterloo.ca/handle/10012/4990
Milevsky M., Posner S.E. 2001 The Titanic option: valuation of the guaranteed minimum death 
benefit in variable annuities and mutual funds. Journal of Risk and Insurance 68: 91-126.
25
Milevsky M., Salisbury T. 2006. Financial valuation of guaranteed minimum withdrawal benefits. 
Insurance: Mathematics and Economics 38: 21-38.
Milevsky M., Salisbury T.S. 2002. The real option to lapse and the valuation of death-protected 
investments. Working Paper York University and the Fields Institute, Toronto.
Milevsky M.A., Promislow S.D. 2001. Mortality derivatives and the option to annuities. Insurance: 
Mathematics and Economics 29:299-318.
Morningstar 2001. Morningstar Principia Pro Plus Variable Annuities
Olivieri A. 2001. Uncertainty in mortality projections: an actuarial perspective. Insurance: 
Mathematics and Economics 29: 231-245.
Piscopo G. 2009. The fair price of Guaranteed Lifelong Withdrawal Benefit Option in Variable 
Annuity. Problems & Perspectives in Management 7(4): 79-83.
Pitacco E. 2004. Survival models in a dynamic context: a survey. Insurance: Mathematics and 
Economics 35:279-298.
Pitacco E., Denuit M., Haberman S., Olivieri A. 2009. Modelling Longevity Dynamics for Pensions 
and Annuity Business. Oxford University Press, Oxford, 
Windcliff H., Forsyth P.A., Vetzal K.R. 2001. Valuation of segregated funds: shout options with 
maturity extensions. Insurance: Mathematics and Economics 29(2): 1-21
Xiong J.X., Idzorek T., Peng C., 2010. Allocation to Deferred Variable Annuities with GMWB for 
Life. Journal of Financial Planning, 2:42-50