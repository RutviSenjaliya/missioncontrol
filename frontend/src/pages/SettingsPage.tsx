import { ErrorNotice } from "../components/ui";
import { usePoll } from "../hooks/usePoll";
import { api } from "../lib/api";

export default function SettingsPage() {
  const { data: s, error, loading, refresh } = usePoll(() => api.status(), []);
  return (
    <>
      <h1 className="page">Connections</h1>
      <p className="lede">Live status of the services MissionControl depends on. Secrets are never shown here.</p>
      <ErrorNotice error={error} onRetry={refresh} />
      {loading && !s && <p className="muted">Checking connections…</p>}
      {s && (
        <div style={{ display: "grid", gap: 16 }}>
          <div className="panel">
            <div className="spread"><strong>MCP server</strong><span className={`pill ${s.mcp.ok ? "good" : "bad"}`}>{s.mcp.ok ? "Connected" : "Unreachable"}</span></div>
            <p className="small" style={{ marginBottom: 6 }}>Endpoint <span className="code">{s.mcp.url}</span>{s.mcp.ok && <> · protocol <span className="code">{s.mcp.protocol_version}</span> · {s.mcp.transport}</>}</p>
            {s.mcp.error && <div className="notice bad small">{s.mcp.error}. Start it with <span className="code">./scripts/run_mcp_server.sh</span>.</div>}
            {s.mcp.tools && (
              <div className="table-wrap" style={{ marginTop: 10 }}>
                <table><thead><tr><th>Tool</th><th>What it does</th></tr></thead>
                  <tbody>{s.mcp.tools.map((t) => <tr key={t.name}><td><span className="code">{t.name}</span></td><td className="small">{t.description}</td></tr>)}</tbody></table>
              </div>
            )}
          </div>
          <div className="panel"><div className="spread"><strong>Database</strong><span className={`pill ${s.database.ok ? "good" : "bad"}`}>{s.database.ok ? s.database.dialect : "Unavailable"}</span></div></div>
          <div className="panel">
            <div className="spread"><strong>Planner</strong><span className="pill">{s.ai_provider.name}{s.ai_provider.model ? ` · ${s.ai_provider.model}` : ""}</span></div>
            <p className="small muted" style={{ marginBottom: 0 }}>Limits per mission: {s.limits.max_tool_calls} tool calls, {s.limits.tool_timeout_seconds}s per tool, {s.limits.mission_timeout_seconds}s total, {s.limits.max_retries} retry for safe steps.</p>
          </div>
          <button className="btn" style={{ justifySelf: "start" }} onClick={refresh}>Check again</button>
        </div>
      )}
    </>
  );
}
