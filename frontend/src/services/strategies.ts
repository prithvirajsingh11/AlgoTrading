import { request } from "./api";
import { StrategyMetadata } from "../types";

export async function listStrategies(): Promise<StrategyMetadata[]> {
  return request<StrategyMetadata[]>("/strategies");
}

export async function getStrategy(strategyId: string): Promise<StrategyMetadata> {
  return request<StrategyMetadata>(`/strategies/${strategyId}`);
}
