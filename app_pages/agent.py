"""AI Analyst — a codified-analysis agent over the measurement warehouse.

The thesis (straight from the cover letter): don't let an LLM free-write SQL or
Python. Codify the analyses, expose them as a typed menu, and let the model do
only what it's good at — reading intent and writing prose. Concretely, every
question runs the same five stages, each shown on the page:

  1. User query.
  2. Semantic layer resolves it to an intent, an analysis type, and parameters
     — the LLM's ONLY job here, constrained to enumerated, pre-approved values.
  3. That analysis maps to fixed, reviewable SQL + Python from this repo.
  4. Results come back in statistical terms (deterministic).
  5. The LLM summarizes those numbers in plain English.

If no OpenAI key is configured the page still runs end-to-end on a deterministic
keyword router + templated summary, with a banner saying so — so the flow is
legible even without a backend.
"""

import hashlib
import json

import streamlit as st

from src import agent_registry as reg, db, llm, theme, ui

ui.page_header(
    "AI Analyst",
    "Ask a measurement question in plain English. Instead of generating SQL on the "
    "fly, the agent resolves your question to one of a fixed menu of approved "
    "analyses and only selects its parameters — then runs vetted SQL/Python and "
    "summarizes the result. Consistent by construction; every stage is shown below.")

enums = reg.warehouse_enums()
schema = reg.build_tool_schema(enums)
use_llm = llm.available()

# ---------------------------------------------------------------- status banner
if use_llm:
    st.markdown(
        f"<div style='border-left:3px solid {theme.STATUS['good']}; background:#1a1a19; "
        f"padding:0.5rem 0.9rem; border-radius:4px; margin-bottom:0.6rem;'>"
        f"<span style='color:{theme.STATUS['good']}; font-weight:700;'>● LLM connected</span> "
        f"<span style='color:#c3c2b7;'>— semantic-layer routing and summarization run on "
        f"<code>{llm.model()}</code> (OpenAI). The model selects an approved analysis and "
        f"parameters and writes the summary; it never authors SQL or Python.</span></div>",
        unsafe_allow_html=True)
else:
    st.markdown(
        f"<div style='border-left:3px solid {theme.STATUS['warning']}; background:#1a1a19; "
        f"padding:0.5rem 0.9rem; border-radius:4px; margin-bottom:0.6rem;'>"
        f"<span style='color:{theme.STATUS['warning']}; font-weight:700;'>◆ Offline mode</span> "
        f"<span style='color:#c3c2b7;'>— no <code>OPENAI_API_KEY</code> found, so stages 2 and 5 "
        f"use a deterministic keyword router and a templated summary. The approved analyses "
        f"in stages 3–4 run identically either way. Add a key in Streamlit secrets to enable "
        f"the LLM.</span></div>",
        unsafe_allow_html=True)

with st.expander("How this works — and why it's built this way"):
    st.markdown(
        f"There are **{len(reg.ANALYSES)} approved analyses**. The LLM is handed the list plus "
        "the allowed parameter values (advertiser names, categories, cohorts — pulled live from "
        "the warehouse) and must return exactly one analysis and a set of those enumerated "
        "parameters via a forced function call. It has no channel to emit a query. That's the "
        "whole point: **codifying the analysis and limiting generation to pre-approved "
        "parameters trades more front-end work for consistent, auditable results.** The SQL in "
        "`sql/*.sql` and the functions in `src/analytics.py` are the same ones the rest of this "
        "console uses — reviewed once, reused everywhere.")
    st.markdown("**The approved menu:**")
    for a in reg.ANALYSES.values():
        st.markdown(f"- **{a.label}** — {a.description}")

# ---------------------------------------------------------------- input
st.session_state.setdefault("agent_query", "")

st.markdown("**Try an example, or ask your own:**")
ex_cols = st.columns(len(reg.ANALYSES))
for col, a in zip(ex_cols, reg.ANALYSES.values()):
    with col:
        example = reg.example_for(a, enums)   # entity filled from live data
        if st.button(example, use_container_width=True, key=f"ex_{a.key}"):
            st.session_state.agent_query = example
            st.rerun()

with st.form("ask"):
    q = st.text_input("Your question", value=st.session_state.agent_query,
                      placeholder="e.g. Is Coca-Cola's advertising actually working?",
                      label_visibility="collapsed")
    go = st.form_submit_button("Run analysis", type="primary")
if go:
    st.session_state.agent_query = q

active_query = st.session_state.agent_query.strip()


