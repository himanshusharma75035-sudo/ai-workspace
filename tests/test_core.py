import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from app import main as app_main
from app.config import settings
from app.database import ControlDatabase
from app.evaluation import load_evaluation_cases, score_evaluation_answer
from app.intents import contextualize_retrieval_query, is_broad_organization_overview, is_greeting
from app.knowledge import _fts_query, chunk_text
from app.orchestrator import (
    SUPPORTED_LANGUAGES,
    IntentRouter,
    _answer_is_usable,
    _automation_answer,
    _email_evidence_fallback,
    _language_instruction,
    _organization_overview_answer,
    _source_comparison_answer,
    build_execution_plan,
)
from app.service_control import SERVICE_ACTIONS, ServiceController, validate_service_request


def test_public_session_exposes_only_safe_runtime_branding() -> None:
    with TestClient(app_main.app) as client:
        response = client.get("/api/session")
    assert response.status_code == 200
    payload = response.json()
    assert payload["branding"] == settings.public_branding
    assert set(payload["branding"]) == {
        "organization_name",
        "assistant_name",
        "organization_initial",
        "allowed_email_domain",
    }
    assert "session_secret" not in payload["branding"]


def test_health_response_does_not_expose_filesystem_path(monkeypatch) -> None:
    async def model_status() -> dict[str, object]:
        return {"models": [], "active_model": None, "available": False}

    monkeypatch.setattr(app_main.orchestrator.model, "status", model_status)
    response = asyncio.run(app_main.health())
    assert "project_root" not in response


def test_chunking_preserves_text() -> None:
    text = "Settlement reconciliation " * 200
    chunks = chunk_text(text, size=300, overlap=50)
    assert len(chunks) > 2
    assert all(chunk.strip() for chunk in chunks)
    assert all(len(chunk) <= 300 for chunk in chunks)


def test_router_selects_expected_capabilities() -> None:
    router = IntentRouter()
    assert router.route("Draft an email for the CFO").name == "email"
    assert router.route("Help me automate the daily report").name == "automation"
    assert router.route("Create a product photo").name == "image"
    assert router.route("What does Example Product offer?").name == "knowledge"

def test_hindi_image_routing() -> None:
    assert IntentRouter().route("\u092e\u0941\u091d\u0947 \u092b\u094b\u091f\u094b \u092c\u0928\u093e\u0913").name == "image"


def test_broad_organization_query_expands_to_overview_terms() -> None:
    query = _fts_query(f"Explain {settings.organization_name}'s different businesses in Hinglish")
    assert '"overview"' in query
    assert '"services"' in query
    assert '"hinglish"' not in query


def test_overview_template_uses_ranked_source_citations() -> None:
    sources = [
        {"title": "Company overview", "summary": "Provides financial technology infrastructure."},
        {"title": "Global platform", "summary": "Supports institutions with APIs."},
        {"title": "Assisted channel", "summary": "Supports last-mile service delivery."},
    ]
    answer = _organization_overview_answer(
        f"{settings.organization_name} ke businesses Hinglish mein batao", sources, "Hinglish"
    )
    assert answer is not None
    assert "[S1]" in answer
    assert "[S2]" in answer
    assert "[S3]" in answer


def test_automation_template_covers_control_questions() -> None:
    answer = _automation_answer("Design an automation")
    assert "Trigger, frequency, and deadline?" in answer
    assert "Reviewer and final approver?" in answer
    assert "Failure, retry, and escalation rules?" in answer
    assert "sandbox" in answer

def test_reported_overview_wording_is_detected() -> None:
    organization = settings.organization_name
    assert is_broad_organization_overview(f"what {organization} actually does")
    assert '"overview"' in _fts_query(f"what {organization} actually does")
    assert not is_broad_organization_overview(f"What does {organization} ProductX offer?")


def test_greetings_do_not_need_model_or_sources() -> None:
    router = IntentRouter()
    assert is_greeting("Hi!")
    assert not router.route("Help me automate a report").requires_sources


def test_followup_retrieval_uses_previous_user_question() -> None:
    history = [
        {"role": "user", "content": "Explain Example Product services"},
        {"role": "assistant", "content": "Example Product supports field services."},
    ]
    contextual = contextualize_retrieval_query("Tell me more about that", history)
    assert contextual.startswith("Explain Example Product services")


