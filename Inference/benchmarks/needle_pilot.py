"""TASK-IG-INF-04 needle pilot: run cactus-compute's Needle tool-calling
agent on this machine and record raw evidence (construction time,
per-prompt latency, peak RSS, raw run() results) to a JSON file.
Scoring happens afterwards, from the recorded raw results.
"""

import json
import resource
import sys
import time

import cactus


def rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


@cactus.tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return f"Sunny in {city}"


@cactus.tool
def set_reminder(text: str, minutes: int) -> str:
    """Set a reminder for some minutes from now."""
    return f"Reminder set: {text} in {minutes} minutes"


@cactus.tool
def search_memory(query: str) -> str:
    """Search the user's stored memory notes for a query."""
    return f"3 notes match {query}"


PROMPTS = [
    "What's the weather in Mumbai?",
    "Remind me to call the bank in 20 minutes",
    "Search my memory for the Oracle server notes",
    "What is the capital of France?",
    "Will it rain in Delhi tomorrow?",
    "Set a reminder for the eggs in 5 minutes",
    "Find what I noted about the voice latency problem",
    "Tell me a one-line joke",
]


def main():
    out = {"stages": {}, "runs": []}
    t0 = time.time()
    agent = cactus.Needle(
        tools=[get_weather, set_reminder, search_memory],
        system="You are FRIDAY, a helpful assistant.",
    )
    out["stages"]["construct_s"] = round(time.time() - t0, 2)
    out["stages"]["rss_after_construct_mb"] = round(rss_mb(), 1)
    for prompt in PROMPTS:
        t0 = time.time()
        try:
            res = agent.run(prompt)
            err = None
        except Exception as exc:
            res, err = None, f"{exc.__class__.__name__}: {exc}"
        out["runs"].append(
            {
                "prompt": prompt,
                "latency_s": round(time.time() - t0, 2),
                "error": err,
                "result": res,
            }
        )
        print(f"done: {prompt[:40]!r} ({out['runs'][-1]['latency_s']}s)", flush=True)
    out["stages"]["rss_final_mb"] = round(rss_mb(), 1)
    agent.close()
    path = sys.argv[1] if len(sys.argv) > 1 else "needle_pilot_results.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("wrote", path)


if __name__ == "__main__":
    main()
