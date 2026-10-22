import os
import base64
import json
import sqlite3
from datetime import datetime

import streamlit as st
from openai import OpenAI

# ============================================================
# Logo (Voxathon mascot, transparent background) as base64
# ============================================================
LOGO_B64 = "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"

# ============================================================
# Database Setup (SQLite for Projects, Memory, and Past Chats)
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
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        project_id = row[0]
    else:
        cursor.execute("INSERT INTO projects (name) VALUES (?)", (project_name,))
        conn.commit()
        project_id = cursor.lastrowid
    conn.close()
    return project_id

def get_all_projects():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM projects ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

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

def save_chat_message(role, content, project_id=None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_history (project_id, role, content) VALUES (?, ?, ?)", (project_id, role, content))
    conn.commit()
    conn.close()

def load_chat_history(project_id=None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if project_id:
        cursor.execute("SELECT role, content FROM chat_history WHERE project_id = ? ORDER BY id ASC", (project_id,))
    else:
        cursor.execute("SELECT role, content FROM chat_history WHERE project_id IS NULL ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]

def clear_chat_history(project_id=None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if project_id:
        cursor.execute("DELETE FROM chat_history WHERE project_id = ?", (project_id,))
    else:
        cursor.execute("DELETE FROM chat_history WHERE project_id IS NULL")
    conn.commit()
    conn.close()

init_db()

# ============================================================
# Streamlit App UI & Layout
# ============================================================
st.set_page_config(page_title="Voxathon AI Assistant", page_icon="🤖", layout="wide")

# Main Header Logo + Title
st.markdown(
    f"""
    <div style="display: flex; align-items: center; gap: 20px; margin-bottom: 20px;">
        <img src="data:image/png;base64,{LOGO_B64}" width="90" style="object-fit: contain;">
        <div>
            <h1 style="margin: 0;">Voxathon AI Assistant</h1>
            <p style="margin: 0; color: #666;">General-Purpose Intelligent Workspace</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# Sidebar
st.sidebar.markdown(
    f"""
    <div style="text-align: center; margin-bottom: 15px;">
        <img src="data:image/png;base64,{LOGO_B64}" width="120" style="object-fit: contain;">
    </div>
    """,
    unsafe_allow_html=True
)
st.sidebar.title("Voxathon Panel")

# Load API Key securely from Env / Secrets if present, or let user input manually
default_key = os.getenv("OPENROUTER_API_KEY", "")
api_key = st.sidebar.text_input("OpenRouter API Key", value=default_key, type="password")

selected_model = st.sidebar.selectbox(
    "AI Model",
    ["GPT-5", "Gemini 4", "Claude Sonnet 5.5", "Gemini 3"]
)

mode = st.sidebar.radio("Mode", ["General AI Assistant", "Projects Mode"])

current_project = None
project_id = None

if mode == "Projects Mode":
    st.sidebar.markdown("---")
    st.sidebar.subheader("Projects")
    existing_projects = get_all_projects()
    
    new_proj = st.sidebar.text_input("New Project Name")
    if st.sidebar.button("Create Project") and new_proj.strip():
        project_id = get_or_create_project(new_proj.strip())
        current_project = new_proj.strip()
        st.session_state.current_project = current_project
        st.session_state.project_id = project_id
        st.sidebar.success(f"Created: {current_project}")
        st.rerun()
        
    if existing_projects:
        current_project = st.sidebar.selectbox("Active Project", existing_projects)
        project_id = get_or_create_project(current_project)
        st.session_state.current_project = current_project
        st.session_state.project_id = project_id

        # Show memories
        memories = get_project_memories(project_id)
        if memories:
            with st.sidebar.expander("📌 Project Memories / Recalls"):
                for fact in memories:
                    st.markdown(f"- {fact}")

st.sidebar.markdown("---")
if st.sidebar.button("Clear Current Chat"):
    clear_chat_history(project_id if mode == "Projects Mode" else None)
    st.session_state.messages = []
    st.rerun()

# Sync Messages with Database History
target_pid = project_id if mode == "Projects Mode" else None
if "last_pid" not in st.session_state or st.session_state.last_pid != target_pid or "messages" not in st.session_state:
    st.session_state.messages = load_chat_history(target_pid)
    st.session_state.last_pid = target_pid

# Display Past & Current Messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User Chat Action
if prompt := st.chat_input("Ask Voxathon anything..."):
    if not api_key:
        st.error("Please enter your OpenRouter API Key in the sidebar.")
        st.stop()
        
    # OpenRouter API Integration setup using OpenAI client
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://voxathon-app.streamlit.app",
            "X-Title": "Voxathon AI Assistant",
        }
    )

    # Render User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    save_chat_message("user", prompt, target_pid)
    with st.chat_message("user"):
        st.markdown(prompt)

    # Base System Prompt (Voxathon AI Assistant)
    system_prompt = (
        "You are Voxathon, a versatile, highly competent, friendly general-purpose AI assistant. "
        "Provide thorough, clear, accurate, and structured answers."
    )

    if mode == "Projects Mode" and project_id:
        memories = get_project_memories(project_id)
        mem_str = "\n".join([f"- {m}" for m in memories]) if memories else "No memory recorded yet."
        system_prompt += (
            f"\n\nYou are operating in Project Mode for the project '{current_project}'."
            f"\nHere is the accumulated long-term memory for this project:\n{mem_str}\n"
            "Use this recalled context naturally when answering the user."
        )

    api_messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m["role"], "content": m["content"]} for m in st.session_state.messages
    ]

    # Map selected model name to OpenRouter model IDs
    model_map = {
        "GPT-5": "openai/gpt-5",
        "Gemini 4": "google/gemini-2.5-flash",  # Update to your target OpenRouter ID string
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
            st.error(f"OpenRouter Connection Error: {e}")
            st.stop()

    st.session_state.messages.append({"role": "assistant", "content": full_res})
    save_chat_message("assistant", full_res, target_pid)

    # Extract Memory for Projects Mode
    if mode == "Projects Mode" and project_id:
        extract_prompt = (
            "Identify if any persistent fact, decision, preference, or critical project context was shared in this exchange. "
            "Return a JSON object with a key 'facts' containing a list of strings (1-2 sentences max each). "
            "If nothing key was shared, return {\"facts\": []}.\n\n"
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
                    add_project_memory(project_id, fact.strip())
        except Exception:
            pass
