"""Generic index-linked lifetime-income modelling engine.

The package name remains ``agile_engine`` for repository compatibility.  The
active product is :class:`IndexLinkedLifetimeIncomeProduct`; ``AgileProduct``
is a transitional alias for older research imports.  See ``README.md`` and
``METHODOLOGY.md`` for product scope, portfolio valuation and model limits.
"""

from .behavior import (BehaviourModel, DynamicHazardFunction,
                       DynamicLapseParams, DynamicTakeUpParams,
                       DynamicWithdrawalParams, FractionalLogitFunction,
                       IncomeTakeUp, LapseAssumptions,
                       PerformanceLapseFunction, WithdrawalBehaviour)
from .capital import CapitalResult, CapitalStresses, compute_capital
from .crediting import (HedgeMarket, credited_return, crediting_package_value,
                        crediting_margin_rate, fair_cap,
                        heston_intra_year_value_factor, heston_package_value,
                        heston_put_cos, intra_year_value_factor)
from .cost_assumptions import (CostAssumptionSet,
                               DEFAULT_COST_ASSUMPTIONS_PATH,
                               load_cost_assumptions)
from .dynamic_behaviour_assumptions import (
    DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
    DynamicBehaviourAssumptionSet,
    load_dynamic_behaviour_assumptions,
)
from .curves import YieldCurve
from .esg import (ESGConfig, EquityParams, HestonParams, HullWhiteParams,
                  Measure, ScenarioSet, simulate)
from .market_assumptions import (
    DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH,
    DEFAULT_MARKET_DATA_DIRECTORY,
    DEFAULT_MODEL_PARAMETERS_PATH,
    MarketAssumptionSet,
    load_market_assumptions,
)
from .model_points import (
    DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH,
    LEGACY_ALLOCATION_COLUMNS,
    PolicyholderModelPoint,
    PolicyholderModelPointSet,
    load_policyholder_model_points,
)
from .mortality import MortalityTable
from .pricing import (ValuationResult, ValuationSettings,
                      fair_lifetime_income_premium, greeks, resolve_horizon,
                      value_contract)
from .product import (AgePensionPlusSpec, AgileProduct, CapSchedule,
                      ExpenseAssumptions, FeeSpec, IncomeRateTable, IncomeType,
                      FundingSource, Index, IndexLinkedLifetimeIncomeProduct,
                      InvestmentOption, MVASpec, PolicySpec, Protection,
                      ReferenceFundSpec,
                      Sex, SpouseDeathElection, WithdrawalRules,
                      FIXED_REFERENCE_FUND_CAP, GENERIC_GUARANTEED_MIN_CAP,
                      DEFAULT_GUARANTEED_MIN_CAPS, JULY_2026_CAPS,
                      JULY_2026_FEMALE_INCOME_RATES,
                      JULY_2026_MALE_INCOME_RATES)
from .profitability import (ProfitabilityResult, ProfitabilitySettings,
                            analyse_profitability)
from .projection import (CreditingCapDecisionContext, ProjectionConfig,
                         ProjectionResult, SurrenderActionValueContext,
                         SurrenderDecisionContext, project)
from .optimal_behaviour_lsmc import (
    CrossFittedOptimalSurrenderPolicy, SurrenderContinuationPolicyFit,
    SurrenderContinuationRegressionDiagnostic,
    build_surrender_regression_features,
    build_surrender_regression_features_from_arrays,
    fit_surrender_continuation_regression,
    fit_surrender_continuation_policy,
)
from .stackelberg_control import (
    PolicyholderAction, TabularStackelbergProblem,
    TabularStackelbergSolution, solve_tabular_stackelberg,
)
from .portfolio import (FairFeeSolveResult, ModelPointPortfolioValuation,
                         PortfolioProgress, PortfolioValuationResult,
                         value_policyholder_portfolio)
from .sensitivities import Scenario, run_sensitivities, standard_scenarios

__version__ = "2.2.0"

__all__ = [
    "AgePensionPlusSpec", "AgileProduct", "BehaviourModel", "CapSchedule",
    "CapitalResult", "CapitalStresses", "CostAssumptionSet",
    "DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH", "DEFAULT_COST_ASSUMPTIONS_PATH",
    "DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY", "DEFAULT_MARKET_DATA_DIRECTORY",
    "DEFAULT_MODEL_PARAMETERS_PATH", "DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH",
    "DynamicBehaviourAssumptionSet", "DynamicHazardFunction",
    "DynamicLapseParams", "DynamicTakeUpParams", "DynamicWithdrawalParams", "ESGConfig",
    "EquityParams", "ExpenseAssumptions", "FairFeeSolveResult", "FeeSpec",
    "FIXED_REFERENCE_FUND_CAP", "FundingSource", "GENERIC_GUARANTEED_MIN_CAP",
    "HedgeMarket",
    "HestonParams", "HullWhiteParams", "IncomeRateTable", "IncomeTakeUp",
    "IncomeType", "Index", "IndexLinkedLifetimeIncomeProduct",
    "InvestmentOption", "JULY_2026_CAPS", "LEGACY_ALLOCATION_COLUMNS",
    "DEFAULT_GUARANTEED_MIN_CAPS", "JULY_2026_FEMALE_INCOME_RATES",
    "JULY_2026_MALE_INCOME_RATES",
    "FractionalLogitFunction", "LapseAssumptions", "MVASpec",
    "PerformanceLapseFunction",
    "MarketAssumptionSet", "Measure", "ModelPointPortfolioValuation",
    "MortalityTable", "PolicySpec", "PolicyholderModelPoint",
    "PolicyholderModelPointSet", "PortfolioProgress", "PortfolioValuationResult",
    "ProfitabilityResult",
    "ProfitabilitySettings", "ProjectionConfig", "ProjectionResult",
    "Protection", "ReferenceFundSpec", "Scenario", "ScenarioSet", "Sex",
    "SpouseDeathElection", "SurrenderDecisionContext",
    "SurrenderActionValueContext",
    "CreditingCapDecisionContext", "CrossFittedOptimalSurrenderPolicy",
    "SurrenderContinuationPolicyFit",
    "SurrenderContinuationRegressionDiagnostic",
    "PolicyholderAction",
    "TabularStackelbergProblem", "TabularStackelbergSolution",
    "ValuationResult", "ValuationSettings", "WithdrawalBehaviour",
    "WithdrawalRules", "YieldCurve",
    "analyse_profitability", "build_surrender_regression_features",
    "build_surrender_regression_features_from_arrays",
    "compute_capital", "credited_return",
    "crediting_margin_rate", "crediting_package_value", "fair_cap",
    "fair_lifetime_income_premium", "fit_surrender_continuation_regression",
    "fit_surrender_continuation_policy",
    "greeks", "heston_intra_year_value_factor",
    "heston_package_value", "heston_put_cos", "intra_year_value_factor",
    "load_cost_assumptions", "load_dynamic_behaviour_assumptions",
    "load_market_assumptions", "load_policyholder_model_points", "project",
    "resolve_horizon", "run_sensitivities", "simulate",
    "solve_tabular_stackelberg", "standard_scenarios",
    "value_contract", "value_policyholder_portfolio",
]
