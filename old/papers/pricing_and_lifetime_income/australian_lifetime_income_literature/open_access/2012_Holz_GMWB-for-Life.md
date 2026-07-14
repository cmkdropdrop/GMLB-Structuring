https://www.ifa-ulm.de/fileadmin/user_upload/download/forschung/2012_ifa_Holz-etal_GMWB-for-life-an-analysis-of-lifelong-withdrawal-guarantees.pdf
→ https://www.ifa-ulm.de/fileadmin/user_upload/download/forschung/2012_ifa_Holz-etal_GMWB-for-life-an-analysis-of-lifelong-withdrawal-guarantees.pdf
Content-Type: application/pdf

GMWB For Life 
An Analysis of Lifelong Withdrawal Guarantees 
Daniela Holz 
Ulm University, Germany 
daniela.holz@gmx.de 
Alexander Kling *) 
Institut für Finanz- und Aktuarwissenschaften 
Helmholtzstr. 22, 89081 Ulm, Germany 
phone: +49 731 5031242, fax: +49 731 5031239 
a.kling@ifa-ulm.de 
Jochen Ruß 
Managing Director 
Institut für Finanz- und Aktuarwissenschaften 
Helmholtzstr. 22, 89081 Ulm, Germany 
phone: +49 731 5031233, fax: +49 731 5031239 
j.russ@ifa-ulm.de 
Key words: variable annuities, guaranteed minimum living benefits, risk-neutral valuation, embedded options 
Abstract 
We analyze the latest guarantee feature in the variable annuities market: 
guaranteed minimum withdrawal benefits for life or guaranteed lifelong 
withdrawal benefits. This option gives the client the right to deduct a certain amount annually from the policy’s account value until death – even if 
a unit-linked account value drops to zero. We show how such products 
can be analyzed within a general framework presented in Bauer et al. 
(2006). We price the embedded guarantee for different product designs 
and parameters under deterministic and optimal client behaviour. 
*) Corresponding Author
1 Introduction 
Variable annuities, i.e. deferred annuities that are fund-linked during the accumulation period were introduced in the 1970s in the United States (see Sloane (1970)). 
Since the 1990s, certain optional guarantees are usually offered in such policies: 
guaranteed minimum death benefits (GMDB) as well as guaranteed minimum living 
benefits (GMLB). The GLWB options can be categorized in three main groups: Guaranteed minimum accumulation benefits (GMAB) provide a guaranteed minimum survival benefit at some or several specified points of time, guaranteed minimum income 
benefits (GMIB) offer a guaranteed lifelong fixed annuity starting at the end of the 
deferment period. However, GMIB products offer no guaranteed lump sum benefit. 
Finally, in guaranteed minimum withdrawal benefits (GMWB) some specified amount 
is guaranteed for withdrawals during the life of the contract as long as both the 
amount that is withdrawn within each policy year and the total amount that is withdrawn over the term of the policy stay within certain limits. A detailed product description and extensive literature overview is given in Bauer et al. (2006) and is therefore 
omitted in this paper. 
In the present paper, we look at the latest variant of GMWB-guarantees, so called 
GMWB for life. Such products have recently been introduced in the US, Asia and 
Europe. As the name suggests, GMWB for life or Guaranteed Lifelong Withdrawal 
Benefits (GLWB) offer a lifelong withdrawal guarantee. Therefore, there is no limit for 
the total amount that is withdrawn over the term of the policy. Usually, with an immediate GLWB, annually a certain percentage of the single premium (the guaranteed 
amount) can be withdrawn from the policy. This percentage rate may depend on the 
age of the insured. If at the time of death there is a remaining account value, then 
this value is paid to the beneficiary as death benefit. If, however, due to declining 
stock markets and/or such withdrawals the account value of the policy becomes zero 
while the insured is still alive, then the insured can continue to withdraw the guaranteed amount annually until death. The insurer charges a fee for this guarantee which 
is usually a fix percentage of the policyholder’s account value per annum. In deferred 
versions of the product, the product is fund linked with or without guarantee during 
the deferment period. The account value at the end of the deferment period (or some 
guaranteed amount if guarantees are included in the deferment period as well) is 
then treated like a single premium to an immediate GLWB contract. 
The rest of the paper is organized as follows. In Section 2, we give a detailed description of GLWB products. Section 3 introduces our model. Here, we build on a 
general model introduced in Bauer et al. (2006) and show, how GLWB products can 
be included in their model. Due to the complexity of the products, in general there are 
no closed form solutions for the valuation problem. Therefore, we have to rely on 
numerical methods and present our valuation approach in Section 4. We show how a 
given contract can be priced with Monte Carlo methods assuming deterministic as 
well as “optimal” policyholder behavior. For the latter, we introduce numerical methods for the determination of such optimal strategies. Finally, in Section 5 we present 
the results of our analyses that are derived in a Monte Carlo framework. We give the 
fair value of the guarantee for a variety of contracts, analyze the influence of several 
parameters and give economic interpretations. Section 6 closes with a summary of 
the main results and an outlook for future research. 
2 Guaranteed Minimum Withdrawal Benefits for Life 
In this Section, we explain the concept of GLWB within variable annuities. We start 
with a very brief description of variable annuities in general and other types of guarantees offered within such products and refer the reader to Bauer et al. (2006) for 
more details. 
Variable Annuities are deferred, fund-linked annuity contracts, usually with a single 
premium payment up-front. Therefore, in what follows we restrict ourselves to single 
premium policies. When concluding the contract, the insured are frequently offered 
optional guarantees, which are paid for by additional fees. 
The single premium P is invested in one or several mutual funds. We call the value At
of the insured’s individual portfolio the insured’s account value. Customers can usually influence the risk-return profile of their investment by choosing from a selection of 
different mutual funds. All fees are taken from this account by cancellation of fund 
units. Furthermore, the insured has the possibility to surrender the contract, to withdraw a portion of the account value (partial surrender), or to annuitize the account 
value after a minimum term. 
If the insured dies during the deferment period, the beneficiary obtains a death benefit that depends on the account value. If a guaranteed minimum death benefit is chosen, then the death benefit paid is the higher of the account value and some specified guaranteed value. Since the late 1990s, guaranteed minimum living benefits are 
offered in the market. The two earliest forms, guaranteed minimum accumulation 
benefits (GMAB) and guaranteed minimum income benefits (GMIB) offer the insured 
a guaranteed maturity benefit, i.e. a minimum benefit at the maturity T of the contract 
(or within a certain period of time). However, with the GMIB, this guarantee only applies if the account value is annuitized. 
Since 2002, a new form of GLWB is offered: so-called guaranteed minimum withdrawal benefits (GMWB). Products with a GMWB option give the policyholder the 
possibility to withdraw a specified amount W G 0 (that usually coincides with the single 
premium) in small portions. Typically, the insured is entitled to annually withdraw a 
certain portion xW of this amount W G 0 , even if the account value has fallen to zero, 
until the total withdrawals reach W G 0 . At maturity, the policyholder can take out or 
annuitize any remaining funds if the account value did not vanish due to withdrawals. 
These guarantees are extremely popular. In the first half of 2005, more than 3 out of 
4 variable annuity contracts sold included a GMWB option. Each of the 15 largest 
variable annuity providers offered this kind of guarantee at that time (cf. Lehmann 
Brothers (2005)). Since GMWB products are so popular, insurers developed several 
versions of this product to be more competitive. 
The latest version that is now already offered in the USA, Asia and Europe includes a 
lifelong withdrawal guarantee: The total amount to be withdrawn W G 0 is not limited. 
Insurers that introduced this type of guarantee (GLWB) were immediately able to significantly increase their new business volume. Usually, the annual amount to be withdrawn in a GLWB product is a certain percentage xWL of the single premium P. Any 
remaining account value at the time of death is paid to the beneficiary as death benefit. If, however, the account value of the policy drops to zero while the insured is still 
alive, the insured can still continue to withdraw the guaranteed amount annually. The 
insurer charges a fee for this guarantee which is usually a pre-specified annual percentage of the account value. Deferred versions of the product also exist in the market. Here, the product is fund linked during the deferment period. The account value 
at the end of the deferment period is then treated like a single premium to an immediate GLWB contract. Sometimes, certain guarantees are also included in the deferment period: if the account value at the end of the deferment period is lower than 
some guaranteed amount, than this guaranteed amount is transferred to the GLWB 
payout phase. 
Furthermore, different additional features like step-ups and roll-ups are offered with 
GLWBs: If a step-up is included, the guaranteed annual withdrawal amount can be 
increased at pre-specified points in time. At these step-up dates, the guaranteed annual withdrawal amount is increased if the portion xWL of the current account value 
exceeds the previous guaranteed annual withdrawal amount.1 Therefore, step-ups 
only occur if the policyholder’s funds yield high performance and the account value 
has not been decreased heavily due to previous withdrawals. Common step-up features are, e.g., annual ratchet guarantees. 
If a roll-up is included within GLWB, the annual guaranteed withdrawal amount is increased by a fixed percentage every year during a certain time period but only if the 
policyholder has not started withdrawing money. Therefore, roll-ups are commonly 
used as an incentive to the policyholder not to withdraw money from the account in 
the first years. 
3 The Model 
3.1 The Financial Market 
We assume that there exists a probability space (Ω,F,Q) with a filtration F ( ) ℑt t ∈[ ] 0,T =
and a risk neutral probability measure Q. Under this risk-neutral measure, payment 
streams can be valued as expected discounted values using the risk-neutral valuation formula (cf. e.g. Bingham and Kiesel (2004)). Existence of this measure also implies an arbitrage free financial market. Thus, for every regular derivative, there exists 
some self-financing investment strategy which replicates the payoff of the derivative. 
This allows the insurer to hedge the liabilities. 
We assume a numéraire process ( ) t t [ ] T B ∈ 0, which evolves according to 
= r dt , B 0 > 0
B
dB
t
t
t , (1) 
where rt denotes the short rate of interest at time t. For all our numerical calculations, 
we assume rt = r. Thus, for the bank account we have rt B t = e . 
We further assume the existence of some risky asset St that serves as underlying 
mutual fund for the considered variable annuity contracts. St evolves according to a 
Geometric Brownian motion with constant coefficients under Q, i.e. 
 
