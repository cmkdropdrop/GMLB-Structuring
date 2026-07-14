https://actuaries.org/app/uploads/2025/07/LIFE_Weber_Biometric_Paper_Munich2009.pdf
→ https://actuaries.org/app/uploads/2025/07/LIFE_Weber_Biometric_Paper_Munich2009.pdf
Content-Type: application/pdf

Mortality-Indexed Annuities
Avoiding Unwanted Risk
Andreas Richter∗ Frederik Weber†
March 2009
Submitted to the Scientific Committee
for the 3rd IAA Life Colloquium in Munich
Related topic: 2.) Designing life insurance products
Abstract
Longevity risk has become a major challenge for governments, individuals, and
annuity providers in most countries, and especially its aggregate form, i.e. the
risk of unsystematic changes to general mortality patterns, bears a large potential
for accumulative losses for insurers. As obvious risk management tools such as
(re)insurance or hedging are less suited to manage an annuity provider’s exposure
to aggregate longevity risk, the current paper proposes a new type of life annuities
where benefits are contingent on actual mortality experience, and details actuarial aspects of implementation. Similar adaptations to conventional product design
exist in investment-linked annuities, and a role model for long-term contracts contingent on actual cost experience is found in German private health insurance so
that the idea is not novel in general, but it is in the context of longevity risk.
By not or re-transferring the systematic longevity risk insurers may avoid accumulative losses so that the primary focus in an extensive Monte-Carlo simulation
is placed on the question of whether such products could also be advantageous for
policyholders and to what extent this would be the case in contrast to a comparable
conventional annuity product.
Keywords: Longevity risk, systematic risk, risk avoidance, mortality-indexed
annuities.
JEL Classification: G22; G23; C15.
∗
Institute for Risk and Insurance Management, Ludwig-Maximilians-Universität München, GeschwisterScholl-Platz 1, 80539 Munich, Germany. Phone: +49 89 2180-2171. E-mail: richter@lmu.de.
†
Institute for Risk and Insurance Management, Ludwig-Maximilians-Universität München, GeschwisterScholl-Platz 1, 80539 Munich, Germany. Phone: +49 89 2180-3882. E-mail: fweber@bwl.lmu.de. Corresponding author.
1
1 Motivation and Introduction
For quite a while scholars and practitioners – not only with a focus on insurance but also
with backgrounds such as sociology, demography, health sciences, and other areas – have
been discussing a globally observable phenomenon commonly named demographic transition.
1
Strong, sustaining changes of mortality, fertility, migration and other factors have tremendously
affected age structures of most countries’ population, and a rapid increase of average individual
lifetime is a predominant consequence.2Inseparably linked to a reduction of mortality rates
at virtually all ages, it may be considered more than welcome from each individual’s point
of view, and it can also be recognized as a societal achievement and major success of wellfunctioning public health and old-age care systems, improved working conditions, and also
healthier lifestyles.
The often cited longevity trend can be traced back approximately 100–150 years for most
Western countries. Looking at female life expectancies in several countries, Oeppen and Vaupel (2002) impressively show that each individual country has experienced a steady growth of
lifetime during the past 150 years which is a strong argument supporting this notion. Even
more interestingly, when taking together all countries, the existence of a global linear trend
also seems to be supported.
The risk of outliving one’s savings or other financial resources to cover expenses during
retirement could also be understood as some sort of individual longevity risk, but the same
term has been used in the literature also to refer to individual fluctuations around a general
average mortality, i.e. the risk of living shorter or longer than the average member of the
respective group of individuals. In fact, life and pension insurance are based on a balancing of
risks across sufficiently large portfolios, and they make explicit use of the individual fluctuations
around an average value without which the entire functioning of insurance would have to be
put into question. While some annuity contracts terminate sooner some cease later so that the
entire portfolio of contracts is eventually balanced, and with an increasing number of policies
results stabilize.3
However, the term aggregate longevity risk, has been used rather to refer to the additional
uncertainty about changes in the underlying patterns, and this particular risk can be considered
a major concern for insurers. Because, given a sufficiently prudent selection of the insured
portfolio, an insurer can well diversify the unsystematic, individual form of this risk and should
on average not suffer losses nor generate gains from mortality differences. On the other hand
the aggregate form can also be considered a systematic risk since it refers to unforeseeable
random changes representing strong correlations between single contracts and thus potential
accumulative losses.
Of course, while differences between single countries seem to exist, the aggregate form of
this risk becomes even more threatening when seen from an international perspective as seems
suitable for a global primary insurance group or most reinsurers.
Increasing life expectancy has not been paralleled by a similar prolongation of working life,
and individuals tend to survive a substantial, increasing number of years beyond retirement age.
1 See Montgomery (2007) for a depiction and explanation of different stages of demographic transition.
2 For a discussion not limited to Western industrialized nations see e.g. United Nations (2005).
3 See for instance Leinert and Wagner (2001) for an analysis of intergenerational effects in the German private
annuities market caused by the longevity trend.
1
In fact, individual provision for an adequate and sufficient standard of living has become one of
the most pressing challenges for 21st century societies. Insurance contracts as the traditionally
dominating instruments for transferring financial risks offer the possibility to transfer longevity
risk exposure by means of life annuity contracts.4
Here, the insurer can be considered to be in a situation similar to assuming the short position
in a forward contract on the annuitants’ survival, and as is the case with securities as underlyings, the actual remaining number of years to live is uncertain for both the annuitant and
the providers. In the view of the longevity trend it thus seems to be quite risky for an insurer
to promise nominally fixed annuity payments contingent on the policyholder’s survival – yet
this might be the most desirable contract design for the (potential) annuitant. Insurers are
thus challenged to reconcile exposure to longevity risk and their customers’ growing demand
for adequately designed insurance products.
Curiosity has driven research for adequate mortality models for quite some time5 and several attempts have been made, yet none of them has been universal enough to fit actually
observed mortality patterns for all countries and all time periods, and it is quite unlikely that
such models will ever exist. For a detailed overview and a categorization of several stochastic
mortality models see e.g. Cairns et al. (2006). One of the most prominent stochastic models
for mortality was proposed by Lee and Carter (1992, henceforth LC), and it has rapidly gained
acceptance in academia and among practitioners, which could partly be due to its relative
simplicity.6 However, in its original form it has a number of shortcomings, such as the homoscedasticity of error terms, which Alho (2000) criticized as somewhat unrealistic, or a lack
of simple implementation.
Among a large number of extensions (see, for example, Lee (2000) or Renshaw and Haberman (2003)) is an approach presented by Brouhns et al. (2002) who resort to the notion that
the number of deaths can be regarded as a Poisson counting process. This implies that error terms are heteroscedastic, which seems to be more realistic, and their model has also the
advantage that parameters can be estimated iteratively, thus greatly facilitating the computational implementation. This alternative approach is thus adopted here and will be denoted by
PML (Poisson Maximum Likelihood).
It needs to be mentioned here that two major concerns persist when applying the already
existing models: model uncertainty, i.e. the uncertainty of whether a specific model is at all
suitable for describing the underlying data, and parameter uncertainty, i.e. the question of
whether – given a specific model – the respective parameters are correctly estimated just by
using observed data from the past. These potential drawbacks must be accepted as inherent
to fitting models to data from the past in order to obtain projections for the future. As they
cannot be completely avoided a they need to be kept in mind.
It is a hope that the accuracy and detailedness of models will be further increased, and some
restrictions which have existed in the past (such as technical limitations or implementation
issues) have become negligible. Ultimately, a wide range of models and sufficient knowledge
4 An extensive investigation for how people in Germany have made provisions for their old-age income is
provided e.g. by GDV (2004).
5 Note for instance the well-known models proposed by De Moivre (1756), Gompertz (1825), or Makeham
(1860).
6 For example, the Lee-Carter model served as a starting point for mortality forecasting models used by the
U.S. Social Security Administration; see for instance Lee and Tuljapurkar (1998) or Lee et al. (2003) and
Edwards et al. (2003).
2
about when to use which of them can be expected.
Among the typical instruments implemented within a structured, iterative risk management process techniques such as hedging or risk transfer, e.g. through insurance, are widely
used. However, due to the strong correlation and thus potential accumulative losses it may be
questioned whether the aggregate form of longevity risk can be insured without restrictions.
Even when pooled with large reinsurance companies, the systematic risk associated with the
longevity trend still prevails and cannot be offset by larger portfolio sizes, i.e. the Law of Large
Numbers is likely to fail and not to alleviate the threat affected insurers might be facing.
Successful hedging on the other hand requires that an insurer engages in financial transactions that effectively cancel or offset the exposure to the particular risk in question. Though
often proposed, natural hedging, i.e. a balancing of exposures to mortality (life insurance) and
longevity risk (annuities), seems at least questionable due to many potential drawbacks. For instance contract terms, relevant ages, or (anti-)selection effects do all speak rather against such
an opportunity, but advances in this field could of course provide insurers with an additional
tool to mitigate aggregate longevity risk.
Eventually, it may seem worthwhile to resort to another risk management tool: risk avoidance. More precisely, by avoiding to assume the aggregate or systematic portion of longevity
risk in annuity contracts, an insurer may effectively reduce this particular exposure. However,
since it is usually an inseparable part of the risk transferred in life annuities the strategy of
avoidance effectively means that not the entire risk would be transferred or, equivalently, to
some extent ex-post shifted back to the policyholders. Riemer-Hommel and Trauth (2005)
claim that such adjustments would be “uncompetitive” but do not further investigate such
innovations and instead concentrate of reinsurance and hedging, among others.
The present contribution is designed to address the question of how exactly providers could
make adaptations to the still predominant “classic” product designs. For this purpose, an
annuity type with benefits linked to actual mortality experience is proposed including an
underlying actuarial model for calculation and reserving purposes. By not or re-transferring
the systematic longevity risk insurers may avoid accumulative losses so that the primary focus
in an extensive Monte-Carlo simulation is placed on the question of whether such products
could also be advantageous for policyholders and to what extent this would be the case in
contrast to a comparable conventional annuity product.
2 Risk Avoidance through Product Redesign
2.1 Introductory Remarks
As mentioned before the choices of hedging or insurance as common risk management tools,
which in many other cases are straightforward, seem to be either unavailable or unsuitable for
an affected insurance company to adequately manage this type of exposure. If instead annuity
providers seek to reduce or diminish their exposure through avoidance of aggregate mortality
risk, it was already mentioned earlier that the most drastic way would of course be to not sell
life annuities and similar products at all. Consequently also all the benefits these products
can provide would be forgone. Considering that this “solution” would deprive individuals or
insurees of the opportunity of transferring any part of their personal longevity risk, it seems
interesting from a welfare point of view whether less drastic risk management options exist
that still allow for a transfer of at least the non-systematic portion of the risk. One way
3
of tackling this could be to exclude (or reduce) the exposure to systematic longevity risk as
already briefly mentioned before. Apart from the immediate fact that insurance companies
disposing off this particular risk may have a preference for such a curtailed product, it is less
obvious whether or not such adaptation is disadvantageous for policyholders, challenging the
asserted “uncompetitiveness” as e.g. claimed by Riemer-Hommel and Trauth (2005).
A specific redesign of conventional life annuities will be proposed and further analyzed below.
Note at this point that annuity markets have already seen similar (successful) adaptations to
conventional product designs which will be briefly presented in Section 2.3, and this may
serve as a justification for turning away from conventional, established products in the present
context which aims at reducing an insurer’s exposure to systematic longevity risk. Also note
that potential role models for the exclusion of a specific, “systematic” part of risk otherwise
transferred to insurers exist in other lines of insurance, and one such model further discussed in
Section 2.3 exhibits similarities to the problem of undesirable aggregate longevity risk exposure
in conventional life annuities.
2.2 Previous Modifications of Conventional Annuities
“Traditional” life annuities in Germany (and many other countries) have long included a valuable, yet conservative guarantee of a minimum interest rate earned on the premiums paid. As
actual returns on the insurers’ investments often exceeded these minimum yields the excess
amounts were consequently largely distributed to policyholders.7 This mechanism obviously
requires little or no action by policyholders, and as long as capital market yields were substantially higher than minimum guarantees, insurers could well use the argument of (historically)
quite attractive surplus participation for marketing purposes.
However, more innovative products such as unit-linked or variable annuities have been designed and successfully introduced in the insurance markets.8 A distinct feature compared to
conventional annuities is the fact that the investment risk is not born by the insurer but by
the policyholder who may often choose from only a limited range of investment bundles offered
by the insurer. With an increase of private persons’ general interest in capital market investments and awareness of its potential for higher returns against a (higher) risk investment-linked
annuities have gained a sizeable share in the pension products market.9
7 German statutory regulation requires insurers to redistribute at least 90% of investment returns earned from
the policyholders’ reserves in excess of the minimum guarantee. Such provisions for Germany, applicable to
different “generations” of life insurance and life annuities contratcs are governed by Verordnung über die Mindestbeitragsrückerstattung in der Lebensversicherung (Mindestzuführungsverordnung – MindZV) as of April
04, 2008 (see BGBl. I S.690), Verordnung über die Mindestbeitragsrückerstattung in der Lebensversicherung
(ZRQuotenV) as of July 23, 1996 (see BGBl. I S.1190), and Verordnung über die Berechnung und Höhe
des Rückgewährrichtsatzes, des Normrisikoüberschusses und des Normzinsertrages in der Lebensversicherung
(Rückgewährquote-Berechnungsverordnung – RQV) as of March 28, 1984 (see BGBl. I S.496), respectively.
As an industry practice, the actual fraction of redistributed execess returns had often been even higher.
8 The term unit-linked annuities generally refers to deferred annuities where during the accumulation phase the
premiums paid are accrued according to the performance of a certain type of investment, chosen or at least
influenced by the policyholder, whereas variable annuities also link the actual amount of benefits during the
payout phase to an investment performance indicator. In a sense, both products do not promise nominally
fixed annuity benefits as would be the case with conventional annuities, but in the former case the amount of
benefits can ultimately be determined at the inception date of the payout phase. For a discussion of especially
the latter annuity type see e.g. Mutschler and Ruß (2001).
9 Relevant statistical data for e.g. Germany can be found in the series “Statistical Yearbook of German Insurance” which is regularly published by the German Insurance Association (GDV), the most recent being
GDV (2008).
4
Despite the admittedly different circumstances of risk non-transfer, just the transition from
guaranteed investment yields to an insured person’s option to flexibly choose investments and
consequently bear the performance risk does not only give a counterexample to the notion that
policyholders would in general reject any changes to traditional products but also that under
certain circumstances they might even be interested in taking on a significant share of the risk.
Of course, policyholders would only accept to bear this additional amount of risk if they are
adequately compensated for, or rather if such an alternative features lower prices or additional
benefits in comparison to the “conventional” product.10
2.3 An Example for Policies Shifting Insurance Risk Back to the Insured: German
Private Health Insurance
The above mentioned idea of linking annuity benefits not to investment performance but to
actual mortality experience – be it that of a given portfolio of insured, an entire insurance
company, the insurance industry as a whole, or a specific country’s population – is not a novel
idea in the sense that products accounting for loss experience do exist. However, due to the
extreme longterm character of life annuity contracts, which can easily exceed 40 years, it is
not a trivial problem to connect the actual realizations of the insured risk to future benefits.
A comparable concept can for instance be found in insurance contracts as they are common
in the German private health market.11 With the exception of civil servants, freelancers,
and higher-income earners these products are only supplemental for the vast majority of the
population, as those persons are generally covered by the health branch of the German social
security system. However, the basic actuarial concept of such contracts as longterm coverage
is similar to life annuities, and this is a distinct feature in comparison to many countries
where health contracts bear more similarities to property/casualty insurance.12 In exchange
for regular constant premium payments health care costs are covered for the entire lifetime of
the insured person. This way, excessive costs for increasingly needed medical procedures at
older ages are avoided at the cost of premiums that are higher than necessary at younger ages.
Another similarity is the fact that it would be a special challenge to adequately predict the
future development of health care costs at the time of contract inception. Generally speaking,
the health care cost inflation has historically been higher than e.g. the consumer price index
development, and further innovations in medical procedures and techniques also lead to more
expensive treatments. This special type of uncertainty can best be compared to the aggregate
form of longevity risk, where a general tendency can be expected but where also the specific
extent of its future development is hard to determine.
To enable insurers to still provide lifelong coverage, premiums may be increased (and also
have to be lowered) in the case and to the extent that actual benefits of a portfolio of policies
paid exceed (or under-run) presumed amounts, i.e. if current premiums turn out to be (more
than or) insufficient. Of course, as it does not seem advisable to make such adjustments
every time the actual expenses in a period even marginally differ from previous projections,
legislation in Germany requires expenses to be above or below a certain threshold in order
10 The rare case of risk lovers longing to forgo guarantees without any compensation from the annuity provider
seems quite absurd here, as such individuals might be inclined to refrain from buying insurance anyway.
11 See Brünjes (1990) for specific technical details regarding Germany and Timmer (1990) for a multi-country
comparison.
12 This is the case e.g. in the US where health insurance is mostly sold on an annual basis without premium
guarantees but typically with an option for the insured to annually renew the policy. For further details see
e.g. Black and Skipper (2000, p.140ff).
5
for premium adjustments to be permissible. Effectively, policyholders thus bear the risk of
systematic health care cost increases which the insurer may completely pass on, and in this
context it has also been named premium risk; see e.g. Kifmann (2000, 2002). It is also obvious
that the extent of premium increases or decreases highly depends on whether a certain trend
of health care cost development is already incorporated in the rate making process and how
much it is. On the other end, the scope for such decisions is also limited by the marketability
and competitiveness in the health insurance market.
Contrasting the challenge for annuity providers to manage or mitigate their exposure to
the systematic portion of longevity risk this concept of shifting back the systematic risk to
policyholders could also be transferred to annuity markets, and this notion will be further
discussed in the following.
2.4 Implementation Issues and Appraisal
Recurring to the other major alteration of conventional annuity design, i.e. investment-linked
products where part of the risk is shifted back to the policyholders, despite some similarities there are also some pronounced differences in comparison to annuities accounting for a
portfolio’s actual mortality experience that will be briefly pointed out.
While in the case of mortality-linked or health insurance products it is the insurance industry
that has a strong incentive to dispose itself of the highly correlated risks of health cost inflation
or – analogously – aggregate longevity (or brevity, i.e. shorter than expected lifetime, for that
matter) to avoid potential accumulative losses, this is less likely the case with investment-linked
products. Rather a general interest of policyholders in participating in higher capital market
returns may be the driving force here.
However, investment performance can hardly be influenced by policyholders, especially when
thinking of the general average individual and the extremely long terms which for immediate
life annuities may easily exceed 30 or 40 years. Thus moral hazard does not seem to play a
role in this case. On the other hand, in health insurance there is a great potential for such
unobservable policyholder behavior which must be thoroughly accounted for. The observable
increase of health care costs may in part be due to ex-post moral hazard arising from the
fact that policyholders once in need for (covered) medical procedures consume (motivated by
themselves; see Feldstein (1973, p.252)) or receive (through medical providers; see e.g. Feldstein
(1970, 1971))) more or more expensive treatments than they would without insurance coverage,
i.e. when paying out of their own pocket, which can be considered a quantity effect.13 But note
that in incomplete repair markets there is also a price effect due to a limited price elasticity,
and this contributes additionally towards increasing health care costs.
Fortunately, these effects would not be present in the case of (indexed) life annuities. In
particular, it is quite unlikely that policyholders have a possibility to intentionally expand their
respective individual lifetimes once insurance coverage is provided.
However, another type of asymmetric information is equally inherent to both health insurance and life annuities: In neither case does the insurer know as much about the health status
(or the “true” life expectancy) as the individual herself. In health insurance, it is thus common to use extensive questionnaires or even require medical examination reports prior to the
13 Nell et al. (2009) investigate the effect of insurance on “repair markets” which includes the demand for
“medical repairs”. Since it is impossible to write complete insurance contracts often rather actual expenses
are compensated for, and this has an effect on repair markets; see e.g. Feldstein (1970), Zweifel and Crivelli
(1996) or Pavcnik (2002).
6
contract acceptance, and the intention is to overcome this asymmetry and offer accordingly
discriminated premiums that account for the individual health status. In the annuities business, however, such premium discrimination is largely inexistent with few exceptions so far.14
Instead, premiums are calculated based on almost the “worst case”, i.e. assuming that insured
persons experience rather long lifetimes. Presuming that individuals have a relatively precise
understanding of what their individual life expectancy is (which could well be questioned)
those with a poorer than average health status are likely to be driven out of these markets.
Consequently, conventional products rather attract persons with higher life expectancies, and
eventually the portfolio of insured is entirely composed of individual risks representing the
poorest quality from the provider’s perspective.15 The extent to which such anti-selection
occurs in the annuity market might also be dependent on the characteristics of the annuity
contracts offered. In particular the fact whether immediate or deferred annuities at variable or
fixed annuitization conditions are offered or whether they include a lump-sum payout option
at some age(s) will have an influence on the degree of adverse selection.
While premium adjustments in the German private health insurance business are triggered
by the experience of a suitably confined portfolio of contracts it is up to the insurer to determine this partitioning, and for outside stakeholders in general or policyholders in particular
it may be difficult to retrace this decision. Furthermore, the credibility of actual cost experience from the policyholders’ point of view is at least limited unless industry cost figures are
drawn on. A similar consideration of course applies to the case of actual mortality experience
as a basis for indexed annuities. Unlike the question of what health care costs exactly are
to be considered, it seems hardly disputable how deaths are to be counted. However, the
maximum possible degree of objectivity and traceability can only be reached when the general
population mortality as published by a governmental statistics agency is the basis for further
considerations, or optionally an official actuarial authority, such as the Government Actuary’s
Department (GAD) in the UK, which inter alia is in charge of publishing life tables. Naturally,
the general population’s or insureds’ mortality is not necessarily identical to a specific annuity
provider’s experience. The opposite extreme would be to base any sort of adjustments on the
experience of an insurance company or even a specific portfolio, thus completely dispelling
basis risk at the cost of slightly more limited transparency.16 No general recommendation on
this particular issue can be made here but the trade-off between transparency and basis risk
has to be pondered in each case.
The bottom line of the above deliberations is that neither of the two presented cases exactly
represent the challenge of retransferring aggregate longevity risk in life annuities to the policyholders through redesign of conventional product features. However, both do, firstly, give
a strong example of successful changes to conventional products and, secondly, may serve as
a guideline for how actual losses or expenditure experience can be used for adjustments of
14 Impaired or enhanced annuities aim at providing higher benefits for individuals with a significantly poorer
health status upon sufficient proof by the policyholder. Schumacher (2008) further analyzes these products,
which seem to be established only in the UK annuity market but are not yet common elsewhere.
15 This is just the famous example of Akerlof’s “lemons” (Akerlof, 1970) where under asymmetric information
without remedies eventually only the worst quality in the market is traded.
16 In investment-linked annuities as briefly mentioned in Section 2.2, the general idea is to make the reserves
related to a specific funds’ development. If instead an overall stock index performance or other comprehensive
indicator is considered, regardless of how exactly these funds are invested, those contracts would rather be
denominated as equity-indexed annuities; see for instance Tiong (2000), Lee (2003), or Lin and Tan (2003).
7
premiums (or benefits, as will be the case here).
For annuities of the above-mentioned type that make benefits contingent on mortality experience the term mortality-indexed annuity (MIA) will be used throughout this paper. Surprisingly, such products do not seem to be offered yet by insurers in the most important insurance
markets nor visibly discussed in academia.17
Acknowledging that it may not be immediately desirable for policyholders not being able to
transfer their entire longevity risk exposure, it has to be kept in mind that the aggregate form
of longevity risk bears a great threat for insurers. Thus, the “solution” represented by the
proposed MIA could be a great step forward for annuity providers to get this highly correlated
risk under control. Such a means of risk avoidance (or reduction) might also foster sluggish
annuity markets, and eventually it may be better if insurers offer curtailed rather than none.
2.5 Proposed Product Features
As was suggested before, it remains to be decided how specifically an annuity provider can
reduce or eliminate aggregate longevity risk exposure from the contracts offered in the insurance
market. In the “plain vanilla” case of a single premium immediate annuity (SPIA) considered
in this paper there is no recurring premium that could be adjusted like in German health
insurance. Consequently the benefits are the remaining parameter, and in fact there is no
necessity for benefits to be constant or nominally fixed throughout the contract term nor in
any fashion pre-determined.18
The innovation proposed here is that at specified intervals the insurance company offering a
mortality-indexed annuity will adjust the benefits contingent on survival for remaining periods
in a way that reflects the difference of actual mortality experience from anticipated values since
the most recent adjustment date – keeping in mind the above mentioned trade-off between basis
risk for the insurer versus transparency in terms of the relevant underlying portfolio.19 Simply
speaking, if more than anticipated insureds are still alive, benefits have to be cut in order
to guarantee lifelong payments given the higher number of survivors. Alternatively a higher
number of deaths will lead to an increase of benefits for the survivors.
More frequent than annual revisions may be meticulous, but are likely to be too timeconsuming or complicated due to limited or lagged data availability and thus appear less
worthwhile. It is understood that statutory provisions may actually limit the choices for an
insurer, but referring again to the role model of German private health insurance, an annual
cycle seems both sensible and feasible if the specific portfolio serves as a reference point. As
insurers cannot predict future overall mortality tendencies either, it is further assumed that
readjustments of benefits should be made on the basis of a best estimate as per actuarial
practice and expertise. Again, regulators may determine specific methodologies or models to
be applied, and for the subsequent analysis one such provision based on the Lee-Carter model
17 A web search on both www.google.com and scholar.google.com in February 2009 did not yield any results for
the keywords mortality[-| ]indexed annuit[y|ies], and for the keywords indexed annuit[y|ies] none
were related to actual mortality experience.
18 This is to be understood from a pure actuarial perspective at this point. In reality it is likely that legal
and statutory requirements limit the possibility for variable annuity benefits. For instance, to qualify for
favorable tax deferral, (non-investment-linked) life annuity contracts in Germany may only offer constant or
increasing payments thus excluding decrements; cf. BMF-Schreiben, Decmeber 22, 2005 IVC1-S2252-343/05,
Rz 20.
19 For the sake of simplicity in the following it will be assumed that adjustments in MIA can be based on the
respective portfolio’s mortality experience without regulatory objection.
8
that was introduced above will be presented in Section 3.2.
3 Investigating Mortality-Indexed Annuities
3.1 Model Setup
The mortality-indexed annuity with the basic features proposed in Section 2.5 is to be further
analyzed here. Especially the question of whether from a policyholder’s perspective such
an innovation tends to be advantageous or not is not yet answered, while clearly annuity
providers should have a special interest in dispelling the aggregate longevity risk inherent to
conventional life annuities. By means of a Monte-Carlo simulation different developments of
actual, previously unknown mortality are investigated regarding their effect on the mortalityindex annuity proposed, i.e. a large number of scenarios is generated and results thus obtained
are further analyzed.
Assuming in a first step – as mentioned before – that the experience from the respective
insurer’s portfolio is drawn upon when making adjustments to the remaining survivors’ annuity
benefits (or face values) F Vt, a sufficiently large portfolio of identical annuity contracts is
considered with an initial size of lx at time t = 0. Insured persons in the considered pool are
assumed to be homogeneous in the sense of identical risk exposures and identical monetary
amounts stipulated in their contracts.20 This also includes an identical age x at t = 0 as well
as the same gender for all insured so that only a single cohort is considered. The contracts
are assumed to be sold to policyholders against a single upfront premium in the amount of π0,
which can also be considered the initial per-contract reserve V0, and this premium is considered
exogenously given throughout the entire analysis.
Given a best estimate of future mortality, the annual benefit F V0 is set at time t = 0 for the
remaining annuity term of T years using the equivalence formula21
π0 = V0 = F V0 · a¨
1
x:T
(3.1)
so that F V0 =
V0
a¨
1
x:T
=
π0
a¨
1
x:T
(3.2)
Here, a¨
1
x:T
is the actuarial present value of a T-year life annuity immediate22 as determined
using the mortality information and projections available at time t = 0 and assuming a constant
discrete interest rate of i per period (or year). Such a “pure” annuity pays a unit for as long
as a person initially aged x is alive, but not beyond his or her (x + T)-th birthday, i.e.
a¨
1
x:T
=
T
X−1
k=0
{kpx · v
k
} where v =
1
1 + i
(3.3)
20 For the purpose of profit sharing and attributing investment returns to individual contracts, German insurers
are required to split their entire portfolio into smaller groups of similar contracts (Abrechnungsverbände) in
order to reflect the different characters of e.g. pure life insurance versus life annuities.
21 The symbols in the formal expressions in this paper follow the International Actuarial Notation standard as
introduced in many actuarial text books; see e.g. Bowers et al. (1997).
22 An annuity immediate pays benefits in advance at the beginning of each period whereas an annuity due pays
in arrears at the end of each period – both contingent on the insured person still being alive at the beginning
of the respective year.
9
For each future point in time t the insurer will determine the respective per-contract reserve
Vt for the remaining survivors. Based on this information future annuity benefits F Vt are
determined – considered to be valid from time t on for the remainder of the contract term, i.e.
time T, unless further deviations from expected mortality developments occur.
Given that lx+t−1 insured were alive at the beginning of the previous year t − 1 the number
of survivors at time t is lx+t. The new per-contract reserve Vt for survivors is then determined
by considering what could be brought forward from the previous period, i.e. the previous year’s
reserve less the annuity payment at the beginning of the previous period – accrued at interest,
but also accounting for the redistribution of the reserves from those who passed away in the
meantime to those still alive. This can also be considered an inheritance effect or survivor
bonus.
23
More formally, at time t
lx+t−1 ·
Vt−1 − F Vt−1
v
= lx+t· Vt (3.4)
so that Vt =
lx+t−1
lx+t
·
Vt−1 − F Vt−1
v
=
Vt−1 − F Vt−1
v · lx+t/lx+t−1
=
(Vt−1 − F Vt−1) · (1 + i)
lx+t/lx+t−1
(3.5)
Note that all these computations are based entirely on already observable information since
at time t it should be known to the annuity provider how many insureds have survived and
how many were alive at the beginning of the previous period. At this point projections or
forecasts are not yet needed.
Given that the actual per-contract reserve Vtis determined, the new (adjusted) benefit F Vt
is set in a similar way as at time t = 0; see Equation (3.2):
Vt = F Vt· a¨
1
x+t:T −t
so that F Vt =
Vt
a¨
1
x+t:T −t
(3.6)
Of course a¨
1
x+t:T −t
is the updated actuarial present value of a (T −t)-year annuity immediate
for a person now aged x + t made at time t relying on a new best estimate at that time for
future mortality.
It is insightful at this point to consider a situation where initial mortality expectations are
correct and do not have to be revised, i.e. the longevity trend incorporated at the contract
inception exactly corresponds to the actual development of nature. Of course this case is the
absence of systematic risk. As mortality is not deterministic either, fluctuations of individuals’ mortality around the (correctly forecasted) general average still occur so that in this case
unsystematic risk is the only source of uncertainty. However, if we consider a theoretically
23 Ruß (2000) comments on different mechanisms how to combine death and survivor benefits in investmentlinked insurance products recurring to these effects as basic principles of insurance. In fact, the Law of Large
Numbers explicitly combines individual differences in mortality to guarantee a stable average value. See also
Blake et al. (2003).
10
infinite number of contracts in a portfolio, the Law of Large Numbers guarantees that individual fluctuations balance, and on average the insurer does not experience deviations from the
projected trend in the sense that actual relative frequencies of death almost exactly correspond
to the probabilities predicted by the model.24 In this special case, the evolution of reserves
as per Equation (3.5) exactly follows the initial calculation made in Equation (3.1), and at
every point in time the reserves brought forward from the preceding period Vt exactly match
the required funds for future payments in the (then constant) amount of F V0. Eventually, in
year T (or rather at the beginning of that year) no deficits nor excess reserves are due, which
effectively means that on an actuarial basis the insurer would not have any risk of losses.
However, as in reality portfolio sizes will always be finite numbers there is some uncertainty
with respect to the difference between relative frequencies and projected probabilities, and
even in the absence of systematic longevity risk (i.e. if projections are still perfect) the insurer
experiences deviations between the actual evolution of the portfolio reserves as per Equation
(3.5) and previous expectations so that adjustments of benefits would also be necessary. This
deliberation shows that in the proposed product at this stage, both the systematic and the
unsystematic longevity risk are shifted back to policyholders, and they are only able to insure the individual longevity risk in the sense that lifelong payments (or rather until age 100
contingent on survival) are guaranteed. However, benefits may be lower than initially expected.
It should also be emphasized here what has been a consistent assumption throughout the
above equations: All calculations and subsequent analyses are made on a net actuarial basis,
i.e. only the actuarial risk is taken into account. No surcharges or loadings to cover acquisition
expenses, no surplus accrual and thus distribution mechanisms, and no statutory or regulatory
requirements or restrictions in terms of reserving, investments, or product features are included
unless specifically mentioned.
Another major concern that is relevant for the present analysis is model uncertainty, and a
vital discussion of quite varying models to predict future mortality has been in the focus of
academia and industry for many years now. Yet no satisfactory solution could be identified as
the actual randomness of mortality seems to be too complex, and in addition trends and findings
thought to be well-fitting have occasionally turned out to be changing over time. However,
for the subsequent simulation of mortality a specific choice has to be made. In particular,
the PML extension of the Lee-Carter model (cf. Section 1) will be used for the reasons of its
widespread acceptance, the apparent robustness, and its relatively easy implementation. It is
well understood, though, that there are alternative choices and that certain shortcomings have
been discussed. Yet, the drawbacks and restrictions do not seem to outweigh the mentioned
advantages.
Naturally, the mentioned restrictions place a caveat on the entire analysis and thus obtained
results, as a far more complex reality will ultimately also influence results. This is especially
true for e.g. investment risk or potential basis risk that could be due to regulatory provisions
regarding admissible choices. However, further insight and a general direction regarding the
advantageousness of risk avoidance through offering mortality-indexed annuities is expected.
24 Again, note that model uncertainty is ignored here, assuming that the general type of stochasticity underlying
mortality developments is known.
11
3.2 Simulation of Mortality
To account for the true insurance character of an MIA where aggregate longevity risk is retransfered to policyholders (or not transfered to the insurer at all) its individual form is explicitly included in the simulation. That way not only does the general average mortality underly
random influences but also each individual’s lifetime. Put in different words, there is also risk
for each insured that his or her individual lifetime deviates from an initial expectation.
What can be considered a “background risk” here is the fluctuation of the overall mortality
pattern. More precisely, future mortality is assumed to develop according to the LC/PML
model. The vast majority of contributions have fitted the LC/PML model to actual data
determining an ARIMA(0,1,0) model as most suitable to describe the {κt} time series. This
effectively means that at any point in time t a linear extrapolation from the current level of
κtis the best estimate (denoted as κˆt),25 and it will also be met on average under the present
assumption.26
Of course, this is only true due to the fact that model uncertainty is excluded from the
present investigation which, instead, assumes that it is a priori known which model underlies
the random future mortality paths. Thus, there should not be any objections to basing best
estimates for the mortality index {κt} at future times t on the same drift initially determined
when calibrating the LC model.
When transferring the proposed product to real annuity markets an additional source of uncertainty may be the question of whether structural changes have occurred or will be occurring
to the mortality patterns applicable to the portfolio of contracts under consideration. While
especially the latter question could only be answered drawing upon epidemiological, medical,
or even philosophical input, the former challenge can be met relatively well with a reestimation
(or recalibration) of the LC model to both historical data as well as actual mortality experience
between times 0 and t. Thus, forecasts from time t on could be improved compared to just
a periodic update. In the present context this is not necessary due to the exclusion of model
uncertainty, though, and as it would also drastically increase the computational complexity, a
reestimation of model parameters is dismissed here.
However, the disturbance terms from the ARIMA model cause uncertainty about the actual realizations κ˜t
.
27 This can be interpreted in a way that at each point in time t nature
draws from the spectrum of possible mortality developments which in expected terms meets
the previous best estimates κˆt. More formally, it is assumed that at any future time t the
uncertainty can be expressed as κ˜t = ˆκt + ˜ηt with ηt ∼ N(0, σ2
κ
). Thus, the larger the time
horizon the larger the (accumulative) uncertainty about realizations κ˜t so that also uncertainty
accumulates the more distant future central death rates are.
25 Note that there is no distinction between a best estimate κˆt+1 made at time t for the year after next and κˆt+1
as a best estimate made at time t + 1 for the period just begun. However, from the context it should always
be clear at what time the respective estimate has been made so that a further distinction in the notation
appears dispensable.
26 For the remainder of the present contribution a tilde above a random variable symbol ˜· shall denote actual
realizations, whereas a hat symbol ˆ· is to indicate projections or forecasts of that random variable.
27 Hanewald et al. (2009) point out that it may be sufficient to concentrate on uncertainty arising from the
ARIMA process adapted to the {κt} time series while the majority of previous contributions have ignored
the error term εx,t in the original Lee-Carter model equation. They also note that Lee and Carter (1992,
Table B2) themselves noted that the former disturbance terms account for roughly 90% of standard errors
of age-specific death rate projections.
12
The individual form of uncertainty about a person’s lifetime is also incorporated into the
proposed product, and this is further commented below. Given an actually realized level of
general mortality as outlined before the result of surviving for another year (from time t to
t + 1) or passing away is the result of a Bernoulli “experiment”. The “population size” in
this experiment is identical to the number of survivors alive at time t, lx+t, and its “success”
probability is pˆx+t as determined by the overall (randomly sampled) mortality implied by κ˜t.
Put in different words, seen from time t the actual number of survivors ˜lx+t+1 at time t + 1
is a random sample from the binomial distribution Bin(lx+t, pˆx+t). However, pˆx+tin turn is
only a best estimate for the yet unknown realization of px+t which itself is subject to the
(immediate) draw of nature. The uncertainty about the actual number of survivors is even
stronger for more distant points in time t + k where also lx+t+k−1 is unknown and has to be
replaced by a best estimate ˆlx+t+k−1.
Note also that the uncertainty about realizations of {κt} accumulates over time in the
sense that more future values of κt are less predictable. This is due to the fact that at each
intermediate point in time i = 0, . . . , t nature “draws” realizations of the disturbance terms
ηi that all accumulate up to time t. Effectively, the distribution of κtis thus more dispersed
for longer time horizons t. As the adjustment mechanism proposed for the mortality-indexed
annuities leads to both higher and lower benefits F Vt at future times t since deviations from
the expected number of survivors in either direction can occur, the increasing dispersion of the
time index {κt} directly translates also into an increasing dispersion of future benefits paths
{F Vt}.
As pointed out above the present model assumes a random nature of mortality that is
twofold: neither the underlying general pattern is certain nor whether and to what extent
individual lifetimes deviate from the general levels. Obviously, by this choice both aggregate
and individual longevity are incorporated in the model. However, with the proposed possibility
for adjustments to {F Vt} at any time t based on the equivalence principle as per Equation
(3.6) and resorting to the best estimates at that time, the insurer offsets the risk that actual
mortality deviates from the projected (overall) trend. In this sense, the proposed mortalityindexed annuity is always balanced from the insurer’s perspective.
3.3 The Benchmark: Conventional Life Annuities
While annuity providers – as pointed out earlier – might generally be interested in the idea of
not having to bear the aggregate longevity risk in mortality-indexed annuities (MIA), it still
remains to be discussed how an assessment of the degree of advantageousness of these products
can be done. More precisely, the deduction of a suitable measure has not yet been clarified.
Acknowledging that MIA do not yet exist and that the starting point for considering such
innovation will necessarily be a conventional life annuity, it seems worthwhile to parallel the
key financial figures from MIA with those from conventional products when exposed to the
same mortality experience. In brief, a conventional annuity does not provide the possibility
for the provider to adjust benefits in any fashion since those will be set in fixed, nominal terms
at the contract inception following Equation (3.2). Thus, dependent on how actual mortality
within the portfolio under investigation realizes during the contract term the reserve at the
beginning of the T-th period (i.e. at time T − 1), denoted by V
∗,conv
T may turn out to be in- or
(over)sufficient and will thus result in either positive or negative values.28
28 If during the contract term the reserve Vt becomes negative, it is assumed here that such deficit can be
financed at the (unique) interest rate i that was applied for discounting, e.g. in Equation (3.3). See also
13
Conventional Annuities under Aggregate Longevity Risk
The exact distribution of final reserves V
∗,conv
T −1
in conventional annuities is not yet known since
it depends on the realized number of survivors in the portfolio of initially lx contracts, and
those numbers fluctuate around the initial best estimates similar to the time series {κt} as
discussed above. However, annuity benefits F V0 are determined as per Equation (3.2) in a
way that if actual mortality exactly follows the initial projection no surplus nor deficit in final
reserves is possible, i.e. the annuity benefits thus determined can be considered fair.29 The
fact that fluctuations around the best estimates are symmetric implies that losses (or profits)
in per-policy reserves at time T can be expected with roughly a 50% chance, and even though
it has to be kept in mind that this is seen from a (net) actuarial perspective it is obvious
that this observation also represents a major disadvantage for the annuity provider. Given the
fairness of the benefits it may be considered “fair” for the insurer to be exposed to the risk of
actuarial losses with a high probability, yet it is also quite likely that the insurer would not
want to accept such a high level of risk of insufficiently funded contracts and thus might aim
at reducing the exposure to a “safe” level. It is self-evident that complete safety in the sense
that no actuarial deficits in reserves are possible cannot be attained. However, it is reasonable
that the annuity provider in charge of offering the benchmarking conventional life annuities
would want to reduce the shortfall (or deficit) risk from roughly 50% substantially, and this
can most easily be achieved by incorporating a safety loading into the annuity calculation.
More precisely, annual benefits are reduced by a certain amount which in turn accumulates
to soothe the high shortfall probabilities to acceptable levels. To facilitate a true comparison
of MIA with conventional annuities, a specific exception from a net actuarial calculation must
therefore be made to reflect the insurer’s perspective as otherwise MIA would be compared to
a product which is likely to never exist. Of course, regulatory requirements may also limit the
range of actual choices in annuity markets, and this must be kept in mind.
In terms of the distribution of V
∗,conv
T
, a simple way to achieve a reduction of the shortfall risk
from roughly 50% to acceptable lower levels consists in a right-shift of the entire distribution,
and this can most easily be done by building up contingency funds ∆T that become available
at time T to increase the per-policy reserve that otherwise leads to deficits with almost 50%
probability. If the admissible (actuarial) shortfall probability for the annuity provider is denoted by α then the α-quantile is defined as zα,T = supz P(V
∗,conv
T < zα,T ) ≥ α. The effect of
subtracting this number zα,T (which for most choices of α will be a negative number) from
V
∗,conv
T
is illustrated by Figure 1. The same effect as subtracting the α-quantile from the perpolicy reserve can be obtained when adding the negative of that amount, i.e. use ∆α,T = −zα,T
to increase the reserves.
To build up the additional amount of ∆α,T required for the distributional right-shift indicated
above by the beginning of year T (or at time T −1), the insurer could charge a certain premium
surcharge or safety loading. As in the present case a single upfront premium is considered, this
can also be achieved by making an otherwise identical product more expensive, i.e. adjust the
benefits and thus reduce the initially determined face value F V0 to F V α
0
so that the additional
contingency funds ∆α,T is financed by the policyholder.30
further remarks on this thought below.
29 Given that the upfront premium π0 is considered fixed, the usual notion of an actuarially fair premium cannot
be applied.
30 As implied by the notation this is of course subject to the admissible likelihood of actuarial losses α chosen
to determine ∆α,T .
14
Figure 1: Right-Shift of Illustrative Density Function by Subtracting Quantile
(a) original
 5000 0 5000 10000
