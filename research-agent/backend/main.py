import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio

from agent import ResearchAgent
from ollama_client import get_available_models

app = FastAPI()

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# --- Pydantic Models ---
class ResearchRequest(BaseModel):
    topic: str
    model: str
    depth: int

# --- Routes ---
@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/models")
async def list_models():
    """
    Get a list of available Ollama models.
    On error, return a fallback list.
    """
    try:
        models = await get_available_models()
        return {"models": models}
    except Exception as e:
        print(f"Error fetching models: {e}")
        # Fallback list
        return {"models": ["llama3.2", "mistral", "deepseek-r1"]}

@app.post("/research")
async def run_research(request: ResearchRequest):
    """
    Starts a research stream using the agent.
    """
    if not request.topic:
        raise HTTPException(status_code=400, detail="Topic cannot be empty.")
    if not request.model:
        raise HTTPException(status_code=400, detail="Model must be selected.")

    # Depth maps to max_searches
    max_searches = request.depth 

    agent = ResearchAgent(model=request.model, max_searches=max_searches)

    async def event_stream():
        try:
            async for event in agent.run(request.topic):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            error_event = {"type": "error", "data": {"content": f"An unexpected error occurred in the stream: {str(e)}"}}
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
