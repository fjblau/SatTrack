import json
import logging
from typing import Any, Optional, TypedDict

from config import config

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an expert orbital mechanics mission planner advising on Kestrel — a satellite inspection, servicing, and active debris removal (ADR) spacecraft.

You will receive:
1. The target object's orbital elements and name
2. Kestrel's planned parking orbit elements
3. Four pre-computed maneuver scenarios, each with exact physics-based parameters (ΔV, transfer time, wait time)
4. The mission type (observation, inspection, servicing, or deorbit/ADR)
5. Optional constraints from the operator (ΔV budget, time urgency, other preferences)

Your task: analyze the scenarios and recommend the BEST one for the specific situation, with a concise explanation.

## The Four Scenarios

**Hohmann Transfer (OPTIMAL tag)** — two-burn minimum-energy coplanar transfer. Lowest ΔV of any coplanar maneuver. Requires waiting for correct phase alignment. Best when fuel efficiency is the priority.

**Fast Intercept (FAST tag)** — overshoot/undershoot transfer orbit that reaches the target altitude earlier. ~20-50% faster, but uses more ΔV (typically 10-50% more). Best when time is critical.

**Phased Rendezvous (NEXT WINDOW tag)** — identical burns to Hohmann, but executed at the *next* optimal alignment window (one synodic period later). Same ΔV as Hohmann. Best if the primary window was missed or Kestrel is not ready for the current window.

**J2 RAAN Alignment (LOW ΔV tag)** — only appears when there is a significant RAAN difference (> 1°) between Kestrel and the target. Uses Earth's J2 oblateness perturbation to passively drift RAAN into alignment before executing a Hohmann. No costly plane-change burn — but can take days to weeks. Best when the RAAN offset is large and time is not critical. Only appears when applicable.

## Decision Framework

Use this reasoning process:

1. **RAAN difference**: If J2 RAAN Alignment is available and the RAAN gap is large (>5°), it is usually the right choice *unless* time is urgent. Plane-change burns are extremely expensive.

2. **Altitude difference**: Large altitude gaps favor Hohmann (big ΔV savings over Fast). Small gaps make Fast Intercept more attractive.

3. **Mission type context**:
   - *Observation/Inspection*: fuel efficiency matters (satellite needs to return or loiter); prefer Hohmann or J2.
   - *Servicing*: client may be in distress — prefer Fast Intercept if time-sensitive.
   - *Deorbit/ADR*: fuel needed for the deorbit burn too — be conservative, prefer Hohmann or J2 to reserve ΔV.

4. **Constraints**: If operator specifies ΔV budget or time limit, filter scenarios that violate them first.

5. **Wait time**: Very long waits (>30 days) for J2 alignment may be unacceptable operationally — flag this.

## Output Format

Respond with a JSON object, no other text:
{
  "recommended_scenario_id": "<one of: hohmann | fast | phased | j2raan>",
  "reasoning": "<2-4 sentences explaining WHY this scenario was chosen over the others, referencing the specific numbers>",
  "trade_off_summary": "<one sentence describing the main trade-off the operator is accepting>",
  "caveats": "<optional: any important warnings, e.g. 'wait time is 23 days — verify Kestrel propellant budget allows for extended loiter'>",
  "confidence": "<high | medium | low>"
}

If a clarifying question would significantly change the recommendation, instead respond:
{
  "needs_clarification": true,
  "clarifying_question": "<one short, specific question>"
}
"""

_CLARIFY_PROMPT = """You are a mission planning assistant. You will receive orbital mechanics data for a satellite rendezvous mission.

Determine whether you need one key piece of information from the operator before recommending a maneuver scenario.

Only ask for clarification if:
- The ΔV budget is unknown AND there is a large spread in ΔV between scenarios (>100 m/s difference)
- The time constraint is unknown AND there is a large spread in total mission time between scenarios (>10 days difference)
- The mission type is ambiguous in a way that changes the recommendation

Do NOT ask for clarification if:
- One scenario is clearly dominant (lowest ΔV AND shortest time)
- The mission type is already specified
- The difference between scenarios is small

