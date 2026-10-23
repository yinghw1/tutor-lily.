import os
import base64
import json
import sqlite3
import uuid
from datetime import datetime

import streamlit as st
from openai import OpenAI

# ============================================================
# Vox Mascot Logo (Clean SVG converted to Base64)
# ============================================================
MASCOT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100"><path d="M 50 12 C 55 12, 85 68, 88 74 C 92 82, 84 90, 75 90 L 25 90 C 16 90, 8 82, 12 74 C 15 68, 45 12, 50 12 Z" fill="#FFDC33" stroke="#000000" stroke-width="2.5" stroke-linejoin="round"/><path d="M 38 38 Q 42 36 46 38" stroke="#000000" stroke-width="1.5" stroke-linecap="round" fill="none"/><path d="M 54 38 Q 58 36 62 38" stroke="#000000" stroke-width="1.5" stroke-linecap="round" fill="none"/><circle cx="42" cy="46" r="8" fill="#FFFFFF" stroke="#000000" stroke-width="1"/><circle cx="42" cy="46" r="6" fill="#0099FF"/><circle cx="42" cy="46" r="4.5" fill="#000000"/><circle cx="40" cy="44" r="2" fill="#FFFFFF"/><circle cx="44" cy="47" r="1" fill="#FFFFFF"/><circle cx="58" cy="46" r="8" fill="#FFFFFF" stroke="#000000" stroke-width="1"/><circle cx="58" cy="46" r="6" fill="#0099FF"/><circle cx="58" cy="46" r="4.5" fill="#000000"/><circle cx="56" cy="44" r="2" fill="#FFFFFF"/><circle cx="60" cy="47" r="1" fill="#FFFFFF"/><path d="M 38 54 Q 50 58 62 54 C 63 68, 37 68, 38 54 Z" fill="#8B0000" stroke="#000000" stroke-width="2"/><path d="M 40 54 Q 50 57 60 54" stroke="#FFFFFF" stroke-width="3" fill="none" stroke-linecap="round"/><path d="M 42 63 Q 48 58 55 64 C 52 68, 45 68, 42 63 Z" fill="#FF6688"/></svg>"""

LOGO_B64 = base64.b64encode(MASCOT_SVG.encode("utf-8")).decode("utf-8")

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

