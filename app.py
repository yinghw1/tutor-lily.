import os
import base64
import json
import sqlite3
import uuid
from datetime import datetime

import streamlit as st
from openai import OpenAI

# ============================================================
# Vox Mascot Logo (Loads voxathon_v1.png if present, else high-detail SVG)
# ============================================================
MASCOT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 500" width="100%" height="100%">
  <rect width="500" height="500" rx="90" fill="#E6D8FF"/>
  <!-- Golden-Yellow Rounded Triangle Body -->
  <path d="M 250 82 C 295 82, 330 135, 365 210 L 418 315 C 448 375, 412 436, 335 436 L 165 436 C 88 436, 52 375, 82 315 L 135 210 C 170 135, 205 82, 250 82 Z" 
        fill="#F4D018" stroke="#000000" stroke-width="5" stroke-linejoin="round"/>
  <!-- Eyebrows -->
  <path d="M 195 190 Q 208 182 220 187" stroke="#000000" stroke-width="3.5" stroke-linecap="round" fill="none"/>
  <path d="M 280 186 Q 292 183 305 190" stroke="#000000" stroke-width="3.5" stroke-linecap="round" fill="none"/>
  <!-- Eyelashes -->
  <path d="M 196 205 L 194 199 M 206 202 L 206 196 M 216 203 L 218 197" stroke="#000000" stroke-width="1.8" stroke-linecap="round"/>
  <path d="M 283 205 L 281 199 M 293 203 L 293 197 M 303 206 L 305 200" stroke="#000000" stroke-width="1.8" stroke-linecap="round"/>
  <!-- Left Eye -->
  <ellipse cx="212" cy="232" rx="23" ry="26" transform="rotate(-6 212 232)" fill="#FFFFFF" stroke="#000000" stroke-width="2.5"/>
  <circle cx="215" cy="233" r="18" fill="#0095FF"/>
  <circle cx="216" cy="233" r="12" fill="#000000"/>
  <circle cx="207" cy="224" r="5.5" fill="#FFFFFF"/>
  <!-- Right Eye -->
  <ellipse cx="288" cy="234" rx="22" ry="25" transform="rotate(-6 288 234)" fill="#FFFFFF" stroke="#000000" stroke-width="2.5"/>
  <circle cx="285" cy="235" r="17" fill="#0095FF"/>
  <circle cx="284" cy="235" r="11.5" fill="#000000"/>
  <circle cx="276" cy="226" r="5" fill="#FFFFFF"/>
  <!-- Smile, Teeth & Tongue -->
  <path d="M 217 268 Q 255 292 292 276 C 302 315, 282 344, 248 341 C 212 338, 200 305, 217 268 Z" 
        fill="#7B0000" stroke="#000000" stroke-width="4" stroke-linejoin="round"/>
  <!-- White Top Teeth -->
  <path d="M 217 268 Q 255 292 292 276 L 293 295 Q 252 294 212 291 Z" 
        fill="#FFFFFF" stroke="#000000" stroke-width="3" stroke-linejoin="round"/>
  <!-- Pink Tongue -->
  <path d="M 212 319 C 228 315, 248 322, 253 340 C 232 340, 218 332, 212 319 Z" fill="#FF6B7B"/>
  <path d="M 217 268 Q 255 292 292 276 C 302 315, 282 344, 248 341 C 212 338, 200 305, 217 268 Z" 
        fill="none" stroke="#000000" stroke-width="4" stroke-linejoin="round"/>
