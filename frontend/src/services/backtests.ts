import { request } from "./api";
import { OHLCVBar } from "../types";

export interface BacktestRunParams {
  symbol: string;
  strategy: string;
  parameters: Record<string, unknown>;
  initial_capital: number;
  commission_fixed?: number;
  commission_percent?: number;
  slippage_bps?: number;
  position_size_pct?: number;
  max_position_pct?: number;
  max_drawdown_limit?: number;
}

export async function runBacktest(params: BacktestRunParams): Promise<unknown> {
  return request("/backtest/run", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function getHistoricalBars(
  symbol: string,
  limit = 200
): Promise<OHLCVBar[]> {
  return request<OHLCVBar[]>(`/market/data/${symbol}?limit=${limit}`);
}

export async function listAvailableSymbols(): Promise<string[]> {
  return request<string[]>("/market/symbols");
}
