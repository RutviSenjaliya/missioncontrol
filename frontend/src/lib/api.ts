import type { Dashboard, Decision, Memory, Mission, Project, ReportMeta, Status, Task } from "./types";

const TOKEN_KEY = "missioncontrol.token";
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string | null) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY));

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken() ?? ""}` },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Can’t reach the MissionControl API. Check that the backend is running on port 8000.");
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = (data as { detail?: unknown }).detail;
    const msg = typeof d === "string" ? d : Array.isArray(d) ? d.map((x: { msg?: string }) => x.msg).join("; ") : `Request failed (${res.status})`;
    throw new ApiError(res.status, msg);
  }
  return data as T;
}

export const api = {
  me: () => req<{ id: number; name: string }>("GET", "/me"),
  status: () => req<Status>("GET", "/status"),
  dashboard: () => req<Dashboard>("GET", "/dashboard"),
  createProject: (name: string, description: string) => req<Project>("POST", "/projects", { name, description }),
  project: (id: number) => req<Project>("GET", `/projects/${id}`),
  memories: (pid: number) => req<Memory[]>("GET", `/projects/${pid}/memories`),
  createMemory: (pid: number, body: Partial<Memory>) => req<Memory>("POST", `/projects/${pid}/memories`, body),
  updateMemory: (id: number, body: Partial<Memory>) => req<Memory>("PATCH", `/memories/${id}`, body),
  deleteMemory: (id: number) => req<void>("DELETE", `/memories/${id}`),
  decisions: (pid: number) => req<Decision[]>("GET", `/projects/${pid}/decisions`),
  createDecision: (pid: number, body: { title: string; description: string; supersedes_decision_id?: number | null }) => req<Decision>("POST", `/projects/${pid}/decisions`, body),
  tasks: (pid: number) => req<Task[]>("GET", `/projects/${pid}/tasks`),
  createTask: (pid: number, body: { title: string; priority: Task["priority"] }) => req<Task>("POST", `/projects/${pid}/tasks`, body),
  updateTask: (id: number, body: Partial<Task>) => req<Task>("PATCH", `/tasks/${id}`, body),
  missions: (pid: number) => req<Mission[]>("GET", `/projects/${pid}/missions`),
  createMission: (pid: number, request: string) => req<Mission>("POST", `/projects/${pid}/missions`, { request }),
  mission: (id: number) => req<Mission>("GET", `/missions/${id}`),
  approve: (id: number) => req<Mission>("POST", `/missions/${id}/approve`),
  reject: (id: number) => req<Mission>("POST", `/missions/${id}/reject`),
  reports: (pid: number) => req<ReportMeta[]>("GET", `/projects/${pid}/reports`),
  report: (id: number) => req<ReportMeta>("GET", `/reports/${id}`),
};