1
 Typically, these step-up dates are annually or every three or five years on the policy anniversary 
date. 
= rdt + dZ , S 0 = 1
S
dS t
t
t σ , (2) 
where σ denotes the (constant) volatility of the risky asset. Under the risk-neutral 
probability measure, the discounted asset process t t [ ] T
t
B
S
∈ 0,
⎟
⎟
⎠
⎞
⎜
⎜
⎝
⎛ is a martingale. At t = 0, 
we assume 1. S 0 = B 0 =
3.2 A Model for the Insurance Contract 
In Bauer et al. (2006), a general model for the description and valuation of variable 
annuity contracts was introduced. Within this framework, any contract with one or 
several living benefit guarantees and/or a guaranteed minimum death benefit can be 
represented. In the numerical analysis however, only contracts with a rather short 
finite time horizon were considered. In particular, GLWB were not analyzed. In what 
follows, we therefore describe how GLWB-products can be included in this model. 
We refer to Bauer et al. (2006) for the explanation of other living benefit guarantees 
and more details on the model. 
Let 
o x 0 be the insured’s age at the start of the contract, 
o x 0 t p be the probability for a x 0 -year old to survive the next t years, 
o q x +t 0 be the probability for a ( ) 0 x + t -year old to die within the next year, and 
o ω be the limiting age of the mortality table, i.e. the age beyond which survival 
is impossible.
The probability that an insured aged x0 at inception passes away in the year (t,t+1] is 
thus given by t p x q x +t ⋅ 0 0 . The limiting age ω allows for a finite time horizon T = 
ω − x 0 . 
We denote the single premium invested into the contract at time t = 0 by P. At denotes the account value at time t. Throughout the paper, we assume that all fees and 
charges are deducted continuously as a percentage ϕ of the account value and no 
upfront charges exist. This leads to A0 = P . Besides, we allow for a surrender fee s
which is charged as a percentage of any withdrawal of funds exceeding guaranteed 
withdrawals within a GMWB or GLWB option. 
Following the notation in Bauer et al. (2006), we denote the value of some withdrawal 
account at time t by Wt. Withdrawals up to time t are credited to this account and 
compounded with the risk-free rate of interest. At inception, we have W0 = 0. Similarly, death benefits paid up to time t are accumulated in the death benefit account Dt
which is also compounded by the risk-free rate until time T. At time t = 0, we have D0 
= 0. 
Throughout this paper, we focus on guaranteed minimum withdrawal benefits and, in 
addition, allow for guaranteed minimum death benefits. We use the following notations again following Bauer et al. (2006): If the contract includes a GMDB option, the 
death benefit at time t is given by the greater of the current account value and the 
guaranteed minimum death benefit base D G t , i.e. { } D At G t max ; . If a GMDB is included, 
the initial amount of the guaranteed minimum death benefit base is given by G 0 A0
D =
if not stated otherwise. Contracts without a GMDB rider simply pay out the current 
fund net asset value in the case of death. Such contracts are modeled by letting 
0 D Gt = for all t. 
For the modeling of GMWB or GLWB options, we introduce two processes W G t and 
E G t . We call W G t the total amount guaranteed for future withdrawals. For standard 
GMWB options, we usually have G 0 A0
W = at inception. For GLWB, the total amount 
of withdrawals is unlimited and thus W Gt = ∞ for all t. The maximum amount that may 
be withdrawn annually due to the GMWB or GLWB-option is called E G t . At t = 0 it is 
given by some percentage of the single premium P, i.e. G 0 x W A0
E = . Please note that 
we use the same state variables for the modeling of GMWB and GLWB options since 
we do not consider contracts with both, a GMWB and a GLWB-option. Such contracts could also be modeled in our framework by introducing separate processes W G t and E G t for each option.2
Finally, we call ( ) ,,, , , D W E
t tttt t t y = AW DG G G the state vector at time t containing all information about the contract at that point in time. 
Since we restrict our analyses to single premium contracts and do not allow for additional premium payments, policyholder actions during the life of the contract are limited to withdrawals. Depending on the amount of money withdrawn, the policyholder 
can withdraw funds as a guaranteed withdrawal of a GMWB/GLWB option, perform a 
partial surrender, i.e. withdraw more than the guaranteed withdrawal amount, or 
completely surrender the contract. 
For the sake of simplicity, we allow for withdrawals at policy anniversaries only. Also, 
we assume that death benefits are paid out at policy anniversaries if the insured person has died during the previous year. Thus, the value of the state variables described above may have discontinuities at times t = 1,2,...,T . Thus, at each policy 
anniversary, we have to distinguish between the value of the respective variable − ⋅ t ()
immediately before and the value + ⋅ t () after withdrawals and death benefit payments. 
During the year, all processes are subject to capital market movements and may 
therefore also change between two policy anniversaries. In what follows, we describe 
the development between two policy anniversaries and the transition at policy anniversaries for different contract designs. From these, we are finally able to determine 
all benefits for any given policy holder strategy and any capital market path. This allows for the valuation of such contracts in a Monte-Carlo framework. 
3.2.1 Development between two Policy Anniversaries 
We assume that the annual guarantee fee ϕ is deducted from the policyholder’s account value on a continuous basis. Thus, the development of the account value be-
 
