from __future__ import annotations

import asyncio
import contextlib
import io
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pypdf import PdfReader
from starlette.middleware.sessions import SessionMiddleware

from .config import ROOT_DIR, TEAMS, settings
from .database import control_db
from .intents import contextualize_retrieval_query, is_greeting
from .knowledge import knowledge
from .orchestrator import SUPPORTED_LANGUAGES, Route, build_execution_plan, orchestrator
from .service_control import SERVICE_ACTIONS, service_controller, validate_service_request

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie=settings.session_cookie_name,
    same_site="lax",
    https_only=settings.cookie_secure,
    max_age=8 * 60 * 60,
)
app.mount("/assets", StaticFiles(directory=ROOT_DIR / "app" / "static"), name="assets")


class DemoLoginRequest(BaseModel):
    email: str
    display_name: str = Field(min_length=1, max_length=100)


class OnboardingRequest(BaseModel):
    requested_team: str
    preferred_language: str = Field(min_length=1, max_length=50)
    role_title: str = Field(min_length=1, max_length=120)
    responsibilities: str = Field(default="", max_length=3000)
    recurring_tasks: str = Field(default="", max_length=3000)
    tools_used: str = Field(default="", max_length=2000)
    automation_goals: str = Field(default="", max_length=3000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    conversation_id: str | None = None
    language: str | None = None


class LanguagePreferenceRequest(BaseModel):
    language: str


class ProfileUpdateRequest(BaseModel):
    role_title: str = Field(min_length=1, max_length=120)
    responsibilities: str = Field(default="", max_length=3000)
    recurring_tasks: str = Field(default="", max_length=3000)
    tools_used: str = Field(default="", max_length=2000)
    automation_goals: str = Field(default="", max_length=3000)


class ConversationTitleRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class FeedbackRequest(BaseModel):
    rating: str = Field(pattern="^(helpful|not_helpful)$")
    comment: str = Field(default="", max_length=1000)


class ApprovalRequest(BaseModel):
    team: str


class ActionRequest(BaseModel):
    action_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class SystemControlRequest(BaseModel):
    admin_key: str = Field(min_length=1, max_length=256)
    confirmation: str = Field(min_length=1, max_length=80)


@app.on_event("startup")
def startup() -> None:
    control_db.initialize()
    knowledge.initialize()


def require_user(request: Request) -> dict[str, Any]:
    email = request.session.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Sign in required")
    user = control_db.get_user(email)
    if not user:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Session is no longer valid")
    return user


def require_owner(request: Request) -> dict[str, Any]:
    user = require_user(request)
    if user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")
    return user


def accessible_teams(user: dict[str, Any]) -> list[str]:
    if user["role"] == "owner":
        return list(TEAMS)
    teams = ["public"]
    if user["approved"] and user["assigned_team"] in TEAMS:
        teams.append(user["assigned_team"])
    return list(dict.fromkeys(teams))


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in user.items() if key != "profile"} | {
        "profile": user.get("profile", {})
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT_DIR / "app" / "static" / "index.html")


@app.get("/api/session")
def session(request: Request) -> dict[str, Any]:
    email = request.session.get("email")
    if not email:
        return {
            "authenticated": False,
            "mode": settings.app_mode,
            "branding": settings.public_branding,
        }
    user = control_db.get_user(email)
    return {
        "authenticated": bool(user),
        "mode": settings.app_mode,
        "branding": settings.public_branding,
        "user": public_user(user) if user else None,
    }


@app.post("/api/login/demo")
def demo_login(payload: DemoLoginRequest, request: Request) -> dict[str, Any]:
    if settings.app_mode != "demo":
        raise HTTPException(status_code=404, detail="Demo login is disabled")
    email = payload.email.strip().lower()
    if "@" not in email or email.rsplit("@", 1)[1] != settings.allowed_email_domain:
        raise HTTPException(
            status_code=403,
            detail=f"Only @{settings.allowed_email_domain} accounts are allowed",
        )
    user = control_db.get_or_create_user(email, payload.display_name.strip())
    request.session["email"] = email
    return {
        "user": public_user(user),
        "mode": settings.app_mode,
        "branding": settings.public_branding,
    }


@app.post("/api/logout")
def logout(request: Request) -> dict[str, bool]:
    request.session.clear()
    return {"ok": True}