def test_conversation_history_is_scoped_by_employee(tmp_path) -> None:
    database = ControlDatabase(tmp_path / "control.db")
    database.initialize()
    database.save_message("shared-id", "finance@company.example", "user", "finance secret")
    database.save_message("shared-id", "operations@company.example", "user", "operations secret")
    finance = database.conversation_messages("shared-id", "finance@company.example")
    assert [item["content"] for item in finance] == ["finance secret"]

def test_source_comparison_is_grounded() -> None:
    sources = [
        {"title": "Product A", "summary": "An assisted service platform."},
        {"title": "Product B", "summary": "A white-label B2B platform."},
    ]
    answer = _source_comparison_answer("Compare Product A versus Product B", sources)
    assert answer is not None
    assert "assisted service platform" in answer
    assert "white-label B2B platform" in answer
    assert "[S1]" in answer and "[S2]" in answer


def test_selected_language_overrides_prompt_language() -> None:
    assert _language_instruction("Please answer in English", "Tamil") == (
        "Reply only in natural Tamil using Tamil script."
    )
    assert _language_instruction("यह हिंदी में है", "English") == "Reply only in clear English."
    assert {"Hindi", "Bengali", "Marathi", "Tamil", "Telugu", "Urdu"} < set(
        SUPPORTED_LANGUAGES
    )


def test_long_task_plan_exposes_multiple_real_models() -> None:
    prompt = (
        "Draft a detailed CFO recommendation and compare Product A with Product B, then "
        "identify financial risks, controls, owners, approval steps, implementation phases, "
        "success metrics and the follow-up email that should be sent."
    )
    route = IntentRouter().route(prompt)
    steps = build_execution_plan(
        prompt,
        route,
        active_model="qwen3:4b",
        available_models=["qwen3:0.6b", "qwen3:4b", "embeddinggemma:latest"],
    )
    models = {step["model"] for step in steps}
    assert "qwen3:0.6b" in models
    assert "embeddinggemma" in models
    assert "qwen3:4b" in models
    assert "policy-engine" in models


def test_language_preference_is_persisted(tmp_path) -> None:
    database = ControlDatabase(tmp_path / "language.db")
    database.initialize()
    database.get_or_create_user("owner@company.example", "Owner")
    updated = database.update_language("owner@company.example", "Bengali")
    assert updated["preferred_language"] == "Bengali"
    assert database.get_user("owner@company.example")["preferred_language"] == "Bengali"


def test_voice_language_and_live_orchestration_controls_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "app" / "static" / "index.html").read_text(encoding="utf-8")
    javascript = (root / "app" / "static" / "app.js").read_text(encoding="utf-8")
    assert 'id="voiceButton"' in html
    assert 'id="languageSelector"' in html
    assert "SpeechRecognition" in javascript
    assert "/api/chat/stream" in javascript


def test_chat_websocket_route_is_registered() -> None:
    from app.main import app

    assert any(getattr(route, "path", None) == "/api/chat/stream" for route in app.routes)


def test_hidden_reasoning_is_rejected_even_with_a_citation() -> None:
    route = IntentRouter().route("What does the organization do?")
    leaked = "Okay, the user asked for organization facts. I should check the source [S1]."
    assert not _answer_is_usable(leaked, "What does the organization do?", route, [{"title": "Company"}])
    leaked_email = (
        "We are drafting an email to the CFO. The user has specified the required "
        "sections. We have two approved sources: [S1] and [S2]. We must: start with a direct answer."
    )
    assert not _answer_is_usable(
        leaked_email,
        "Draft an email",
        IntentRouter().route("Draft an email"),
        [{"title": "Product A"}, {"title": "Product B"}],
    )


def test_controlled_email_fallback_uses_both_sources() -> None:
    sources = [
        {"title": "Product A", "summary": "An assisted service platform."},
        {"title": "Product B", "summary": "A white-label B2B platform."},
    ]
    answer = _email_evidence_fallback("Draft a comparison email", sources, "English")
    assert answer is not None
    assert "assisted service platform" in answer
    assert "white-label B2B platform" in answer
    assert "[S1]" in answer and "[S2]" in answer