# ---------------------------------------------------------------- pipeline
def execute(query: str) -> dict:
    """Run the five stages once. Cached per query in session_state so toggling an
    expander (which reruns the script) never re-hits the API."""
    out = {"query": query}
    args, mode, err = None, "offline", None
    if use_llm:
        r = llm.resolve_intent(query, schema)
        if r["ok"]:
            at = r["args"].get("analysis_type")
            if at in reg.ANALYSES:
                args, mode = r["args"], "llm"
            elif at == reg.UNSUPPORTED:
                # The model deliberately declined — surface it, don't run anything.
                out.update(resolve=r["args"], resolve_mode="llm",
                           resolve_error=None, unresolved=True)
                return out
            else:
                err = "the model did not return a valid analysis"
        else:
            err = r.get("error")
    if args is None:
        args = reg.resolve_deterministic(query, enums)
        mode = "offline"
        if args["analysis_type"] == reg.UNSUPPORTED:
            out.update(resolve=args, resolve_mode="offline",
                       resolve_error=err, unresolved=True)
            return out
    out.update(resolve=args, resolve_mode=mode, resolve_error=err)

    analysis = reg.ANALYSES[args["analysis_type"]]
    params = {p: args[p] for p in analysis.params if args.get(p) is not None}
    result = analysis.run(enums, **params)
    out.update(analysis=analysis, result=result, params_used=params)

    payload = {"analysis": analysis.label, "parameters": result.bound_params,
               "headline": result.headline, "statistics": result.stats}
    s_text = f"{result.headline} {result.takeaway}"
    s_mode, s_err = "offline", None
    if use_llm:
        s = llm.summarize(payload)
        if s["ok"]:
            s_text, s_mode = s["text"], "llm"
        else:
            s_err = s["error"]
    out.update(summary=s_text, summary_mode=s_mode, summary_error=s_err)
    return out


def stage_header(n: int, title: str):
    st.markdown(
        f"<div style='display:flex; align-items:center; gap:0.6rem; margin:0.2rem 0 0.4rem;'>"
        f"<span style='background:{theme.ACCENT}; color:#fff; font-weight:800; border-radius:50%;"
        f"width:1.6rem; height:1.6rem; display:inline-flex; align-items:center; "
        f"justify-content:center; font-size:0.9rem;'>{n}</span>"
        f"<span style='font-weight:700; font-size:1.05rem; color:#fff;'>{title}</span></div>",
        unsafe_allow_html=True)


def mode_chip(mode: str) -> str:
    if mode == "llm":
        return (f"<span style='color:{theme.STATUS['good']}; font-size:0.8rem;'>"
                f"● {llm.model()}</span>")
    return (f"<span style='color:{theme.STATUS['warning']}; font-size:0.8rem;'>"
            f"◆ offline fallback</span>")


# ------------------------------------------------- unsupported-query hand-off
# When the semantic layer declines a question, it's really a feature request:
# codify a new approved analysis. We turn that into an Analytics Engineering
# ticket. (Demo stub — captured in session_state, not posted to a live Jira.)

def _ticket_payload(query: str, resolve: dict) -> dict:
    return {
        "project": "ANALYTICS",
        "issuetype": "New Measurement Analysis",
        "summary": f"Codify an approved analysis for: “{query.strip()}”",
        "components": ["Analytics Engineering", "AI Analyst"],
        "labels": ["ai-analyst", "unsupported-query", "semantic-layer"],
        "description": (
            "The AI Analyst semantic layer could not map this request to any of the "
            f"{len(reg.ANALYSES)} approved analyses and declined to run one.\n\n"
            f"Original question: {query.strip()}\n"
            f"Resolved intent: {resolve.get('intent', '—')}\n\n"
            "Action: assess whether this warrants a new codified analysis "
            "(named SQL + vetted Python + typed parameters) in the approved registry."),
    }


def _file_analytics_ticket(query: str, resolve: dict) -> dict:
    payload = _ticket_payload(query, resolve)
    n = int(hashlib.sha1(query.strip().lower().encode()).hexdigest(), 16) % 9000 + 1000
    return {"key": f"ANALYTICS-{n}", "summary": payload["summary"], "payload": payload}


