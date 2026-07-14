https://cirano.qc.ca/files/publications/2012s-08.pdf
→ https://cirano.qc.ca/files/publications/2012s-08.pdf


 

 

 

 

 

 

 

 

 

 

 

 

 

 

 

 

 

 

 

 

 

 

 

 

 

 

 

 

 

 

Montréal 

Avril 2012 
 

 

 

 
© 2012 M. Martin Boyer, Lars Stentoft. Tous droits réservés. All rights reserved. Reproduction partielle permise 

avec citation du document source, incluant la notice ©. 

Short sections may be quoted without explicit permission, if full credit, including © notice, is given to the source. 

 

 

 

Série Scientifique 

Scientific Series 

 

  2012s-08 
 

If we can simulate it, we can insure it:  

An application to longevity risk management 
 

M. Martin Boyer, Lars Stentoft 



CIRANO 

Le CIRANO est un organisme sans but lucratif constitué en vertu de la Loi des compagnies du Québec. Le financement de 

son infrastructure et de ses activités de recherche provient des cotisations de ses organisations-membres, d’une subvention 

d’infrastructure du Ministère du Développement économique et régional et de la Recherche, de même que des subventions et 

mandats obtenus par ses équipes de recherche. 

CIRANO is a private non-profit organization incorporated under the Québec Companies Act. Its infrastructure and research 

activities are funded through fees paid by member organizations, an infrastructure grant from the Ministère du 

Développement économique et régional et de la Recherche, and grants and research mandates obtained by its research 

teams. 

 

Les partenaires du CIRANO 

Partenaire majeur 

Ministère du Développement économique, 

de l’Innovation et de l’Exportation 

Partenaires corporatifs 

Autorité des marchés financiers 

Banque de développement du Canada 

Banque du Canada 

Banque Laurentienne du Canada 

Banque Nationale du Canada 

Banque Royale du Canada 

Banque Scotia 

Bell Canada 

BMO Groupe financier 

Caisse de dépôt et placement du Québec 

CSST 

Fédération des caisses Desjardins du Québec 

Financière Sun Life, Québec 

Gaz Métro 

Hydro-Québec 

Industrie Canada 

Investissements PSP 

Ministère des Finances du Québec 

Power Corporation du Canada 

Rio Tinto Alcan 

State Street Global Advisors 

Transat A.T. 

Ville de Montréal 

Partenaires universitaires 

École Polytechnique de Montréal 

HEC Montréal 

McGill University 

Université Concordia 

Université de Montréal 

Université de Sherbrooke 

Université du Québec 

Université du Québec à Montréal 

Université Laval 

 

Le CIRANO collabore avec de nombreux centres et chaires de recherche universitaires dont on peut consulter la liste sur son 

site web. 

ISSN 1198-8177 

 

Les cahiers de la série scientifique (CS) visent à rendre accessibles des résultats de recherche effectuée au CIRANO afin 

de susciter échanges et commentaires. Ces cahiers sont écrits dans le style des publications scientifiques. Les idées et les 

opinions émises sont sous l’unique responsabilité des auteurs et ne représentent pas nécessairement les positions du 

CIRANO ou de ses partenaires. 

This paper presents research carried out at CIRANO and aims at encouraging discussion and comment. The observations 

and viewpoints expressed are the sole responsibility of the authors. They do not necessarily represent positions of 

CIRANO or its partners. 

Partenaire financier 



If we can simulate it, we can insure it:  

An application to longevity risk management
*
 

 

 

M. Martin Boyer
†
, Lars Stentoft

 ‡
 

 

 
 

 

 

Résumé / Abstract 
 

This paper proposes a unified framework for measuring and managing longevity risk. 

Specifically, we develop a flexible framework for valuing survivor derivatives like forwards, 

swaps, as well as options both of European and American style. Our framework is essentially 

independent of the assumed underlying dynamics and the choice of method for risk 

neutralization and relies only on the ability to simulate from the risk neutral process. We provide 

an application to derivatives on the survivor index when the underlying dynamics are from a 

Lee-Carter model. Our results show that taking the optionality into consideration is important 

from a pricing perspective. 

 

Mots clés/Keywords: Least squares Monte Carlo, Longevity risk, 

Reinsurance, Simulation. 

 

Codes JEL: G22, G23 

                                                 
*
 The authors thank Joanna Mejza for fascinating discussions and Amélie Favaro for excellent research 

assistance. This research is financially supported by the Social Science and Humanities Research Council of 

Canada as well as by CIRANO. 
†
 HEC Montréal and CIRANO. 3000, Côte-Sainte-Catherine, Montréal, Québec, H3T 2A7 Canada. 

‡
 HEC Montréal, CIRANO, CIRPEE and CREATES. 3000, Côte-Sainte-Catherine, Montréal, Québec, H3T 2A7 

Canada. 



1 Introduction

In 1986 the rock band Queen sang “Who wants to live forever?” in which they conclude

“Who waits forever anyway?” They could have easily put in song “Who wants to live old

an poor forever?” for that is the risk of outliving our assets. Indeed, outliving our assets is

not an enviable outcome of increased longevity at older ages, and anyone would probably

try to avoid running out of funds when they are old and grey. Sadly, however, lacking

financial resources is one of the pernicious effects stemming from the risk of a population

living longer than planned, so that not enough money has been saved to fulfill its financial

needs. We refer to this risk as longevity risk. Put differently, longevity risk arises when the

annuitants’ actual life expectancy is greater than their expected life expectancy. Unknown

longevity affects the overall profitability of institutions that offer lifetime pensions, such as

large corporations and governments, as well as the total savings of individuals.

Financially, aggregate longevity risk is mostly negative since retirement systems in devel-

oped countries rely on aggregate mortality rate forecasts to calculate an individual’s pension

benefits until his death (not to mention all other costs associated with old-age, such as medi-

care and disability benefits). When the life expectancy of a cohort of pensioners exceeds

forecasts, the retirement system must pay this cohort income that exceeds the level initially

projected and accumulated. It is then exposed to the risk of lacking the capital needed to

meet its financial commitments. The problem is similar for individuals who are accumulat-

ing wealth in expectation of converting all that wealth into annuities upon retirement (see

Levhari and Mirman, 1977, and Davies, 1981); an unanticipated increase in longevity will

lead to insufficient wealth accumulation on the part of an individual who will then need to

either reduce consumption more than anticipated or delay retirement altogether (see Cocco

and Gomes, 2009).1

1For a detailed discussion of this annuity puzzle, see Brown (2004). The puzzle is derived from the
mismatch between annuity purchases and what would have been optimal under lifetime consumption model

2



Considering the size of the risk exposure, the only way to potentially manage longevity

risk is, arguably, by drawing upon the wealth of the entire capital market. The argument

is essentially that even though potential losses due to longevity risk are larger than what

any one insurer or group of insurers can assume, such a loss exposure is not uncommon for

the capital markets. Put differently, what is a systemic risk for the life insurance market is

an idiosyncratic risk for the entire capital market. The ability of capital markets to absorb

larger amounts of risk than the market for life reinsurance stems from two factors: First,

capital markets are very large and much larger than the market capitalization and surplus

of the insurance industry, and second, there is virtually no correlation between longevity

risk and market risk so that exposure to longevity risk shifts the portfolio frontier up and to

the left. The benefit to capital market participants of assuming this type of risk is that it

gives money managers access to a new class of assets. Because of the negligible correlation

between longevity risk assets and the money managers’ portfolio of financial assets, having

exposure to longevity risk can decrease the volatility of their entire book of business.

Capital markets have started to develop products that allow financial institutions to in-

vest in mortality and longevity. The primary example of such a product is the mortality

swap whereby one party will pay a measure of expected mortality and in return will receive

a measure of actual mortality experience (for a discussion of other types of longevity deriva-

tives see Blake et al., 2006, inter alia). On of the reasons why capital markets have been

relatively slow in developing longevity products is that calculating their fair value raises

many challenges. First of all, mortality, unlike financial assets, is not a traded asset and

therefore longevity products cannot be valued simply by the absence of arbitrage (under the

risk-neutral measure) since no replication portfolio can be built. It is therefore necessary

to use incomplete market valuation methods that imply the existence of a market risk pre-

mium, which can only be appraised using market data. Secondly, given that the cash flows

à la Yaari (1964). For more on this topic, see the recent Huang et al. (2012) paper.

3



of these products are directly linked to mortality or survival rates their valuation requires

the ability to forecast these rates accurately. While this could be achieved using mortality

projections models, these are oftentimes somewhat non-standard, at least from a derivatives

pricing perspective.

