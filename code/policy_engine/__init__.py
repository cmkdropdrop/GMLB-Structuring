"""Generic index-linked lifetime-income modelling engine.

The package name remains ``policy_engine`` for repository compatibility.  The
active product is :class:`IndexLinkedLifetimeIncomeProduct`; ``AgileProduct``
is a transitional alias for older research imports.  See the repository
``README.md`` and ``documents/modelling_methodology.md`` for product scope,
portfolio valuation and model limits.
"""

from .behavior import (BehaviourModel, DynamicHazardFunction,
                       DynamicLapseParams, DynamicTakeUpParams,
                       DynamicWithdrawalParams, FractionalLogitFunction,
                       IncomeTakeUp, LapseAssumptions,
                       PerformanceLapseFunction, WithdrawalBehaviour)
from .capital import CapitalResult, CapitalStresses, compute_capital
from .crediting import (HedgeCapLegMode, HedgeMarket, credited_return,
                        crediting_package_value, crediting_margin_rate,
                        fair_cap, hedge_option_package_value,
                        heston_intra_year_value_factor, heston_package_value,
                        heston_put_cos, intra_year_value_factor,
                        retained_excess_return)
from .cost_assumptions import (CostAssumptionSet,
                               DEFAULT_COST_ASSUMPTIONS_PATH,
                               load_cost_assumptions)
