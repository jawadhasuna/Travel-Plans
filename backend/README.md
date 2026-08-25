# Travel Plans — agent backend

The API behind [travelsplan.vercel.app](https://travelsplan.vercel.app). Four
Google ADK agents on Gemini: three specialists research flights, hotels and an
itinerary at the same time, then a fourth writes them up as one plan.

Source: [github.com/jawadhasuna/Travel-Plans](https://github.com/jawadhasuna/Travel-Plans)

## Endpoints

**`POST /plan`** — takes `{"request": "3 days in Istanbul, budget, from Lahore"}`
and streams Server-Sent Events back:

| Event | Meaning |
|---|---|
| `start` | request accepted |
| `message` | one agent finished — carries `agent`, `label`, `text` |
| `retry` | hit the Gemini free-tier limit, waiting before another go |
| `error` | gave up, with the reason |
| `done` | all four finished |

It streams because four Gemini calls take 10–30 seconds, which is long enough
for a proxy to time out on a plain request.

**`GET /health`** — returns whether an API key is configured and whether a plan
is currently running.

## Configuration

One environment variable:

| | |
|---|---|
| `GOOGLE_API_KEY` | a Gemini API key from [aistudio.google.com](https://aistudio.google.com/apikey) |

Set it on the service rather than baking it into the image:

```bash
gcloud run services update travel-plans --region us-central1 --update-env-vars GOOGLE_API_KEY=your_key
```

## Deploying

```bash
gcloud run deploy travel-plans --source . --region us-central1 --allow-unauthenticated
```

Cloud Build reads the Dockerfile, builds the image, and Cloud Run serves it,
scaling to zero when nobody is using it.

## Notes on the free tier

One plan costs four Gemini calls. The free tier is measured in requests per
minute, so a few visitors at once will trip a 429. Two things keep that from
being visible: a semaphore means concurrent requests queue rather than collide,
and a 429 is retried once after the delay Google asks for.

Running the model as `gemini-3.5-flash-lite` rather than `flash` is part of the
same trade — roomier quota, faster, and more than good enough for travel
suggestions.