The goal of this paper is to develop a flexible framework for pricing essentially all types

of longevity derivatives which is independent of the assumed dynamics. For this reason we

choose to use simulation techniques. Simulation techniques are widely used in the finance

literature to price derivatives. We show how this framework can be used to price survivor

forwards, swaps, and both European and American style options. Though it is possible to

obtain closed-form, and hence simpler, formulas for some longevity forwards and swaps, and

for some European options, such closed-form solutions generally require restrictive assump-

tions about the dynamics of the underlying risk factors. For example, Dawson et alii (2010)

rely on a tightly parameterized beta distribution to derive their closed-form Black-Scholes-

Merton-type prices for the European swaption. Compared to this our framework is much

more flexible and all that is needed is the ability to simulate from the risk neutral distribu-

tion, something that is often the case after an appropriate distortion or transformation.

Moreover, even if the choice of model allows for closed-form solutions for some types of

derivative contracts, this will not be the case for derivatives that allow e.g. early exercise (such

as the American option) or whose value is path dependent (such as up-and-in and down-

and-out options, or Asian options). Thus, in order to price these instruments numerical

methods have to be used. One important advantage of the simulation method is that it can

easily be augmented to take path dependence into consideration. It can also be extended

to incorporate possible early exercise. Finally, it should be noted that simulation methods

are particularly well suited to price derivatives on multiple underlying risks. In particular,

the computational complexity of the simulation technique grows linearly in the number of

risks, whereas most other numerical methods that exist for option pricing are plagued with

4



a computational complexity that grows exponentially in the number of risks − and hence

are said to suffer from the “curse of dimensionality”.

The simulation framework we propose in the current paper is flexible enough to accom-

modate the particular features of the insurance mortality data. As an application, we show

how it can be applied to manage longevity risk where the mortality distribution follows a

Lee-Carter model, though any other model could be used (see Robine, 2011, and Gaille,

2010, for surveys of mortality models used in the current context).2 To be specific, we

price survivor forwards, swaps, and options in this unified framework. Our results show

that taking the optionality into consideration is important from a pricing perspective and if

this is if neglected the value of these products is severely underestimated. Since insurance

and reinsurance contracts can be seen as put options, this finding has non-trivial implica-

tions for the valuation of such contracts. In fact, the inherent flexibility of the simulation

method we propose allows one to price efficiently various types of derivatives (such as bull

and bear spreads, knock-in and lookback options, etc.) which, in turn, allows one to design

and price products that enable insurers and reinsurers to manage risk exposure efficiently.

Thus, a framework as flexible as the one we propose has extraordinary applications for the

management of risk in the context of longevity risk.

The rest of this paper proceeds as follows: In Section 2 we provide a review of some of

the products that have been proposed in the market for longevity risk. We also suggest a

new product: A survivor option with time varying strike prices. In Section 3 we explain

how these products can be priced using simulation techniques. In Section 4 we provide an

application of our framework to a simple model and provide prices for the various products.

Finally, Section 5 concludes.

2Commonly used by insurance companies, the Lee-Carter model (see Lee and Carter, 1992) is a simple one-
factor model that offers a relatively good fit over a full range of ages (see Gaille, 2010, for more details). Li and
Chan (2007) even call the Lee-Carter model the “gold standard of mortality trend fitting and forecasting”.
This one-factor model estimates and forecasts mortality rates on the assumption that mortality is perfectly
correlated at all ages and prevents any cohort-effect, an effect that is specific to a particular year of birth.

5



2 Examples of longevity derivative products

In the financial markets several products exist that allow investors to transfer risk. A classic

example is the use of forwards or futures contracts on stock indices to hedge exposure to

the equity markets or to speculate in the future direction of the market. Futures contracts

also exist on bonds and other interest rate products. Swap contracts are also extremely

important in the interest rate and foreign currency markets. A simple fixed for floating

interest rate swap, for example, is a contract in which one counterparty makes fixed interest

rate payments and in return receives floating rate payments on a given notional amount.

Contrary to the aforementioned products that not only exist but are also liquidly traded

in many markets, derivative products that allow to hedge or transfer longevity risk virtually

do not exist or, if they do exist conceptually, they do not trade actively. In this section we

review some financial products that could be introduced in the market for longevity risk.

The first of these is the survivor forward, which is arguably the simplest possible type of

financial derivative product. It can be used to form the basic building blocks upon which

many more complex derivatives can be constructed. One example is the survivor swaps

which we detail next. Finally, we discuss how option contracts can be constructed where the

underlying asset is longevity risk.

2.1 Survivor forwards

One of the first standardized products on longevity and mortality risk, the q-Forward, was

proposed by the JPMorgan Pension Advisory Group (see Coughlan et al., 2007) as the sim-

plest capital markets instruments that can be used for transferring longevity and mortality

risk.3 The structure of the product involves the exchange of the realized mortality rate of

3In fact, one of the first types of longevity products was longevity bonds where the proposed coupon rate
is a function of the survival rate of a population. Though this product allows trading longevity exposure it
has historically been quite unsuccessful.

6



a population at some future date in return for a fixed mortality rate agreed upon at the

time the contract is signed. Although Coughlan et al. (2007) propose that the forwards be

settled against the LifeMetrics index − incidently also developed by JPMorgan − any type

of survivor index could be used, on any population, sub-type of population or a population

that shares similar characteristics.

To illustrate how a survivor forward works let sex,t be the expected probability that an

individual aged x survives from time t−1 to time t given the information currently available.

Similarly, let srx,t be the realized percentage of individuals aged x that survive from time t−1

to time t. Today’s forward premium is then fixed such that

NPV (adjusted fixed leg) = NPV (floating leg) . (1)

To achieve this we define the adjustment factor πf
t as the solution to

(
1 + π

f
t

)
NPV

(
sex,t

)
= NPV

(
srx,t

)
. (2)

Though the fixed leg depends on the expected survival rates these are conditional on the

information at the time of pricing and hence known and fixed. Thus, we may calculate π
f
t

as follows

π
f
t =

NPV
(
srx,t

)

NPV
(
sex,t

) − 1. (3)

The resulting π
f
t is called the price of the survivor forward. Note that at any time several

forward prices exist for contracts with different maturity. For example, the premium for a

forward contract on the survivor rates from time t to t+ 1 is

π
f
t+1 =

NPV
(
srx,t+1

)

NPV
(
sex,t+1

) − 1. (4)

7



The net payment to a long position in a survivor forward at maturity t is given by

srx,t −
(
1 + π

f
t

)
sex,t. (5)

That is, if the realized survivor rate, srx,t, turns out to be higher than the expected rate, sex,t

multiplied by
(
1 + π

f
t

)
, the long position receives money. For a pension plan it is obvious

that this type of product can be used to hedge the risk associated with increasing longevity.

In particular, if the future payment on the liabilities of the plan corresponds to srx,t by

entering into a long position in a survivor forward the plan’s combined payments correspond

to
(
1 + π

f
t

)
sex,t, i.e. a fixed payment known at time t. Hence there is no longer any exposure

to longevity risk.

2.2 Survivor swaps

The survivor forward is likely the simplest possible instrument which can be used to hedge

exposure to longevity risk at a given time, and by extension a portfolio of such forwards can

be used to hedge this risk over a period of time. This type of arrangement is well known

in the market for interest rate risk where the combined portfolio is traded together as an

interest rate swap. In a similar way a survivor swap is a portfolio of survivor forwards. For

example, one could consider a swap on the survival rates from t− 1 to t, from t to t+1, and

from t + 1 to t + 2. The straightforward generalization of the formula for the forward price

in (3) yields the following solution for the survivor swap price

πs
t,t+2 =

NPV
(
srx,t

)
+NPV

(
srx,t+1

)
+NPV

(
srx,t+2

)

NPV
(
sex,t

)
+NPV

(
sex,t+1

)
+NPV

(
sex,t+2

) − 1, (6)

where we use the same notation as in the section above. Note that by definition it follows

that πs
t,t = π

f
t .

8



Unlike some of the previous literature on longevity risk, where derivatives are written

on the mortality of a benchmark cohort of a given age at a given time (see e.g. Dowd et

al., 2006), we consider here contracts on the mortality of a given benchmark cohort through

time. Thus, we essentially suggest to structure longevity derivatives directly on a given

survivor “index”. However, the methodology we derive does not depend at all on the way

the index is constructed, as we mentioned earlier, and it could equally well be used to price

swap contracts on the cumulative mortality of a benchmark cohort for which (6) would be

π
s,cumm
t,t+2 =

NPV
(
srx,t

)
+NPV

