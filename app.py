import os
import json
import sqlite3
import uuid
from datetime import datetime

import streamlit as st
from openai import OpenAI

# ============================================================
# Logo (Clean Voxathon SVG Mascot - Transparent Background)
# ============================================================
LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <circle cx="50" cy="50" r="45" fill="#4F46E5" />
  <circle cx="35" cy="40" r="8" fill="#FFFFFF" />
  <circle cx="65" cy="40" r="8" fill="#FFFFFF" />
  <circle cx="35" cy="40" r="4" fill="#1E1B4B" />
  <circle cx="65" cy="40" r="4" fill="#1E1B4B" />
  <path d="M 30 65 Q 50 80 70 65" stroke="#FFFFFF" stroke-width="5" stroke-linecap="round" fill="none" />
</svg>"""

# ============================================================
# Database Setup (SQLite for Projects, Memory, Sessions & Chats)
# ============================================================
DB_FILE = "voxathon_app.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Projects Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Project Memory Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            key_fact TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)
    
    # Chat Sessions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id TEXT PRIMARY KEY,
            project_id INTEGER NULL,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Chat History Messages Table
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

# Database Functions
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
    
    # Auto-update session title based on first prompt
    cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id = ?", (session_id,))
    count = cursor.fetchone()[0]
    if count == 1 and role == "user":
        title = content[:25] + "..." if len(content) > 25 else content
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
# Streamlit App UI & Setup
# ============================================================
st.set_page_config(page_title="Voxathon AI Assistant", page_icon="🤖", layout="wide")

# Main Header
col_logo, col_title = st.columns([1, 8])
with col_logo:
    st.markdown(LOGO_SVG, unsafe_allow_html=True)
with col_title:
    st.title("Voxathon AI Assistant")
    st.caption("General-Purpose Intelligent Workspace")

# Sidebar Configuration
st.sidebar.markdown(f"<div style='text-align: center; margin-bottom: 10px;'>{LOGO_SVG}</div>", unsafe_allow_html=True)
st.sidebar.title("Voxathon Navigation")

# OpenRouter API Key Input (Masked, optional environment variable fallback)
default_api_key = os.getenv("OPENROUTER_API_KEY", "")
api_key = st.sidebar.text_input("OpenRouter API Key", value=default_api_key, type="password")

selected_model = st.sidebar.selectbox(
    "AI Model",
    ["GPT-5", "Gemini 4", "Claude Sonnet 5.5", "Gemini 3"]
)

# Navigation Mode Selection
mode = st.sidebar.radio("Workspace Mode", ["General AI Assistant", "Projects Mode"])

current_project_id = None
current_project_name = None

# Sidebar Handling: General Assistant vs Projects Mode
if mode == "General AI Assistant":
    st.sidebar.markdown("---")
    if st.sidebar.button("➕ New Chat", use_container_width=True):
        new_sid = create_chat_session(title="New Chat", project_id=None)
        st.session_state.active_session_id = new_sid
        st.rerun()

    st.sidebar.subheader("Past Chats")
    sessions = get_sessions(project_id=None)
    
    if not sessions:
        if "active_session_id" not in st.session_state:
            st.session_state.active_session_id = create_chat_session("New Chat", None)
    else:
        if "active_session_id" not in st.session_state:
            st.session_state.active_session_id = sessions[0][0]
            
        session_dict = {s[1]: s[0] for s in sessions}
        selected_title = st.sidebar.radio(
            "Select Session:",
            list(session_dict.keys()),
            index=0 if st.session_state.active_session_id not in session_dict.values() else list(session_dict.values()).index(st.session_state.active_session_id)
        )
        st.session_state.active_session_id = session_dict[selected_title]

else: # Projects Mode
    st.sidebar.markdown("---")
    st.sidebar.subheader("Projects Workspace")
    all_projects = get_all_projects()
    
    # Create New Project
    new_pname = st.sidebar.text_input("Create Project Name")
    if st.sidebar.button("Add Project") and new_pname.strip():
        pid = get_or_create_project(new_pname.strip())
        st.session_state.current_project_id = pid
        st.sidebar.success(f"Project '{new_pname.strip()}' created!")
        st.rerun()

    if all_projects:
        proj_dict = {p[1]: p[0] for p in all_projects}
        if "current_project_id" not in st.session_state or st.session_state.current_project_id not in proj_dict.values():
            st.session_state.current_project_id = all_projects[0][0]
            
        selected_pname = st.sidebar.selectbox("Active Project", list(proj_dict.keys()))
        current_project_id = proj_dict[selected_pname]
        current_project_name = selected_pname
        st.session_state.current_project_id = current_project_id

        # New Project Chat Button
        if st.sidebar.button("➕ New Project Chat", use_container_width=True):
            new_sid = create_chat_session(title=f"{current_project_name} Chat", project_id=current_project_id)
            st.session_state.active_session_id = new_sid
            st.rerun()

        st.sidebar.markdown("**Project Chats**")
        proj_sessions = get_sessions(project_id=current_project_id)
        
        if not proj_sessions:
            if "active_session_id" not in st.session_state or get_sessions(project_id=current_project_id) == []:
                st.session_state.active_session_id = create_chat_session(f"{current_project_name} Chat", current_project_id)
        else:
            psession_dict = {s[1]: s[0] for s in proj_sessions}
            selected_ptitle = st.sidebar.radio(
                "Select Project Session:",
                list(psession_dict.keys())
            )
            st.session_state.active_session_id = psession_dict[selected_ptitle]

        # Display Project Long-term Memories
        memories = get_project_memories(current_project_id)
        if memories:
            with st.sidebar.expander("📌 Recalled Project Memories"):
                for m in memories:
                    st.markdown(f"- {m}")

# Fetch active messages
active_session_id = st.session_state.get("active_session_id")
messages = load_session_messages(active_session_id) if active_session_id else []

# Display Active Conversation
for msg in messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User Chat Input
if prompt := st.chat_input("How can Voxathon help you today?"):
    if not api_key:
        st.error("Please provide an OpenRouter API Key in the sidebar.")
        st.stop()

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://voxathon-app.streamlit.app",
            "X-Title": "Voxathon AI Assistant",
        }
    )

    # Save and display user query
    save_chat_message(active_session_id, "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    # Base System Prompt
    system_prompt = (
        "You are Voxathon, a versatile, highly competent, friendly general-purpose AI assistant. "
        "Provide thorough, clear, accurate, and structured answers."
    )

    if mode == "Projects Mode" and current_project_id:
        memories = get_project_memories(current_project_id)
        mem_str = "\n".join([f"- {m}" for m in memories]) if memories else "No memory recorded yet."
        system_prompt += (
            f"\n\nYou are operating in Project Mode for the project '{current_project_name}'."
            f"\nHere is the accumulated long-term memory for this project:\n{mem_str}\n"
            "Use this recalled context naturally when answering the user."
        )

    # Load updated message stream for API context
    full_chat_history = load_session_messages(active_session_id)
    api_messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m["role"], "content": m["content"]} for m in full_chat_history
    ]

    model_map = {
        "GPT-5": "openai/gpt-5",
        "Gemini 4": "google/gemini-2.5-flash",
        "Claude Sonnet 5.5": "anthropic/claude-3.5-sonnet",
        "Gemini 3": "google/gemini-pro"
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

    # Extract memory when in Projects Mode
    if mode == "Projects Mode" and current_project_id:
        extract_prompt = (
            "Identify if any persistent fact, decision, preference, or critical project requirement was shared in this turn. "
            "Return a JSON object with a key 'facts' containing a list of short string summaries. "
            "If nothing persistent was shared, return {\"facts\": []}.\n\n"
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
