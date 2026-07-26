"""Hard username/password gate.

Credentials are read from Streamlit secrets (AUTH_USERNAME /
AUTH_PASSWORD_SHA256). No password is baked into the repo: if
AUTH_PASSWORD_SHA256 is not configured, every login attempt is rejected.
Set the hash in .streamlit/secrets.toml (gitignored) locally, or in the
Streamlit Cloud "Secrets" UI when deploying.
"""

import hashlib
import hmac

import streamlit as st

_DEFAULT_USER = "netflix"


def _expected() -> tuple[str, str | None]:
    """Return (username, password_sha256) from secrets.

    The password hash is never stored in the repo. When it is absent the
    hash is None and no credentials can match.
    """
    try:
        return (st.secrets.get("AUTH_USERNAME", _DEFAULT_USER),
                st.secrets.get("AUTH_PASSWORD_SHA256"))
    except Exception:
        return _DEFAULT_USER, None


def _is_configured() -> bool:
    return bool(_expected()[1])


def _check(user: str, password: str) -> bool:
    exp_user, exp_hash = _expected()
    if not exp_hash:
        return False
    got = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(user.strip().lower(), exp_user.lower()) and \
        hmac.compare_digest(got, exp_hash.lower())


def require_login() -> bool:
    """Render the login wall. Returns True once authenticated."""
    if st.session_state.get("authed"):
        return True

    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown(
            "<div style='text-align:center; padding-top:14vh;'>"
            "<div style='font-size:2.1rem; font-weight:800; color:#E50914; letter-spacing:0.5px;'>ADS MEASUREMENT</div>"
            "<div style='color:#898781; margin-bottom:1.4rem;'>Internal console · synthetic data demo</div>"
            "</div>", unsafe_allow_html=True)
        with st.form("login", clear_on_submit=False):
            user = st.text_input("Username", autocomplete="username")
            pw = st.text_input("Password", type="password", autocomplete="current-password")
            ok = st.form_submit_button("Sign in", use_container_width=True, type="primary")
        if not _is_configured():
            st.warning("Login is not configured. Set AUTH_PASSWORD_SHA256 in "
                       "Streamlit secrets to enable sign-in.")
        if ok:
            if _check(user, pw):
                st.session_state["authed"] = True
                st.rerun()
            st.error("Invalid credentials.")
        st.caption("Access is restricted. Credentials are shared out-of-band. "
                   "All data in this console is synthetic — no real Netflix or advertiser data.")
    return False


def logout_button():
    if st.sidebar.button("Sign out", use_container_width=True):
        st.session_state.clear()
        st.rerun()
