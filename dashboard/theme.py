"""Professional dashboard theme: slate dark, indigo accent, card layout, styled sidebar."""
import os
from datetime import datetime

import streamlit as st

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root { --bg:#0b1220; --surface:#111a2e; --surface2:#16223a; --border:#24324d; --text:#e6ebf5; --muted:#8b9bb8;
        --accent:#6366f1; --accent2:#818cf8; --ok:#22c55e; --warn:#f59e0b; --bad:#ef4444; }

.stApp { background: var(--bg); color: var(--text); }
.stApp, .stApp p, .stApp label, .stApp li, .stApp input, .stApp textarea, .stApp button, .stApp select {
  font-family: 'Inter', system-ui, sans-serif; }
.block-container { padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1280px; }
header[data-testid="stHeader"] { background: var(--bg); border-bottom: 1px solid var(--border); }
h1, h2, h3, h4 { color: var(--text) !important; font-weight: 650 !important; letter-spacing: -.01em; }
h3 { font-size: 1.25rem !important; margin-top: .4rem; }
p, label, .stCaption, small { color: var(--muted); }
hr { border-color: var(--border) !important; margin: 1.1rem 0 !important; }

/* Top header bar */
.pro-head { display:flex; align-items:center; justify-content:space-between; gap:16px; padding:18px 24px; margin-bottom:22px;
  background: linear-gradient(135deg, #1a2547 0%, #111a2e 60%); border:1px solid var(--border); border-radius:14px;
  box-shadow: 0 6px 24px rgba(0,0,0,.25); }
.pro-title { font-size:1.45rem; font-weight:700; color:var(--text); letter-spacing:-.01em; }
.pro-sub { font-size:.88rem; color:var(--muted); margin-top:2px; }
.pro-right { display:flex; align-items:center; gap:10px; font-size:.85rem; color:var(--muted); }
.pro-pill { display:inline-flex; align-items:center; gap:7px; padding:5px 12px; border-radius:999px;
  background: rgba(34,197,94,.12); color: var(--ok); font-weight:600; border:1px solid rgba(34,197,94,.3); }
.pro-dot { width:8px; height:8px; border-radius:50%; background: var(--ok); }

/* Sidebar: hamesha dikhe */
section[data-testid="stSidebar"], section[data-testid="stSidebar"][aria-expanded="false"] {
  transform: none !important; margin-left: 0 !important; min-width: 270px !important; width: 270px !important;
  visibility: visible !important; background: var(--surface); border-right: 1px solid var(--border); }
section[data-testid="stSidebar"] > div { padding-top: 1rem; }
.sb-brand { display:flex; align-items:center; gap:12px; padding:6px 6px 18px 6px; margin-bottom:10px; border-bottom:1px solid var(--border); }
.sb-logo { width:40px; height:40px; border-radius:11px; display:flex; align-items:center; justify-content:center;
  background: linear-gradient(135deg, var(--accent), #8b5cf6); color:#fff; font-weight:700; font-size:1.15rem; }
.sb-name { font-weight:700; color:var(--text); font-size:1rem; line-height:1.2; }
.sb-sub { color:var(--muted); font-size:.78rem; }
section[data-testid="stSidebar"] *, section[data-testid="stSidebar"] label { color: var(--text); }
section[data-testid="stSidebar"] div[role="radiogroup"] { gap: 4px; }
section[data-testid="stSidebar"] div[role="radiogroup"] label { padding: 10px 14px; border-radius: 10px; width: 100%;
  border: 1px solid transparent; cursor: pointer; transition: all .15s ease; }
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover { background: var(--surface2); }
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
  background: rgba(99,102,241,.16); border-color: rgba(99,102,241,.55); }
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p { color: #fff; font-weight: 600; }

/* Cards */
div[data-testid="stVerticalBlockBorderWrapper"], div[data-testid="stExpander"], div[data-testid="stForm"] {
  background: var(--surface) !important; border: 1px solid var(--border) !important; border-radius: 12px !important;
  box-shadow: 0 2px 10px rgba(0,0,0,.18); }
div[data-testid="stExpander"] summary { font-weight: 600; padding: 4px 6px; }
div[data-testid="stMetric"] { background: var(--surface); border:1px solid var(--border); border-radius:12px; padding:16px 18px;
  box-shadow: 0 2px 10px rgba(0,0,0,.18); }
div[data-testid="stMetricLabel"] p { color: var(--muted); font-size:.82rem; font-weight:500; text-transform:uppercase; letter-spacing:.06em; }
div[data-testid="stMetricValue"] { color: var(--text); font-weight: 700; }

/* Buttons */
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
  background: var(--surface2); color: var(--text); border: 1px solid var(--border); border-radius: 9px;
  font-weight: 600; padding: .5rem 1rem; transition: all .15s ease; }
.stButton > button:hover, .stFormSubmitButton > button:hover { border-color: var(--accent2); color:#fff; background:#1d2c4a; }
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
  background: linear-gradient(135deg, var(--accent), #7c3aed); border: none; color:#fff; box-shadow: 0 4px 14px rgba(99,102,241,.4); }
.stButton > button[kind="primary"]:hover { filter: brightness(1.1); }
.stButton > button:disabled { opacity:.4; }

/* Inputs */
.stTextInput input, .stTextArea textarea, .stNumberInput input, div[data-baseweb="select"] > div {
  background: #0d1526 !important; color: var(--text) !important; border: 1px solid var(--border) !important; border-radius: 9px !important; }
.stTextInput input:focus, .stTextArea textarea:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 3px rgba(99,102,241,.25) !important; }

/* Tabs, alerts, media, code */
button[data-baseweb="tab"] { font-weight: 600; color: var(--muted); }
button[data-baseweb="tab"][aria-selected="true"] { color: var(--text); }
div[data-baseweb="tab-highlight"] { background: var(--accent) !important; }
div[data-testid="stAlert"] { border-radius: 10px; border: 1px solid var(--border); }
video, .stVideo { border-radius: 12px; border: 1px solid var(--border); }
img { border-radius: 10px; }
code, pre { background:#0d1526 !important; border:1px solid var(--border); border-radius: 8px; }
div[data-testid="stDataFrame"] { border:1px solid var(--border); border-radius: 10px; overflow:hidden; }
/* Video player: khari (9:16) video ko munasib size mein rakho */
div[data-testid="stVideo"] { display:flex; justify-content:center; background:#000; border:1px solid var(--border);
  border-radius:12px; padding:0; overflow:hidden; }
div[data-testid="stVideo"] video, .stVideo video { width:auto !important; height:auto !important; max-width:100% !important;
  max-height: 520px !important; margin:0 auto; display:block; object-fit:contain; background:#000; }
/* Sidebar key box fix */
section[data-testid="stSidebar"], section[data-testid="stSidebar"][aria-expanded="false"] {
  min-width: 300px !important; width: 300px !important; }
section[data-testid="stSidebar"] div[data-baseweb="input"],
section[data-testid="stSidebar"] div[data-baseweb="base-input"] {
  background: #0d1526 !important; border: 1px solid var(--border) !important; border-radius: 9px !important; }
section[data-testid="stSidebar"] input {
  background: transparent !important; color: var(--text) !important; -webkit-text-fill-color: var(--text) !important;
  font-size: .95rem !important; letter-spacing: normal !important; padding: 10px 12px !important; }
section[data-testid="stSidebar"] input::placeholder { color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important; opacity: 1; }
section[data-testid="stSidebar"] div[data-baseweb="input"] button, section[data-testid="stSidebar"] div[data-baseweb="input"] svg {
  color: var(--muted) !important; fill: var(--muted) !important; background: transparent !important; }
section[data-testid="stSidebar"] div[data-testid="stExpander"] summary p { white-space: normal !important; overflow-wrap: anywhere; }
section[data-testid="stSidebar"] div[data-testid="stForm"] { border: none !important; box-shadow: none !important; padding: 0 !important; background: transparent !important; }
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { overflow-wrap: anywhere; font-size: .82rem; }
section[data-testid="stSidebar"] code { overflow-wrap: anywhere; white-space: normal; font-size: .85rem; padding: 2px 6px; }
/* Icon font fix */
span[data-testid="stIconMaterial"], .material-icons, .material-symbols-rounded,
span[class*="material-symbols"], span[class*="MaterialIcon"] {
  font-family: 'Material Symbols Rounded', 'Material Icons' !important; font-weight: normal !important;
  font-style: normal !important; letter-spacing: normal !important; text-transform: none !important;
  -webkit-font-feature-settings: 'liga'; font-feature-settings: 'liga'; white-space: nowrap; }
div[data-testid="stExpander"] summary { display:flex; align-items:center; gap:8px; }
div[data-testid="stExpander"] summary p { margin:0; }
::-webkit-scrollbar { width: 9px; height: 9px; }
::-webkit-scrollbar-thumb { background: #2b3b5c; border-radius: 6px; }
"""


def header_html(now=datetime.now) -> str:
    stamp = now().strftime("%a, %d %b %Y  %H:%M")
    return (
        '<div class="pro-head"><div>'
        '<div class="pro-title">Faceless Video AI</div>'
        '<div class="pro-sub">Content automation studio: research, script, video, publish, analytics</div></div>'
        f'<div class="pro-right"><span class="pro-pill"><span class="pro-dot"></span>System online</span>{stamp}</div></div>'
    )


def brand_html() -> str:
    return ('<div class="sb-brand"><div class="sb-logo">F</div><div>'
            '<div class="sb-name">Faceless Video AI</div><div class="sb-sub">Automation Studio</div></div></div>')


def inject_theme(show_header: bool = True) -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    try:
        st.sidebar.markdown(brand_html(), unsafe_allow_html=True)
    except Exception:  # noqa: BLE001 - brand na dikhe to bhi dashboard chale
        pass
    if show_header:
        st.markdown(header_html(), unsafe_allow_html=True)
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        try:
            from dashboard.key_panel import show_key_panel
            show_key_panel()
        except Exception:  # noqa: BLE001 - panel na chale to bhi dashboard chale
            pass
