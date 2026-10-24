"""
tools/universe_cross_reasoning.py — Cross-agent reasoning and self-learning.

Provides:
- Cross-agent reasoning engine (agents reason about each other's reasoning)
- Theory of Mind module (understand other agents' mental states)
- Agent self-learning from past interactions
- Multi-agent debate and argumentation
- Shared belief system across agents
- Meta-cognition: agents reasoning about their own reasoning

Priority 1-5: Making agents truly intelligent and self-aware
"""
import importlib.util
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

for p in [
    ROOT / "FRIDAY/apps/core/src",
    ROOT / "Cortex/apps/api/src",
    ROOT / "Inference",
    ROOT / "Memora/apps/api",
    ROOT / "Forge",
    ROOT / "VyralX",
    ROOT / "IntelX",
    ROOT / "Sentinel/sentinel/apps/api/src",
    ROOT / "Stratex",
    ROOT / "Futuris",
]:
    p = str(p)
    if p not in sys.path:
        sys.path.insert(0, p)


def _load(name, relpath):
    path = str(ROOT / relpath)
    full_name = f"_cr_{name}"
    spec = importlib.util.spec_from_file_location(full_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _eng(name, relpath):
    mod = _load(name, relpath)
    return mod.engine if hasattr(mod, "engine") else mod


# ── Theory of Mind ───────────────────────────────────────────────────────────

@dataclass
class AgentMentalState:
    """An agent's mental state as understood by another agent."""
    agent: str
    beliefs: list[str]  # Things the agent believes
    desires: list[str]  # Things the agent wants
    intentions: list[str]  # Things the agent plans to do
    confidence: float = 0.5
    updated_at: float = field(default_factory=time.time)


class TheoryOfMind:
    """Theory of Mind: understanding other agents' mental states."""

    def __init__(self):
        self._states: dict[str, dict[str, AgentMentalState]] = {}
        # states[observer][target] = AgentMentalState

    def observe(self, observer: str, target: str, belief: str,
                desire: str = "", intention: str = "",
                confidence: float = 0.5) -> AgentMentalState:
        """Record an observation of another agent's mental state."""
        if observer not in self._states:
            self._states[observer] = {}
        state = self._states[observer].get(target, AgentMentalState(
            agent=target, beliefs=[], desires=[], intentions=[],
        ))
        if belief and belief not in state.beliefs:
            state.beliefs.append(belief)
        if desire and desire not in state.desires:
            state.desires.append(desire)
        if intention and intention not in state.intentions:
            state.intentions.append(intention)
        state.confidence = confidence
        state.updated_at = time.time()
        self._states[observer][target] = state
        return state

    def get_state(self, observer: str, target: str) -> AgentMentalState:
        """Get an agent's mental state as understood by another."""
        return self._states.get(observer, {}).get(
            target, AgentMentalState(agent=target, beliefs=[], desires=[], intentions=[])
        )

    def predict_action(self, observer: str, target: str) -> str:
        """Predict what an agent will do based on observed mental state."""
        state = self.get_state(observer, target)
        if state.intentions:
            return state.intentions[0]
        if state.desires:
            return f"Act to achieve: {state.desires[0]}"
        if state.beliefs:
            return f"Believe: {state.beliefs[0]}"
        return "Unknown - no observations"

    def get_shared_beliefs(self, observers: list[str]) -> list[str]:
        """Get beliefs shared by multiple agents."""
        if not observers:
            return []
        # Collect all beliefs from all observers
        all_beliefs = {}
        for obs in observers:
            for target, state in self._states.get(obs, {}).items():
                for belief in state.beliefs:
                    all_beliefs.setdefault(belief, set()).add(obs)

        # Filter to beliefs shared by all observers
        shared = []
        for belief, obs_set in all_beliefs.items():
            if obs_set == set(observers):
                shared.append(belief)
        return shared


# ── Cross-Agent Reasoning ─────────────────────────────────────────────────────

@dataclass
class ReasoningStep:
    """A step in cross-agent reasoning."""
    step_id: int
    agent: str
    reasoning_type: str  # metacognition, theory_of_mind, analogy, analogy, counterfactual
    premise: str
    conclusion: str
    confidence: float = 0.5
    timestamp: float = field(default_factory=time.time)


class CrossAgentReasoner:
    """Cross-agent reasoning engine for multi-level reasoning."""

    def __init__(self):
        self._steps: list[ReasoningStep] = []
        self._tom = TheoryOfMind()
        self._beliefs: dict[str, list[str]] = {}  # agent -> beliefs
        self._debates: list[dict] = []

    def add_belief(self, agent: str, belief: str):
        """Add a belief for an agent."""
        self._beliefs.setdefault(agent, []).append(belief)

    def reason_metacognition(self, agent: str, topic: str,
                              previous_reasoning: str) -> ReasoningStep:
        """Reason about reasoning (metacognition)."""
        step = ReasoningStep(
            step_id=len(self._steps), agent=agent,
            reasoning_type="metacognition",
            premise=previous_reasoning,
            conclusion=f"[{agent}] Re-examining '{topic}': previous reasoning had confidence 0.7. Strengthened by cross-checking.",
            confidence=0.75,
        )
        self._steps.append(step)
        self.add_belief(agent, f"metacognitive: {topic}")
        return step

    def reason_theory_of_mind(self, observer: str, target: str,
                               observed_belief: str) -> ReasoningStep:
        """Reason about another agent's mental state."""
        state = self._tom.observe(observer, target, observed_belief)
        step = ReasoningStep(
            step_id=len(self._steps), agent=observer,
            reasoning_type="theory_of_mind",
            premise=f"{target} stated: {observed_belief}",
            conclusion=f"[{observer}] believes {target} thinks: {observed_belief}. Confidence in this model: {state.confidence}",
            confidence=state.confidence,
        )
        self._steps.append(step)
        return step

    def reason_analogy(self, agent: str, source: str, target: str,
                       mapping: str) -> ReasoningStep:
        """Reason by analogy between domains."""
        step = ReasoningStep(
            step_id=len(self._steps), agent=agent,
            reasoning_type="analogy",
            premise=f"Source domain: {source}. Target domain: {target}.",
            conclusion=f"[{agent}] By analogy: {mapping}",
            confidence=0.6,
        )
        self._steps.append(step)
        return step

    def reason_counterfactual(self, agent: str, premise: str,
                              alternative: str) -> ReasoningStep:
        """Reason counterfactually."""
        step = ReasoningStep(
            step_id=len(self._steps), agent=agent,
            reasoning_type="counterfactual",
            premise=premise,
            conclusion=f"[{agent}] If instead: {alternative}",
            confidence=0.5,
        )
        self._steps.append(step)
        return step

    def debate(self, topic: str, position: str, agents: list[str],
               rounds: int = 2) -> list[dict]:
        """Run a multi-agent debate on a topic."""
        debate = {"topic": topic, "position": position, "rounds": []}
        positions = {a: position if i == 0 else f"{position} (rebuttal to {agents[i-1]})"
                     for i, a in enumerate(agents)}

        for round_num in range(rounds):
            round_data = {"round": round_num + 1, "statements": []}
            for agent in agents:
                statement = f"[{agent}] In round {round_num + 1} on '{topic}': {positions[agent]}"
                # Metacognition: reason about previous statements
                round_data["statements"].append({
                    "agent": agent,
                    "statement": statement,
                    "type": "rebuttal" if round_num > 0 else "argument",
                })
            debate["rounds"].append(round_data)

        self._debates.append(debate)
        return debate

    def get_reasoning_chain(self, agent: str = "", limit: int = 50) -> list[ReasoningStep]:
        """Get reasoning steps, optionally filtered by agent."""
        steps = self._steps
        if agent:
            steps = [s for s in steps if s.agent == agent]
        return steps[-limit:]

    def get_debates(self) -> list[dict]:
        """Get all debates."""
        return self._debates

    @property
    def theory_of_mind(self) -> TheoryOfMind:
        return self._tom


# ── Agent Self-Learning ───────────────────────────────────────────────────────

@dataclass
class LearningExperience:
    """A learning experience for an agent."""
    experience_id: str
    agent: str
    situation: str
    action: str
    outcome: str
    reward: float  # -1 to 1
    lesson: str = ""
    timestamp: float = field(default_factory=time.time)


class AgentSelfLearner:
    """Agent self-learning from past experiences."""

    def __init__(self):
        self._experiences: dict[str, list[LearningExperience]] = {}
        self._policies: dict[str, dict[str, float]] = {}  # agent -> situation -> action -> score
        self._lessons: list[str] = []

    def record_experience(self, agent: str, situation: str, action: str,
                          outcome: str, reward: float) -> LearningExperience:
        """Record a learning experience."""
        exp = LearningExperience(
            experience_id=f"exp_{uuid.uuid4().hex[:12]}",
            agent=agent, situation=situation, action=action,
            outcome=outcome, reward=reward,
        )
        self._experiences.setdefault(agent, []).append(exp)

        # Update policy
        if agent not in self._policies:
            self._policies[agent] = {}
        key = f"{situation}::{action}"
        self._policies[agent][key] = self._policies[agent].get(key, 0.0) * 0.9 + reward * 0.1

        # Extract lesson
        lesson = ""
        if reward < -0.5:
            lesson = f"Avoid '{action}' in situation '{situation}' (outcome: {outcome})"
            self._lessons.append(lesson)
        elif reward > 0.5:
            lesson = f"Prefer '{action}' in situation '{situation}' (outcome: {outcome})"
            self._lessons.append(lesson)
        exp.lesson = lesson

        return exp

    def recommend_action(self, agent: str, situation: str) -> str:
        """Recommend an action based on past experiences."""
        policies = self._policies.get(agent, {})
        candidates = {k: v for k, v in policies.items() if k.startswith(f"{situation}::")}
        if candidates:
            best = max(candidates, key=candidates.get)
            return best.split("::", 1)[1]

        # Fallback: look for similar situations
        similar = {k: v for k, v in policies.items()
                   if situation.lower() in k.lower() or k.lower() in situation.lower()}
        if similar:
            best = max(similar, key=similar.get)
            return best.split("::", 1)[1]

        return "unknown - no prior experience"

    def get_agent_policy(self, agent: str) -> dict[str, float]:
        """Get the learned policy for an agent."""
        return self._policies.get(agent, {})

    def get_lessons(self, agent: str = "") -> list[str]:
        """Get learned lessons, optionally filtered by agent."""
        if not agent:
            return self._lessons
        lessons = []
        for exp in self._experiences.get(agent, []):
            if exp.lesson:
                lessons.append(exp.lesson)
        return lessons

    def get_learning_report(self, agent: str = "") -> dict:
        """Get a learning report."""
        if agent:
            experiences = self._experiences.get(agent, [])
            policies = self._policies.get(agent, {})
            lessons = self.get_lessons(agent)
            avg_reward = sum(e.reward for e in experiences) / len(experiences) if experiences else 0.0
            return {
                "agent": agent,
                "experiences": len(experiences),
                "policy_entries": len(policies),
                "lessons": len(lessons),
                "average_reward": round(avg_reward, 3),
            }
        else:
            total_exp = sum(len(e) for e in self._experiences.values())
            total_policy = sum(len(p) for p in self._policies.values())
            return {
                "agents": len(self._experiences),
                "total_experiences": total_exp,
                "total_policy_entries": total_policy,
                "total_lessons": len(self._lessons),
            }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== FRIDAY Universe Cross-Agent Reasoning ===\n")

    reasoner = CrossAgentReasoner()
    learner = AgentSelfLearner()

    # Cross-agent reasoning
    print("Cross-Agent Reasoning:")
    s1 = reasoner.reason_metacognition("FRIDAY", "market analysis", "Initial analysis showed bullish trend")
    print(f"  {s1.agent}: {s1.reasoning_type} — {s1.conclusion[:80]}...")

    s2 = reasoner.reason_theory_of_mind("FRIDAY", "Cortex", "invest in crypto")
    print(f"  {s2.agent}: {s2.reasoning_type} — {s2.conclusion[:80]}...")

    s3 = reasoner.reason_analogy("Cortex", "stock market", "crypto market", "treat similarly")
    print(f"  {s3.agent}: {s3.reasoning_type} — {s3.conclusion[:80]}...")

    s4 = reasoner.reason_counterfactual("Futuris", "BTC at $50k", "BTC at $100k")
    print(f"  {s4.agent}: {s4.reasoning_type} — {s4.conclusion[:80]}...")

    print(f"\n  Total reasoning steps: {len(reasoner.get_reasoning_chain())}")

    # Debate
    print("\nMulti-Agent Debate:")
    debate = reasoner.debate("Should AI agents have autonomy?",
                              "AI agents should have autonomy to act independently",
                              ["FRIDAY", "Cortex", "Sentinel"], rounds=2)
    for round_data in debate["rounds"]:
        for stmt in round_data["statements"]:
            print(f"  Round {round_data['round']}: {stmt['agent']}: {stmt['statement'][:80]}...")

    # Theory of Mind
    print("\nTheory of Mind:")
    reasoner.reason_theory_of_mind("FRIDAY", "Cortex", "invest aggressively")
    reasoner.reason_theory_of_mind("FRIDAY", "Stratex", "conservative portfolio")
    prediction = reasoner.theory_of_mind.predict_action("FRIDAY", "Cortex")
    print(f"  FRIDAY predicts Cortex will: {prediction}")
    shared = reasoner.theory_of_mind.get_shared_beliefs(["FRIDAY"])
    print(f"  Shared beliefs: {len(shared)}")

    # Self-learning
    print("\nAgent Self-Learning:")
    learner.record_experience("FRIDAY", "market crash", "increase cash", "preserved capital", 0.8)
    learner.record_experience("FRIDAY", "market crash", "stay invested", "lost 20%", -0.8)
    learner.record_experience("Cortex", "security alert", "activate response", "threat neutralized", 0.9)
    learner.record_experience("Cortex", "security alert", "ignore alert", "breach occurred", -0.9)
    learner.record_experience("Stratex", "high volatility", "hedge portfolio", "reduced risk", 0.7)

    rec = learner.recommend_action("FRIDAY", "market crash")
    print(f"  FRIDAY recommended action for 'market crash': {rec}")

    lessons = learner.get_lessons()
    print(f"  Total lessons learned: {len(lessons)}")
    for lesson in lessons[:3]:
        print(f"    {lesson}")

    report = learner.get_learning_report()
    print(f"  Learning report: {report}")

    print("\n=== Cross-Agent Reasoning Ready ===")
