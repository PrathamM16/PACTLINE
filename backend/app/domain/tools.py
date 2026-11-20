import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domain.commitments import CommitmentLedger
from app.errors import IntegrationUnavailable, ProviderError
from app.storage import Store, now_iso

DATE_FIELDS = ("due_date", "deadline", "claimed_deadline", "agreed_deadline", "date_from", "date_to")
DATETIME_FIELDS = ("remind_at", "start", "end")
WRITE_ROLES = ("owner", "member")
SUMMARY_LIMIT = 300


@dataclass(frozen=True)
class ToolContext:
    workspace_id: str
    user_id: str
    role: str = "member"
    email: str = ""


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict
    handler: Callable
    writes: bool
    precheck: Callable | None = None


def _param(kind: str, description: str) -> dict:
    return {"type": kind, "description": description}


def _schema(**params) -> dict:
    return {"type": "object", "properties": params, "required": list(params), "additionalProperties": False}


OPTIONAL_NOTE = " Use an empty string if not mentioned."
JSON_TYPES = {"string": str, "boolean": bool, "integer": int}


def _blank(value):
    return None if value in (None, "") else value


def _parse_date(value, field_name):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be an ISO date YYYY-MM-DD")


class ToolRegistry:
    def __init__(self, store: Store, today: Callable[[], date] = date.today, calendar=None, timezone: str = "Asia/Kolkata", mail_configured: bool = False):
        self.store = store
        self.ledger = CommitmentLedger(store)
        self._today = today
        self._calendar = calendar
        self._tz = timezone
        self._mail_configured = mail_configured
        self._tools: dict[str, ToolDefinition] = {}
        self._register_all()

    def definitions(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def _add(self, name, description, parameters, handler, writes, precheck=None):
        self._tools[name.lower()] = ToolDefinition(name, description, parameters, handler, writes, precheck)

    def _check_args(self, tool: ToolDefinition, args: dict) -> dict | None:
        missing = [p for p in tool.parameters["required"] if p not in args]
        if missing:
            return {"ok": False, "error": "missing_arguments", "missing": missing}
        for name, spec in tool.parameters["properties"].items():
            if not isinstance(args[name], JSON_TYPES[spec["type"]]):
                return {"ok": False, "error": "invalid_request", "message": f"{name} must be a {spec['type']}"}
            if len(str(args[name])) > 1000:
                return {"ok": False, "error": "invalid_request", "message": f"{name} is too long"}
        try:
            for name in DATE_FIELDS:
                if name in args and _blank(args[name]):
                    _parse_date(args[name], name)
            for name in DATETIME_FIELDS:
                if name in args:
                    datetime.fromisoformat(args[name])
        except ValueError as exc:
            return {"ok": False, "error": "invalid_request", "message": str(exc)}
        return None

    def call(self, name: str, ctx: ToolContext, args: dict, tool_call_id: str = "") -> dict:
        tool = self._tools.get(name.lower())
        if tool is None:
            return {"ok": False, "error": "unknown_tool"}
        if tool_call_id:
            cached = self.store.get_tool_result(ctx.workspace_id, tool_call_id)
            if cached is not None:
                return cached
        problem = self._check_args(tool, args)
        if problem:
            self.store.audit(ctx.workspace_id, ctx.user_id, tool.name, "-", "rejected", problem.get("message", problem["error"]))
            return problem
        if tool.writes and ctx.role not in WRITE_ROLES:
            self.store.audit(ctx.workspace_id, ctx.user_id, tool.name, "-", "forbidden")
            return {"ok": False, "error": "forbidden", "message": "This role cannot make changes."}
        if tool.writes:
            early = self._precheck(tool, ctx, args)
            result = early if early is not None else self._request_approval(tool, ctx, args)
        else:
            result = self._run(tool, ctx, args)
        if tool_call_id and result.get("ok"):
            self.store.save_tool_result(ctx.workspace_id, tool_call_id, result)
        return result

    def _failure(self, tool: ToolDefinition, ctx: ToolContext, exc: Exception) -> dict:
        kind = "integration_unavailable" if isinstance(exc, IntegrationUnavailable) else "provider_error"
        self.store.audit(ctx.workspace_id, ctx.user_id, tool.name, "-", kind, str(exc))
        return {"ok": False, "error": kind, "message": str(exc)}

    def _precheck(self, tool: ToolDefinition, ctx: ToolContext, args: dict) -> dict | None:
        if tool.precheck is None:
            return None
        try:
            return tool.precheck(ctx, args)
        except (IntegrationUnavailable, ProviderError) as exc:
            return self._failure(tool, ctx, exc)
        except ValueError as exc:
            return {"ok": False, "error": "invalid_request", "message": str(exc)}

    def _run(self, tool: ToolDefinition, ctx: ToolContext, args: dict) -> dict:
        try:
            data = tool.handler(ctx, args)
        except (IntegrationUnavailable, ProviderError) as exc:
            return self._failure(tool, ctx, exc)
        except KeyError:
            self.store.audit(ctx.workspace_id, ctx.user_id, tool.name, "-", "not_found")
            return {"ok": False, "error": "not_found"}
        except (ValueError, PermissionError) as exc:
            self.store.audit(ctx.workspace_id, ctx.user_id, tool.name, "-", "failed", str(exc))
            return {"ok": False, "error": "invalid_request", "message": str(exc)}
        self.store.audit(ctx.workspace_id, ctx.user_id, tool.name, "-", "succeeded")
        return {"ok": True, "data": data}

    def _request_approval(self, tool: ToolDefinition, ctx: ToolContext, args: dict) -> dict:
        shown = ", ".join(f"{k}={v}" for k, v in args.items() if _blank(v))[:SUMMARY_LIMIT]
        record = {"id": str(uuid4()), "tool": tool.name, "args": dict(args), "status": "pending", "requested_by": ctx.user_id, "summary": f"{tool.name}: {shown}", "result": None, "created_at": now_iso()}
        self.store.put("approval", ctx.workspace_id, record["id"], record)
        self.store.audit(ctx.workspace_id, ctx.user_id, tool.name, record["id"], "approval_requested")
        return {"ok": True, "status": "awaiting_user_approval", "approval_id": record["id"], "message": "Nothing has been changed yet. Tell the user what you intend to do and ask them to press Approve in the app, then check getApprovalStatus."}

    def pending_approvals(self, ctx: ToolContext) -> list[dict]:
        return [a for a in self.store.list_records("approval", ctx.workspace_id) if a["status"] == "pending"]

    def decide(self, ctx: ToolContext, approval_id: str, approve: bool) -> dict:
        record = self.store.get("approval", ctx.workspace_id, approval_id)
        if record is None:
            raise KeyError(approval_id)
        if ctx.role not in WRITE_ROLES or (ctx.user_id != record["requested_by"] and ctx.role != "owner"):
            self.store.audit(ctx.workspace_id, ctx.user_id, "decide", approval_id, "forbidden")
            raise PermissionError("not allowed to decide this approval")
        if record["status"] != "pending" or not self.store.once(f"approval:{approval_id}"):
            raise ValueError("approval already decided")
        if not approve:
            record["status"] = "rejected"
        else:
            outcome = self._run(self._tools[record["tool"].lower()], ctx, {**record["args"], "_approval_id": approval_id})
            record["status"] = "executed" if outcome["ok"] else "failed"
            record["result"] = outcome
        record["decided_by"] = ctx.user_id
        self.store.put("approval", ctx.workspace_id, approval_id, record)
        self.store.audit(ctx.workspace_id, ctx.user_id, "decide", approval_id, record["status"])
        return record

    def _register_all(self):
        self._add("createTask", "Request creating a task. Needs the user to approve in the app.", _schema(title=_param("string", "Task title."), assignee=_param("string", "Person responsible." + OPTIONAL_NOTE), due_date=_param("string", "ISO date YYYY-MM-DD." + OPTIONAL_NOTE)), self._create_task, True)
        self._add("assignTask", "Request assigning a task to a person. Needs approval.", _schema(task_id=_param("string", "Task id."), assignee=_param("string", "Person responsible.")), self._assign_task, True)
        self._add("completeTask", "Request marking a task completed. Needs approval.", _schema(task_id=_param("string", "Task id.")), self._complete_task, True)
        self._add("listTasks", "List tasks, optionally for one assignee.", _schema(assignee=_param("string", "Filter by person." + OPTIONAL_NOTE)), self._list_tasks, False)
        self._add("createCommitment", "Request recording a commitment someone made. Needs approval.", _schema(owner=_param("string", "Who promised."), description=_param("string", "What was promised."), deadline=_param("string", "ISO date YYYY-MM-DD." + OPTIONAL_NOTE), evidence=_param("string", "The user's words that support this.")), self._create_commitment, True)
        self._add("raiseDeadlineDisagreement", "Record that someone disputes a commitment's deadline. Never pick a date yourself.", _schema(commitment_id=_param("string", "Commitment id."), actor=_param("string", "Who disagrees."), claimed_deadline=_param("string", "ISO date YYYY-MM-DD they claim.")), self._dispute, False)
        self._add("resolveDeadline", "Request setting the agreed deadline after people clearly agreed. Needs approval.", _schema(commitment_id=_param("string", "Commitment id."), actor=_param("string", "Who confirmed."), agreed_deadline=_param("string", "ISO date YYYY-MM-DD.")), self._resolve, True)
        self._add("listCommitments", "List pending commitments.", _schema(owner=_param("string", "Filter by person." + OPTIONAL_NOTE)), self._list_commitments, False)
        self._add("createShoppingList", "Request creating a shopping list. Needs approval.", _schema(name=_param("string", "List name.")), self._create_list, True)
        self._add("addShoppingItem", "Request adding an item to a shopping list. Needs approval.", _schema(list_id=_param("string", "List id."), item=_param("string", "Item name."), quantity=_param("string", "Quantity." + OPTIONAL_NOTE), assignee=_param("string", "Person who will buy it." + OPTIONAL_NOTE)), self._add_item, True)
        self._add("getShoppingList", "Show the contents of one shopping list.", _schema(list_id=_param("string", "List id.")), self._get_list, False)
        self._add("createReminder", "Request scheduling an email reminder to the account owner. Needs approval; delivery happens later and is reported by getDailyBriefing.", _schema(text=_param("string", "Reminder text."), remind_at=_param("string", "ISO datetime."), for_person=_param("string", "Who to remind." + OPTIONAL_NOTE)), self._create_reminder, True)
        self._add("savePreference", "Request remembering a stable user preference. Needs approval.", _schema(key=_param("string", "Short preference name."), value=_param("string", "Preference value.")), self._save_preference, True)
        self._add("listCalendarEvents", "List real Google Calendar events between two dates (inclusive).", _schema(date_from=_param("string", "ISO date YYYY-MM-DD."), date_to=_param("string", "ISO date YYYY-MM-DD.")), self._list_calendar_events, False)
        self._add("createCalendarEvent", "Request adding an event to Google Calendar. Checks for clashes first. Needs approval.", _schema(title=_param("string", "Event title."), start=_param("string", "ISO datetime, local time."), end=_param("string", "ISO datetime, local time."), description=_param("string", "Notes." + OPTIONAL_NOTE), ignore_conflicts=_param("boolean", "True only if the user already said to book despite a clash.")), self._create_event, True, self._calendar_precheck)
        self._add("listRepositories", "List your GitHub repositories.", _schema(unused=_param("string", "Always pass an empty string.")), self._list_repos, False)
        self._add("generatePipeline", "Generate a CI/CD pipeline for a GitHub repository. Needs approval.", _schema(owner=_param("string", "Repository owner."), repo=_param("string", "Repository name."), branch=_param("string", "Branch name, e.g., develop."), job_name=_param("string", "Jenkins job name."), node_version=_param("string", "Node version, e.g., 20."), sonar_key=_param("string", "SonarQube project key." + OPTIONAL_NOTE)), self._generate_pipeline, True)
        self._add("createPipelinePullRequest", "Create a pull request with the generated Jenkinsfile. Needs approval.", _schema(owner=_param("string", "Repository owner."), repo=_param("string", "Repository name."), branch=_param("string", "Branch name for the PR."), jenkinsfile=_param("string", "The Jenkinsfile content."), title=_param("string", "PR title.")), self._create_pr, True)
        self._add("analyzeSonarQube", "Analyze code quality and security using SonarQube. Returns pass/fail status and recommendations.", _schema(project_key=_param("string", "SonarQube project key (e.g., owner_project).")), self._analyze_sonar, False)
        self._add("getApprovalStatus", "Check whether a requested action was approved and what actually happened.", _schema(approval_id=_param("string", "Approval id returned earlier.")), self._approval_status, False)
        self._add("getDailyBriefing", "Get stored preferences, pending tasks, commitments, disagreements, reminders and pending approvals.", _schema(unused=_param("string", "Always pass an empty string.")), self._briefing, False)

    def _create_task(self, ctx, a):
        due = _parse_date(a["due_date"], "due_date") if _blank(a["due_date"]) else None
        task = {"id": str(uuid4()), "title": a["title"], "assignee": _blank(a["assignee"]), "due_date": due.isoformat() if due else None, "status": "pending", "created_by": ctx.user_id}
        self.store.put("task", ctx.workspace_id, task["id"], task)
        return task

    def _task(self, ctx, task_id):
        task = self.store.get("task", ctx.workspace_id, task_id)
        if task is None:
            raise KeyError(task_id)
        return task

    def _assign_task(self, ctx, a):
        task = self._task(ctx, a["task_id"])
        task["assignee"] = a["assignee"]
        self.store.put("task", ctx.workspace_id, task["id"], task)
        return task

    def _complete_task(self, ctx, a):
        task = self._task(ctx, a["task_id"])
        task["status"] = "completed"
        self.store.put("task", ctx.workspace_id, task["id"], task)
        return task

    def _list_tasks(self, ctx, a):
        who = _blank(a["assignee"])
        return [t for t in self.store.list_records("task", ctx.workspace_id) if who is None or t["assignee"] == who]

    def _commitment_view(self, c):
        return {"id": c.id, "owner": c.owner, "description": c.description, "deadline": c.deadline.isoformat() if c.deadline else None, "confirmation": c.confirmation.value, "status": c.status.value, "disputed_deadlines": {k: v.isoformat() for k, v in c.disputed_deadlines.items()}}

    def _create_commitment(self, ctx, a):
        deadline = _parse_date(a["deadline"], "deadline") if _blank(a["deadline"]) else None
        return self._commitment_view(self.ledger.propose(a["owner"], a["description"], deadline, "voice", ctx.workspace_id, a["evidence"], ctx.user_id))

    def _dispute(self, ctx, a):
        return self._commitment_view(self.ledger.dispute(a["commitment_id"], ctx.workspace_id, a["actor"], _parse_date(a["claimed_deadline"], "claimed_deadline")))

    def _resolve(self, ctx, a):
        return self._commitment_view(self.ledger.resolve(a["commitment_id"], ctx.workspace_id, a["actor"], _parse_date(a["agreed_deadline"], "agreed_deadline")))

    def _list_commitments(self, ctx, a):
        return [self._commitment_view(c) for c in self.ledger.pending(ctx.workspace_id, _blank(a["owner"]))]

    def _create_list(self, ctx, a):
        shopping = {"id": str(uuid4()), "name": a["name"], "items": []}
        self.store.put("shopping_list", ctx.workspace_id, shopping["id"], shopping)
        return shopping

    def _shopping(self, ctx, list_id):
        shopping = self.store.get("shopping_list", ctx.workspace_id, list_id)
        if shopping is None:
            raise KeyError(list_id)
        return shopping

    def _add_item(self, ctx, a):
        shopping = self._shopping(ctx, a["list_id"])
        shopping["items"].append({"item": a["item"], "quantity": _blank(a["quantity"]), "assignee": _blank(a["assignee"]), "done": False})
        self.store.put("shopping_list", ctx.workspace_id, shopping["id"], shopping)
        return shopping

    def _get_list(self, ctx, a):
        return self._shopping(ctx, a["list_id"])

    def _aware(self, value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=ZoneInfo(self._tz))

    def _need_calendar(self):
        if self._calendar is None:
            raise IntegrationUnavailable("Google Calendar is not connected")
        return self._calendar

    def _list_calendar_events(self, ctx, a):
        first = _parse_date(a["date_from"], "date_from")
        last = _parse_date(a["date_to"], "date_to")
        window_start = datetime.combine(first, datetime.min.time())
        window_end = datetime.combine(last + timedelta(days=1), datetime.min.time())
        return self._need_calendar().list_events(window_start, window_end)

    def _calendar_precheck(self, ctx, a):
        calendar = self._need_calendar()
        start, end = self._aware(a["start"]), self._aware(a["end"])
        if end <= start:
            raise ValueError("end must be after start")
        if a["ignore_conflicts"]:
            return None
        clashes = [e for e in calendar.list_events(start, end) if not e["all_day"]]
        if not clashes:
            return None
        return {"ok": True, "status": "conflict", "conflicts": [{"summary": e["summary"], "start": e["start"], "end": e["end"]} for e in clashes], "message": "Nothing was booked. Tell the user about the clash and ask whether to book anyway or pick another time."}

    def _create_event(self, ctx, a):
        calendar = self._need_calendar()
        start, end = self._aware(a["start"]), self._aware(a["end"])
        if end <= start:
            raise ValueError("end must be after start")
        event_id = hashlib.sha1(a.get("_approval_id", str(uuid4())).encode()).hexdigest()
        return calendar.create_event(event_id, a["title"], start, end, _blank(a["description"]) or "")

    def _create_reminder(self, ctx, a):
        reminder = {"id": str(uuid4()), "text": a["text"], "remind_at": datetime.fromisoformat(a["remind_at"]).isoformat(), "for_person": _blank(a["for_person"]), "recipient_email": _blank(ctx.email), "delivery": "pending", "attempts": 0, "delivery_configured": self._mail_configured}
        self.store.put("reminder", ctx.workspace_id, reminder["id"], reminder)
        return reminder

    def _save_preference(self, ctx, a):
        self.store.put("preference", ctx.workspace_id, f"{ctx.workspace_id}:{a['key']}", {"key": a["key"], "value": a["value"]})
        return {a["key"]: a["value"]}

    def _approval_status(self, ctx, a):
        record = self.store.get("approval", ctx.workspace_id, a["approval_id"])
        if record is None:
            raise KeyError(a["approval_id"])
        return {"status": record["status"], "result": record["result"]}

    def _calendar_today(self):
        if self._calendar is None:
            return {"connected": False}
        today = datetime.combine(self._today(), datetime.min.time())
        try:
            return {"connected": True, "events": self._calendar.list_events(today, today + timedelta(days=2))}
        except ProviderError as exc:
            return {"connected": True, "error": str(exc)}

    def _follow_ups(self, ctx, today):
        tasks = [t for t in self.store.list_records("task", ctx.workspace_id) if t["status"] == "pending"]
        reminders = self.store.list_records("reminder", ctx.workspace_id)
        brief = lambda r: {"id": r["id"], "text": r["text"], "remind_at": r["remind_at"], "error": r.get("error")}
        return {
            "overdue_tasks": [t for t in tasks if t["due_date"] and t["due_date"] < today.isoformat()],
            "unassigned_tasks": [t for t in tasks if not t["assignee"]],
            "reminders_sent": [brief(r) for r in reminders if r["delivery"] == "sent"],
            "reminders_failed": [brief(r) for r in reminders if r["delivery"] == "failed"],
            "reminders_waiting": [brief(r) for r in reminders if r["delivery"] == "pending"],
        }

    def _list_repos(self, ctx, a):
        from app.integrations.github import GitHubClient
        from app.integrations.http import urllib_transport
        
        client = GitHubClient.from_env(__import__("os").environ, urllib_transport)
        if not client:
            raise IntegrationUnavailable("GitHub is not configured")
        repos = client.list_user_repos()
        return {"repos": repos}

    def _generate_pipeline(self, ctx, a):
        from app.devops.pipeline import PipelineSpec, generate_jenkinsfile, validate_spec
        
        spec = PipelineSpec(
            job_name=a["job_name"],
            repository=f"{a['owner']}/{a['repo']}",
            branch=a["branch"],
            app_type="angular",
            node_version=a["node_version"],
            stages=("install", "lint", "unit_tests", "sonar_analysis", "quality_gate", "build"),
            sonar_project_key=_blank(a["sonar_key"]),
        )
        errors = validate_spec(spec)
        if errors:
            raise ValueError("; ".join(errors))
        content = generate_jenkinsfile(spec)
        return {"ok": True, "jenkinsfile": content, "job_name": a["job_name"], "repo": a["repo"]}

    def _create_pr(self, ctx, a):
        from app.integrations.github import GitHubClient
        from app.integrations.http import urllib_transport
        
        client = GitHubClient.from_env(__import__("os").environ, urllib_transport)
        if not client:
            raise IntegrationUnavailable("GitHub is not configured")
        
        # Create branch
        default_branch = client.get_default_branch_sha(a["owner"], a["repo"])
        client.create_branch(a["owner"], a["repo"], a["branch"], default_branch)
        
        # Commit Jenkinsfile
        client.create_or_update_file(
            a["owner"], a["repo"], "Jenkinsfile", a["jenkinsfile"].encode(), a["branch"],
            "Add CI/CD pipeline [pactline]"
        )
        
        # Create PR
        pr = client.create_pull_request(
            a["owner"], a["repo"], a["title"], a["branch"],
            a.get("base_branch") or "main",
            "Generated by PACTLINE"
        )
        return {"ok": True, "pr_url": pr.get("html_url"), "pr_number": pr.get("number")}

    def _analyze_sonar(self, ctx, a):
        from app.integrations.sonarqube import SonarQubeClient
        from app.integrations.http import urllib_transport
        
        client = SonarQubeClient.from_env(__import__("os").environ, urllib_transport)
        if not client:
            raise IntegrationUnavailable("SonarQube is not configured")
        
        project_key = a["project_key"]
        summary = client.get_quality_summary(project_key)
        
        return {
            "project_key": project_key,
            "quality_gate_passed": summary.get("quality_gate_passed", False),
            "quality_gate_status": summary.get("quality_gate_status"),
            "coverage": summary.get("coverage", 0),
            "bugs": summary.get("bugs", 0),
            "vulnerabilities": summary.get("vulnerabilities", 0),
            "code_smells": summary.get("code_smells", 0),
            "open_issues": summary.get("open_issues", 0),
            "recommendation": summary.get("recommendation", ""),
            "failed_conditions": summary.get("failed_conditions", []),
        }

    def _briefing(self, ctx, a):
        today = self._today()
        preferences = {p["key"]: p["value"] for p in self.store.list_records("preference", ctx.workspace_id)}
        return {
            "date": today.isoformat(),
            "preferences": preferences,
            "calendar": self._calendar_today(),
            "pending_tasks": [t for t in self.store.list_records("task", ctx.workspace_id) if t["status"] == "pending"],
            "pending_commitments": [self._commitment_view(c) for c in self.ledger.pending(ctx.workspace_id)],
            "overdue_commitments": [self._commitment_view(c) for c in self.ledger.overdue(ctx.workspace_id, today)],
            "deadline_disagreements": [self._commitment_view(c) for c in self.ledger.conflicts(ctx.workspace_id)],
            "shopping_lists": self.store.list_records("shopping_list", ctx.workspace_id),
            "reminders": self.store.list_records("reminder", ctx.workspace_id),
            "reminder_delivery_configured": self._mail_configured,
            "follow_ups": self._follow_ups(ctx, today),
            "pending_approvals": [{"id": p["id"], "summary": p["summary"]} for p in self.pending_approvals(ctx)],
        }
