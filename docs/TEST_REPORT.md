# Test report

Environment: build sandbox (Python 3.12, SQLite 3.45, no network, no FastAPI/Angular/psycopg installed).

## Executed
| ID | What | Command | Result |
|---|---|---|---|
| U1 | Unit tests (security, storage, accounts, tools, commitments, workflow, webhooks, pipeline, integrations, Agora payload, service, Google Calendar client, mailer, reminders, calendar tools) | `cd backend && python3 -m unittest discover -s tests -t .` | 340 passed |
| U2 | Persistence across reopen (file-backed SQLite) | included in U1 | passed |
| U3 | Byte-compile of FastAPI app | `python3 -m py_compile app/api/main.py` | passed |

All of the above are unit/mocked tests. None is a live provider test.

## Not executed (reason)
| ID | Test | Reason |
|---|---|---|
| A | Start FastAPI, /health | fastapi not installable here |
| B | Angular production build | npm install unavailable here |
| C | Browser to deployed backend | no deployment |
| D-H | Agora token, agent start/stop, mic, transcripts, Murf audio | needs credentials, network, browser |
| I-J | Spoken task saved in PostgreSQL, restart | Postgres driver path (psycopg) never run; SQLite path is tested |
| K | Google Calendar event | client and tools unit-tested against fakes; never run against Google |
| L | Shopping list by voice | tool exists, never run by voice |
| M | Reminder delivery | scheduler and SMTP mailer unit-tested against fakes; never sent a real email |
| N-Q | Jenkins/Sonar by voice | voice tools not exposed; clients tested against fakes only |
| R | GitHub webhook live | route written, not run |
| S | Integration-outage handling | not run live |
