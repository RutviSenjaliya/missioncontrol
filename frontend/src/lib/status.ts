import type { MissionStatus, Verification } from "./types";

export const TERMINAL: MissionStatus[] = ["completed", "failed", "partially_completed", "cancelled"];
export const isTerminal = (s: MissionStatus) => TERMINAL.includes(s);

export type Tone = "neutral" | "active" | "waiting" | "good" | "bad" | "partial";

export function statusTone(s: MissionStatus): Tone {
  switch (s) {
    case "completed": return "good";
    case "failed": return "bad";
    case "partially_completed": return "partial";
    case "awaiting_approval": return "waiting";
    case "planning": case "running": case "verifying": return "active";
    default: return "neutral";
  }
}

export const STATUS_LABEL: Record<MissionStatus, string> = {
  pending: "Pending", planning: "Planning", awaiting_approval: "Needs your approval", running: "Running",
  verifying: "Verifying", completed: "Completed", failed: "Failed", partially_completed: "Partially completed", cancelled: "Cancelled",
};

export function verificationLabel(v: Verification): string {
  if (v === "passed") return "Verified";
  if (v === "failed") return "Verification failed";
  if (v === "not_applicable") return "Read-only";
  return "Not verified";
}

export function timeAgo(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "";
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}
