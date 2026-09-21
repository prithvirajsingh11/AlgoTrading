import { request } from "./api";
import { DatasetMetadata, ValidationReport } from "../types";

export async function listDatasets(): Promise<DatasetMetadata[]> {
  return request<DatasetMetadata[]>("/datasets");
}

export async function getDataset(datasetId: string): Promise<DatasetMetadata> {
  return request<DatasetMetadata>(`/datasets/${datasetId}`);
}

export async function validateDataset(datasetId: string): Promise<ValidationReport> {
  return request<ValidationReport>(`/datasets/${datasetId}/validate`, {
    method: "POST",
  });
}
