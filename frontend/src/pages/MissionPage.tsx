import { useState } from "react";
import { ErrorNotice, Stamp, StatusPill, missionVerification } from "../components/ui";
import { usePoll } from "../hooks/usePoll";
import { api } from "../lib/api";
import { isTerminal } from "../lib/status";
import type { ExecEvent, Check } from "../lib/types";

function eventTone(e: ExecEvent): string {
  if (e.verification_status === "passed" || e.event_type === "mission_completed") return "good";
  if (e.verification_status === "failed" || /failed|unavailable/.test(e.event_type)) return "bad";
  if (e.event_type === "approval_requested") return "waiting";
  if (e.event_type === "tool_invoked") return "active";
  return "";
}

export default function MissionPage({ id }: { id: number }) {
  const { data: m, error, refresh } = usePoll(() => api.mission(id), [id], (d) => !isTerminal(d.status) && d.status !== "awaiting_approval");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true); setActionError(null);
    try { await fn(); } catch (e) { setActionError(e instanceof Error ? e.message : String(e)); }
    // keep polling until the mission settles
    const poll = async () => { const d = await refresh(); if (d && !isTerminal(d.status) && d.status !== "awaiting_approval") setTimeout(poll, 800); else setBusy(false); };
    poll();
  }

  if (error && !m) return <ErrorNotice error={error} onRetry={refresh} />;
  if (!m) return <p className="muted">Loading mission…</p>;

  const verifyEvents = (m.events ?? []).filter((e) => e.event_type === "verification");
  const reportChecks = verifyEvents.flatMap((e) => ((e.result as { checks?: Check[] } | null)?.checks ?? []));
  const mcp = (m.events ?? []).find((e) => e.event_type === "mcp_connected")?.result as { protocol_version?: string; tools?: string[] } | undefined;
  const v = missionVerification(m);

  return (
    <>
      <p className="small muted" style={{ margin: "0 0 6px" }}><a href={`#/projects/${m.project_id}`}>Back to project</a></p>
      <div className="spread"><h1 className="page num">Mission #{m.id}</h1><div className="row"><StatusPill status={m.status} /><Stamp v={v} /></div></div>
      <p className="lede">“{m.request}”</p>

      {m.status === "awaiting_approval" && (
        <div className="notice waiting">
          <div className="spread">
            <span><strong>This mission will change project records.</strong> Nothing has been changed yet. Review the plan, then approve or reject it.</span>
            <span className="row">
              <button className="btn btn-approve" disabled={busy} onClick={() => act(() => api.approve(m.id))}>Approve and run</button>
              <button className="btn btn-danger" disabled={busy} onClick={() => act(() => api.reject(m.id))}>Reject</button>
            </span>
          </div>
        </div>
      )}
      {m.error && <div className={`notice ${m.status === "partially_completed" ? "waiting" : "bad"}`}><strong>{m.status === "partially_completed" ? "Not complete. " : "Failed. "}</strong>{m.error}</div>}
      {m.status === "completed" && m.result_summary && <div className="notice good"><strong>Done. </strong>{m.result_summary}</div>}
      <ErrorNotice error={actionError} />

      <div className="grid-2">
        <section>
          <h2 className="section">Execution timeline</h2>
          <ol className="timeline">
            {(m.events ?? []).map((e) => (
              <li key={e.id} className={`tl-item ${eventTone(e)}`}>
                <span className="tl-dot num">{e.seq}</span>
                <div className="tl-text">
                  {e.tool_name && <div className="tl-tool">{e.tool_name}</div>}
                  <div>{e.description}</div>
                  {e.result != null && <details className="raw"><summary>Recorded data</summary><pre>{JSON.stringify(e.result, null, 2)}</pre></details>}
                </div>
              </li>
            ))}
          </ol>
          {!isTerminal(m.status) && m.status !== "awaiting_approval" && <p className="muted small">Updating live…</p>}
        </section>

        <aside style={{ display: "grid", gap: 16 }}>
          <div className="panel evidence">
            <h3>Verification evidence</h3>
            {v === "passed" && <p className="small" style={{ marginTop: 0 }}>Checked by MissionControl against data read back from the database — not taken from the agent’s own words.</p>}
            {v === "not_applicable" && <p className="small" style={{ marginTop: 0 }}>Read-only mission: no records changed, so there was nothing to verify.</p>}
            {verifyEvents.length === 0 && v !== "not_applicable" && <p className="small muted" style={{ marginTop: 0 }}>No verification has run yet.</p>}
            <ul className="checks">
              {reportChecks.length
                ? reportChecks.map((c, i) => <li key={i}><span className={c.passed ? "ok" : "no"}>{c.passed ? "✓" : "✗"}</span><span>{c.check.replace("section:", "Section: ").replace(/_/g, " ")} <span className="muted">— {c.detail}</span></span></li>)
                : verifyEvents.filter((e) => e.verification_status !== "not_applicable").map((e) => <li key={e.id}><span className={e.verification_status === "passed" ? "ok" : "no"}>{e.verification_status === "passed" ? "✓" : "✗"}</span><span>{e.description}</span></li>)}
            </ul>
            {(m.reports ?? []).map((r) => <p key={r.id} style={{ marginBottom: 0 }}><a href={`#/reports/${r.id}`}>Open report #{r.id}: {r.title}</a></p>)}
            {m.plan?.success_conditions && (
              <div className="claim"><div className="claim-label">Success conditions set before execution</div><ul className="small" style={{ margin: "6px 0 0", paddingLeft: 18 }}>{m.plan.success_conditions.map((s, i) => <li key={i}>{s}</li>)}</ul></div>
            )}
          </div>

          {m.plan && (
            <div className="panel evidence">
              <h3>Plan</h3>
              <p className="small" style={{ marginTop: 0 }}>{m.plan.summary}</p>
              <ol className="plan small">
                {m.plan.steps.map((s) => <li key={s.n}><code>{s.tool}</code> {s.purpose}{s.role === "verify" && <span className="muted"> (verification)</span>}</li>)}
              </ol>
              <p className="small muted" style={{ marginBottom: 0 }}>Planner: {m.plan.provider ?? "unknown"} · {m.tool_calls} tool call(s) used</p>
            </div>
          )}

          {mcp && (
            <div className="panel evidence">
              <h3>MCP connection</h3>
              <p className="small" style={{ margin: 0 }}>Protocol <span className="code">{mcp.protocol_version}</span> over Streamable HTTP. Tools discovered: {mcp.tools?.length ?? 0}.</p>
            </div>
          )}
        </aside>
      </div>
    </>
  );
}