(
srx−1,t+1

)
+NPV

(
srx−2,t+2

)

NPV
(
sex,t

)
+NPV

(
sex−1,t+1

)
+NPV

(
sex−2,t+2

) − 1. (7)

There are at least two reasons to prefer the swap contract in (6) over the one in (7).

• Firstly, the contract specification in (6) is closest in spirit to the existing financial

derivatives and this will likely be conducive to the development of this market.

• Secondly, the price in (7) depends on several different survivor rates, or the term

structure of rates. In general these rates are related and when valuing such instruments

the correlation between them has to be considered. This potentially complicates the

pricing as a multivariate model may be needed.

The net payment to a long position in a swap at time t is given by

srx,t −
(
1 + π

f
t

)
sex,t, (8)

and these payments are realized until the maturity of the contract. Hence, a pension plan

that pays srx,t on its liabilities can hedge its longevity risk exposure over time by entering

into a swap contract. Likewise, the swap in (7) can be used to hedge the cumulative risk

associated with the longevity risk of a given cohort aged x at time t over time. More

generally, an investor can obtain exposure to longevity risk by entering into a survivor swap.

9



For example, an investor who expects survivor rates to increase more than what is currently

expected should enter into a long swap position which will lead to positive cash flows over

time if realized rates turn out to be higher than the expected rates. Investors in longevity

risk need not wait until the maturity of the swap, which could be many years into the

future, to profit. In particular, though the swap has an initial value of zero, this value will

subsequently change and if survivor rates increase the swap will have a positive value. Hence,

as an alternative to holding on to the swap the long investor can sell the swap and collect a

positive return.

2.3 Survivor options

Whereas survivor forwards and swaps have been suggested previously as possible tools to

hedge longevity risk, very little has been proposed in terms of using option type contracts.

This is paradoxical given that option contracts offer interesting alternatives for hedging and

speculative purposes. For example, very liquid markets for options on stock indices exist

alongside the market for futures contracts. In some cases (that is, in the case of individual

stocks) it is even only possible to trade options on the stock since no futures market exist.

The simplest possible example of these instruments (a plain vanilla European option) would

simply be the right to buy (a call option) or sell (a put option) longevity risk exposure at a

given price (the strike price) at a given point in time (the maturity). Since this is a right,

and not an obligation as it is the case with the forward contract with similar maturity, the

option will have a strictly positive price. This price should equal the present value of the

expected future cash flow, which is bounded below at zero.

In order to maintain a close link to the contract and notation we used earlier for forwards

and swaps, we propose to consider options with a particular strike price. To be specific, we

suggest that one should use the expected survivor rate as the strike price. Thus, for a call

10



option the price will be given by

c = E
[
e−τT max

(
srx,T − sex,T , 0

)]
, (9)

where r is the risk free interest rate, T the maturity of the contract, and E [·] denotes the

expected value operator. Likewise, the price of a put option is given by

p = E
[
e−τT max

(
sex,T − srx,T , 0

)]
. (10)

By construction there is a close relationship between the option prices and the forward

premium akin to the put-call parity. In particular, a portfolio that is long a call option and

short a put option with same maturity has a value equal to the present value of the fixed leg

payments of the forward contract maturing at the same time as the options.

We consider a similar construct for the American style option which, unlike the European

options, can be exercised at any time up to and including the contract’s maturity date.

Denoting the stopping time by τ the price of the call option is given by

C = sup
τ∈T

E
[
e−τr max

(
srx,τ − sex,τ , 0

)]
, (11)

where T denotes the set of all stopping times. Likewise, the price of the put option is given

by

P = sup
τ∈T

E
[
e−τr max

(
sex,τ − srx,τ , 0

)]
. (12)

Note that in the two American option formulas the strike price is time varying and set equal

to the expected survivor rate at any given time. Thus, this product is somewhat different

from options traded on the stock market. However, letting strike prices vary in time allows

for straightforward comparison with survivor forwards and swaps.

11



3 Pricing longevity derivatives using simulation

Section 2 shows that the valuation of longevity instruments requires the ability to forecast

future mortality rates. While this could be achieved using mortality projections models,

such as extrapolation models that are commonly used, these are oftentimes somewhat non-

standard at least from a derivatives pricing perspective. Hence, to obtain reasonable price

estimates, one needs to develop a framework flexible enough to accommodate the particular

features of the underlying data.

In this section we show how simulation methods can be used to price longevity derivatives.

We first discuss briefly how one can go about obtaining the risk neutral distribution to be

simulated from. Next we describe how European-style derivative instruments can be priced

based on the simulated distribution. Finally, we detail how one can take early exercise into

consideration in simulations using the least squares Monte Carlo, or LSM, method originally

proposed by Longstaff and Schwartz (2001).

3.1 Risk neutral distributions

Unlike financial assets, mortality is not a continuously traded asset; hence the market is

said to be incomplete and a risk premium exists for exposure to this type of risky asset.

Wang (2000) proposes a financial asset valuation method based on distorting the cumulative

distribution of a variable X . This yields a new risk-adjusted cumulative distribution of cash

flows that can then be discounted at the risk-free rate. Wang (2000) defines the following

risk adjusted distribution

F̃ (x) = Φ
[
Φ−1 (F (x))− λ

]
, (13)

where F (x) is the cumulative distribution function, or CDF, of the variable X , Φ is the

normal CDF, and λ is a risk premium.

The Wang-transform methodology has several advantages. First of all, it is a universal

12



valuation method that can be applied to any type of distribution function F (x). Secondly,

the transformation can easily be adjusted to account for the uncertainty that surrounds the

distribution parameters. Finally, the distortion retains the Normal and Log-Normal distri-

butions: If X follows a Normal distribution with N (µ, σ2), then the transformed variable

X̃ also follows a Normal distribution with N (µ− λσ, σ2); if X follows a Log-Normal distri-

bution with ln (X) ∼ N (µ, σ2), then the transformed variable X̃ also follows a Log-Normal

distribution with ln
(
X̃
)
∼ N (µ− λσ, σ2).

3.1.1 Risk neutral simulation

Since the method proposed by Wang (2000) distorts the final distribution using the risk

premium λ we refer to it as a risk adjusted distribution. This allows for straightforward

pricing of the forward and swap contracts, for instance. However, to be able to develop a

fully flexible pricing method, which can be used to price more sophisticated products such as

the American style option, one needs not only the final distribution but also the distribution

at intermediate steps. To achieve this, one must instead adjust directly the simulation, a

method we shall refer to as a “risk neutral simulation”. The immediate benefit of the risk

neutral simulation approach is that all paths have equal probability which is convenient for

pricing derivatives such as options.4

To implement the risk neutral simulation approach we use the convenient property of the

Normal and Log-Normal models mentioned previously. In particular, because the distortion

retains the Normal and Log-Normal distributions, an obvious alternative to the method

of risk adjusting the distribution is to simulate directly the risk adjusted innovations. In a

Normal model for example, we simulate directly with innovations that are ε ∼ N (µ− λσ, σ2)

instead of innovations that are ε ∼ N (µ, σ2) and then distorting the distribution. Moreover,

instead of simulating only the distribution at maturity, we may use the property that the

4The only potential drawback is that one may need to re-simulate if the risk parameter changes.

13



family of normal distributions is infinitely divisible to obtain the risk neutral distribution

at any intermediate time. This is very useful when pricing American options that have an

early exercise date.

3.1.2 Relation to other risk neutralization methods

The distortion operator defined above and given in its general form as

gλ (u) = Φ
[
Φ−1 (u)− λ

]
, (14)

is a special case of a more general class of distribution distortions (see for instance Wang,

2007). In particular, let g : [0, 1] → [0, 1] be a differentiable function with g (0) = 0 and

g (1) = 1, and let F (x) denote the CDF of the random variable X . Then F̃ (x) = g (F (x))

yields a transformed CDF defined as a probability distortion and representing a change of

probability measure. In the continuous case the probability distortion yields the following

Radon-Nikodym derivative:

RNλ (x) =
f̃ (x)

f (x)
= g′ (F (x)) . (15)

In particular, for the transform in (13) the Radon-Nikodym is given by

RNλ (x) = exp
(
λΦ−1 (F (x))

)
exp

(
−
λ2

2

)
. (16)

The correspondence of a particular transform to a given Radon-Nikodym derivative allows

comparison to several other well known methods of risk neutralization. For example, another

transform often used in actuarial science is the Esscher transform (for more on the Esscher

transform, see among others Gerber and Shiu, 1994, and Buhlmann et al., 1996). The

14



Esscher transform is given by

RNh (x) =
f̃ (x)

