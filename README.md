# Faceless Video AI

Ek topic se publish-ready YouTube video: research, script, voiceover, visuals, editing, captions, thumbnail, SEO, fact-check, quality check aur publishing. **Shorts (9:16) ka workflow implement hai.** **Long-form (16:9, 10-20 minute) ka end-to-end workflow bhi taiyar hai: research se render, QA, YouTube package aur publish tak.**

Status: 12 long-form upgrade tasks complete; 0 remaining.

## Progress ek nazar mein

<!-- PROGRESS-START -->
**Complete: 12 | Remaining: 0 | Backlog: 0** (12 planned tasks, 100% complete)

Tests: 514 (`python -m pytest tests -q`)
<!-- PROGRESS-END -->

The task list below is the current long-form implementation scope. Previous long-form task numbering and unrelated backlog entries have been replaced by this plan.

---

## 1. Ye project kya karta hai

Aap topic (ya sirf niche, jaise "space facts") dete hain aur system khud kaam karta hai. Insani step sirf **review aur Approve** hai, taake ghalat facts wali video khud publish na ho.

**Shorts mode (taiyar):**
- Gemini se script aur scenes (English, Hindi, Urdu, Arabic, Spanish, French)
- Edge TTS se voiceover, har lafz ke timestamp ke saath
- Pixabay se clips, FFmpeg se 9:16 video: transitions, animated word-by-word captions, mood ke mutabiq music (voice ke waqt halki), sound effects
- Channel ki branding: caption ke rang, logo, intro/outro
- Fact-check, SEO (title, description, hashtags, tags), thumbnail, quality check
- Dashboard se review: script edit, clip badalna, dobara banana, Approve/Reject
- YouTube par publish ya schedule, roz ki limit, auto production, trend research, analytics aur AI recommendations
- Multi-channel (har channel ki niche, language, voice, schedule, branding) aur ek topic ki kai languages mein variations

**Long-form mode (taiyar; ek asli 9.8 minute ki 1920x1080 episode se verify):**
- Target 10-20 minute ki 16:9 (1920x1080) educational, documentary ya storytelling videos banana hai
- Pehle outline, phir chapter by chapter script, har chapter ka alag fact-check (Google Search grounding)
- Scene breakdown aur landscape clips collect karne ka code maujood hai; clip collection mein repetition kam karne aur resume ki support hai
- Remaining implementation is tracked in the 12 English-language tasks below: source-backed research, script and visuals, narration, rendering, quality assurance, YouTube packaging, series continuity, configurable providers, API/dashboard integration, Shorts regression coverage, and end-to-end acceptance.

## 2. Flow

Har video ka apna folder banta hai: `output/runs/<waqt>_<topic>/` (video, thumbnail, captions, storyboard, voiceover, clips, seo, quality, result ki JSON files).

## 3. Tech stack

| Kaam | Technology | Note |
|---|---|---|
| AI | Google Gemini (`google-genai`) | Model `.env` se; Google Search grounding fact-check ke liye |
| Backend | Python + FastAPI + Uvicorn | |
| Voiceover | Edge TTS | Free, key nahi chahiye, word timestamps |
| Stock footage | Pixabay API | Free key |
| Video editing | FFmpeg + subprocess | |
| Captions | ASS format | Word-by-word highlight, Hindi/Urdu/Arabic shaping (libass) |
| Thumbnail | Pillow aur FFmpeg libass | Non-Latin text libass se |
| Database | SQLite (`data/app.db`) | Migrations ke saath |
| Dashboard | Streamlit | |
| Publishing | YouTube Data API v3 | OAuth Desktop app |
| Scheduler | APScheduler | Auto publish aur auto production |
| Tests | pytest | Asli API calls nahi, sab fake |

## 4. Features ki halat

### 4.1 Shuru ke 16 features

