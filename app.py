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
# Database Configuration (SQLite)
# ============================================================
DB_FILE = "voxathon_app.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Table for Projects
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Table for Project Memories
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            key_fact TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
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

# Initialize DB on startup
init_db()

# ============================================================
# Streamlit App UI & Setup
# ============================================================
st.set_page_config(page_title="Voxathon AI", page_icon="🤖", layout="wide")

st.title("🤖 Voxathon AI Assistant")

# Sidebar - API Key, Model Selection & Mode Selection
st.sidebar.header("Configuration")
api_key = st.sidebar.text_input("API Key", type="password")

# AI Model Selector (Updated)
selected_model = st.sidebar.selectbox(
    "Select AI Model",
    [
        "GPT-5",
        "Gemini 4",
        "Claude Sonnet 5.5",
        "Gemini 3"
    ]
)

mode = st.sidebar.radio("Select Mode", ["General AI Assistant", "Projects Mode"])

current_project = None
project_id = None

if mode == "Projects Mode":
    st.sidebar.subheader("Project Management")
    existing_projects = get_all_projects()
    
    new_proj_input = st.sidebar.text_input("Create New Project")
    if st.sidebar.button("Add Project") and new_proj_input.strip():
        project_id = get_or_create_project(new_proj_input.strip())
        current_project = new_proj_input.strip()
        st.sidebar.success(f"Created project: {current_project}")
        st.rerun()
        
    if existing_projects:
        current_project = st.sidebar.selectbox("Select Existing Project", existing_projects)
        project_id = get_or_create_project(current_project)
        
        # Display stored memories
        memories = get_project_memories(project_id)
        if memories:
            with st.sidebar.expander("Stored Project Memories"):
                for m in memories:
                    st.write(f"• {m}")

# Initialize Session Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User Input Handling
if prompt := st.chat_input("How can Voxathon help you today?"):
    if not api_key:
        st.error("Please enter your API Key in the sidebar.")
        st.stop()
        
    client = OpenAI(api_key=api_key)

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Base System Prompt for Voxathon General Purpose Assistant
    system_prompt = (
        "You are Voxathon, a helpful, versatile, and friendly general-purpose AI assistant. "
        "Answer questions clearly, provide assistance on a wide array of topics, and maintain a polite tone."
    )

    # Adjust behavior for Projects Mode
    if mode == "Projects Mode" and project_id:
        existing_memories = get_project_memories(project_id)
        memory_context = "\n".join([f"- {m}" for m in existing_memories]) if existing_memories else "None yet."
        
        system_prompt += f"\n\nYou are currently operating in Project Mode for the project named '{current_project}'."
        system_prompt += f"\nHere is the stored memory/context from past interactions in this project:\n{memory_context}"

    api_messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m["role"], "content": m["content"]} for m in st.session_state.messages
    ]

    # Model ID mapping (adjust string identifiers to match your proxy/provider as needed)
    model_mapping = {
        "GPT-5": "gpt-5",
        "Gemini 4": "gemini-4",
        "Claude Sonnet 5.5": "claude-sonnet-5.5",
        "Gemini 3": "gemini-3"
    }
    target_model = model_mapping.get(selected_model, "gpt-5")

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        
        try:
            # Stream AI Response
            response = client.chat.completions.create(
                model=target_model,
                messages=api_messages,
                stream=True
            )
            
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    response_placeholder.markdown(full_response + "▌")
                    
            response_placeholder.markdown(full_response)
        except Exception as e:
            st.error(f"Error calling model '{selected_model}': {e}")
            st.stop()
        
    st.session_state.messages.append({"role": "assistant", "content": full_response})

    # Memory Extraction in Projects Mode
    if mode == "Projects Mode" and project_id:
        extraction_prompt = (
            "Analyze the following user input and assistant response. Extract 1-2 important core facts, preferences, "
            "or project requirements mentioned that should be remembered for future reference in this project. "
            "Return the facts as a JSON list of strings, e.g., [\"User wants to use PostgreSQL\", \"Target audience is developers\"]. "
            "If no key persistent fact was shared, return an empty list [].\n\n"
            f"User: {prompt}\nAssistant: {full_response}"
        )
        
        try:
            extraction_res = client.chat.completions.create(
                model=target_model,
                messages=[{"role": "user", "content": extraction_prompt}],
                response_format={"type": "json_object"}
            )
            data = json.loads(extraction_res.choices[0].message.content)
            facts = data.get("facts", data.get("memories", []))
            
            if isinstance(facts, list):
                for fact in facts:
                    if isinstance(fact, str) and fact.strip():
                        add_project_memory(project_id, fact.strip())
        except Exception:
            pass  # Fail gracefully if memory extraction encounters an error

