"""Welcome — the candidate statement that frames this whole application.

The opening note, the approach to AI-for-BI, and the approach to auction
environments are the source material the rest of the console was built around
(the AI Analyst page implements the five-stage flow described here verbatim).
"""

import streamlit as st

from src import ui

ui.page_header(
    "Welcome",
    "Why this application exists, and how it connects to the Analytics Engineer 5 — "
    "Ads Measurement DSE role.")

st.markdown(
    "<div style='border-left:3px solid #E50914; padding:0.2rem 0 0.2rem 1rem; "
    "color:#c3c2b7; font-size:1.02rem; line-height:1.6;'>"
    "I write this as a man in progress; I am still reading, still experimenting, "
    "still growing. I will at times come up short and will take those opportunities "
    "to improve. I have pushed the limits of the start-up organizations that I have "
    "been a part of. I submit this application hoping to join a world-class team, "
    "because I am ready to contribute to world-class ideas."
    "</div>",
    unsafe_allow_html=True)

st.markdown(
    "This web app expresses a portion of the knowledge that I have gained, concepts "
    "that I have implemented, and positions that I currently hold — and connects these "
    "to my inferences about the responsibilities of the **Analytics Engineer 5 — Ads "
    "Measurement DSE** position.")

st.divider()

st.subheader("Approach to AI for BI")
st.markdown(
    "I reserve the right to change my opinion, but I have found lately that codifying "
    "analysis and limiting SQL/Python generation to pre-approved parameters generates "
    "the most consistent quality and the highest level of adaptability. This results in "
    "more work on the front end and a better business result on the back end. In practice "
    "this looks like:")
st.markdown(
    "1. **User query.**\n"
    "2. Query resolves in the **semantic layer** to intent, analysis type(s), and "
    "parameter selection.\n"
    "3. Analysis type(s) relate to **approved SQL and Python flows**, with input "
    "parameters (e.g. date range, entity selection).\n"
    "4. **Result(s) returned in statistical terms.**\n"
    "5. **LLM summarization** of the returned results.")
st.info("You can see a mock-up of this in the **AI Analyst** pane of the app "
        "(not connected to an LLM backend).", icon="🤖")

st.divider()

st.subheader("Approach to Auction Environments")
st.markdown(
    "One of my favorite metrics is **Inventory Buyer Density**. I'm marrying a few terms "
    "here. Not all inventory is created equal: some inventory gets a lot of buyers, some "
    "gets a few, some gets none. In a Vickrey auction the expected revenue of the seller "
    "can be described as:")

st.latex(r"E\!\left[V_{(n-1)}\right] = \frac{n-1}{n+1}")
st.caption("Katsov, 2018, p. 72, Equation 2.138")
st.markdown(
    "- $E[\\cdot]$ is the expected value of the inventory.\n"
    "- $V_{(n-1)}$ is the second-highest value.\n"
    "- $n$ is the number of bidders.")

st.markdown(
    "More independent bidders increases the expected second-highest bid and thereby "
    "increases the seller's expected revenue (Katsov, 2018, p. 72). Because this occurs on "
    "each piece of inventory, one of the main goals as a seller in this environment is to "
    "increase the number of independent bidders on each piece of inventory. This involves "
    "first determining the **buyer density** of each piece of inventory. For ease of "
    "explainability in this app, I have represented this concept in terms of inventory "
    "cohorts, with the **sell-through rate** being a ratio of a boolean (sale or no sale). "
    "I'd imagine that each campaign really has an audience target, but the same concept "
    "applies.")

st.markdown(
    "As the system matures, the constraints will change and the KPIs will change. For now, "
    "**inventory buyer density** and **ghost ads** (Johnson, Lewis, & Nubbemeyer) might be "
    "the best way to view the system; in the future it might be about applying recent "
    "advances such as **PIE** (Gordon, Moakler, & Zettelmeyer). I'm ready to grow with the "
    "system.")

with st.expander("References"):
    st.markdown(
        "- Katsov, I. (2018). *Introduction to algorithmic marketing: Artificial "
        "intelligence for marketing operations.* "
        "[PDF](https://storage.googleapis.com/algorithmic-marketing-book/"
        "algorithmic-marketing-ai-for-marketing-operations-r1.8ga.pdf)\n"
        "- Johnson, G. A., Lewis, R. A., & Nubbemeyer, E. I. (2015, May 20). "
        "*A revolution in measuring ad effectiveness: Knowing who would have been exposed.* "
        "Think with Google. "
        "[Link](https://business.google.com/in/think/marketing-strategies/"
        "a-revolution-in-measuring-ad-effectiveness/)\n"
        "- Gordon, B. R., Moakler, R., & Zettelmeyer, F. (2026). *Predicted incrementality "
        "by experimentation (PIE) for ad measurement* (NBER Working Paper No. 35044). "
        "National Bureau of Economic Research. "
        "[https://doi.org/10.3386/w35044](https://doi.org/10.3386/w35044)")
