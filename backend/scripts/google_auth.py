
import http.server
import os
import secrets
import sys
import threading
import webbrowser
from urllib.parse import parse_qs, urlparse
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.integrations.gcal import auth_url, exchange_code
from app.integrations.http import urllib_transport

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

PORT = 8765
REDIRECT = f"http://127.0.0.1:{PORT}"


def main() -> None:
    client_id = os.environ["GOOGLE_CLIENT_ID"]
    client_secret = os.environ["GOOGLE_CLIENT_SECRET"]

    state = secrets.token_urlsafe(16)
    received = {}
    done = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            query = parse_qs(urlparse(self.path).query)

            received["code"] = query.get("code", [""])[0]
            received["state"] = query.get("state", [""])[0]
            received["error"] = query.get("error", [""])[0]

            print("\nOAuth callback received:")
            print("Code received:", bool(received["code"]))
            print("State received:", bool(received["state"]))
            print("State matches:", received["state"] == state)
            print("Google error:", received["error"] or "None")

            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"PACTLINE: authorization callback received. You can close this tab.")
            done.set()

        def log_message(self, *args):
            return

    server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    url = auth_url(client_id, REDIRECT, state)

    print("Opening Google authorization...")
    webbrowser.open(url)

    if not done.wait(timeout=300):
        server.shutdown()
        sys.exit("Timed out waiting for Google callback.")

    server.shutdown()

    if received.get("error"):
        sys.exit("Google authorization error: " + received["error"])

    if received.get("state") != state:
        sys.exit("OAuth state mismatch. Check the callback output above.")

    if not received.get("code"):
        sys.exit("Google did not return an authorization code.")

    token = exchange_code(
        client_id,
        client_secret,
        received["code"],
        REDIRECT,
        urllib_transport
    )

    print("\nAdd this line to backend/.env (keep it secret):")
    print("GOOGLE_REFRESH_TOKEN=" + token)


if __name__ == "__main__":
    main()
