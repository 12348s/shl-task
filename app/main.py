import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from schemas import ChatRequest, ChatResponse, Recommendation
from agent import chat as agent_chat

app = FastAPI(title="SHL Assessment Recommender", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages list cannot be empty")

    try:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        result = agent_chat(messages)

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

    except Exception:
        # Never let an internal error break the schema
        return ChatResponse(
            reply="I'm sorry, I encountered an issue processing your request. Could you please try again?",
            recommendations=[],
            end_of_conversation=False,
        )