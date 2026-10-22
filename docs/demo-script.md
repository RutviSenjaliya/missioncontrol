# Demo script (target 2:45, hard limit 3:00)

Setup before recording: run `./scripts/setup.sh` on a clean database, start the three services, run `python scripts/smoke_test.py` once to confirm 17/17, then reset the database and seed again (`alembic downgrade base && alembic upgrade head && python -m app.cli seed --demo`) so the demo starts clean. Keep a terminal tailing the MCP server log next to the browser.

| # | Time | Scene | Do | Say (English) | Proof on screen |
|---|---|---|---|---|---|
| 0 | 0:00–0:12 | Hook | Show dashboard | “Every time our team opened an AI chat, we re-explained the project. And when it said ‘done’, we had to check it ourselves.” | — |
| 1 | 0:12–0:30 | Establish context | Open *Campus Events App* → Memory tab; add “Must work offline for check-in” as a constraint | “MissionControl stores goals, stack, constraints and decisions as structured memory, with a source for each record.” | New row with source *user*; superseded Flask decision struck through on Tasks & decisions |
| 2 | 0:30–0:55 | Fresh session | Sign out, sign in, Missions tab → “Create a sprint plan from our goals, decisions and unfinished tasks” | “New session, nothing pasted in. Context comes from the database.” | Timeline: *context retrieved* event with ids; report shows the new constraint and FastAPI, not Flask |
| 3 | 0:55–1:17 | Execute a mission | “Create a project handoff report” | “The agent plans two steps and sets success conditions before it runs anything.” | Plan panel; status moves Planning → Running → Verifying |
| 4 | 1:17–1:42 | Prove MCP | Point at the *MCP connection* panel and the terminal log | “Every action is a real MCP call over Streamable HTTP to our self-hosted server. Here are the calls arriving.” | Protocol 2025-11-25, 8 tools; server log lines `tool=generate_project_report … outcome=ok` |
| 5 | 1:42–2:04 | Verify | Open the report; show checks | “It doesn’t trust its own words. It reads the saved report back, checks every section and that every referenced task and decision exists.” | 10/10 checks, *Verified* stamp |
| 6 | 2:04–2:22 | Approval + continuity | “Add task: Record the demo video (high priority)” → Approve | “Changes to project records wait for approval, enforced by the server. Then the change is read back.” | *Needs your approval* → Completed, verified; then “Summarize our progress” lists previous missions |
| 7 | 2:22–2:40 | Honest failure | Stop the MCP server (Ctrl+C), ask for a handoff report | “When something breaks, it says so.” | Red *Failed*: “MCP server unavailable…”; no report, no green |
| 8 | 2:40–2:48 | Close | Dashboard | “MissionControl: it remembers, it does the work, and it proves it.” | Repo URL on screen |

Tips: record at 1440×900, browser zoom 110%, hide bookmarks. Restart the MCP server after scene 7 if you record more takes.