f (x)
=

ehx

E [ehx]
, (17)

and thus essentially corresponds to a particular exponential specification of the Radon-

Nikodym derivative. Finally, this type of specification is closely connected to the approach

used for risk neutralization in Christoffersen et al. (2010) in which the Radon-Nikodym

derivative is specified directly as an exponential affine form that essentially writes as

RNν (x) = exp (−νx−Ψ (ν)) , (18)

where Ψ (u) is the conditional cumulative generating function given by

E [exp (−uε)] = exp (Ψ (u)) . (19)

Note that by construction this is the same as the Esscher transform above. Also note that

in the case of Normal distributed risk all these methods coincide. The use of exponential

affine forms has become standard in the finance literature (see also Gourieroux and Monfort,

2007, for a similar setup using an exponential affine stochastic discount factor).

In reality, when pricing longevity products one is often faced with situations where payoffs

depend on the distribution of several risks. In such a situation a multivariate generalization of

the Wang transform or the Radon-Nikodym is needed and luckily such generalizations exist.

For example, Wang (2003) proposes a generalization of Wang (2000), whereas Wang (2007)

establishes a relation between multivariate exponential tilting and multivariate distortion

and Kijima (2006) establishes a relationship between the multivariate Esscher and Wang

transforms. Finally, Rombouts and Stentoft (2011) extend the exponential affine Radon-

Nikodym approach of Christoffersen et al. (2010) to the multivariate framework.

15



3.2 European style instruments

Once the risk neutral distribution has been obtained, it is straightforward to price derivatives.

In fact, this is particularly easy in the case of forward and swap contracts as their value only

depends on the mean of this distribution. Moreover, analytical formulas can be derived

for these products in some cases. For example, this is the case if the risks are Normal or

Log-Normal distributed. It is also possible to obtain closed form solutions in some cases for

the European option. For example, in a constant volatility Log-Normal model a closed form

Black-Scholes-Merton type price is obtained.

More generally however, it is not possible to obtain closed form solutions and hence

numerical methods are required. For example, this is the case when considering options

with path dependent payoffs. Though several methods exist, simulation techniques are one

of the most flexible methods. The use of simulations is well known in finance and dates back

to at least Boyle (1977). The technique is based on the intuition that expected values can

be estimated by sample means and this makes the method immediately applicable when the

goal is to price forwards, swaps, or even European options. After all, the price of the forward

or swap is closely related to the expected value of the underlying asset (the survivor rate

in our case), and the price of a European option depends only on the expected value of a

transformation of this rate according to the payoff function.

As an illustration, consider the case of a European put option on a given survivor index,

srx,t, maturing at time T . Based on a sample of N simulated future paths of the survivor

index appropriately risk neutralized, the price can be approximated by

pN =
1

N

N∑

n=1

e−rT max
(
sex,T − srx,T (n) , 0

)
, (20)

where srx,T (n) is the value of the index along path number n. This estimate converges to

the true price, p, in (10) under very mild assumptions; the only restriction being that the

16



payoff function is square integrable. Moreover, the approach can be easily generalized to

accommodate options on multiple indices and options with path dependent exercise prices.

3.3 Derivatives with early exercise features

For the American option things are not as simple, however. In particular one cannot simply

approximate the true price, P , in (12) by

PN =
1

N

N∑

n=1

max
τ∈1,..,T

[
e−τT max

(
sex,τ − srx,τ (n) , 0

)]
. (21)

The reason this won’t work is that it implies that the option holder has perfect foresight. As a

consequence the result will be biased upward and the price estimate will be too high. Instead,

the preferred way to solve such problems is to use the dynamic programming principle

whereby the price of the American option is determined through the calculation of a number

of conditional expectations that can be used to estimate the optimal stoping time (that is,

the optimal time to exercise the option prior to the maturity date).

Although for a long time it was believed that pricing American options was impossible

using simulations, there exist today several methods that can be used. Among these, the

least squares Monte Carlo, or LSM, method of Longstaff and Schwartz (2001) is one of the

most popular.5 The underlying idea is to approximate the conditional expectations using

cross sectional regressions, an idea that was also suggested in Carriere (1996). For example,

to price the American put option the LSM method proceeds as follows:

Step 1 (Initialization): Initialize the stopping time along each path at maturity by setting

τn = T .

5Bacinello, Biffis & Millossovich (2010) use the LSM method to value life insurance contracts with early
exercise features in general and Bacinello, Biffis & Millossovich (2009) and Nordahl (2008) apply the technique
to value life insurance with surrender options and exchange options.

17



Step 2 (Backward induction): For t = T −1, .., 1 calculate the pathwise discounted pay-

off from following the optimal stopping time τn. Denoted this CF (τn) and regress it

on the current state variables, here the simulated values of srx,t (n) along path n, and

functions thereof. Denote the pathwise predicted cash flows from this regression by

ĈF (τn) and update the stopping time as follows:

τn = t1{max(sex,t−srx,t(n),0)≥ĈF (τn)} + τn1{max(sex,t−srx,t(n),0)<ĈF (τn)}. (22)

Step 3 (Pricing): Given the pathwise stopping times the price of the American option is

estimated by the mean of the pathwise payoffs:

PN =
1

N

N∑

n=1

CF (τn) . (23)

Thus, we immediately realized that “if we can simulate it, we can price it”.6 Similar formulas

can be used to price the call option.

Not only is the LSM method simple, it also has nice asymptotic properties. In particu-

lar, Stentoft (2004) shows that as the number of paths and the number of regressors tend to

infinity, the estimate in (23) converges to the true price in (12) under some relatively mild

regularity conditions. Moreover, compared to other simulation methods that use regressions

the method we propose can be shown to be optimal, in the sense of producing less biased es-

timates, for a finite number of paths and regressors (see Stentoft, 2008). Finally, as discussed

by Stentoft (2012) compared to other simulation approaches the regression based methods

have clear advantages in terms of their computational efficiency and asymptotic properties.

6In the movie “The Cowboy Way” Woody Harrelson’s character Pepper says: “If it’s got hair, I can ride
it. If it’s got a beat, I can dance to it”. It’s a bit the same thing here!

18



4 Application to pricing survivor derivatives

In this section we show how the various longevity risk derivatives discussed in Section 2

(i.e., the survivor forward, swap, and options) can be valued using the simulation approach

discussed in Section 3. As an illustration we report results for the case when mortality is

modeled using the Lee-Carter model. Our methodology could equally well be used with any

other longevity modeling approach, such as the extended Lee-Carter model of Renshaw and

Haberman (2006) or the two factor model of Cairns, Blake and Dowd (2006).7 In fact, the

framework can also be used with models that use standardized longevity indices directly.8

We first review the Lee-Carter model with a special focus on how it allows one to forecast

survival rate using simulations under the risk neutral measure. We then provide pricing

results for the three types of longevity risk derivatives: The survivor forward, the survivor

swap, and the survivor options.

4.1 The Lee-Carter model

The model proposed by Lee and Carter (1992) is given by

ln (mx,t) = ax + bxkt + εx,t, (24)

wheremx,t is the mortality rate andmx,t = 1−sx,t. Thus, in this model the natural logarithm

of the mortality rate for the year t of a person of age x can be expressed using three terms:

two terms dependant on age and one term which depends on the year t. In particular, there

is a constant a and a constant b for each age x. We will use the term “constants” herein as

the ax values and the bx values are presumed fixed over time. The kt values, however, vary

according to the year t, but are identical for any age x.

7See Robine (2011) and Gaille (2010) for surveys of mortality models that could be used.
8In a companion paper we use this approach. Preliminary results were presented at the Seventh Interna-

tional Longevity Risk and Capital Markets Solutions Conference held in Frankfurt, Germany, 2011.

19



Table 1: This table reports the cohort dependent parameters, ax and bx, from the Lee Carter
model. The parameter estimates are obtained with data for US females from 1950 to 2007.

Cohort aged 65-69 aged 70-74 aged 75-79 aged 80-84
ax -4.0058 -3.5465 -3.0712 -2.5702
bx 0.0383 0.041 0.0456 0.0408

Under some identifying assumptions each of the model’s variables has a clearly defined

economic interpretation. For example, kt is a time indicator of the mortality level and it

provides a general idea of the global mortality level for each year t. Thus, if we observe a

trend of decreasing kt values over the years, this means that mortality rates have a tendency

to decline over time. The bx values provide the sensitivity of the mortality rate of a specific

age to changes in this level of overall mortality. For an age x, the higher the value of b, the

more impact a variation in the kt values will have on the mortality rates of people this age.

