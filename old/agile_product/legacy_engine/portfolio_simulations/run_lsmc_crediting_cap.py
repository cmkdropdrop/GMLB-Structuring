"""DEPRECATED research implementation of annual Crediting-Cap control.

When this file is executed it delegates to the canonical, monthly-engine-based
``optimize_crediting_rate_lsmc.py`` runner.  The legacy annual approximation
below is retained only for audit history and must not be used for results.
That canonical runner is a separate Stackelberg management-action study and
is intentionally outside the joint Income-Election/Surrender enhancement: its
customer response retains a fixed model-point Income Election.  Use
``run_lsmc_cap_behaviour_scenarios.py`` for Cap×Stress refits of the combined
Policyholder Behaviour policy.

LSMC-Optimierung des jaehrlichen Crediting-Rate-Caps (Storage-Stil).

Fragestellung
-------------
Der Versicherer darf zu Beginn jedes Policenjahres einen Cap (Maximum Return)
fuer das jaehrliche Point-to-Point-Crediting des generischen Produkts setzen.
Gesucht sind (a) die heutige optimale Cap-Entscheidung fuer das erste Jahr und
(b) der zugehoerige heutige Portfoliobarwert

    PV  =  PV(Claims) - PV(Fees),

alles unter dem risikoneutralen Mass mit pfadweisen stochastischen
Diskontfaktoren, projiziert bis der juengste versicherte Kopf des
Modellportfolios 120 Jahre alt ist, mit Sterblichkeit und dynamischem
Policyholder Behaviour (Income-Lapse und Excess Withdrawals reagieren auf die
Moneyness der Garantie und damit auf die Cap-Historie).

Oekonomische Definition des Ziel-PV
-----------------------------------
Claims und Fees werden bewusst vollstaendig gefasst, weil ein naives
"Guarantee Claims minus Bestandsgebuehren" das Optimierungsproblem entartet:
eine hoehere Gutschrift waere dann Gratisgeld (weniger Shortfall-Claims UND
mehr AV-basierte Fees), und der maximale Cap wuerde pfadweise dominieren.
Tatsaechlich muss der Versicherer die Gutschrift finanzieren; im Engine-Jargon
ist das die (negative) Crediting Margin.  Das Script bucht deshalb

    Claims := Guarantee Claims (Income-Zahlungen ueber das Account Value
              hinaus)  +  Crediting-Kosten (Gutschrift abzueglich der
              realisierten risikofreien Verzinsung des Deckungsvermoegens),
    Fees   := vereinnahmte Produkt-/LIP-Gebuehren  +  einbehaltene MVA.

Pfadweise gilt exakt (Teleskop-Identitaet der Kontodynamik, im Script als
numerischer Selbsttest mitgefuehrt):

    PV(Claims) - PV(Fees)  ==  PV(alle Leistungsauszahlungen) - Einmalpraemie.

Minimiert wird also der Barwert der Nettobelastung des Versicherers; das
"naive" PV(Guarantee Claims) - PV(Gebuehren) wird zu Transparenzzwecken je
Strategie zusaetzlich ausgewiesen.

Warum kein Standard-LSMC fuer amerikanische Optionen
----------------------------------------------------
Longstaff/Schwartz (2001) loest ein optimales STOPP-Problem: einmalige
Ausuebung, der Zustand ist rein exogen.  Hier liegt dagegen ein wiederholtes
Kontrollproblem mit ENDOGENEM Zustand vor: die Cap-Wahl jedes Jahres
veraendert Account Values, Moneyness und damit Behaviour aller Folgejahre --
strukturell dasselbe Problem wie die Bewirtschaftung eines Gasspeichers
(Kontrolle veraendert den Fuellstand).  Der Gasspeicher-Klassiker
Boogert/de Jong (2008) diskretisiert dazu den endogenen Zustand (Inventar) auf
ein Gitter; das ist hier nicht direkt moeglich, weil der endogene Zustand ein
Vektor je Modellpunkt-Kohorte ist und alle Kohorten durch den EINEN
portfolioweiten Cap gekoppelt sind.  Verwendet wird deshalb die fuer
Speicherprobleme etablierte Verallgemeinerung:

1.  Kontroll-Randomisierung (Kharroubi/Langrene/Pham 2014): der Trainings-
    Forward-Lauf streut zufaellige Cap-Pfade (Mischung aus "ohne Cap" --
    gemaess Aufgabenstellung --, konstanten Caps und i.i.d. Cap-Ziehungen),
    damit die Regression den endogenen Zustandsraum sieht.
2.  Backward Induction mit einer Q-Regression JE AKTION
    (Nadarajah/Margot/Secomandi 2017): je Jahr n und Cap c wird
    E[cf_n(c) + disc * V_{n+1}(s'(c)) | Zustand_n] auf Zeit-n-Features
    regressiert.  Entscheidungen benutzen ausschliesslich Zeit-n-Information
    (kein Look-Ahead); die Wertfunktion wird Tsitsiklis/Van-Roy-artig
    zurueckpropagiert, da der Folgezustand aktionsabhaengig ist.
3.  Optionale Policy-Iteration: erneuter Trainingslauf unter der
    epsilon-greedy Vorgaengerpolicy verbessert die Zustandsabdeckung.
4.  Out-of-Sample-Forward-Bewertung der Greedy-Policy auf frischen Pfaden:
    der berichtete PV ist der erwartungstreue Wert einer implementierbaren
    Policy und damit eine gueltige obere Schranke des Minimums (analog zur
    Lower-Bound-Logik von Longstaff/Schwartz beim Maximieren).

Cap-Gitter gemaess Vorgabe: {0.2%, 1%, 2%, ..., 20%}.  Hinweis: 0.2% liegt
UNTER dem kontraktuellen Guaranteed Minimum Cap von 0.25% des generischen
Produkts; das Gitter folgt bewusst der Forschungs-Vorgabe.

Modellvereinfachungen gegenueber der monatlichen Engine-Projektion
------------------------------------------------------------------
* Jahresgitter: Crediting, Gebuehren (ein Jahresfaktor statt ACT/365F-
  Subledger), Income (jaehrlich nachschuessig), Dekremente und Behaviour-
  Signale (am Jahrestag ausgewertet und im Jahr konstant gehalten) wie im
  archivierten agile_engine.lsmc.
* Joint-Life (Continue Income): Last-Survivor-Dekremente ab Ausstellung;
  die Election-Datums-Konditionierung der Portfolio-Engine entfaellt.
* Kein Intra-Year-DVA, keine Versichererkosten, keine Hedge-
  Transaktionskosten; Mindestbetraege fuer Teilentnahmen werden ignoriert.
* Take-up deterministisch gemaess Modellpunkt (wie im Portfolio-Runner);
  Growth-Phase kennt kontraktuell weder Lapse noch Entnahmen.
* Erwartungswert-Dekremente je Modellpunkt (keine Einzelleben-Simulation).

Es werden keine bestehenden Skripte oder Engine-Module veraendert; dieses
Script ist ein eigenstaendiger Runner im Stil von run_portfolio_valuation.py.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from numpy.typing import NDArray

if __package__:
    from ._run_logging import log_to_console
else:
    from _run_logging import log_to_console

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from agile_engine import (  # noqa: E402
    DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH,
    DEFAULT_COST_ASSUMPTIONS_PATH,
    DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
    DEFAULT_MODEL_PARAMETERS_PATH,
    DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH,
    FeeSpec,
    GENERIC_GUARANTEED_MIN_CAP,
    IndexLinkedLifetimeIncomeProduct,
    MortalityTable,
    ProjectionConfig,
    ReferenceFundSpec,
    __version__ as ENGINE_VERSION,
    load_cost_assumptions,
    load_dynamic_behaviour_assumptions,
    load_market_assumptions,
    load_policyholder_model_points,
)
from agile_engine.esg import Measure, STEPS_PER_YEAR, simulate  # noqa: E402
from agile_engine.product import (  # noqa: E402
    Index,
    SpouseDeathElection,
)

Array = NDArray[np.float64]

DEFAULT_OUTPUT_DIRECTORY = (
    Path(__file__).resolve().parent / "output" / "lsmc_crediting_cap"
)
LOGGER_NAME = "agile_engine.lsmc_crediting_cap_runner"

#: Cap-Gitter gemaess Aufgabenstellung: mindestens 0.2%, danach 1%..20%.
DEFAULT_CAP_GRID: Tuple[float, ...] = (0.002,) + tuple(
    round(0.01 * k, 10) for k in range(1, 21)
)

#: Sentinel fuer "ohne Cap" im Trainings-Forward-Lauf (Credit = max(R, 0)).
UNCAPPED_SENTINEL = 10.0

#: Cashflow-Legs eines Jahres (jeweils pro Pfad, AUD je Durchschnittsvertrag,
#: bewertet am Jahresende des Schrittes).
LEG_NAMES = (
    "claims",            # Guarantee Claims: Income ueber verfuegbares AV hinaus
    "credit_cost",       # Gutschrift minus realisierte Cash-Verzinsung des AV
    "fees",              # vereinnahmte Produkt- + LIP-Gebuehren
    "mva_retained",      # einbehaltene MVA aus Surrender/Excess Withdrawals
    "income",            # gesamte Income-Zahlungen (inkl. Claims-Anteil)
    "death",             # Todesfallleistungen (AV nach Gebuehren)
    "withdrawals",       # Barauszahlungen aus Excess Withdrawals
    "surrender",         # Barauszahlungen aus Income-Phase-Lapse
    "net_cost",          # claims + credit_cost - fees - mva_retained
    "outgo",             # income + death + withdrawals + surrender
)


# ---------------------------------------------------------------------------
# CLI / Logging (Konventionen des Portfolio-Runners)
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--model-points", type=Path,
                        default=DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH)
    parser.add_argument("--cost-assumptions", type=Path,
                        default=DEFAULT_COST_ASSUMPTIONS_PATH)
    parser.add_argument("--cost-assumption-set", default=None)
    parser.add_argument("--dynamic-behaviour", type=Path,
                        default=DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY)
    parser.add_argument("--behaviour-assumption-set", default=None)
    parser.add_argument("--zero-curve", type=Path,
                        default=DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH)
    parser.add_argument("--model-parameters", type=Path,
                        default=DEFAULT_MODEL_PARAMETERS_PATH)
    parser.add_argument(
        "--model",
        choices=("heston_hull_white", "hull_white_bs"),
        default="heston_hull_white",
        help="ESG mit stochastischen Zinsen (pfadweise Diskontfaktoren)",
    )
    parser.add_argument("--n-train", type=int, default=8_192,
                        help="Trainingspfade fuer die Backward Induction")
    parser.add_argument("--n-eval", type=int, default=16_384,
                        help="unabhaengige Bewertungspfade (Out-of-Sample)")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--heston-substeps", type=int, default=4)
    parser.add_argument("--chunk-paths", type=int, default=4_096,
                        help="ESG-Pfade je Simulationsblock (Speicher)")
    parser.add_argument("--ridge", type=float, default=1.0e-6,
                        help="Ridge-Parameter der Regressionen")
    parser.add_argument("--policy-iterations", type=int, default=2,
                        help="1 = reine Kontroll-Randomisierung; >=2 zusaetzliche "
                             "epsilon-greedy Policy-Iterationen")
    parser.add_argument("--exploration", type=float, default=0.30,
                        help="Explorationswahrscheinlichkeit ab Iteration 2")
    parser.add_argument("--mix-uncapped", type=float, default=1.0,
                        help="Gewicht der Trainingspfade ohne Cap (Vorgabe)")
    parser.add_argument("--mix-constant", type=float, default=1.0,
                        help="Gewicht der Trainingspfade mit konstantem Zufalls-Cap")
    parser.add_argument("--mix-iid", type=float, default=1.0,
                        help="Gewicht der Trainingspfade mit i.i.d. Zufalls-Caps")
    parser.add_argument("--cap-grid", default=None,
                        help="optionale Kommaliste zur Ueberschreibung des "
                             "Cap-Gitters, z.B. '0.002,0.01,0.02'")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--log-level",
                        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
                        default="INFO")
    parser.add_argument("--log-file", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.n_train <= 0 or args.n_eval <= 0 or args.chunk_paths <= 0:
        parser.error("--n-train, --n-eval und --chunk-paths muessen positiv sein")
    if args.seed < 0:
        parser.error("--seed muss nicht-negativ sein")
    if args.heston_substeps <= 0:
        parser.error("--heston-substeps muss positiv sein")
    if not math.isfinite(args.ridge) or args.ridge < 0.0:
        parser.error("--ridge muss endlich und nicht-negativ sein")
    if args.policy_iterations < 1:
        parser.error("--policy-iterations muss >= 1 sein")
    if not 0.0 <= args.exploration <= 1.0:
        parser.error("--exploration muss in [0, 1] liegen")
    mix = (args.mix_uncapped, args.mix_constant, args.mix_iid)
    if any(not math.isfinite(m) or m < 0.0 for m in mix) or sum(mix) <= 0.0:
        parser.error("Trainings-Mix-Gewichte muessen >= 0 sein und sich nicht "
                     "zu null summieren")
    if args.cap_grid is not None:
        try:
            grid = tuple(float(x) for x in str(args.cap_grid).split(","))
        except ValueError:
            parser.error("--cap-grid muss eine Kommaliste von Zahlen sein")
        if len(grid) < 2 or any(not math.isfinite(c) or c < 0.0 for c in grid) \
                or sorted(set(grid)) != sorted(grid):
            parser.error("--cap-grid muss >= 2 aufsteigende, nicht-negative "
                         "Werte enthalten")
    return args


def _configure_logging(
    output: Path,
    requested_log_file: Optional[Path],
    level_name: str,
) -> tuple[logging.Logger, Path]:
    log_path = (
        output / "lsmc_crediting_cap.log"
        if requested_log_file is None
        else requested_log_file.expanduser().resolve()
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(getattr(logging, level_name.upper()))
    logger.propagate = False
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger, log_path


def _write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty CSV: {path}")
    fieldnames: List[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Jaehrliche Marktdaten aus dem monatlichen ESG
# ---------------------------------------------------------------------------

@dataclass
class AnnualMarket:
    """Jahresweise Marktgroessen; alle Arrays (n_paths, ...) auf Jahrestagen.

    ``fund_return[:, n]`` ist der Point-to-Point-Return des kompletten
    30/70-Referenzfonds ueber Policenjahr n, ``disc`` der pfadweise
    Diskontfaktor D(0, n) an den Jahrestagen, ``grow_cash[:, n] = D_n/D_{n+1}``
    die realisierte Geldmarkt-Bruttoverzinsung des Jahres n.
    """

    n_paths: int
    n_years: int
    fund_return: Array          # (n, H)
    disc: Array                 # (n, H+1)
    grow_cash: Array            # (n, H)
    short_rate: Array           # (n, H+1)
    variance: Optional[Array]   # (n, H+1) Heston-Varianz Global Equity
    z10_cc: Array               # (n, H+1) pfadweiser 10y-Zero (stetig)
    mva_factor: Array           # (n, H+1) aktueller MVA-Abschlag in [0, 1]


def build_annual_market(
    model: str,
    esg_config,
    product: IndexLinkedLifetimeIncomeProduct,
    n_years: int,
    n_paths: int,
    base_seed: int,
    substeps: int,
    chunk_paths: int,
    logger: logging.Logger,
    label: str,
) -> AnnualMarket:
    """Simuliert das ESG blockweise und extrahiert Jahresgroessen.

    Blockweise Simulation begrenzt den Speicher der monatlichen Pfade; die
    Blockseeds sind deterministisch aus ``base_seed`` abgeleitet und werden im
    Manifest dokumentiert.
    """
    ref = product.reference_fund
    curve = esg_config.curve

    def issue_zero(tau: float) -> float:
        return float(np.expm1(curve.zero(max(tau, 1e-6))))

    parts: Dict[str, List[Array]] = {key: [] for key in (
        "fund_return", "disc", "short_rate", "variance", "z10_cc", "mva_factor")}
    has_variance = model in ("heston", "heston_hull_white")
    remaining = int(n_paths)
    chunk_index = 0
    while remaining > 0:
        size = min(int(chunk_paths), remaining)
        seed = int(base_seed) + 7919 * chunk_index
        kwargs = {"substeps": int(substeps)} if has_variance else {}
        scen = simulate(model, esg_config, float(n_years), size,
                        measure=Measure.RISK_NEUTRAL, seed=seed, **kwargs)
        fund = scen.monthly_rebalanced_reference_fund_index(
            equity_index=ref.equity_index,
            equity_weight=ref.equity_weight,
            bond_tenor=ref.bond_tenor_years,
        )
        annual_idx = np.arange(0, n_years * STEPS_PER_YEAR + 1, STEPS_PER_YEAR)
        fund_annual = fund[:, annual_idx]
        parts["fund_return"].append(
            fund_annual[:, 1:] / np.maximum(fund_annual[:, :-1], 1e-300) - 1.0)
        parts["disc"].append(np.asarray(scen.discount[:, annual_idx]))
        parts["short_rate"].append(np.asarray(scen.short_rate[:, annual_idx]))
        if has_variance:
            parts["variance"].append(
                np.asarray(scen.variance[Index.GLOBAL_EQUITY][:, annual_idx]))
        z10 = np.empty((size, n_years + 1))
        mva = np.zeros((size, n_years + 1))
        mva_window = product.withdrawals.mva_period_years
        for year in range(n_years + 1):
            step = year * STEPS_PER_YEAR
            z10[:, year] = scen.forward_zero_cc(step, 10.0)
            tau = mva_window - year
            if tau > 0:
                factor = product.mva.factor(
                    issue_zero(tau), scen.zero_rate(step, tau), tau)
                mva[:, year] = np.clip(np.asarray(factor, dtype=float), 0.0, 1.0)
        parts["z10_cc"].append(z10)
        parts["mva_factor"].append(mva)
        logger.debug("ESG-Block %s #%d: %d Pfade | seed=%d",
                     label, chunk_index, size, seed)
        del scen, fund
        remaining -= size
        chunk_index += 1

    disc = np.vstack(parts["disc"])
    market = AnnualMarket(
        n_paths=int(n_paths),
        n_years=int(n_years),
        fund_return=np.vstack(parts["fund_return"]),
        disc=disc,
        grow_cash=disc[:, :-1] / np.maximum(disc[:, 1:], 1e-300),
        short_rate=np.vstack(parts["short_rate"]),
        variance=np.vstack(parts["variance"]) if has_variance else None,
        z10_cc=np.vstack(parts["z10_cc"]),
        mva_factor=np.vstack(parts["mva_factor"]),
    )
    logger.info("ESG %s: %d Pfade x %d Jahre (%s, %d Bloecke)",
                label, market.n_paths, market.n_years, model, chunk_index)
    return market


# ---------------------------------------------------------------------------
# Portfolio-Modell auf Jahresgitter
# ---------------------------------------------------------------------------

@dataclass
class Cohort:
    """Ein Modellpunkt mit vorberechneten Dekrementen und Annuitaetsfaktoren."""

    model_point_id: str
    weight: float                 # contract_weight (PV-Gewicht)
    premium: float                # Einmalpraemie = Start-AV
    gross_premium: float          # Behaviour-Kovariate (Bruttopraemie)
    election_year: int
    income_rate: float            # Lifetime Income Rate bei Election
    q: Array                      # (H,) jaehrliche Sterbedekremente
    af_table: Array               # (H+1, n_z) Annuitaetsfaktor je Jahr/Zins
    spouse: bool


class PortfolioModel:
    """Jahresmodell des Modellpunkt-Portfolios unter waehlbarem Cap-Pfad.

    Die Zustaende je Kohorte sind Account Value ``A`` (je ueberlebendem
    Vertrag), In-Force-Gewicht ``w`` (Erwartungswert-Dekremente) und das bei
    Election fixierte Jahreseinkommen ``I``.  Alle Groessen sind Arrays der
    Form (K, n_paths).
    """

    def __init__(self, model_points, mortality: MortalityTable,
                 product: IndexLinkedLifetimeIncomeProduct, behaviour,
                 n_years: int, z_grid: Optional[Array] = None) -> None:
        self.product = product
        self.fee_rate = float(product.fees.total)
        self.behaviour = behaviour
        self.use_dynamic_lapse = bool(behaviour.use_dynamic)
        self.use_dynamic_withdrawals = bool(behaviour.use_dynamic_withdrawals)
        self.base_income_lapse = float(behaviour.lapse.income_phase)
        self.base_excess_rate = float(behaviour.withdrawals.excess_rate)
        self.n_years = int(n_years)
        self.z_grid = (np.linspace(-0.05, 0.20, 26)
                       if z_grid is None else np.asarray(z_grid, dtype=float))

        decrement_cache: Dict[tuple, Array] = {}
        af_cache: Dict[tuple, Array] = {}
        cohorts: List[Cohort] = []
        for mp in model_points.model_points:
            policy = mp.policy
            issue_offset = float(policy.commencement_year) - mortality.base_year
            joint = bool(
                policy.spouse
                and policy.spouse_age is not None
                and policy.spouse_death_election
                == SpouseDeathElection.CONTINUE_INCOME
            )
            spouse_sex = (policy.spouse_sex or policy.sex) if joint else None
            demo_key = (policy.age, policy.sex, joint,
                        policy.spouse_age if joint else None, spouse_sex)

            q_vec = decrement_cache.get(demo_key)
            if q_vec is None:
                if joint:
                    surv = mortality.joint_last_survivor_curve(
                        policy.age, policy.sex,
                        float(policy.spouse_age), spouse_sex,
                        self.n_years, years_from_base=issue_offset)
                else:
                    surv = mortality.survival_curve(
                        policy.age, policy.sex, self.n_years,
                        years_from_base=issue_offset)
                q_vec = 1.0 - surv[1:] / np.maximum(surv[:-1], 1e-300)
                q_vec = np.clip(q_vec, 0.0, 1.0)
                decrement_cache[demo_key] = q_vec

            election_year = int(round(float(policy.income_start_year)))
            af_key = demo_key + (election_year,)
            af_tab = af_cache.get(af_key)
            if af_tab is None:
                af_tab = np.zeros((self.n_years + 1, len(self.z_grid)))
                for year in range(election_year, self.n_years + 1):
                    kwargs = dict(
                        years_from_base=issue_offset + year,
                        projection_duration_start=float(year),
                    )
                    if joint:
                        kwargs["joint_age"] = float(policy.spouse_age) + year
                        kwargs["joint_sex"] = spouse_sex
                    af_tab[year] = np.asarray(mortality.annuity_factor(
                        policy.age + year, policy.sex, self.z_grid, **kwargs),
                        dtype=float)
                af_cache[af_key] = af_tab

            income_rate = product.income_rates.lifetime_income_rate(
                policy.age, policy.sex, policy.income_type, policy.spouse,
                election_year, policy.spouse_age, policy.spouse_sex,
                policy.age_pension_plus)
            cohorts.append(Cohort(
                model_point_id=mp.model_point_id,
                weight=float(mp.contract_weight),
                premium=float(policy.net_initial_investment),
                gross_premium=float(policy.initial_investment),
                election_year=election_year,
                income_rate=float(income_rate),
                q=q_vec,
                af_table=af_tab,
                spouse=joint,
            ))
        self.cohorts: Tuple[Cohort, ...] = tuple(cohorts)
        self.n_cohorts = len(cohorts)
        self.premium_pc = float(
            sum(c.weight * c.premium for c in cohorts))

    # ------------------------------------------------------------------ #
    # Zustaende
    # ------------------------------------------------------------------ #

    def initial_state(self, n_paths: int) -> tuple[Array, Array, Array]:
        account = np.tile(
            np.array([c.premium for c in self.cohorts])[:, None],
            (1, n_paths))
        weight = np.ones((self.n_cohorts, n_paths))
        income = np.zeros((self.n_cohorts, n_paths))
        return account, weight, income

    # ------------------------------------------------------------------ #
    # Ein Jahresschritt
    # ------------------------------------------------------------------ #

    def year_step(
        self,
        market: AnnualMarket,
        year: int,
        account: Array,
        weight: Array,
        income: Array,
        cap: float | Array,
        credit_off: bool = False,
    ) -> tuple[Array, Array, Array, Dict[str, Array]]:
        """Jahrestag ``year`` -> ``year + 1``; Eingaben werden nicht mutiert.

        Reihenfolge je Jahr (Jahres-Approximation der Engine-Reihenfolge):
        Election am Jahrestag (deterministisch), Behaviour-Signale am
        Jahrestag (im Jahr konstant), Crediting, Gebuehren, Tod, Income
        (nachschuessig, nur Ueberlebende), Excess Withdrawals, Lapse.
        Alle Legs sind am Ende des Jahres faellig; der Aufrufer diskontiert
        mit ``market.disc[:, year + 1]``.
        """
        n_paths = account.shape[1]
        fund_r = market.fund_return[:, year]
        if credit_off:
            credit: float | Array = np.zeros(n_paths)
        else:
            credit = np.minimum(np.maximum(fund_r, 0.0), cap)
        cash_return = market.grow_cash[:, year] - 1.0
        f_now = market.mva_factor[:, year]
        f_end = market.mva_factor[:, year + 1]
        z10 = market.z10_cc[:, year]

        new_account = np.empty_like(account)
        new_weight = np.empty_like(weight)
        new_income = np.empty_like(income)
        legs = {name: np.zeros(n_paths) for name in LEG_NAMES}

        for k, coh in enumerate(self.cohorts):
            a = account[k]
            w = weight[k]
            inc = income[k]
            if year == coh.election_year:
                inc = coh.income_rate * a
            elected = year >= coh.election_year
            q = float(coh.q[year])
            cw = coh.weight

            a_credited = a * (1.0 + credit)
            fee = a_credited * self.fee_rate
            a_post_fee = a_credited - fee
            survivors = w * (1.0 - q)

            legs["fees"] += cw * w * fee
            legs["death"] += cw * w * q * a_post_fee
            legs["credit_cost"] += cw * w * a * (credit - cash_return)

            if not elected:
                # Growth-Phase: kontraktuell weder Lapse noch Entnahmen.
                new_account[k] = a_post_fee
                new_weight[k] = survivors
                new_income[k] = inc
                continue

            # Behaviour-Signale am Jahrestag (adaptiert, im Jahr konstant).
            af = np.interp(z10, self.z_grid, coh.af_table[year])
            guarantee_pv = inc * af
            surrender_value = a * (1.0 - f_now)
            ratio_lapse = np.divide(
                guarantee_pv, np.maximum(surrender_value, 1e-300),
                out=np.full(n_paths, float(np.exp(2.0))),
                where=surrender_value > 1e-12)
            log_m_lapse = np.log(np.maximum(ratio_lapse, 1e-300))
            ratio_wd = np.divide(
                guarantee_pv, np.maximum(a, 1e-300),
                out=np.full(n_paths, float(np.exp(2.0))),
                where=a > 1e-12)
            log_m_wd = np.log(np.maximum(ratio_wd, 1e-300))
            if self.use_dynamic_lapse:
                lapse = np.asarray(self.behaviour.dynamic.income_probability(
                    self.base_income_lapse, log_m_lapse,
                    coh.gross_premium, 1.0), dtype=float)
            else:
                lapse = np.full(n_paths, self.base_income_lapse)
            if self.use_dynamic_withdrawals:
                utilisation = np.asarray(
                    self.behaviour.dynamic_withdrawals.excess_rate(
                        self.base_excess_rate, log_m_wd,
                        coh.gross_premium, f_now), dtype=float)
            else:
                utilisation = np.full(n_paths, self.base_excess_rate)

            pay = inc
            from_av = np.minimum(pay, a_post_fee)
            claim = pay - from_av
            a_after_income = a_post_fee - from_av
            legs["income"] += cw * survivors * pay
            legs["claims"] += cw * survivors * claim

            gross_wd = utilisation * a_after_income
            reduction = np.divide(
                gross_wd, np.maximum(a_after_income, 1e-300),
                out=np.zeros(n_paths), where=a_after_income > 0.0)
            legs["withdrawals"] += cw * survivors * gross_wd * (1.0 - f_end)
            legs["mva_retained"] += cw * survivors * gross_wd * f_end
            a_after_wd = a_after_income - gross_wd
            inc_after_wd = inc * (1.0 - reduction)

            legs["surrender"] += cw * survivors * lapse * a_after_wd * (1.0 - f_end)
            legs["mva_retained"] += cw * survivors * lapse * a_after_wd * f_end

            new_account[k] = a_after_wd
            new_weight[k] = survivors * (1.0 - lapse)
            new_income[k] = inc_after_wd

        legs["net_cost"] = (legs["claims"] + legs["credit_cost"]
                            - legs["fees"] - legs["mva_retained"])
        legs["outgo"] = (legs["income"] + legs["death"]
                         + legs["withdrawals"] + legs["surrender"])
        return new_account, new_weight, new_income, legs

    # ------------------------------------------------------------------ #
    # Regressions-Features
    # ------------------------------------------------------------------ #

    def raw_feature_names(self, market: AnnualMarket) -> List[str]:
        names = ["short_rate"]
        if market.variance is not None:
            names.append("variance")
        names += ["growth_acc", "av_income", "income_total",
                  "log_moneyness", "exhausted_share", "inforce"]
        return names

    def raw_features(self, market: AnnualMarket, year: int,
                     account: Array, weight: Array, income: Array) -> Array:
        """Zeit-``year``-Zustandsfeatures (adaptiert; keine Jahres-Returns)."""
        n_paths = account.shape[1]
        z10 = market.z10_cc[:, year]
        growth_av = np.zeros(n_paths)
        growth_prem = 0.0
        av_inc = np.zeros(n_paths)
        inc_tot = np.zeros(n_paths)
        guarantee_pv = np.zeros(n_paths)
        exhausted = np.zeros(n_paths)
        inforce = np.zeros(n_paths)
        for k, coh in enumerate(self.cohorts):
            cw = coh.weight
            inforce += cw * weight[k]
            if year < coh.election_year:
                growth_av += cw * weight[k] * account[k]
                growth_prem += cw * coh.premium
            else:
                av_inc += cw * weight[k] * account[k]
                # Im Election-Jahr ist das Income deterministisch rho * AV,
                # auch wenn der Zustand es erst im Jahresschritt fixiert.
                inc_k = (income[k] if year != coh.election_year
                         else coh.income_rate * account[k])
                w_inc = cw * weight[k] * inc_k
                inc_tot += w_inc
                af = np.interp(z10, self.z_grid, coh.af_table[year])
                guarantee_pv += w_inc * af
                exhausted += np.where(account[k] <= 1e-8, w_inc, 0.0)
        scale = max(self.premium_pc, 1e-300)
        columns = [market.short_rate[:, year]]
        if market.variance is not None:
            columns.append(market.variance[:, year])
        columns.append(growth_av / max(growth_prem, 1e-300)
                       if growth_prem > 0.0 else np.zeros(n_paths))
        columns.append(av_inc / scale)
        columns.append(inc_tot / scale)
        columns.append(np.clip(
            np.log((guarantee_pv + 1e-12) / (av_inc + 1e-12)), -3.0, 3.0))
        columns.append(exhausted / np.maximum(inc_tot, 1e-300))
        columns.append(inforce)
        return np.column_stack(columns)


# ---------------------------------------------------------------------------
# Regression (Basis, Standardisierung, Ridge)
# ---------------------------------------------------------------------------

@dataclass
class FeatureStats:
    mean: Array
    std: Array


def fit_feature_stats(raw: Array) -> FeatureStats:
    mean = raw.mean(axis=0)
    std = raw.std(axis=0)
    std = np.where(std > 1e-12, std, 1.0)
    return FeatureStats(mean=mean, std=std)


def design_matrix(raw: Array, stats: FeatureStats) -> Array:
    """Basis: Konstante, standardisierte Features, Quadrate, Kreuzterme."""
    z = (raw - stats.mean) / stats.std
    n_features = z.shape[1]
    columns = [np.ones(z.shape[0]), z, z ** 2]
    crosses = []
    for i in range(n_features):
        for j in range(i + 1, n_features):
            crosses.append((z[:, i] * z[:, j])[:, None])
    if crosses:
        columns.append(np.concatenate(crosses, axis=1))
    return np.concatenate(
        [c if c.ndim == 2 else c[:, None] for c in columns], axis=1)


def ridge_solve(x: Array, targets: Array, ridge: float) -> Array:
    """Ridge-Regression (Konstante unbestraft); Least-Squares-Fallback."""
    gram = x.T @ x
    penalty = ridge * float(np.trace(gram)) / max(gram.shape[0], 1)
    reg = penalty * np.eye(gram.shape[0])
    reg[0, 0] = 0.0
    rhs = x.T @ targets
    try:
        return np.linalg.solve(gram + reg, rhs)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(x, targets, rcond=None)[0]


# ---------------------------------------------------------------------------
# Trainings-Forward-Lauf (Kontroll-Randomisierung / epsilon-greedy)
# ---------------------------------------------------------------------------

@dataclass
class TrainingStates:
    """Aufgezeichnete Zustaende des Trainingslaufs (float32, K x n x H+1)."""

    account: np.ndarray
    weight: np.ndarray
    income: np.ndarray


def roll_training_states(
    port: PortfolioModel,
    market: AnnualMarket,
    cap_grid: Array,
    rng: np.random.Generator,
    mix: Tuple[float, float, float],
    policy: Optional["FittedPolicy"],
    exploration: float,
) -> TrainingStates:
    """Forward-Lauf, der die Zustandsstuetzstellen der Regression erzeugt.

    Ohne ``policy`` (Iteration 1) werden die Cap-Pfade randomisiert:
    Segment "uncapped" folgt der Aufgabenstellung (Basislauf ohne Cap),
    "constant" und "iid" sichern die Abdeckung des unter realistischen
    Politiken erreichbaren Zustandsraums.  Mit ``policy`` wird epsilon-greedy
    unter der Vorgaengerpolicy gerollt (Policy-Iteration).
    """
    n_paths = market.n_paths
    n_years = market.n_years
    n_actions = len(cap_grid)

    account, weight, income = port.initial_state(n_paths)
    shape = (port.n_cohorts, n_paths, n_years + 1)
    states = TrainingStates(
        account=np.zeros(shape, dtype=np.float32),
        weight=np.zeros(shape, dtype=np.float32),
        income=np.zeros(shape, dtype=np.float32),
    )

    if policy is None:
        weights = np.asarray(mix, dtype=float)
        weights = weights / weights.sum()
        segment = rng.choice(3, size=n_paths, p=weights)
        constant_caps = cap_grid[rng.integers(0, n_actions, size=n_paths)]
    else:
        segment = None
        constant_caps = None

    for year in range(n_years):
        states.account[:, :, year] = account
        states.weight[:, :, year] = weight
        states.income[:, :, year] = income
        if policy is None:
            caps = np.where(
                segment == 0, UNCAPPED_SENTINEL,
                np.where(segment == 1, constant_caps,
                         cap_grid[rng.integers(0, n_actions, size=n_paths)]))
        else:
            caps = policy.decide(port, market, year, account, weight, income)
            explore = rng.random(n_paths) < exploration
            random_caps = cap_grid[rng.integers(0, n_actions, size=n_paths)]
            caps = np.where(explore, random_caps, caps)
        account, weight, income, _ = port.year_step(
            market, year, account, weight, income, caps)
    states.account[:, :, n_years] = account
    states.weight[:, :, n_years] = weight
    states.income[:, :, n_years] = income
    return states


# ---------------------------------------------------------------------------
# Backward Induction (Q-Regression je Aktion)
# ---------------------------------------------------------------------------

@dataclass
class FittedPolicy:
    """Jahresweise Q-Regressionskoeffizienten und Feature-Statistiken."""

    cap_grid: Array
    q_coefs: List[Array]              # je Jahr: (p, n_actions)
    stats: List[FeatureStats]         # je Jahr

    def q_values(self, port: PortfolioModel, market: AnnualMarket, year: int,
                 account: Array, weight: Array, income: Array) -> Array:
        raw = port.raw_features(market, year, account, weight, income)
        x = design_matrix(raw, self.stats[year])
        return x @ self.q_coefs[year]

    def decide(self, port: PortfolioModel, market: AnnualMarket, year: int,
               account: Array, weight: Array, income: Array) -> Array:
        q_hat = self.q_values(port, market, year, account, weight, income)
        return self.cap_grid[np.argmin(q_hat, axis=1)]


def backward_induction(
    port: PortfolioModel,
    market: AnnualMarket,
    states: TrainingStates,
    cap_grid: Array,
    ridge: float,
    logger: logging.Logger,
) -> FittedPolicy:
    """Storage-LSMC-Rueckwaertsinduktion auf den Trainingszustaenden.

    Werteinheit: ``V_n`` ist der auf den Jahrestag n diskontierte Barwert der
    kuenftigen Netto-Kosten (claims + credit_cost - fees - mva_retained).
    Q-Ziel je Aktion c:  (D_{n+1}/D_n) * (cf_n(c) + V_{n+1}(s'(c))).
    Entscheidungen im Vorwaertslauf verwenden nur die auf Zeit-n-Features
    regressierten Q-Werte (kein Look-Ahead).
    """
    n_years = market.n_years
    n_paths = market.n_paths
    n_actions = len(cap_grid)
    disc_step = 1.0 / market.grow_cash          # (n, H): D_{n+1}/D_n

    q_coefs: List[Optional[Array]] = [None] * n_years
    stats_by_year: List[Optional[FeatureStats]] = [None] * n_years
    value_coef: Optional[Array] = None          # V_{n+1}-Koeffizienten
    value_stats: Optional[FeatureStats] = None

    started = time.perf_counter()
    for year in range(n_years - 1, -1, -1):
        account = states.account[:, :, year].astype(float)
        weight = states.weight[:, :, year].astype(float)
        income = states.income[:, :, year].astype(float)

        raw = port.raw_features(market, year, account, weight, income)
        stats = fit_feature_stats(raw)
        x = design_matrix(raw, stats)

        targets = np.empty((n_paths, n_actions))
        for j, cap in enumerate(cap_grid):
            acc2, w2, inc2, legs = port.year_step(
                market, year, account, weight, income, float(cap))
            continuation = np.zeros(n_paths)
            if value_coef is not None:
                raw2 = port.raw_features(market, year + 1, acc2, w2, inc2)
                continuation = design_matrix(raw2, value_stats) @ value_coef
            targets[:, j] = disc_step[:, year] * (legs["net_cost"] + continuation)

        q_coefs[year] = ridge_solve(x, targets, ridge)
        stats_by_year[year] = stats

        q_hat = x @ q_coefs[year]
        best = np.argmin(q_hat, axis=1)
        chosen_target = targets[np.arange(n_paths), best]
        value_coef = ridge_solve(x, chosen_target, ridge)
        value_stats = stats

        if year % 10 == 0 or year == n_years - 1:
            logger.info(
                "Backward Induction | Jahr %d | mittlere Cap-Wahl %.2f%% | "
                "%.1fs", year, 100.0 * float(np.mean(cap_grid[best])),
                time.perf_counter() - started)

    return FittedPolicy(cap_grid=cap_grid,
                        q_coefs=[c for c in q_coefs],
                        stats=[s for s in stats_by_year])


# ---------------------------------------------------------------------------
# Vorwaerts-Bewertung einer Strategie
# ---------------------------------------------------------------------------

@dataclass
class StrategyResult:
    label: str
    pv_net: float
    pv_net_se: float
    pv_claims: float
    pv_credit_cost: float
    pv_fees: float
    pv_mva_retained: float
    pv_outgo: float
    pv_income: float
    pv_death: float
    pv_withdrawals: float
    pv_surrender: float
    pv_naive_claims_minus_fees: float
    identity_residual: float
    first_year_cap: Optional[float]
    cap_share_by_year: Optional[Array] = None   # (H, n_actions)
    cap_mean_by_year: Optional[Array] = None    # (H,)

    def row(self) -> Dict[str, object]:
        return {
            "strategy": self.label,
            "first_year_cap": self.first_year_cap,
            "pv_net_liability_aud": self.pv_net,
            "pv_net_liability_se_aud": self.pv_net_se,
            "pv_guarantee_claims_aud": self.pv_claims,
            "pv_crediting_cost_aud": self.pv_credit_cost,
            "pv_fees_collected_aud": self.pv_fees,
            "pv_mva_retained_aud": self.pv_mva_retained,
            "pv_naive_claims_minus_fees_aud": self.pv_naive_claims_minus_fees,
            "pv_total_policyholder_outgo_aud": self.pv_outgo,
            "pv_income_payments_aud": self.pv_income,
            "pv_death_benefits_aud": self.pv_death,
            "pv_withdrawal_payments_aud": self.pv_withdrawals,
            "pv_surrender_payments_aud": self.pv_surrender,
            "accounting_identity_residual_aud": self.identity_residual,
        }


def run_strategy(
    port: PortfolioModel,
    market: AnnualMarket,
    label: str,
    *,
    policy: Optional[FittedPolicy] = None,
    constant_cap: Optional[float] = None,
    credit_off: bool = False,
    first_year_cap: Optional[float] = None,
) -> StrategyResult:
    """Bewertet eine Cap-Strategie out-of-sample auf ``market``.

    Genau eine der Steuerungen ``policy`` / ``constant_cap`` / ``credit_off``
    bestimmt die Cap-Wahl; ``first_year_cap`` erzwingt optional die
    Erstjahres-Entscheidung einer Greedy-Policy.
    """
    modes = sum((policy is not None, constant_cap is not None, bool(credit_off)))
    if modes != 1:
        raise ValueError("Genau eine Strategie-Steuerung angeben.")
    n_paths = market.n_paths
    n_years = market.n_years
    account, weight, income = port.initial_state(n_paths)

    pv_path_net = np.zeros(n_paths)
    pv_legs = {name: 0.0 for name in LEG_NAMES}
    n_actions = len(policy.cap_grid) if policy is not None else 0
    cap_share = np.zeros((n_years, n_actions)) if policy is not None else None
    cap_mean = np.zeros(n_years) if policy is not None else None
    chosen_first_cap: Optional[float] = (
        float(constant_cap) if constant_cap is not None else None)

    for year in range(n_years):
        if credit_off:
            caps: float | Array = 0.0
        elif constant_cap is not None:
            caps = float(constant_cap)
        else:
            if year == 0 and first_year_cap is not None:
                caps = np.full(n_paths, float(first_year_cap))
            else:
                caps = policy.decide(port, market, year,
                                     account, weight, income)
            if year == 0:
                chosen_first_cap = float(np.median(caps))
            grid = policy.cap_grid
            idx = np.searchsorted(grid, np.asarray(caps) - 1e-12)
            idx = np.clip(idx, 0, n_actions - 1)
            cap_share[year] = np.bincount(idx, minlength=n_actions) / n_paths
            cap_mean[year] = float(np.mean(caps))
        account, weight, income, legs = port.year_step(
            market, year, account, weight, income, caps,
            credit_off=credit_off)
        discount = market.disc[:, year + 1]
        pv_path_net += discount * legs["net_cost"]
        for name in LEG_NAMES:
            pv_legs[name] += float(np.mean(discount * legs[name]))

    pv_net = float(np.mean(pv_path_net))
    pv_net_se = float(np.std(pv_path_net, ddof=1) / math.sqrt(n_paths))
    identity = (pv_legs["outgo"] - port.premium_pc) - pv_net
    return StrategyResult(
        label=label,
        pv_net=pv_net,
        pv_net_se=pv_net_se,
        pv_claims=pv_legs["claims"],
        pv_credit_cost=pv_legs["credit_cost"],
        pv_fees=pv_legs["fees"],
        pv_mva_retained=pv_legs["mva_retained"],
        pv_outgo=pv_legs["outgo"],
        pv_income=pv_legs["income"],
        pv_death=pv_legs["death"],
        pv_withdrawals=pv_legs["withdrawals"],
        pv_surrender=pv_legs["surrender"],
        pv_naive_claims_minus_fees=pv_legs["claims"] - pv_legs["fees"],
        identity_residual=identity,
        first_year_cap=chosen_first_cap,
        cap_share_by_year=cap_share,
        cap_mean_by_year=cap_mean,
    )


# ---------------------------------------------------------------------------
# Grafiken (headless, Stil des Portfolio-Runners)
# ---------------------------------------------------------------------------

def _create_plots(
    constant_results: List[StrategyResult],
    profile_results: List[StrategyResult],
    optimal: StrategyResult,
    cap_grid: Array,
    output: Path,
    logger: logging.Logger,
) -> Dict[str, str]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "Grafiken benoetigen matplotlib; alternativ --no-plots verwenden."
        ) from exc

    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#B8C0CC",
        "axes.grid": True,
        "grid.color": "#DDE2E8",
        "grid.alpha": 0.7,
        "grid.linewidth": 0.7,
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "legend.frameon": False,
    })
    output.mkdir(parents=True, exist_ok=True)
    footer = ("Marktkonsistente Research-Bewertung | Heston-Hull-White unter Q | "
              "LSMC-Kontrollproblem (Storage-Stil) | keine Produktionsbasis")
    paths: Dict[str, str] = {}

    # 1) PV je konstantem Cap vs. optimale Politik
    fixed = [r for r in constant_results if r.first_year_cap is not None]
    fig, ax = plt.subplots(figsize=(12.5, 7.0))
    caps_pct = [100.0 * r.first_year_cap for r in fixed]
    pv = [r.pv_net for r in fixed]
    se = [1.96 * r.pv_net_se for r in fixed]
    ax.errorbar(caps_pct, pv, yerr=se, fmt="o-", color="#007AB3",
                label="konstanter Cap (alle Jahre)")
    no_credit = next((r for r in constant_results
                      if r.first_year_cap is None), None)
    if no_credit is not None:
        ax.axhline(no_credit.pv_net, color="#5B6573", linestyle=":",
                   label="ohne Crediting")
    ax.axhline(optimal.pv_net, color="#168A45", linestyle="--",
               label="LSMC-optimale Cap-Politik")
    if optimal.first_year_cap is not None:
        ax.axvline(100.0 * optimal.first_year_cap, color="#168A45",
                   linewidth=0.9, alpha=0.6)
    ax.set_xlabel("Crediting-Rate-Cap in % p.a.")
    ax.set_ylabel("PV Nettobelastung in AUD (je Durchschnittsvertrag)")
    ax.set_title("PV(Claims) - PV(Fees) je Cap-Strategie", loc="left")
    ax.legend()
    fig.text(0.01, 0.01, footer, fontsize=8, color="#5B6573")
    fig.tight_layout(rect=(0.0, 0.035, 1.0, 1.0))
    path = output / "01_pv_vs_constant_cap.png"
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    paths[path.stem] = str(path)

    # 2) Erstjahres-Cap-Profil (erzwungene Erstentscheidung, danach greedy)
    if profile_results:
        fig, ax = plt.subplots(figsize=(12.5, 7.0))
        caps_pct = [100.0 * r.first_year_cap for r in profile_results]
        pv = [r.pv_net for r in profile_results]
        se = [1.96 * r.pv_net_se for r in profile_results]
        ax.errorbar(caps_pct, pv, yerr=se, fmt="D-", color="#E87722",
                    label="Jahr-1-Cap erzwungen, ab Jahr 2 greedy")
        best = min(profile_results, key=lambda r: r.pv_net)
        ax.axvline(100.0 * best.first_year_cap, color="#168A45",
                   linestyle="--", label="optimaler Jahr-1-Cap")
        ax.set_xlabel("Cap des ersten Jahres in % p.a.")
        ax.set_ylabel("PV Nettobelastung in AUD (je Durchschnittsvertrag)")
        ax.set_title("Wert der Erstjahres-Entscheidung", loc="left")
        ax.legend()
        fig.text(0.01, 0.01, footer, fontsize=8, color="#5B6573")
        fig.tight_layout(rect=(0.0, 0.035, 1.0, 1.0))
        path = output / "02_first_year_cap_profile.png"
        fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        paths[path.stem] = str(path)

    # 3) Cap-Politik ueber die Zeit (Anteil je Gitterpunkt)
    if optimal.cap_share_by_year is not None:
        fig, ax = plt.subplots(figsize=(13.5, 7.0))
        share = optimal.cap_share_by_year.T   # (n_actions, H)
        image = ax.imshow(share, aspect="auto", origin="lower",
                          cmap="Blues", vmin=0.0, vmax=1.0)
        ax.set_yticks(range(len(cap_grid)),
                      [f"{100.0 * c:g}%" for c in cap_grid])
        ax.set_xlabel("Policenjahr")
        ax.set_ylabel("gewaehlter Cap")
        ax.set_title("LSMC-Cap-Politik: Anteil der Pfade je Cap und Jahr",
                     loc="left")
        colorbar = fig.colorbar(image, ax=ax, shrink=0.85)
        colorbar.set_label("Pfadanteil")
        fig.text(0.01, 0.01, footer, fontsize=8, color="#5B6573")
        fig.tight_layout(rect=(0.0, 0.035, 1.0, 1.0))
        path = output / "03_cap_policy_heatmap.png"
        fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        paths[path.stem] = str(path)

    logger.info("%d Grafiken erstellt", len(paths))
    return paths


# ---------------------------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------------------------

def _legacy_main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    logger, log_path = _configure_logging(output, args.log_file, args.log_level)
    started = time.perf_counter()

    try:
        logger.info("[1/6] LSMC-Crediting-Cap-Run gestartet | Output: %s", output)

        # ---------------- Eingabedaten (Konventionen des Runners) -------- #
        logger.info("[2/6] Markt-, Kosten-, Behaviour- und Modellpunktdaten laden")
        market_set = load_market_assumptions(args.zero_curve, args.model_parameters)
        generic_base_product = IndexLinkedLifetimeIncomeProduct(
            reference_fund=ReferenceFundSpec(),
            fees=FeeSpec(lip_waived_in_income_phase_if_aps=False),
            dividend_yield={
                index: parameters.dividend_yield
                for index, parameters in market_set.esg.equity.items()
            },
        )
        costs = load_cost_assumptions(
            args.cost_assumptions,
            assumption_set_id=args.cost_assumption_set,
            value_basis="base",
            product=generic_base_product,
            projection=ProjectionConfig(record_paths=False, heston_cos=False),
        )
        behaviour_assumptions = load_dynamic_behaviour_assumptions(
            args.dynamic_behaviour,
            assumption_set_id=args.behaviour_assumption_set,
            value_basis="base",
        )
        behaviour = behaviour_assumptions.behaviour
        model_points = load_policyholder_model_points(
            args.model_points,
            expected_market_parameter_set_id=market_set.parameter_set_id,
            expected_yield_curve_id=market_set.curve_id,
        )
        mortality = MortalityTable.gompertz_makeham()
        product = costs.product

        cap_grid = np.asarray(
            DEFAULT_CAP_GRID if args.cap_grid is None
            else tuple(float(x) for x in str(args.cap_grid).split(",")),
            dtype=float,
        )
        if float(cap_grid.min()) < GENERIC_GUARANTEED_MIN_CAP:
            logger.warning(
                "Cap-Gitter unterschreitet den kontraktuellen Guaranteed "
                "Minimum Cap von %.2f%% (Minimum im Gitter: %.2f%%); "
                "Research-Vorgabe der Aufgabenstellung.",
                100.0 * GENERIC_GUARANTEED_MIN_CAP,
                100.0 * float(cap_grid.min()),
            )

        # Horizont: bis der juengste versicherte Kopf (inkl. Spouse) 120 ist.
        youngest = min(
            min(mp.policy.age,
                mp.policy.spouse_age if mp.policy.spouse_age is not None
                else mp.policy.age)
            for mp in model_points.model_points
        )
        n_years = int(math.ceil(120.0 - float(youngest)))
        logger.info(
            "%d Modellpunkte | juengster versicherter Kopf %.0f Jahre | "
            "Projektionshorizont %d Jahre | Cap-Gitter %s",
            len(model_points.model_points), youngest, n_years,
            "[" + ", ".join(f"{100.0 * c:g}%" for c in cap_grid) + "]",
        )

        port = PortfolioModel(model_points, mortality, product, behaviour,
                              n_years)

        # ---------------- ESG (Training / Bewertung getrennt) ------------ #
        logger.info(
            "[3/6] Risikoneutrale %s-Szenarien simulieren | train=%d | eval=%d "
            "| seed=%d", args.model, args.n_train, args.n_eval, args.seed)
        market_train = build_annual_market(
            args.model, market_set.esg, product, n_years, args.n_train,
            args.seed, args.heston_substeps, args.chunk_paths, logger, "train")
        market_eval = build_annual_market(
            args.model, market_set.esg, product, n_years, args.n_eval,
            args.seed + 500_000, args.heston_substeps, args.chunk_paths,
            logger, "eval")

        # ---------------- LSMC: Training + Backward Induction ------------ #
        logger.info(
            "[4/6] LSMC (Storage-Stil): Kontroll-Randomisierung, %d "
            "Policy-Iteration(en), %d Aktionen",
            args.policy_iterations, len(cap_grid))
        rng = np.random.default_rng(args.seed + 1)
        mix = (args.mix_uncapped, args.mix_constant, args.mix_iid)
        policy: Optional[FittedPolicy] = None
        for iteration in range(1, args.policy_iterations + 1):
            states = roll_training_states(
                port, market_train, cap_grid, rng, mix,
                policy=policy,
                exploration=args.exploration,
            )
            logger.info("Trainingslauf %d abgeschlossen (%s)",
                        iteration,
                        "randomisierte Caps" if iteration == 1
                        else f"epsilon-greedy, eps={args.exploration:g}")
            policy = backward_induction(
                port, market_train, states, cap_grid, args.ridge, logger)
            del states

        # ---------------- Bewertung / Sanity Checks ---------------------- #
        logger.info("[5/6] Out-of-Sample-Bewertung und Sanity Checks")
        optimal = run_strategy(port, market_eval, "lsmc_optimal_policy",
                               policy=policy)
        logger.info(
            "LSMC-Politik | Jahr-1-Cap (greedy) %.2f%% | PV %s%.2f AUD "
            "(SE %.2f)", 100.0 * (optimal.first_year_cap or float("nan")),
            "" if optimal.pv_net < 0 else "+", optimal.pv_net,
            optimal.pv_net_se)

        profile_results: List[StrategyResult] = []
        for cap in cap_grid:
            result = run_strategy(
                port, market_eval, f"first_year_cap_{cap:.4f}",
                policy=policy, first_year_cap=float(cap))
            result.first_year_cap = float(cap)
            profile_results.append(result)
        best_profile = min(profile_results, key=lambda r: r.pv_net)
        logger.info(
            "Erstjahres-Cap-Profil | Optimum %.2f%% | PV %.2f AUD",
            100.0 * best_profile.first_year_cap, best_profile.pv_net)

        constant_results: List[StrategyResult] = []
        sanity_caps = [0.002] + [0.01 * k for k in range(1, 21)]
        for cap in sanity_caps:
            constant_results.append(run_strategy(
                port, market_eval, f"constant_cap_{cap:.4f}",
                constant_cap=float(cap)))
        constant_results.append(run_strategy(
            port, market_eval, "no_crediting", credit_off=True))
        best_constant = min(
            (r for r in constant_results if r.first_year_cap is not None),
            key=lambda r: r.pv_net)
        logger.info(
            "Bester konstanter Cap %.2f%% | PV %.2f AUD | LSMC-Vorteil %.2f AUD",
            100.0 * best_constant.first_year_cap, best_constant.pv_net,
            best_constant.pv_net - best_profile.pv_net)
        max_identity = max(
            abs(r.identity_residual)
            for r in [optimal, best_profile] + constant_results)
        logger.info(
            "Max. Residuum der Buchungsidentitaet PV(Outgo)-Praemie == "
            "PV(Claims)-PV(Fees): %.6e AUD", max_identity)

        # ---------------- Ergebnisse schreiben --------------------------- #
        logger.info("[6/6] CSV-Ergebnisse, Manifest und Grafiken schreiben")
        summary = {
            "engine_version": ENGINE_VERSION,
            "valuation_as_of_date": market_set.curve_metadata["as_of_date"],
            "valuation_currency": market_set.curve_metadata["currency"],
            "optimal_first_year_cap": best_profile.first_year_cap,
            "optimal_first_year_cap_pct": 100.0 * best_profile.first_year_cap,
            "greedy_first_year_cap": optimal.first_year_cap,
            "pv_net_liability_optimal_aud": best_profile.pv_net,
            "pv_net_liability_optimal_se_aud": best_profile.pv_net_se,
            "premium_per_average_contract_aud": port.premium_pc,
            "best_constant_cap": best_constant.first_year_cap,
            "pv_net_liability_best_constant_aud": best_constant.pv_net,
            "lsmc_advantage_vs_best_constant_aud":
                best_constant.pv_net - best_profile.pv_net,
            "pv_net_liability_no_crediting_aud": next(
                r.pv_net for r in constant_results
                if r.first_year_cap is None),
            "max_accounting_identity_residual_aud": max_identity,
            "n_years": n_years,
            "youngest_covered_age": float(youngest),
            "aggregation_basis":
                "normalised_weighted_average_per_representative_contract",
        }
        summary.update({f"optimal_{k}": v
                        for k, v in best_profile.row().items()
                        if k not in ("strategy", "first_year_cap")})
        summary_path = output / "lsmc_summary.csv"
        _write_csv(summary_path, [summary])

        profile_path = output / "first_year_cap_profile.csv"
        _write_csv(profile_path, [r.row() for r in profile_results])

        sanity_path = output / "fixed_cap_sanity.csv"
        _write_csv(sanity_path, [r.row() for r in constant_results])

        policy_rows: List[Dict[str, object]] = []
        if optimal.cap_share_by_year is not None:
            for year in range(n_years):
                row: Dict[str, object] = {
                    "policy_year": year,
                    "mean_cap": float(optimal.cap_mean_by_year[year]),
                }
                for j, cap in enumerate(cap_grid):
                    row[f"share_cap_{100.0 * cap:g}pct"] = float(
                        optimal.cap_share_by_year[year, j])
                policy_rows.append(row)
        policy_path = output / "cap_policy_by_year.csv"
        _write_csv(policy_path, policy_rows)

        figures: Dict[str, str] = {}
        if not args.no_plots:
            figures = _create_plots(constant_results, profile_results,
                                    optimal, cap_grid, output / "figures",
                                    logger)

        manifest = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "runtime_seconds": time.perf_counter() - started,
            "engine_version": ENGINE_VERSION,
            "method": {
                "objective": (
                    "minimise PV(claims) - PV(fees) with claims = guarantee "
                    "claims + realised crediting cost and fees = collected "
                    "product/LIP fees + retained MVA; pathwise identical to "
                    "PV(total policyholder outgo) - single premium"
                ),
                "algorithm": (
                    "storage-style regression Monte Carlo for stochastic "
                    "control: control randomisation (Kharroubi/Langrene/Pham "
                    "2014) incl. an uncapped base run, per-action Q "
                    "regressions per year (Nadarajah/Margot/Secomandi 2017; "
                    "endogenous-state analogue of the Boogert/de Jong 2008 "
                    "inventory grid), Tsitsiklis/Van-Roy value backups, "
                    "optional epsilon-greedy policy iteration, greedy "
                    "out-of-sample forward evaluation (upper bound of the "
                    "minimal net PV)"
                ),
                "not_applicable": (
                    "standard Longstaff/Schwartz optimal stopping: the cap "
                    "choice is a repeated control that feeds back into the "
                    "endogenous account/moneyness state, not a stopping time"
                ),
                "valuation_measure": "risk_neutral",
                "market_model": args.model,
                "discounting": "pathwise stochastic money-market deflators",
                "cap_grid": [float(c) for c in cap_grid],
                "cap_grid_note": (
                    "0.2% grid point lies below the contractual guaranteed "
                    "minimum cap of 0.25% (research instruction)"
                ),
                "annual_grid_approximations": [
                    "annual crediting/fees/income/decrements as in the "
                    "archived agile_engine.lsmc (fees as one annual factor, "
                    "income annually in arrears)",
                    "behaviour signals evaluated at anniversaries and held "
                    "within the year (engine convention)",
                    "joint continue-income points use last-survivor "
                    "decrements from issue (no election-date conditioning)",
                    "no intra-year DVA, no insurer expenses, no hedge "
                    "transaction costs, withdrawal minimum amounts ignored",
                    "deterministic take-up from model-point income_start_year "
                    "(portfolio-runner convention)",
                ],
                "training_cap_mix_uncapped_constant_iid": list(
                    (args.mix_uncapped, args.mix_constant, args.mix_iid)),
                "policy_iterations": args.policy_iterations,
                "exploration": args.exploration,
                "ridge": args.ridge,
                "feature_names": port.raw_feature_names(market_train),
                "seeds": {
                    "train_base": args.seed,
                    "train_chunk_stride": 7919,
                    "training_rng": args.seed + 1,
                    "eval_base": args.seed + 500_000,
                },
            },
            "mortality": {
                "basis": "illustrative_gompertz_makeham",
                "calibration_status": "not_calibrated_for_production",
                "base_year": mortality.base_year,
                "annual_improvement_rate": mortality.improvement_rate,
            },
            "portfolio": {
                "model_point_count": len(model_points.model_points),
                "youngest_covered_age": float(youngest),
                "horizon_years": n_years,
                "premium_per_average_contract_aud": port.premium_pc,
                "aggregation_basis": summary["aggregation_basis"],
            },
            "settings": {
                "n_train": args.n_train,
                "n_eval": args.n_eval,
                "heston_substeps": args.heston_substeps,
                "chunk_paths": args.chunk_paths,
            },
            "sources": {
                "model_points": model_points.source_metadata(),
                "market": market_set.source_metadata(),
                "costs": costs.source_metadata(),
                "dynamic_behaviour": behaviour_assumptions.source_metadata(),
            },
            "outputs": {
                "lsmc_summary_csv": str(summary_path),
                "first_year_cap_profile_csv": str(profile_path),
                "fixed_cap_sanity_csv": str(sanity_path),
                "cap_policy_by_year_csv": str(policy_path),
                "run_log": str(log_path),
                "figures": figures,
            },
            "summary": summary,
        }
        manifest_path = output / "run_manifest.json"
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True,
                      allow_nan=False, default=str)
            handle.write("\n")

        logger.info("Optimaler Cap Jahr 1: %.2f%% | PV(Claims)-PV(Fees): "
                     "AUD %.2f (SE %.2f) je Durchschnittsvertrag",
                     100.0 * best_profile.first_year_cap,
                     best_profile.pv_net, best_profile.pv_net_se)
        logger.info("Summary: %s", summary_path)
        logger.info("Manifest: %s", manifest_path)
        logger.info("Run abgeschlossen in %.1f Sekunden",
                    time.perf_counter() - started)
        return 0
    except Exception:
        logger.exception("LSMC-Crediting-Cap-Run fehlgeschlagen")
        return 1


def main(argv: Optional[Sequence[str]] = None) -> Optional[int]:
    """Delegate all supported entry points to the canonical monthly runner.

    ``argv`` is retained for callers which imported the legacy runner's
    ``main`` function.  The canonical runner currently parses ``sys.argv``
    directly, so a supplied argument sequence is installed only for the
    duration of that call and is restored afterwards.  This unchanged-argv
    delegation also exposes the canonical market-cache, hedge-cache and
    hedge-pricing CLI switches without duplicating their implementation here.
    """
    log_to_console(
        "NOTICE: run_lsmc_crediting_cap.py is the separate Stackelberg cap-"
        "control study with fixed model-point Income Election; it is not the "
        "combined Policyholder Election/Surrender Cap×Stress runner.",
        level="NOTICE",
        stream=sys.stderr,
    )
    if __package__:
        from .optimize_crediting_rate_lsmc import main as canonical_main
    else:
        from optimize_crediting_rate_lsmc import main as canonical_main

    if argv is None:
        return canonical_main()

    previous_argv = sys.argv
    try:
        sys.argv = [previous_argv[0], *(str(value) for value in argv)]
        return canonical_main()
    finally:
        sys.argv = previous_argv


if __name__ == "__main__":
    raise SystemExit(main())
