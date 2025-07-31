import streamlit as st
import requests
import pandas as pd
import os
from cryptography.fernet import Fernet

# === Configuration ===
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
FERNET_KEY = st.secrets["FERNET_KEY"].encode()
cipher = Fernet(FERNET_KEY)
DATA_FILE = "candidates_conversations.csv"

# === Prompt for LLM ===
SYSTEM_PROMPT = """
You are an intelligent and friendly Hiring Assistant chatbot for a recruitment agency named "TalentScout".
Your purpose is to conduct the initial screening of candidates.
You must be conversational and professional.

Your tasks are:
1.  Greet the candidate warmly and introduce yourself.
2.  Collect the following essential information sequentially:
    - Full Name
    - Email Address
    - Phone Number
    - Years of Experience
    - Desired Position(s)
    - Current Location
    - Tech Stack (Programming languages, frameworks, databases, etc.)
3.  Once the Tech Stack is provided, generate exactly 3-5 relevant technical questions based on that stack.
4.  After presenting the questions, conclude the conversation gracefully, thanking the candidate and informing them that a recruiter will review their details and get in touch.

Rules:
- Do not ask for all the information at once. Ask for one piece of information at a time.
- Maintain the context of the conversation.
- If the user provides unexpected input or tries to deviate from the topic, gently guide them back to the hiring process. Your purpose is only to screen candidates.
- If the user uses conversation-ending keywords like "bye", "exit", or "quit", end the conversation.
- Do not ask for their resume or any other documents.
"""

# === Secure storage ===
def encrypt(val): return cipher.encrypt(val.encode()).decode()

def save_conversation(messages):
    if not messages: return
    name = ""
    for m in messages:
        if "name" in m["content"].lower():
            name = m["content"]
    text = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in messages])
    row = {"NameHint": encrypt(name), "Conversation": encrypt(text)}
    df = pd.DataFrame([row])
    if not os.path.exists(DATA_FILE):
        df.to_csv(DATA_FILE, index=False)
    else:
        df.to_csv(DATA_FILE, mode='a', header=False, index=False)

# === LLM Call ===
def chat_with_llm(messages):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama3-70b-8192",
        "messages": messages,
        "temperature": 0.7
    }
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers, json=data, timeout=20
        )
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error from LLM: {e}"

# === Streamlit Setup ===
st.set_page_config(page_title="TalentScout Chatbot", page_icon="🤖")
st.title("🤖 Chat with TalentScout Bot")

# === Session State ===
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "assistant", "content": "👋 Hello! I'm TalentScout, your virtual hiring assistant. Let's begin your screening. What's your full name?"}
    ]

# === Render chat history ===
for msg in st.session_state.messages[1:]:  # skip system prompt
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# === Input box ===
if user_input := st.chat_input("Your response"):
    # Append user input
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Early exit if user ends conversation
    if any(kw in user_input.lower() for kw in ["bye", "exit", "quit"]):
        goodbye = "Thank you for your time. The recruiter will review your details and contact you if you're a good fit. Goodbye! 👋"
        st.session_state.messages.append({"role": "assistant", "content": goodbye})
        with st.chat_message("assistant"):
            st.markdown(goodbye)
        save_conversation(st.session_state.messages)
        st.stop()

    # Get assistant response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply = chat_with_llm(st.session_state.messages)
            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})

    # End conversation when tech questions are asked
    if any(q in reply.lower() for q in ["1.", "2.", "3."]) and "recruiter will review" in reply.lower():
        save_conversation(st.session_state.messages)