2
 Since GW is not needed for GLWB options, two processes GE and one process GW are sufficient. 
tween two policy anniversaries is given by the development of the underlying fund 
after deduction of the guarantee fee, i.e. 
 − + + −ϕ
+ = ⋅ e
S
S A A
t
t
t t
1
1 . (3) 
As described earlier, the withdrawals and death benefits are compounded on the accounts Wt and Dt at the risk-free rate of interest r. This leads to 
∫ =
+
− +
+
1
1
t
t
r sds
Wt Wt e and ∫ − +
+
+
=
1
1
t
t
r sds
Dt Dt e . 
Throughout this paper, we use return of premium death benefits if a GMDB option is 
included. Thus, the value of the guaranteed minimum death benefit base is not 
changed between two policy anniversaries which leads to // //
1
DEW DEW G G t t− +
+ = . 
Since withdrawals only occur at integer times t, the processes W G t and E G t only 
change during the year if some roll-up feature is included. The time horizon within 
which roll-ups occur is usually limited to a certain number of years tWL from the beginning of the withdrawal period. Roll-ups only are applied if no withdrawals have 
been made so far. We denote the annual roll-up rate by iw and let 1 ( ) 1 W W GG i tt W
− +
+ = +
and 1 ( ) 1 E E GG i tt W
− +
+ = + if Wt = 0 and WL t t ≤ . If no roll-up is included, 1
W W G G t t
− +
+ = . Besides 
roll-ups, withdrawal guarantees are often equipped with so called step-up features. If 
a step-up is included, withdrawal guarantees can only be increased at the policy anniversaries. Thus, step-ups are described in the following section. 
3.2.2 Transition at a Policy Anniversary t
At the policy anniversaries, we have to distinguish the following four cases: 
a) The insured has died within the previous year (t-1,t] 
If the insured person has died within the previous policy year, the death benefit is 
credited to the death benefit account Dt : max{ ; } D Dt t tt D GA + − −− = + . With the payment of 
the death benefit, the insurance contract matures. Thus, the policyholder’s account 
value and all riders attached to it are terminated, i.e. 0 At
+ = , 0 D Gt+ = , 0 W Gt+ = , and 
0 E Gt
+ = . Withdrawals that have been made earlier remain on the withdrawal account 
Wt: W W t t
+ − = . 
b) The insured has survived the previous policy year and does not withdraw any 
money from his account at time t
If no death benefit is paid out to the policyholder and no withdrawals are made from 
the contract, the account value as well as the withdrawal and the death benefit account remain unchanged, i.e. A A t t
+ − = , Dt t D + − = and W W t t+ − = . Also the guaranteed 
minimum death benefit doesn’t change in this case which leads to D D G G t t
+ − = . 
If the contract includes a withdrawal guarantee with step-up and t is a step-up point, 
the total amount available for future withdrawals is increased if the account value exceeds the current value of the guarantee account, i.e. max ; { } W W G GA t tt
+ −+ = . Note that 
in the case of GLWB, this value remains unchanged (at infinity). The annual guaran-
teed withdrawal amount E Gt may also be increased. It is given by 
max ; { } E E G G xA t t Wt
+ −+ = ⋅ . 
c) The insured has survived the previous policy year and at the policy anniversary 
withdraws an amount within the limits of the withdrawal guarantee
If the insured has survived the past year, no death benefits are paid and therefore 
Dt t D + − = . Any withdrawal Et below the guaranteed annual withdrawal amount E Gt
− and 
lower than the total withdrawal amount W Gt
− reduces the account value by the withdrawn amount. Of course, we do not allow for negative policyholder account values 
and thus get A AE t tt max 0; { } + − = − . The withdrawal account is increased by the amount 
withdrawn, i.e. WWE t tt
+ − = + . 
In the case of a GMWB option, the remaining total withdrawal amount is reduced by 
the amount withdrawn, i.e. W W GGE t tt
+ − = − . For GLWB-guarantees, the total amount of 
withdrawals is unlimited and thus remains unchanged W W G G t t
+ − = =∞ . For both riders, 
the maximal annual withdrawal amount E E G G t t
+ − = remains unchanged. If, however, a 
step-up feature is included and t is a step-up point, the total amount available for future withdrawals can be increased as described in b), i.e. max ; { } W W G GA t tt
+ −+ = (for 
GMWB only) and the new annual guaranteed withdrawal amount E Gt is given by 
max ; { } E E G G xA t t Wt
+ −+ = ⋅ . 
With any withdrawals, the guaranteed death benefits are reduced at the same rate as 
the account value, i.e. D t D
t t
t
A G G
A
+
+ −
−
⎛ ⎞ = ⎜ ⎟ ⎝ ⎠
. 
d) The insured has survived the previous policy year and at the policy anniversary 
withdraws an amount exceeding the limits of the withdrawal guarantee
In this case again, no death benefits are paid and therefore Dt t D + − = . 
Withdrawals exceeding the limits of the withdrawal guarantee always lead to a partial 
or full surrender of the annuity contract, depending on the amount of money withdrawn and on the amount remaining within the policyholder’s account. 
Any withdrawal Et exceeding the limits of the withdrawal guarantee can be separated 
into two parts, the guaranteed amount { }−
+
−
+ = +
W
t
E E t G t 1 G 1
1
1 min ; and the exceeding part 
2 1 Et tt = − E E . As in case c), the account value is reduced by the amount withdrawn, i.e. 
A AE ttt
+ − = − , and the withdrawn amount is credited to the withdrawal account after 
deduction of surrender charges for the exceeding part.3 Thus, we get 
( ) 1 2 1 W W EE s t t tt
+ − = + + ⋅− . 
 
