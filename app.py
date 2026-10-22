import os
import base64
import json
import sqlite3
import uuid
from datetime import datetime

import streamlit as st
from openai import OpenAI

# ============================================================
# Vox Mascot Logo (Base64 Encoded SVG)
# ============================================================
MASCOT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100"><path d="M 50 12 C 55 12, 85 68, 88 74 C 92 82, 84 90, 75 90 L 25 90 C 16 90, 8 82, 12 74 C 15 68, 45 12, 50 12 Z" fill="#FFDC33" stroke="#000000" stroke-width="2.5" stroke-linejoin="round"/><path d="M 38 38 Q 42 36 46 38" stroke="#000000" stroke-width="1.5" stroke-linecap="round" fill="none"/><path d="M 54 38 Q 58 36 62 38" stroke="#000000" stroke-width="1.5" stroke-linecap="round" fill="none"/><circle cx="42" cy="46" r="8" fill="#FFFFFF" stroke="#000000" stroke-width="1"/><circle cx="42" cy="46" r="6" fill="#0099FF"/><circle cx="42" cy="46" r="4.5" fill="#000000"/><circle cx="40" cy="44" r="2" fill="#FFFFFF"/><circle cx="44" cy="47" r="1" fill="#FFFFFF"/><circle cx="58" cy="46" r="8" fill="#FFFFFF" stroke="#000000" stroke-width="1"/><circle cx="58" cy="46" r="6" fill="#0099FF"/><circle cx="58" cy="46" r="4.5" fill="#000000"/><circle cx="56" cy="44" r="2" fill="#FFFFFF"/><circle cx="60" cy="47" r="1" fill="#FFFFFF"/><path d="M 38 54 Q 50 58 62 54 C 63 68, 37 68, 38 54 Z" fill="#8B0000" stroke="#000000" stroke-width="2"/><path d="M 40 54 Q 50 57 60 54" stroke="#FFFFFF" stroke-width="3" fill="none" stroke-linecap="round"/><path d="M 42 63 Q 48 58 55 64 C 52 68, 45 68, 42 63 Z" fill="#FF6688"/></svg>"""

LOGO_B64 = base64.b64encode(MASCOT_SVG.encode("utf-8")).decode("utf-8")

# ============================================================
# Database Setup
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
    cursor.execute("INSERT INTO project_memories (project_id, key_fact) VALUES (?, ?)", (project_id, fact))
    conn.commit()
    conn.close()

