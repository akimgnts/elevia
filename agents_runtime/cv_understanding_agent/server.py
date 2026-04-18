from __future__ import annotations

from fastapi import FastAPI

from .agent import CVUnderstandingAgent
from .config import LlmUnavailableError, get_model_name
from .contracts import AgentSessionRequest, SessionResponse

app = FastAPI(title="Elevia Agents Runtime", version="0.1.0")
agent = CVUnderstandingAgent()


@app.get("/health")
async def health() -> dict[str, str]:
    try:
        model = get_model_name()
        return {"status": "ok", "agent": agent.name, "model": model}
    except Exception as exc:  # pragma: no cover - defensive
        return {"status": "error", "detail": str(exc)}


@app.post("/profile-understanding/session", response_model=SessionResponse)
async def create_profile_understanding_session(payload: AgentSessionRequest) -> SessionResponse:
    try:
        return agent.run(payload)
    except LlmUnavailableError:
        raise
