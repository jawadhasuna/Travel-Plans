"""The travel planning crew.

Three specialists work the same request at the same time — flights, hotels,
itinerary — and a fourth agent stitches their three answers into one plan.

A note on the shape of this, because it changed. The obvious way to write it is
one coordinator with the three specialists as `sub_agents`, and let the model
decide who to ask. That is what an LLM-driven coordinator does: it picks ONE
sub-agent, hands the conversation over, and the turn ends there. You get flight
options and nothing else — no hotels, no itinerary, no combined plan.

So the fan-out is explicit instead. ParallelAgent runs all three specialists
concurrently and parks each answer in session state under its `output_key`; the
synthesizer then reads all three by name. Running them in parallel also means
the whole thing takes as long as the slowest specialist rather than the sum of
all three.
"""

from google.adk.agents import Agent, ParallelAgent, SequentialAgent

MODEL = "gemini-3.5-flash-lite"   # lite has a roomier free-tier quota; see app.py

flights_agent = Agent(
    name="flights_agent",
    model=MODEL,
    description="Suggests flight options for a trip.",
    instruction=(
        "You suggest realistic flight routes and rough price ranges for the "
        "requested trip. Keep it brief."
    ),
    output_key="flights",
)

hotels_agent = Agent(
    name="hotels_agent",
    model=MODEL,
    description="Suggests hotel/accommodation options for a trip.",
    instruction=(
        "You suggest 2-3 accommodation options fitting the trip's destination "
        "and budget vibe. Keep it brief."
    ),
    output_key="hotels",
)

itinerary_agent = Agent(
    name="itinerary_agent",
    model=MODEL,
    description="Plans a day-by-day itinerary of activities for a trip.",
    instruction=(
        "You create a simple day-by-day activity plan for the requested trip "
        "length and destination."
    ),
    output_key="itinerary",
)

specialists = ParallelAgent(
    name="specialists",
    description="Runs the flights, hotels and itinerary agents at the same time.",
    sub_agents=[flights_agent, hotels_agent, itinerary_agent],
)

# The braces are filled in from session state with whatever the three
# specialists wrote there.
synthesizer = Agent(
    name="travel_coordinator",
    model=MODEL,
    description="Combines the specialists' answers into one trip plan.",
    instruction=(
        "You are a travel planning coordinator. Three specialists have already "
        "researched the trip. Combine their findings into one clear, organized "
        "plan under the headings Flights, Where to stay, and Day by day. "
        "Do not invent details none of them mentioned, and do not repeat "
        "yourself.\n\n"
        "FLIGHTS:\n{flights}\n\n"
        "HOTELS:\n{hotels}\n\n"
        "ITINERARY:\n{itinerary}"
    ),
)

crew = SequentialAgent(
    name="travel_crew",
    description="Researches a trip with three specialists, then writes the plan.",
    sub_agents=[specialists, synthesizer],
)

# Friendly names for the web UI, so it can label who is speaking instead of
# showing raw identifiers.
AGENT_LABELS = {
    "flights_agent": "Flights",
    "hotels_agent": "Hotels",
    "itinerary_agent": "Itinerary",
    "travel_coordinator": "The plan",
}
