# Crediting Rate Cap: Profitability, Liability Value and Capital

**Date:** 12 July 2026  
**Scope:** insurer perspective in the generic case study; not an actual
offered product or rate card

## 1. Scope

This note describes the Cap's effects on insurer profitability, the present
value of liabilities less fee income, and capital. The implemented case-study
Cap is fixed at 6.00% p.a.; higher/lower references below are comparative
sensitivities, not alternative base-product settings. Customer utility,
competition and sales volumes are outside scope.

## 2. Product mechanics

- The Reference Fund is 50% Global Equity and 50% nominal Australian
  government bonds, rebalanced monthly.
- The full fund return is calculated before Total Protection and the Cap are
  applied.
- The annual credit is:

$$
c_y=\min\left(\max\left(R_y^F,0\right),C_y\right)
$$

- The Cap is constant at 6.00% p.a. in every Crediting Year. The contractual
  minimum-cap concept remains 0.25% p.a.; it is not a minimum annual credit.
- Product Fee and Lifetime Income Premium accrue daily and are charged at the
  Anniversary or defined termination events. Only collected fees are insurer
  income.
- At Income Election, fixed income is based on post-fee Account Value. Later
  positive credits do not increase it.

## 3. Direct value effect

The simplified non-unit liability is:

$$
\mathrm{BEL}_{NU}(C)
=
\operatorname{PV}_Q\!\left(
\mathrm{Claims}+\mathrm{Expenses}+\mathrm{HedgeCosts}
\right)
-
\operatorname{PV}_Q\!\left(
\mathrm{ProductFees}+\mathrm{LIP}+\mathrm{CreditingMargin}+\mathrm{MVA}
\right)
$$

Before Risk Margin:

$$
\mathrm{Gross\ VNB}(C)=-\mathrm{BEL}_{NU}(C)
$$

The annual crediting package has value:

$$
p(C)
=
P(0,T)
+\operatorname{Call}(K=1)
-\operatorname{Call}(K=1+C)
$$

Its marginal Cap cost and current Crediting Margin are:

$$
\frac{\partial p(C)}{\partial C}
=
\operatorname{E}_Q\!\left[
D(0,T)\,\mathbf{1}_{\{R^F>C\}}
\right]
>0
$$

$$
\mathrm{CM}(C)=AV^{frame}\left[1-p(C)\right]
$$

A higher Cap therefore increases the fair value of the crediting package and
reduces the current Crediting Margin. A lower Cap has the opposite direct
effect. Over the full contract, the result also depends on future fees,
Guarantee Claims and capital.

The isolated measure PV(Guarantee Claims) minus PV(LIP) is insufficient because
it excludes Product Fee, Crediting Margin, expenses, hedge costs and capital.
VNB after Risk Margin and PVFP are separate measures; the same capital cost
must not be counted in both.

## 4. Phase-dependent effects

### Before Income Election

$$
I_0^{ann}=g(n)\,AV_{\mathrm{Election}}^{postfee}
$$

A higher Cap can increase both Election Account Value and guaranteed fixed
income. Future Account Value, fees, variable expenses and Guarantee Claims may
therefore scale together. There are no Guarantee Claims during Growth itself;
the effect arises after Election.

Whether this raises or lowers insurer value depends on the margin per additional
unit of Election Account Value. The direct reduction in current Crediting
Margin remains.

### After Income Election

Fixed income no longer increases with positive credits. A higher Cap then adds
Account Value without adding guaranteed income. This can extend fee collection,
delay Account Value exhaustion and reduce or defer Guarantee Claims.

The effect is material when Account Value is near exhaustion and a long income
period remains. It is small when Account Value is high, the Cap rarely binds,
or Account Value is already zero.

## 5. Summary of effects

| Component | Higher Cap | Lower Cap |
|---|---|---|
| Current crediting package | Higher value; lower current Crediting Margin | Lower value; higher current Crediting Margin |
| Fee income | Higher potential fee base and duration | Lower fee base and duration |
| Before Election | Higher Account Value and higher fixed income | Lower Account Value and lower fixed income |
| After Election | Larger Account Value buffer; later claims | Faster Account Value exhaustion; earlier claims |
| Variable expenses | Higher | Lower |
| Profit timing | More cost or lost margin early; possible later benefits | More current margin; lower later fee and claim benefits |
| Guarantee capital | May rise before Election and fall after Election | May fall before Election and rise after Election |
| Hedge exposure | Higher gross crediting exposure | Lower gross crediting exposure |

Collected fees reduce Account Value. Fee income and its effect on later
Guarantee Claims must therefore be valued in the same projection. Uncollected
fee accruals may be partly unrecoverable.

## 6. Capital

The capital effect is not monotonic:

- before Election, a higher Cap can increase fixed income and longevity or
  low-rate exposure;
- after Election, it can reduce guarantee moneyness and guarantee-tail capital;
- market and hedge capital depend on hedge effectiveness, collateral,
  counterparty exposure, basis risk and regulatory hedge recognition; and
- a lower Cap does not remove the 0% protection floor.

In the base product the 6.00% Cap remains fixed for current and future
Crediting Years. Any changing Cap schedule is a separately identified product
or sensitivity, not an automatic management action.

The repository capital model is an AGILE-specific research proxy, not an
APRA/LAGIC fund-level calculation for the new 50/50 product. It does not fully
represent actual assets, derivatives or residual hedge risks, and its capital
run-off is not a full annual stress revaluation.

## 7. Boundaries

- The numerical 6.00% Cap is a fixed case-study product input, not a market
  calibration or a conclusion from executable hedge quotes.
- Legacy pure-equity Caps are not transferable.
- Cap-dependent sales, lapse, Election and withdrawal responses are not
  empirically calibrated.
- Actual hedge quotes, transaction costs, collateral terms and an APRA/LAGIC
  capital model are unavailable.

This note documents comparative economic effects only. It does not assert
that 6.00% is a market-derived or commercially recommended Cap.

## 8. Internal references

- [Generic product design](./Produktdesign_Index_Linked_Lifetime_Income_Fallbeispiel.md)
- [Research engine methodology](../AGILE_Modelling_Engine/METHODOLOGY.md)
- [Repository instructions](../AGENTS.md)