3
 Note that surrender charges only apply to the exceeding part, Therefore surrender charges were not 
considered in case c) above. 
In the case of a GMWB option, usually the remaining total withdrawal amount is reduced by the withdrawn amount, but at least by the same percentage, by which the 
account value is reduced.4 From this we get min ; WW W t
t tt t
t
A G GEG
A
+
+− −
−
⎧ ⎫ = − ⎨ ⎬ ⎩ ⎭
. For GLWB, 
the total amount of withdrawals is unlimited and thus again remains unchanged 
W W G G t t+ − = =∞ . For both riders, the maximum annual withdrawal amount E Gt+ is reduced by the same percentage, by which the account value is reduced, i.e. 
E t E
t t
t
A G G
A
+
+ −
− = ⋅ . If a step-up feature is included and t is a step-up point, the total 
amount available for future withdrawals may be increased: max ; E E t
t t Wt
t
A G G xA
A
+
+ −+
−
⎧ ⎫ = ⋅⋅ ⎨ ⎬ ⎩ ⎭
. 
As in case c), with any withdrawals, the guaranteed death benefits are reduced at the 
same rate as the account value, i.e. D t D
t t
t
A G G
A
+
+ −
−
⎛ ⎞ = ⎜ ⎟ ⎝ ⎠
. 
3.2.3 Maturity Benefits at T 
At maturity of the contract at t = T = ω - x, the insured has either died or surrendered 
the contract. Thus, all insurance benefits have already been credited to Dt or Wt and 
no additional final payment is given to the policyholder. We therefore call WT and DT
the maturity benefit of the contract. 
4 Valuation of the Guarantees 
Assuming independence between financial markets and mortality and risk-neutrality 
of the insurer with respect to mortality risk, we are able to use the product measure of 
the risk-neutral measure of the financial market and the mortality measure. In what 
follows, we denote this product measure by Q. 
4.1 Deterministic Policyholder Behavior 
If we assume deterministic policyholder behavior, any withdrawal strategy can easily 
be described by using a withdrawal vector ( ) ( )T
T IR∞ ξ = ξ ξ ∈ + ;...; 1
_ 5
 where ξt denotes 
the deterministic withdrawal amount at the end of year t, if the insured is still alive. Of 
course, if any such withdrawal exceeds the guaranteed annual withdrawal amount, 
the withdrawal leads to a partial or even full surrender. By allowing for ξ t = ∞ , a full 
surrender at time t can also be represented within such a strategy. Since deterministic strategies are already specified at time t = 0, every deterministic strategy is F0 -
measurable. 
 
We denote the set of all possible F0-measurable strategies by 
( )T
T IR ∞ Ψ = Ψ × × Ψ ⊂ + ... 1 .For any given strategy and under the assumption that the 
 
4
 Whenever a non-guaranteed withdrawal occurs, future guarantees may be reduced. We here describe a so-called pro-rata reduction which is the predominant form in the market. 
5
 Here, + IR denotes the non negative real numbers (including zero); furthermore we let = ∪ { } ∞ . +
∞
+ IR IR
insured dies in year { }0 t ∈ 1,2,...,ω − x , the maturity-values ⎟
⎟
⎠
⎞ ⎜
⎜
⎝
⎛ _
WT t ;ξ and ⎟
⎟
⎠
⎞
⎜
⎜
⎝
⎛ _
DT t ;ξ are 
specified for each capital market path. Thus, the time zero value assuming the given 
policyholder strategy including all options is given by the risk-neutral discounted expected value of these maturity values: 
0
0
0 0
_ __
0 11
1
; ;.
T
s x r ds
t x xt Q T T
t
V p q Ee Wt Dt
ω
ξ ξξ
− −
− +−
=
⎡ ⎤ ⎛⎞ ⎛ ⎞ ⎛ ⎞ ∫ ⎛ ⎞ ⎢ ⎥ ⎜⎟ ⎜ ⎟ ⎜ ⎟ =⋅ + ⎜ ⎟ ⎝⎠ ⎝ ⎠ ⎝ ⎠ ⎝ ⎠ ⎣ ⎦
∑ (4) 
4.2 Probabilistic Policyholder Behavior 
If policyholders follow certain deterministic strategies with certain probabilities, we 
call this behavior probabilistic behavior. Policyholder strategies are still F0-
measurable but several such strategies are now weighted by certain probabilities. We 
denote the corresponding deterministic strategies by ( ) ( )T j
T
j
j
IR∞ = ∈ +
( ) ( )
1
( ) _
ξ ξ ;...;ξ , 
j = 1,2,...,n and the respective probabilities by ( j ) p ξ where of course ∑==
n
j
j p
1
( )
ξ 1 . For 
any probabilistic strategy, the value of the contract under probabilistic policyholder 
behavior is given by 
⎟
⎟
⎠
⎞
⎜
⎜
⎝
⎛ = ∑=
( ) _
0
1
( )
0
n j
j
j V p ξ V ξ . (5) 
4.3 Stochastic Policyholder Behavior 
We call a policyholder strategy stochastic if the decision whether and how much 
money should be withdrawn depends on the account value or other information 
available at time t. Thus, stochastic policyholder strategies are not necessarily F0-
measurable. However, we still assume some Ft-measurable process (X), which determines the amount to be withdrawn depending on the state vector − y t at time t. 
Thus, we get: ( ) y t Ε t t = − X , , t = 1,2,...,T . 
Assuming that the insured dies in year t ∈ { } 1,2,...,ω − x , for each stochastic strategy 
(X) the values W ( ) t ;(X) T and D ( ) t ;(X) T are specified for any capital market path. 
Therefore, the value of the contract following some stochastic strategy (X) is given 
by: 
 () ( ) ( ) ( ) 0
