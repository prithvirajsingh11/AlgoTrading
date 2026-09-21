import { request } from "./api";
import { JevDecision, JevStatus } from "../types";

export async function getJevStatus(): Promise<JevStatus> {
  return request<JevStatus>("/ai/jev/status");
}

export async function evaluateJev(
  context: Record<string, unknown>,
  configHash = ""
): Promise<JevDecision> {
  return request<JevDecision>("/ai/jev/evaluate", {
    method: "POST",
    body: JSON.stringify({ context, config_hash: configHash }),
  });
}
