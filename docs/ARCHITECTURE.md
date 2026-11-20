# Architecture

Modular monolith. Domain logic in `app/domain` and `app/devops` has no framework dependencies and is unit tested.

Flow for a voice DevOps request: Agora RTC and Conversational AI -> LLM requests a typed tool -> backend validates the spec -> Jenkinsfile generated from fixed templates only -> validator enforces a command allowlist -> ApprovalGate records an explicit decision bound to tool and resource -> DevopsTools calls Jenkins only with a matching approval and reports "confirmed" only after Jenkins returns the job -> Sonar quality gate read from the Sonar API -> audit event written.

The LLM never receives credentials and never supplies shell commands; stages map to fixed commands.
