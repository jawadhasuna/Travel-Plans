/* Travel Plans — front end
 *
 * Talks to the agent backend on Hugging Face Spaces. The backend streams
 * Server-Sent Events, one per agent, so the three specialists fill in as they
 * finish rather than the page sitting blank for half a minute.
 */

// Where the agents live. Override in the browser console with
// localStorage.setItem("backend", "http://127.0.0.1:7863") when testing locally.
const BACKEND =
  localStorage.getItem("backend") ||
  "https://jawadhasuna-travel-plans.hf.space";

const $ = (id) => document.getElementById(id);
const input = $("request");
const goButton = $("go");
const status = $("status");

/* ---------- a very small markdown renderer ----------
 *
 * The agents answer in markdown. Rather than pull in a library for four
 * constructs, this handles the ones they actually use: ### headings, **bold**,
 * *italic*, and bullet lists. Everything is escaped first, so nothing the model
 * writes can inject markup into the page.
 */

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

function markdown(text) {
  const lines = escapeHtml(text).split("\n");
  const out = [];
  let inList = false;

  const closeList = () => { if (inList) { out.push("</ul>"); inList = false; } };

  for (let line of lines) {
    line = line.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    // Italic only when the asterisk is not part of a list marker.
    line = line.replace(/(^|[^*\w])\*([^*\n]+?)\*(?![*\w])/g, "$1<em>$2</em>");

    const heading = line.match(/^\s*#{1,6}\s+(.*)$/);
    const bullet = line.match(/^\s*[-*+]\s+(.*)$/);

    if (heading) {
      closeList();
      out.push(`<h3>${heading[1]}</h3>`);
    } else if (bullet) {
      if (!inList) { out.push("<ul>"); inList = true; }
      out.push(`<li>${bullet[1]}</li>`);
    } else if (line.trim() === "") {
      closeList();
    } else {
      closeList();
      out.push(`<p>${line}</p>`);
    }
  }
  closeList();
  return out.join("");
}

/* ---------- panels ---------- */

const panels = {
  flights_agent: document.querySelector('[data-agent="flights_agent"]'),
  hotels_agent: document.querySelector('[data-agent="hotels_agent"]'),
  itinerary_agent: document.querySelector('[data-agent="itinerary_agent"]'),
  travel_coordinator: $("plan"),
};

function setState(agent, state, label) {
  const panel = panels[agent];
  if (!panel) return;
  panel.dataset.state = state;
  const tag = panel.querySelector(".state");
  if (tag) tag.textContent = label;
}

function reset() {
  $("crew").hidden = false;
  $("plan").hidden = false;
  for (const [agent, panel] of Object.entries(panels)) {
    panel.querySelector(".body").innerHTML = "";
    setState(agent, "running", agent === "travel_coordinator" ? "waiting" : "thinking");
  }
  setState("travel_coordinator", "", "waiting");
}

/* ---------- the request ---------- */

async function plan() {
  const request = input.value.trim();
  if (request.length < 3) {
    status.textContent = "Tell me where you want to go first.";
    status.classList.add("error");
    input.focus();
    return;
  }

  status.classList.remove("error");
  status.textContent = "Sending your trip to the crew…";
  goButton.disabled = true;
  input.disabled = true;
  reset();

  try {
    const response = await fetch(`${BACKEND}/plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request }),
    });

    if (!response.ok) throw new Error(`Backend returned ${response.status}`);

    // Parse the SSE stream by hand — EventSource cannot do POST.
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Events are separated by a blank line.
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop();

      for (const chunk of chunks) {
        const eventName = (chunk.match(/^event: (.+)$/m) || [])[1];
        const rawData = (chunk.match(/^data: (.+)$/m) || [])[1];
        if (!eventName || !rawData) continue;
        handle(eventName, JSON.parse(rawData));
      }
    }
  } catch (error) {
    status.textContent =
      `Couldn't reach the agents — ${error.message}. The backend sleeps when idle; give it a moment and try again.`;
    status.classList.add("error");
    for (const agent of Object.keys(panels)) setState(agent, "", "waiting");
  } finally {
    goButton.disabled = false;
    input.disabled = false;
  }
}

function handle(eventName, data) {
  if (eventName === "start") {
    status.textContent = "Three specialists are working on it…";
    return;
  }

  if (eventName === "message") {
    const panel = panels[data.agent];
    if (!panel) return;
    panel.querySelector(".body").innerHTML = markdown(data.text);
    setState(data.agent, "done", "done");
    if (data.agent !== "travel_coordinator") {
      const remaining = ["flights_agent", "hotels_agent", "itinerary_agent"]
        .filter((a) => panels[a].dataset.state !== "done").length;
      status.textContent = remaining
        ? `${remaining} still working…`
        : "Writing up the plan…";
      if (!remaining) setState("travel_coordinator", "running", "writing");
    }
    return;
  }

  if (eventName === "retry") {
    status.textContent =
      `Gemini's free tier is busy. Retrying in ${data.seconds} seconds…`;
    return;
  }

  if (eventName === "error") {
    status.textContent = data.message;
    status.classList.add("error");
    for (const agent of Object.keys(panels)) {
      if (panels[agent].dataset.state !== "done") setState(agent, "", "—");
    }
    return;
  }

  if (eventName === "done") {
    status.textContent = "Done.";
    return;
  }
}

/* ---------- wiring ---------- */

goButton.addEventListener("click", plan);
input.addEventListener("keydown", (e) => { if (e.key === "Enter") plan(); });

for (const button of $("examples").querySelectorAll("button")) {
  button.addEventListener("click", () => {
    input.value = button.textContent;
    plan();
  });
}
