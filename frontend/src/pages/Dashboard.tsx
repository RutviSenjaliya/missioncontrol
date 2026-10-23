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

  // Each summary card opens the most useful place for what it counts.
  const open = (hash: string) => { window.location.hash = hash; };
  const scrollTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  const projects = data?.projects ?? [];
  const active = data?.active_missions ?? [];
  const running = active.filter((m) => m.status !== "awaiting_approval");
  const awaiting = active.filter((m) => m.status === "awaiting_approval");
  const taskProject = projects.find((p) => p.open_tasks > 0) ?? projects[0];
  const cards = [
    { label: "Projects", value: projects.length,
      hint: projects.length === 1 ? `Open ${projects[0].name}` : "See all projects",
      go: () => (projects.length === 1 ? open(`#/projects/${projects[0].id}`) : scrollTo("projects-list")) },
    { label: "Unfinished tasks", value: openTasks,
      hint: taskProject ? "See unfinished tasks" : "Create a project first",
      go: () => (taskProject ? open(`#/projects/${taskProject.id}/work/unfinished`) : scrollTo("projects-list")) },
    { label: "Missions in progress", value: active.length,
      hint: running.length === 1 ? "Open the running mission" : active.length ? "See active missions" : "Start one in a project",
      go: () => (running.length === 1 && awaiting.length === 0 ? open(`#/missions/${running[0].id}`)
        : active.length ? scrollTo("active-missions") : projects[0] ? open(`#/projects/${projects[0].id}/missions`) : scrollTo("projects-list")) },
    { label: "Waiting for your approval", value: waiting,
      hint: awaiting.length === 1 ? "Review and approve" : awaiting.length ? "See missions to approve" : "Nothing to approve",
      go: () => (awaiting.length === 1 ? open(`#/missions/${awaiting[0].id}`) : scrollTo("active-missions")) },
  ];

  return (
    <>
      <h1 className="page">Dashboard</h1>
      <p className="lede">Every mission below shows what actually happened. A result is only stamped verified after MissionControl reads it back from the database.</p>
      <ErrorNotice error={error} onRetry={refresh} />
      {data && (
        <div className="stats">
          {cards.map((c) => (
            <button key={c.label} type="button" className="stat stat-link" onClick={c.go} title={c.hint}>
              <b className="num">{c.value}</b><span>{c.label}</span><small>{c.hint} →</small>
            </button>
          ))}
        </div>
      )}

      <div className="grid-2">
        <section>
          <h2 className="section" id="active-missions">Active missions</h2>
          {loading && !data ? <p className="muted">Loading missions…</p> : data?.active_missions.length ? (
            <div className="strips">{data.active_missions.map((m) => <MissionStrip key={m.id} m={m} showProject />)}</div>
          ) : <Empty>No mission is running. Open a project and ask MissionControl to do something.</Empty>}

          <h2 className="section">Recently finished</h2>
          {data?.recent_missions.length ? (
            <div className="strips">{data.recent_missions.map((m) => <MissionStrip key={m.id} m={m} showProject />)}</div>
          ) : <Empty>Finished missions appear here with their verification result.</Empty>}
        </section>

        <aside>
          <h2 className="section" id="projects-list">Projects</h2>
          {data?.projects.length ? (
            <div className="strips">
              {data.projects.map((p) => (
                <a key={p.id} className="strip" href={`#/projects/${p.id}`} style={{ gridTemplateColumns: "8px minmax(0,1fr) auto" }}>
                  <span className="strip-edge" aria-hidden />
                  <span className="strip-body"><span className="strip-req" style={{ display: "block" }}>{p.name}</span><span className="strip-meta" style={{ display: "block" }}>{p.description || "No description yet"}</span></span>
                  <span className="strip-state"><span className="small muted num" title="Unfinished tasks">{p.open_tasks} open</span></span>
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