Finally, the ax values are interpreted as being the average over time of the natural logarithm

of the mortality rates of people of age x.

4.1.1 Estimation results for the Lee and Carter model

We apply the Lee-Carter model to US females and use data from 1950 to 2007 for estimation.9

We will be paying particular attention to the older cohorts, say those aged 65-69 and older.

In Table 1 we report the estimated values for the cohort dependent parameters ax and bx

(although only the results for the older cohorts are reported, all other results are available

from the authors). The table shows that the estimated ax decreases with age. This means

that the level of mortality increases with age which is very intuitive. The estimated value of

bx on the other hand is generally increasing. This means that the sensitivity of mortality to

the overall mortality level kt increases with age, something which is again very intuitive.

Finally, based on the full set of estimated parameters one can re-estimate the values of kt

9The appendix contains details on the procedure used for estimation.

20



1950 1960 1970 1980 1990 2000 2010
−8

−6

−4

−2

0

2

4

6

8

10

k
t
 from the Lee−Carter model through time for US females

Figure 1: This figure plots the estimated time series of estimated kt for US females. The
estimates are obtained using data from 1950 to 2007.

to generate the life tables observed in reality. To do this we iteratively calculate the values

of kt, for each time t, that results in matching as closely as possible the total number of

deaths. The resulting time series is shown in Figure 1. The figure clearly shows a downward

trending pattern indicating that overall mortality rates have been declining. Note though

that this decrease is not deterministic and instead kt evolves randomly over time.

4.1.2 Forecasting with the Lee and Carter model

In order to use the Lee-Carter model to forecast future mortality rates all that is needed is

to project the future values of kt. After all, the coefficients ax and bx are presumed fixed

21



Table 2: This table reports time series estimated for the time dependent parameter kt from
the Lee Carter model. The parameter estimates are obtained with data for US females from
1950 to 2007.

θ s.e. (θ) φ s.e. (φ) R2 σ

-0.29033 0.04499 0.98681 0.00941 0.995 0.33954

over time and vary only with age. We consider here the simplest possible model, that is we

use a simple autoregressive model of order one, an AR(1) model. The model is written as

kt = θ + φkt−1 + εt, (25)

where εt ∼ N (0, σ2) and where it is assumed that φ < 1 for stationarity. Under these

assumptions we can estimate the values of θ and φ using a linear regression method, and

calculate the variance of the residual εt values.

Table 2 shows the resulting parameter estimates along with the R2. The table shows

that a simple AR(1) model actually provides a very good fit to the data. It is nevertheless

worth noting that the estimated value of φ is not statistically lower than 1 and there may

be problems of data non-stationarity.10 A more elaborate model is thus likely needed to

accommodate the features of the data, but since the simple AR(1) model is sufficient to

illustrate the points of this paper, we shall leave open for future research the possibility of

using more sophisticated longevity models.

4.1.3 Risk neutral simulation

In the Lee-Carter model uncertainty about future mortality rates stems from uncertainty

about the future values of kt as this depends on the innovations εt. Hence for pricing purposes

10It should be noted that there is essentially an “errors in variable” problem here as the kt’s are estimated.
Hence the estimated coefficient φ is expected to by biased toward zero, and the errors in variables problem
also affects the variance of the estimate.

22



0.985 0.9855 0.986 0.9865 0.987 0.9875 0.988 0.9885
0

200

400

600

800

1000

1200
Lambda=0

0.985 0.9855 0.986 0.9865 0.987 0.9875 0.988 0.9885
0

200

400

600

800

1000

1200
Lambda=0.1

0.985 0.9855 0.986 0.9865 0.987 0.9875 0.988 0.9885 0.989 0.9895
0

200

400

600

800

1000

1200
Lambda=0.2

0.985 0.9855 0.986 0.9865 0.987 0.9875 0.988 0.9885 0.989 0.9895
0

200

400

600

800

1000

1200
Lambda=0.3

Figure 2: This figure plots the simulated risk neutral distribution of survivor rates for the
cohort of 65-69 year old US females for various values of λ. The simulations are based on
parameter estimates from Tables 1 and 2 and using as the initial value k0 = −7.5034.

it is these innovations that need to be risk neutralized. As we explained earlier, in a Normal

setting this can be achieved by shifting the innovations. Thus, instead of using random

draws from a N (0, σ2) distribution we use draws from a N (−λσ, σ2) distribution. Since the

derivatives we consider are not written on kt and are instead linked to the survivor index

we transform the simulated values of kt into predicted mortality rates using (24) from which

the simulated survivor rates can be obtained. Thus, this situation is easily accommodated

in our simulation setup, though it should be noted that for other approaches this may make

it impossible to solve the pricing problem as the actual dynamics become intractable or

unknown.

A simulation consists of a large number of trajectories for the kt values which we generate

recursively: One for each year necessary where each kt is generated based on the estimated

parameters, and a random Normal error. In Figure 2 we show the 5 year ahead risk neutral

densities for the 65-69 cohort for various values of the risk premium parameter λ between

23



Table 3: This table shows percentiles of the simulated distribution for the cohort of 65-69
year old females in the US in 2012 for different values of λ. The simulations are based on
parameter estimates using data from 1950 to 2007.

Percentiles 0.01 0.05 0.1 0.5 0.9 0.95 0.99
λ = 0.0 0.98592 0.98619 0.98633 0.98682 0.98729 0.98742 0.98766
λ = 0.1 0.98601 0.98628 0.98642 0.98690 0.98737 0.98750 0.98773
λ = 0.2 0.98610 0.98636 0.98650 0.98698 0.98745 0.98758 0.98781
λ = 0.3 0.98619 0.98645 0.98659 0.98706 0.98753 0.98766 0.98789

0.0 and 0.3.11 The simulated densities are based on the cohort specific values in Table 1

and on the estimates of the dynamics for the mortality level kt in Table 2. The figure shows

that the density shifts to the right as the risk premium increases. In Table 3 we report some

percentiles of the simulated distributions. The table confirms that the distribution shifts to

the right and also shows that the relative largest differences are found in the left tail of the

distribution consistent with the Log-Normal distribution of these rates.

4.2 Pricing results

With the simulated values under the risk neutral distribution we can now price any of the

longevity risk derivatives mentioned above. In particular, the survivor forwards and swaps

are relatively simple functions of the mean, or expected value, of the simulated risk neutral

density. In Panel A of Table 4 we report such simulated risk neutral density means for the

years 2008 to 2012 for different values of λ. Again these predictions are based on estimates

obtained with data from 1950 to 2007 for American females aged 65-69. For the options,

however, we need the entire simulated distribution; a situation we shall return to later.

11These values encompass the range of reasonable estimates for λ. For example, Lin and Cox (2005)
estimate λ to be 0.1792 for American males aged 65 and 0.2312 for American females aged 65.

24



Table 4: This table shows the means of the simulated distribution as well as the forward and
swap premiums for different values of the risk premium. Panel A shows the mean values,
Panel B the forward premium, and Panel C the swap premium.

Panel A: Mean values
Year 2008 2009 2010 2011 2012

λ = 0.0 0.98644 0.98653 0.98663 0.98672 0.98681
λ = 0.1 0.98645 0.98657 0.98668 0.98679 0.98689
λ = 0.2 0.98647 0.98660 0.98673 0.98686 0.98698
λ = 0.3 0.98649 0.98664 0.98678 0.98692 0.98706

Panel B: Forward premiums
Maturity 1 2 3 4 5
λ = 0.1 0.17820 0.36062 0.52115 0.69008 0.84091
λ = 0.2 0.37023 0.72670 1.05701 1.38222 1.71109
λ = 0.3 0.52758 1.05155 1.55338 2.04468 2.51496

Panel C: Swap premiums
Maturity 1 2 3 4 5
λ = 0.1 0.17820 0.26807 0.34996 0.43127 0.50844
λ = 0.2 0.37023 0.54584 0.71123 0.87164 1.02979
λ = 0.3 0.52758 0.78571 1.03410 1.27569 1.50916

4.2.1 Survivor forwards

Based on the values in Panel A of Table 4 we can calculate the survivor forward premiums

as

π
f
t =

NPV (RASIt)

NPV (PSIt)
− 1, (26)

where RASIt is the risk adjusted survivor index given by the mean of the simulated risk

neutral density and PSIt is the predicted survivor index. Though the latter could be calcu-

lated in various ways, for simplicity and model consistency we take these to be equal to the

simulated values with λ = 0. This approach is completely consistent as long as we suppose

that values are available at the time of pricing, which essentially requires that the model and

model parameters are known.

25



The resulting premiums in basis points are shown in Panel B of Table 4, in which we

