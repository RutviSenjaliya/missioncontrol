import type { ReactNode } from "react";
import { parseMarkdown, type Inline } from "../lib/markdown";
import { STATUS_LABEL, statusTone, timeAgo, verificationLabel } from "../lib/status";
import type { Mission, MissionStatus, Verification } from "../lib/types";

export function StatusPill({ status }: { status: MissionStatus }) {
  return <span className={`pill ${statusTone(status)}`}>{STATUS_LABEL[status]}</span>;
}

/** The stamp only says "Verified" when the application's own read-back checks passed. */
export function Stamp({ v }: { v: Verification }) {
  if (v === "passed") return <span className="stamp" title="Checked by the application against persisted data">Verified</span>;
  if (v === "failed") return <span className="stamp bad">Check failed</span>;
  if (v === "not_applicable") return <span className="stamp na">Read-only</span>;
  return null;
}

export function missionVerification(m: Mission): Verification {
  if (m.status === "completed") {
    const readOnly = m.plan?.steps.every((s) => !s.check || s.check.type === "read_only");
    return readOnly ? "not_applicable" : "passed";
  }
  if (m.status === "partially_completed" && (m.error ?? "").includes("verification failed")) return "failed";
  return null;
}

export function MissionStrip({ m, showProject }: { m: Mission; showProject?: boolean }) {
  const tone = statusTone(m.status);
  const meta = [showProject && m.project_name, m.mission_type?.replace(/_/g, " "), timeAgo(m.created_at)].filter(Boolean).join(" · ");
  return (
    <a className={`strip ${tone}`} href={`#/missions/${m.id}`}>
      <span className="strip-edge" aria-hidden />
      <span className="strip-id num" aria-label={`Mission ${m.id}`}>#{m.id}</span>
      <span className="strip-body">
        <span className="strip-req" style={{ display: "block" }}>{m.request}</span>
        <span className="strip-meta" style={{ display: "block" }}>{m.result_summary && m.status !== "completed" && m.error ? m.error : (m.result_summary ?? meta)}</span>
        {m.result_summary && <span className="strip-meta" style={{ display: "block" }}>{meta}</span>}
      </span>
      <span className="strip-state">
        <StatusPill status={m.status} />
        <Stamp v={missionVerification(m)} />
      </span>
    </a>
  );
}

export function ErrorNotice({ error, onRetry }: { error: string | null; onRetry?: () => void }) {
  if (!error) return null;
  return (
    <div className="notice bad" role="alert">
      <div className="spread"><span>{error}</span>{onRetry && <button className="btn" onClick={onRetry}>Try again</button>}</div>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

function InlineText({ parts }: { parts: Inline[] }) {
  return <>{parts.map((p, i) => (p.bold ? <strong key={i}>{p.text}</strong> : p.italic ? <em key={i}>{p.text}</em> : <span key={i}>{p.text}</span>))}</>;
}

export function Markdown({ source }: { source: string }) {
  return (
    <div className="doc">
      {parseMarkdown(source).map((b, i) => {
        switch (b.kind) {
          case "h1": return <h1 key={i}>{b.text}</h1>;
          case "h2": return <h2 key={i}>{b.text}</h2>;
          case "h3": return <h3 key={i}>{b.text}</h3>;
          case "ul": return <ul key={i}>{b.items.map((it, j) => <li key={j}><InlineText parts={it} /></li>)}</ul>;
          case "p": return <p key={i}><InlineText parts={b.parts} /></p>;
        }
      })}
    </div>
  );
}

export { verificationLabel };
