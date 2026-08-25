r"""Travel planner — command line version.

The agents themselves live in backend/agents.py so the CLI and the web API
share one definition. Run:

    python travel_planner.py
"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from agents import crew, AGENT_LABELS          # noqa: E402
from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types                 # noqa: E402

load_dotenv()


async def main():
    runner = InMemoryRunner(agent=crew)
    user_id, session_id = "user1", "session1"
    await runner.session_service.create_session(
        app_name=runner.app_name, user_id=user_id, session_id=session_id
    )

    print("Travel Planner ready! Type 'exit' to quit.\n")

    while True:
        request = input("You: ")
        if request.lower() == "exit":
            break

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=request)]),
        ):
            if not (event.content and event.content.parts):
                continue
            author = getattr(event, "author", "") or "?"
            text = "".join(p.text for p in event.content.parts if p.text).strip()
            if text:
                print(f"\n[{AGENT_LABELS.get(author, author)}]\n{text}\n")


if __name__ == "__main__":
    asyncio.run(main())
