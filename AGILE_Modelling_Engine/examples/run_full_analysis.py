"""Legacy single-policy analysis: pricing, capital and sensitivities.

This is retained for research compatibility and is not the active generic
portfolio workflow. Use ``portfolio_simulations/run_portfolio_valuation.py``
for the repository policyholder model points.

Usage:
    python examples/run_full_analysis.py [--model MODEL] [--paths N]
                                         [--sensitivities] [--fast]

Models: heston_hull_white (default), heston, hull_white_bs, black_scholes.
Outputs a console report and CSV files in examples/output/.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import replace

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agile_engine import (DEFAULT_COST_ASSUMPTIONS_PATH,
                          DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
                          DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH,
                          DEFAULT_MODEL_PARAMETERS_PATH,
                          MortalityTable, PolicySpec, ProfitabilitySettings,
                          ValuationSettings, analyse_profitability,
                          compute_capital, fair_lifetime_income_premium, greeks,
                          load_cost_assumptions,
                          load_dynamic_behaviour_assumptions,
                          load_market_assumptions,
                          run_sensitivities, value_contract)


def build_inputs(cost_path=DEFAULT_COST_ASSUMPTIONS_PATH,
                 assumption_set_id=None,
                 behaviour_directory=DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
                 behaviour_assumption_set_id=None,
                 curve_path=DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH,
                 model_parameters_path=DEFAULT_MODEL_PARAMETERS_PATH):
    """Base case: CSV-sourced market data, costs, behaviour and PDS caps,
    65-year-old male, AUD 100k, 100% Australian Equity Total Protection,
    dynamic income take-up, lapse and withdrawals from the behaviour CSVs."""
    market = load_market_assumptions(curve_path, model_parameters_path)
    esg = market.esg
    mortality = MortalityTable.gompertz_makeham()   # ILLUSTRATIVE ALT-like basis
    costs = load_cost_assumptions(
        cost_path, assumption_set_id=assumption_set_id
    )
    behaviour_assumptions = load_dynamic_behaviour_assumptions(
        behaviour_directory,
        assumption_set_id=behaviour_assumption_set_id,
    )
    product = costs.product                         # CSV fees/MVA + PDS caps
    policy = PolicySpec(age=65, income_start_year=5)
    behaviour = behaviour_assumptions.behaviour
    expenses = costs.expenses
    return (esg, mortality, product, policy, behaviour, expenses, costs,
            behaviour_assumptions, market)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="heston_hull_white",
                    choices=["black_scholes", "heston", "hull_white_bs",
                             "heston_hull_white"])
    ap.add_argument("--paths", type=int, default=10_000)
    ap.add_argument("--sensitivities", action="store_true")
    ap.add_argument("--fast", action="store_true", help="reduced path counts")
    ap.add_argument("--cost-assumptions", default=str(DEFAULT_COST_ASSUMPTIONS_PATH),
                    help="path to cost_assumptions.csv")
    ap.add_argument("--cost-assumption-set", default=None,
                    help="assumption_set_id in the cost CSV")
    ap.add_argument("--behaviour-assumptions",
                    default=str(DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY),
                    help="directory containing the two behaviour CSVs")
    ap.add_argument("--behaviour-assumption-set", default=None,
                    help="assumption_set_id in the behaviour CSVs")
    ap.add_argument("--zero-curve",
                    default=str(DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH),
                    help="path to australian_zero_curve.csv")
    ap.add_argument("--model-parameters",
                    default=str(DEFAULT_MODEL_PARAMETERS_PATH),
                    help="path to model_parameters.csv")
    args = ap.parse_args()
    if args.fast:
        args.paths = min(args.paths, 4000)

    (esg, mortality, product, policy, behaviour, expenses, costs,
     behaviour_assumptions, market) = build_inputs(
        args.cost_assumptions, args.cost_assumption_set,
        args.behaviour_assumptions, args.behaviour_assumption_set,
        args.zero_curve, args.model_parameters)
    settings = ValuationSettings(model=args.model, n_paths=args.paths, seed=2026,
                                 horizon_years=None,
                                 projection=replace(costs.projection,
                                                    record_paths=False))
    outdir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(outdir, exist_ok=True)
    t0 = time.time()

    # ------------------------------------------------------------------ #
    # 1. Market-consistent valuation
    # ------------------------------------------------------------------ #
    val = value_contract(product, policy, esg, mortality, behaviour,
                         expenses=expenses, settings=settings)
    print(f"\n=== 1. Market-consistent valuation ({args.model}, "
          f"{args.paths:,} paths) ===")
    print(f"{'premium':32s}{val.premium:14,.0f}")
    for k in ("income_paid", "guarantee_claims", "death_benefits",
              "surrender_benefits", "fees_product", "fees_lip",
              "crediting_margin", "mva_retained", "hedge_costs", "expenses"):
        print(f"{'PV ' + k:32s}{val.pv[k]:14,.0f}")
    print(f"{'guarantee value (claims-LIP)':32s}{val.guarantee_value:14,.0f}")
    print(f"{'insurer net value (VNB gross)':32s}{val.insurer_net_value:14,.0f}")
    print(f"{'BEL non-unit':32s}{val.bel_nonunit:14,.0f}")
    print(f"{'identity gap':32s}{val.identity_gap:14.4%}")

    # fair Lifetime Income Premium (guarantee value-neutral)
    fair_lip = fair_lifetime_income_premium(product, policy, esg, mortality,
                                            behaviour, settings=settings)
    fair_label = f"fair LIP (charged {product.fees.lifetime_income_premium:.2%})"
    print(f"{fair_label:32s}{fair_lip:14.4%}")

    # market greeks
    g = greeks(product, policy, esg, mortality, behaviour, settings=settings,
               expenses=expenses)
    print(f"{'equity delta (% of P0 per 100%)':32s}{g['equity_delta_pct']:14.4f}")
    print(f"{'vega (per vol pt, % of P0)':32s}{g['vega_per_volpt']:14.4%}")
    print(f"{'rho (per 100bp, % of P0)':32s}{g['rho_per_100bp']:14.4%}")

    # ------------------------------------------------------------------ #
    # 2. Capital requirements (Solvency-II-style standard formula)
    # ------------------------------------------------------------------ #
    cap = compute_capital(product, policy, esg, mortality, behaviour,
                          expenses=expenses, settings=settings,
                          stresses=costs.capital_stresses)
    print("\n=== 2. Capital (SII-style standard formula) ===")
    for k, v in cap.scr_by_module.items():
        print(f"{'SCR ' + k:32s}{v:14,.0f}")
    print(f"{'SCR market (diversified)':32s}{cap.scr_market:14,.0f}")
    print(f"{'SCR life (diversified)':32s}{cap.scr_life:14,.0f}")
    print(f"{'BSCR':32s}{cap.bscr:14,.0f}")
    rm_label = f"risk margin (CoC {costs.capital_stresses.coc_rate:.1%})"
    print(f"{rm_label:32s}{cap.risk_margin:14,.0f}")

    # ------------------------------------------------------------------ #
    # 3. Profitability
    # ------------------------------------------------------------------ #
    prof = analyse_profitability(product, policy, esg, mortality, behaviour,
                                 expenses, settings=settings,
                                 prof_settings=costs.profitability,
                                 capital_result=cap,
                                 capital_stresses=costs.capital_stresses)
    print("\n=== 3. Profitability (real-world, CE reserving) ===")
    print(f"{'VNB after risk margin':32s}{prof.vnb_market_consistent:14,.0f}")
    print(f"{'new business margin':32s}{prof.new_business_margin:14.2%}")
    pvfp_label = f"PVFP @ {costs.profitability.hurdle_rate:.1%} hurdle"
    print(f"{pvfp_label:32s}{prof.pvfp_hurdle:14,.0f}")
    print(f"{'PVFP margin':32s}{prof.pvfp_margin:14.2%}")
    irr = "n/a" if prof.irr is None else f"{prof.irr:.2%}"
    print(f"{'IRR on distributable':32s}{irr:>14s}")
    print(f"{'payback year':32s}{str(prof.payback_year):>14s}")

    np.savetxt(os.path.join(outdir, f"profit_signature_{args.model}.csv"),
               np.column_stack([prof.years, prof.profit_signature,
                                prof.distributable, prof.bel_pattern,
                                prof.capital_pattern]),
               delimiter=",", header="year,profit_signature,distributable,"
               "bel_nonunit,required_capital", comments="")

    # ------------------------------------------------------------------ #
    # 4. Sensitivities of value and profitability
    # ------------------------------------------------------------------ #
    if args.sensitivities:
        print("\n=== 4. Sensitivities (bump & revalue, common random numbers) ===")
        sens_settings = ValuationSettings(model=args.model,
                                          n_paths=min(args.paths, 6000),
                                          seed=2026, horizon_years=None,
                                          projection=replace(costs.projection,
                                                             record_paths=False))
        df = run_sensitivities(product, policy, esg, mortality, behaviour,
                               expenses, settings=sens_settings,
                               prof_settings=costs.profitability,
                               capital_stresses=costs.capital_stresses)
        cols = ["scenario", "vnb", "guarantee_value", "pvfp_hurdle",
                "nbm_pct", "d_vnb", "d_pvfp"]
        print(df[cols].to_string(index=False,
                                 float_format=lambda x: f"{x:,.0f}"
                                 if abs(x) > 100 else f"{x:.2f}"))
        df.to_csv(os.path.join(outdir, f"sensitivities_{args.model}.csv"),
                  index=False)

    print(f"\nCost source: {costs.source_path} [{costs.assumption_set_id}]")
    print("Behaviour source: "
          f"{behaviour_assumptions.source_path} "
          f"[{behaviour_assumptions.assumption_set_id}]")
    print("Market sources: "
          f"{market.source_paths['curve']} [{market.curve_id}], "
          f"{market.source_paths['model_parameters']} "
          f"[{market.parameter_set_id}]")
    print(f"Done in {time.time() - t0:.1f}s. CSVs in {outdir}")


if __name__ == "__main__":
    main()
