import { request } from "./api";
import {
  PaperTradingStatus,
  PaperTradingSessionSummary,
  PaperOrderRecord,
  PaperPositionRecord,
  PaperEventRecord,
  CreatePaperSessionPayload,
  PaperExportResult,
} from "../types";

export async function getPaperStatus(): Promise<PaperTradingStatus> {
  return request<PaperTradingStatus>("/paper/status");
}

export async function listPaperSessions(): Promise<PaperTradingSessionSummary[]> {
  return request<PaperTradingSessionSummary[]>("/paper/sessions");
}

export async function getPaperSession(sessionId: string): Promise<PaperTradingSessionSummary> {
  return request<PaperTradingSessionSummary>(`/paper/sessions/${sessionId}`);
}

export async function createPaperSession(payload: CreatePaperSessionPayload): Promise<PaperTradingSessionSummary> {
  return request<PaperTradingSessionSummary>("/paper/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function startPaperSession(sessionId: string): Promise<PaperTradingSessionSummary> {
  return request<PaperTradingSessionSummary>(`/paper/sessions/${sessionId}/start`, {
    method: "POST",
  });
}

export async function pausePaperSession(sessionId: string): Promise<PaperTradingSessionSummary> {
  return request<PaperTradingSessionSummary>(`/paper/sessions/${sessionId}/pause`, {
    method: "POST",
  });
}

export async function resumePaperSession(sessionId: string): Promise<PaperTradingSessionSummary> {
  return request<PaperTradingSessionSummary>(`/paper/sessions/${sessionId}/resume`, {
    method: "POST",
  });
}

export async function stopPaperSession(sessionId: string): Promise<PaperTradingSessionSummary> {
  return request<PaperTradingSessionSummary>(`/paper/sessions/${sessionId}/stop`, {
    method: "POST",
  });
}

export async function stepPaperSession(
  sessionId: string
): Promise<{ session: PaperTradingSessionSummary; events_count: number; events: PaperEventRecord[] }> {
  return request<{ session: PaperTradingSessionSummary; events_count: number; events: PaperEventRecord[] }>(
    `/paper/sessions/${sessionId}/step`,
    {
      method: "POST",
    }
  );
}

export async function changePaperSpeed(sessionId: string, speed: string): Promise<PaperTradingSessionSummary> {
  return request<PaperTradingSessionSummary>(`/paper/sessions/${sessionId}/speed`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ speed }),
  });
}

export async function getPaperOrders(sessionId: string): Promise<PaperOrderRecord[]> {
  return request<PaperOrderRecord[]>(`/paper/sessions/${sessionId}/orders`);
}

export async function getPaperPositions(sessionId: string): Promise<PaperPositionRecord[]> {
  return request<PaperPositionRecord[]>(`/paper/sessions/${sessionId}/positions`);
}

export async function getPaperEvents(sessionId: string, limit: number = 100): Promise<PaperEventRecord[]> {
  return request<PaperEventRecord[]>(`/paper/sessions/${sessionId}/events?limit=${limit}`);
}

export async function exportPaperResults(sessionId: string): Promise<PaperExportResult> {
  return request<PaperExportResult>(`/paper/sessions/${sessionId}/export`);
}

export function getPaperWebSocketUrl(sessionId: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.hostname || "localhost";
  const port = "8000";
  return `${protocol}//${host}:${port}/api/v1/paper/ws/${sessionId}`;
}
