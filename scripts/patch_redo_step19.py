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


if "LAST_RUN_DIR" in (root / "app/pipeline.py").read_text(encoding="utf-8"):
    print("Pehle se patch ho chuka hai")
    raise SystemExit(0)

edit("app/pipeline.py", [
    ("TOTAL_STEPS = 7\n",
     "TOTAL_STEPS = 7\nLAST_RUN_DIR = None  # aakhri run ka folder (fail hui job ka folder yaad rakhne ke liye)\n"),
    ("    run_dir.mkdir(parents=True, exist_ok=True)\n",
     "    run_dir.mkdir(parents=True, exist_ok=True)\n    global LAST_RUN_DIR\n    LAST_RUN_DIR = str(run_dir)\n"),
])

edit("app/core/db.py", [])
files["app/core/db.py"] = files["app/core/db.py"].rstrip("\n") + '''


def set_run_dir(db_path, video_id: int, run_dir) -> None:
    """Run folder ka path likhna (fail hui video ko dobara chalane ke liye)."""
    with connect(db_path) as con:
        con.execute("UPDATE videos SET run_dir = ? WHERE id = ?", (run_dir, video_id))
'''

main_text = (root / "app/api/main.py").read_text(encoding="utf-8")
if "BackgroundTasks" not in main_text:
    print("[FAIL] main.py mein BackgroundTasks import nahi. Kuch nahi badla.")
    raise SystemExit(1)

BLOCK = '''    redo_fn = redoer or default_redo

    def run_redo_job(video_id, run_dir, edits, branding):
        with lock:
            try:
                db.transition(path, video_id, "generating", {"queued"})
                result = redo_fn(run_dir=run_dir, edits=edits, branding=branding)
                db.finish_video(path, video_id, result)
            except Exception as exc:
                db.fail_video(path, video_id, str(exc) or type(exc).__name__)

    @app.get("/videos/{video_id}/storyboard")
    def get_storyboard(video_id: int):
        video = video_or_404(video_id)
        view = load_storyboard_view(video["run_dir"])
        if view is None:
            raise HTTPException(404, "Is video ka script folder nahi mila")
        return view

    @app.post("/videos/{video_id}/redo", status_code=202)
    def redo_video(video_id: int, body: RedoRequest, background: BackgroundTasks):
        video = video_or_404(video_id)
        run_dir = video["run_dir"]
        if load_storyboard_view(run_dir) is None:
            raise HTTPException(400, "Is video ka script folder nahi mila, Generate se nayi video banayein")
        try:
            db.transition(path, video_id, "queued", {"ready", "needs_review", "failed"})
        except db.InvalidTransitionError as exc:
            raise HTTPException(409, str(exc)) from exc
        channel = db.get_channel(path, video["channel_id"]) if video["channel_id"] else None
        branding = branding_from_row(channel) if channel else None
        background.add_task(run_redo_job, video_id, run_dir, body.edits, branding)
        return {"id": video_id, "status": "queued"}

'''
edit("app/api/main.py", [
    ("from app.services.branding import Branding, branding_from_row\n",
     "from app.services.branding import Branding, branding_from_row\n"
     "from app.services.redo import RedoRequest, default_redo, load_storyboard_view\n"
     "from app import pipeline as pipeline_mod\n"),
    ("stats_fn=None, insights_fn=None, auto_produce=None) -> FastAPI:",
     "stats_fn=None, insights_fn=None, auto_produce=None, redoer=None) -> FastAPI:"),
    ("                used = db.used_topics(path, channel_id)\n",
     "                pipeline_mod.LAST_RUN_DIR = None\n                used = db.used_topics(path, channel_id)\n"),
    ("                db.fail_video(path, video_id, str(exc) or type(exc).__name__)\n",
     "                db.fail_video(path, video_id, str(exc) or type(exc).__name__)\n"
     "                if pipeline_mod.LAST_RUN_DIR:\n"
     "                    db.set_run_dir(path, video_id, pipeline_mod.LAST_RUN_DIR)\n"),
    ('    @app.delete("/channels/{channel_id}")\n', BLOCK + '    @app.delete("/channels/{channel_id}")\n'),
])

VIDEO = '    def video(self, video_id: int) -> dict:\n        return self._request("GET", f"/videos/{video_id}").json()\n'
edit("dashboard/api_client.py", [(VIDEO, VIDEO +
     '\n    def storyboard(self, video_id: int) -> dict:\n'
     '        return self._request("GET", f"/videos/{video_id}/storyboard").json()\n\n'
     '    def redo(self, video_id: int, edits=()) -> dict:\n'
     '        return self._request("POST", f"/videos/{video_id}/redo", json={"edits": list(edits)}).json()\n')])

PANEL = '''def start_redo(client: ApiClient, video_id: int, edits: list) -> None:
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


'''
edit("dashboard/streamlit_app.py", [
    ("def video_detail(client: ApiClient, video_id: int) -> None:",
     PANEL + "def video_detail(client: ApiClient, video_id: int) -> None:"),
    ("        publish_panel(client, video)\n", "        redo_panel(client, video)\n        publish_panel(client, video)\n"),
])

bak = root / "output" / "step19_bak"
bak.mkdir(parents=True, exist_ok=True)
for rel in files:
    shutil.copy(root / rel, bak / rel.replace("/", "__"))
for rel, text in files.items():
    (root / rel).write_text(text, encoding="utf-8")
print("[OK] 5 files patch ho gayin. Backups: output/step19_bak")
