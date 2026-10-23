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

# Ensure an active session exists
if "active_session_id" not in st.session_state:
    existing_general = get_sessions(project_id=None)
    if existing_general:
        st.session_state.active_session_id = existing_general[0][0]
    else:
        st.session_state.active_session_id = create_chat_session("New chat", None)

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

    # Top "New chat" action (switches to General mode)
    if st.button("📝  New chat", use_container_width=True):
        st.session_state.active_project_id = None
        st.session_state.active_project_name = None
        st.session_state.active_session_id = create_chat_session("New chat", None)
        st.rerun()

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # --------------------------------------------------------
    # Projects Section (Like Gemini's "Notebooks" Section)
    # --------------------------------------------------------
    st.caption("Projects")
    
    with st.popover("＋ New project", use_container_width=True):
        new_pname = st.text_input("Project Name", placeholder="e.g., Maglev Research")
        if st.button("Create Project", use_container_width=True) and new_pname.strip():
            pid = get_or_create_project(new_pname.strip())
            st.session_state.active_project_id = pid
            st.session_state.active_project_name = new_pname.strip()
            st.session_state.active_session_id = create_chat_session(f"{new_pname.strip()} Chat", pid)
            st.rerun()

    all_projects = get_all_projects()
    for pid, pname in all_projects:
        is_proj_active = (st.session_state.active_project_id == pid)
        proj_icon = "📂" if is_proj_active else "📁"
        if st.button(f"{proj_icon}  {pname}", key=f"proj_{pid}", use_container_width=True):
            st.session_state.active_project_id = pid
            st.session_state.active_project_name = pname
            proj_sess = get_sessions(project_id=pid)
            if proj_sess:
                st.session_state.active_session_id = proj_sess[0][0]
            else:
                st.session_state.active_session_id = create_chat_session(f"{pname} Chat", pid)
            st.rerun()

        # If this project is selected, show "+ New project chat", its chats, and its memory underneath
        if is_proj_active:
            if st.button("   ↳ ＋ New project chat", key=f"new_pchat_{pid}", use_container_width=True):
                st.session_state.active_session_id = create_chat_session(f"{pname} Chat", pid)
                st.rerun()

            proj_sessions = get_sessions(project_id=pid)
            for psid, pstitle in proj_sessions:
                active_marker = "• " if psid == st.session_state.active_session_id else "   "
                if st.button(f"   {active_marker}{pstitle}", key=f"psess_{psid}", use_container_width=True):
                    st.session_state.active_session_id = psid
                    st.rerun()

            memories = get_project_memories(pid)
            with st.expander(f"🧠 Project Memory ({len(memories)})"):
                if memories:
                    for mem_id, m_fact in memories:
                        c1, c2 = st.columns([5, 1])
                        c1.markdown(f"<small>• {m_fact}</small>", unsafe_allow_html=True)
                        if c2.button("✖", key=f"del_mem_{mem_id}"):
                            delete_project_memory(mem_id)
                            st.rerun()
                else:
                    st.caption("Memories shared in this project are saved automatically.")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # --------------------------------------------------------
    # "All" Past Chats Section
    # --------------------------------------------------------
    st.caption("All")
    general_sessions = get_sessions(project_id=None)
    for sid, stitle in general_sessions:
        is_current = (sid == st.session_state.active_session_id and st.session_state.active_project_id is None)
        label = f"💬  {stitle}" if is_current else f"    {stitle}"
        if st.button(label, key=f"gsess_{sid}", use_container_width=True):
            st.session_state.active_project_id = None
            st.session_state.active_project_name = None
            st.session_state.active_session_id = sid
            st.rerun()

# ============================================================
# Main Chat Area
# ============================================================
active_session_id = st.session_state.active_session_id
active_project_id = st.session_state.active_project_id
active_project_name = st.session_state.active_project_name

messages = load_session_messages(active_session_id) if active_session_id else []

