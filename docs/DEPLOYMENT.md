# Deployment (Render blueprint)

1. Push this folder to a GitHub repository.
2. In Render choose New > Blueprint and select the repository; render.yaml creates the API, static site and PostgreSQL.
3. Fill every `sync: false` variable in the dashboard. Set CORS_ORIGINS to the static site URL.
4. Verify `GET /health`, then `GET /api/integrations/status`.
5. In GitHub repository settings add a webhook to `https://<api-host>/webhooks/github`, content type application/json, same secret as GITHUB_WEBHOOK_SECRET.
6. Jenkins is separate from application hosting: run it on a cloud VM or container service, reachable over HTTPS, and set JENKINS_BASE_URL.

Known gaps before production: replace in-memory stores with PostgreSQL repositories, generate Alembic migrations, add authentication. Free instances may sleep; check current Render terms.