@app.post("/api/onboarding")
def onboarding(payload: OnboardingRequest, request: Request) -> dict[str, Any]:
    user = require_user(request)
    if payload.preferred_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail="Unsupported language")
    try:
        updated = control_db.complete_onboarding(
            user["email"],
            requested_team=payload.requested_team,
            preferred_language=payload.preferred_language,
            role_title=payload.role_title,
            profile={
                "responsibilities": payload.responsibilities,
                "recurring_tasks": payload.recurring_tasks,
                "tools_used": payload.tools_used,
                "automation_goals": payload.automation_goals,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"user": public_user(updated)}


@app.post("/api/preferences/language")
def update_language(payload: LanguagePreferenceRequest, request: Request) -> dict[str, Any]:
    user = require_user(request)
    if payload.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail="Unsupported language")
    updated = control_db.update_language(user["email"], payload.language)
    return {"user": public_user(updated), "languages": list(SUPPORTED_LANGUAGES)}


@app.put("/api/profile")
def update_profile(payload: ProfileUpdateRequest, request: Request) -> dict[str, Any]:
    user = require_user(request)
    try:
        updated = control_db.update_profile(
            user["email"],
            role_title=payload.role_title.strip(),
            profile={
                "responsibilities": payload.responsibilities,
                "recurring_tasks": payload.recurring_tasks,
                "tools_used": payload.tools_used,
                "automation_goals": payload.automation_goals,
            },
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"user": public_user(updated)}


@app.get("/api/teams")
def teams(request: Request) -> dict[str, Any]:
    require_user(request)
    return {
        "teams": [
            {"id": team, "label": team.replace("_", " ").title()}
            for team in TEAMS
            if team != "public"
        ]
    }


@app.get("/api/health")
async def health() -> dict[str, Any]:
    model_status = await orchestrator.model.status()
    return {
        "status": "ok",
        "mode": settings.app_mode,
        "model": model_status,
        "retrieval": {
            "mode": "hybrid_bm25_semantic",
            "embedding_model": settings.ollama_embedding_model,
            "available": any(
                name.split(":", 1)[0] == settings.ollama_embedding_model.split(":", 1)[0]
                for name in model_status.get("models", [])
            ),
        },
    }


EventCallback = Callable[[dict[str, Any]], Awaitable[None]]


async def _execute_chat(
    payload: ChatRequest,
    user: dict[str, Any],
    progress: EventCallback | None = None,
) -> dict[str, Any]:
    started_at = time.monotonic()
    if payload.language:
        if payload.language not in SUPPORTED_LANGUAGES:
            raise HTTPException(status_code=400, detail="Unsupported language")
        user = {**user, "preferred_language": payload.language}

    conversation_id = payload.conversation_id or str(uuid.uuid4())
    execution_id = str(uuid.uuid4())
    route_hint = (
        Route("welcome", "Welcome", False)
        if is_greeting(payload.message)
        else orchestrator.router.route(payload.message)
    )
    model_status = await orchestrator.model.status()
    steps = build_execution_plan(
        payload.message,
        route_hint,
        active_model=model_status.get("active_model"),
        available_models=model_status.get("models", []),
    )
    steps_by_id = {step["id"]: step for step in steps}

    async def emit(event: dict[str, Any]) -> None:
        event = {"execution_id": execution_id, **event}
        if event.get("type") == "step" and event.get("id") in steps_by_id:
            step = steps_by_id[event["id"]]
            for key in ("status", "model", "detail"):
                if event.get(key) is not None:
                    step[key] = event[key]
        if progress:
            await progress(event)

    await emit({"type": "plan", "route": route_hint.name, "steps": steps})
    await emit({"type": "step", "id": "route", "status": "running"})
    await emit(
        {
            "type": "step",
            "id": "route",
            "status": "completed",
            "detail": f"Selected {route_hint.label}",
        }
    )

    await emit({"type": "step", "id": "memory", "status": "running"})
    history = control_db.conversation_messages(conversation_id, user["email"], limit=6)
    await emit(
        {
            "type": "step",
            "id": "memory",
            "status": "completed",
            "detail": f"Loaded {len(history)} prior messages",
        }
    )

    retrieval_query = contextualize_retrieval_query(payload.message, history)
    sources: list[dict[str, Any]] = []
    if route_hint.requires_sources:
        await emit({"type": "step", "id": "retrieval", "status": "running"})
        sources = await asyncio.to_thread(
            knowledge.search, retrieval_query, accessible_teams(user), 4
        )
        await emit(
            {
                "type": "step",
                "id": "retrieval",
                "status": "completed",
                "detail": f"Found {len(sources)} approved sources",
            }
        )

    control_db.save_message(conversation_id, user["email"], "user", payload.message)
    result = await orchestrator.respond(
        prompt=payload.message,
        user=user,
        sources=sources,
        history=history,
        route=route_hint,
        available_models=model_status.get("models", []),
        progress=emit,
    )
    route = result["route"]

    action = None
    if route.action_type:
        action = control_db.create_action(
            user["email"],
            route.action_type,
            {"request": payload.message, "draft": result["answer"], "sandbox": True},
        )

    source_cards = [
        {
            "index": index,
            "title": source["title"],
            "source": source["source"],
            "team": source["team"],
            "excerpt": (source.get("summary") or source["content"])[:360],
            "updated_at": source.get("updated_at"),
        }
        for index, source in enumerate(sources, 1)
    ]
    completed_models = list(
        dict.fromkeys(
            step.get("model", "")
            for step in steps
            if step.get("status") == "completed" and step.get("model")
        )
    )
    evidence_status = (
        "grounded"
        if route.requires_sources and source_cards
        else "insufficient_evidence"
        if route.requires_sources
        else "not_required"
    )
    latency_ms = round((time.monotonic() - started_at) * 1000)
    metadata = {
        "route": route.name,
        "model": result["model"],
        "models": completed_models,
        "source_count": len(source_cards),
        "action_id": action["id"] if action else None,
        "execution_id": execution_id,
        "evidence_status": evidence_status,
        "latency_ms": latency_ms,
        "sources": source_cards,
    }
    message_id = control_db.save_message(
        conversation_id, user["email"], "assistant", result["answer"], metadata
    )
    control_db.audit(user["email"], "chat_completed", metadata)
    return {
        "conversation_id": conversation_id,
        "answer": result["answer"],
        "route": {"name": route.name, "label": route.label},
        "model": result["model"],
        "message_id": message_id,
        "sources": source_cards,
        "action": action,
        "orchestration": {
            "execution_id": execution_id,
            "steps": steps,
            "models": completed_models,
        },
        "quality": {
            "evidence_status": evidence_status,
            "source_count": len(source_cards),
            "latency_ms": latency_ms,
        },
    }