0.00000 0.00005 0.00010 0.00015 0.00020 0.00025
z_0.01
(b) after right-shift
 5000 0 5000 10000
0.00000 0.00005 0.00010 0.00015 0.00020 0.00025
z_0.01
Source: authors’ calculation.
The plots show the empricial density function for 10,000 random samples from a hypothetical
N (0, σ2 = 4,000,000) distribution (a) without further changes and (b) after subtracting the 0.01-quantile z0.01.
The adjusted benefit F V α
0 < F V0 (not adjusted to actual mortality experience like F Vt
in
MIA) can be considered basically the original benefit F V0 determined by Equation (3.2), but
from each payment a certain fixed amount is deducted. This deduction in turn can be considered a recurring premium the insurer charges or retains to finance the ultimate contingency
funds. Or, put differently, the insurer only sells conventional life annuities if at the same time
an insurance savings scheme towards an ultimate financial cushion is embedded in the contract.
The above considerations can be expressed more formally as
π0 =
T
X−1
k=0
{F V0 · kpˆx · v
k
}
= F V0 · a¨
1
x:T
see Eq. (3.1)
=
T
X−1
k=0
{F V α
0
· kpˆx · v
k
} + ∆α,T · v
T −1
T −1pˆx
= F V α
0
· a¨
1
x:T
+ ∆α,T · T −1Ex (3.7)
In the last expression of (3.7), T −1Ex is a T − 1-year pure (unit) endowment insurance for
a person aged x.
31 By comparing Equations (3.1) and (3.7) the adjusted face value F V α
0
can
be determined from the non-adjusted value F V0 through
F V0 · a¨
1
x:T
= F V α
0
· a¨
1
x:T
+ ∆α,T · T −1Ex (3.8)
so that F V α
0 =
F V0 · a¨
1
x:T
− ∆α,T · T −1Ex
a¨
1
x:T
= F V0 −
∆α,T · T −1Ex
a¨
1
x:T
= F V0 − ∆α,T · s¨
1
x:T
(3.9)
31 Note that the last annuity payments are due at time T − 1 so that it is sufficient to analyze the provider’s
financial situation at that time.
15
where s¨
1
x:T
is the actuarial accumulated value at time T contingent on survival that corresponds to the same unit annuity underlying the actuarial present value a¨
1
x:T
.
At this point the question may arise of whether one should also consider the per-policy reserves Vt at any intermediate time t since obviously an insurer offering conventional annuities
would neither be willing to accept actuarial net losses at those points in time. For an answer, two important features of the comparable conventional annuities underlying the present
investigation have to be kept in mind.
Firstly, if for any actual mortality development the reserve is negative at some intermediate
point in time, it was assumed that the annuity provider may finance this shortfall at the
same fixed interest rate i that was assumed as the minimum guaranteed interest rate; cf. also
Footnote 28. Although external funds raised on capital markets will mostly not be available
at such a low rate, this notion appears more realistic when considering the possibility that
such shortfall may be financed by borrowing against some other line of business or portfolio of
contracts within the insurance company. Also note that due to the inheritance effect32 negative
reserves may become positive thus settling the deficit – although this is not necessarily the
case. As a last remark on this note that reserve values analyzed are entirely based on a net
actuarial assessment, i.e. except for the safety loading discussed above they do not include any
further loadings or surcharges, and the excess investment yields are also not accounted for at
this point so that in reality it is likely that actual per-policy reserves are higher in tendency
and deficits less likely and less severe.
Secondly, and more importantly, it may be hard (if not impossible) to answer the question
whether the safety loading as determined per Equations (3.7) and (3.9) is also sufficient to
avoid shortfalls at intermediate points in time 0 < t < T − 1 or whether the respective
shortfall probabilities P (V
α
t < 0) can thus be reduced to levels well below α. The reason is
that, on the one hand, per-policy reserves are reduced over time by the annuity payments due
to surviving policyholders whereas on the other hand they are accrued at interest and the
additional “survivor bonus”.
Thus, another way of asserting the adequacy of the safety loading as per the above equations
is possible by analyzing the evolution of the α-quantiles of the per-policy reserves V
∗,conv
t
, i.e.
{zα,t}t=0,...,T . If those are decreasing in t, i.e. if the lowest value is given by zα,T or, likewise,
the highest contingency funds value is represented by ∆α,T , then it is sufficient to use the
safety loading as determined above. Simply speaking, if the worst cases (in the relevant are of
the quantiles under investigation) are to be expected at the end of the period, it is sufficient
to buffer the potential downside risk at this point as thus intermediate shortfalls are also accounted for. For the analysis provided in Chapter 4 the required monotonicity of {zα,t}t=0,...,T is
fulfilled in all treatments (cf. Table 2), justifying to rely on the safety loading established above.
Another issue that has not been further discussed so far is the fact that on average there
is no actuarial profit or loss with the unadjusted F V0. By including the safety loading, the
additional contingency funds ∆α,T per surviving policyholder accumulated over the contract
period further improves the financial situation with a small effective net deficit risk of only
α. The resulting considerable expected profits for the conventional annuities that serve as a
benchmark for the proposed MIA arise entirely from mortality fluctuations, as it is assumed
here that the insurer does not generate higher investment yields than the constant interest rate
32 See the remarks in Footnote 23 on the “extra” survivor bonus in life annuities.
16
i, at which the per-policy reserves are carried forward following the equivalence principle; cf.
Equation 3.5.33 For an adaptation of the proposed MIA and the benchmark products into real
insurance markets it remains to be further discussed whether and how such expected profits
would have to be accounted for and how this might change results presented below. It is also
immediately obvious that actual insurers’ possibilities and admissible procedures for profit
sharing mechanisms that are common to a particular market highly depend on regulatory
requirements.34 In tendency, profit-sharing of “mortality gains” should improve the position
of conventional products in comparison to mortality-indexed annuities as those adjust benefits
in a way that completely incorporates mortality gains and leaves no surplus due to mortality
fluctuations to be redistributed.35 For the present investigation, however, the details of profitsharing will not be further investigated.
Comparing Mortality-Indexed Annuities and Conventional Annuities
It is more than obvious that a MIA would be (dis-)advantageous compared to a conventional life
annuity exactly when it provides higher (lower) benefits at any given future time. However, due
to the fluctuations of mortality (and consequently also of adjusted benefits F Vt) it is not clear
how often and to what extent the benefits are higher than F V α
0
in a comparable conventional
annuity – provided that the latter includes contingency funds as discussed above. Note that
with certainty F V0 > F V α
0 but that no definite statements are possible as to F Vt for future
points in time. The standard assumption of risk-averse policyholders is ignored in this context.
In a further analysis the fact that risk-averse individuals being reluctant to not transfer the
aggregate longevity risk could also be incorporated when determining to what extent MIA are
advantageous compared to conventional products. In tendency, the excess of MIA benefits F Vt
over F V α
0
is diminished by the increase in risk to be born by the policyholder. Overall effects
are thus likely to be highly dependent on the degree of individual risk aversion.
What also needs to be kept in mind is the fact that for most policyholders sooner benefits
in excess of “conventional” benefits should have a stronger weight than those in the more
distant future. Discounting should reflect such time preferences and also it is less likely for
each insured to actually live to see such late excess benefits, requiring “mortality discounting”
as incorporated in the concept of actuarial present values; cf. Equation (3.3).
Following the overall principles governing actuarial calculation in life and pension insurance,
it thus seems worthwhile to further analyze the actuarial present value of the difference in
benefits of MIA compared to conventional annuities as seen from time t = 0. One should
expect that if the fluctuations of adjusted benefits {F Vt} do not turn out to be overly downward
drifting below the level of F V α
0
and/or if this only occurs in the more distant future, then the
initially higher level of F V0 in comparison to F V α
0
combined with a higher likelihood for
33 Only recently German legislation has set off the surplus generated by “mortality (or risk) gains” and “cost
gains”. In contrast to “investment gains” on policy reserves, of which at least 90% have long been required
to be credited to policyholders, of the two last-mentioned items now at least 75% and 50%, respectively, are
require to be attributed to individual policies. Cf. also the remarks on regulatory provisions regarding profit
sharing in Germany in Footnote 7 on p.4.
34 While from a pure shareholder value perspective it would be straightforward to retain all surplus generated
from deviating mortality, investment yield, or cost development, actual limitations placed on the insurance
industry by regulatory specifications are generally intended to protect policyholders’ interests. An abundant
selection of previous contributions have discussed or analyzed profit-sharing, and for the specific case of
Germany cf. e.g. Schwintowski and Ebers (2002), Ebers (2001), or Gruschinske (1989).
35 This is achieved by the term lx+t/lx+t−1 in Equation (3.5).
17
each insured to actually receive those benefits at all and sooner are likely to prevail. As a
direct consequence the mentioned “actuarial present value of MIA excess benefits” will become
positive, thus being in line with the notion of a measure of advantageousness. Technically, for
each scenario in the Monte-Carlo simulation the amount
ADV α
MIA =
T
X−1
k=0
{(F Vk − F V α
0
) · kp˜x · v
k
}
=
T
X−1
k=0
{(F Vk − F V α
0
) ·
˜lx+k/˜lx · v
k
} (3.10)
is computed where actual survival rates kp˜x = ˜lx+k/
˜lx are used. The thus obtained empirical
distribution of ADV α
MIA will be further analyzed next.
4 Simulation and Results
4.1 Data and Parameterization
To perform the simulation of key financial figures (and especially the measure for advantageousness ADV α
MIA developed in Section 3.3) for the mortality-indexed annuities proposed in
Section 2.5 several particular choices in terms of data and parameterizations have to be made.
Those will be detailed and motivated in the present section.
Firstly, since the simulation intends to investigate variations in the mortality (or longevity)
within a stylized homogeneous portfolio of insured and the respective implications for the
adjustments of MIA benefits, it is self-evident that the selection effect of (generally lower)
annuitant mortality versus the general population mortality should be accounted for. Thus
due to the limited availability of such annuitant mortality data the present simulation resorts
to the UK data set provided by the CMI.36 This ultimately led to the LC time index {κt}
being modeled as an ARIMA(0,1,0) time series, thus being in line with previous research.
Secondly, since there are more male annuitants than females in the mentioned data set it will
be assumed that the homogeneous cohort under investigation is composed of males exclusively.
A limited number of years covered by the data also forces to base the calibration (or parameter
estimation) of the LC/PML model on calendar years z = 1983, . . . , 2003, and consequently all
projections begin in year z = 2004 which corresponds to time t = 0. Although for calibration
purposes only ages x = 25, . . . , 110 could be considered, the cohort’s initial age is assumed to
be x = 60 at time t = 0, and the annuity term here is limited to T = 41 at the outset. Thus,
the last annuity payment is due at the beginning of the year z = 2044 (or at time t = 40,
equivalently) where all surviving cohort members have just completed their 100th birthday with
no further payments thereafter. However, ultimate financial data such as per-policy reserves
can also be considered in the “second” after the last annuity payments at time T − 1 since no
further cash flows are to occur for the remainder of the T-th year. This is simply owed to the
fact that an annuity immediate was assumed here, which makes payments in advance.
36 The Continuous Mortality Investigation (CMI) is an institution sponsored by the Faculty of Institute of
Actuaries in the UK in charge of fostering research related to mortality modeling issues. Data provided
encompasses annuitant mortality data per capita from the British insurance industry.
18
Lastly, the upfront premium considered to be exogenously given37 is set as π0 = 100,000,
and the number of generated scenarios in the Monte-Carlo simulation is set to N = 10,000
throughout the subsequent analyses.38
The above outlined parameterization choices are summarized in Table 1.
Table 1: Parameterization for the Simulation of MIA Advantageousness
number of scenarios initial age annuity term upfront single premium
N x T π0
10,000 60 41 100,000
Two parameterization choices have not yet been further discussed. For the size of the fictitious portfolio, i.e. the initial number of insured, two different choices are considered: On the
one hand, to reflect comfortable diversification effects a relatively large (given the assumed
homogeneity) portfolio is assumed by setting l60 = 100,000. On the other hand, individual
fluctuations of lifetime are modeled as Bernoulli experiments with the actual number of survivors being random samples from suitably parameterized distribution. Given the Law of
Large Numbers, which states that sample means will converge to the theoretical “true” mean
of the underlying distribution upon increasing sample sizes, it is likely that thus randomly
sampled number of survivors will be relatively close to the respective overall survival probabilities “drawn by nature”. To challenge individual fluctuations to a larger extent and also
accounting for the fact that in reality (primary) insurers may only be able to compose smaller
homogeneous annuity portfolios, an alternative portfolio size of l60 = 1,000 is also considered.
For the constant interest rate i incorporated into the calculation of actuarial present values
a¨
1
x:T
and discounting purposes also two different assumptions were made. Note that the present
analysis is made from a net actuarial standpoint where actual (excess) yields on the invested
reserves are disregarded. As discussed above, an adequate mechanism for redistribution of
surplus must be thoroughly considered. However, a quite conservative yet commonly found
value of i = 3% p.a. is assumed as well as the more ambitious choice of i = 5% p.a. In the long
run, with the use of long-term governmental bonds insurers in many countries have been able
to generate returns on their investments well above the former choice with little difficulties to
attain the latter level.39
Table 2 provides an overview of the portfolio size and interest rate combinations including
the abbreviations for the resulting “treatments” referred to below.
For the admissible shortfall risk α values of 0.01, 0.005, and 0.001 are used to reflect reasonable choices not uncommon in the industry. If necessary for distinction, the specific values
37 To illustrate the notion of a fixed upfront premium in the amount of π0 it may be helpful to consider a
pre-existing individual savings plan, a term life insurance ending exactly at the annuity inception date, or an
inheritance made. In either case proceeds from these financial instruments become available at time t = 0
exactly in the amount of π0. An additional assumption could be that the annuity provider cannot ask the
policyholder to pay an increased upfront premium in order to allow the establishment of contingency funds,
but accordingly needs to make adjustments to the initial annuity face value, i.e. provide only F V α
0 instead
of F V0.
38 A precise notation would require to add a symbol j to all formula symbols introduced in this contribution
to denote that they differ by scenario. For the sake of clarity, such notation has been ignored so far and will
only be used below if explicitly necessary.
39 See also Kling et al. (2007) for a thorough analysis of the effects on risk exposure that different regimes of
surplus distribution as related to investment yields being in excess of interest rate guarantees.
19
Table 2: Treatments for the Simulation of MIA Advantageousness
i
3% 5%
l60
100,000 AI AII (base case)
1,000 BI BII
will be added as a left superscript, e.g. as ADV 0.001
MIA .
4.2 Results and Discussion
When applying the parameterization and underlying data outlined in Section 4.1 to the MonteCarlo simulation model introduced in Section 3.1, the data being computed is extensive: Four
treatments with N = 10,000 scenarios each were run, and in each run j a series of MIA face
values {F V j
t
}t=0...40 was generated,40 contingent on three different levels of α – among other
interim data necessary to actually compute the MIA developments.
Figure 2: Paths of MIA Benefits in Comparison to Conventional Annuity – Treatment AI ,
α = 0.005
6000
6500
7000
non-adjusted benefits [with safety loadings 0.005]
4500
5000
5500
6000
time 
FV (0,adj.)=5448
FV (0)=5632
Source: authors’ calculation, based on data provided by the CMI.
The dotted line indicates the face value F V0 = 5,632 prior to contingency funds inclusion; the dashed line
shows F V 0.005
0 = 5,448 (“FV(0,adj.)”) for a comparable conventional annuity.
For instance, for the base case treatment using α = 0.005 Figure 2 depicts the spectrum
of MIA benefit paths as well as those obtained from a comparable “conventional” life annuity
– both with and without contingency funds.41 Obviously, it is next to impossible to directly
40 Note that no payments are due after time T − 1 so that no value of F V41 needs to be determined.
41 It is obvious and also evident from Figure 2 that for the latter case, benefits from the conventional product
coincide with the initial MIA benefit that is determined for the very first period (and later revised), as at
time t = 0 the respective best estimates coincide as well.
20
assess this amount of data. While at first glance it may seem that paths tend to fall below the
“conventional” benefit level (dashed, lower horizontal line) quickly,42 it has also to be kept in
mind what was mentioned above in the context of deducing the measure for advantageousness:
benefits below that threshold in the not-so-near future can be assumed to be less grave due
to discounting and mortality in the meantime. In addition, note that an annuity pays (accumulative) benefits at all times contingent on survival, i.e. rather the sum of excess or deficit
benefits (or the area between each MIA path and the constant of F V α
0
) is a relevant quantity.
As the interest and “survival” discounting cannot easily be captured when using visualizations similar to Figure 2, those provide less insight into MIA advantageousness. Instead, MIA
face values are boiled down to realizations of ADV α
MIA as an aggregate measure including the
twofold discount of interest and mortality, which effectively leaves 120,000 values for further
analysis. The remaining complexity of the results can suitably be depicted by using histograms
of the empirical distribution of ADV α
MIA, such as Figure 3 for different levels of α in the base
case treatment AI or Figures 4, 5, and 6 for analogous representations for the other treatments
AII , BI , and BII , respectively. Further analysis of the distributions of ADV α
MIA may work towards an answer to whether the apparent attractiveness of MIA for insurers also applies to
potential policyholders.43
Treatment AI – the base case
For the base case treatment AI , the innovative mortality-indexed annuity turns out to be
considerably more advantageous than a conventional annuity in the majority of cases; see
Figure 3. In fact, the MIA provides an average level of ADV α
MIA of between roughly 3,100 and
3,700 – depending on α. Given that F V0 is 5,632, these values correspond to 55% to 65% of an
annual benefit payment. For treatment AI , these values (among a selection of risk measures)
are listed in Table 3 separated by the insurer’s shortfall risk α. What can also be observed is
the fact that the downside or shortfall risk P [ADV α
MIA < 0] is in the area of only 2 − 5% so
that it is rather unlikely that the innovative product is truly disadvantageous as measured by
ADV α
MIA. Obviously, the smaller α, i.e. the smaller the insurer’s admissible actuarial shortfall
risk when including contingency funds, the more advantageous are potential MIA benefits.
This is simply due to the fact that a higher α requires F V α
0
to be lower, ceteris paribus, in
order for ∆α,T to be available by time T.
Another more general measure for the riskiness would be the variability of the (degree of)
advantageousness. Figure 3 provides little evidence of whether the increase in downside risk
P [ADV α
MIA < 0] (when gradually increasing α from 0.001 to 0.005 and 0.010; cf. Figures 3(a),
(b) and (c)) is only due to a shift of the respective density functions, or whether also a higher
dispersion has its share. The empirical variances are therefore also listed in Table 3, and apart
from the fact that the actual differences in relative terms are quite small compared to their
high levels, a slight increase of the variability can still be observed. However, the much stronger
reduction of empirical means suggests that the former explanation is the dominant cause.
Although it turns out that advantageous scenarios are very likely with the policyholders’ downside risk being rather limited, it is interesting to further analyze also how negative potential adverse scenarios may turn out to be. For this purpose, also the expected
42 In fact, roughly half of values F V40 are lower than the initial value F V0 and roughly one third even below
the (comparable) level of F V 0.005
MIA .
43 Recall that ADV α
MIA was developed as a measure for the advantageousness of MIA in comparison to conventional life annuities if only the insurer needs to include a safety loading or build up contingency funds to
reduce the actuarial shortfall risk to α.
21
Figure 3: Empirical Distribution of ADV α
MIA – Treatment AI
(a) α = 0.001
F V α
0 = 5,426.77
f
−5000 0 5000 10000
0.00000 0.00005 0.00010 0.00015 0.00020 0.00025
(b) α = 0.005
F V α
0 = 5,447.78
f
−5000 0 5000 10000
0.00000 0.00005 0.00010 0.00015 0.00020 0.00025
(c) α = 0.010
F V α
0 = 5,456.95
f
−5000 0 5000 10000
0.00000 0.00005 0.00010 0.00015 0.00020 0.00025
Source: authors’ calculation, based on data provided by the CMI.
[policyholder] shortfall (or rather “expected MIA disadvantageousness”) is computed, i.e.
E [ADV α
MIA | ADV αMIA < 0]. Those values provide an idea of how severe waiving a transfer
of aggregate longevity risk to an annuity provider may be, and the respective quantities are
also provided in Table 3. It is not surprising then that with a higher α (and thus also higher
values of F V α
0
) the general level of ADV α
MIA is lower, and consequently also expected shortfalls
take on more negative values.
Table 3: Key Figures from Treatment AI
Annuity Benefits α = 0.001 α = 0.005 α = 0.010
F V0 5,631.67
F V α
0
5,426.77 5,447.78 5,456.95
Risk Measure
E [ADV α
MIA] 3,700.17 3,327.33 3,164.66
P [ADV α
MIA < 0] 2.34% 3.90% 4.64%
Var[ADV α
MIA] 3,650,434 3,678,755 3,691,146
E [ADV α
MIA | ADV α
MIA < 0] −646.16 −692.67 −737.81
Source: authors’ calculation, based on data provided by the CMI.
Of course the above mentioned downside risk directly leads to the question of how the
insurer’s remaining (actuarial) shortfall risk α compares to the extent of aggregate longevity
risk that is transferred back to the policyholders in MIA, and from the discussed values it is clear
that those two measures for the uncertainty do not coincide at all. Effectively, the downside
risk is much larger in MIA, where the policyholders are at risk, compared to conventional
annuities where it is the insurer’s liability to cover potential deficits in per-policy reserves.
However, through the assumed contingency funds this risk reduced to the minimum desired
level.44
44 The comparatively large portfolio size of initially l60 = 100,000 in treatments AI and AII rather plays in favor
of the insurer as well, since relative frequencies or proportions (of e.g. survivors) are then not too deviant
from theoretical probabilities, effectively also working towards a risk reduction.
22
A further question that is related to the imbalance of risk bearing is the issue of marketability.
More precisely, assuming that the insurer does not intend to (or, for reasons of competitiveness,
may not) conceal the downside potential in MIA contracts, it is at least questionable how
well it would be received by insurees. Naturally, an immediate attractive counterargument
can be brought forward: the (non-reduced) annuity benefit F V0 that can be provided when
policyholders agree to bear aggregate longevity risk is initially higher than the comparable
value of F V α
0
.
It must thus remain an open question at this point whether a skilled marketing is able to
place innovative MIA contracts with interested persons. However, it is beyond the scope of
this contribution to further analyze individuals’ risk perception, assessment, or willingness to
bear longevity risk.
Treatment AII
When transiting to treatment AII , i.e. incorporating a higher interest rate of i = 5%, a very
general first observation is that the graphical representations in Figure 4 do not drastically
differ from those of treatment AI . However, on closer inspection it is also evident that the
respective distributions of ADV α
MIA are shifted slightly further to the left. This is probably
less revealed by Figure 4 but more so by the respective risk measures provided in Table 4.
Figure 4: Empirical Distribution of ADV α
MIA – Treatment AII
(a) α = 0.001
F V α
0 = 6,814.29
f
−5000 0 5000 10000
0.00000 0.00005 0.00010 0.00015 0.00020 0.00025
(b) α = 0.005
F V α
0 = 6,829.79
f
−5000 0 5000 10000
0.00000 0.00005 0.00010 0.00015 0.00020 0.00025
(c) α = 0.010
F V α
0 = 6,838.79
f
−5000 0 5000 10000
0.00000 0.00005 0.00010 0.00015 0.00020 0.00025
Source: authors’ calculation, based on data provided by the CMI.
In particular, the empirical means are significantly reduced by roughly 1,150 − 1,350 compared to treatment AI to levels of between 2,000 and 2,400 (see Table 4), and the “shortfall”
probability, i.e. the frequency of disadvantageous MIA benefit paths, is almost twice of what
it was before. Contrarily, the expected shortfalls are smaller (in absolute terms), and these
observations demand some further commenting.
Firstly, a higher interest rate primarily has an influence on the actuarial present values
a¨
1
x:T
which are lower compared to the case of i = 3% due to the stronger discounting; see
Equation (3.3). When inspecting Equation (3.2), this obviously results in a higher level of
F V0 given that the upfront premium remains unchanged.45 Similarly, in Equation (3.6) the
higher interest rate results in higher annuity benefits F Vt as the updated actuarial present
values a¨
1
x+t:T −t
are also increased. However, the effect on Equation (3.5) is ambiguous. For
45 Compare the remarks on this assumption in Footnote 37 on p.19.
23
the case of t = 1, a higher value of i obviously yields a higher value of V1,
46 but for times t > 1
both Vt−1 and F Vt−1 are higher compared to the base case so that a general statement on the
evolution of per-policy reserves Vtis not possible. Naturally, the claimed effect on Equation
(3.6) is rendered ambiguous.
For the benchmarking conventional annuity, rearranging Equation (3.7) and taking into
account that both a¨
1
x:T
and T −1Ex are lower under a higher i suggests that F V α
0 must be
higher as again the upfront single premium π0 is considered fixed, but this is also contingent
on a constant value of ∆α,T .
The described theoretically motivated effects on both F V0 and F V α
0
can also clearly be
identified in the first lines of Table 4 in comparison to the respective values in Table 3. However,
the difference between F V0 and F V α
0
is lower now; for instance, in the case of α = 0.001 it
is now only 160 instead of 205 units compared to treatment AI . Therefore, a higher interest
rate i seems to work in favor of the conventional annuity, where only a lower initial benefit
adjustment from F V0 to F V α
0
is necessary to incorporate the safety loading that accumulates
to the desired contingency funds and thus reduces the insurer’s shortfall risk to a given level of
α. Yet the (initial) levels of benefits for both the innovative MIA and the conventional product
are considerably higher under a higher interest rate i.
Secondly, as the proposed measure of advantageousness, ADV α
MIA, is based on the actuarial
present value of the difference between MIA benefits evolution and the comparable conventional
benefits F V α
0
, Equation (3.10) reveals that discounting with the fixed interest rate i has an
important effect. Obviously, when increasing i from 3% to 5% the stronger discounting through
a lower v causes ADV α
MIA to be lower ceteris paribus. On the other hand, as pointed out above,
the (initially) lower difference between F V0 and F V α
0 has an adverse effect. However, as is
evident from Figure 2, negative (and positive) differences between F Vt and F V α
0
are rather to
be expected in the long run, and such later deficit (or excess) benefits for the MIA product tend
to be stronger the longer the time horizon is. Even though negative differences are weighed less
now, the enormous upside potential for strongly positive realizations of ADV α
MIA is compressed
by stronger discounting, and as lower levels of e.g. E [ADV α
MIA] in Table 4 compared to the
base case show, the latter effect obviously prevails.
Table 4: Key Figures from Treatment AII
Annuity Benefits α = 0.001 α = 0.005 α = 0.010
F V0 6,975.56
F V α
0
6,814.29 6,829.79 6,838.79
Risk Measure
E [ADV α
MIA] 2,366.11 2,143.97 2,015.09
P [ADV α
MIA < 0] 5.62% 7.50% 8.91%
Var[ADV α
MIA] 2,354,463 2,365,189 2,371,423
E [ADV α
MIA | ADV αMIA < 0] −601.69 −649.60 −667.88
Source: authors’ calculation, based on data provided by the CMI.
A stronger discounting in the case of i = 5% also causes such negative differences to have
a lower impact on the advantageousness of MIA. i.e. deficits (and excesses, likewise) are far
46 Recall that the initial reserve is identical to the upfront single premium, i.e. V0 = π0.
24
more attenuated aas already mentioned, and the obvious consequence for treatment AII in
comparison to the base case can also be observed from Table 4 versus Table 3: the empirical
variances are less than two thirds of what they had been before. Interestingly, the expected
shortfalls are (in absolute terms) slightly smaller now, which can be interpreted in such a way
that if the MIA is disadvantageous the extent is less harmful, and in the view of the general
left-shift of the distributions of ADV α
MIA compared to the base case, this observation is in
perfect accordance with the notably smaller variances.
Treatments BI and BII
If the much smaller portfolios from treatments BI and BII with only l60 = 1,000 are considered,
the above findings still apply accordingly. More precisely, the higher interest rate of 5% in
treatment BII versus a moderate 3% in treatment BI has an overall effect that is similar to
the above comparison of AI and AII : The initial annuity benefits F V0 and F V α
0
are higher for
the higher interest rate (with the reduction in the differences of F V0 and F V α
0 being 200 instead
of 240), the shortfall frequency is roughly doubled and the empirical means are significantly
lower under higher interest rates, which again is the immediate consequence of a left-shift of
the distributions of ADV α
MIA, of course contingent on α. This difference can also be identified
in the diagrams in Figure 6 versus those in Figure 5, and Tables 5 and 6 give the relevant
key figures. Similar to the previous cases of treatments AI and AII , the distributions under a
higher interest rate are also more compressed, which is evident from a reduction of the variances
by roughly one third and likewise less negative expected shortfalls (or “expected policyholder
disadvantageousness” of MIA). Thus, a higher interest rate works in exactly the same fashion
here – despite the lower number of contracts in the underlying portfolios of insured so that
one conclusion is that results are much more sensitive to discounting than they are to different
portfolio sizes.
Figure 5: Empirical Distribution of ADV α
MIA – Treatment BI
(a) α = 0.001
F V α
0 = 5,391.62
f
−5000 0 5000 10000
0.00000 0.00005 0.00010 0.00015 0.00020 0.00025
(b) α = 0.005
F V α
0 = 5,417.04
f
−5000 0 5000 10000
0.00000 0.00005 0.00010 0.00015 0.00020 0.00025
(c) α = 0.010
F V α
0 = 5,431.19
f
−5000 0 5000 10000
0.00000 0.00005 0.00010 0.00015 0.00020 0.00025
Source: authors’ calculation, based on data provided by the CMI.
However, another observation is the overall difference of the results under treatments BI and
BII compared to those in the case of larger annuity portfolios. Obviously, the fact that the
Law of Large Numbers works less well here causes stronger deviations of the actual number
of survivors from the initial best estimates. Accumulating over time, these deviations cause
a more dispersed distribution of per-policy reserves for the conventional product used as a
benchmark. In turn, to reduce deficit reserves here and make the benchmark comparable, the
25
Table 5: Key Figures from Treatment BI
Annuity Benefits α = 0.001 α = 0.005 α = 0.010
F V0 5,631.67
F V α
0
5,391.62 5,417.04 5,431.19
Risk Measure
E [ADV α
MIA] 4,326.52 3,875.51 3,624.41
P [ADV α
MIA < 0] 2.02% 3.40% 4.40%
Var[ADV α
MIA] 4,550,639 4,593,644 4,617,675
E [ADV α
MIA | ADV α
MIA < 0] −728.69 −805.33 −855.19
Source: authors’ calculation, based on data provided by the CMI.
contingency funds need to be increased compared to the case of the larger portfolios discussed
before. In turn, conventional annuities deliver benefits that are smaller in the “B” treatments
when compared to the respective numbers from the “A” treatments. This is evident from
the values for F V α
0
in Tables 5 and 6, respectively. Thus, in Equation (3.10) the differences
between F Vt and F V α
0
tend to be larger ceteris paribus, and this immediately leads to values
of ADV α
MIA that are generally higher. In short: the “B” distributions are shifted to the right,
which is also evident e.g. from the higher empirical means or lower shortfall probabilities in
Tables 5 and6 when compared to Tables 3 and4, respectively. Interestingly, the dispersions in
treatments with smaller portfolios are roughly 1.25 − 1.27 times what they had been before,
and as a direct consequence expected “shortfalls” take on more negative values. In short:
disadvantageous scenarios are less likely here, and the overall prospect for benefits under MIA
are considerably better for smaller portfolios. However, if negative developments occur they
are more severe than in the case of larger annuity portfolios.
Figure 6: Empirical Distribution of ADV α
MIA – Treatment BII
(a) α = 0.001
F V α
0 = 6,777.00
f
−5000 0 5000 10000
0.00000 0.00005 0.00010 0.00015 0.00020 0.00025
(b) α = 0.005
F V α
0 = 6,803.44
f
−5000 0 5000 10000
0.00000 0.00005 0.00010 0.00015 0.00020 0.00025
(c) α = 0.010
F V α
0 = 6,814.68
f
−5000 0 5000 10000
0.00000 0.00005 0.00010 0.00015 0.00020 0.00025
Source: authors’ calculation, based on data provided by the CMI.
26
Table 6: Key Figures from Treatment BII
Annuity Benefits α = 0.001 α = 0.005 α = 0.010
F V0 6,975.56
F V α
0
6,777.00 6,803.44 6,814.68
Risk Measure
E [ADV α
MIA] 2,891.20 2,527.11 2,366.09
P [ADV α
MIA < 0] 4.44% 7.04% 8.35%
Var[ADV α
MIA] 2,994,518 3,007,693 3,017,638
E [ADV α
MIA | ADV α
MIA < 0] −687.64 −734.58 −771.30
Source: authors’ calculation, based on data provided by the CMI.
5 Summary and Conclusion
As discussed in Section 1, the rather welcome longevity trend has also some implications that
have to be cautiously accounted for by both individuals and insurance companies. For the
latter, when doing annuity and pension business, there is evidence that the aggregate form of
longevity risk as distinguished earlier may represent a severe systematic risk. It is obvious that
the high correlation of individual risks and thus the potential for accumulative losses represent
a major drawback for insurers. More precisely, unforeseen deviations of actual mortality development from previous expectations can barely – if at all – be hedged or diversified so that
ultimately the question of whether insurers should decline to assume this particular risk seems
legitimate. It has become clear that this form of risk avoidance appears to be quite promising
for insurers.
Following the example of German private health insurance that was briefly introduced in
Section 2.3 as a “role model” for the proposed MIA, a variation to conventional “pure” life annuities is proposed where actual benefits contingent on survival are linked to actual mortality
experienced by a certain reference group; see Section 2.5. The fact that such products seem to
not exist thus appears rather astonishing given the existence of similar product innovations.
These mortality-indexed annuities (MIA) are then further analyzed by comparing the variable
benefits from such contracts with a comparable conventional product, assuming that the latter
would include a safety margin or contingency funds used to avoid actuarial shortfalls for the
insurer as discussed in further detail in Section 3.3. Effectively, the difference of benefits in
MIA and comparable contracts are aggregated by using the notion of an actuarial present value
of these differences, i.e. the sum of annual differences but accounting for the twofold discount
by interest and mortality.
The results from a Monte-Carlo simulation under various parameterizations presented in
Section 4.2 reveal that with a high likelihood policyholders are better off with the innovative
MIA, although there is twofold risk: On the one hand, the degree of advantageousness varies
greatly, i.e. empirical distributions feature relatively large dispersions, and this is a direct
consequence of the fact that aggregate longevity risk is not transfered but born by the insured.
The overall tendency though is a pronounced advantageousness since contingency funds need
not exist and MIA benefits are generally higher. On the other hand, however, accumulating
uncertainty regarding mortality translates into a downside risk in the sense that MIA may
27
actually be disadvantageous for policyholders, i.e. there is a chance that the benefits from
MIA are considerably lower than they would have been in a comparable conventional annuity
contract.
Results obviously depend on what the insurer’s admissible ruin probability and thus the
amount of contingency funds is. The smaller the admissible shortfall risk the larger the loading
or equivalently the difference in initial benefits. As a higher difference would provide an
additional headstart for mortality-indexed annuities it is logically consistent that the degree of
advantageousness as measured by ADV α
MIA would also be higher and consequently the downside
risk for policyholders lower. The huge upside potential can also be a strong argument in favor of
MIA, and it is evident from the histograms where the largest portion of probability mass is not
only to the right of zero but also stretches far into highly positive values of ADV α
MIA. Similar
to the transition from conventional annuities to investment-linked contracts as discussed in
Section 2.2 some policyholders may find it appealing to be offered such contracts but a more
detailed analysis of this issue is subject to further research. As briefly mentioned before, such
analysis also would have to take into account the individual attitude towards risk or, more
precisely, the degree of risk aversion.
What needs to be further considered is that for the present investigation it was assumed that
both MIA and conventional annuities encompass a fixed guaranteed interest rate (set at only
3% and 5% so that it is not unlikely that the insurer’s investment of the collected premiums or
policy reserve will yield higher returns), and the latter type also include a sizeable contingency
funds (which in the presented model on average delivers high profits to the annuity provider).
Therefore, products actually offered in insurance markets provide certain mechanisms to have
policyholders participate in the expected profits from investments and excess reserves. For
the MIA contracts proposed here, a further analysis aiming at a higher degree of reality could
assume stochastic investment yields from a suitable mix of e.g. stocks and bonds. At each
point in time t when adjusting annuity benefits, the evolution of the per-policy reserve as per
Equation (3.5) would be based on actual investment yields ˜ıt−1 instead of the fixed interest
rate i assumed here, and profit sharing could be done by taking only e.g. 90% of the simulated
investment yield. Yet, the computational complexity of the model presented here would be
greatly increased so that such mechanism was not incorporated for the present work. In
tendency, however, both the innovative MIA as well as the benchmarking annuities would be
even more advantageous for policyholders, and it remains to be seen whether the overall effect
would change the results discussed above at all.
As for the first point, one may well argue that it is not adequate to assume the simplest type
of an annuity contract – as considered in the present investigation and also referred to as the
“plain vanilla” case – to be typical for actual insurance markets. For instance German insurance
companies have traditionally almost exclusively offered participating insurance contracts on
both the life insurance and the annuities markets.47 In exchange for a relatively conservative
guaranteed minimum interest rate on the policy reserves, at least 90% of returns in excess
of that minimum rate have to be accumulated on account of each contract.48 However, this
47 For an insightful analysis of annuity types and different designs offered in the German market as well as an
evaluation for different types of customers, see von Gaudecker and Weber (2004).
48 The minimum guaranteed rate that is mandatory for the calculation of policy reserves is set and regularly
revised by BaFin, the Federal Regulatory Authority in Germany. The current rate is prescribed by §2
DeckRV, and it is set in accordance with the smoothed development of yields on long term bonds as per §65
VAG. The general decrease of capital markets over the past years led to a current rate of 2.25%, effective for
all contracts sold in or after 2007. It had been 2.75% before and was previously as high as 4.00%.
28
approach leads to an entirely different regime of guarantee(s). Although German insurers
have tended to use the argument of historically realized rates of return – including actually
attributed surplus – for their marketing, the exact amount is a priori unknown and far from
being guaranteed. In fact most part of the assigned surplus participation is not necessarily
binding for the insurer until eventually attributed on a per-contract basis.49
From a practical point of view the markedly complex mechanisms of determination, individual assignment and actual payout of the respective surplus share make it a special challenge to
realistically account for this concept in any model as various such mechanisms have long been
in use in the industry, and the actual range of choices available also highly depends on the
regulatory and legislative environment. By including profit-sharing mechanisms, several other
issues follow that also would need to be discussed: Besides a notable increase of risk exposure
for insurance companies,50 it also raises the question of how to value such mechanisms51. Nevertheless, interesting and possibly more realistic results are to be expected from an inclusion
in some further investigation.
Another important caveat must be made at this point. As emphasized earlier the problems
arising from model uncertainty are not confronted in the present investigation. Rather it was
assumed that the LC/PML approach represents the true model underlying actual mortality
so that the insurer’s projections were only subject to the explicit stochasticity incorporated
in the LC/PML model. Also, parameter uncertainty might render the model calibration and
thus projections erroneous. Reality is likely to originate more sophisticated fluctuations or
structural changes, and it remains a challenge for the industry and academia to improve and
further the achievements of adequate mortality modeling.
Both uncertainties that are ignored here will actually increase the variations of ultimate
reserves VT for the conventional product, so that contingency funds must be larger to still attain
the same low shortfall risk and this would then tend to deliver higher values of the measure
of MIA advantageousness. Yet, also the MIA benefits would tend to be more dispersed so
that the overall effect remains ambiguous at this point, and the same argument applies when
considering alternative mortality models that might be less conservative and produce more
deviating projections.52
Insofar as the models used for projections by the insurance company (or prescribed by regulators) are considered faulty or insufficient, model uncertainty must be kept in mind when
analyzing the above results. Effectively insurers might consider including additional safety
margins to account for these risks, and this could further bias the transfer of results obtained
in this contribution.
49 The German Federal Court of Justice recently criticized the prevailing practice of insurers’ surplus attribution, which largely favored uncanceled contracts by means of large terminal bonuses, for its lack of transparency; see BGH IV ZR 162/03, IV ZR 177/03, IV ZR 245/03. Providers were thus obliged to “adequately”
account for the development of reserves underlying surplus participation. As a consequence §153 VVG (Versicherungsvertragsgesetz) was revised and the Verordnung über die Mindestbeitragsrückerstattung in der
Lebensversicherung (Mindestzuführungsverordnung – MindZV) as of April 04, 2008 (see BGBl. I S. 690)
replaced the previously applicable Verordnung über die Mindestbeitragsrückerstattung in der Lebensversicherung (ZRQuotenV) as of July 23, 1996 (see BGBl. I S. 1190) for new business.
50 See Kling et al. (2007) for an analysis in the case of life insurance companies.
51 See Bauer et al. (2006).
52 A relatively simple way to mimic increasing uncertainty about projections over time would consist in multiplying the ARIMA disturbance term used to model the time index in the LC/PML approach with a factor
increasing over time, such as e.g. 1 + t
100 
.
29
It is also to be noted that for the present contribution the MIA product investigated effectively not only transfers systematic mortality (or longevity) risk back to policyholders but also
the unsystematic portion of this risk. By adjusting benefits F Vt according to Equations (3.5)
and (3.6) fluctuations in the actual number of survivors ˜lx+t are not further distinguished with
respect to their origin, i.e. to what extent they arise from general changes in the underlying
mortality pattern (systematic risk) or whether they are due to the deviation of individuals’
mortality from the portfolio average.53
The chosen implementation, however, causes that more risk than initially discussed is shifted
back to policyholders, and it may be worthwhile to reflect on the question whether such a strong
cutback of risk born by the annuity provider is conducive to the purpose of risk reduction for
the insurer. Recall that the objective of the proposed MIA was to avoid the potential for
accumulative losses due to systematic changes in the longevity trend. When also shifting back
the unsystematic portion of longevity risk this objective is obviously exceeded. The reason for
forgoing such a further distinction is to facilitate the computations. Also, the chosen approach
may be far easier for annuity providers to implement as it does not require any further analyses.
Instead, at each point in time t calculations may be cased on the current number of survivors
lx+t, and this information is likely to be immediately available for the insurer. Eventually the
fact that this present case can be considered the most extreme scenario of risk avoidance in
comparison to the least re-transfer of longevity risk
The possibly most important question here is the effect of not shifting back the unsystematic
longevity risk on the results that have been presented and discussed in Section 4.2. Although
further analyses are required for a precise assessment, some thoughts on the tendency of changes
in results are still possible at this point. Naturally, if opposed to the situation analyzed here
the insurer bears the unsystematic longevity risk the resulting mortality-indexed annuity would
in tendency be better for the policyholders. As they would not have to bear the unsystematic
component of longevity risk the excess or difference of adjusted benefits compared to a comparable conventional product would be larger ceteris paribus. In addition, as the annuity provider
would have to bear that risk, ultimate per-policy reserves will not always break even for the
MIA contracts – opposed to the case analyzed above. Following the argumentation in Section
3.3 to justify the establishing of contingency funds for the benchmark product, this could now
also be applied to the (partial) MIA contracts. As this might counteract the improvement of
ADV α
MIA pointed out before, the overall effect is ambiguous. Therefore, further analyses are
necessary.
An extension for a further investigation of the proposed mortality-indexed annuities could
be an issue that is inseparably linked to an actual implementation into real annuity markets:
costs and expenses. As pointed out earlier, the present assessment was entirely made on a net
actuarial basis, i.e. without costs, expenses, or profit-sharing etc. – with the exception being
the safety loading for conventional annuities when serving as a benchmark for MIA. Actual
products offered in insurance markets do almost never provide a fair premium without any
surcharges or loadings, and costs that are typically included in gross actuarial calculation are
those pertaining to the policy acquisition (i.e. commissions payable to insurance agents and
53 Of course, the latter cause would be the effect of an imperfect diversification across individual risks in the
portfolio of contracts. More formally: the effect asserted by the Law of Large Numbers only holds for a
theoretically infinite number of contracts, and as this never coincides with reality there is the risk of such
deviations.
30
the costs of checking and processing applications) as well as recurring costs for running the
insurance company, annual statements on policy reserves etc.).54
In the specific case of MIA it remains to be discussed whether and how exactly expenses and
loadings have an influence and the results obtained above. For a true comparison, not only
MIA but also the benchmark product would have to include expenses and loadings, and it is
not obvious at this point in which case these are lower. Further research in this direction is
required to provide a satisfactory appraisal.
Not to be overlooked is the observation that the notion of benefits being linked to demographic development in general, or mortality experience in particular, may actually be not
so uncommon in some countries. For instance, the German public pension system, which is
organized on a pay-as-you-go basis, delivers benefits that are set by statutory ordinance including a so-called “demographic factor” for some time. Thus no ultimate guarantee as to the
exact amount of retirement provision can be made during the working life, and also thereafter
benefits may be changed by legislators as appropriate. Naturally, the demographic transition
has also had an impact on population age structures in Germany, and as a consequence social
security benefits have rather not been increased or barely compensated for inflation. Despite an
entirely different range of problems and challenges associated with public pay-as-you-go pension systems, this thought raises hope that the notion of benefits being contingent on mortality
experience is not considered absurd or generally dismissed.
Further discussion and deliberations regarding this innovative idea, which at a closer investigation does not appear so much surprising, may be necessary to ultimately convince both
insurers and insurees of the overall benefits that mortality-indexed annuities (MIA) can provide.
Eventually individuals who in general seem to be rather reluctant to buy life annuities55
could be provided additional incentives to do so given the potentially advantageous features of
mortality-linked annuities.
54 Many actuarial textbooks provide an introduction of how to include initial and recurring costs into pricing
and reserving of insurance contracts as a transition from a net perspective presented in the first place; see
e.g. Bowers et al. (1997, Ch.15).
55 This empirical observation in contrast to the theoretical optimality of complete annuitization of wealth is
generally discussed in the literature as the “annuity puzzle”; see Yaari (1965); Davidoff et al. (2005).
31
References
Akerlof, George A. (1970). “The Market for Lemons - Quality Uncertainty and the Market
Mechanism.” Quarterly Journal of Economics, 84(3): 488–500.
Alho, Juha M. (2000). “Discussion of Lee (2000).” North American Actuarial Journal, 4:
91–93.
Bauer, Daniel, Rüdiger Kiesel, Alexander Kling, and Jochen Ruß (2006). “Risk-Neutral
Valuation of Participating Life Insurance Contracts.” Insurance: Mathematics and
Economics, 39(2): 171–183.
Black, Kenneth and Harold D. Jr. Skipper (2000). Life and Health Insurance. Upper
Saddle River, NJ: Prentice Hall, 13th edn.
Blake, David, Andrew Cairns, and Kevin Dowd (2003). “Annuitisation Options.”
Bowers, Newton L., Hans U. Gerber, James C. Hickman, Donald A. Jones, and Cecil J.
Nesbitt (1997). Actuarial Mathematics. Schaumburg, Illinois: Society of Actuaries, 2nd
edn.
Brouhns, Natacha, Michel Denuit, and Jeroen K. Vermunt (2002). “A Poisson
log-bilinear regression approach to the construction of projected lifetables.” Insurance:
Mathematics and Economics, 31: 373–393.
Brünjes, Christian (1990). Technische Methoden der privaten Krankenversicherung in
Deutschland, 44–62. In: Timmer (1990).
Cairns, Andrew J., David Blake, and Kevin Dowd (2006). “Pricing Death: Frameworks
for the Valuation and Securitization of Mortality Risk.” ASTIN Bulletin, 36: 79–120.
Davidoff, Thomas, Jeffrey R. Brown, and Peter A. Diamond (2005). “Annuities and
Individual Welfare.” The American Economic Review, 95: 1573–1590.
De Moivre, Abraham (1756). “The doctrine of chances.”
Ebers, Markus (2001). Die Überschußbeteiligung in der Lebensversicherung. Baden-Baden:
Nomos.
Edwards, Ryan D., Ronald D. Lee, Michael W. Anderson, Shripad Tuljapurkar, and
Carl Boe (2003). “Key Equations in the Tuljapurkar-Lee Model of the Social Security
System.” Michigan Retirement Research Center, Working Paper 2003-044.
Feldstein, Martin S. (1970). “The Rising Price of Physicians’ Services.” Review of
Economics and Statistics, 52: 121–133.
Feldstein, Martin S. (1971). “Hospital Costs Inflation: A Study in Nonprofit Price
Dynamics.” American Economic Review, 61: 853–872.
Feldstein, Martin S. (1973). “The Welfare Loss of Excess Health Insurance.” Journal of
Political Economy, 81: 251–280.
von Gaudecker, Hans-Martin and Carsten Weber (2004). “Surprises in a Growing
Market Niche: An Evaluation of the German Private Life Annuities Market.” The Geneva
Papers on Risk and Insurance, Issues and Practice, 29: 394–416.
GDV (2004). “Die Märkte für Altersvorsorge in Deutschland: Eine Analyse bis 2020.” No. 23
in Schriftenreihe des Ausschusses Volkswirtschaft. Karlsruhe: Verlag
Versicherungswirtschaft.
GDV (2008). “Statistical Yearbook of German Insurance.” Berlin: Gesamtverband der
Deutschen Versicherungswirtschaft e.V. URL
https://secure.gdv.de/gdv-veroeffentlichungen/upload_img/146_dwl.pdf.
Gompertz, Benjamin (1825). “On the nature of the function expressive of the law of human
mortality.” Philosophical Transactions, 27(5): 513–519.
Gruschinske, G. (1989). “Überschußbeteiligung in der Lebensversicherung in der
Diskussion.” Zeitschrift für Versicherungswesen, 40: 642–648.
Hanewald, Katja, Thomas Post, and Helmut Gründl (2009). “Stochastic Mortality,
Macroeconomic Risks, and Life Insurer Solvency.” Humboldt-Universität Berlin, Working
Paper.
Kifmann, Mathias (2000). “The Premium Risk Problem in Health Insurance.” Schmollers
Jahrbuch – Zeitschrift für Wirtschafts- und Sozialwissenschaften, 120: 567–586.
Kifmann, Mathias (2002). Insuring Premium Risk in Competitive Health Insurance Markets,
vol. 15 of Beiträge zur Finanzwissenschaft. Tübingen: Mohr Siebeck. ISBN 9783161477409.
Kling, Alexander, Andreas Richter, and Jochen Ruß (2007). “The Impact of Surplus
Distribution on the Risk Exposure of With Profit Life Insurance Policies Including Interest
Rate Guarantees.” Journal of Risk and Insurance, 74(3): 571–589.
doi:10.1111/j.1539-6975.2007.00225.x.
Lee, Hangsuck (2003). “Pricing equity-indexed annuities with path-dependent options.”
Insurance: Mathematics and Economics, 33(3): 677–690. ISSN 0167-6687.
doi:10.1016/j.insmatheco.2003.09.006.
Lee, Ronald D. (2000). “The Lee-Carter Method For Forecasting Mortality, with Various
Extensions and Applications.” North American Actuarial Journal, 4: 80–91.
Lee, Ronald D., Michael W. Anderson, and Shripad Tuljapurkar (2003). “Stochastic
Forecasts of the Social Security Trust Fund.” Report prepared for the Social Security
Administration. Michigan Retirement Research Center, Working Paper 2003-043.
Lee, Ronald D. and Lawrence R. Carter (1992). “Modeling and forecasting US mortality.”
Journal of the American Statistical Association, 87: 659–675.
Lee, Ronald D. and Shripad Tuljapurkar (1998). Stochastic Forecasts for Social Security,
chap. 9, 393–430. Chicago: University of Chicago Press.
Leinert, Johannes and Gert G. Wagner (2001). “Probleme einer steigenden
Lebenserwartung in der privaten Rentenversicherung: Theorie und Empirie für
Deutschland.” DIW Discussion Paper No. 258.
33
Lin, X. Sheldon and Ken Seng Tan (2003). “Valuation of Equity-Indexed Annuities under
Stochastic Interest Rates.” North American Actuarial Journal, 7(4): 72–91.
Makeham, William M. (1860). “On the law of mortality and the construction of annuity
tables.” Journal of the Institute of Actuaries, 8: 301–310.
Montgomery, Keith (2007). “The Demographic Transition.” Working Paper, University of
Wisconsin-Marathon County. Retrieved October 28, 2007 from
http://www.uwmc.uwc.edu/geography/Demotrans/demtran.htm.
Mutschler, Karin and Jochen Ruß (2001). “Die Fondsgebundene Rentenversicherung mit
Fondsanbindung in der Rentenbezugsphase – Produktideen und empirische Analysen.”
Blätter der Deutschen Gesellschaft für Versicherungs- und Finanzmathematik, 25(1):
95–110. doi:10.1007/BF02857120.
Nell, Martin, Andreas Richter, and Jörg Schiller (2009). “When prices hardly matter:
Incomplete insurance contracts and markets for repair goods.” European Economic Review,
(in press).
Oeppen, Jim and James W. Vaupel (2002). “Broken Limits to Life Expectancy.” Science,
296: 1029–1031.
Pavcnik, Nina (2002). “Do pharmaceutical prices respond to patient out-of-pocket
expenses?” RAND Journal of Economics, 33: 469–487.
Renshaw, Arthur E. and Steven Haberman (2003). “Lee-Carter mortality forecasting with
age-specific enhancement.” Insurance: Mathematics and Economics, 33(2): 255–272.
Riemer-Hommel, Petra and Thomas Trauth (2005). “The Challenge of Managing
Longevity Risk.” In: Frenkel, Michael, Ulrich Hommel, and Markus Rudolf (Eds.),
“Risk Management – Challenge and Opportunity,” 391–406. Berlin: Springer, 2nd edn.
Ruß, Jochen (2000). “Todesfall-Leistung bei der Fondsgebundenen Rente – Betrug oder
Performancesteigerung?” Online at
http://www.ifa-ulm.de/downloads/Performance_im_Todesfall.pdf.
Schumacher, Petra (2008). “Enhanced Annuities — Produktinnovation als
Lösungsstrategie für das Annuity Puzzle?” Zeitschrift für die gesamte
Versicherungswissenschaft, Suppl. 2008: 71–89. doi:10.1007/s12297-008-0036-4.
Schwintowski, Hans-Peter and Martin Ebers (2002). “Lebensversicherung – stille
Reserven – Überschussbeteiligung.” Zeitschrift für die gesamte Versicherungswissenschaft,
91(3): 393–452.
Timmer, Hans-Georg (1990). Technische Methoden der privaten Krankenversicherung in
Europa – Marktverhältnisse und Wesensmerkmale der Versicherungstechnik. No. 23 in
Schriftenreihe Angewandte Versicherungsmathematik. Karlsruhe: Verlag
Versicherungswirtschaft.
Tiong, Serena (2000). “Valuing Equity-Indexed Annuities.” North American Actuarial
Journal, 4(4): 149–170.
34
United Nations (2005). “World Population Prospects. The 2004 Revision – Highlights.”
Report.
Yaari, Menahem E. (1965). “Uncertain Lifetime, Life Insurance, and the Theory of the
Consumer.” Review of Economic Studies, 32: 137–150.
Zweifel, Peter and Luca Crivelli (1996). “Price Regulation of Drugs: Lessons from
Germany.” Journal of Regulatory Economics, 10: 257–273.
35