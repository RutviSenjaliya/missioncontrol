import { useState, type FormEvent } from "react";
import { Empty, ErrorNotice, MissionStrip, Stamp } from "../components/ui";
import { usePoll } from "../hooks/usePoll";
import { api } from "../lib/api";
import { isTerminal, timeAgo } from "../lib/status";
import type { Memory, Task } from "../lib/types";

const TABS = [
  { id: "missions", label: "Missions" },
  { id: "memory", label: "Memory" },
  { id: "work", label: "Tasks & decisions" },
  { id: "reports", label: "Reports" },
];

const EXAMPLES = [
  "Create a project handoff report",
  "Create a sprint plan from our goals, decisions and unfinished tasks",
  "Summarize our progress",
  "Show open tasks",
  "Add task: Record the demo video (high priority)",
  "Record decision: Use PostgreSQL - one shared source of truth",
];

export default function ProjectPage({ id, tab, view }: { id: number; tab: string; view?: string }) {
  const project = usePoll(() => api.project(id), [id]);
  if (project.error && !project.data) return <ErrorNotice error={project.error} onRetry={project.refresh} />;
  const p = project.data;
  return (
    <>
      <h1 className="page">{p?.name ?? "Loading…"}</h1>
      <p className="lede">{p?.description || "Add a description so reports start with a clear summary."}</p>
      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} role="tab" className="tab" aria-selected={tab === t.id} onClick={() => (window.location.hash = `#/projects/${id}/${t.id}`)}>{t.label}</button>
        ))}
      </div>
      {tab === "memory" ? <MemoryTab pid={id} /> : tab === "work" ? <WorkTab pid={id} view={view} /> : tab === "reports" ? <ReportsTab pid={id} /> : <MissionsTab pid={id} />}
    </>
  );
}

function MissionsTab({ pid }: { pid: number }) {
  const missions = usePoll(() => api.missions(pid), [pid], (ms) => ms.some((m) => !isTerminal(m.status) && m.status !== "awaiting_approval"), 1000);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true); setError(null);
    try { const m = await api.createMission(pid, text.trim()); window.location.hash = `#/missions/${m.id}`; }
    catch (err) { setError(err instanceof Error ? err.message : "Could not start the mission."); setBusy(false); }
  }

  return (
    <>
      <form className="composer" onSubmit={send}>
        <label htmlFor="req" className="small muted">Ask MissionControl to do something for this project</label>
        <textarea id="req" value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} placeholder="e.g. Create a project handoff report"
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send(e); }} />
        <div className="spread">
          <div className="chips">{EXAMPLES.map((x) => <button type="button" key={x} className="chip" onClick={() => setText(x)}>{x}</button>)}</div>
          <button className="btn btn-primary" disabled={busy || !text.trim()}>{busy ? "Starting…" : "Start mission"}</button>
        </div>
      </form>
      <ErrorNotice error={error} />
      <h2 className="section">Mission history</h2>
      <ErrorNotice error={missions.error} onRetry={missions.refresh} />
      {missions.data?.length ? <div className="strips">{missions.data.map((m) => <MissionStrip key={m.id} m={m} />)}</div>
        : !missions.loading && <Empty>No missions yet. Start one above — try a handoff report.</Empty>}
    </>
  );
}