@app.post("/api/chat")
async def chat(payload: ChatRequest, request: Request) -> dict[str, Any]:
    user = require_user(request)
    if not user["onboarding_complete"]:
        raise HTTPException(status_code=409, detail="Complete onboarding first")
    return await _execute_chat(payload, user)


@app.websocket("/api/chat/stream")
async def chat_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    work_task: asyncio.Task[dict[str, Any]] | None = None
    receive_task: asyncio.Task[dict[str, Any]] | None = None
    try:
        email = websocket.session.get("email")
        user = control_db.get_user(email) if email else None
        if not user:
            await websocket.send_json({"type": "error", "detail": "Sign in required"})
            await websocket.close(code=4401)
            return
        if not user["onboarding_complete"]:
            await websocket.send_json({"type": "error", "detail": "Complete onboarding first"})
            await websocket.close(code=4409)
            return
        payload = ChatRequest.model_validate(await websocket.receive_json())

        async def send_progress(event: dict[str, Any]) -> None:
            await websocket.send_json(event)

        work_task = asyncio.create_task(_execute_chat(payload, user, send_progress))
        receive_task = asyncio.create_task(websocket.receive_json())
        while True:
            done, _ = await asyncio.wait(
                {work_task, receive_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if work_task in done:
                receive_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await receive_task
                result = await work_task
                await websocket.send_json({"type": "complete", "result": result})
                await websocket.close(code=1000)
                return

            client_event = receive_task.result()
            if client_event.get("type") == "cancel":
                work_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await work_task
                control_db.audit(
                    user["email"],
                    "chat_cancelled",
                    {"conversation_id": payload.conversation_id},
                )
                await websocket.send_json({"type": "cancelled"})
                await websocket.close(code=1000)
                return
            receive_task = asyncio.create_task(websocket.receive_json())
    except WebSocketDisconnect:
        if work_task and not work_task.done():
            work_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await work_task
        return
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "detail": str(exc)})
            await websocket.close(code=1011)
        except Exception:
            return


@app.get("/api/conversations")
def conversations(request: Request) -> dict[str, Any]:
    user = require_user(request)
    return {"conversations": control_db.list_conversations(user["email"])}


@app.get("/api/conversations/{conversation_id}")
def conversation_detail(conversation_id: str, request: Request) -> dict[str, Any]:
    user = require_user(request)
    try:
        return {"conversation": control_db.conversation_detail(conversation_id, user["email"])}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc


@app.patch("/api/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: str, payload: ConversationTitleRequest, request: Request
) -> dict[str, Any]:
    user = require_user(request)
    try:
        conversation = control_db.rename_conversation(
            conversation_id, user["email"], payload.title
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"conversation": conversation}


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, request: Request) -> dict[str, bool]:
    user = require_user(request)
    try:
        control_db.delete_conversation(conversation_id, user["email"])
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc
    return {"ok": True}