Respond with JSON only:
{"needs_clarification": false}
or
{"needs_clarification": true, "clarifying_question": "<one short question>"}
"""


class _State(TypedDict):
    mission_context: dict
    clarification: str
    clarifying_question: str
    recommended_scenario_id: str
    reasoning: str
    trade_off_summary: str
    caveats: str
    confidence: str
    error: str


_llm = None


def initialize_kestrel_agent() -> None:
    global _llm
    if not config.agent.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set — Kestrel mission advisor will be unavailable.")
        return
    try:
        from langchain_openai import ChatOpenAI
        _llm = ChatOpenAI(
            model=config.agent.MODEL,
            api_key=config.agent.OPENAI_API_KEY,
            temperature=0,
        )
        logger.info("Kestrel mission advisor initialized with model '%s'.", config.agent.MODEL)
    except Exception as exc:
        logger.error("Failed to initialize Kestrel agent: %s", exc, exc_info=True)


def is_ready() -> bool:
    return _llm is not None


def _parse_llm_response(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:])
        if content.rstrip().endswith("```"):
            content = content.rstrip()[:-3]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"error": f"Could not parse LLM response: {content[:200]}"}


def _build_mission_prompt(ctx: dict) -> str:
    target = ctx.get("target", {})
    kestrel = ctx.get("kestrel", {})
    scenarios = ctx.get("scenarios", [])
    mission_type = ctx.get("mission_type", "observation")
    constraints = ctx.get("constraints", "")

    scenario_lines = []
    for sc in scenarios:
        dv_km = sc.get("dvTotal", 0) / 1000
        wait_h = sc.get("waitTime", 0) / 3600
        transfer_h = sc.get("transferTime", 0) / 3600
        line = (
            f"  [{sc.get('tag', sc.get('id', '?'))}] {sc.get('name', '?')}: "
            f"ΔV_total={dv_km:.3f} km/s  ΔV₁={sc.get('dv1', 0)/1000:.3f} km/s  ΔV₂={sc.get('dv2', 0)/1000:.3f} km/s  "
            f"transfer={transfer_h:.1f} h  wait={wait_h:.1f} h"
        )
        if sc.get("driftAltKm"):
            line += f"  drift_orbit={sc['driftAltKm']} km"
        if sc.get("dRaanDeg"):
            line += f"  RAAN_gap={sc['dRaanDeg']:.1f}°"
        scenario_lines.append(line)

    raan_diff = abs(
        (float(target.get("raan_deg", 0)) - float(kestrel.get("raan_deg", 0)) + 540) % 360 - 180
    )

    prompt = f"""## Mission Context

Target: {target.get('name', 'Unknown')}
  Altitude: {target.get('alt_km', '?')} km
  Inclination: {target.get('inc_deg', '?')}°
  RAAN: {target.get('raan_deg', '?')}°

Kestrel parking orbit:
  Altitude: {kestrel.get('alt_km', '?')} km
  Inclination: {kestrel.get('inc_deg', '?')}°
  RAAN: {kestrel.get('raan_deg', '?')}°
  RAAN difference from target: {raan_diff:.1f}°

Mission type: {mission_type}

Altitude difference: {abs(float(target.get('alt_km', 0)) - float(kestrel.get('alt_km', 0))):.0f} km

## Available Scenarios

{chr(10).join(scenario_lines)}

## Operator Constraints / Preferences

{constraints if constraints else 'None specified.'}
"""
    return prompt


def run_kestrel_advisor(
    mission_context: dict,
    clarification: str = "",
) -> dict[str, Any]:
    if _llm is None:
        return {
            "recommended_scenario_id": "",
            "reasoning": "",
            "trade_off_summary": "",
            "caveats": "",
            "confidence": "",
            "error": "Mission advisor unavailable. Ensure OPENAI_API_KEY is set.",
            "clarifying_question": "",
        }

    from langchain_core.messages import HumanMessage, SystemMessage

    prompt = _build_mission_prompt(mission_context)

    # Step 1: check if clarification needed (skip if already provided)
    if not clarification:
        clarify_resp = _llm.invoke([
            SystemMessage(content=_CLARIFY_PROMPT),
            HumanMessage(content=prompt),
        ])
        clarify_parsed = _parse_llm_response(clarify_resp.content)
        if clarify_parsed.get("needs_clarification"):
            return {
                "recommended_scenario_id": "",
                "reasoning": "",
                "trade_off_summary": "",
                "caveats": "",
                "confidence": "",
                "error": "",
                "clarifying_question": clarify_parsed.get("clarifying_question", ""),
            }

    # Step 2: generate recommendation
    full_prompt = prompt
    if clarification:
        full_prompt += f"\n\nOperator clarification: {clarification}"

    rec_resp = _llm.invoke([
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=full_prompt),
    ])
    parsed = _parse_llm_response(rec_resp.content)

    if parsed.get("needs_clarification"):
        return {
            "recommended_scenario_id": "",
            "reasoning": "",
            "trade_off_summary": "",
            "caveats": "",
            "confidence": "",
            "error": "",
            "clarifying_question": parsed.get("clarifying_question", ""),
        }

    return {
        "recommended_scenario_id": parsed.get("recommended_scenario_id", ""),
        "reasoning": parsed.get("reasoning", ""),
        "trade_off_summary": parsed.get("trade_off_summary", ""),
        "caveats": parsed.get("caveats", ""),
        "confidence": parsed.get("confidence", ""),
        "error": parsed.get("error", ""),
        "clarifying_question": "",
    }