def get_project_memories(project_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT key_fact FROM project_memories WHERE project_id = ? ORDER BY created_at ASC", (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

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
        title = content[:28] + "..." if len(content) > 28 else content
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
    page_title="Vox",
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
        max-width: 850px;
        padding-top: 2rem;
        padding-bottom: 6rem;
    }

    [data-testid="stChatInput"] {
        border-radius: 28px !important;
        border: 1px solid rgba(128, 128, 128, 0.2) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
    }

    .stButton>button {
        border-radius: 20px;
        border: 1px solid rgba(128, 128, 128, 0.2);
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        border-color: #0099FF;
        color: #0099FF;
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
            <img src="data:image/svg+xml;base64,{LOGO_B64}" width="42" height="42">
            <span style="font-size: 22px; font-weight: 600; letter-spacing: -0.5px;">Vox</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    default_api_key = os.getenv("OPENROUTER_API_KEY", "")
    api_key = st.text_input("API Key", value=default_api_key, type="password", placeholder="Enter OpenRouter Key")

    selected_model = st.selectbox(
        "Model",
        ["GPT-5", "Gemini 4", "Claude Sonnet 5.5", "Gemini 3"]
    )

    mode = st.radio("Workspace", ["General Assistant", "Projects Mode"])

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
        if "active_session_id" not in st.session_state:
            st.session_state.active_session_id = sessions[0][0]
            
        session_dict = {s[1]: s[0] for s in sessions}
        st.sidebar.caption("Recent Chats")
        selected_title = st.sidebar.radio(
            "Recent Chats",
            list(session_dict.keys()),
            label_visibility="collapsed"
        )
        st.session_state.active_session_id = session_dict[selected_title]

else:  # Projects Mode
    st.sidebar.markdown("---")
    st.sidebar.caption("Projects")
    all_projects = get_all_projects()
    
    new_pname = st.sidebar.text_input("New Project", placeholder="Project Name")
    if st.sidebar.button("Create Project", use_container_width=True) and new_pname.strip():
        pid = get_or_create_project(new_pname.strip())
        st.session_state.current_project_id = pid
        st.rerun()

    if all_projects:
        proj_dict = {p[1]: p[0] for p in all_projects}
        if "current_project_id" not in st.session_state or st.session_state.current_project_id not in proj_dict.values():
            st.session_state.current_project_id = all_projects[0][0]
            
        selected_pname = st.sidebar.selectbox("Active Project", list(proj_dict.keys()))
        current_project_id = proj_dict[selected_pname]
        current_project_name = selected_pname
        st.session_state.current_project_id = current_project_id

        if st.sidebar.button("➕ New Project Chat", use_container_width=True):
            new_sid = create_chat_session(title=f"{current_project_name} Chat", project_id=current_project_id)
            st.session_state.active_session_id = new_sid
            st.rerun()

        proj_sessions = get_sessions(project_id=current_project_id)
        if not proj_sessions:
            if "active_session_id" not in st.session_state:
                st.session_state.active_session_id = create_chat_session(f"{current_project_name} Chat", current_project_id)
        else:
            psession_dict = {s[1]: s[0] for s in proj_sessions}
            st.sidebar.caption("Project Chats")
            selected_ptitle = st.sidebar.radio(
                "Project Chats",
                list(psession_dict.keys()),
                label_visibility="collapsed"
            )
            st.session_state.active_session_id = psession_dict[selected_ptitle]

        memories = get_project_memories(current_project_id)
        if memories:
            with st.sidebar.expander("🧠 Saved Context"):
                for m in memories:
                    st.markdown(f"• {m}")

# ============================================================
# Main Header & Chat Stream
# ============================================================
active_session_id = st.session_state.get("active_session_id")
messages = load_session_messages(active_session_id) if active_session_id else []

if not messages:
    st.markdown(
        f"""
        <div style="text-align: center; margin-top: 60px; margin-bottom: 40px;">
            <img src="data:image/svg+xml;base64,{LOGO_B64}" width="72" height="72">
            <h2 style="font-weight: 500; margin-top: 15px;">Hello, I'm Vox</h2>
            <p style="color: gray;">How can I help you today?</p>
        </div>
        """,
        unsafe_allow_html=True
    )

for msg in messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ============================================================
# Bottom Controls: File Attachment & Thinking Level
# ============================================================
col_file, col_thinking = st.columns([3, 2])

with col_file:
    uploaded_file = st.file_uploader(
        "Attach files", 
        type=["png", "jpg", "jpeg", "html", "txt", "py", "json", "csv", "md"],
        label_visibility="collapsed"
    )

with col_thinking:
    thinking_level = st.select_slider(
        "Thinking Level",
        options=["Low", "Mid", "High"],
        value="Mid",
        label_visibility="collapsed"
    )

if prompt := st.chat_input("Ask Vox anything..."):
    if not api_key:
        st.error("Please enter your OpenRouter API key in the sidebar.")
        st.stop()

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://voxathon-app.streamlit.app",
            "X-Title": "Vox (Voxathon)",
        }
    )

    # Process file attachment
    file_content_str = ""
    if uploaded_file is not None:
        file_name = uploaded_file.name
        file_ext = file_name.split(".")[-1].lower()
        if file_ext in ["png", "jpg", "jpeg"]:
            file_content_str = f"\n\n[Attached Image: {file_name}]"
        else:
            try:
                string_data = uploaded_file.getvalue().decode("utf-8")
                file_content_str = f"\n\n--- Attached File ({file_name}) ---\n{string_data}\n--------------------------------------"
            except Exception:
                file_content_str = f"\n\n[Attached binary file: {file_name}]"

    combined_prompt = prompt + file_content_str

    save_chat_message(active_session_id, "user", combined_prompt)
    with st.chat_message("user"):
        st.markdown(combined_prompt)

    # Tailor system instruction based on Thinking Level
    thinking_instructions = {
        "Low": " Provide direct, concise, and straight-to-the-point answers with minimal preamble.",
        "Mid": " Provide balanced, accurate, well-reasoned answers with clear logical steps.",
        "High": " Think deeply and exhaustively. Perform rigorous logical analysis, break down step-by-step, and provide comprehensive, highly detailed explanations."
    }

    system_prompt = (
        "You are Vox (full name: Voxathon), a versatile, highly competent, friendly AI assistant."
        + thinking_instructions.get(thinking_level, "")
    )

    if mode == "Projects Mode" and current_project_id:
        memories = get_project_memories(current_project_id)
        mem_str = "\n".join([f"- {m}" for m in memories]) if memories else "No memory recorded yet."
        system_prompt += (
            f"\n\nYou are operating in Project Mode for '{current_project_name}'."
            f"\nHere is the saved long-term project context:\n{mem_str}\n"
            "Use this context naturally when assisting."
        )

    full_chat_history = load_session_messages(active_session_id)
    api_messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m["role"], "content": m["content"]} for m in full_chat_history
    ]

    model_map = {
        "GPT-5": "openai/gpt-4o",
        "Gemini 4": "google/gemini-2.5-flash",
        "Claude Sonnet 5.5": "anthropic/claude-3.5-sonnet",
        "Gemini 3": "google/gemini-flash-1.5"
    }
    model_code = model_map.get(selected_model, "openai/gpt-4o")

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
            "Identify if any persistent fact, decision, preference, or requirement was shared in this turn. "
            "Return JSON: {\"facts\": [\"short fact 1\", \"short fact 2\"]}. If none, return {\"facts\": []}.\n\n"
            f"User: {prompt}\nAssistant: {full_res}"
        )
        try:
            mem_res = client.chat.completions.create(
                model=model_code,
                messages=[{"role": "user", "content": extract_prompt}],
                response_format={"type": "json_object"}
            )
            extracted = json.loads(mem_res.choices[0].message.content).get("facts", [])
            for fact in extracted:
                if isinstance(fact, str) and fact.strip():
                    add_project_memory(current_project_id, fact.strip())
        except Exception:
            pass
