import { request } from "./api";
import { ExperimentConfig, ExperimentResult, ProviderComparisonResult } from "../types";

export async function createAndRunExperiment(
  config: Partial<ExperimentConfig>
): Promise<ExperimentResult> {
  return request<ExperimentResult>("/experiments", {
    method: "POST",
    body: JSON.stringify(config),
  });
}

export async function listExperiments(limit = 100): Promise<Array<Record<string, unknown>>> {
  return request<Array<Record<string, unknown>>>(`/experiments?limit=${limit}`);
}

export async function getExperiment(experimentId: string): Promise<ExperimentResult> {
  return request<ExperimentResult>(`/experiments/${experimentId}`);
}

export async function rerunExperiment(experimentId: string): Promise<ExperimentResult> {
  return request<ExperimentResult>(`/experiments/${experimentId}/run`, {
    method: "POST",
  });
}

export async function compareExperiments(
  experimentIds: string[]
): Promise<ProviderComparisonResult> {
  return request<ProviderComparisonResult>("/experiments/compare", {
    method: "POST",
    body: JSON.stringify({ experiment_ids: experimentIds }),
  });
}