0
0 0 0 11
0
(X) , (X) , (X)
T
s x r ds
t x xt Q T T
t
V p q E e Wt Dt
ω− −
− +−
=
⎡ ⎤ ∫ ⎢ ⎥ = ⋅⋅ + ⎢ ⎥ ⎢⎣ ⎥⎦
∑ . (6) 
We let Ξ denote the set of all admissible stochastic strategies. Then the value V 0 of 
a contract assuming a rational policyholder is given by 
( ) (X)
(X)
0 0 V supV
∈Ξ
= . (7) 
Even though the value of the contract under rational policyholder behavior can easily 
be defined, the respective rational strategy is not obvious and cannot be easily determined. In the following section, we describe how Monte-Carlo simulation can be 
used to approximate optimal policyholder strategies. The ideas are based on Anderson (1999). 
4.4 Determining the Contract Value using Monte Carlo Methods 
By Itô’s formula (see, e.g. Bingham and Kiesel (2004)), the iteration 
; ~ ( ) 0,1
2 exp 1 1
2
1
1 e A r z z N
S
S A A t t t
t
t
t t + +
− + + − +
+
⎭
⎬
⎫
⎩
⎨
⎧
+⎟
⎟
⎠
⎞
⎜
⎜
⎝
⎛ = ⋅ = ⋅ − − σ
σ
ϕ ϕ iid, 
can be conveniently used to produce realizations of sample paths ( j ) a of the policyholder’s account using Monte Carlo Simulation.6
 For any capital market development 
and for any time of death, the evolution of all accounts and processes is determined 
by the rules given in Section 3.2. Thus, realizations of the benefits 
() () () () , (X) , (X) j j wt dt T T + at time T are uniquely defined for any capital market scenario 
and the time zero value of these benefits in this sample scenario is given by 
() ( ) ( ) 0
0 0
() () ()
0 11
1
(X) , (X) , (X)
x
j rT j j
t x xt T T
t
v e pq w t d t
ω−
−
− +−
=
=⋅ + ⎡ ⎤ ∑ ⎣ ⎦ . 
Hence, ( ) ∑ ( ) =
= J
j
i v
J
V 1
( )
0 0
1 (X) (X) is a Monte-Carlo estimate for the value of the contract 
with J denoting the number of simulations. 
At the end of each year the policyholder can decide what amount to withdraw from 
the account. In Milevsky and Salisbury (2006) the authors prove that within their 
model an optimal strategy for a GMWB contract can only be achieved by withdrawing 
either nothing or the guaranteed annual withdrawal amount or the total account 
value. In contrast to a GMWB, for a GLWB withdrawing nothing can never be optimal 
unless roll-ups or step-ups are included. Therefore in an optimal strategy, the policyholder can only withdraw the guaranteed amount or surrender the contract. 
The property that optimal strategies can only be achieved by withdrawing the guaranteed annual withdrawal amount or the total account value also holds within our 
model: First, a withdrawal below the guaranteed annual withdrawal amount can never 
be optimal since no adjustments are made for future withdrawal guarantees in this 
case. Hence, when withdrawing less than the guaranteed annual withdrawal the future guarantees are the same than when withdrawing the full guaranteed amount. 
However, in the latter case, the account value is lower and thus the value of future 
withdrawal guarantees is higher. Furthermore, if a GMDB is included, the so-called 
additional death benefit, i.e. the part of the death benefit that exceeds the fund value, 
is reduced. Due to the martingale property of the underlying asset process and the 
guarantee fee that is deducted from the account value, the value of the additional 
death benefit is never greater than the withdrawal amount itself. Second, if it is optimal for the policyholder to withdraw more than the guaranteed annual withdrawal 
amount, than it has to be optimal to completely surrender the contract since all 
changes of the state variables occur on a pro-rata basis only. 
In the case of surrender, the policyholder receives the account value after deduction 
of surrender charges; in return he waives all claims arising from the GLWB-option, 
i.e. the lifelong guaranteed annual withdrawals and future death or surrender benefits. 
 
6
 For an introduction to Monte Carlo methods see, e.g., Glasserman (2003). 
Thus, under optimal behaviour, the policyholder would withdraw exactly the annual 
guaranteed amount each year until the value of the underlying fund less surrender 
fee exceeds the expected value of future benefits. Then, he would surrender the contract. 
We now describe how optimal policyholder strategies can be found using MonteCarlo simulations. The task is to maximize a contract’s value by surrendering at an 
optimal point of time allowing for Ft-measurable strategies only. 
We call 0
0
2 1 1 ... x KK K R xω
ω
− − − = ×× ⊆ − an exercise strategy. Following this strategy, the 
contract is surrendered at time t if and only if the contract has not been surrendered 
before and At ∈ Kt
− , i.e. 
1 ( ) = 1 −
K At t
 and 1 ( ) = 0 −
K Au u
 ∀u ∈{1,...,t −1}. 
