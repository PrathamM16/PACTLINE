# Security notes

Secrets live in environment variables only. Webhooks require a valid HMAC SHA-256 signature and a unique delivery id. Jenkins actions require allowlisted repository and job plus a matching explicit approval. Generated Jenkinsfiles are checked against a command allowlist and forbidden tokens. Not yet implemented: authentication, RBAC, rate limiting.