from .dynamic_behaviour_assumptions import (
    DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
    DynamicBehaviourAssumptionSet,
    load_dynamic_behaviour_assumptions,
)
from .equity_allocation import (
    DEFAULT_EQUITY_ALLOCATION_ID,
    DEFAULT_EQUITY_ALLOCATION_PATH,
    EquityAllocation,
    load_equity_allocation,
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
from .scenario_cache import (
    SCENARIO_CACHE_SCHEMA_VERSION,
    ScenarioCacheError,
    ScenarioCacheMismatchError,
    ScenarioCacheNotFoundError,
    ScenarioCacheSpec,
    load_scenario_set,
    save_scenario_set,
)
from .forward_start_hedge_pricing import (
    DEFAULT_HEDGE_CROSS_FIT_FOLDS,
    DEFAULT_HEDGE_CROSS_FIT_SEED,
    HEDGE_PRICING_VERSION,
    HedgePriceCacheError,
    HedgePriceCacheMismatchError,
    HedgePriceCacheNotFoundError,
    HedgePriceCacheSpec,
    HedgePriceSurface,
    annual_call_spread_payoffs,
    build_hedge_price_surface,
    direct_discounted_mc_pv,
    load_hedge_price_surface,
    save_hedge_price_surface,
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
                      bind_cached_hedge_prices, build_scenarios,
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
from .projection import (CreditingCapDecisionContext,
                         IncomeActionDecision, IncomeActionDecisionContext,
                         IncomeActionState, IncomeActionTransition,
                         IncomeActionType, IncomeElectionDecisionContext,
                         IncomeMonthScenarioSlice, IncomeMonthTransition,
                         IncomeTransitionPanelCollector,
                         ProjectionConfig, advance_income_month,
                         apply_income_action,
                         build_income_action_decision_context,
                         ProjectionResult, SurrenderActionValueContext,
                         SurrenderDecisionContext, project)
from .optimal_behaviour_validation import (
    OptimalBehaviourValidationResult, PairedPolicyValidationGate,
    build_validation_result, paired_noninferiority_gate,
)
from .optimal_behaviour_lsmc import (
    CrossFittedOptimalBehaviourPolicy, CrossFittedOptimalSurrenderPolicy,
    ELECTION_FEATURE_NAMES, INCOME_ACTION_FEATURE_NAMES,
    PARTIAL_ACTION_FEATURE_NAMES, POLICYHOLDER_LSMC_MORTALITY_BASIS,
    IncomeActionAdvantagePolicyFit,
    IncomeActionRegressionSet, OptimalBehaviourLSMCSettings,
    OptimalBehaviourPolicy, OptimalBehaviourPolicyFit,
    OptimalBehaviourRegressionDiagnostic, SurrenderContinuationPolicyFit,
    SurrenderContinuationRegressionDiagnostic,
    build_income_action_regression_features,
    build_income_election_regression_features,
    build_partial_action_regression_features,
    build_surrender_regression_features,
    build_surrender_regression_features_from_arrays,
    fit_optimal_behaviour_policy,
    fit_income_action_advantage_policy,
    fit_surrender_continuation_regression,
    fit_surrender_continuation_policy,
    mortality_free_policyholder_basis,
)
from .stackelberg_control import (
    PolicyholderAction, TabularStackelbergProblem,
    TabularStackelbergSolution, solve_tabular_stackelberg,
)
from .portfolio import (FairFeeSolveResult, ModelPointPortfolioValuation,
                         PortfolioProgress, PortfolioValuationResult,
                         value_policyholder_portfolio)
from .sensitivities import Scenario, run_sensitivities, standard_scenarios

__version__ = "3.0.0"

__all__ = [
    "AgePensionPlusSpec", "AgileProduct", "BehaviourModel", "CapSchedule",
    "CapitalResult", "CapitalStresses", "CostAssumptionSet",
    "DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH", "DEFAULT_COST_ASSUMPTIONS_PATH",
    "DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY", "DEFAULT_MARKET_DATA_DIRECTORY",
    "DEFAULT_EQUITY_ALLOCATION_ID", "DEFAULT_EQUITY_ALLOCATION_PATH",
    "DEFAULT_MODEL_PARAMETERS_PATH", "DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH",
    "DEFAULT_HEDGE_CROSS_FIT_FOLDS", "DEFAULT_HEDGE_CROSS_FIT_SEED",
    "DynamicBehaviourAssumptionSet", "DynamicHazardFunction",
    "DynamicLapseParams", "DynamicTakeUpParams", "DynamicWithdrawalParams", "ESGConfig",
    "EquityAllocation", "EquityParams", "ExpenseAssumptions",
    "FairFeeSolveResult", "FeeSpec",
    "FIXED_REFERENCE_FUND_CAP", "FundingSource", "GENERIC_GUARANTEED_MIN_CAP",
    "HedgeCapLegMode", "HedgeMarket",
    "HEDGE_PRICING_VERSION", "HedgePriceCacheError",
    "HedgePriceCacheMismatchError", "HedgePriceCacheNotFoundError",
    "HedgePriceCacheSpec", "HedgePriceSurface",
    "HestonParams", "HullWhiteParams", "IncomeRateTable", "IncomeTakeUp",
    "IncomeActionDecision", "IncomeActionDecisionContext", "IncomeActionState",
    "IncomeActionTransition", "IncomeActionType", "IncomeMonthScenarioSlice",
    "IncomeMonthTransition", "IncomeTransitionPanelCollector",
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
    "SCENARIO_CACHE_SCHEMA_VERSION", "ScenarioCacheError",
    "ScenarioCacheMismatchError", "ScenarioCacheNotFoundError",
    "ScenarioCacheSpec",
    "SpouseDeathElection", "SurrenderDecisionContext",
    "IncomeElectionDecisionContext",
    "SurrenderActionValueContext",
    "CreditingCapDecisionContext", "CrossFittedOptimalBehaviourPolicy",
    "CrossFittedOptimalSurrenderPolicy", "ELECTION_FEATURE_NAMES",
    "INCOME_ACTION_FEATURE_NAMES", "PARTIAL_ACTION_FEATURE_NAMES",
    "POLICYHOLDER_LSMC_MORTALITY_BASIS",
    "IncomeActionAdvantagePolicyFit", "IncomeActionRegressionSet",
    "OptimalBehaviourLSMCSettings", "OptimalBehaviourPolicy",
    "OptimalBehaviourPolicyFit", "OptimalBehaviourRegressionDiagnostic",
    "OptimalBehaviourValidationResult", "PairedPolicyValidationGate",
    "SurrenderContinuationPolicyFit",
    "SurrenderContinuationRegressionDiagnostic",
    "PolicyholderAction",
    "TabularStackelbergProblem", "TabularStackelbergSolution",
    "ValuationResult", "ValuationSettings", "WithdrawalBehaviour",
    "WithdrawalRules", "YieldCurve",
    "advance_income_month", "analyse_profitability", "apply_income_action",
    "annual_call_spread_payoffs", "bind_cached_hedge_prices",
    "build_hedge_price_surface", "build_scenarios",
    "build_income_action_decision_context",
    "build_income_action_regression_features",
    "build_income_election_regression_features",
    "build_partial_action_regression_features",
    "build_validation_result",
    "build_surrender_regression_features",
    "build_surrender_regression_features_from_arrays",
    "compute_capital", "credited_return",
    "crediting_margin_rate", "crediting_package_value", "fair_cap",
    "hedge_option_package_value",
    "fair_lifetime_income_premium", "fit_optimal_behaviour_policy",
    "fit_income_action_advantage_policy",
    "fit_surrender_continuation_regression",
    "fit_surrender_continuation_policy",
    "mortality_free_policyholder_basis",
    "paired_noninferiority_gate",
    "greeks", "heston_intra_year_value_factor",
    "heston_package_value", "heston_put_cos", "intra_year_value_factor",
    "load_cost_assumptions", "load_dynamic_behaviour_assumptions",
    "load_equity_allocation", "load_hedge_price_surface",
    "load_market_assumptions", "load_scenario_set",
    "load_policyholder_model_points", "project",
    "resolve_horizon", "retained_excess_return", "run_sensitivities", "simulate",
    "save_hedge_price_surface", "save_scenario_set", "direct_discounted_mc_pv",
    "solve_tabular_stackelberg", "standard_scenarios",
    "value_contract", "value_policyholder_portfolio",
]
