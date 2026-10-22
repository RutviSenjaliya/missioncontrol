import { ErrorNotice, Markdown, Stamp } from "../components/ui";
import { usePoll } from "../hooks/usePoll";
import { api } from "../lib/api";
import { timeAgo } from "../lib/status";

export default function ReportPage({ id }: { id: number }) {
  const { data: r, error, refresh } = usePoll(() => api.report(id), [id]);
  if (error && !r) return <ErrorNotice error={error} onRetry={refresh} />;
  if (!r) return <p className="muted">Loading report…</p>;
  const checks = r.verification_details?.checks ?? [];
  return (
    <>
      <p className="small muted" style={{ margin: "0 0 6px" }}><a href={`#/projects/${r.project_id}/reports`}>Back to reports</a>{r.mission_id && <> · <a href={`#/missions/${r.mission_id}`}>Mission #{r.mission_id}</a></>}</p>
      <div className="spread"><h1 className="page">{r.title}</h1><Stamp v={r.verification_status} /></div>
      <p className="lede">Report #{r.id}, saved {timeAgo(r.created_at)}. Built only from records stored for this project; every task and decision carries its record number.</p>
      <div className="grid-2">
        {r.content ? <Markdown source={r.content} /> : null}
        <aside className="panel evidence">
          <h3>Verification</h3>
          {checks.length ? (
            <ul className="checks">{checks.map((c, i) => <li key={i}><span className={c.passed ? "ok" : "no"}>{c.passed ? "✓" : "✗"}</span><span>{c.check.replace("section:", "Section: ").replace(/_/g, " ")} <span className="muted">— {c.detail}</span></span></li>)}</ul>
          ) : <p className="small muted">This report has not been verified.</p>}
        </aside>
      </div>
    </>
  );
}
