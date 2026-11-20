# Setup in VS Code

## 1. Open and install
1. Open the PACTLINE folder in VS Code and accept the recommended extensions.
2. Backend:
   - `cd backend`
   - `python -m venv .venv` then activate it (Windows PowerShell: `.venv\Scripts\Activate.ps1`)
   - `pip install -r requirements.txt`
   - `copy .env.example .env` (or `cp`) and fill the values
3. Frontend: `cd frontend && npm install && npm start`
4. Run the offline tests any time: `cd backend && python -m unittest discover -s tests -t .`

## 2. Accounts and keys (all required for voice)
| Variable | Where to get it |
|---|---|
| AGORA_APP_ID, AGORA_APP_CERTIFICATE | Agora Console project. Enable Conversational AI and Signaling (RTM) on the project. |
| AGORA_CUSTOMER_ID, AGORA_CUSTOMER_SECRET | Agora Console RESTful API credentials. Used as HTTP Basic auth for the join/leave calls. |
| LLM_API_KEY, LLM_MODEL, LLM_URL | An OpenAI-compatible chat model that supports function calling (Agora custom tools do not work with custom LLM or Dify). |
| MURF_API_KEY, MURF_VOICE_ID | Murf account with Falcon streaming access. Default voice Matthew, locale en-US. |
| JWT_SECRET | 32+ random characters you generate (`python -c "import secrets;print(secrets.token_urlsafe(48))"`). Signs login tokens and per-session tool tokens. |
| DATABASE_URL | Postgres URL in the cloud; locally `sqlite:///pactline.db`. Migrations run automatically at startup. |
| PUBLIC_API_URL | HTTPS URL of the API that Agora's servers can reach. |

## 3. Why the API must be on a public HTTPS URL
Agora's engine, not your browser, calls the tool endpoints (`POST {PUBLIC_API_URL}/tools/<name>`) using a short-lived per-session token that PACTLINE mints when you press Start (no shared secret is stored at Agora). `http://localhost` will not work. Two options:
- Deploy the backend to Render first (see DEPLOYMENT.md) and use that URL. Recommended, and it matches your cloud-only requirement.
- For quick local debugging only, expose port 8000 through a tunnel (for example Cloudflare Tunnel or ngrok) and use its https URL. The tunnel needs your laptop on.

## 4. Run
- Backend: VS Code Run and Debug > "API (uvicorn)". Check http://localhost:8000/health.
- Frontend: http://localhost:4200. Set `window.PACTLINE_API` (or edit `src/app/core/api.ts`) to your API URL, and add the frontend origin to CORS_ORIGINS.
- Open Voice room, allow the microphone, press Start. Use headphones to avoid echo.

## 5. First things to verify after npm install
- `src/app/voice/convo-session.ts` imports `ConversationalAIAPI`, `EConversationalAIAPIEvents`, `ETranscriptHelperMode` from `agora-agent-client-toolkit`. The docs confirm the package name and version (2.9.0) and the class and event names, but I could not read the package's export map. If VS Code underlines this import, open `node_modules/agora-agent-client-toolkit` and adjust the import only.
- The event handler signatures (agent id first, then payload) follow the Web toolkit API page.

## 6. First use
Open the app, register an account (sign-in is required), then Voice room > Start. Writes requested by the agent appear in the Approvals panel; press Approve and the agent can report the real outcome.

## 7. Google Calendar (the external action for the everyday-life workflow)
1. Google Cloud Console: create a project, enable **Google Calendar API**, configure the OAuth consent screen (External, add your own Google account as a **test user**), create an **OAuth client ID** of type *Web application* (or Desktop) and add `http://127.0.0.1:8765` as an authorized redirect URI.
2. Put `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `backend/.env`.
3. One-time authorization on your laptop (development action only, not hosting): `cd backend && python scripts/google_auth.py`. Approve access in the browser; copy the printed `GOOGLE_REFRESH_TOKEN=...` line into `.env`.
4. Optional: `GOOGLE_CALENDAR_ID` (default `primary`), `USER_TIMEZONE` (default `Asia/Kolkata`).
The app uses the scope from Google's Create-events guide (`https://www.googleapis.com/auth/calendar`). While the consent screen is in "Testing" mode Google may expire refresh tokens after 7 days; re-run the script the day before the demo.

## 8. Email reminders (real delivery)
Set `SMTP_HOST`, `SMTP_PORT` (587 STARTTLS or 465 SSL), `SMTP_USER`, `SMTP_PASSWORD`, optional `SMTP_FROM`. For Gmail use an **app password** (requires 2-step verification), host `smtp.gmail.com`. Reminders go to the email of the account that approved them. A background job checks every 30 seconds; the Outcome panel has a "Send due reminders now" button for demos. A reminder shows `sent` only after the mail server accepted it, `failed` with the error otherwise, and stays `pending` if SMTP is not configured.

## 9. Indian voice and language
Pick a voice from the organizers' recommended Indian voices sheet and set `MURF_VOICE_ID` (and `MURF_LOCALE`, e.g. an Indian-English locale if the sheet lists one). I have not verified any voice ID or locale string against Murf, so confirm them in the sheet or Murf's voice list. The agent prompt tells the model to reply in the user's language (English, Hindi or Hinglish); whether speech recognition handles Hindi depends on `ASR_LANGUAGE`, which I have not verified for Agora, so test it.
