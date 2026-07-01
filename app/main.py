"""
Step 4: FastAPI application.

Two endpoints:
  GET  /health  — readiness check (returns {"status": "ok"})
  POST /chat    — stateless conversational agent

The service is stateless. Full conversation history arrives on every
POST /chat call. No server-side session storage.
"""

import sys
from pathlib import Path

# Ensure app/ is on the import path when running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from schemas import ChatRequest, ChatResponse, Recommendation
from agent import chat as agent_chat

app = FastAPI(
    title="SHL Assessment Recommender",
    description="Conversational agent for recommending SHL assessments.",
    version="1.0.0",
)

# Allow all origins — needed for the automated evaluator to hit the endpoint
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Readiness check. Returns 200 as soon as the service is up."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Stateless conversational endpoint.

    Accepts full conversation history on every call.
    Returns agent reply + optional structured recommendations.
    """
    try:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        if not messages:
            raise HTTPException(status_code=400, detail="messages list cannot be empty")

        result = agent_chat(messages)

        # Ensure recommendations are properly typed
        recommendations = [
            Recommendation(
                name=r["name"],
                url=r["url"],
                test_type=r["test_type"],
            )
            for r in result.get("recommendations", [])
        ]

        return ChatResponse(
            reply=result["reply"],
            recommendations=recommendations,
            end_of_conversation=result.get("end_of_conversation", False),
        )

    except HTTPException:
        raise
    except Exception as e:
        # Never let an internal error break the schema — return a safe fallback
        return ChatResponse(
            reply="I'm sorry, I encountered an issue. Could you please rephrase your question?",
            recommendations=[],
            end_of_conversation=False,
        )