The value of the contract under some given strategy K is then given by 0 V K( ) as 
defined above. For this given strategy, the contract is surrendered at the stopping 
time 0 ( ): inf{ {1,..., 1}| } K t t τ ω t x AK − = ∈ −− ∈ or not surrendered at all, i.e. τ ω ( ): K = − x0 , if 
At ∉ Kt
− ∀t ∈{1,...,ω − x0 −1}. This value can be easily calculated by Monte Carlo 
methods. 
In what follows we explain how an optimal strategy can be approximated. Obviously, 
an optimal strategy has to be of the form 2
1 1 0
0 [ , ) ... [ , ) − − = ∞ − − ∞ ⊆ x K k x x k x Rω
ω : if it is optimal to surrender at some fund value, it has to be optimal to surrender at any higher 
fund value, as well, since a higher fund value leads to a higher surrender value if the 
contract is surrendered, and a lower value of future guarantees as well as a higher 
future guarantee fee if the contract is not surrendered. Analogously, if it is optimal not 
to surrender the contract at a given value, it is also optimal not to surrender at any 
lower fund value. For the determination of the optimal surrender boundaries
1 1 0 ,..., −x − k kω we use the following backward induction algorithm: 
First, we determine the optimal strategy at time t = ω - x0 - 1 by maximizing the contract value following a given strategy 0 1 [ ,) x kω− − ∞ for 0x 1 kω− − . Second, we determine 
some optimal strategy at t = ω - x0 - 2 by maximizing the contract value following a 
given strategy 0 0 2 1 [ ,)[ ,) x x k k ω ω −− −− ∞× ∞ for 0x 2 kω− − , etc. Thus, by repeatedly maximizing 
the contract value for the optimal surrender boundaries, we are able to determine 
optimal stratefies. 
5 Results 
We use the numerical methods presented in Section 4 to calculate the risk-neutral 
value of variable annuities including GMWB or GLWB guarantees for a given guarantee fee ϕ . We call a contract and the corresponding guarantee fee fair if the contract’s risk-neutral value equals the single premium paid, i.e. if P =V 0 =V 0 ( ) ϕ . 
Unless stated otherwise, we use a risk-free rate of interest r of 4%, a volatility σ of 
15%, and a single premium P = 10,000. Furthermore, we let the age of the insured x0
= 65, and the surrender fee s =10%. Moreover, we use best estimate mortality tables 
of the German society of actuaries (DAV 2004 R) for a male insured. 
5.1 Determination of the Fair Guarantee Fee 
To illustrate how the fair guarantee fee can be derived within our framework, in a first 
step, we analyze the influence of the guarantee fee on the value of contracts for 
three different kinds of GLWB guarantees. Contract 1 contains a plain vanilla guarantee, some guaranteed annual withdrawal amount of 5% of the single premium, contract 2 contains a roll-up at a rate of i = 6% for a maximum of 5 years, whereas an 
annual step-up is considered in contract 3. We assume deterministic customer behavior: For contract 1 and contract 3, the insured withdraws the guaranteed annual 
amount of 500 - beginning immediately in the first year of the contract; for contract 2, 
we assume that the insured person does not access his guaranteed amount for the 
first five years and then starts to withdraw the guaranteed amount of 669 per annum 
(which has been increased due to the roll-up feature). For all three versions, we assume that the contract is not surrendered. 
Figure 1 shows the corresponding contract values as a function of the annual guarantee fee. 
Figure 1 Contract values as a function of the guarantee fee for different versions of GLWB 
For contract 1, the contract value equals 10,000 at a guarantee fee of 43, thus this is 
the fair guarantee fee. For contracts 2 and 3, the fair guarantee fee amounts to 48 
bps and 80 bps, respectively. 
5.2 Fair Guarantee Fees for Different Contracts 
In this section we analyze contracts with different GLWB-versions. We start with contracts containing a roll-up feature and then move on to contracts with different stepup / ratchet features. 
5.2.1 GLWB with Roll-Up 
In this section, we analyze and compare three different contracts. Contract 1 guarantees lifelong withdrawals of 5% of the initial premium (no roll-up). Contract 2 provides 
an annual increase of the guaranteed withdrawal amount of 6% for a maximal period 
of 5 years, as long as no withdrawals are made. The third contract comes with a 5% 
roll-up rate and a roll-up period of 10 years. We consider all three contracts with and 
without a money-back GMDB option. 
We assume the following policyholder behavior: In contract 1 the policyholder withdraws 5% of the initial premium up to his death starting immediately. For contract 2 
and 3 the insured starts the withdrawals of 669 and 814, respectively at the end of 
the roll-up period (5 and 10 years, respectively) and then withdraws annually and lifelong the corresponding guaranteed annual withdrawal amount. 
Table 1 shows the fair guarantee fee for these three contracts with and without an 
additional GMDB option. 
no roll-up 6% roll-up benefit for 5 
years 
5% roll-up benefit for 
10 years 
 contract 
strategy w/o DB with DB w/o DB with DB w/o DB with DB
Withdrawals of guaranteed amount starting at 
the end of roll-up period 
43 bps 48 bps 47 bps 52 bps 28 bps 35 bps 
Table 1: Fair guarantee fee for GLWB contracts with roll-up 
The results show that it is not always optimal to postpone withdrawals until the end of 
the roll-up period even if guaranteed annual withdrawal amounts are increased in this 
case. The value of contract 3 under the assumed strategy is significantly lower than 
the value of contract 1. On the one hand, a roll-up rate exceeding the risk free rate 
leads to an increase in the value of the guarantee if withdrawals are postponed. On 
the other hand however, the insured becomes older during the waiting period. With 
increasing age, the expected number of withdrawals until death decreases and so 
does the value of the guarantee. Apparently, for our third contract, the latter effect is 
dominant. 
The additional fee for death benefit (difference between columns “with DB” and “w/o 
DB”) increases as we move from contract 1 to 2 and 3. This is due to the fact that 
every withdrawal leads to a reduction of the GMDB value. Since we assume fewer 
and later withdrawals in contracts 2 and 3, the corresponding GMDB option is more 
valuable. 
5.2.2 GLWB with ratchet guarantee 
For the analysis of contracts with step-up feature, we again compare three different 
GLWB contracts. Contract 1 has no step-up feature and thus coincides with contract 
1 from the previous subsection. In contract 2 a step-up is possible every 5th anniversary of the policy following the rules described in section 3. Finally, contract 3 comes 
with an annual step-up. Each of the contracts is analyzed with and without an additional money-back GMDB. 
We assume the policyholder to annually withdraw the guaranteed amount until death 
(no surrender). If the guaranteed amount is increased by a step-up, we assume that 
the policyholder immediately increases the annual withdrawal amount to the new 
guaranteed amount. 
The fair guarantee fees of the contracts are shown in Table 2. 
 contract no step-up 5 year step-up annual step-up 
strategy 
w/o DB with DB w/o DB with DB w/o DB with DB
Withdrawals of guaranteed amount beginning in 
year 1 
43 bps 48 bps 55 bps 62 bps 80 bps 88 bps 
Table 2: Fair guarantee fee for GLWB contracts with different step-up features 
Obviously the step-up feature provides additional value for the policyholders. Our 
analysis shows that the more frequently step-ups are provided, the higher the value 
of the feature and thus the fair guarantee fees are. 
The additional fee for the death benefit (difference between columns “with DB” and 
“w/o DB”) is roughly equal for all three contracts (about 10% of the fair fee without 
GMDB). The effect observed in section 5.2.1 for contracts with roll-up can not be 
found here, since in scenarios where the GMDB option is in the money (declining 
fund values), the three contracts develop similarly. 
5.3 Sensitivity Analysis with respect to the Guaranteed Annual Withdrawal Amount 
In this section, we look at the influence of the annual maximum guaranteed withdrawal amount on the fair guarantee fee for the plain vanilla GLWB contract (i.e. neither a roll-up nor a step-up is included). We consider annual withdrawal amounts of 
xWL=3%, xWL=4%, xWL=5%, and xWL=6%. The fair guarantee fees are displayed in 
Table 3. 
 contract 
