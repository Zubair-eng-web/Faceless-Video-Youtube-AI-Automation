"""Dashboard: key expire ho to banner + khali box, aur sidebar mein hamesha key badalne ka box."""
import streamlit as st

from dashboard.api_client import ApiClient, ApiError

TITLES = {"invalid": "Gemini API key expire ho gayi ya galat hai", "missing": "Gemini API key set nahi hai"}
LABELS = {"ok": "theek", "limited": "quota khatam", "invalid": "expire/galat", "missing": "set nahi", "error": "jaanch nahi hui"}


def _form(client, suffix: str, label: str) -> None:
    with st.form(f"gemini_key_{suffix}", clear_on_submit=True):
        new = st.text_input(label, type="password", placeholder="AIza...", key=f"gemini_input_{suffix}")
        go = st.form_submit_button("Key save karein", type="primary")
    if go:
        try:
            res = client.set_gemini_key(new)
        except ApiError as exc:
            st.error(str(exc))
            return
        st.session_state["gemini_msg"] = res.get("message", "Key save ho gayi")
        st.rerun()


def show_key_panel(client=None) -> None:
    client = client or ApiClient()
    msg = st.session_state.pop("gemini_msg", None)
    if msg:
        st.success(msg)
    try:
        status = client.gemini_status()
    except Exception:  # noqa: BLE001 - API band ho to panel chhupa rahe
        return
    state = status.get("state", "error")
    if state in TITLES:
        st.error(f"**{TITLES[state]}.** {status.get('message', '')} "
                 "Neeche nayi key paste karein, baqi sab khud ho jayega.")
        _form(client, "banner", "Nayi Gemini API key")
        st.caption("Nayi key yahan se lein: https://aistudio.google.com/apikey")
    elif state == "limited":
        st.warning(status.get("message", "Gemini ka quota khatam hai."))
    with st.sidebar.expander("Gemini API key"):
        st.markdown(f"**Halat:** {LABELS.get(state, state)}")
        masked = status.get("masked")
        st.markdown("**Maujooda key:**")
        st.code(masked if masked else "set nahi", language=None)
        _form(client, "sidebar", "Key badlein")
