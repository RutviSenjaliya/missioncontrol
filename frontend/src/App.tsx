import { useEffect, useState } from "react";
import { api, getToken, setToken } from "./lib/api";
import type { Project } from "./lib/types";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import MissionPage from "./pages/MissionPage";
import ProjectPage from "./pages/ProjectPage";
import ReportPage from "./pages/ReportPage";
import SettingsPage from "./pages/SettingsPage";

function useHash() {
  const [hash, setHash] = useState(() => window.location.hash.slice(1) || "/");
  useEffect(() => {
    const on = () => { setHash(window.location.hash.slice(1) || "/"); window.scrollTo(0, 0); };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return hash;
}

export default function App() {
  const [user, setUser] = useState<{ id: number; name: string } | null>(null);
  const [checked, setChecked] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const route = useHash();

  useEffect(() => {
    if (!getToken()) { setChecked(true); return; }
    api.me().then(setUser).catch(() => setToken(null)).finally(() => setChecked(true));
  }, []);

  useEffect(() => {
    if (user) api.dashboard().then((d) => setProjects(d.projects)).catch(() => undefined);
  }, [user, route]);

  if (!checked) return null;
  if (!user) return <Login onSignedIn={setUser} />;

  const seg = route.split("/").filter(Boolean);
  let page;
  if (seg[0] === "projects" && seg[1]) page = <ProjectPage id={Number(seg[1])} tab={seg[2] ?? "missions"} view={seg[3]} />;
  else if (seg[0] === "missions" && seg[1]) page = <MissionPage id={Number(seg[1])} />;
  else if (seg[0] === "reports" && seg[1]) page = <ReportPage id={Number(seg[1])} />;
  else if (seg[0] === "settings") page = <SettingsPage />;
  else page = <Dashboard />;

  const current = (href: string) => (`#${route}` === href || (href !== "#/" && `#${route}`.startsWith(href + "/")) ? "page" : undefined);

  return (
    <div className="shell">
      <nav className="rail" aria-label="Main">
        <a className="brand" href="#/"><span className="brand-mark" aria-hidden />MissionControl</a>
        <div className="rail-group">
          <h2>Workspace</h2>
          <a href="#/" aria-current={current("#/")}>Dashboard</a>
          <a href="#/settings" aria-current={current("#/settings")}>Connections</a>
        </div>
        <div className="rail-group">
          <h2>Projects</h2>
          {projects.map((p) => (
            <a key={p.id} href={`#/projects/${p.id}`} aria-current={current(`#/projects/${p.id}`)}>{p.name}</a>
          ))}
        </div>
        <div className="rail-foot">
          <span>Signed in as {user.name}</span>
          <button className="btn-link" style={{ justifySelf: "start", padding: 0 }} onClick={() => { setToken(null); setUser(null); }}>Sign out</button>
        </div>
      </nav>
      <main className="main">{page}</main>
    </div>
  );
}
