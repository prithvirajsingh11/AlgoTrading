import React, { useState, useEffect } from "react";
import { listDatasets } from "../services/datasets";
import { getMLFeatures, trainMLModel, runMLWalkForward } from "../services/ml";
import { createAndRunExperiment } from "../services/experiments";
import { DatasetMetadata, FeatureMetadata, MLTrainResult, WalkForwardMLResult, ExperimentResult } from "../types";
import { LoadingSpinner, ErrorMessage, StatusBadge, MetricsGrid } from "../components/Common";
import { Binary, Play, RefreshCw, Layers } from "lucide-react";

export const MLLabPage: React.FC = () => {
  const [datasets, setDatasets] = useState<DatasetMetadata[]>([]);
  const [featureDict, setFeatureDict] = useState<Record<string, FeatureMetadata>>({});
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [initError, setInitError] = useState<string | null>(null);

  // Configuration form
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("AAPL");
  const [horizon, setHorizon] = useState<number>(5);
  const [threshold, setThreshold] = useState<number>(0.0);
  const [nEstimators, setNEstimators] = useState<number>(100);
  const [maxDepth, setMaxDepth] = useState<number>(4);
  const [learningRate, setLearningRate] = useState<number>(0.05);
  const [seed] = useState<number>(42);

  // Execution states
  const [isTraining, setIsTraining] = useState(false);
  const [trainResult, setTrainResult] = useState<MLTrainResult | null>(null);

  const [isWalkForward, setIsWalkForward] = useState(false);
  const [walkForwardResult, setWalkForwardResult] = useState<WalkForwardMLResult | null>(null);

  const [isBacktesting, setIsBacktesting] = useState(false);
  const [backtestResult, setBacktestResult] = useState<ExperimentResult | null>(null);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const init = async () => {
      setLoadingInitial(true);
      setInitError(null);
      try {
        const [dList, fDict] = await Promise.all([listDatasets(), getMLFeatures()]);
        setDatasets(dList);
        setFeatureDict(fDict);
        if (dList.length > 0) {
          setSelectedDatasetId(dList[0].dataset_id);
        }
      } catch (err) {
        setInitError((err as Error).message);
      } finally {
        setLoadingInitial(false);
      }
    };
    init();
  }, []);

  const handleTrain = async () => {
    setIsTraining(true);
    setError(null);
    try {
      const res = await trainMLModel({
        dataset_id: selectedDatasetId,
        horizon,
        threshold,
        n_estimators: nEstimators,
        max_depth: maxDepth,
        learning_rate: learningRate,
        seed,
        train_pct: 0.6,
        val_pct: 0.2,
        test_pct: 0.2,
      });
      setTrainResult(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsTraining(false);
    }
  };

  const handleWalkForward = async () => {
    setIsWalkForward(true);
    setError(null);
    try {
      const res = await runMLWalkForward({
        dataset_id: selectedDatasetId,
        train_bars: 100,
        test_bars: 30,
        step_bars: 30,
        horizon,
        threshold,
        n_estimators: nEstimators,
        max_depth: maxDepth,
        learning_rate: learningRate,
        seed,
      });
      setWalkForwardResult(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsWalkForward(false);
    }
  };

  const handleRunBacktest = async () => {
    setIsBacktesting(true);
    setError(null);
    try {
      const ds = datasets.find((d) => d.dataset_id === selectedDatasetId);
      const res = await createAndRunExperiment({
        dataset: {
          dataset_id: selectedDatasetId,
          symbols: ds ? ds.symbols : [selectedDatasetId],
          timeframe: ds?.timeframe || "1d",
        },
        strategy: {
          name: "MLStrategy",
          parameters: {
            buy_threshold: 0.55,
            sell_threshold: 0.45,
          },
        },
        portfolio: { initial_capital: 100000 },
        execution: { commission_fixed: 1.0, commission_percent: 0.0005, slippage_bps: 5.0 },
        risk: {
          max_position_pct: 0.5,
          max_drawdown_limit: 0.3,
          allow_shorting: false,
          position_sizing_method: "percent_equity",
          position_size_pct: 0.2,
          risk_per_trade: 0.02,
        },
        seed,
        ml: {
          enabled: true,
          buy_threshold: 0.55,
          sell_threshold: 0.45,
        },
      });
      setBacktestResult(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsBacktesting(false);
    }
  };

  if (loadingInitial) return <LoadingSpinner message="Loading ML research environment..." />;
  if (initError) return <ErrorMessage message={initError} />;

  // Sort feature importance
  const sortedFeatures = trainResult
    ? Object.entries(trainResult.artifact.feature_importance || {}).sort((a, b) => b[1] - a[1])
    : [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Page Header */}
      <div>
        <h1 style={{ fontSize: "1.25rem", fontWeight: 700, letterSpacing: "-0.01em" }}>
          Supervised Machine Learning Lab
        </h1>
        <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
          Strict zero-lookahead feature engineering, XGBoost training, out-of-sample walk-forward evaluation, and feature importance analysis
        </p>
      </div>

      {/* Model Configuration Workbench */}
      <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
        <div style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--accent-blue)", marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <Binary size={18} /> Model &amp; Label Configuration
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem", marginBottom: "1.25rem" }}>
          <div>
            <label style={{ display: "block", fontSize: "0.7rem", color: "var(--text-secondary)", marginBottom: "0.25rem", textTransform: "uppercase" }}>
              Training Dataset
            </label>
            <select
              value={selectedDatasetId}
              onChange={(e) => setSelectedDatasetId(e.target.value)}
              style={{ width: "100%" }}
            >
              {datasets.map((d) => (
                <option key={d.dataset_id} value={d.dataset_id}>
                  {d.dataset_id} ({d.row_count} bars)
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ display: "block", fontSize: "0.7rem", color: "var(--text-secondary)", marginBottom: "0.25rem", textTransform: "uppercase" }}>
              Prediction Horizon (Bars)
            </label>
            <input
              type="number"
              value={horizon}
              onChange={(e) => setHorizon(Number(e.target.value))}
              min={1}
              max={50}
              style={{ width: "100%" }}
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "0.7rem", color: "var(--text-secondary)", marginBottom: "0.25rem", textTransform: "uppercase" }}>
              Label Return Threshold (e.g. 0.0)
            </label>
            <input
              type="number"
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              step={0.005}
              style={{ width: "100%" }}
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "0.7rem", color: "var(--text-secondary)", marginBottom: "0.25rem", textTransform: "uppercase" }}>
              XGBoost Trees (n_estimators)
            </label>
            <input
              type="number"
              value={nEstimators}
              onChange={(e) => setNEstimators(Number(e.target.value))}
              min={10}
              max={500}
              step={10}
              style={{ width: "100%" }}
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "0.7rem", color: "var(--text-secondary)", marginBottom: "0.25rem", textTransform: "uppercase" }}>
              Max Tree Depth
            </label>
            <input
              type="number"
              value={maxDepth}
              onChange={(e) => setMaxDepth(Number(e.target.value))}
              min={2}
              max={10}
              style={{ width: "100%" }}
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "0.7rem", color: "var(--text-secondary)", marginBottom: "0.25rem", textTransform: "uppercase" }}>
              Learning Rate
            </label>
            <input
              type="number"
              value={learningRate}
              onChange={(e) => setLearningRate(Number(e.target.value))}
              min={0.01}
              max={0.5}
              step={0.01}
              style={{ width: "100%" }}
            />
          </div>
        </div>

        {/* Action Triggers */}
        <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end", flexWrap: "wrap" }}>
          <button onClick={handleTrain} disabled={isTraining || isWalkForward || isBacktesting} className="btn btn-primary">
            {isTraining ? <LoadingSpinner message="Training..." /> : <><Play size={15} /> TRAIN MODEL</>}
          </button>
          <button onClick={handleWalkForward} disabled={isTraining || isWalkForward || isBacktesting} className="btn btn-secondary">
            {isWalkForward ? <LoadingSpinner message="Evaluating..." /> : <><Layers size={15} /> RUN WALK-FORWARD</>}
          </button>
          <button onClick={handleRunBacktest} disabled={isTraining || isWalkForward || isBacktesting} className="btn btn-secondary">
            {isBacktesting ? <LoadingSpinner message="Backtesting..." /> : <><RefreshCw size={15} /> RUN BACKTEST</>}
          </button>
        </div>
      </div>

      {error && <ErrorMessage message={error} />}

      {/* Area 1: Classification Performance */}
      {trainResult && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <div>
              <h2 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--status-purple)" }}>
                Area 1: Supervised Classification Performance
              </h2>
              <span className="mono" style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                Schema Hash: {trainResult.artifact.feature_schema_hash} · Model Version: {trainResult.artifact.model_version}
              </span>
            </div>
            <StatusBadge status="OUT-OF-SAMPLE TEST SET" variant="blue" />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "1rem", marginBottom: "1.25rem" }}>
            <div style={{ backgroundColor: "var(--bg-app)", padding: "0.75rem", borderRadius: "4px", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Test Accuracy</div>
              <div className="mono" style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                {(trainResult.test_metrics.accuracy * 100).toFixed(2)}%
              </div>
            </div>
            <div style={{ backgroundColor: "var(--bg-app)", padding: "0.75rem", borderRadius: "4px", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Precision</div>
              <div className="mono" style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                {(trainResult.test_metrics.precision * 100).toFixed(2)}%
              </div>
            </div>
            <div style={{ backgroundColor: "var(--bg-app)", padding: "0.75rem", borderRadius: "4px", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Recall</div>
              <div className="mono" style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                {(trainResult.test_metrics.recall * 100).toFixed(2)}%
              </div>
            </div>
            <div style={{ backgroundColor: "var(--bg-app)", padding: "0.75rem", borderRadius: "4px", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>F1-Score</div>
              <div className="mono" style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                {trainResult.test_metrics.f1.toFixed(3)}
              </div>
            </div>
            <div style={{ backgroundColor: "var(--bg-app)", padding: "0.75rem", borderRadius: "4px", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>ROC-AUC</div>
              <div className="mono" style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                {trainResult.test_metrics.roc_auc.toFixed(3)}
              </div>
            </div>
            <div style={{ backgroundColor: "var(--bg-app)", padding: "0.75rem", borderRadius: "4px", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Brier Score</div>
              <div className="mono" style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                {trainResult.test_metrics.brier_score.toFixed(4)}
              </div>
            </div>
          </div>

          {/* Confusion Matrix Table */}
          {trainResult.test_metrics.confusion_matrix && (
            <div style={{ backgroundColor: "var(--bg-app)", padding: "1rem", borderRadius: "4px", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.5rem", textTransform: "uppercase" }}>
                Out-Of-Sample Confusion Matrix
              </div>
              <div className="mono" style={{ display: "grid", gridTemplateColumns: "120px 100px 100px", gap: "0.5rem", fontSize: "0.8125rem", textAlign: "center" }}>
                <div style={{ color: "var(--text-muted)", textAlign: "left" }}>Actual \ Pred</div>
                <div style={{ backgroundColor: "var(--bg-surface-elevated)", padding: "0.35rem" }}>Pred DOWN (0)</div>
                <div style={{ backgroundColor: "var(--bg-surface-elevated)", padding: "0.35rem" }}>Pred UP (1)</div>

                <div style={{ color: "var(--text-secondary)", textAlign: "left" }}>Actual DOWN (0)</div>
                <div style={{ padding: "0.35rem", border: "1px solid var(--border-strong)" }}>
                  TN: {trainResult.test_metrics.confusion_matrix.true_negative}
                </div>
                <div style={{ padding: "0.35rem", border: "1px solid var(--border-strong)" }}>
                  FP: {trainResult.test_metrics.confusion_matrix.false_positive}
                </div>

                <div style={{ color: "var(--text-secondary)", textAlign: "left" }}>Actual UP (1)</div>
                <div style={{ padding: "0.35rem", border: "1px solid var(--border-strong)" }}>
                  FN: {trainResult.test_metrics.confusion_matrix.false_negative}
                </div>
                <div style={{ padding: "0.35rem", border: "1px solid var(--border-strong)" }}>
                  TP: {trainResult.test_metrics.confusion_matrix.true_positive}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Area 2: Trading Performance (Separated) */}
      {backtestResult && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
            <h2 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--accent-blue)" }}>
              Area 2: Event-Driven Trading Performance (MLStrategy)
            </h2>
            <StatusBadge status="TRADING EXECUTION" variant="green" />
          </div>
          <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: "1rem" }}>
            Signals routed through Risk Manager, broker slippage (5 bps), commissions, and cash limits.
          </p>
          <MetricsGrid metrics={backtestResult.metrics} />
        </div>
      )}

      {/* Feature Importance Table & Chart */}
      {sortedFeatures.length > 0 && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
          <h3 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "0.75rem" }}>
            Feature Importance (XGBoost Gain Ratio)
          </h3>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Feature Name</th>
                  <th>Category</th>
                  <th>Gain Importance</th>
                  <th>Formula / Origin</th>
                </tr>
              </thead>
              <tbody>
                {sortedFeatures.map(([featName, imp], idx) => {
                  const meta = featureDict[featName];
                  const pct = (imp * 100).toFixed(2);
                  return (
                    <tr key={featName}>
                      <td className="mono" style={{ color: "var(--text-muted)" }}>#{idx + 1}</td>
                      <td className="mono" style={{ fontWeight: 600 }}>{featName}</td>
                      <td>
                        <StatusBadge status={meta?.type || "rolling"} variant="blue" />
                      </td>
                      <td className="mono">
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                          <span>{pct}%</span>
                          <div style={{ width: "100px", height: "6px", backgroundColor: "var(--bg-app)", borderRadius: "3px", overflow: "hidden" }}>
                            <div style={{ width: `${Math.min(100, imp * 100 * 3)}%`, height: "100%", backgroundColor: "var(--accent-blue)" }} />
                          </div>
                        </div>
                      </td>
                      <td className="mono" style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                        {meta?.formula || meta?.description || "Calculated indicator"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Walk-Forward Rolling Windows View */}
      {walkForwardResult && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
          <h3 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "0.5rem" }}>
            Rolling Walk-Forward Out-Of-Sample Windows ({walkForwardResult.total_windows} Windows)
          </h3>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Window</th>
                  <th>Train Range</th>
                  <th>Test Range</th>
                  <th>Train Bars</th>
                  <th>Test Bars</th>
                  <th>Test Accuracy</th>
                  <th>F1 Score</th>
                  <th>ROC-AUC</th>
                </tr>
              </thead>
              <tbody>
                {walkForwardResult.windows.map((w) => (
                  <tr key={w.window_id}>
                    <td className="mono">Window #{w.window_id + 1}</td>
                    <td className="mono" style={{ fontSize: "0.75rem" }}>{w.train_start.split("T")[0]} → {w.train_end.split("T")[0]}</td>
                    <td className="mono" style={{ fontSize: "0.75rem" }}>{w.test_start.split("T")[0]} → {w.test_end.split("T")[0]}</td>
                    <td className="mono">{w.train_bars}</td>
                    <td className="mono">{w.test_bars}</td>
                    <td className="mono" style={{ fontWeight: 600 }}>{(w.classification_metrics.accuracy * 100).toFixed(1)}%</td>
                    <td className="mono">{w.classification_metrics.f1.toFixed(3)}</td>
                    <td className="mono">{w.classification_metrics.roc_auc.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