report the values for various maturities and for various values of the risk premium λ. The first

thing to note from the table is that survivor forward premiums are increasing in maturity and

in the risk premium. The reason an increasing risk premium increases the forward premium

is very intuitive: The higher is the risk premium, the more compensation investors require

for exposure to uncertainty. Note that as maturity increases the relative importance of the

risk premium decreases.

4.2.2 Survivor swaps

To price the swaps we need further assumptions about the rate of interest. In the following,

we assume that this is fixed at 3% and constant through time. The price of a swap with 3

payments is now given by

πs
t,t+2 =

NPV (RASIt) +NPV (RASIt+1) +NPV (RASIt+2)

NPV (PSIt) +NPV (PSIt+1) +NPV (PSIt+2)
− 1, (27)

where again we set PSIt equal to the simulated means with λ = 0. The premiums in basis

points are shown in Panel C of Table 4 for different maturities and values of the risk premium

λ. Note that by construction a swap with one year to maturity has the same premium as

the forward.

The first thing to note from this panel is that, as it was the case with the forward

premiums, swap premiums are increasing in maturity and in the risk premium. The table

also shows that the relative increase in the swap premium with maturity greater than one

year is less pronounced than for the forward premium. The reason for this is that the swap

can be seen as a portfolio of forwards, and hence the swap premium is essentially an average

of the forward premiums. Increasing risk premium, on the other hand, has a larger relative

effect on the swaps than on the forwards. For example, increasing λ from 0.1 to 0.2 for the

26



swap with two year maturity doubles the premium whereas this only increases the forward

premium by 3/4. The reason for this is again that as maturity increases the relative increase

in the premium with increases in the risk premium decreases.

4.2.3 Survivor moving strike options

Once the interest rate is fixed, the European style option can be valued immediately from

the simulated risk neutral densities since its price today is simply the expected value of the

discounted future cash flows. Finding the price of the American style options, on the other

hand, requires us to make further assumptions about the number of times the options can be

exercised. In our example, and given the setup of the simulation, it makes sense to assume

that early exercise is possible once each year. This corresponds not only to each time step

in the simulation, but also, and perhaps more importantly, to the release of new mortality

information by the authorities in reality. In Tables 5 and 6 we report the prices, both for

European style and American style options, and the early exercise ratio for options with

maturities up to 5 years as a function of different values for the risk premium.12

We first consider the put option prices in Table 5. Panel A shows that, for a given strike

price, option prices increase with maturity. In particular, the 5 year option with λ = 0.0

is almost twice as valuable as the option with 1 year to maturity. Interestingly, this effect

quickly vanishes as the risk premium increases and when λ = 0.3 the European option prices

are roughly constant across maturity. For the American style options, on the other hand,

the effect is present even with the highest risk premium as shown in Panel B. As a result

of the flat price schedule for the European style options and the increasing price schedule

for the American style options, the early exercises ratio increases dramatically with the risk

premium as Panel C shows. Put differently, our results show that the ability to exercise early

longevity options is worth relatively more when investors are more risk averse. For example,

12In the LSM method we use a second degree polynomial in the survivor rate in the cross sectional
regressions.

27



Table 5: This table shows prices for put options with time varying strike prices for different
values of the risk premium. Panel A shows the European prices, Panel B the American
prices, and Panel C the early exercise premium in percentage of the US price, the early
exercise ratio.

Panel A: European prices
Maturity 1 2 3 4 5
λ = 0.0 0.68444 0.92619 1.08620 1.19740 1.28150
λ = 0.1 0.60076 0.76402 0.86351 0.91336 0.95192
λ = 0.2 0.52041 0.62438 0.67419 0.68825 0.68256
λ = 0.3 0.45960 0.51585 0.52321 0.50459 0.48198

Panel B: American prices
Maturity 1 2 3 4 5
λ = 0.0 0.68444 0.93653 1.11970 1.25720 1.37200
λ = 0.1 0.60076 0.79615 0.93176 1.02840 1.10680
λ = 0.2 0.52041 0.67589 0.77618 0.84852 0.89958
λ = 0.3 0.45960 0.58317 0.65809 0.70580 0.74129

Panel C: Early exercise ratio
Maturity 1 2 3 4 5
λ = 0.0 0.00% 1.10% 2.99% 4.76% 6.60%
λ = 0.1 0.00% 4.04% 7.32% 11.19% 14.00%
λ = 0.2 0.00% 7.62% 13.14% 18.89% 24.13%
λ = 0.3 0.00% 11.54% 20.50% 28.51% 34.98%

the ability to exercise early is worth 35% of the American style option when λ = 0.3 which

is almost 6 times the value of early exercise when λ = 0.0.

Next we consider the call option prices in Table 6, in which we observe that call options

prices increase with maturity. In contrast to put options, prices of European style call

options in Panel A remain strongly related to the options’ maturity for all values of the

risk premium under consideration. The table also shows that, in contrast to the fact that

American and European style call options on stocks that pay no dividend should have the

same price, this is no longer the case when we consider options on a longevity index. In

particular, Panel C shows that the early exercise ratio is above 6% for the 5 year option (i.e.,

28



Table 6: This table shows prices for call options with time varying strike prices for different
values of the risk premium. Panel A shows the European prices, Panel B the American
prices, and Panel C the early exercise premium in percentage of the US price, the early
exercise ratio.

Panel A: European prices
Maturity 1 2 3 4 5
λ = 0.0 0.68444 0.92619 1.08620 1.19740 1.28150
λ = 0.1 0.77135 1.09910 1.33340 1.51730 1.66620
λ = 0.2 0.87482 1.29950 1.62730 1.89790 2.13590
λ = 0.3 0.96464 1.49280 1.92390 2.29400 2.61810

Panel B: American prices
Maturity 1 2 3 4 5
λ = 0.0 0.68444 0.93817 1.11780 1.25740 1.37190
λ = 0.1 0.77135 1.09930 1.34040 1.53570 1.70100
λ = 0.2 0.87482 1.29950 1.62730 1.89780 2.13610
λ = 0.3 0.96464 1.49280 1.92390 2.29400 2.61810

Panel C: Early exercise ratio
Maturity 1 2 3 4 5
λ = 0.0 0.00% 1.28% 2.82% 4.77% 6.59%
λ = 0.1 0.00% 0.02% 0.52% 1.20% 2.05%
λ = 0.2 0.00% 0.00% 0.00% -0.01% 0.01%
λ = 0.3 0.00% 0.00% 0.00% 0.00% 0.00%

the American option is worth more than 6% more than the European option) when λ = 0.0.

This discrepancy, however, vanishes as the risk premium increases.

Finally, when comparing the European option prices in Tables 5 and 6 to the forward

premium in Panel B of Table 4 the first thing to note is that the optionality that comes

with the options is important. For example, for contracts with the shortest maturity the

call option is approximately 7 times more “expensive” than the forward when λ = 0.1. The

relative importance decreases somewhat with maturity, and significantly so when the risk

premium increases so that for the longest maturity contracts, the optionality almost vanishes

when the risk premium is high. Note that the results confirm numerically the put-call parity.

29



Table 7: This table shows the swap premiums for different maturities and different values of
λ. Results are based on the high interest rate scenario with r = 6% using the mean values
in Panel A of Table 4.

Maturity 1 2 3 4 5
λ = 0.1 0.17820 0.26676 0.34667 0.42519 0.49895
λ = 0.2 0.37023 0.54328 0.70466 0.85957 1.01066
λ = 0.3 0.52758 0.78195 1.02429 1.25758 1.48068

4.3 Extensions and robustness checks

The results reported above were for one specific cohort and for a specific value of the interest

rate used for discounting. In this section we consider extensions to the results provided

above. We first consider the situation with interest rates set at 6% instead of the 3% used

above. Next, we consider the results obtained when considering the 80-84 year old cohort.

4.3.1 High interest scenario

Though a change in interest rates does not affect the premium paid for the forwards it will

affect the premium paid for the swap contracts. In Table 7 we report the premiums based

on the high interest rate scenario which may be directly compared to the results in Panel

C of Table 4. The table shows that swap premiums are lower when interest rates are high.

Moreover, the decrease in price is more significant for longer maturity contracts and the

premium for the contracts maturing in 5 periods are roughly 2% lower in this case.

A change in interest rates also affects the option prices. In Table 8 we show the prices

for the put options when interest rates are 6% instead of 3%. Compared to the results of

Table 5, we note that put option prices decrease with interest rates. This is to be expected

as an increase in the interest rates means that future payoffs are discounted more heavily.

