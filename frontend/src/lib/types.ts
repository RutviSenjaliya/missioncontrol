// Shapes returned by the MissionControl REST API (backend/app/api/routes.py).
export type MissionStatus =
  | "pending" | "planning" | "awaiting_approval" | "running" | "verifying"
  | "completed" | "failed" | "partially_completed" | "cancelled";
export type Verification = "passed" | "failed" | "not_applicable" | null;

export interface Project { id: number; name: string; description: string; open_tasks: number; created_at: string; updated_at: string }
export interface Memory {
  id: number; project_id: number; memory_type: "semantic" | "episodic" | "procedural" | "working";
  content: string; source: string; status: "active" | "superseded"; confirmation: "confirmed" | "tentative";
  tags: string[]; supersedes_id: number | null; mission_id: number | null; created_at: string; updated_at: string;
}
export interface Decision { id: number; title: string; description: string; status: "confirmed" | "proposed" | "superseded"; source: string; supersedes_decision_id: number | null; created_at: string }
export interface Task { id: number; title: string; description: string; status: "open" | "in_progress" | "blocked" | "done"; priority: "high" | "medium" | "low"; completed_at: string | null; created_at: string }
export interface PlanStep { n: number; tool: string; args: Record<string, unknown>; purpose: string; role: "action" | "verify" | "read"; check?: { type: string } }
export interface Plan { mission_type: string; summary: string; requires_approval: boolean; steps: PlanStep[]; success_conditions: string[]; provider?: string }
export interface ExecEvent { id: number; mission_id: number; seq: number; event_type: string; description: string; tool_name: string | null; result: unknown; verification_status: Verification; created_at: string; project_name?: string }
export interface Check { check: string; passed: boolean; detail: string }
export interface ReportMeta { id: number; project_id: number; mission_id: number | null; title: string; required_sections: string[]; verification_status: Verification; verification_details: { checks: Check[] } | null; created_at: string; content?: string }
export interface Mission {
  id: number; project_id: number; request: string; mission_type: string | null; status: MissionStatus; plan: Plan | null;
  requires_approval: boolean; approved_at: string | null; result_summary: string | null; error: string | null; tool_calls: number;
  created_at: string; started_at: string | null; completed_at: string | null; events?: ExecEvent[]; reports?: ReportMeta[]; project_name?: string;
}
export interface Dashboard { projects: Project[]; active_missions: Mission[]; recent_missions: Mission[]; recent_events: ExecEvent[] }
export interface Status {
  database: { ok: boolean; dialect?: string; error?: string };
  mcp: { ok: boolean; url: string; server?: string; protocol_version?: string; transport?: string; tools?: { name: string; description: string }[]; error?: string };
  ai_provider: { name: string; model: string | null };
  limits: Record<string, number>;
}
