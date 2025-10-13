from agent import create_agent
import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import uvicorn
import os
import sys

# Add parent directory to path for agent imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI()
agent_instance = None
sse_client = None

@app.on_event("startup")
async def startup_event():
    global agent_instance
    agent_instance = await create_agent()
    if agent_instance is None:
        print("Failed to create agent instance.")
    else:
        print("Agent instance created successfully.")

@app.get("/stream")
async def stream_response(query: str):
    global agent_instance
    if agent_instance is None:
        return StreamingResponse(iter(["Agent not initialized.\n"]), media_type="text/plain")

    async def event_generator():
        try:
            async for chunk in agent_instance.stream_chat(query):
                yield chunk
        except Exception as e:
            yield f"Error: {str(e)}\n"

    return StreamingResponse(event_generator(), media_type="text/plain")