function MemoryTab({ pid }: { pid: number }) {
  const mem = usePoll(() => api.memories(pid), [pid]);
  const [content, setContent] = useState("");
  const [kind, setKind] = useState("fact");
  const [tentative, setTentative] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");

  async function run(fn: () => Promise<unknown>) {
    setError(null);
    try { await fn(); await mem.refresh(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  function add(e: FormEvent) {
    e.preventDefault();
    const tags = kind === "fact" ? [] : [kind];
    const memory_type = kind === "procedure" ? "procedural" : "semantic";
    run(async () => { await api.createMemory(pid, { content: content.trim(), tags: kind === "procedure" ? [] : tags, memory_type, confirmation: tentative ? "tentative" : "confirmed" } as Partial<Memory>); setContent(""); });
  }

  const rows = (mem.data ?? []).filter((m) => filter === "all" || m.memory_type === filter);
  return (
    <>
      <p className="muted" style={{ marginTop: 0 }}>Everything MissionControl remembers about this project. Each record shows where it came from; correct or delete anything that is wrong.</p>
      <form className="panel" style={{ display: "grid", gap: 12, marginBottom: 18 }} onSubmit={add}>
        <div className="field"><label htmlFor="mem">Remember something</label><textarea id="mem" className="input" value={content} onChange={(e) => setContent(e.target.value)} placeholder="e.g. Backend: Python FastAPI" maxLength={5000} required /></div>
        <div className="row">
          <label className="small">Kind&nbsp;
            <select className="input" style={{ width: "auto", display: "inline-block" }} value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="fact">Fact</option><option value="goal">Goal</option><option value="stack">Technology</option><option value="constraint">Constraint</option><option value="procedure">Procedure</option>
            </select>
          </label>
          <label className="small row" style={{ gap: 6 }}><input type="checkbox" checked={tentative} onChange={(e) => setTentative(e.target.checked)} /> Not confirmed yet</label>
          <button className="btn btn-primary" style={{ marginLeft: "auto" }} disabled={!content.trim()}>Save memory</button>
        </div>
      </form>
      <ErrorNotice error={error || mem.error} />
      <div className="row" style={{ marginBottom: 10 }}>
        {["all", "semantic", "episodic", "procedural"].map((f) => <button key={f} className="chip" aria-pressed={filter === f} style={filter === f ? { borderColor: "var(--ink)" } : undefined} onClick={() => setFilter(f)}>{f === "all" ? "All" : f === "semantic" ? "Project facts" : f === "episodic" ? "Events" : "Procedures"}</button>)}
      </div>
      {rows.length ? (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Memory</th><th>Source</th><th>Updated</th><th><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              {rows.map((m) => (
                <tr key={m.id}>
                  <td>
                    {editing === m.id ? (
                      <div style={{ display: "grid", gap: 6 }}>
                        <textarea className="input" value={draft} onChange={(e) => setDraft(e.target.value)} aria-label="Edit memory" />
                        <div className="row"><button className="btn btn-primary" onClick={() => run(async () => { await api.updateMemory(m.id, { content: draft }); setEditing(null); })}>Save</button><button className="btn" onClick={() => setEditing(null)}>Cancel</button></div>
                      </div>
                    ) : (
                      <>
                        <div className={m.status === "superseded" ? "superseded" : undefined}>{m.content}</div>
                        <div>{m.tags.map((t) => <span key={t} className="tag">{t}</span>)}<span className="tag">{m.memory_type}</span>{m.confirmation === "tentative" && <span className="tag">not confirmed</span>}{m.status === "superseded" && <span className="tag">superseded</span>}</div>
                      </>
                    )}
                  </td>
                  <td className="small">{m.mission_id ? <a href={`#/missions/${m.mission_id}`}>{m.source}</a> : m.source}</td>
                  <td className="small muted">{timeAgo(m.updated_at)}</td>
                  <td className="small" style={{ whiteSpace: "nowrap" }}>
                    {m.confirmation === "tentative" && <button className="btn-link" onClick={() => run(() => api.updateMemory(m.id, { confirmation: "confirmed" }))}>Confirm</button>}
                    <button className="btn-link" onClick={() => { setEditing(m.id); setDraft(m.content); }}>Edit</button>
                    <button className="btn-link btn-danger" onClick={() => { if (confirm("Delete this memory? This cannot be undone.")) run(() => api.deleteMemory(m.id)); }}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : !mem.loading && <Empty>Nothing remembered yet. Add the project’s goals, technology and constraints above.</Empty>}
    </>
  );
}

const STATUS_TEXT: Record<Task["status"], string> = { open: "Open", in_progress: "In progress", blocked: "Blocked", done: "Done" };

function WorkTab({ pid, view }: { pid: number; view?: string }) {
  const tasks = usePoll(() => api.tasks(pid), [pid]);
  const decisions = usePoll(() => api.decisions(pid), [pid]);
  const [title, setTitle] = useState("");
  const [prio, setPrio] = useState<Task["priority"]>("medium");
  const [dTitle, setDTitle] = useState("");
  const [dDesc, setDDesc] = useState("");
  const [supersedes, setSupersedes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const showAll = view !== "unfinished";
  const setView = (v: "unfinished" | "all") => (window.location.hash = `#/projects/${pid}/work${v === "unfinished" ? "/unfinished" : ""}`);
  const allTasks = tasks.data ?? [];
  const unfinished = allTasks.filter((t) => t.status !== "done");
  const shown = showAll ? allTasks : unfinished;

  async function run(fn: () => Promise<unknown>, after: () => Promise<unknown>) {
    setError(null);
    try { await fn(); await after(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  return (
    <div className="grid-2">
      <section>
        <h2 className="section" style={{ marginTop: 0 }}>{showAll ? "Tasks" : `Unfinished tasks (${unfinished.length})`}</h2>
        <div className="row" style={{ marginBottom: 10 }} role="group" aria-label="Which tasks to show">
          <button type="button" className="chip" aria-pressed={!showAll} style={!showAll ? { borderColor: "var(--ink)" } : undefined} onClick={() => setView("unfinished")}>Unfinished ({unfinished.length})</button>
          <button type="button" className="chip" aria-pressed={showAll} style={showAll ? { borderColor: "var(--ink)" } : undefined} onClick={() => setView("all")}>All ({allTasks.length})</button>
        </div>
        <form className="row" style={{ marginBottom: 12 }} onSubmit={(e) => { e.preventDefault(); run(async () => { await api.createTask(pid, { title: title.trim(), priority: prio }); setTitle(""); }, tasks.refresh); }}>
          <input className="input" style={{ flex: "1 1 220px" }} aria-label="Task title" placeholder="New task" value={title} onChange={(e) => setTitle(e.target.value)} required />
          <select className="input" style={{ width: "auto" }} aria-label="Priority" value={prio} onChange={(e) => setPrio(e.target.value as Task["priority"])}><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select>
          <button className="btn btn-primary" disabled={!title.trim()}>Add task</button>
        </form>
        <ErrorNotice error={error || tasks.error} />
        {shown.length ? (
          <div className="table-wrap"><table>
            <thead><tr><th>#</th><th>Task</th><th>Priority</th><th>Status</th></tr></thead>
            <tbody>{shown.map((t) => (
              <tr key={t.id}>
                <td className="num muted">{t.id}</td>
                <td className={t.status === "done" ? "superseded" : undefined}>{t.title}</td>
                <td className={t.priority === "high" ? "prio-high" : undefined}>{t.priority}</td>
                <td><select className="input" style={{ width: "auto", padding: "4px 8px" }} aria-label={`Status of ${t.title}`} value={t.status} onChange={(e) => run(() => api.updateTask(t.id, { status: e.target.value as Task["status"] }), tasks.refresh)}>
                  {Object.entries(STATUS_TEXT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></td>
              </tr>))}</tbody>
          </table></div>
        ) : !tasks.loading && <Empty>{showAll ? "No tasks yet." : "Nothing unfinished — every task is done. 🎉"}</Empty>}
      </section>
      <section>
        <h2 className="section" style={{ marginTop: 0 }}>Decisions</h2>
        <form className="panel" style={{ display: "grid", gap: 10, marginBottom: 12 }} onSubmit={(e) => { e.preventDefault(); run(async () => { await api.createDecision(pid, { title: dTitle.trim(), description: dDesc.trim(), supersedes_decision_id: supersedes ? Number(supersedes) : null }); setDTitle(""); setDDesc(""); setSupersedes(""); }, decisions.refresh); }}>
          <input className="input" aria-label="Decision" placeholder="Decision, e.g. Migrate backend to FastAPI" value={dTitle} onChange={(e) => setDTitle(e.target.value)} required />
          <input className="input" aria-label="Reason" placeholder="Why (optional)" value={dDesc} onChange={(e) => setDDesc(e.target.value)} />
          <div className="row">
            <select className="input" style={{ flex: 1 }} aria-label="Replaces" value={supersedes} onChange={(e) => setSupersedes(e.target.value)}>
              <option value="">Doesn’t replace an earlier decision</option>
              {(decisions.data ?? []).filter((d) => d.status === "confirmed").map((d) => <option key={d.id} value={d.id}>Replaces #{d.id}: {d.title}</option>)}
            </select>
            <button className="btn btn-primary" disabled={!dTitle.trim()}>Record decision</button>
          </div>
        </form>
        <ErrorNotice error={decisions.error} />
        {decisions.data?.length ? (
          <ul className="checks">{decisions.data.map((d) => (
            <li key={d.id}><span className="num muted small">#{d.id}</span><span><span className={d.status === "superseded" ? "superseded" : undefined}><strong>{d.title}</strong>{d.description && ` — ${d.description}`}</span> <span className="tag">{d.status}</span>{d.supersedes_decision_id && <span className="tag">replaces #{d.supersedes_decision_id}</span>}</span></li>
          ))}</ul>
        ) : !decisions.loading && <Empty>No decisions recorded.</Empty>}
      </section>
    </div>
  );
}

function ReportsTab({ pid }: { pid: number }) {
  const reports = usePoll(() => api.reports(pid), [pid]);
  return (
    <>
      <ErrorNotice error={reports.error} onRetry={reports.refresh} />
      {reports.data?.length ? (
        <div className="strips">{reports.data.map((r) => (
          <a key={r.id} className={`strip ${r.verification_status === "passed" ? "good" : r.verification_status === "failed" ? "bad" : ""}`} href={`#/reports/${r.id}`}>
            <span className="strip-edge" aria-hidden />
            <span className="strip-id num">#{r.id}</span>
            <span className="strip-body"><span className="strip-req" style={{ display: "block" }}>{r.title}</span><span className="strip-meta" style={{ display: "block" }}>{r.required_sections.join(", ")} · {timeAgo(r.created_at)}</span></span>
            <span className="strip-state"><Stamp v={r.verification_status} />{!r.verification_status && <span className="small muted">Not verified</span>}</span>
          </a>))}
        </div>
      ) : !reports.loading && <Empty>No reports yet. Ask for a handoff report on the Missions tab.</Empty>}
    </>
  );
}
