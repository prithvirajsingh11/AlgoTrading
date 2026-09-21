/**
 * Domain TypeScript contracts for AlgoTrade.
 * Matches backend schemas from Pydantic and Dataclasses strictly without using `any`.
 */

export interface DatasetMetadata {
  dataset_id: string;
  symbols: string[];
  timeframe: string;
  start_timestamp: string | null;
  end_timestamp: string | null;
  row_count: number;
  source: string;
  validation_status: "valid" | "invalid" | "unvalidated";
}

export interface ValidationReport {
  valid: boolean;
  total_rows: number;
  errors: string[];
  warnings: string[];
  start_date: string | null;
  end_date: string | null;
}

export interface StrategyParamDef {
  name: string;
  type: "int" | "float" | "str" | "bool";
  default: number | string | boolean;
  description?: string;
}

export interface StrategyMetadata {
  id: string;
  name: string;
  category: string;
  description: string;
  status: "ACTIVE" | "COMING_SOON" | "DEPRECATED";
  parameters: StrategyParamDef[];
}

export interface TradeRecord {
  symbol: string;
  entry_time: string;
  exit_time: string;
  direction: "LONG" | "SHORT";
  size: number;
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_pct: number;
  duration_bars: number;
  exit_reason: string;
}

export interface BacktestMetrics {
  total_return_pct: number;
  cagr: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_pct: number;
  win_rate: number;
  total_trades: number;
  profit_factor: number;
  final_equity: number;
  total_pnl: number;
  gross_profit?: number;
  gross_loss?: number;
  max_consecutive_losses?: number;
}

export interface EquityPoint {
  timestamp: string;
  equity?: number;
  total_equity?: number;
  cash?: number;
  position_value?: number;
  drawdown_pct?: number;
}

export interface DrawdownPoint {
  timestamp: string;
  equity: number;
  total_equity: number;
  high_watermark: number;
  drawdown_pct: number;
}

export interface ExecutionStatistics {
  total_bars: number;
  runtime_ms: number;
  trade_count: number;
  initial_capital: number;
  commission_fixed: number;
  commission_percent: number;
  slippage_bps: number;
  seed: number;
}

export interface AIDecisionStats {
  model: string;
  total_decisions: number;
  buy_count: number;
  sell_count: number;
  hold_count: number;
  no_action_count: number;
  avg_confidence: number;
  avg_latency_ms: number;
  cache_hits: number;
  cache_misses: number;
  fallbacks: number;
  provider_mode: string;
}

export interface ConfusionMatrix {
  true_negative: number;
  false_positive: number;
  false_negative: number;
  true_positive: number;
}

export interface ClassificationMetrics {
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  roc_auc: number;
  brier_score: number;
  log_loss?: number;
  confusion_matrix: ConfusionMatrix;
  support_positive: number;
  support_negative: number;
}

export interface MLModelArtifactSummary {
  model_version: string;
  feature_schema_hash: string;
  feature_names: string[];
  feature_importance: Record<string, number>;
  classification_metrics: ClassificationMetrics;
  random_seed: number;
}

export interface MLTrainResult {
  artifact: MLModelArtifactSummary;
  train_metrics: ClassificationMetrics;
  val_metrics: ClassificationMetrics | null;
  test_metrics: ClassificationMetrics;
  calibration_report: {
    method: string;
    brier_before: number;
    brier_after: number;
    calibrated: boolean;
  } | null;
  dataset_summary: {
    symbol: string;
    total_samples: number;
    features_count: number;
  };
}

export interface WalkForwardMLWindow {
  window_id: number;
  train_bars: number;
  test_bars: number;
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
  classification_metrics: ClassificationMetrics;
  test_predictions_count: number;
}

export interface WalkForwardMLResult {
  symbol: string;
  total_windows: number;
  windows: WalkForwardMLWindow[];
  aggregate_classification: ClassificationMetrics;
}

