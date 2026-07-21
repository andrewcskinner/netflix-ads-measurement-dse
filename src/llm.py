"""OpenAI wiring for the AI Analyst page.

The LLM does exactly two jobs and nothing else:

1. **Semantic-layer resolution** (`resolve_intent`) — a single forced
   function call that maps a natural-language question onto ONE approved
   analysis and a set of *enumerated, pre-validated* parameters. The model
   physically cannot emit SQL or Python here; its only degrees of freedom are
   which approved analysis to run and which allowed parameter values to pass.
2. **Summarization** (`summarize`) — turns the numbers the deterministic layer
   already computed into a plain-English readout, grounded on those numbers.

Everything between those two steps — the SQL, the statistics — is codified
Python that the model never touches. If no API key is configured the page still
works: `available()` returns False and the page falls back to a deterministic
keyword router + templated summary (see agent_registry), with a visible banner.

Key lookup order: Streamlit secrets, then environment. Several spellings are
accepted so it "just works" regardless of how the key was named.
"""

from __future__ import annotations

import json
import os

import streamlit as st

MODEL_DEFAULT = "gpt-4o-mini"
_KEY_NAMES = ("OPENAI_API_KEY", "OPENAI_APIKEY", "OPENAI_apikey", "OPENAI_KEY")
_MODEL_NAMES = ("OPENAI_MODEL", "OPENAI_model")


def _from_secrets(name: str):
    try:
        return st.secrets.get(name)
    except Exception:
        return None


def api_key() -> str | None:
    for n in _KEY_NAMES:
        v = _from_secrets(n) or os.environ.get(n)
        if v:
            return str(v).strip()
    return None


def model() -> str:
    for n in _MODEL_NAMES:
        v = _from_secrets(n) or os.environ.get(n)
        if v:
            return str(v).strip()
    return MODEL_DEFAULT


def _sdk_importable() -> bool:
    try:
        import openai  # noqa: F401
        return True
    except Exception:
        return False


def available() -> bool:
    """True when both an API key and the openai SDK are present."""
    return bool(api_key()) and _sdk_importable()


def _client():
    from openai import OpenAI
    return OpenAI(api_key=api_key())


# --------------------------------------------------------------- stage 2

def resolve_intent(query: str, tool_schema: dict) -> dict:
    """Force one call to the `run_measurement_analysis` tool and return its
    arguments as a dict. The tool schema (built from the approved registry)
    constrains analysis_type and every parameter to enumerated values, so the
    model selects — it does not author.

    Returns {"ok": True, "args": {...}} or {"ok": False, "error": str}.
    """
    system = (
        "You are the semantic layer of a business-intelligence system for a "
        "streaming ad platform. Map the user's question onto EXACTLY ONE approved "
        "analysis by calling `run_measurement_analysis`. You may only choose from "
        "the enumerated analysis_type values and the enumerated parameter values in "
        "the schema. You never write SQL, Python, or free-form values. If a "
        "parameter is not relevant to the chosen analysis, omit it. Restate the "
        "user's intent in one plain sentence in the `intent` field."
    )
    try:
        resp = _client().chat.completions.create(
            model=model(),
            temperature=0,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": query}],
            tools=[tool_schema],
            tool_choice={"type": "function",
                         "function": {"name": tool_schema["function"]["name"]}},
        )
        call = resp.choices[0].message.tool_calls[0]
        return {"ok": True, "args": json.loads(call.function.arguments),
                "model": resp.model}
    except Exception as e:  # network, auth, quota, malformed args
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# --------------------------------------------------------------- stage 5

def summarize(payload: dict) -> dict:
    """Plain-English readout grounded strictly on pre-computed numbers.

    `payload` carries the analysis label, the resolved parameters, and the
    statistical result dict. Returns {"ok": True, "text": str} or an error.
    """
    system = (
        "You are a measurement analyst writing a short readout for a business "
        "stakeholder. Use ONLY the numbers in the JSON provided — never invent or "
        "extrapolate figures. Write 2-4 sentences, plain English, decision-oriented: "
        "say what the result is and what to do about it. No preamble, no bullet lists."
    )
    try:
        resp = _client().chat.completions.create(
            model=model(),
            temperature=0.3,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": json.dumps(payload, default=str)}],
        )
        return {"ok": True, "text": resp.choices[0].message.content.strip()}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