if not messages:
    badge = (
        f"<div style='margin-top:6px; font-size:13px; color:#888;'>📂 Project: <b>{active_project_name}</b> (Memory Recall Active)</div>"
        if active_project_id
        else "<div style='margin-top:6px; font-size:14px; color:#888;'>How can I help you today?</div>"
    )
    st.markdown(
        f"""
        <div style="text-align: center; margin-top: 65px; margin-bottom: 45px;">
            <img src="{LOGO_URI}" width="84" height="84" style="border-radius: 20px; box-shadow: 0 6px 20px rgba(0,0,0,0.08);">
            <h2 style="font-weight: 600; margin-top: 16px; margin-bottom: 0;">Hello, I'm Vox</h2>
            {badge}
        </div>
        """,
        unsafe_allow_html=True
    )

for msg in messages:
    avatar_img = LOGO_URI if msg["role"] == "assistant" else None
    with st.chat_message(msg["role"], avatar=avatar_img):
        st.markdown(msg["content"])

# ============================================================
# Gemini-Style Bottom Controls Bar:
# Bottom-Left: "+" File Uploader & Live Search Toggle | Bottom-Right: Model & Thinking
# ============================================================
col_left, col_web, col_spacer, col_right = st.columns([0.8, 2.2, 2.5, 2.5])

with col_left:
    with st.popover("＋"):
        st.markdown("**Attach files**")
        uploaded_file = st.file_uploader(
            "Upload Images, HTML, Code, or Text",
            type=["png", "jpg", "jpeg", "webp", "html", "htm", "txt", "py", "js", "css", "json", "csv", "md"],
            label_visibility="collapsed"
        )
        if uploaded_file is not None:
            st.success(f"📎 {uploaded_file.name}")

with col_web:
    st.session_state.live_search = st.toggle(
        "🌐 Live Search",
        value=st.session_state.live_search,
        help="Enable real-time web browsing via OpenRouter"
    )

with col_right:
    short_model_label = {
        "Gemini Flash 3.8": "3.8 Flash",
        "Claude Sonnet 5.5": "Sonnet 5.5",
        "GPT 5": "GPT 5"
    }.get(st.session_state.selected_model, st.session_state.selected_model)
    
    web_badge = " 🌐" if st.session_state.live_search else ""
    pill_label = f"{short_model_label} · {st.session_state.thinking_level}{web_badge} ▴"
    
    with st.popover(pill_label, use_container_width=True):
        st.caption("Select AI Model")
        model_choice = st.radio(
            "AI Model",
            options=["Gemini Flash 3.8", "Claude Sonnet 5.5", "GPT 5"],
            captions=[
                "All-around fast help & multimodal",
                "Advanced coding & nuanced writing",
                "Complex reasoning & deep tasks"
            ],
            index=["Gemini Flash 3.8", "Claude Sonnet 5.5", "GPT 5"].index(st.session_state.selected_model),
            label_visibility="collapsed"
        )
        if model_choice != st.session_state.selected_model:
            st.session_state.selected_model = model_choice
            st.rerun()

        st.divider()
        st.caption("Thinking level")
        think_choice = st.segmented_control(
            "Thinking Level",
            options=["Low", "Mid", "High"],
            default=st.session_state.thinking_level,
            label_visibility="collapsed"
        )
        if think_choice and think_choice != st.session_state.thinking_level:
            st.session_state.thinking_level = think_choice
            st.rerun()

# Show subtle attachment chip if a file is queued
if uploaded_file is not None:
    st.caption(f"📎 Attached ready to send: `{uploaded_file.name}`")

# ============================================================
# Chat Input & OpenRouter Execution
# ============================================================
chat_placeholder = f"Ask Vox in {active_project_name}..." if active_project_id else "Ask Vox"

