import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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


@app.post("/chat")
def chat(request: ChatRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages list cannot be empty")

    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    
    try:
        result = agent_chat(messages)
    except Exception as e:
        # Return the actual error so we can debug it
        return JSONResponse(
            status_code=200,
            content={
                "reply": f"DEBUG ERROR: {type(e).__name__}: {str(e)}",
                "recommendations": [],
                "end_of_conversation": False,
                "debug_traceback": traceback.format_exc()
            }
        )

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