import { useState, type FormEvent } from "react";
import { Empty, ErrorNotice, MissionStrip } from "../components/ui";
import { usePoll } from "../hooks/usePoll";
import { api } from "../lib/api";
import { timeAgo } from "../lib/status";

export default function Dashboard() {
  const { data, error, loading, refresh } = usePoll(() => api.dashboard(), [], (d) => d.active_missions.some((m) => m.status !== "awaiting_approval"), 1500);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function create(e: FormEvent) {
    e.preventDefault();
    setCreating(true); setFormError(null);
    try { const p = await api.createProject(name.trim(), desc.trim()); window.location.hash = `#/projects/${p.id}/memory`; }
    catch (err) { setFormError(err instanceof Error ? err.message : "Could not create the project."); }
    finally { setCreating(false); }
  }

  const openTasks = data?.projects.reduce((n, p) => n + p.open_tasks, 0) ?? 0;
  const waiting = data?.active_missions.filter((m) => m.status === "awaiting_approval").length ?? 0;

  return (
    <>
      <h1 className="page">Dashboard</h1>
      <p className="lede">Every mission below shows what actually happened. A result is only stamped verified after MissionControl reads it back from the database.</p>
      <ErrorNotice error={error} onRetry={refresh} />
      {data && (
        <div className="stats">
          <div className="stat"><b className="num">{data.projects.length}</b><span>Projects</span></div>
          <div className="stat"><b className="num">{openTasks}</b><span>Unfinished tasks</span></div>
          <div className="stat"><b className="num">{data.active_missions.length}</b><span>Missions in progress</span></div>
          <div className="stat"><b className="num">{waiting}</b><span>Waiting for your approval</span></div>
        </div>
      )}

      <div className="grid-2">
        <section>
          <h2 className="section">Active missions</h2>
          {loading && !data ? <p className="muted">Loading missions…</p> : data?.active_missions.length ? (
            <div className="strips">{data.active_missions.map((m) => <MissionStrip key={m.id} m={m} showProject />)}</div>
          ) : <Empty>No mission is running. Open a project and ask MissionControl to do something.</Empty>}

          <h2 className="section">Recently finished</h2>
          {data?.recent_missions.length ? (
            <div className="strips">{data.recent_missions.map((m) => <MissionStrip key={m.id} m={m} showProject />)}</div>
          ) : <Empty>Finished missions appear here with their verification result.</Empty>}
        </section>

        <aside>
          <h2 className="section">Projects</h2>
          {data?.projects.length ? (
            <div className="strips">
              {data.projects.map((p) => (
                <a key={p.id} className="strip" href={`#/projects/${p.id}`} style={{ gridTemplateColumns: "8px minmax(0,1fr) auto" }}>
                  <span className="strip-edge" aria-hidden />
                  <span className="strip-body"><span className="strip-req" style={{ display: "block" }}>{p.name}</span><span className="strip-meta" style={{ display: "block" }}>{p.description || "No description yet"}</span></span>
                  <span className="strip-state"><span className="small muted num">{p.open_tasks} open</span></span>
                </a>
              ))}
            </div>
          ) : !loading && <Empty>No projects yet. Create one below.</Empty>}

          <form className="panel" style={{ marginTop: 14, display: "grid", gap: 12 }} onSubmit={create}>
            <strong>New project</strong>
            <div className="field"><label htmlFor="pname">Name</label><input id="pname" className="input" value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} /></div>
            <div className="field"><label htmlFor="pdesc">What is it?</label><textarea id="pdesc" className="input" value={desc} onChange={(e) => setDesc(e.target.value)} maxLength={5000} /></div>
            {formError && <div className="notice bad">{formError}</div>}
            <button className="btn btn-primary" disabled={creating || !name.trim()}>{creating ? "Creating…" : "Create project"}</button>
          </form>

          <h2 className="section">Recent activity</h2>
          {data?.recent_events.length ? (
            <ul className="checks">
              {data.recent_events.map((e) => (
                <li key={e.id}><span className={`small ${e.verification_status === "passed" ? "ok" : /failed|partially/.test(e.event_type) ? "no" : "muted"}`}>●</span><span className="small"><a href={`#/missions/${e.mission_id}`}>Mission #{e.mission_id}</a>: {e.description.length > 140 ? e.description.slice(0, 140) + "…" : e.description} <span className="muted">· {timeAgo(e.created_at)}</span></span></li>
              ))}
            </ul>
          ) : <p className="muted small">No activity yet.</p>}
        </aside>
      </div>
    </>
  );
}