def create_chat_session(title="New Chat", project_id=None):
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
    if project_id:
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
        title = clean_text[:28] + "..." if len(clean_text) > 28 else clean_text
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
# Streamlit Page Setup & Custom UI Styling
# ============================================================
st.set_page_config(
    page_title="Voxathon",
    page_icon=f"data:image/svg+xml;base64,{LOGO_B64}",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    [data-testid="stSidebar"] {
        border-right: 1px solid rgba(128, 128, 128, 0.15);
        padding-top: 10px;
    }

    .main .block-container {
        max-width: 860px;
        padding-top: 2rem;
        padding-bottom: 6rem;
    }

    [data-testid="stChatInput"] {
        border-radius: 28px !important;
        border: 1px solid rgba(128, 128, 128, 0.25) !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.06);
    }

    .stButton>button {
        border-radius: 20px;
        border: 1px solid rgba(128, 128, 128, 0.2);
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        border-color: #FFDC33;
        color: #FFDC33;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================
# Sidebar & Navigation
# ============================================================
with st.sidebar:
    st.markdown(
        f"""
        <div style="display: flex; align-items: center; gap: 12px; padding: 10px 0 20px 0;">
            <img src="data:image/svg+xml;base64,{LOGO_B64}" width="45" height="45">
            <div>
                <div style="font-size: 22px; font-weight: 700; letter-spacing: -0.5px; line-height: 1.1;">Vox</div>
                <div style="font-size: 12px; color: gray;">Voxathon AI</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    default_api_key = os.getenv("OPENROUTER_API_KEY", "")
    api_key = st.text_input("OpenRouter API Key", value=default_api_key, type="password", placeholder="sk-or-v1-...")

    selected_model = st.selectbox(
        "AI Model",
        ["GPT 5", "Claude Sonnet 5.5", "Gemini Flash 3.8"]
    )

    mode = st.radio("Mode", ["General Assistant", "Projects Mode"])

current_project_id = None
current_project_name = None

if mode == "General Assistant":
    st.sidebar.markdown("---")
    if st.sidebar.button("➕ New Chat", use_container_width=True):
        new_sid = create_chat_session(title="New Chat", project_id=None)
        st.session_state.active_session_id = new_sid
        st.rerun()

    sessions = get_sessions(project_id=None)
    if not sessions:
        if "active_session_id" not in st.session_state:
            st.session_state.active_session_id = create_chat_session("New Chat", None)
    else:
        session_ids = [s[0] for s in sessions]
        if "active_session_id" not in st.session_state or st.session_state.active_session_id not in session_ids:
            st.session_state.active_session_id = sessions[0][0]
            
        st.sidebar.caption("Past Chats")
        for sid, s_title in sessions:
            is_active = (sid == st.session_state.active_session_id)
            btn_label = f"💬 {s_title}" if is_active else s_title
            if st.sidebar.button(btn_label, key=f"sess_{sid}", use_container_width=True):
                st.session_state.active_session_id = sid
                st.rerun()

else:  # Projects Mode
    st.sidebar.markdown("---")
    st.sidebar.caption("Projects Workspace")
    all_projects = get_all_projects()
    
    with st.sidebar.expander("➕ Create New Project", expanded=not bool(all_projects)):
        new_pname = st.text_input("Project Name", placeholder="e.g. Maglev Research")
        if st.button("Create Project", use_container_width=True) and new_pname.strip():
            pid = get_or_create_project(new_pname.strip())
            st.session_state.current_project_id = pid
            new_sid = create_chat_session(title=f"{new_pname.strip()} Chat", project_id=pid)
            st.session_state.active_session_id = new_sid
            st.rerun()

    if all_projects:
        proj_dict = {p[1]: p[0] for p in all_projects}
        if "current_project_id" not in st.session_state or st.session_state.current_project_id not in proj_dict.values():
            st.session_state.current_project_id = all_projects[0][0]
            
        current_idx = list(proj_dict.values()).index(st.session_state.current_project_id)
        selected_pname = st.sidebar.selectbox("Active Project", list(proj_dict.keys()), index=current_idx)
        current_project_id = proj_dict[selected_pname]
        current_project_name = selected_pname
        st.session_state.current_project_id = current_project_id

        if st.sidebar.button("➕ New Project Chat", use_container_width=True):
            new_sid = create_chat_session(title=f"{current_project_name} Chat", project_id=current_project_id)
            st.session_state.active_session_id = new_sid
            st.rerun()

        proj_sessions = get_sessions(project_id=current_project_id)
        if not proj_sessions:
            st.session_state.active_session_id = create_chat_session(f"{current_project_name} Chat", current_project_id)
            proj_sessions = get_sessions(project_id=current_project_id)
            
        psession_ids = [s[0] for s in proj_sessions]
        if "active_session_id" not in st.session_state or st.session_state.active_session_id not in psession_ids:
            st.session_state.active_session_id = proj_sessions[0][0]

        st.sidebar.caption(f"{current_project_name} Chats")
        for psid, ps_title in proj_sessions:
            is_active = (psid == st.session_state.active_session_id)
            btn_label = f"📂 {ps_title}" if is_active else ps_title
            if st.sidebar.button(btn_label, key=f"psess_{psid}", use_container_width=True):
                st.session_state.active_session_id = psid
                st.rerun()

        memories = get_project_memories(current_project_id)
        with st.sidebar.expander(f"🧠 Project Memory ({len(memories)})"):
            if memories:
                for mem_id, m_fact in memories:
                    col_m1, col_m2 = st.columns([5, 1])
                    col_m1.markdown(f"<small>• {m_fact}</small>", unsafe_allow_html=True)
                    if col_m2.button("✖", key=f"del_mem_{mem_id}"):
                        delete_project_memory(mem_id)
                        st.rerun()
            else:
                st.caption("No memories stored yet. Chat to build project memory automatically!")

# ============================================================
# Main Chat Area
# ============================================================
active_session_id = st.session_state.get("active_session_id")
messages = load_session_messages(active_session_id) if active_session_id else []

if not messages:
    sub_greeting = (
        f"Project Workspace: <b>{current_project_name}</b> — Memory Recall Active"
        if mode == "Projects Mode" and current_project_name
        else "Your general-purpose AI assistant. How can I help you today?"
    )
    st.markdown(
        f"""
        <div style="text-align: center; margin-top: 50px; margin-bottom: 40px;">
            <img src="data:image/svg+xml;base64,{LOGO_B64}" width="80" height="80">
            <h2 style="font-weight: 600; margin-top: 15px;">Hello, I'm Voxathon</h2>
            <p style="color: gray;">{sub_greeting}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

for msg in messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ============================================================
# Bottom Controls: File Uploader & Thinking Level
# ============================================================
col_file, col_thinking = st.columns([3, 2])

with col_file:
    uploaded_file = st.file_uploader(
        "Attach Images, HTML, or Files",
        type=["png", "jpg", "jpeg", "webp", "html", "htm", "txt", "py", "js", "css", "json", "csv", "md"],
        label_visibility="collapsed"
    )

with col_thinking:
    thinking_level = st.select_slider(
        "Thinking Level",
        options=["Low", "Mid", "High"],
        value="Mid"
    )

if prompt := st.chat_input("Ask Vox anything..."):
    if not api_key:
        st.error("Please enter your OpenRouter API key in the sidebar.")
        st.stop()

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://voxathon.streamlit.app",
            "X-Title": "Voxathon AI Assistant",
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
        "You are Voxathon (or Vox for short), a versatile, intelligent, and helpful general-purpose AI assistant."
        + thinking_prompts.get(thinking_level, "")
    )

    if mode == "Projects Mode" and current_project_id:
        memories = get_project_memories(current_project_id)
        mem_str = "\n".join([f"- {m[1]}" for m in memories]) if memories else "No project memories saved yet."
        system_prompt += (
            f"\n\nYou are currently in Projects Mode working on the project: '{current_project_name}'."
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
    model_code = model_map.get(selected_model, "openai/gpt-5")

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""
        
        try:
            stream = client.chat.completions.create(
                model=model_code,
                messages=api_messages,
                stream=True
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

    if mode == "Projects Mode" and current_project_id:
        extract_prompt = (
            "Review the following interaction from a project chat. Extract any important facts, goals, preferences, "
            "technical choices, or project details shared by the user that should be remembered for future chats in this project. "
            "Return ONLY a valid JSON object with a single key 'facts' containing a list of concise strings. "
            "If no new persistent project info was shared, return {\"facts\": []}.\n\n"
            f"User: {prompt}\nAssistant: {full_res}"
        )
        try:
            mem_res = client.chat.completions.create(
                model=model_code,
                messages=[{"role": "user", "content": extract_prompt}],
                response_format={"type": "json_object"}
            )
            raw_json = mem_res.choices[0].message.content
            extracted = json.loads(raw_json).get("facts", [])
            if isinstance(extracted, list):
                for fact in extracted:
                    if isinstance(fact, str) and fact.strip():
                        add_project_memory(current_project_id, fact.strip())
        except Exception:
            pass