strategy 
xWL = 3% xWL = 4% xWL = 5% xWL = 6% 
Withdrawals of guaranteed amount annually 
beginning in year 1 
3 bps 12 bps 43 bps 117 bps 
Table 3: Influence of the maximum annual withdrawal amount on the fair guarantee fee 
for a GLWB contract 
The maximum annual withdrawal amount notably influences the fair guarantee fee. 
Rather low annual withdrawal rates of 3% lead to a low fair guarantee fee of 3 bps, 
while a fee of 117 bps is necessary to back a GLWB option with 6% annual withdrawals. Unlike in a GMWB contract, the total withdrawal amount is not restricted. As 
a consequence, the influence of the annual maximum withdrawal amount in a GLWB 
contract is considerably higher than in a GMWB contract. For more details on the 
comparison of GMWB and GLWB see Section 5.7. 
5.4 Sensitivity Analysis with respect to the Insured’s Age 
In the previous sections we assumed the insured to be 65 years old. We now determine the influence of the age on the contract value. In particular with respect to lifelong guarantees, the age is of significant influence on the contract value, since mortality rates roughly increase exponentially in age. We calculate contract values for 
insured persons aged 55, 65, 75, 85 and 95 years, respectively. The policyholder’s 
strategy is assumed to be the same in all contracts, namely lifelong withdrawals of 
the guaranteed annual amount from the beginning of the contract and no surrender. 
Table 4 shows the fair guarantee fees for these contracts. 
 Age 
strategy 
55 65 75 85 95 
Withdrawals of guaranteed amount annually 
(500) beginning in year 1 
105 bps 43 bps 11 bps ~0.5 bps ~0.05 bps 
Table 4: Fair guarantee fee for contracts with GLWB under different ages of the insurant 
Since withdrawals are guaranteed lifelong, the fair guarantee fee is decreasing in the 
insured’s age within the considered age interval. While the fair guarantee fee for a 55 
year old amounts to 105 bps it decreases to less than 1 bp for an 85 or 95 year old 
person. These results explain why most of the current GLWB products require a 
minimum age of 60 years when withdrawals start. Some alternative to requiring for a 
minimum age would be to link the guaranteed annual withdrawal amount to the age 
at with withdrawals are actually started. 
 
Thus, we now fix a guarantee fee of 50 bps and determine the fair withdrawal rate for 
different ages, i.e. the withdrawal rate for which the contract’s risk-neutral value coincides with the premium paid. The fair withdrawal rates are displayed in Table 5. 
 age 
strategy 
55 65 75 85 95 
Withdrawals of guaranteed amount annually 
beginning in year 1 
4.4% 5.2% 6.6% 9.2% 13.4% 
Table 5: Fair withdrawal rate for GLWB contracts for a guarantee fee of 50 bps and different ages 
Obviously, for the same fee, higher withdrawal rates can be guaranteed to older people. Whilst for a 55 year old only an annual withdrawal amount of 440 can be guaranteed, this amount increases to 1340 for a 95 year old. 
5.5 Analysis of the Longevity Risk 
As mentioned above, mortality rates are an important factor for the calculation of 
such contracts. So far, we used the mortality table DAV 2004R for our calculations. 
An increase of longevity that exceeds the trend embedded in this table would have a 
negative impact on the insurer’s profitability. To analyze this risk we calculate the fair 
guarantee fee assuming different mortality probabilities. Table 6 gives the fair guarantee fee for the plain vanilla GLWB contract for different ages assuming the mortal-
ity table DAV 2004R as above and additionally under the assumption that mortality 
rates drop to 70% of the rates given in this table. 
 age 
mortality table 
55 65 75 85 95 
DAV 2004R 105 bps 43 bps 11 bps ~0.5 bps ~0.05 bps 
70% of DAV 2004R 138 bps 58 bps 20 bps ~1.5 bps ~0.05 bps 
Table 6: Fair guarantee fee of a GLWB contract for different ages and different mortality 
scenarios 
The results show that the value of lifelong withdrawal guarantees is rather sensitive 
with respect to longevity. For a 55-year old, the fair guarantee fee increases by almost one third to 138 bps, and for an 75-year old, the fair guarantee fee doubles if 
mortality rates drop by 30%. 
5.6 Sensitivity Analysis with respect to Capital Market Parameters 
In this section we analyze the influence of the capital market parameters r and σ on 
the contract value. Up to now we based our calculations on the assumption of r=4% 
and σ=15%. We consider the plain vanilla GLWB contract assuming a customer who 
withdraws the guaranteed annual amount and does not surrender. We vary the riskfree rate of interest r as well as the volatility σ .
Table 7 shows the fair guarantee fee for different combinations of the capital market 
parameter values. 
 risk-free rate 
volatility 
r=3% r =4% r =5% 
σ = 10% 48 bps 19 bps 7 bps 
σ = 15% 85 bps 43 bps 20 bps 
σ = 20% 124 bps 69 bps 41 bps 
Table 7: Influence of the capital market parameters r and σ on the fair guarantee fee for 
a GLWB contract 
As expected, the fair guarantee fee is decreasing in the risk-free rate of interest and 
increasing in the volatility since, on the one hand, the risk-neutral value of a guarantee decreases with increasing interest rates; and, on the other hand, options are 
more expensive when volatility increases. Changes in volatility have a tremendous 
impact on the option values and, thus, on the fair guarantee fee. 
At inception of the contract and with some products also during the term of the contract, the insured has the possibility to influence the volatility by choosing the underlying fund from a predefined selection of mutual funds. Since for some products offered 
in the market the fees do not depend on the fund choice, this possibility presents another valuable option for the policyholder. For any risk-free rate r, the fair guarantee 
fee for σ = 20% is more than twice as high as the fee for σ =10%. Thus, one important risk management tool for insurers offering variable annuity guarantees is the 
strict limitation and control of the types of underlying funds offered within these products. 
An alternative would be to link the guaranteed annual withdrawal amount to the 
fund’s expected volatility. One insurer gives a guaranteed annual withdrawal amount 
of 5% of the single premium paid for three different funds with different stock ratios 
between. However, the fee increases in the fund’s stock ratio. Besides, a fourth fund 
with an even higher stock ratio is offered. However, the guaranteed annual withdrawal amount is reduced to 4.5% if this fund is chosen. 
Therefore, in a next step we determine the fair withdrawal rate for different capital 
market parameters for a guarantee fee of 50 bps. The results are shown in Table 8. 
 risk-free rate 
