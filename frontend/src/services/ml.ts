import { request } from "./api";
import { FeatureMetadata, MLTrainResult, WalkForwardMLResult } from "../types";

export interface MLTrainParams {
  dataset_id: string;
  horizon?: number;
  threshold?: number;
  n_estimators?: number;
  max_depth?: number;
  learning_rate?: number;
  seed?: number;
  train_pct?: number;
  val_pct?: number;
  test_pct?: number;
  calibration_method?: string;
}

export interface MLWalkForwardParams {
  dataset_id: string;
  train_bars?: number;
  test_bars?: number;
  step_bars?: number;
  horizon?: number;
  threshold?: number;
  n_estimators?: number;
  max_depth?: number;
  learning_rate?: number;
  seed?: number;
}

export async function getMLFeatures(): Promise<Record<string, FeatureMetadata>> {
  return request<Record<string, FeatureMetadata>>("/ml/features");
}

export async function trainMLModel(params: MLTrainParams): Promise<MLTrainResult> {
  return request<MLTrainResult>("/ml/train", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function runMLWalkForward(
  params: MLWalkForwardParams
): Promise<WalkForwardMLResult> {
  return request<WalkForwardMLResult>("/ml/walk-forward", {
    method: "POST",
    body: JSON.stringify(params),
  });
}
