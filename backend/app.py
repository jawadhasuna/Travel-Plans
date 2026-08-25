"""HTTP front door for the travel planning agents.

Runs on Hugging Face Spaces. The browser talks to /plan and gets each agent's
answer streamed back as it arrives, rather than waiting for the whole crew to
finish — four Gemini calls can take half a minute, which is long enough for a
proxy to give up on a plain request.

Two things guard the free-tier quota. One plan costs four Gemini calls and the
free tier is measured in requests per minute, so a handful of visitors at once
will trip a 429. A semaphore makes concurrent visitors queue instead of collide,
and a 429 is retried once after the delay Google asks for rather than being
thrown straight at the user.
"""

import asyncio
import json
import os
import re
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agents import crew, AGENT_LABELS

app = FastAPI(title="Travel Planner Agents")

# The browser calling this is served from somewhere else entirely, so it needs
# explicit permission. Vercel gives every deployment its own subdomain, hence
# the regex rather than a fixed list.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

# One plan at a time. Requests do not fail while another is running, they wait.
one_at_a_time = asyncio.Semaphore(1)

MAX_RETRY_WAIT = 65     # seconds; Google's suggested delay is usually under a minute


class PlanRequest(BaseModel):
    request: str = Field(min_length=3, max_length=500)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "key_configured": bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")),
        "busy": one_at_a_time.locked(),
    }


def sse(event: str, payload: dict) -> str:
    """Format one Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def rate_limit_wait(error: Exception) -> int | None:
    """If this is a quota error, how long does Google want us to wait?

    Returns None for any other kind of failure, so genuine bugs are not
    silently retried.
    """
    text = str(error)
    if "429" not in text and "RESOURCE_EXHAUSTED" not in text:
        return None
    match = re.search(r"'retryDelay':\s*'(\d+)s'", text)
    return min(int(match.group(1)) + 2, MAX_RETRY_WAIT) if match else 30


async def stream_once(request: str):
    """Run the crew once, yielding each agent's contribution as it lands."""
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    runner = InMemoryRunner(agent=crew)
    user_id = "web"
    session_id = uuid.uuid4().hex          # a fresh session per request, so two
                                           # visitors never see each other's trip
    await runner.session_service.create_session(
        app_name=runner.app_name, user_id=user_id, session_id=session_id
    )

    seen = set()
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=request)]),
    ):
        if not (event.content and event.content.parts):
            continue
        author = getattr(event, "author", "") or "travel_coordinator"
        text = "".join(p.text for p in event.content.parts if p.text).strip()
        if not text:
            continue
        # Guard against the same paragraph arriving twice as the run unwinds.
        fingerprint = (author, text[:120])
        if fingerprint in seen:
            continue
        seen.add(fingerprint)

        yield sse("message", {
            "agent": author,
            "label": AGENT_LABELS.get(author, author),
            "text": text,
        })


async def run_crew(request: str):
    yield sse("start", {"request": request})

    async with one_at_a_time:
        for attempt in (1, 2):
            try:
                async for chunk in stream_once(request):
                    yield chunk
                yield sse("done", {})
                return
            except Exception as exc:
                wait = rate_limit_wait(exc)
                if wait is None or attempt == 2:
                    message = (
                        f"Gemini's free tier is rated {('busy' if wait else 'unavailable')}. "
                        "Try again in a minute."
                        if wait else f"{type(exc).__name__}: {exc}"
                    )
                    yield sse("error", {"message": message})
                    return
                # Partial output already reached the browser; tell it to clear
                # what it has so the retry does not append to a half-finished plan.
                yield sse("retry", {"seconds": wait})
                await asyncio.sleep(wait)


@app.post("/plan")
async def plan(body: PlanRequest):
    return StreamingResponse(
        run_crew(body.request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Spaces sits behind a proxy that will otherwise buffer the whole
            # response and defeat the point of streaming.
            "X-Accel-Buffering": "no",
        },
    )