volatility 
r=3% r =4% r =5% 
σ = 10% 4.9% 5.7% 6.6% 
σ = 15% 4.6% 5.2% 5.8% 
σ = 20% 4.1% 4.7% 5.1% 
Table 8: Influence of the capital market parameters r and σ on the fair withdrawal rate 
for a GLWB contract (guarantee fee 50 bps) 
Obviously, for a given guarantee fee the fair withdrawal rate is increasing in the riskfree rate of interest and decreasing in the volatility. 
5.7 Comparison of GLWB and GMWB 
As mentioned above, GLWB-options are a recent variation of GMWB-products. In 
what follows, we compare the two product types. 
In a first step, we analyze the value of a contract with GLWB under different withdrawal rates. The values for contracts under the withdrawal rates 3%, 4% and 5% as 
a function of the annual guarantee fee are shown in Figure 2. 
Figure 2 Value of GLWB contracts as a function of the annual guarantee fee 
The three curves are nearly parallel. The results show, as expected, that the contract 
is significantly more valuable for a higher annual withdrawal rate. 
In a second step, we analyze the influence of the annual withdrawal rate on a GMWB 
contract. Figure 3 displays the contract values for withdrawal rates of 5%, 6% and 
7%. 
Figure 3 Value of GMWB contracts as a function of the annual guarantee fee 
For small guarantee fees, the contract values are very close; only for higher guarantee fees, the gap between the different contracts increases and the contract with a 
withdrawal rate of 7% is significantly more valuable than the ones with lower rates. 
The obvious difference between Figure 2 and Figure 3 is due to the different structure 
of the GMWB and GLWB options. In a GMWB the total withdrawal amount is limited 
(for example by the initial premium); a higher annual withdrawal rate in a contract 
with GMWB results in a lower number of withdrawals. By contrast, high withdrawals 
that are guaranteed within a GLWB are guaranteed until death and therefore increase the value of the option significantly. 
Finally, we compare the fair withdrawal rate within the GLWB and the GMWB option 
for given guarantee fees. As a policyholder’s strategy we assume that the annual 
guaranteed amount is withdrawn until death within a GLWB and until the total withdrawal amount has been reached within a GMWB. For the analysis we choose a 
guarantee fee of 12 bps, which is the fair guarantee fee for a common product in the 
US-market, a 7% GMWB; further, we examine the fair guarantee fee for the GLWB 
with a withdrawal rate of 5%, which is 43 bps. 
The results are shown in Table 9. 
 Benefit 
Guarantee fee 
Guaranteed Lifetime Withdrawal 
Benefit 
Guaranteed Minimum Withdrawal 
Benefit 
12 bps 4.0% 7.0% 
43 bps 5.0% 12.5% 
Table 9: Fair withdrawal rate for GLWB and GMWB under different guarantee fees 
For the guarantee fee of 12 bps, the fair withdrawal rate of a GLWB-option is 4%. 
This means, for the same guarantee fee the policyholder can withdraw 400 annually 
within a GLWB and 700 in a GMWB. Furthermore, a contract with 5% GLWB corresponds to a GMWB contract with 12.5% guaranteed annual withdrawal. 
This valuation is of relevance, as some insurers offer their clients the choice between 
a GMWB and a GLWB with different withdrawal rates. 
5.8 Results under Optimal Customer Behavior 
In this last subsection, we show the results for optimal customer behavior that have 
been derived using the methods described in Section 4. First we calculate the 
bounds t k for the optimal strategy in a contract that contains a GLWB for a guarantee 
fee of 50 bps. 
Figure 4 displays the bounds t k , which start at about 18,700 € in the first year and 
decrease slightly in the beginning and stronger as the insured’s age increases. 
Figure 4 Optimal Surrender Strategy for a GLWB contract and a guarantee of 50 bps 
The fair guarantee fee under optimal policyholder behavior amounts to 49 bps. This 
is slightly lower than the current fees of most insurance companies for this benefit. It 
is notable that the fair guarantee fee under optimal customer behavior differs only 
slightly from the fair fee assuming deterministic behavior (annual withdrawal, no surrender). Bauer et al (2006) found much larger differences between deterministic and 
optimal client behavior for GMAB, GMIB and GMWB products. The reasons for this 
is, as we have seen above, that in GLWB products, the client has fewer choices than 
in other products since optimal behavior is always characterized by either withdrawing the guaranteed amount or surrendering the contract. 
6 Summary and Outlook 
Guaranteed lifelong withdrawal benefits are the latest innovation in the variable annuity market. The products are very popular since they cover longevity risk like a regular 
annuity but combine this feature with a permanent availability of the remaining account value (if positive). 
However, our analyses have shown that such products are rather risky for the insurer: Whilst these products are much less sensitive with respect to client behavior 
than other guarantees typically embedded in variable annuities (cf. Bauer et al. 
(2006)), the sensitivity with respect to changes in interest rates and fund volatilities as 
well as mortality rates is significant. This is particularly dangerous considering the 
long time horizon of the products and the fact that according to market survey (cf. 
Lehman Brothers (2005)) often only delta risk is hedged.
Since our asset model is rather simple, a worthwhile extension might be an analysis 
of such products in a Lévy-type framework with stochastic interest rates. Also, in particular for GLWB products, it would be interesting to see how our results change in a 
model with stochastic mortality rates (cf. e.g. Cairns et al. (2005) or Bauer et al. 
(2007)). 
References 
Aase, K.K. und Persson, S.A. (1994): Pricing of Unit-Linked Insurance Policies. 
Scandinavian Actuarial Journal, 1, 26-52. 
Anderson, L. (1999): A Simple Approach to the Pricing of Bermudan Swaptions in the 
Multi-factor Labor Market Model. Journal of Computational Finance, 3, 5–32. 
Bauer, D.; Kling, A. and Russ, J. (2006): A Universal Pricing Framework for Guaranteed Minimum Benefits in Variable Annuities. Working Paper, Ulm University. 
Bauer D.; Börger M.; Ruß, J. and Zwiesler, H-J. (2007): The Volatility of Mortality. 
Working Paper, Ulm University. 
Bingham, N.H. und Kiesel, R. (2004): Risk-Neutral Valuation – Pricing and Hedging 
of Finanicial Derivatives. Springer Verlag, Berlin. 
Cairns, A.J., Blake, D., Dowd, K., 2005b. Pricing Death: Frameworks for the Valuation and Securitization of Mortality Risk. ASTIN Bulletin, 36:79–120. 
Dahl, M., Møller, T., (2006): Valuation and hedging life insurance liabilities with systematic mortality risk. Insurance: Mathematics and Economics, 39, 193-217. 
Glasserman, P. (2003): Monte Carlo Methods in Financial Engineering. Series: 
Stochastic Modelling and Applied Probability, Vol. 53. Springer Verlag, Berlin. 
Lehman Brothers (2005): Variable Annuity Living Benefit Guarantees: Over Complex, 
Over Popular and Over Here? European Insurance, 22. April 2005. 
Milevsky, M. und Salisbury, T.S. (2006): Financial valuation of guaranteed minimum 
withdrawal benefits. Insurance: Mathematics and Economics: 38, 21-38. 
Møller, T. (2001): Risk-minimizing hedging strategies for insurance payment processes. Finance and Stochastics, 5, 419-446. 
Sloane, W. R. (1970): Life Insurers, Variable Annuities and Mutual Funds: A Critical 
Study. Journal of Risk and Insurance, 37, S. 99. 