@app.post("/api/messages/{message_id}/feedback")
def answer_feedback(
    message_id: int, payload: FeedbackRequest, request: Request
) -> dict[str, Any]:
    user = require_user(request)
    try:
        feedback = control_db.save_feedback(
            message_id, user["email"], payload.rating, payload.comment
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Assistant message not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"feedback": feedback}


_ALLOWED_UPLOADS = {".txt", ".md", ".csv", ".json", ".pdf"}


def extract_text(filename: str, data: bytes) -> str:
    if Path(filename).suffix.lower() == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    return data.decode("utf-8", errors="replace")


@app.post("/api/documents/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    team: str | None = Form(default=None),
) -> dict[str, Any]:
    user = require_user(request)
    target_team = user["assigned_team"]
    if user["role"] == "owner" and team:
        target_team = team
    if not user["approved"] or target_team not in TEAMS or target_team == "public":
        raise HTTPException(status_code=403, detail="Approved department access required")

    original_name = Path(file.filename or "document").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in _ALLOWED_UPLOADS:
        raise HTTPException(status_code=400, detail="Allowed files: TXT, MD, CSV, JSON, PDF")
    data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds upload limit")
    text = extract_text(original_name, data).strip()
    if not text:
        raise HTTPException(status_code=400, detail="No readable text found")

    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", original_name).strip("-") or "document.txt"
    upload_dir = settings.uploads_dir / target_team
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_path = upload_dir / f"{uuid.uuid4().hex[:10]}-{safe_name}"
    stored_path.write_bytes(data)
    source = f"upload://{target_team}/{stored_path.name}"
    indexed = knowledge.add_document(target_team, original_name, source, text)
    control_db.audit(
        user["email"],
        "document_uploaded",
        {"team": target_team, "name": original_name, "source": source},
    )
    return {"team": target_team, "title": original_name, "source": source, **indexed}


@app.get("/api/documents")
def documents(request: Request) -> dict[str, Any]:
    user = require_user(request)
    return {"documents": knowledge.list_documents(accessible_teams(user))}


@app.get("/api/admin/users")
def admin_users(request: Request) -> dict[str, Any]:
    require_owner(request)
    return {"users": [public_user(user) for user in control_db.list_users()]}


@app.post("/api/admin/users/{user_id}/approve")
def approve_user(user_id: int, payload: ApprovalRequest, request: Request) -> dict[str, Any]:
    owner = require_owner(request)
    try:
        user = control_db.approve_user(owner["email"], user_id, payload.team)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"user": public_user(user)}


@app.get("/api/admin/audit")
def audit(request: Request) -> dict[str, Any]:
    require_owner(request)
    return {"events": control_db.recent_audit()}


@app.get("/api/admin/dashboard")
def dashboard(request: Request) -> dict[str, Any]:
    require_owner(request)
    return {"metrics": control_db.dashboard_metrics()}


@app.get("/api/admin/system")
def system_status(request: Request) -> dict[str, Any]:
    require_owner(request)
    return {
        "enabled": settings.service_controls_enabled,
        "configured": len(settings.service_control_key) >= 32,
        "actions": [
            {"id": action_id, **details}
            for action_id, details in SERVICE_ACTIONS.items()
        ],
        **service_controller.status(),
    }


@app.post("/api/admin/system/{action}", status_code=202)
def control_system(
    action: str, payload: SystemControlRequest, request: Request
) -> dict[str, Any]:
    owner = require_owner(request)
    if not settings.service_controls_enabled:
        raise HTTPException(status_code=503, detail="Service controls are disabled")
    if len(settings.service_control_key) < 32:
        raise HTTPException(status_code=503, detail="Service control key is not configured")
    try:
        details = validate_service_request(
            action,
            payload.admin_key,
            payload.confirmation,
            settings.service_control_key,
        )
    except PermissionError as exc:
        control_db.audit(owner["email"], "service_control_denied", {"action": action})
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        runner_pid = service_controller.schedule(action)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    control_db.audit(
        owner["email"],
        "service_action_scheduled",
        {"action": action, "runner_pid": runner_pid},
    )
    return {
        "accepted": True,
        "action": action,
        "label": details["label"],
        "message": f'{details["label"]} scheduled. Service status may change shortly.',
        "recovery": service_controller.status()["recovery"],
    }


@app.post("/api/actions")
def prepare_action(payload: ActionRequest, request: Request) -> dict[str, Any]:
    user = require_user(request)
    return {"action": control_db.create_action(user["email"], payload.action_type, payload.payload)}


@app.post("/api/actions/{action_id}/confirm")
def confirm_action(action_id: str, request: Request) -> dict[str, Any]:
    user = require_user(request)
    try:
        action = control_db.confirm_action(user["email"], action_id)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"action": action}
