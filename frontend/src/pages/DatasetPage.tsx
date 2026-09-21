import React, { useState, useEffect } from "react";
import { listDatasets, validateDataset } from "../services/datasets";
import { DatasetMetadata, ValidationReport } from "../types";
import { LoadingSpinner, ErrorMessage, StatusBadge, EmptyState } from "../components/Common";
import { CheckCircle, AlertTriangle, XCircle, RefreshCw } from "lucide-react";

export const DatasetPage: React.FC = () => {
  const [datasets, setDatasets] = useState<DatasetMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Validation report state
  const [validatingId, setValidatingId] = useState<string | null>(null);
  const [reports, setReports] = useState<Record<string, ValidationReport>>({});
  const [activeReportId, setActiveReportId] = useState<string | null>(null);

  const fetchDatasets = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listDatasets();
      setDatasets(data);
      if (data.length > 0 && !activeReportId) {
        // Automatically validate first dataset to show report
        handleValidate(data[0].dataset_id);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDatasets();
  }, []);

  const handleValidate = async (id: string) => {
    setValidatingId(id);
    setActiveReportId(id);
    try {
      const report = await validateDataset(id);
      setReports((prev) => ({ ...prev, [id]: report }));
    } catch (err) {
      setError(`Failed validating ${id}: ${(err as Error).message}`);
    } finally {
      setValidatingId(null);
    }
  };

  if (loading && datasets.length === 0) return <LoadingSpinner message="Discovering historical datasets..." />;
  if (error && datasets.length === 0) return <ErrorMessage message={error} onRetry={fetchDatasets} />;

  const activeReport = activeReportId ? reports[activeReportId] : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 style={{ fontSize: "1.25rem", fontWeight: 700, letterSpacing: "-0.01em" }}>
            Dataset Manager
          </h1>
          <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
            Discovered market feeds, chronological integrity checks, and quantitative data validation
          </p>
        </div>
        <button onClick={fetchDatasets} className="btn btn-secondary btn-sm">
          <RefreshCw size={14} /> Refresh Catalog
        </button>
      </div>

      {error && <ErrorMessage message={error} />}

      {/* Dataset Inventory Table */}
      <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
        <h2 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: "0.75rem" }}>
          Discovered Historical Datasets ({datasets.length})
        </h2>

        {datasets.length === 0 ? (
          <EmptyState title="No Datasets Found" message="Check backend data/raw/ directory for CSV market feeds." />
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Dataset ID</th>
                  <th>Symbols</th>
                  <th>Timeframe</th>
                  <th>Rows</th>
                  <th>Start Date</th>
                  <th>End Date</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {datasets.map((d) => {
                  const isValidating = validatingId === d.dataset_id;
                  const isInspected = activeReportId === d.dataset_id;
                  return (
                    <tr key={d.dataset_id} style={{ backgroundColor: isInspected ? "rgba(59, 130, 246, 0.05)" : "transparent" }}>
                      <td className="mono" style={{ fontWeight: 600 }}>{d.dataset_id}</td>
                      <td className="mono">{d.symbols.join(", ")}</td>
                      <td className="mono">{d.timeframe}</td>
                      <td className="mono">{d.row_count.toLocaleString()}</td>
                      <td className="mono" style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                        {d.start_timestamp ? d.start_timestamp.split("T")[0] : "-"}
                      </td>
                      <td className="mono" style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                        {d.end_timestamp ? d.end_timestamp.split("T")[0] : "-"}
                      </td>
                      <td>{d.source}</td>
                      <td>
                        <StatusBadge
                          status={reports[d.dataset_id] ? (reports[d.dataset_id].valid ? "VALID" : "INVALID") : d.validation_status}
                        />
                      </td>
                      <td>
                        <button
                          onClick={() => handleValidate(d.dataset_id)}
                          disabled={isValidating}
                          className="btn btn-secondary btn-sm"
                        >
                          {isValidating ? (
                            <RefreshCw size={12} className="animate-spin" />
                          ) : (
                            <CheckCircle size={12} />
                          )}
                          VALIDATE DATASET
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Validation Report Area */}
      {activeReportId && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <div>
              <h3 style={{ fontSize: "1rem", fontWeight: 700 }}>
                Validation Report: {activeReportId}
              </h3>
              <p style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                Strict statistical and structural sanity verification
              </p>
            </div>
            {activeReport && (
              <StatusBadge
                status={activeReport.valid ? "PASSED SANITY CHECKS" : "VALIDATION ISSUES DETECTED"}
                variant={activeReport.valid ? "green" : "red"}
              />
            )}
          </div>

          {validatingId === activeReportId ? (
            <LoadingSpinner message={`Running integrity audit on ${activeReportId}...`} />
          ) : activeReport ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              {/* Summary Stats */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "1rem" }}>
                <div style={{ padding: "0.75rem", backgroundColor: "var(--bg-app)", borderRadius: "4px", border: "1px solid var(--border-subtle)" }}>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Total Rows</div>
                  <div className="mono" style={{ fontSize: "1.2rem", fontWeight: 700 }}>{activeReport.total_rows.toLocaleString()}</div>
                </div>
                <div style={{ padding: "0.75rem", backgroundColor: "var(--bg-app)", borderRadius: "4px", border: "1px solid var(--border-subtle)" }}>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Start Timestamp</div>
                  <div className="mono" style={{ fontSize: "0.85rem", fontWeight: 600 }}>{activeReport.start_date ? activeReport.start_date.split("T")[0] : "-"}</div>
                </div>
                <div style={{ padding: "0.75rem", backgroundColor: "var(--bg-app)", borderRadius: "4px", border: "1px solid var(--border-subtle)" }}>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>End Timestamp</div>
                  <div className="mono" style={{ fontSize: "0.85rem", fontWeight: 600 }}>{activeReport.end_date ? activeReport.end_date.split("T")[0] : "-"}</div>
                </div>
                <div style={{ padding: "0.75rem", backgroundColor: "var(--bg-app)", borderRadius: "4px", border: "1px solid var(--border-subtle)" }}>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Error Count</div>
                  <div className="mono" style={{ fontSize: "1.2rem", fontWeight: 700, color: activeReport.errors.length > 0 ? "var(--status-red)" : "var(--status-green)" }}>
                    {activeReport.errors.length}
                  </div>
                </div>
              </div>

              {/* Validation Errors Section */}
              {activeReport.errors.length > 0 && (
                <div style={{ padding: "1rem", backgroundColor: "var(--status-red-subtle)", border: "1px solid rgba(239, 68, 68, 0.3)", borderRadius: "4px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--status-red)", fontWeight: 700, fontSize: "0.875rem", marginBottom: "0.5rem" }}>
                    <XCircle size={16} /> Critical Validation Errors ({activeReport.errors.length}):
                  </div>
                  <ul style={{ paddingLeft: "1.5rem", fontSize: "0.8125rem", color: "var(--status-red)", display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                    {activeReport.errors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Warnings Section */}
              {activeReport.warnings.length > 0 && (
                <div style={{ padding: "1rem", backgroundColor: "var(--status-amber-subtle)", border: "1px solid rgba(245, 158, 11, 0.3)", borderRadius: "4px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--status-amber)", fontWeight: 700, fontSize: "0.875rem", marginBottom: "0.5rem" }}>
                    <AlertTriangle size={16} /> Dataset Warnings ({activeReport.warnings.length}):
                  </div>
                  <ul style={{ paddingLeft: "1.5rem", fontSize: "0.8125rem", color: "var(--status-amber)", display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                    {activeReport.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Passed Checks */}
              {activeReport.errors.length === 0 && (
                <div style={{ padding: "1rem", backgroundColor: "var(--status-green-subtle)", border: "1px solid rgba(16, 185, 129, 0.3)", borderRadius: "4px", color: "var(--status-green)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontWeight: 700, fontSize: "0.875rem", marginBottom: "0.5rem" }}>
                    <CheckCircle size={16} /> All Quantitative Integrity Checks Passed:
                  </div>
                  <div style={{ fontSize: "0.8125rem", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "0.5rem" }}>
                    <div>✓ Strict chronological timestamp ordering</div>
                    <div>✓ No future lookahead bar leakage</div>
                    <div>✓ Non-zero positive prices (OHLC)</div>
                    <div>✓ High &ge; Open, Low, Close invariants</div>
                    <div>✓ Low &le; Open, High, Close invariants</div>
                    <div>✓ Non-negative volume bars</div>
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
};