export interface FeatureMetadata {
  type: "current_bar" | "lagged" | "rolling";
  description: string;
  formula: string;
}

export interface ExperimentConfig {
  dataset: {
    dataset_id?: string;
    symbols: string[];
    timeframe: string;
    start_date?: string | null;
    end_date?: string | null;
  };
  strategy: {
    name: string;
    parameters: Record<string, number | string | boolean>;
  };
  execution: {
    commission_fixed: number;
    commission_percent: number;
    slippage_bps: number;
  };
  risk: {
    max_position_pct: number;
    max_drawdown_limit: number;
    allow_shorting: boolean;
    position_sizing_method: string;
    position_size_pct: number;
    risk_per_trade: number;
  };
  portfolio: {
    initial_capital: number;
  };
  seed: number;
  jev?: {
    enabled: boolean;
    model?: string;
    min_confidence?: number;
    cache_enabled?: boolean;
    timeout_seconds?: number;
    decision_frequency?: string;
    decision_frequency_n?: number;
  };
  ml?: {
    enabled: boolean;
    buy_threshold?: number;
    sell_threshold?: number;
  };
}

export interface ExperimentResult {
  experiment_id: string;
  configuration_hash: string;
  config: Record<string, unknown>;
  dataset_metadata: Record<string, unknown>;
  strategy_info: {
    name: string;
    parameters: Record<string, unknown>;
  };
  metrics: BacktestMetrics;
  trade_records: TradeRecord[];
  equity_curve: EquityPoint[];
  drawdown_curve: DrawdownPoint[];
  execution_statistics: ExecutionStatistics;
  walk_forward_results?: Record<string, unknown> | null;
  ai_decision_stats?: AIDecisionStats | null;
  classification_metrics?: ClassificationMetrics | null;
  feature_importance?: Record<string, number> | null;
  warnings: string[];
  created_at: string;
  completed_at: string;
}

export interface JevStatus {
  enabled: boolean;
  configured: boolean;
  model: string;
  provider_status: "ready" | "unconfigured" | "disabled";
  timeout_seconds: number;
  min_confidence: number;
}

export interface JevDecision {
  decision: "BUY" | "SELL" | "HOLD" | "NO_ACTION";
  confidence: number;
  reasoning: string;
  model: string;
  timestamp: string;
  latency_ms: number;
  source: "live_api" | "cache" | "fallback_error" | "fallback_confidence" | "stub";
  fallback_used: boolean;
}

export interface StrategyProviderComparison {
  experiment_id: string;
  strategy_name: string;
  category: "traditional" | "machine_learning" | "jev_assisted";
  provider: "rule_based" | "xgboost" | "typesafe_jev";
  trading_metrics: {
    total_return_pct: number;
    cagr: number;
    sharpe_ratio: number;
    sortino_ratio: number;
    max_drawdown_pct: number;
    win_rate: number;
    profit_factor: number;
    total_trades: number;
  };
  classification_metrics?: ClassificationMetrics | null;
  ai_decision_stats?: AIDecisionStats | null;
  feature_importance?: Record<string, number> | null;
}

export interface ProviderComparisonResult {
  count: number;
  comparisons: StrategyProviderComparison[];
}

export interface PortfolioSummary {
  account_id: string;
  currency: string;
  initial_capital: number;
  current_cash: number;
  positions_count: number;
  status: string;
  total_equity?: number;
  realized_pnl?: number;
  unrealized_pnl?: number;
  current_exposure?: number;
  drawdown_pct?: number;
}

export interface Position {
  symbol: string;
  quantity: number;
  avg_entry_price: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  leg_type?: "LONG" | "SHORT" | "PAIR_LEG_A" | "PAIR_LEG_B";
  pair_id?: string;
}

export interface PaperTradingStatus {
  is_active: boolean;
  mode: string;
  message: string;
}

export interface OHLCVBar {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}
