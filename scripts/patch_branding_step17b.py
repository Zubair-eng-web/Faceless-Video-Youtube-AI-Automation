import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
files = {}


def edit(rel, pairs):
    t = files.get(rel) or (root / rel).read_text(encoding="utf-8")
    for old, new in pairs:
        n = t.count(old)
        if n != 1:
            print(f"[FAIL] {rel}: pattern {n} dafa mila: {old[:70]!r}. Kuch nahi badla.")
            raise SystemExit(1)
        t = t.replace(old, new)
    files[rel] = t


if "def branding_form" in (root / "dashboard/streamlit_app.py").read_text(encoding="utf-8"):
    print("Pehle se patch ho chuka hai")
    raise SystemExit(0)

DEL = ('    def delete_channel(self, channel_id: int) -> dict:\n'
       '        return self._request("DELETE", f"/channels/{channel_id}").json()\n')
edit("dashboard/api_client.py", [(DEL, DEL +
     '\n    def branding(self, channel_id: int) -> dict:\n'
     '        return self._request("GET", f"/channels/{channel_id}/branding").json()\n\n'
     '    def set_branding(self, channel_id: int, data: dict) -> dict:\n'
     '        return self._request("PUT", f"/channels/{channel_id}/branding", json=data).json()\n')])

FORM = '''LOGO_POSITIONS = ["top-left", "top-right", "bottom-left", "bottom-right", "center"]


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


'''
edit("dashboard/streamlit_app.py", [
    ("def page_channels(client: ApiClient) -> None:", FORM + "def page_channels(client: ApiClient) -> None:"),
    ("            left.caption(f\"Niche: {channel['niche'] or '-'} | Language: {channel['language']}\")\n",
     "            left.caption(f\"Niche: {channel['niche'] or '-'} | Language: {channel['language']}\")\n"
     "            branding_form(client, channel)\n"),
])

edit("app/services/production.py", [
    ("def run_one(db_path, runner, channel, lock=JOB_LOCK) -> int:",
     "def _branding_kwargs(db_path, channel) -> dict:\n"
     "    \"\"\"Channel ki branding (agar set ho) runner ko dene ke liye.\"\"\"\n"
     "    from app.services.branding import branding_from_row\n"
     "    b = branding_from_row(db.get_channel(db_path, channel[\"id\"]))\n"
     "    return {\"branding\": b} if b else {}\n\n\n"
     "def run_one(db_path, runner, channel, lock=JOB_LOCK) -> int:"),
    ('voice=channel["voice"], used_topics=used,',
     'voice=channel["voice"], used_topics=used, **_branding_kwargs(db_path, channel),'),
])

edit("app/pipeline.py", [
    ("def slugify(text: str, max_len: int = 40) -> str:",
     "def core_video(run_dir, video):\n"
     "    \"\"\"Intro/outro lagi ho to quality check asli content wali video (video_core.mp4) par.\"\"\"\n"
     "    core = Path(run_dir) / \"video_core.mp4\"\n"
     "    return core if core.exists() else video\n\n\n"
     "def slugify(text: str, max_len: int = 40) -> str:"),
    ("check_fn, video, vo, board, clips,", "check_fn, core_video(run_dir, video), vo, board, clips,"),
])

bak = root / "output" / "step17b_bak"
bak.mkdir(parents=True, exist_ok=True)
for rel in files:
    shutil.copy(root / rel, bak / rel.replace("/", "__"))
for rel, text in files.items():
    (root / rel).write_text(text, encoding="utf-8")
print("[OK] 4 files patch ho gayin. Backups: output/step17b_bak")
