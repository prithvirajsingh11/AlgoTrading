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

export interface PaperTradingSessionSummary {
  session_id: string;
  created_at: string;
  started_at?: string | null;
  stopped_at?: string | null;
  dataset_id: string;
  symbols: string[];
  timeframe: string;
  strategy: string;
  strategy_params: Record<string, any>;
  provider: string;
  initial_capital: number;
  current_equity: number;
  cash: number;
  realized_pnl: number;
  unrealized_pnl: number;
  current_exposure: number;
  speed: string;
  status: "CREATED" | "RUNNING" | "PAUSED" | "STOPPED" | "ERROR";
  error_message?: string | null;
  current_bar_index: number;
  total_bars: number;
  simulation_timestamp?: string | null;
  mode?: "HISTORICAL_REPLAY" | "REAL_TIME";
  data_provider_type?: string;
  safety_state?: "SIGNALS_ENABLED" | "SIGNALS_PAUSED";
  max_data_age_seconds?: number;
  last_data_timestamp?: string | null;
  latency_ms?: number | null;
}

export interface MarketProviderInfo {
  id: string;
  name: string;
  type: string;
  is_live: boolean;
  description: string;
  requires_api_key: boolean;
  status: string;
}

export interface MarketConnectionStatus {
  provider: string;
  state: "DISCONNECTED" | "CONNECTING" | "CONNECTED" | "RECONNECTING" | "ERROR";
  connected: boolean;
  subscribed_symbols: string[];
  reconnect_count: number;
  last_message_at: string | null;
  last_heartbeat_at: string | null;
  latency_ms: number | null;
  last_error: string | null;
  safety_state?: "SIGNALS_ENABLED" | "SIGNALS_PAUSED";
  session_id?: string;
}

export interface ProviderStatusEvent {
  timestamp: string;
  event_type: "PROVIDER_STATUS";
  session_id: string;
  provider: string;
  status: string;
  connected: boolean;
  reconnect_count: number;
  latency_ms?: number | null;
  is_stale: boolean;
  safety_state: "SIGNALS_ENABLED" | "SIGNALS_PAUSED";
  last_heartbeat?: string | null;
  error_message?: string | null;
}

export interface MarketUpdateEvent {
  timestamp: string;
  event_type: "MARKET_UPDATE";
  session_id: string;
  symbol: string;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close: number;
  volume?: number | null;
  bid?: number | null;
  ask?: number | null;
  mid?: number | null;
  last_price?: number | null;
  latency_ms?: number | null;
  is_stale?: boolean;
}

export interface PaperOrderRecord {
  order_id: string;
  session_id: string;
  timestamp: string;
  symbol: string;
  side: "BUY" | "SELL";
  order_type: "MARKET" | "LIMIT" | "STOP_LOSS";
  quantity: number;
  requested_price?: number | null;
  fill_price?: number | null;
  status: "PENDING" | "FILLED" | "CANCELLED" | "REJECTED";
  commission: number;
  slippage: number;
  rejection_reason?: string | null;
  strategy_name?: string;
  provider?: string;
}

export interface PaperPositionRecord {
  symbol: string;
  quantity: number;
  avg_entry_price: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  direction: "LONG" | "SHORT";
}

export interface PaperEventRecord {
  event_id?: number;
  event_type: string;
  timestamp: string;
  session_id: string;
  symbol?: string;
  close?: number;
  open?: number;
  high?: number;
  low?: number;
  volume?: number;
  signal_type?: string;
  approved?: boolean;
  reason?: string;
  order_id?: string;
  side?: string;
  quantity?: number;
  fill_price?: number;
  total_equity?: number;
  cash?: number;
  realized_pnl?: number;
  status?: string;
  message?: string;
  [key: string]: any;
}

export interface CreatePaperSessionPayload {
  dataset_id: string;
  symbols?: string[];
  timeframe?: string;
  strategy: string;
  strategy_params?: Record<string, any>;
  provider?: string;
  mode?: "HISTORICAL_REPLAY" | "REAL_TIME";
  data_provider?: string;
  data_provider_type?: string;
  live_provider?: string;
  max_data_age_seconds?: number;
  max_desync_seconds?: number;
  initial_capital?: number;
  speed?: string;
  allow_shorting?: boolean;
  start_date?: string;
  end_date?: string;
  execution_config?: {
    commission_fixed?: number;
    commission_percent?: number;
    slippage_bps?: number;
  };
  risk_config?: {
    max_position_pct?: number;
    max_drawdown_limit?: number;
    allow_shorting?: boolean;
    position_size_pct?: number;
  };
}

export interface PaperExportResult {
  session: PaperTradingSessionSummary;
  summary: {
    initial_capital: number;
    current_equity: number;
    net_profit: number;
    return_pct: number;
    realized_pnl: number;
    unrealized_pnl: number;
    total_trades: number;
    total_orders: number;
    total_bars_replayed: number;
    status: string;
  };
  equity_curve: Array<{
    timestamp: string;
    equity: number;
    cash: number;
    realized_pnl: number;
    unrealized_pnl: number;
  }>;
  trades: any[];
  orders: PaperOrderRecord[];
  events_sample: PaperEventRecord[];
}