The decrease in price is most pronounced for the European style options. For example,

the option with 5 years maturity is worth 14% less in the high interest scenario. For the

30



Table 8: This table shows prices for put options with time varying strike prices for different
values of the risk premium. Panel A shows the European prices, Panel B the American
prices, and Panel C the early exercise premium in percentage of the US price, the early
exercise ratio. Results are based on a high interest rate scenario with r = 6%.

Panel A: European prices
Maturity 1 2 3 4 5
λ = 0.0 0.66421 0.87225 0.99274 1.06200 1.10300
λ = 0.1 0.58300 0.71953 0.78919 0.81007 0.81933
λ = 0.2 0.50503 0.58802 0.61617 0.61043 0.58748
λ = 0.3 0.44601 0.48581 0.47817 0.44753 0.41485

Panel B: American prices
Maturity 1 2 3 4 5
λ = 0.0 0.66421 0.89461 1.05040 1.16420 1.25180
λ = 0.1 0.58300 0.76309 0.87901 0.96146 1.02330
λ = 0.2 0.50503 0.64903 0.73760 0.79677 0.83943
λ = 0.3 0.44601 0.56101 0.62761 0.66908 0.69786

Panel C: Early exercise ratio
Maturity 1 2 3 4 5
λ = 0.0 0.00% 2.50% 5.49% 8.78% 11.89%
λ = 0.1 0.00% 5.71% 10.22% 15.75% 19.93%
λ = 0.2 0.00% 9.40% 16.46% 23.39% 30.01%
λ = 0.3 0.00% 13.41% 23.81% 33.11% 40.55%

American style option the decrease is somewhat smaller and depends on the assumed value

for λ. For example, the options with 5 years maturity are worth between 6% and 9% less

when λ = 0.3 and λ = 0.0, respectively. As a result the early exercise ratio is much larger

when interest rates are high; the early exercise ratio may even reach 80% of the American

style options when λ = 0.0.

4.3.2 Results for the cohort aged 80-84

We now consider the results for the 80-84 year old cohort. We first report the mean values

and the forward and swap premiums in Table 9 which may compared to those in Table 4.

31



Table 9: This table shows the means of the simulated distribution as well as the forward and
swap premiums for the survivor index for the cohort aged 80-84 for different values of the
risk premium. Panel A shows the mean values, Panel B the forward premiums, and Panel
C the swap premiums.

Panel A: Mean values
Year 2008 2009 2010 2011 2012

λ = 0.0 0.94409 0.94451 0.94493 0.94533 0.94573
λ = 0.1 0.94417 0.94467 0.94515 0.94563 0.94610
λ = 0.2 0.94425 0.94483 0.94539 0.94593 0.94647
λ = 0.3 0.94432 0.94497 0.94560 0.94622 0.94682

Panel B: Forward premiums
Maturity 1 2 3 4 5
λ = 0.1 0.81760 1.65318 2.38706 3.15821 3.84529
λ = 0.2 1.69856 3.33097 4.84067 6.32448 7.82252
λ = 0.3 2.42033 4.81961 7.11304 9.35426 11.49541

Panel C: Swap premiums
Maturity 1 2 3 4 5
λ = 0.1 0.81760 1.22931 1.60405 1.97578 2.32823
λ = 0.2 1.69856 2.50288 3.25957 3.99266 4.71467
λ = 0.3 2.42033 3.60251 4.73879 5.84275 6.90840

Naturally, the means in this table are lower than those we first presented for the 65-69 year

old cohort. This is to be expected as the mortality of the 80-84 year old cohort is higher.

The table also shows that the estimated premiums for both the forwards and swaps are

significantly higher for the older cohorts so that premiums are roughly 4.6 times higher for

the older cohort than for the younger cohort. This relationship holds across maturity and

for different values of the risk premium λ.

In Table 10 we show the prices for the put options when the older cohort is considered.

Compared to the results of Table 5, Table 10 shows that premiums are higher for the 80-84

year old cohort than for the 65-69 year old cohort. Moreover, and similar to the situation

with the forward and swap contracts, there is almost a constant relative increase in the

32



Table 10: This table shows prices for put options with time varying strike prices for different
values of the risk premium for the cohort aged 80-84. Panel A shows the European prices,
Panel B the American prices, and Panel C the early exercise premium in percentage of the
US price, the early exercise ratio.

Panel A: European prices
Maturity 1 2 3 4 5
λ = 0.0 3.00550 4.06520 4.76550 5.25080 5.61700
λ = 0.1 2.63800 3.35310 3.78790 4.00460 4.17160
λ = 0.2 2.28500 2.74010 2.95710 3.01710 2.99060
λ = 0.3 2.01790 2.26360 2.29460 2.21170 2.11140

Panel B: American prices
Maturity 1 2 3 4 5
λ = 0.0 3.00550 4.11190 4.91350 5.51670 6.01850
λ = 0.1 2.63800 3.49520 4.08950 4.51250 4.85620
λ = 0.2 2.28500 2.96720 3.40680 3.72310 3.94720
λ = 0.3 2.01790 2.56020 2.88840 3.09760 3.25260

Panel C: Early exercise ratio
Maturity 1 2 3 4 5
λ = 0.0 0.00% 1.13% 3.01% 4.82% 6.67%
λ = 0.1 0.00% 4.07% 7.37% 11.26% 14.10%
λ = 0.2 0.00% 7.65% 13.20% 18.96% 24.24%
λ = 0.3 0.00% 11.59% 20.56% 28.60% 35.09%

premiums. This means that the price of the options are on average 4.4 times higher for the

older cohort. The reason that there is a constant relation between the premiums is that the

same model is used for the underlying stochastic factor.

5 Conclusion

This paper develop a unified framework for measuring and managing the risk of insurance

products. Specifically, we propose to use a flexible simulation based approach that has been

used successfully in pricing financial derivatives. Based on this least squares Monte-Carlo

33



approach, derivative products such as reinsurance contracts that can be seen as put options

can be designed to enable the insurer to value and manage its risk exposure efficiently.

Because of its flexibility, the simulation approach is particularly well suited to be used

for pricing derivative products on longevity risk since modeling the underlying risk factors

is non-standard. All that is required is the ability to simulate from the risk neutral distri-

bution. This can often be obtained through distortion or other equivalent transformations.

The simulation method can be used to price derivatives with path dependence as well as

derivatives that allow e.g. early exercise such as the American style options.

We show how this technique can be applied to manage longevity risk when the mortality

distribution follows a Lee-Carter model. Our results show that taking the optionality into

consideration is important from a pricing perspective. Moreover, the possibility of exercising

the options early increases the value of put options significantly. Our findings have important

implications for the valuation of reinsurance contracts that are essentially put options. We

also price products in a high interest rate scenario and for cohorts of different ages. The

results show that the premium of forward contracts, swaps, and options decrease marginally

with the interest rate but increase significantly with cohort age.

Though the application we provide is to a very simple benchmark Lee-Carter model,

the simulation method we propose can be used to price longevity products in general irre-

spective of the assumed model. An obvious extension is to apply our methodology to more

complicated models. This can be done with little or no complications as long as it remains

possible to simulate directly from the driving risk neutral distribution. Our approach can

also easily incorporate parameter uncertainty by applying simple Bayesian methods, and it

would be interesting to examine the effect of this on particularly the older cohorts. Finally,

other extensions include pricing longer maturity contracts and contracts on other survivor

indices.

34



References

1. Bacinello, A. R., E. Biffis, and P. Millossovich (2009): “Regression-Based Algorithms

for Life Insurance Contracts with Surrender Guarantees,” Quantitative Finance, 10(9),

1077–1090.

2. Bacinello, A. R., E. Biffis, and P. Millossovich (2010): “Pricing Life Insurance Con-

tracts with Early Exercise Features,” Journal of Computational and Applied Mathe-

matics, 233, 27-35

3. Blake, D., A. J. G. Cairns, and K. Dowd (2006): “Living with Mortality: Longevity

Bonds and Other Mortality-Linked Securities,” British Actuarial Journal, 12(I), 153-

228.

4. Boyle, P. P. (1977): “Options: A Monte Carlo Approach,” Journal of Financial Eco-

nomics, 4, 323–338.

5. Brown, J. R. (2004): “Life Annuities and Uncertain Lifetimes,” NBER Research Paper,

Spring 2004.

6. Bühlmann, H., F. Delbaen, P. Embrechts, and A. N. Shiryaev (1996): “No-arbitrage,

Change of Measure and Conditional Esscher Transforms,” CWI Quartely, 9, 291–317.

7. Cairns, A. J. G., D. Blake, and K. Dowd (2006): “A Two-Factor Model for Stochastic

