"""Dashboard: Long-form page."""
import time

import streamlit as st

def call(client, method, path, **kw):
    r = client._request(method, path, **kw)
    if hasattr(r, "json"):
        try:
            return r.json()
        except ValueError:
            return None
    return r


LANGS = ["English", "Hindi", "Urdu", "Arabic", "Spanish", "French"]


def page_long(client):
    st.header("Long-form videos (16:9)")
    channels = call(client, "GET", "/channels")
    series = call(client, "GET", "/series")
    ch_opts = {"(koi nahi)": None, **{c["name"]: c["id"] for c in channels}}
    sr_opts = {"(koi nahi)": None, **{s["name"]: s["id"] for s in series}}

    with st.expander("Nayi long video", expanded=True):
        topic = st.text_input("Topic", key="long_topic")
        a, b, c = st.columns(3)
        language = a.selectbox("Language", LANGS, key="long_lang")
        minutes = b.slider("Minutes", 3, 20, 10, key="long_min")
        ch = c.selectbox("Channel", list(ch_opts), key="long_ch")
        sr = st.selectbox("Series", list(sr_opts), key="long_sr")
        if st.button("Generate long video", disabled=len(topic.strip()) < 3):
            r = call(client, "POST", "/long/generate", json={
                "topic": topic, "language": language, "minutes": minutes,
                "channel_id": ch_opts[ch], "series_id": sr_opts[sr]})
            st.success(f"Video #{r['id']} queue mein (episode: {r.get('episode') or '-'})")

    with st.expander("Nayi series"):
        n = st.text_input("Series ka naam", key="ser_name")
        nar = st.text_input("Narrator style (khali = default)", key="ser_nar")
        tone = st.text_input("Tone (khali = default)", key="ser_tone")
        aud = st.text_input("Audience (khali = default)", key="ser_aud")
        if st.button("Series banayen", disabled=not n.strip()):
            call(client, "POST", "/series", json={"name": n, "narrator": nar, "tone": tone, "audience": aud,
                                                      "channel_id": ch_opts[st.session_state.get("long_ch", "(koi nahi)")]})
            st.success("Series ban gayi")
            st.rerun()

    rows = call(client, "GET", "/long")
    if not rows:
        st.info("Abhi koi long video nahi.")
        return
    st.dataframe(rows, use_container_width=True)
    pick = st.selectbox("Video chunein", [r["id"] for r in reversed(rows)], key="long_pick")
    d = call(client, "GET", f"/videos/{pick}/long")
    pr = d["progress"]
    st.progress(min(max(pr.get("pct", 0), 0), 100) / 100, text=f"{d['status']} | stage: {pr.get('stage')} | {pr.get('message', '')}")
    if d.get("error"):
        st.error(d["error"])

    b1, b2, b3, b4 = st.columns(4)
    if d["status"] in ("failed", "needs_review", "ready") and b1.button("Resume / dobara"):
        call(client, "POST", f"/videos/{pick}/long/resume")
        st.rerun()
    if d["status"] in ("ready", "needs_review") and b2.button("Approve"):
        call(client, "POST", f"/videos/{pick}/long/approve")
        st.rerun()
    if d["status"] in ("ready", "needs_review", "approved") and b3.button("Reject"):
        client.reject(pick)
        st.rerun()
    if d["status"] == "approved" and b4.button("Publish"):
        client.publish(pick)
        st.success("Publish shuru")

    q = d.get("quality")
    if q:
        st.subheader("Quality")
        st.write(f"{len(q['issues'])} masle")
        for i in q["issues"]:
            st.write(f"- **{i['level']}** {i['area']}: {i['msg']}" + (f" -> {i['fix']}" if i.get("fix") else ""))
    p = d.get("package")
    if p:
        st.subheader(p["title"])
        for ch_ in p["chapters"]:
            st.write(f"{ch_['time']} {ch_['title']}")
        st.text_area("Description", p["description"], height=220)
        try:
            st.image(client.thumbnail_bytes(pick))
        except Exception:
            pass
    if d["status"] in ("ready", "needs_review", "approved", "published"):
        st.video(client.video_url(pick))
    if d["status"] in ("queued", "generating"):
        time.sleep(5)
        st.rerun()
