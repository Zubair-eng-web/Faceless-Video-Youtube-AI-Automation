"""Streamlit dashboard. Chalane ke liye: python -m streamlit run dashboard/streamlit_app.py"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from app.services.tts import VOICES  # noqa: E402
from dashboard import helpers as H  # noqa: E402
from dashboard import ops_helpers as O  # noqa: E402
from dashboard.api_client import ApiClient, ApiError  # noqa: E402
from dashboard.helpers import (  # noqa: E402
    HAS_FILES,
    STATUSES,
    can_approve,
    can_reject,
    channel_options,
    description_text,
    format_duration,
    is_active,
    quality_summary,
    status_label,
    video_label,
    video_rows,
)

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
LANGUAGES = list(VOICES)
PAGES = ["Videos", "Generate", "Channels", "Production", "Analytics", "Variations", "Long-form"]
ALL = "(sab)"
NO_CHANNEL = "(koi channel nahi)"
DEFAULT_LANG = "(channel ki default)"

st.set_page_config(page_title="Faceless Video AI", layout="wide")


@st.cache_resource
def get_client() -> ApiClient:
    return ApiClient(API_URL)


def flash(kind: str, text: str) -> None:
    st.session_state["flash"] = (kind, text)


def show_flash() -> None:
    item = st.session_state.pop("flash", None)
    if item:
        kind, text = item
        (st.success if kind == "success" else st.error)(text)


def act(call, video_id: int, message: str) -> None:
    try:
        call(video_id)
        flash("success", message)
    except ApiError as exc:
        flash("error", str(exc))
    st.rerun()


# ---------- Channels ----------
LOGO_POSITIONS = ["top-left", "top-right", "bottom-left", "bottom-right", "center"]


def branding_form(client: ApiClient, channel: dict) -> None:
    cid = channel["id"]
    with st.expander("Branding: rang, logo, intro/outro"):
        try:
            b = client.branding(cid)
        except Exception as exc:  # noqa: BLE001 - form na khule to bhi page chale
            st.caption(f"Branding load nahi hui: {exc}")
            return
        with st.form(f"branding_{cid}"):
            c1, c2 = st.columns(2)
            highlight = c1.color_picker("Bolne wale lafz ka rang", b["highlight_color"])
            text = c2.color_picker("Baqi captions ka rang", b["text_color"])
            scale = st.slider("Caption ka size", 0.6, 1.6, float(b["font_scale"]), 0.05)
            st.caption("Files assets/branding folder mein rakhein, yahan sirf naam likhein.")
            logo = st.text_input("Logo (maslan logo.png)", b.get("logo_path") or "")
            position = st.selectbox("Logo ki jagah", LOGO_POSITIONS,
                                    index=LOGO_POSITIONS.index(b["logo_position"]))
            opacity = st.slider("Logo ki opacity", 0.1, 1.0, float(b["logo_opacity"]), 0.05)
            width = st.slider("Logo ki chaurai", 0.05, 0.4, float(b["logo_width"]), 0.01)
            intro = st.text_input("Intro video (maslan intro.mp4)", b.get("intro_path") or "")
            outro = st.text_input("Outro video (maslan outro.mp4)", b.get("outro_path") or "")
            saved = st.form_submit_button("Branding save karein")
        if saved:
            try:
                client.set_branding(cid, {
                    "highlight_color": highlight, "text_color": text, "font_scale": scale,
                    "logo_path": logo.strip() or None, "logo_position": position,
                    "logo_opacity": opacity, "logo_width": width,
                    "intro_path": intro.strip() or None, "outro_path": outro.strip() or None,
                })
                flash("success", f"'{channel['name']}' ki branding save ho gayi")
            except ApiError as exc:
                flash("error", str(exc))
            st.rerun()


def page_channels(client: ApiClient) -> None:
    st.subheader("Channels")
    with st.form("new_channel", clear_on_submit=True):
        name = st.text_input("Channel ka naam")
        niche = st.text_input("Niche (jaise: space facts)")
        language = st.selectbox("Language", LANGUAGES)
        submitted = st.form_submit_button("Channel banayen")
    if submitted:
        try:
            client.create_channel(name, niche, language)
            flash("success", f"Channel '{name}' ban gaya")
        except ApiError as exc:
            flash("error", str(exc))
        st.rerun()

    channels = client.channels()
    if not channels:
        st.info("Abhi koi channel nahi. Upar se pehla channel banayen.")
        return
    st.caption("Channel delete karne se uski videos rehti hain, sirf channel se link hat jata hai.")
    for channel in channels:
        with st.container(border=True):
            left, right = st.columns([5, 1])
            left.markdown(f"**{channel['name']}**  (id {channel['id']})")
            left.caption(f"Niche: {channel['niche'] or '-'} | Language: {channel['language']}")
            branding_form(client, channel)
            if right.button("Delete", key=f"delete_{channel['id']}"):
                try:
                    client.delete_channel(channel["id"])
                    flash("success", f"Channel '{channel['name']}' hata diya")
                except ApiError as exc:
                    flash("error", str(exc))
                st.rerun()


# ---------- Generate ----------
def page_generate(client: ApiClient) -> None:
    st.subheader("Generate: nayi video banayen")
    options = channel_options(client.channels())
    with st.form("generate"):
        channel_label = st.selectbox("Channel", [NO_CHANNEL] + list(options))
        topic = st.text_input("Topic (khali chor dein to niche se chuna jayega)")
        niche = st.text_input("Niche (sirf jab channel na ho aur topic khali ho)")
        language = st.selectbox("Language", [DEFAULT_LANG] + LANGUAGES)
        seconds = st.slider("Lambai (seconds)", 15, 90, 40)
        submitted = st.form_submit_button("Video banayen", type="primary")
    st.caption("Free API limits ki wajah se videos ek ek kar ke banti hain. Ek video mein 2-3 minute lagte hain.")
    st.caption("Hindi, Urdu aur Arabic ke liye Noto fonts assets/fonts mein hone chahiye (python -m scripts.check_fonts se check karein).")
    if submitted:
        try:
            job = client.generate(
                topic=topic.strip() or None,
                channel_id=options.get(channel_label),
                niche=niche.strip() or None,
                language=None if language == DEFAULT_LANG else language,
                seconds=seconds,
            )
            st.success(f"Job #{job['id']} shuru ho gaya. 'Videos' page par progress dekhein.")
        except ApiError as exc:
            st.error(str(exc))


# ---------- Videos ----------
@st.fragment(run_every=5)
def live_progress(client: ApiClient) -> None:
    """Jo videos ban rahi hain unka haal, har 5 second baad khud update hota hai."""
    try:
        active = [v for v in client.videos(limit=50) if is_active(v)]
    except ApiError as exc:
        st.warning(str(exc))
        return
    ids = sorted(v["id"] for v in active)
    previous = st.session_state.get("active_ids", [])
    st.session_state["active_ids"] = ids
    if set(previous) - set(ids):
        st.rerun()  # koi job khatam hui, poora page naya karein
    for video in active:
        st.info(f"Video #{video['id']}: {status_label(video['status'])} ({video['topic'] or 'topic chuna ja raha hai'})")


def publish_panel(client: ApiClient, video: dict) -> None:
    from datetime import datetime, timedelta

    status = video["status"]
    video_id = video["id"]
    st.markdown("**Publish**")
    if status == "published":
        st.success(f"YouTube par upload ho gayi (privacy: {video.get('privacy') or '-'})")
        link = H.youtube_link(video)
        if link:
            st.markdown(f"[YouTube par kholen]({link})")
        if video.get("publish_error"):
            st.caption(video["publish_error"])
        return
    if status == "publishing":
        st.info("YouTube par upload ho rahi hai...")
        return
    if status == "publish_failed":
        st.error(video.get("publish_error") or "Upload fail ho gayi")
        if st.button("Dobara koshish (retry)", key=f"retry_{video_id}"):
            act(client.retry_publish, video_id, f"Video #{video_id} dobara publish ke liye tayyar")
        return
    if not H.can_publish(status):
        st.caption("Publish ke liye pehle video Approve karein.")
        return
    if video["channel_id"] is None:
        st.warning("Is video ka channel nahi hai, isliye YouTube par nahi ja sakti.")
        return
    try:
        connected = {c["id"]: c["connected"] for c in client.youtube_channels()}
    except ApiError:
        connected = {}
    if not connected.get(video["channel_id"], False):
        st.warning(
            "Channel YouTube se connect nahi. Terminal me chalayen: "
            f"python -m scripts.connect_youtube {video['channel_id']}"
        )
        return

    if video.get("publish_error"):
        st.caption(video["publish_error"])
    scheduled = H.schedule_text(video)
    if scheduled:
        st.info(f"Schedule: {scheduled} par khud publish hogi (jab AUTO_PUBLISH on ho)")
        if st.button("Schedule hata dein", key=f"unschedule_{video_id}"):
            act(client.unschedule, video_id, "Schedule hata diya")
    if st.button("Abhi publish karein", key=f"publish_{video_id}", type="primary"):
        act(client.publish, video_id, f"Video #{video_id} upload shuru ho gayi")

    default = datetime.now() + timedelta(hours=1)
    day = st.date_input("Publish ki tareekh", value=default.date(), key=f"day_{video_id}")
    at = st.time_input("Waqt", value=default.time().replace(second=0, microsecond=0), key=f"time_{video_id}")
    if st.button("Schedule karein", key=f"schedule_{video_id}"):
        when = H.combine_when(day, at)
        act(lambda vid: client.schedule(vid, when), video_id, f"Video #{video_id} {when} ke liye schedule ho gayi")


def show_fact_check(fc) -> None:
    if not fc:
        return
    if not fc.get("checked", True):
        st.caption("Fact-check nahi hua: " + str(fc.get("error")))
        return
    claims = fc.get("claims", [])
    fixed = set(fc.get("fixed_scenes", []))
    bad = [c for c in claims if c.get("verdict") != "ok"]
    st.write("Fact-check:", f"{len(claims)} daway, {len(bad)} par shak ya ghalti")
    for c in bad:
        tag = "GHALAT" if c.get("verdict") == "wrong" else "SHAK"
        extra = " (khud theek kiya)" if c.get("scene_number") in fixed else ""
        st.warning(f"{tag} scene {c.get('scene_number')}{extra}: {c.get('claim')} | {c.get('reason', '')}")


def start_redo(client: ApiClient, video_id: int, edits: list) -> None:
    try:
        client.redo(video_id, edits)
        flash("success", f"Video #{video_id} dobara ban rahi hai")
    except ApiError as exc:
        flash("error", str(exc))
    st.rerun()


def redo_panel(client: ApiClient, video: dict) -> None:
    vid = video["id"]
    if video["status"] not in ("ready", "needs_review", "failed") or not video.get("run_dir"):
        return
    with st.expander("Script/clips edit karein ya dobara banayen"):
        try:
            sb = client.storyboard(vid)
        except Exception as exc:  # noqa: BLE001 - panel na khule to bhi page chale
            st.caption(f"Script nahi mila: {exc}")
            return
        with st.form(f"redo_{vid}"):
            st.caption("Sirf jo scene badalna ho wahi badlein. Narration badli to voiceover, fact-check aur SEO "
                       "dobara banenge. Query badli to sirf us scene ki nayi clip aayegi.")
            narrations, queries = {}, {}
            for s in sb["scenes"]:
                n = s["number"]
                narrations[n] = st.text_area(f"Scene {n}: narration", s["narration"], key=f"rn_{vid}_{n}")
                queries[n] = st.text_input(f"Scene {n}: clip search query", s["search_query"], key=f"rq_{vid}_{n}")
            apply = st.form_submit_button("Badlav lagakar dobara banayen", type="primary")
        if apply:
            edits = []
            for s in sb["scenes"]:
                n = s["number"]
                item = {"scene": n}
                if " ".join(narrations[n].split()) != " ".join(s["narration"].split()):
                    item["narration"] = narrations[n]
                if " ".join(queries[n].split()) != " ".join(s["search_query"].split()):
                    item["search_query"] = queries[n]
                if len(item) > 1:
                    edits.append(item)
            if edits:
                start_redo(client, vid, edits)
            else:
                st.warning("Koi badlav nahi kiya.")
        st.caption("Bina badlav dobara chalane se adhoori ya fail hui video wahin se aage barhti hai, "
                   "aur branding ki nayi settings ke saath render hoti hai.")
        if st.button("Dobara chalayen (bina badlav)", key=f"resume_{vid}"):
            start_redo(client, vid, [])


def video_detail(client: ApiClient, video_id: int) -> None:
    video = client.video(video_id)
    status = video["status"]
    st.divider()
    left, right = st.columns([1, 1.7], gap="large")
    with left:
        if status in HAS_FILES:
            st.video(client.video_url(video_id), format="video/mp4")
        elif status == "failed":
            st.error(video["error"] or "Video fail ho gayi")
        else:
            st.info("Video ban rahi hai. Thori der mein ready ho jayegi.")
    with right:
        st.markdown(f"### {video['title'] or video['topic'] or 'Naya video'}")
        st.write(status_label(status), "| Duration:", format_duration(video["duration"]))
        if status in HAS_FILES:
            try:
                st.image(client.thumbnail_bytes(video_id), caption="Thumbnail", width=220)
            except ApiError:
                st.caption("Thumbnail nahi mila")
        headline, lines = quality_summary(video["quality"])
        if video["quality"]:
            st.write("Quality:", headline)
            for line in lines:
                st.caption(line)
        show_fact_check(video.get("fact_check"))
        if video["seo"]:
            seo = video["seo"]
            st.markdown("**Title**")
            st.code(seo["title"], language=None)
            st.markdown("**Description**")
            st.code(description_text(seo), language=None)
            st.markdown("**Tags**")
            st.code(", ".join(seo["tags"]), language=None)
            st.caption("Thumbnail text: " + seo["thumbnail_text"])
        approve_col, reject_col = st.columns(2)
        if approve_col.button("Approve", key=f"approve_{video_id}", disabled=not can_approve(status), type="primary"):
            act(client.approve, video_id, f"Video #{video_id} approve ho gayi")
        if reject_col.button("Reject", key=f"reject_{video_id}", disabled=not can_reject(status)):
            act(client.reject, video_id, f"Video #{video_id} reject ho gayi")
        redo_panel(client, video)
        publish_panel(client, video)


def page_videos(client: ApiClient) -> None:
    st.subheader("Videos")
    channels = client.channels()
    names = {c["id"]: c["name"] for c in channels}
    options = channel_options(channels)
    col_status, col_channel, col_refresh = st.columns([2, 2, 1])
    status = col_status.selectbox("Status", [ALL] + STATUSES)
    channel_label = col_channel.selectbox("Channel", [ALL] + list(options))
    col_refresh.write("")
    if col_refresh.button("Refresh"):
        st.rerun()

    videos = client.videos(
        status=None if status == ALL else status,
        channel_id=None if channel_label == ALL else options[channel_label],
    )
    live_progress(client)
    if not videos:
        st.info("Abhi koi video nahi. 'Generate' page se banayen.")
        return
    st.dataframe(video_rows(videos, names), hide_index=True)
    labels = {v["id"]: video_label(v) for v in videos}
    selected = st.selectbox("Video chunein", list(labels), format_func=lambda i: labels[i])
    video_detail(client, selected)


# ---------- Production ----------
def page_production(client: ApiClient) -> None:
    st.subheader("Production: roz khud videos banwayen")
    info = client.production()
    if info["auto_production_note"] if False else info["auto_produce"]:
        st.success(f"Auto production ON: har {info['check_minutes']} minute baad check hota hai.")
    else:
        st.warning("Auto production abhi OFF hai. Shuru karne ke liye .env me AUTO_PRODUCE=true likhein aur server dobara chalayen.")
    st.caption("Khud bani videos 'ready' ya 'needs_review' me aati hain. Publish se pehle aap ko Approve karna hota hai.")
    if not info["channels"]:
        st.info("Pehle Channels page se channel banayen (niche ke saath).")
        return
    for ch in info["channels"]:
        with st.container(border=True):
            st.markdown(f"**{ch['name']}** - {O.schedule_summary(ch)}")
            st.caption(f"Aaj bani: {ch['produced_today']} | fail: {ch['failed_today']} | niche: {ch['niche'] or '-'}")
            with st.form(f"schedule_{ch['id']}"):
                daily = st.number_input("Roz kitni videos (0 = band)", min_value=0, max_value=5,
                                        value=ch["daily_videos"], key=f"daily_{ch['id']}")
                at = st.text_input("Kis waqt se shuru (HH:MM)", value=ch["produce_at"], key=f"at_{ch['id']}")
                seconds = st.slider("Video ki lambai (seconds)", 15, 90, ch["video_seconds"], key=f"secs_{ch['id']}")
                saved = st.form_submit_button("Save")
            if saved:
                try:
                    client.set_schedule(ch["id"], int(daily), at, int(seconds))
                    flash("success", f"'{ch['name']}' ka production schedule save ho gaya")
                except ApiError as exc:
                    flash("error", str(exc))
                st.rerun()


# ---------- Analytics ----------
def page_analytics(client: ApiClient) -> None:
    st.subheader("Analytics")
    st.caption("Views, likes aur comments YouTube se aate hain. Private videos ke numbers aksar 0 hote hain.")
    left, right = st.columns(2)
    if left.button("Stats refresh karein"):
        try:
            flash("success", O.refresh_message(client.refresh_analytics()))
        except ApiError as exc:
            flash("error", str(exc))
        st.rerun()

    data = client.analytics()
    summary = data["summary"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Videos (stats ke saath)", summary["videos"])
    c2.metric("Total views", O.format_count(summary["total_views"]))
    c3.metric("Engagement", O.engagement_text(summary["engagement"]))
    best = summary.get("best")
    if best:
        st.caption(f"Sab se zyada views: #{best['id']} {best['title']} ({O.format_count(best['views'])})")
    rows = O.analytics_rows(data["videos"])
    if rows:
        st.dataframe(rows, hide_index=True)
    else:
        st.info("Abhi koi published video nahi.")

    if right.button("AI recommendations (1 Gemini request)"):
        try:
            st.session_state["insights"] = client.insights()
        except ApiError as exc:
            st.error(str(exc))
    insights = st.session_state.get("insights")
    if insights:
        st.markdown("### Recommendations")
        st.write(insights["summary"])
        for title, key in (("Kya kaam kar raha hai", "what_works"),
                           ("Kya behtar karein", "what_to_improve"),
                           ("Agle topics", "next_topics")):
            st.markdown(f"**{title}**")
            for item in insights[key]:
                st.markdown(f"- {item}")


# ---------- Variations ----------
def page_variations(client: ApiClient) -> None:
    st.subheader("Variations: ek topic, kai languages")
    st.caption("Har language ki alag video banti hai (ek ke baad ek, har video par ~3 Gemini requests). Dashboard ke Videos page par nazar aayengi.")
    channels = client._request("GET", "/channels").json()
    if not channels:
        st.info("Pehle Channels page se channel banayen.")
        return
    names = {f"{c['id']} - {c['name']}": c["id"] for c in channels}
    with st.form("variations_form"):
        pick = st.selectbox("Channel", list(names))
        topic = st.text_input("Topic")
        langs = st.text_input("Languages (comma se alag, max 5)", value="English, Spanish")
        go = st.form_submit_button("Banayen")
    if go:
        try:
            res = client.create_variations(names[pick], topic, [x.strip() for x in langs.split(",")])
            flash("success", f"{len(res['videos'])} videos queue me hain. Videos page par dekhein.")
        except ApiError as exc:
            flash("error", str(exc))
        st.rerun()


# ---------- Main ----------
def main() -> None:
    try:
        from dashboard.theme import inject_theme
        inject_theme()
    except Exception:  # theme na chale to bhi dashboard chale
        pass
    client = get_client()
    st.title("Faceless Video AI")
    try:
        client.health()
    except ApiError as exc:
        st.error(str(exc))
        st.write("API server ye command se chalayen (alag terminal me):")
        st.code("python -m uvicorn app.api.main:create_app --factory --port 8000", language=None)
        st.stop()

    show_flash()
    with st.sidebar:
        page = st.radio("Page", PAGES)
        stats = client.stats()
        st.divider()
        st.metric("Total videos", stats.get("total", 0))
        details = " | ".join(f"{k}: {v}" for k, v in stats.items() if k != "total")
        if details:
            st.caption(details)
        try:
            info = client.publishing_info()
            mode = "ON" if info["auto_publish"] else "OFF"
            st.caption(f"Auto publish: {mode} | privacy: {info['privacy']} | aaj: {info['published_today']}/{info['daily_limit']}")
        except ApiError:
            pass
        st.caption("API: " + API_URL)

    try:
        if page == "Videos":
            page_videos(client)
        elif page == "Generate":
            page_generate(client)
        elif page == "Channels":
            page_channels(client)
        elif page == "Production":
            page_production(client)
        elif page == "Analytics":
            page_analytics(client)
        elif page == "Long-form":
            try:
                from dashboard.long_page import page_long
            except ImportError:
                from long_page import page_long
            page_long(client)
        else:
            page_variations(client)
    except ApiError as exc:
        st.error(str(exc))


main()
