import { useState, type FormEvent } from "react";
import { api, setToken } from "../lib/api";

export default function Login({ onSignedIn }: { onSignedIn: (u: { id: number; name: string }) => void }) {
  const [token, setTok] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    setToken(token.trim());
    try { onSignedIn(await api.me()); }
    catch (err) { setToken(null); setError(err instanceof Error ? err.message : "Sign-in failed."); }
    finally { setBusy(false); }
  }

  return (
    <div className="login">
      <form className="panel" onSubmit={submit}>
        <div className="brand"><span className="brand-mark" aria-hidden />MissionControl</div>
        <p className="muted" style={{ margin: 0 }}>Your projects, remembered. Work done through real tools, and checked before it’s called done.</p>
        <div className="field">
          <label htmlFor="token">API token</label>
          <input id="token" className="input" type="password" autoComplete="off" value={token} onChange={(e) => setTok(e.target.value)} required />
          <span className="small muted">Use DEMO_USER_TOKEN from your .env, or a token from <code className="code">python -m app.cli create-user</code>.</span>
        </div>
        {error && <div className="notice bad" role="alert">{error}</div>}
        <button className="btn btn-primary" disabled={busy || !token.trim()}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
    </div>
  );
}
