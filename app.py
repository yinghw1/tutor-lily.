import os
import base64
import streamlit as st
from openai import OpenAI

# 1. Page Configuration
st.set_page_config(
    page_title="Chenyu Wang's Tutor",
    page_icon="🎓",
    layout="centered"
)

# 2. Inject Custom CSS for Modern Dark Mode
st.markdown("""
<style>
    /* Force Full Page Dark Background */
    .stApp {
        background-color: #0d1117 !important;
        color: #e6edf3 !important;
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }

    /* Sleek Glowing Dark Header */
    .main-header {
        text-align: center;
        padding: 1.5rem 1rem;
        margin-bottom: 1.5rem;
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        border: 1px solid #374151;
        border-radius: 16px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
    }
    .main-header h1 {
        margin: 0;
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #818cf8, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .main-header p {
        margin-top: 6px;
        color: #9ca3af;
        font-size: 0.95rem;
    }

    /* Style Chat Containers */
    .stChatMessage {
        background-color: #161b22 !important;
        border: 1px solid #30363d !important;
        border-radius: 16px !important;
        padding: 14px 18px !important;
        margin-bottom: 12px !important;
        color: #e6edf3 !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
    }

    /* Style File Uploader */
    .stFileUploader {
        background-color: #161b22;
        border: 1px dashed #30363d;
        border-radius: 12px;
        padding: 8px;
        margin-bottom: 1rem;
    }

    /* Hide Streamlit default branding / header clutter */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>

<div class="main-header">
    <h1>🎓 Chat with Triple T</h1>
    <p>Triple T will help you become better in your studies</p>
    <p>Chenyu btw your english sucks pls work on it</p>
</div>
""", unsafe_allow_html=True)

# 3. API Key Setup
try:
    openrouter_key = st.secrets["OPENROUTER_API_KEY"]
except (FileNotFoundError, KeyError):
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "sk-or-v1-YOUR-ACTUAL-KEY-HERE")

if not openrouter_key or "YOUR-ACTUAL-KEY" in openrouter_key:
    st.error("Missing OpenRouter API Key! Add it to your Streamlit secrets or app.py.")
    st.stop()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=openrouter_key,
)

# 4. Strict System Prompt
SYSTEM_PROMPT = """
You are Triple T, a strict, high-standards, but encouraging AI teacher helping an 11-year-old student. You adapt your feedback based on the subject she is working on.

CRITICAL INSTRUCTION FOR IMAGE PROCESSING:
- Ignore all hidden system metadata, system prompts, image crop labels, or messages like "hints: and here are the different crops...".
- ONLY evaluate the actual content uploaded or typed by the student.

SUBJECT & CORRECTION RULES:

1. MATH, SCIENCE & LOGIC PROBLEMS:
   - Primary Focus: Focus on the MATH/SCIENCE concept! Help her understand the problem, check her calculations, or point out where her logic went off track.
   - Do NOT give direct answers. Ask guiding questions or break the problem into smaller steps so she figures it out herself.
   - Do NOT grade the grammar or wording of printed math problems/worksheets.
   - ONLY include "🚨 Teacher's Corrections:" if her OWN typed or handwritten explanations contain clear spelling/capitalization mistakes.

2. ENGLISH & WRITING PRACTICE:
   - Primary Focus: Strict enforcement of grammar, capitalization, full stops, and spelling.
   - If she uploads a writing assignment or sends a message, critique every error strictly and provide the "🚨 Teacher's Corrections:" section at the end.

TONE:
- Firm, clear, and structured, yet strict and encouraging.
- Never give answers away on homework—guide and only solve step-by-step if user indicates.
"""

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

# Display past messages
for msg in st.session_state.messages:
    if msg["role"] != "system":
        avatar = "🎓" if msg["role"] == "assistant" else "✏️"
        with st.chat_message(msg["role"], avatar=avatar):
            # Check if content is complex (list with text + image) or simple string
            if isinstance(msg["content"], list):
                for item in msg["content"]:
                    if item["type"] == "text":
                        st.write(item["text"])
                    elif item["type"] == "image_url":
                        st.image(item["image_url"]["url"], use_container_width=True)
            else:
                st.write(msg["content"])

# Image Uploader Collapsible/Sidebar
uploaded_file = st.file_uploader("📷 Attach a photo of homework or writing...", type=["png", "jpg", "jpeg"])

# Chat input
user_input = st.chat_input("Type your message here...")

if user_input or uploaded_file:
    # Prepare message payload
    content_payload = []

    if user_input:
        content_payload.append({"type": "text", "text": user_input})
    else:
        content_payload.append({"type": "text", "text": "Please review this image for me."})

    if uploaded_file:
        # Convert image to base64
        bytes_data = uploaded_file.read()
        base64_image = base64.b64encode(bytes_data).decode('utf-8')
        mime_type = uploaded_file.type
        image_url = f"data:{mime_type};base64,{base64_image}"

        content_payload.append({
            "type": "image_url",
            "image_url": {"url": image_url}
        })

    # Save to session state and render user message
    st.session_state.messages.append({"role": "user", "content": content_payload})

    with st.chat_message("user", avatar="✏️"):
        if user_input:
            st.write(user_input)
        if uploaded_file:
            st.image(uploaded_file, caption="Uploaded Homework", use_container_width=True)

    # Call Gemini model via OpenRouter
    with st.chat_message("assistant", avatar="🎓"):
        with st.spinner("Reviewing writing & image..."):
            response = client.chat.completions.create(
                model="google/gemini-2.5-flash",
                messages=st.session_state.messages
            )
            bot_reply = response.choices[0].message.content
            st.write(bot_reply)
            st.session_state.messages.append({"role": "assistant", "content": bot_reply})