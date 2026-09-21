import { request } from "./api";
import { PaperTradingStatus, PortfolioSummary, Position } from "../types";

export async function getPortfolioSummary(): Promise<PortfolioSummary> {
  return request<PortfolioSummary>("/portfolio/summary");
}

export async function listPositions(): Promise<Position[]> {
  return request<Position[]>("/portfolio/positions");
}

export async function getPaperStatus(): Promise<PaperTradingStatus> {
  return request<PaperTradingStatus>("/paper/status");
}
