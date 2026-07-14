# Generic Index-Linked Lifetime-Income Case Study

## Purpose and terminology

This repository models an illustrative Australian single-premium lifetime-income
contract. It is a generic research case study, not a representation of a current
insurer offer and not advice. A **policyholder** is the insured person. A
**model point** is one representative insured person used in the numerical
portfolio.

The contract has two irreversible phases:

1. **Growth phase.** The account value participates in an annually protected,
   capped return. The policyholder may elect income once per policy year after
   at least one full growth year.
2. **Income phase.** A fixed nominal lifetime-income amount is locked at the
   election date. The same protected reference fund continues to determine the
   account value. Positive later performance does not ratchet the locked income.

The automatic backstop starts income at the first anniversary after age 100 if
the policyholder has not elected earlier.

## Core product parameters

| Feature | Case-study convention |
|---|---|
| Premium | Single premium in AUD |
| Reference fund | 30% Global Equity, 70% nominal Australian government bonds |
| Rebalancing | Monthly to the 30/70 target |
| Bond sleeve | Rolling five-year constant-maturity government-bond proxy |
| Annual protection | Total protection: negative annual reference-fund returns credit 0% |
| Base maximum return | 6.00% per crediting year |
| Guaranteed minimum cap | 0.25%; this is a floor on the announced cap, not a minimum credited return |
| Income election | Once at a policy anniversary, irreversible |
| Income | Fixed monthly lifetime income, paid in arrears |
| Growth withdrawals | Prohibited |
| Income withdrawals | Partial/excess or full withdrawal subject to the contract rules |
| Customer fees | 0.30% product fee plus 1.15% lifetime-income premium per year |
| Spouse continuation | Optional at income election; lower initial rate and last-survivor coverage |

The product-level 30% equity allocation is authoritative. Legacy allocation
columns retained in source model-point files are validated for provenance but do
not drive the generic reference fund.

## Reference-fund return

The equity and bond sleeves are combined before protection is applied. For one
month,

$$
R^{\mathrm{fund}}_{m}=0.30R^{\mathrm{equity}}_{m}+0.70R^{\mathrm{bond}}_{m}.
$$

The sleeves are reset to their targets after each monthly return. The annual
point-to-point reference return is compounded from the twelve monthly fund
returns. Protection is never applied separately to the equity and bond sleeves.

The Global Equity index is treated as an AUD-denominated or AUD-hedged total
return index. The bond sleeve contains no credit spread, default, migration,
inflation-linkage or transaction-cost model.

## Annual crediting

For crediting year $y$, let $R_y^{\mathrm{fund}}$ be the full annual reference-fund
return and $C_y$ the cap announced by the insurer. The contractual simple
credit is

$$
g_y=\min\left(\max\left(R_y^{\mathrm{fund}},0\right),C_y\right).
$$

A 0.25% guaranteed minimum cap means $C_y\ge 0.0025$. It does not prevent a
0% credit when the reference fund falls. The active base case uses a 6% cap;
the optimisation studies allow the insurer to reset the cap annually on the
predeclared admissible grid.

The complete reference-fund return is formed first, then the floor and cap are
applied. This ordering is essential because the contract protects one combined
investment option.

## Account-value and anniversary order

The monthly projector maintains the account value, the fee subledger, the
credited-return frame, the income base and in-force/life states. At a policy
anniversary the economically relevant order is:

1. complete the old crediting year and apply its protected credit;
2. post accrued product and lifetime-income fees;
3. process mortality and any contractual survivor treatment;
4. permit the eligible growth-to-income election on the post-fee account value;
5. announce the cap for the new crediting year and purchase its hedge;
6. process eligible income-phase voluntary actions;
7. continue monthly income and account-value movements.

The precise implementation is in
[`projection.py`](../code/policy_engine/projection.py). Management decisions may
use only information observable before the new cap is chosen.

## Growth phase and income election

No partial, excess or full withdrawal is permitted during growth. At each
eligible anniversary the policyholder may either wait one further year or start
income. Election is irreversible and does not change the reference-fund
allocation.

The initial annual income equals the post-fee account value at election times a
rate from the case-study rate card. The rate depends on the rating age/life
basis and includes an additive deferral increment for each completed growth
year. The fixed annual amount is then paid monthly in arrears.

Positive credits after election increase the account value but do not increase
locked income. This asymmetry is central to behaviour: a higher cap is generally
more valuable while the policyholder remains in growth, while in income the
only direct way to realise a high account value may be a voluntary withdrawal.

## Income funding and guarantee claim

Monthly income is funded from the account value while funds remain. Once the
account value is exhausted, covered income continues and the shortfall is an
insurer-funded guarantee claim. Account-value-funded customer payments are
investment-component cashflows and are not deducted a second time in the
insurer CSM proxy.

## Withdrawals in income

An income-phase partial withdrawal is an excess withdrawal in addition to the
scheduled income. It reduces the account value immediately and reduces future
locked income proportionally to the complete account-value deduction. The
case-study minimum transaction amount is AUD 100 and the remaining account
value must be at least AUD 2,000.

A full withdrawal terminates the lifetime-income guarantee. The cash surrender
benefit is the post-fee account value less any applicable market value adjustment
(MVA). Exhaustion through scheduled income is not a surrender: the guarantee
continues after ordinary exhaustion.

The MVA is a bounded proxy during the first ten policy years. It can only reduce
the withdrawal payment and cannot exceed its withdrawal base.

## Death and spouse continuation

In growth, death pays the positive post-fee account value and terminates the
contract. In income, a single-life contract similarly pays any positive account
value. If spouse continuation was elected, death of the primary life follows the
selected contractual path:

- **continue income:** the fixed amount continues while the spouse survives;
- **lump sum:** the positive account value is paid and the contract terminates.

The last-survivor death terminates continuing spouse income. Death benefits are
not subject to MVA.

## Insurer hedge and backing assumption

Customer money is assumed to be held in a money-market backing account. The
insurer receives the pathwise money-market return; the customer receives the
contractual protected reference-fund credit instead.

The standard hedge is a bull call spread purchased in the capital market: the
insurer buys the lower-strike call and sells the call at the customer cap. It
does not sell options to the policyholder. Raising the cap makes the sold call
less valuable and therefore increases the net hedge cost. In the explicit
`not_sold` research alternative, the insurer keeps reference performance above
the customer cap, but this is not the standard base case.

Annual new-issue hedge prices use the exact path-congruent `mc_conditional`
hedge-price cache. `moment_matched_bs` is an explicitly selected proxy only;
the under-year DVA mark remains a separate moment-matched proxy.

## Model boundaries

The case study omits tax, reinsurance, credit risk, FX risk, tactical asset
allocation, transaction costs and a calibrated physical rate-risk premium. Its
mortality and dynamic-behaviour assumptions are research proxies. Results must
therefore be described as model outputs under stated assumptions, not product
illustrations, calibrated forecasts or recognised IFRS 17 amounts.