Mortality with Parameter Uncertainty: Theory and Calibration,” The Journal of Risk

and Insurance, 73(4), 687–718.

8. Carriere, J. (1996): “Valuation of the Early-exercise Price for Options using Simula-

tions and Nonparametric Regression,” Insurance: Mathematics and Economics, 19(1),

19-30.

35



9. Christoffersen, P., R. Elkamhi, B. Feunou, and K. Jacobs (2010): “Option Valuation

with Conditional Heteroskedasticity and Non-Normality,” Review of Financial Studies,

23, 2139–2183.

10. Cocco, J. F., and F. J. Gomes (2009): “Longevity Risk, Retirement Savings, and

Financial Innovation,” London Business School working paper.

11. Coughlan, G., D. Epstein, A. Sinha, and P. Honig (2007): “q-Forwards: Derivatives

for Transferring Longevity and Mortality Risk,” JPMorgan Pension Advisory Group

Report.

12. Davies, J. (1981): “Uncertain Lifetime, Consumption and Dissaving in Retirement,”

Journal of Political Economy, 89, 561–577.

13. Dawson, P., K. Dowd, A. J. G. Cairns, and D. Blake (2010): ”Survivor Derivatives: A

Consistent Pricing Framework,” The Journal of Risk and Insurance, 77(3), 579-596.

14. Dowd, K., D. Blake, A. J. G. Cairns, and P. Dawson (2006): “Survivor Swaps,” The

Journal of Risk and Insurance, 73(1), 1-17.

15. Gaille S., (2010): Improving longevity and mortality risk models. Ph.D. Thesis, Uni-

versité de Lausanne, Faculté des Hautes Études Commerciales.

16. Gerber, H., and E. Shiu (1994): “Option Pricing by Esscher Transforms,” Transactions

of the Society of Actuaries, 46, 99–191.

17. Gourieroux, C., and A. Monfort (2007): “Econometric Specification of Stochastic Dis-

count Factor Models,” Journal of Econometrics, 136, 509–530.

18. Huang, H., M. A. Milevsky and T. S. Salisbury (2012): “Yaari’s LifeCycle Model in

the 21st Century: Consumption Under a Stochastic Force of Mortality, ” Risk Theory

Society Seminar paper, March 2012.

36



19. Kijima, M. (2006): “A Multivariate Extension of Equilibrium Pricing Transforms: The

Multivariate Esscher and Wang Transforms for Pricing Financial and Insurance Risks,”

ASTIN Bulletin, 36(1), 269–283.

20. Lee, R. D., and L. R. Carter (1992): “Modeling and Forecasting U.S. Mortality,”

Journal of the American Statistical Association, 87(419):659–671.

21. Levhari, D., and L. Mirman (1977): “Savings and Consumption with an Uncertain

Horizon,” Journal of Political Economy, 85, 265–281.

22. Li, S.-H. and W.-S. Chan (2007): “The Lee-Carter Model for Forecasting Mortality

Revisited,” North-American Actuarial Journal, 11(1): .68-89.

23. Lin, Y. and S. H. Cox (2005): “Securitization of Mortality Risks in Life Annuities,”

The Journal of Risk and Insurance, 72(2), 227-252.

24. Longstaff, F. A. and E. S. Schwartz (2001): “Valuing American Options by Simulation:

A Simple Least-Squares Approach,” Review of Financial Studies, 14, 113-147.

25. Nordahl, H. A. (2008): “Valuation of Life Insurance Surrender and Exchange Options,”

Insurance: Mathematics and Economics, 42, 909-919.

26. Renshaw, A., and S. Haberman (2006): “A Cohort-based Extension to the Lee-Carter

Model for Mortality Reduction Factors,” Insurance: Mathematics and Economics,

38(419), 556–570.

27. Robine, J.-M. (2011): “A Survey of Longevity Modeling Approaches,” Mimeo.

28. Rombouts, J., and L. Stentoft (2011): “Multivariate Option Pricing with Time Varying

Volatility and Correlations,” Journal of Banking and Finance 35, 2267–2281.

37



29. Stentoft, L. (2004): “Convergence of the Least Squares Monte Carlo Approach to

American Option Valuation”, Management Science 50 (9), 1193-1203.

30. Stentoft, L. (2008): “Value Function Approximation or Stopping Time Approximation:

A Comparison of Two Recent Numerical Methods for American Option Pricing using

Simulation and Regression”, SSRN Working Paper.

31. Stentoft, L. (2012): “American Option Pricing using Simulation: An Introduction with

an Application to the GARCH Option Pricing Model,” forthcoming in Handbook of

Research Methods and Applications in Empirical Finance.

32. Wang, S. S. (2000): “A Class of Distortion Operators for Pricing Financial and Insur-

ance Risks,” The Journal of Risk and Insurance, 67(1), 15–36.

33. Wang, S. S. (2003): “Equilibrium Pricing Transforms: New Results Using Buhlmann’s

1980 Economic Model,” ASTIN Bulletin, 33(1), 57–73.

34. Wang, S. S. (2007): “Normalized Exponential Tilting: Pricing and Measuring Multi-

variate Risks,” North American Actuarial Journal, 11(3), 89–99.

35. Yaari, M. E. (1964): “On the Consumer’s Lifetime Allocation Process,” International

Economic Review, 5: 304-317.

38



A Estimation of the Lee Carter model

The estimation of the Lee and Carter model is performed according to the following stages:

1. Calculation of the ax values

2. Calculation of the kt values

3. Estimation of the bx values

4. Re-estimation of the kt values

First of all, the ax values must be calculated. As previously explained, these values are,

for all x, the average over time of the natural logarithm of the mortality rates at age x.

Letting n denote the the number of years of data used to estimate the model, then we have

ax =
1

n

∑

t

ln (mx,t) .

Secondly, the kt values must be calculated. Given that the sum of the bx values has been

fixed at 1, these values can be approximated. For each t, the kt values equal the sum across

all ages of the difference between the natural logarithm of the mortality rates in t and the

ax values. In mathematical terms this can be expressed as

kt =
∑

x

ln (mx,t)− ax.

Thirdly, the bx values can now be estimated using linear regressions over time, performed

separately for all x values. For each x value, we perform a linear regression without constant

where the dependant variable is the difference between the natural logarithms over time of

the mortality rates at age x and the constant ax associated with this x value, and where the

explanatory variable is the kt values. Thus, for each x value, we regress y = ln (mx,t) − ax

on x = kt. The coefficients corresponds to the estimated values of bx.

39



Fourth and finally, it is recommend that the kt values be re-estimated. As calculated so

far, the kt values do not allow one to generate the life tables observed in reality. Indeed, they

have been calculated in such a manner that each mortality rate at each age is of the same

significance. However, certain age categories are larger than others. As a consequence, a

same mortality rate for two different ages will not necessarily represent the same number of

deaths. Lee and Carter therefore propose a re-estimation of the kt values by iteration using

observations of the size of each population for each age and the number of deaths. Thus, let

Nx,t denote the size of the population of age x in the year t and let Dt denote the number of

deaths, inclusive of all ages, in the year t. For each t, we must determine, by iteration, the

associated kt value so that

Dt =
∑

x

Nx,te
ax+bxkt,

for each t. In particular, eax+bxkt corresponds to the mortality rate of individuals of age x

in the year t. The number of individuals of age x in t is then multiplied by this mortality

rate and we thus obtain the number of deaths in the year t among individuals of age x. The

same calculation can be performed for all x values. The sum of the number of deaths in the

year t allows us to obtain the total number of deaths for that year. We must then find the

k value of the period that is as close as possible to the total number of deaths. A new study

by iteration is performed for each t.

Once these four stage have been completed, we know the ax, the bx and the kt values that

make it possible to model, as realistically as possible, the surface of the mortality observed,

the latter corresponding to the different mortality rates over time and across all ages.

40


	Introduction
	Examples of longevity derivative products
	Survivor forwards
	Survivor swaps
	Survivor options

	Pricing longevity derivatives using simulation
	Risk neutral distributions
	Risk neutral simulation
	Relation to other risk neutralization methods

	European style instruments
	Derivatives with early exercise features

	Application to pricing survivor derivatives
	The Lee-Carter model
	Estimation results for the Lee and Carter model
	Forecasting with the Lee and Carter model
	Risk neutral simulation

	Pricing results
	Survivor forwards
	Survivor swaps
	Survivor moving strike options

	Extensions and robustness checks
	High interest scenario
	Results for the cohort aged 80-84


	Conclusion
	Estimation of the Lee Carter model

