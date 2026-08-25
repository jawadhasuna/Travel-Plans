# Travel Plans

Four AI agents plan a trip together. Three specialists research flights, hotels and
a day-by-day itinerary **at the same time**, then a fourth reads all three answers
and writes them up as one plan.

**Live: [travelsplan.vercel.app](https://travelsplan.vercel.app)**

Ask for *"4 days in Istanbul in May, mid budget, flying from Islamabad"* and watch
three panels fill in as each specialist finishes, then the plan assemble underneath.

---

## The interesting part

The obvious way to build this is one coordinator agent with the three specialists
as its `sub_agents`, and let the model decide who to ask. That is what the first
version did, and it does not work.

An LLM coordinator picks **one** sub-agent, hands the conversation over, and the
turn ends. You get flight options and nothing else — no hotels, no itinerary, no
combined plan, despite an instruction telling it to combine all three.

The fix is to stop asking the model to orchestrate and orchestrate explicitly:

```
                    ┌── flights_agent ───┐
request ── Parallel ├── hotels_agent ────┤── session state ── synthesizer ── plan
                    └── itinerary_agent ─┘
```

`ParallelAgent` runs all three concurrently, each writing its answer to session
state under its own `output_key`. The synthesizer's prompt then reads all three by
name. Running them in parallel also halved the wall-clock time — the whole thing
takes as long as the slowest specialist rather than the sum of all three.

**A full plan takes about 12 seconds.**

## How it is deployed

Two halves, two platforms, because they want different things:

| | Where | Why |
|---|---|---|
| `web/` | Vercel | static HTML, CSS and JS — no build step |
| `backend/` | Google Cloud Run | a container that scales to zero when idle |

Vercel's serverless functions are the natural home for the API too, but an agent
run takes 10–30 seconds and would spend most of that fighting timeouts. Cloud Run
holds a request open as long as it needs and costs nothing while nobody is using
it.

The backend streams **Server-Sent Events** rather than returning one response at
the end, so each specialist's answer reaches the browser the moment it lands
instead of the page sitting blank for half a minute.

## Working within the free tier

One plan costs four Gemini calls, and the free tier is measured in requests per
minute — `gemini-3.5-flash` allows five. Two visitors in the same minute is enough
to trip a 429.

Three things keep that from being visible:

- `gemini-3.5-flash-lite` instead of `flash` — roomier quota, faster, and more than
  good enough for travel suggestions
- a semaphore, so concurrent visitors queue rather than collide
- one retry on 429 after the delay Google asks for, surfaced in the UI as
  *"Gemini's free tier is busy, retrying in N seconds"* rather than a dead page

## The drawing

The background is inline SVG, not an image file — it stays sharp at any window
size and the pieces move independently. Clouds drift at three different speeds,
the plane hovers, the toddler waves. All of it sits behind
`prefers-reduced-motion`.

The boarding door is at the front of the fuselage for a reason: the first version
put it mid-body, which buried the stairs and the whole family behind the wing and
engine.

## Endpoints

**`POST /plan`** — `{"request": "3 days in Istanbul, budget, from Lahore"}`,
streams SSE:

| Event | Meaning |
|---|---|
| `start` | request accepted |
| `message` | one agent finished — carries `agent`, `label`, `text` |
| `retry` | hit the free-tier limit, waiting before another go |
| `error` | gave up, with the reason |
| `done` | all four finished |

**`GET /health`** — whether a key is configured and whether a plan is running.

## Running it yourself

You need a Gemini API key from [aistudio.google.com](https://aistudio.google.com/apikey).

```bash
cd backend
```

```bash
python -m venv .venv
```

```bash
.venv\Scripts\pip install -r requirements.txt
```

```bash
$env:GOOGLE_API_KEY = "your_key"
```

Then either the command line version:

```bash
python ..\travel_planner.py
```

Or the API, with the frontend pointed at it:

```bash
.venv\Scripts\uvicorn app:app --port 7863
```

Serve `web/` on any static server and run
`localStorage.setItem("backend", "http://127.0.0.1:7863")` in the browser console
to override the deployed backend.

## Deploying

```bash
gcloud run deploy travel-plans --source backend --region us-central1 --allow-unauthenticated
```

```bash
gcloud run services update travel-plans --region us-central1 --update-env-vars GOOGLE_API_KEY=your_key
```

The frontend is whatever static host you like; `web/` deploys to Vercel as-is.

## Files

| | |
|---|---|
| `backend/agents.py` | the four agents and how they are wired together |
| `backend/app.py` | FastAPI, SSE streaming, quota handling |
| `web/index.html` | the page and the whole SVG scene |
| `web/app.js` | SSE parsing, a small markdown renderer, panel state |
| `travel_planner.py` | command line version, sharing the same agents |

## Stack

Google ADK · Gemini 3.5 Flash Lite · FastAPI · Cloud Run · Vercel · no frontend
framework and no build step