| # | Feature | Halat | Note |
|---|---|---|---|
| 1 | AI Topic Research | DONE | Gemini aur YouTube trends (Step 18) |
| 2 | AI Script Generation | DONE | |
| 3 | AI Storyboard | DONE | |
| 4 | Automated Voiceover | DONE | Edge TTS |
| 5 | Smart Stock Video | DONE | Pixabay |
| 6 | Automatic Video Editing | DONE | FFmpeg |
| 7 | Animated Captions | DONE | 6 zabanen |
| 8 | Background Music & SFX | DONE | Mood ke mutabiq music, ducking, whoosh (Step 15) |
| 9 | Thumbnail & SEO | DONE | |
| 10 | Multiple Variations | DONE | Ek topic ki kai languages (Step 14) |
| 11 | AI Quality Checker | DONE | Technical jaanch aur fact-check |
| 12 | Multilingual Videos | DONE | Hindi, Urdu, Arabic, English, Spanish, French |
| 13 | Autonomous Publishing | DONE | YouTube (subject to audit restrictions). Other platforms are not supported |
| 14 | Content Scheduling | DONE | Publish aur production schedule |
| 15 | Analytics & Optimization | DONE | Views, likes, AI recommendations |
| 16 | Multi-Channel Management | DONE | Niche, language, voice, schedule, branding |

### 4.2 Long-form feature status

The codebase already includes outline-and-chapter script generation, chapter-level fact-checking, long-form scene breakdown, landscape clip collection, and resume support. These are building blocks—not a complete long-form production workflow. The remaining work is tracked only in the task list below.

## 5. Folder structure

<!-- AUTO-STRUCTURE-START -->
```
app/core/      analytics, config, db, db_production, db_publish, db_series, models, storyboard
app/agents/    insights_agent, research_agent, script_agent, seo_agent
app/services/  api_key, audio_mix, background, branding, captions, fact_check, fonts, gemini_client, long_clips, long_factcheck, long_narration, long_package, long_pipeline, long_quality, long_render, long_research, long_script, long_validation, long_visuals, maintenance, music, pixabay, production, publisher, quality, redo, scheduler, sfx, thumbnail, thumbnail_ass, trends, tts, variations, video_editor, youtube, youtube_stats
app/api/       long_routes, main, production_routes, publish_routes, runner, schemas, variation_routes
dashboard/     api_client, helpers, key_panel, long_page, ops_helpers, streamlit_app, theme
```
<!-- AUTO-STRUCTURE-END -->

Baqi folders: `tests/`, `scripts/` (aur `scripts/archive/` purani ek-baar-wali scripts), `assets/` (fonts, music, cache), `data/` (SQLite, YouTube tokens), `output/` (har video ka folder).

## 6. Setup (ek baar)

1. Zarurat: Python 3.11+, FFmpeg (`ffmpeg` aur `ffprobe` PATH mein; multilingual captions ke liye libass/harfbuzz/fribidi wala build), VS Code ka PowerShell terminal.
2. Project root mein virtual environment banayen aur dependencies install karein:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. `.env.example` ki copy `.env` banayen aur `GEMINI_API_KEY` aur `PIXABAY_API_KEY` set karein:

   ```powershell
   Copy-Item .env.example .env
   ```

   Gemini key dashboard ke key manager se bhi set ki ja sakti hai, jab API aur dashboard chal rahe hon.
4. FFmpeg aur Python dependencies check karein: `python check_env.py`.

## 7. Kaise chalayen

Pehle `.\.venv\Scripts\Activate.ps1`. Aham commands:

| Kaam | Command |
|---|---|
| Tests | `python -m pytest tests -q` |
| Ek command se Shorts video | `python -m scripts.make_video "topic"` (`--niche`, `--language`, `--seconds`, `--voice`) |
| API server | `python -m uvicorn app.api.main:create_app --factory --port 8000` |
| Dashboard | `python -m streamlit run dashboard/streamlit_app.py` (http://localhost:8501) |
| Dono ek saath | `powershell -ExecutionPolicy Bypass -File scripts\run_all.ps1` |
| YouTube channel connect | `python -m scripts.connect_youtube 1` |
| README ki halat | `python -m scripts.readme_tool status` |

Saari scripts (khud banti hai):

<!-- AUTO-SCRIPTS-START -->
| Command | Kaam |
|---|---|
| `python -m scripts.check_fonts` | Fonts aur FFmpeg ki jaanch, aur Hindi/Urdu/Arabic ke caption aur thumbnail ke sample images. |
| `python -m scripts.check_progress` | - |
| `python -m scripts.connect_youtube` | YouTube channel connect: python -m scripts.connect_youtube 1 (1 = database me channel ki id). |
| `python -m scripts.diagnose_production` | - |
| `python -m scripts.diagnose_run` | Ek run ka tajziya: har scene ka waqt, awaaz ki khamoshi, kala screen aur clip. Kuch badalta nahi. |
| `python -m scripts.import_long_run` | Maujooda long run folder ko database mein import karna (dashboard par dikhane ke liye). |
| `python -m scripts.maintenance` | Maintenance: log rotation + database backup + purane run folders ki list. |
| `python -m scripts.make_video` | Topic se poori video: python -m scripts.make_video "topic" ya --niche "niche". |
| `python -m scripts.readme_tool` | README.md ko ek hi, hamesha sahi file rakhne ka tool: progress, tasks, steps log aur auto sections. |
| `python -m scripts.run_long_acceptance` | Task 36 acceptance run: topic se poori long-form episode + report. |
| `python -m scripts.run_production_once` | Production ek baar chalana: jin channels ka waqt aa chuka un ki ek ek video banti hai. |
| `python -m scripts.set_branding` | Channel ki branding lagana/dekhna. |
| `python -m scripts.set_schedule_now` | - |
| `python -m scripts.set_schedule_one` | - |
| `python -m scripts.status` | Project ka haal: keys, channels, schedule, videos, YouTube permissions. |
| `python -m scripts.try_analytics` | Live test: published videos ke stats YouTube se lena (youtube.readonly permission chahiye). |
| `python -m scripts.try_audio_graph` | Live test: asli FFmpeg par ducking + sfx wala audio graph chalakar dekhna ke syntax theek hai. |
| `python -m scripts.try_branding` | Live test: nakli logo ko asli FFmpeg se test video par lagana. |
| `python -m scripts.try_clips` | Live test: storyboard ke pehle scenes ke liye Pixabay se clips. Asli PIXABAY_API_KEY chahiye. |
| `python -m scripts.try_factcheck` | Live test: output/last_storyboard.json ka asli Gemini se fact-check (auto-fix band, sirf report). |
| `python -m scripts.try_finish` | Live test: SEO (1 Gemini request) + thumbnail + quality check. |
| `python -m scripts.try_long_clips` | Live test: long script ke scenes ke liye asli Pixabay clips + visual report + credits. |
| `python -m scripts.try_long_factcheck` | Live test: long script ka chapter-wise fact-check (asli Gemini + Google Search). |
| `python -m scripts.try_long_package` | Live test: long-form YouTube package. Usage: python -m scripts.try_long_package [--scenes 10] [--force] [run folder] |
| `python -m scripts.try_long_quality` | Live test: long-form quality check. Usage: python -m scripts.try_long_quality [--scenes 10] [--skip-black] [run folder] |
| `python -m scripts.try_long_render` | Render existing long-form narration and clips as a 16:9 video. |
| `python -m scripts.try_long_script` | Live test: asli Gemini se long script (research + script + jaanch). Free API calls lagti hain |
| `python -m scripts.try_long_voice` | Live test: long script ki narration (Edge TTS, key nahi chahiye). Pehle 10 scenes (jaldi). |
| `python -m scripts.try_multilingual` | Live test: Hindi/Urdu/Arabic ki chhoti video (Gemini aur Pixabay ke baghair, sirf Edge TTS aur FFmpeg). |
| `python -m scripts.try_script` | Live test: niche -> topics -> script -> storyboard. 2 Gemini requests lagti hain. |
| `python -m scripts.try_trends` | Live test: asli YouTube se trending titles. Usage: python -m scripts.try_trends "space facts" [--language Urdu] |
| `python -m scripts.try_upload` | Live test: sab se nayi video YouTube par upload (default PRIVATE). Ek upload = 1600 quota units. |
| `python -m scripts.try_video` | Live test: storyboard -> voiceover + clips -> pehli poori video. Asli PIXABAY key aur internet chahiye. |
| `python -m scripts.try_voice` | Live test: storyboard -> voiceover + word timings. Internet chahiye, key nahi. |
<!-- AUTO-SCRIPTS-END -->

Video dekhne ke liye browser ya Windows ka default player use karein. VS Code ka preview mp4 ki awaaz nahi chalata.

## 8. API endpoints (khud banta hai)

API docs: http://127.0.0.1:8000/docs

<!-- AUTO-API-START -->
| Method | Route |
|---|---|
| GET | /analytics |
| POST | /analytics/insights |
| POST | /analytics/refresh |
| GET | /channels |
| POST | /channels |
| DELETE | /channels/{channel_id} |
| GET | /channels/{channel_id} |
| GET | /channels/{channel_id}/branding |
| PUT | /channels/{channel_id}/branding |
| PUT | /channels/{channel_id}/schedule |
| POST | /channels/{channel_id}/variations |
| POST | /generate |
| GET | /health |
| GET | /long |
| POST | /long/generate |
| GET | /production |
| GET | /publishing |
| GET | /series |
| POST | /series |
| GET | /settings/gemini |
| POST | /settings/gemini |
| GET | /stats |
| GET | /videos |
| GET | /videos/{video_id} |
| POST | /videos/{video_id}/approve |
| GET | /videos/{video_id}/file |
| GET | /videos/{video_id}/long |
| POST | /videos/{video_id}/long/approve |
| POST | /videos/{video_id}/long/resume |
| POST | /videos/{video_id}/publish |
| POST | /videos/{video_id}/redo |
| POST | /videos/{video_id}/reject |
| POST | /videos/{video_id}/retry-publish |
| POST | /videos/{video_id}/schedule |
| GET | /videos/{video_id}/storyboard |
| GET | /videos/{video_id}/thumbnail |
| POST | /videos/{video_id}/unschedule |
| GET | /youtube/channels |
<!-- AUTO-API-END -->

## 9. Dashboard

<!-- AUTO-DASHBOARD-START -->
Pages: Videos, Generate, Channels, Production, Analytics, Variations, Long-form
<!-- AUTO-DASHBOARD-END -->

## 10. Settings (`.env` aur environment variables)

<!-- AUTO-ENV-START -->
| Variable | Default | Kahan |
|---|---|---|
| `AI_PROVIDER` | gemini | app/core/config.py |
| `AUTO_PRODUCE` | False | app/core/config.py |
| `AUTO_PUBLISH` | False | app/core/config.py |
| `CACHE_DIR` | (computed) | app/core/config.py |
| `DAILY_UPLOAD_LIMIT` | 5 | app/core/config.py |
| `DB_PATH` | (computed) | app/core/config.py |
| `DEFAULT_PRIVACY` | private | app/core/config.py |
| `FONTS_DIR` | (computed) | app/core/config.py |
| `GEMINI_API_KEY` | (secret) | app/core/config.py |
| `GEMINI_MAX_ATTEMPTS` | 4 | app/core/config.py |
| `GEMINI_MIN_INTERVAL_SECONDS` | 0.0 | app/core/config.py |
| `GEMINI_MODEL` | gemini-3.1-flash-lite | app/core/config.py |
| `GEMINI_RETRY_DELAY` | 5.0 | app/core/config.py |
| `LONG_CHAPTER_PAUSE` | 0.7 | app/services/long_narration.py |
| `LONG_FACTCHECK_AUTOFIX` | - | app/services/long_factcheck.py |
| `LONG_FACTCHECK_GROUNDED` | - | app/services/long_factcheck.py |
| `LONG_MAX_MINUTES` | 20.0 | app/services/long_script.py |
| `LONG_MAX_SCENES` | 150 | app/services/long_script.py |
| `LONG_MAX_SCENE_WORDS` | 32 | app/services/long_script.py |
| `LONG_MIN_MINUTES` | 3.0 | app/services/long_script.py |
| `LONG_SCENE_PAUSE` | 0.15 | app/services/long_narration.py |
| `LONG_SCENE_SECONDS` | 7.0 | app/services/long_script.py |
| `LONG_TARGET_LUFS` | - | app/services/long_narration.py |
| `LONG_VIDEO_HEIGHT` | 1080 | app/core/config.py |
| `LONG_VIDEO_WIDTH` | 1920 | app/core/config.py |
| `LONG_WORDS_PER_MINUTE` | 150 | app/services/long_script.py |
| `MUSIC_DIR` | (computed) | app/core/config.py |
| `OUTPUT_DIR` | (computed) | app/core/config.py |
| `PIXABAY_API_KEY` | (secret) | app/core/config.py |
| `PRODUCE_CHECK_MINUTES` | 10 | app/core/config.py |
| `PUBLISH_CHECK_MINUTES` | 5 | app/core/config.py |
| `TRENDS_REGION` | - | app/services/trends.py |
| `VIDEO_FPS` | 30 | app/core/config.py |
| `VIDEO_HEIGHT` | 1920 | app/core/config.py |
| `VIDEO_WIDTH` | 1080 | app/core/config.py |
<!-- AUTO-ENV-END -->

Dhyan rakhein:
- **`AUTO_PUBLISH=true`** ho to schedule wali approved videos khud YouTube par upload hoti hain.
- **`AUTO_PRODUCE=true`** ho to server chalte waqt jin channels ka schedule 0 se zyada ho, un ki videos khud banti hain aur Gemini quota kharch hoti hai.
- Ek key `.env` mein ek hi dafa likhein.
- Lambi videos ki settings `LONG_*` variables se hoti hain.
- **`LONG_AUTO_APPROVE=true`** ho to long-form video `ready` hote hi khud approve aur schedule hoti hai (`needs_review` kabhi khud upload nahi hoti). Default band hai.

## 11. YouTube ki setup aur limits

1. Google Cloud mein project banayen, **YouTube Data API v3** Enable karein.
2. **Google Auth Platform:** External, scopes `youtube.upload` aur `youtube.readonly`, phir **Publish app** (warna token 7 din mein expire hota hai).
3. **Desktop app** client ki JSON `client_secret.json` naam se project folder mein rakhein.
4. `python -m scripts.connect_youtube <channel id>` chalayen.

Limits (YouTube ke docs ke mutabiq):
- Naye API projects jab tak compliance audit pass na karein, unki upload ki hui videos **private** rehti hain.
- Ek upload lagbhag 1600 quota units leta hai, roz 10,000 units milte hain.
- 15 minute se lambi videos ke liye channel ka verify hona aam tor par zaroori hota hai.

## 12. Security

- `.env`, `client_secret.json` aur `data/tokens/` kisi ko share na karein aur git mein na dalein.
- Koi key chat ya screenshot mein share ho jaye to naya bana kar purana band kar dein.
- Dashboard aur API sirf is computer par chalte hain aur in mein login nahi hai. Internet par kholne se pehle login lagana zaroori hai (backlog).
- Paid Gemini key ke liye alag Google Cloud project, aur Cloud Billing mein budget alert lagayen.

## 13. Tasks

### 13.1 Completed long-form upgrade tasks

<!-- DONE-START -->
| # | Task | Completed work |
|---|---|---|
| 25 | Source-backed research and fact verification | Google Search se chapter-wise facts aur source links; long_research.json |
| 26 | Long-form outline and chapter script generation | Script validation: words, scenes, pacing, hook, dohrayi narration |
| 27 | Relevant scenes and visual assets | Clip author/license tracking, visual report aur credits |
| 28 | Professional long-form narration | Pronunciation rules, scene/chapter pauses, loudness balance, resume aur narration report |
| 29 | Synchronized 16:9 editing and chunk rendering | 1920x1080 chunk render, resume, concat aur final audio mix; drift 0.01s |
| 30 | End-to-end long-form quality assurance | Coverage, timing, captions, audio, black frames, 16:9 aur episode checks; 0 error live run |
| 31 | Long-form YouTube metadata and packaging | Title/description/tags, chapter timestamps, credits, 1280x720 thumbnail aur publishing metadata; live Gemini SEO check Task 36 mein |
| 32 | YouTube series continuity | Series table, episode numbering, style aur structure reuse |
| 33 | Configurable AI providers, models, and limits | AI_PROVIDER, retry/throttle limits aur long-form video size .env se configurable |
| 34 | Long-form API and dashboard workflow | 8-stage long pipeline, progress, resume, approve, series API aur Long-form dashboard page; Shorts routes unchanged |
| 35 | Shorts compatibility and regression coverage | Poori suite pass; 9:16 aur 16:9 profile aur shared helpers ke regression tests |
| 36 | Full long-form acceptance run | 9.8 min 1920x1080 episode: research, script, narration, render, QA 0 error, thumbnail, SEO; 14 Gemini requests, 21 min runtime |
<!-- DONE-END -->

### 13.2 Remaining long-form upgrade tasks

<!-- TODO-START -->
| # | Task | Details | Requirement |
|---|---|---|---|
<!-- TODO-END -->

### 13.3 Additional backlog

<!-- BACKLOG-START -->
| Item | Details |
|---|---|
<!-- BACKLOG-END -->

## 14. Mukammal implementation steps

Ye steps Shorts pipeline aur uski support services ki implementation history hain. Long-form ke abhi pending tasks upar alag list mein hain.

| Steps | Mukammal kaam |
|---|---|
| 1-2 | Python environment, dependencies/configuration, project structure aur environment checks |
| 3-5 | Gemini research/script/storyboard, Edge TTS voiceover/timestamps aur Pixabay stock clip search |
| 6-8 | FFmpeg vertical video editing/captions, SEO/thumbnail/quality checks aur ek-command pipeline |
| 9-10 | SQLite data layer, FastAPI backend aur Streamlit dashboard |
| 11-13 | YouTube OAuth/upload, approve/schedule/retry, auto-production controls aur analytics |
| 14-18 | Multilingual captions, variations, background music/ducking/SFX, fact-check, channel branding aur trend research |
| 19-20 | Script/clip edit aur redo/resume, maintenance, database backups, log rotation aur local service/Docker helpers |
| 21-22 | Dashboard theme aur Gemini API-key management |
| 23-24 | Long-form outline/chapter script generation aur grounded, chapter-wise fact-check |

### Step 33: Configurable AI providers, models, and limits
- make_gemini_client factory, requests_made counter, GEMINI_MIN_INTERVAL_SECONDS, LONG_* values ab .env se bhi parhi jati hain
- Total 469 tests.

### Step 25: Source-backed research and fact verification
- long_research.py, LONG_RESEARCH_GROUNDED, facts har chapter ke prompt mein
- Total 480 tests.

### Step 26: Long-form outline and chapter script generation
- long_validation.py, try_long_script mein research aur jaanch
- Total 480 tests.

### Step 27: Relevant scenes and visual assets
- long_visuals.py, visual_report.json, visual_credits.json, credits_text for description
- Total 488 tests.

### Step 28: Professional long-form narration
- long_narration.py, LONG_VOICE/LONG_VOICE_RATE/LONG_*_PAUSE, narration_report.json
- Total 495 tests.

### Step 29: Synchronized 16:9 editing and chunk rendering
- long_render.py (plan_chunks, chunk signature resume, concat -c copy, render_report.json), try_long_render
- Total 498 tests.

### Step 30: End-to-end long-form quality assurance
- long_quality.py (check_long_quality, long_quality.json), try_long_quality
- Total 501 tests.

### Step 32: YouTube series continuity
- db_series.py (create_series, attach_episode, save_structure, series_style), migration series + videos.series_id/episode_no
- Total 506 tests.

### Step 34: Long-form API and dashboard workflow
- long_pipeline.py, long_routes.py (/long/generate, /long, /videos/{id}/long, resume, approve, /series), dashboard/long_page.py
- Total 510 tests.

### Step 35: Shorts compatibility and regression coverage
- tests/test_profiles_regression.py (default profiles, segment_args crop, shared segment_args/build_ass)
- Total 513 tests.

### Step 31: Long-form YouTube metadata and packaging
- long_package.py (build_long_package, chapter_timestamps, long_package.json), try_long_package; 3 unit tests
- Total 513 tests.

### Step 36: Full long-form acceptance run
- run_long_acceptance.py, acceptance_report.json; music ke saath final mix alag verify
- Total 513 tests.

<!-- STEPS-LOG-END -->

## 15. Maloom limits

- Videos abhi sirf private upload hoti hain (audit se pehle), is liye analytics ke numbers kam hote hain.
- AI kabhi kabhi ghalat facts likh deta hai. Fact-check un ko kam karta hai, khatam nahi. Approve se pehle khud dekhein.
- Gemini aur Pixabay ki free limits hain. Limits project ke hisab se lagti hain, aur Gemini ki roz ki limit Pacific time ke aadhi raat par reset hoti hai.
- Pixabay ki shart ke mutabiq search results 24 ghante se zyada cache nahi kiye jate.
- Music folder (`assets/music`) mein apni royalty-free tracks rakhein, license check kar ke.
- Windows mein file ka extension chhupa ho to download ki hui JSON ka naam `.json.json` ban sakta hai.

## 16. Is README ko kaise update karte hain

Ye ek hi README hai. Har step ke baad:
- `python -m scripts.readme_tool complete <number> --title "..." --summary "..." --detail "..."` task ko "Baqi" se "Mukammal" mein le jata hai, steps log mein entry jorta hai aur ginti khud badhata hai.
- `python -m scripts.readme_tool sync` API routes, dashboard pages, scripts, `.env` variables aur folder structure dobara code se banata hai.
- `python -m scripts.readme_tool status` progress aur baqi tasks dikhata hai.





python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt