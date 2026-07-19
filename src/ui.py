"""Small shared UI helpers."""

import streamlit as st

from src import theme


def kpi_row(items: list[tuple]):
    """items: (label, value, delta_or_None)"""
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        label, value, delta = (item + (None,))[:3]
        with col:
            st.metric(label, value, delta)


def status_chip(fill: float) -> str:
    label, color, icon = theme.status_for_fill(fill)
    return f"{icon} {label}"


def page_header(title: str, blurb: str):
    st.title(title)
    st.markdown(f"<p style='color:#c3c2b7; margin-top:-0.5rem;'>{blurb}</p>",
                unsafe_allow_html=True)