def test_conversations_feedback_profile_and_dashboard_are_user_scoped(tmp_path) -> None:
    database = ControlDatabase(tmp_path / "demo-v2.db")
    database.initialize()
    owner = database.get_or_create_user("owner@company.example", "Owner")
    database.complete_onboarding(
        owner["email"],
        requested_team="finance",
        preferred_language="English",
        role_title="Finance Lead",
        profile={"responsibilities": "Reporting"},
    )
    updated = database.update_profile(
        owner["email"],
        role_title="Finance Controller",
        profile={"responsibilities": "Reporting and controls", "tools_used": "SQL"},
    )
    assert updated["assigned_team"] == "finance"
    assert updated["profile"]["tools_used"] == "SQL"

    database.save_message("conversation-1", owner["email"], "user", "Explain the company")
    answer_id = database.save_message(
        "conversation-1",
        owner["email"],
        "assistant",
        "Company answer [S1]",
        {"route": "knowledge", "evidence_status": "grounded", "latency_ms": 1200},
    )
    conversations = database.list_conversations(owner["email"])
    assert conversations[0]["title"] == "Explain the company"
    assert conversations[0]["message_count"] == 2

    detail = database.conversation_detail("conversation-1", owner["email"])
    assert detail["messages"][-1]["id"] == answer_id
    feedback = database.save_feedback(answer_id, owner["email"], "helpful", "Clear")
    assert feedback["rating"] == "helpful"
    metrics = database.dashboard_metrics()
    assert metrics["helpful_rate"] == 100
    assert metrics["average_latency_ms"] == 1200
    assert metrics["measured_latency_answers"] == 1

    other = database.get_or_create_user("other@company.example", "Other")
    assert database.list_conversations(other["email"]) == []
    try:
        database.save_feedback(answer_id, other["email"], "not_helpful")
    except KeyError:
        pass
    else:
        raise AssertionError("Another employee must not rate an answer they cannot access")

    renamed = database.rename_conversation(
        "conversation-1", owner["email"], "Company overview"
    )
    assert renamed["title"] == "Company overview"
    database.delete_conversation("conversation-1", owner["email"])
    assert database.list_conversations(owner["email"]) == []


def test_quality_evaluation_cases_are_valid_and_score_deterministically() -> None:
    root = Path(__file__).resolve().parents[1]
    cases = load_evaluation_cases(root / "evaluations" / "golden_questions.jsonl")
    assert len(cases) >= 10
    case = {
        "id": "example",
        "expected_any": ["workflow", "Product"],
        "minimum_citations": 2,
        "pass_score": 75,
    }
    score = score_evaluation_answer(case, "The company provides workflow tools. Product A helps [S1] [S2].")
    assert score["overall_score"] == 100
    assert score["passed"]


def test_demo_v2_routes_and_controls_exist() -> None:
    from app.main import app

    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/api/conversations" in paths
    assert "/api/messages/{message_id}/feedback" in paths
    assert "/api/profile" in paths
    assert "/api/admin/dashboard" in paths
    root = Path(__file__).resolve().parents[1]
    html = (root / "app" / "static" / "index.html").read_text(encoding="utf-8")
    enhancements = (root / "app" / "static" / "enhancements.js").read_text(encoding="utf-8")
    assert 'id="conversationList"' in html
    assert 'id="dashboardMetrics"' in html
    assert "cancelCurrentExecution" in enhancements
    assert "submitFeedback" in enhancements


def test_service_control_requires_key_and_exact_confirmation() -> None:
    control_key = "a-separate-service-control-key-123456789"
    details = validate_service_request(
        "restart_app", control_key, "RESTART APP", control_key
    )
    assert details["label"] == "Restart web application"
    assert len({item["confirmation"] for item in SERVICE_ACTIONS.values()}) == len(
        SERVICE_ACTIONS
    )

    try:
        validate_service_request("restart_app", "wrong-key", "RESTART APP", control_key)
    except PermissionError:
        pass
    else:
        raise AssertionError("A wrong service-control key must be rejected")

    try:
        validate_service_request("restart_app", control_key, "restart app", control_key)
    except ValueError:
        pass
    else:
        raise AssertionError("The action confirmation phrase must match exactly")


def test_system_control_routes_ui_and_project_local_recovery_exist(tmp_path) -> None:
    from app.main import app

    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/api/admin/system" in paths
    assert "/api/admin/system/{action}" in paths

    controller = ServiceController(tmp_path)
    status = controller.status()
    assert not status["application"]["running"]
    assert str(tmp_path.resolve()) in status["recovery"]["start"]

    root = Path(__file__).resolve().parents[1]
    html = (root / "app" / "static" / "index.html").read_text(encoding="utf-8")
    enhancements = (root / "app" / "static" / "enhancements.js").read_text(
        encoding="utf-8"
    )
    assert 'id="systemView"' in html
    assert 'data-system-action="start_all"' in html
    assert 'data-system-action="stop_all"' in html
    assert 'id="systemAdminKey" type="password"' in html
    assert "localStorage" not in enhancements
    assert 'byId("systemAdminKey").value=""' in enhancements