</svg>"""

def get_logo_uri():
    for fname in ["voxathon_v1.png", "voxathon logo.jpeg", "logo.png"]:
        if os.path.exists(fname):
            with open(fname, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
                mime = "image/png" if fname.endswith(".png") else "image/jpeg"
                return f"data:{mime};base64,{b64}"
    b64_svg = base64.b64encode(MASCOT_SVG.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64_svg}"

LOGO_URI = get_logo_uri()

# ============================================================
# Silent API Key Loader (Secrets or Environment Variable)
# ============================================================
def get_api_key():
    try:
        if "OPENROUTER_API_KEY" in st.secrets:
            return st.secrets["OPENROUTER_API_KEY"]
    except Exception:
        pass
    return os.getenv("OPENROUTER_API_KEY", "")

# ============================================================
# Database Setup (SQLite for Projects, Memory & Chat History)
# ============================================================
DB_FILE = "voxathon_app.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            key_fact TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id TEXT PRIMARY KEY,
            project_id INTEGER NULL,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

def get_or_create_project(project_name):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
    row = cursor.fetchone()
    if row:
        pid = row[0]
    else:
        cursor.execute("INSERT INTO projects (name) VALUES (?)", (project_name,))
        conn.commit()
        pid = cursor.lastrowid
    conn.close()
    return pid

def get_all_projects():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM projects ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_project_memory(project_id, fact):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM project_memories WHERE project_id = ? AND key_fact = ?", (project_id, fact))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO project_memories (project_id, key_fact) VALUES (?, ?)", (project_id, fact))
        conn.commit()
    conn.close()

def delete_project_memory(memory_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM project_memories WHERE id = ?", (memory_id,))
    conn.commit()
    conn.close()

def get_project_memories(project_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, key_fact FROM project_memories WHERE project_id = ? ORDER BY created_at ASC", (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def create_chat_session(title="New chat", project_id=None):
    session_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_sessions (session_id, project_id, title) VALUES (?, ?, ?)", (session_id, project_id, title))
    conn.commit()
    conn.close()
    return session_id

def get_sessions(project_id=None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if project_id is not None:
        cursor.execute("SELECT session_id, title FROM chat_sessions WHERE project_id = ? ORDER BY created_at DESC", (project_id,))
    else:
        cursor.execute("SELECT session_id, title FROM chat_sessions WHERE project_id IS NULL ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def save_chat_message(session_id, role, content):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)", (session_id, role, content))
    cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id = ?", (session_id,))
    count = cursor.fetchone()[0]
    if count == 1 and role == "user":
        clean_text = content.split("\n\n--- Content")[0].split("\n\n📎")[0]
        title = clean_text[:30] + "..." if len(clean_text) > 30 else clean_text
        cursor.execute("UPDATE chat_sessions SET title = ? WHERE session_id = ?", (title, session_id))
    conn.commit()
    conn.close()

def load_session_messages(session_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]

init_db()

# ============================================================
# Streamlit Page Config & Gemini-Inspired CSS
# ============================================================
st.set_page_config(
    page_title="Vox · Voxathon",
    page_icon=LOGO_URI,
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Clean Gemini Sidebar */
    [data-testid="stSidebar"] {
        border-right: 1px solid rgba(128, 128, 128, 0.12);
        padding-top: 0.5rem;
    }

    /* Sidebar Buttons (Left-aligned, borderless pill feel like Gemini) */
    [data-testid="stSidebar"] .stButton>button {
        border: none !important;
        background: transparent !important;
        text-align: left !important;
        justify-content: flex-start !important;
        padding: 8px 14px !important;
        border-radius: 20px !important;
        font-size: 14px !important;
        font-weight: 400 !important;
        transition: background 0.15s ease;
    }
    [data-testid="stSidebar"] .stButton>button:hover {
        background: rgba(128, 128, 128, 0.12) !important;
    }

    /* Main Chat Container */
    .main .block-container {
        max-width: 820px;
        padding-top: 2rem;
        padding-bottom: 5rem;
    }

    /* Rounded Gemini Chat Input Pill */
    [data-testid="stChatInput"] {
        border-radius: 28px !important;
        border: 1px solid rgba(128, 128, 128, 0.22) !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06) !important;
    }

    /* Popover buttons at bottom left (+) and bottom right (Model/Thinking) */
    [data-testid="stPopover"] > button {
        border-radius: 22px !important;
        border: 1px solid rgba(128, 128, 128, 0.2) !important;
        padding: 4px 14px !important;
        font-size: 13.5px !important;
        font-weight: 500 !important;
        background: rgba(128, 128, 128, 0.05) !important;
    }
    [data-testid="stPopover"] > button:hover {
        border-color: #F4D018 !important;
        background: rgba(244, 208, 24, 0.1) !important;
    }

    /* NEW: Floating sidebar toggle (top-right) */
    .st-key-toggle_sidebar {
        position: fixed;
        top: 14px;
        right: 20px;
        z-index: 1000002;
        width: auto !important;
    }
    .st-key-toggle_sidebar button {
        border-radius: 50% !important;
        width: 40px;
        height: 40px;
        padding: 0 !important;
        border: 1px solid rgba(128, 128, 128, 0.22) !important;
        background: rgba(128, 128, 128, 0.06) !important;
    }
    .st-key-toggle_sidebar button:hover {
        border-color: #F4D018 !important;
        background: rgba(244, 208, 24, 0.12) !important;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize State Defaults
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "Gemini Flash 3.8"
if "thinking_level" not in st.session_state:
    st.session_state.thinking_level = "Mid"
if "live_search" not in st.session_state:
    st.session_state.live_search = False
if "active_project_id" not in st.session_state:
    st.session_state.active_project_id = None
if "active_project_name" not in st.session_state:
    st.session_state.active_project_name = None

# NEW: Sidebar visibility state
if "sidebar_visible" not in st.session_state:
    st.session_state.sidebar_visible = True

# Ensure an active session exists
if "active_session_id" not in st.session_state:
    existing_general = get_sessions(project_id=None)
    if existing_general:
        st.session_state.active_session_id = existing_general[0][0]
    else:
        st.session_state.active_session_id = create_chat_session("New chat", None)

# ============================================================
# NEW: Sidebar Toggle Button (floating, top-right)
# ============================================================
def toggle_sidebar():
    st.session_state.sidebar_visible = not st.session_state.sidebar_visible

st.button(
    "",
    key="toggle_sidebar",
    icon=":material_left_panel_close:" if st.session_state.sidebar_visible else ":material_left_panel_open:",
    help="Hide sidebar" if st.session_state.sidebar_visible else "Show sidebar",
    on_click=toggle_sidebar,
)

# Hide the sidebar (and its native collapsed control) when toggled off
if not st.session_state.sidebar_visible:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"],
        [data-testid="stSidebarCollapsedControl"] {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# Sidebar (Gemini Layout: Brand -> New Chat -> Projects -> All Chats)
# ============================================================
with st.sidebar:
    # Top Vox Branding Header
    st.markdown(
        f"""
        <div style="display: flex; align-items: center; gap: 11px; padding: 6px 8px 18px 8px;">
            <img src="{LOGO_URI}" width="34" height="34" style="border-radius: 8px;">
            <span style="font-size: 20px; font-weight: 600; letter-spacing: -0.3px;">Vox</span>
            <span style="font-size: 11px; color: gray; background: rgba(128,128,128,0.12); padding: 2px 7px; border-radius: 10px;">Voxathon</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Top "New chat" action (switches▌