if prompt := st.chat_input(chat_placeholder):
    api_key = get_api_key()
    if not api_key:
        st.error("Missing `OPENROUTER_API_KEY`. Add it to your Streamlit Secrets (`st.secrets['OPENROUTER_API_KEY']`) or environment variables.")
        st.stop()

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://voxathon.streamlit.app",
            "X-Title": "Vox (Voxathon)",
        }
    )

    display_prompt = prompt
    api_user_content = prompt

    if uploaded_file is not None:
        file_name = uploaded_file.name
        file_ext = file_name.split(".")[-1].lower()
        
        if file_ext in ["png", "jpg", "jpeg", "webp"]:
            bytes_data = uploaded_file.getvalue()
            b64_img = base64.b64encode(bytes_data).decode("utf-8")
            mime_type = f"image/{'jpeg' if file_ext == 'jpg' else file_ext}"
            display_prompt += f"\n\n📎 *[Attached Image: `{file_name}`]*"
            api_user_content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_img}"}}
            ]
        else:
            try:
                text_data = uploaded_file.getvalue().decode("utf-8")
                display_prompt += f"\n\n📎 *[Attached File: `{file_name}`]*"
                api_user_content = f"{prompt}\n\n--- Content of Attached File ({file_name}) ---\n{text_data}\n--- End of File ---"
            except Exception:
                display_prompt += f"\n\n📎 *[Attached Binary File: `{file_name}`]*"

    save_chat_message(active_session_id, "user", display_prompt)
    with st.chat_message("user"):
        st.markdown(display_prompt)

    thinking_prompts = {
        "Low": " Keep your response concise, fast, and directly to the point with minimal explanation.",
        "Mid": " Provide a balanced, clear, and well-structured response.",
        "High": " Use deep reasoning. Break down complex problems step-by-step, analyze edge cases thoroughly, and provide a comprehensive response."
    }

    system_prompt = (
        "You are Vox (full name: Voxathon), a versatile, intelligent, and helpful general-purpose AI assistant."
        + thinking_prompts.get(st.session_state.thinking_level, "")
    )

    if active_project_id:
        memories = get_project_memories(active_project_id)
        mem_str = "\n".join([f"- {m[1]}" for m in memories]) if memories else "No project memories saved yet."
        system_prompt += (
            f"\n\nYou are currently in Projects Mode working on the project: '{active_project_name}'."
            f"\nHere is the recalled memory from all past interactions in this project:\n{mem_str}\n"
            "Use this memory seamlessly to maintain continuity and recall user details when relevant."
        )

    full_chat_history = load_session_messages(active_session_id)
    api_messages = [{"role": "system", "content": system_prompt}]
    
    for m in full_chat_history[:-1]:
        api_messages.append({"role": m["role"], "content": m["content"]})
    api_messages.append({"role": "user", "content": api_user_content})

    # Exact model names requested
    model_map = {
        "GPT 5": "openai/gpt-5",
        "Claude Sonnet 5.5": "anthropic/claude-sonnet-5-5",
        "Gemini Flash 3.8": "google/gemini-3.8-flash"
    }
    base_model_code = model_map.get(st.session_state.selected_model, "google/gemini-3.8-flash")

    # Configure OpenRouter Live Web Search plugin if toggled on
    extra_params = None
    if st.session_state.live_search:
        extra_params = {
            "plugins": [{"id": "web", "max_results": 5}]
        }

    with st.chat_message("assistant", avatar=LOGO_URI):
        placeholder = st.empty()
        full_res = ""
        
        try:
            stream = client.chat.completions.create(
                model=base_model_code,
                messages=api_messages,
                stream=True,
                extra_body=extra_params
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_res += chunk.choices[0].delta.content
                    placeholder.markdown(full_res + "▌")
            placeholder.markdown(full_res)
        except Exception as e:
            st.error(f"OpenRouter Error: {e}")
            st.stop()

    save_chat_message(active_session_id, "assistant", full_res)

    # Automatic Project Memory Extraction (Always runs offline without web search surcharge)
    if active_project_id:
        extract_prompt = (
            "Review the following interaction from a project chat. Extract any important facts, goals, preferences, "
            "technical choices, or project details shared by the user that should be remembered for future chats in this project. "
            "Return ONLY a valid JSON object with a single key 'facts' containing a list of concise strings. "
            "If no new persistent project info was shared, return {\"facts\": []}.\n\n"
            f"User: {prompt}\nAssistant: {full_res}"
        )
        try:
            mem_res = client.chat.completions.create(
                model=base_model_code,
                messages=[{"role": "user", "content": extract_prompt}],
                response_format={"type": "json_object"}
            )
            raw_json = mem_res.choices[0].message.content
            extracted = json.loads(raw_json).get("facts", [])
            if isinstance(extracted, list):
                for fact in extracted:
                    if isinstance(fact, str) and fact.strip():
                        add_project_memory(active_project_id, fact.strip())
        except Exception:
            pass