if active_query:
    runs = st.session_state.setdefault("agent_runs", {})
    cache_key = f"{active_query}|{'llm' if use_llm else 'offline'}"
    if cache_key not in runs:
        with st.spinner("Resolving intent → running approved analysis → summarizing…"):
            runs[cache_key] = execute(active_query)
    r = runs[cache_key]
    args = r["resolve"]

    st.divider()

    # ---- Stage 1
    stage_header(1, "User query")
    st.markdown(
        f"<div style='background:#1a1a19; border-radius:6px; padding:0.7rem 1rem; "
        f"color:#fff; font-size:1.05rem;'>“{r['query']}”</div>", unsafe_allow_html=True)

    # ---- Stage 2
    st.write("")
    stage_header(2, "Semantic layer → intent, analysis type, parameters")
    st.markdown(mode_chip(r["resolve_mode"]), unsafe_allow_html=True)

    # The semantic layer can decline: if the question maps to none of the
    # approved analyses, we stop here rather than force an unrelated readout.
    if r.get("unresolved"):
        st.error(
            "**Out of scope — this question doesn't map to any approved analysis.**  \n"
            f"“{r['query']}” couldn't be resolved to one of the "
            f"{len(reg.ANALYSES)} measurement analyses this agent is allowed to run, so "
            "nothing was executed. This is the semantic layer working as intended: it "
            "only proceeds when it can ground a question in a pre-approved analysis.")
        st.caption("The semantic layer returned `analysis_type = \"unsupported\"` instead of "
                   "picking an analysis, so stages 3–5 were skipped.")
        st.markdown("**Try one of these instead:**")
        for a in reg.ANALYSES.values():
            st.markdown(f"- {reg.example_for(a, enums)}  ·  _{a.label}_")

        st.write("")
        st.markdown("**Need this analysis?** Hand it to Analytics Engineering to codify as a "
                    "new approved analysis — that's how the menu grows.")
        tickets = st.session_state.setdefault("agent_tickets", {})
        filed = tickets.get(r["query"])
        if filed:
            st.success(f"✅ Filed **{filed['key']}** — “{filed['summary']}” is queued for "
                       "Analytics Engineering.")
        else:
            if st.button("🎫 Open a Jira ticket for Analytics Engineering",
                         type="primary", key="jira_unresolved"):
                tickets[r["query"]] = _file_analytics_ticket(r["query"], r["resolve"])
                st.rerun()
            with st.expander("What gets sent to Analytics Engineering"):
                st.code(json.dumps(_ticket_payload(r["query"], r["resolve"]), indent=2),
                        language="json")
        st.caption("Demo stub — in this synthetic app the ticket is captured locally, not "
                   "posted to a live Jira project.")
        st.stop()

    res = r["result"]
    analysis = r["analysis"]
    if r.get("resolve_error"):
        st.warning(f"LLM routing failed ({r['resolve_error']}); fell back to the keyword router.")
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown(f"**Resolved intent:** {args.get('intent', r['query'])}")
        st.markdown(f"**Analysis type:** `{analysis.key}` — {analysis.label}")
        pretty = r["params_used"] or {"(none)": "analysis needs no parameters"}
        st.markdown("**Parameters selected:** "
                    + ", ".join(f"`{k} = {v}`" for k, v in pretty.items()))
    with c2:
        st.caption("The exact structured output the semantic layer returned "
                   "(a forced function call):")
        st.code(json.dumps(args, indent=2), language="json")
    st.caption(f"The model could only choose one of {len(reg.ANALYSES)} approved analyses and "
               "parameter values drawn from the warehouse's own advertisers, categories, and "
               "cohorts. It has no path to write a query.")

    # ---- Stage 3
    st.write("")
    stage_header(3, "Approved SQL + Python flow (fixed in the repo)")
    fns = ", ".join(f"`{f}`" for f in res.python_fns) or "—"
    st.markdown(f"This analysis binds the parameters above into pre-written code: "
                f"**SQL** {', '.join(f'`sql/{n}.sql`' for n in res.sql_names)} · "
                f"**Python** {fns}.")
    if res.notes:
        st.info(res.notes)
    for name in res.sql_names:
        with st.expander(f"⌗ sql/{name}.sql — reviewed, version-controlled, not generated"):
            st.code(db.sql_text(name), language="sql")

    # ---- Stage 4
    st.write("")
    stage_header(4, "Result (in statistical terms)")
    st.markdown(
        f"<div style='border-left:4px solid {theme.CAT[0]}; background:#1a1a19; "
        f"padding:0.7rem 1rem; border-radius:6px; color:#fff; margin-bottom:0.6rem;'>"
        f"{res.headline}</div>", unsafe_allow_html=True)
    if res.figure is not None:
        st.plotly_chart(res.figure, use_container_width=True)
    if res.table is not None:
        st.dataframe(res.table, hide_index=True, use_container_width=True,
                     column_config=res.table_config)
    with st.expander("Full statistical result (the exact numbers handed to the summarizer)"):
        st.json(res.stats)

    # ---- Stage 5
    st.write("")
    stage_header(5, "Plain-English summary")
    st.markdown(mode_chip(r["summary_mode"]), unsafe_allow_html=True)
    if r.get("summary_error"):
        st.warning(f"LLM summary failed ({r['summary_error']}); used the templated readout.")
    st.markdown(
        f"<div style='border-left:4px solid {theme.ACCENT}; background:#1a1a19; "
        f"padding:0.9rem 1.15rem; border-radius:6px; color:#fff; font-size:1.03rem; "
        f"line-height:1.55;'>{r['summary']}</div>", unsafe_allow_html=True)
    st.caption("Generated strictly from the Stage 4 numbers — the summarizer is instructed to "
               "use only those figures, never to invent or extrapolate.")
else:
    st.info("Ask a question above, or click an example, to see the five-stage flow.")
