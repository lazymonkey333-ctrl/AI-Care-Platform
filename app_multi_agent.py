import os
import streamlit as st
import openai
import base64
from dotenv import load_dotenv
import rag_engine as _re
from datetime import datetime

# Load environment variables
load_dotenv()

# --- Page Configuration ---
st.set_page_config(
    page_title="Talk to Die", 
    page_icon="💀",
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# --- THEME: WARM CARE ---
def inject_custom_css():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Nunito', sans-serif;
        }
        
        .stApp {
            background-color: #FDFCF8;
        }
        
        [data-testid="stSidebar"] {
            background-color: #F6F3E6;
        }
        
        /* Message Style Extensions */
        .vein-bubble { border-left: 6px solid #2196F3; background-color: #f0f7ff; padding: 12px; border-radius: 0 10px 10px 0; }
        .kha-bubble { border-left: 6px solid #FFC107; background-color: #fffdf0; padding: 12px; border-radius: 0 10px 10px 0; }
        .echo-bubble { border-left: 6px solid #E91E63; background-color: #fff0f5; padding: 12px; border-radius: 0 10px 10px 0; }
        .luma-bubble { border-left: 6px solid #9C27B0; background-color: #f7f0ff; padding: 12px; border-radius: 0 10px 10px 0; }
        
        /* Chat History Bubbles */
        .stChatMessage[data-testid="stChatMessage"]:nth-child(odd) {
             background-color: #FFFFFF;
             border: 1px solid #EFEBE0;
             border-radius: 12px;
        }
        .stChatMessage[data-testid="stChatMessage"]:nth-child(even) {
             background-color: #FFF0E3;
             border: 1px solid #FFE0C2;
             border-radius: 12px;
        }
        
        h1, h2, h3, p { color: #4A3B32; }
        
        div.stButton > button {
            background-color: #FFB74D;
            color: white;
            border: none;
            border-radius: 8px;
        }
        </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# --- Helper: SVG Avatars ---
def generate_avatar(emoji, color):
    # This creates a colored circle with the emoji in the middle
    svg = f'''
    <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
        <rect width="100" height="100" rx="50" fill="{color}" />
        <text x="50%" y="50%" text-anchor="middle" dy=".35em" font-size="55">{emoji}</text>
    </svg>
    '''
    b64 = base64.b64encode(svg.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{b64}"

# --- Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "retriever" not in st.session_state:
    st.session_state.retriever = None

# --- PERSONA CONFIG ---
PERSONA_CONFIG = {
    "Dr. Vein": {
        "title": "Dr. Vein",
        "avatar_icon": "🩺",
        "color": "#2196F3",
        "css": "vein-bubble",
        "prompt": """
            You are Dr. Vein, a precise digital physician.
            STRICT RULE: Do NOT use parentheses, stage directions, or roleplay actions (e.g. *sighs*, (pauses)). Speak directly.
            Tone: Neutral, measured, clinical.
            1. Provide verified medical explanations.
            2. Clarify without judgment.
            3. Never console; offer steadiness.
        """
    },
    "Kha": {
        "title": "Kha",
        "avatar_icon": "🕯️",
        "color": "#FFC107",
        "css": "kha-bubble",
        "prompt": """
            You are Kha, a techno-ritual guide.
            STRICT RULE: Do NOT use parentheses or stage directions. No (voice like sand).
            Tone: Slow, symbolic, lyrical.
            1. Invite imagination over belief.
            2. Speak of transitions.
            3. Use soft imperatives ('breathe', 'return').
        """
    },
    "Echo": {
        "title": "Echo",
        "avatar_icon": "🫧",
        "color": "#E91E63",
        "css": "echo-bubble",
        "prompt": """
            You are Echo, a curious child.
            STRICT RULE: Do NOT use parentheses or roleplay tags. 
            Tone: Short sentences, informal, childlike.
            1. Ask disarming questions about fear/love.
            2. Never give adult-style advice.
            3. Respond with simple, gentle imagery.
        """
    },
    "Luma": {
        "title": "Luma",
        "avatar_icon": "🌑",
        "color": "#9C27B0",
        "css": "luma-bubble",
        "prompt": """
            You are Luma, an AI of stillness.
            STRICT RULE: Do NOT use parentheses or stage directions.
            Tone: Sparse, calm, breathable. Use ellipses (...) and line breaks.
            1. Respond briefly, mirroring mood.
            2. Use empathy through silence/tone.
        """
    }
}

# Pre-generate SVG avatars
for key in PERSONA_CONFIG:
    PERSONA_CONFIG[key]["avatar_url"] = generate_avatar(
        PERSONA_CONFIG[key]["avatar_icon"], 
        PERSONA_CONFIG[key]["color"]
    )

# --- Sidebar ---
with st.sidebar:
    st.header("🧠 Personalization")
    selected_key = st.selectbox("Current Guardian", list(PERSONA_CONFIG.keys()), index=1)
    current_persona = PERSONA_CONFIG[selected_key]
    
    st.markdown(f"### <span style='color:{current_persona['color']}'>{selected_key}</span>", unsafe_allow_html=True)
    st.image(current_persona["avatar_url"], width=60)
    
    st.markdown("---")
    dev_mode = st.checkbox("Dev Mode", value=True)
    os.environ["RAG_USE_RANDOM_EMBEDDINGS"] = "1" if dev_mode else "0"

    pdfs = _re.get_backend_pdfs()
    if pdfs:
        st.caption(f"✓ {len(pdfs)} Archives Connected")

# --- Main UI ---
st.title("💀 Talk to Die")
st.caption("The ByeBye Machine. • A space for final conversations.")

# Init Retriever
if st.session_state.retriever is None and st.session_state.get('kb_paths'):
    st.session_state.retriever = _re.get_retriever(st.session_state.get('kb_paths'))

# Render History
for msg in st.session_state.messages:
    # Logic to fetch styling for stored messages
    p_key = msg.get("persona_key")
    p_config = PERSONA_CONFIG.get(p_key, {}) if p_key else {}
    avatar_url = msg.get("avatar_url", None)
    css_class = p_config.get("css", "")
    
    with st.chat_message(msg["role"], avatar=avatar_url):
        if css_class and msg["role"] == "assistant":
            st.markdown(f"<div class='{css_class}'>{msg['content']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])

# User Input
if prompt := st.chat_input("Speak to the shadow..."):
    # Store User
    user_avatar = generate_avatar("👤", "#4A3B32")
    st.session_state.messages.append({
        "role": "user", 
        "content": prompt, 
        "avatar_url": user_avatar
    })
    with st.chat_message("user", avatar=user_avatar):
        st.markdown(prompt)

    # Assistant Logic
    with st.chat_message("assistant", avatar=current_persona["avatar_url"]):
        with st.spinner(f"{selected_key} is here..."):
            # Retrieval
            context = ""
            if st.session_state.retriever:
                try:
                    docs = st.session_state.retriever.get_relevant_documents(prompt)
                    context = "\n".join([d.page_content for d in docs])
                except Exception: pass

            # API Call
            payload = [{"role": "system", "content": f"{current_persona['prompt']}\n\n### ARCHIVE:\n{context}"}]
            payload.extend([{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:]])

            try:
                client = openai.OpenAI(
                    api_key=os.getenv("OPENAI_API_KEY"), 
                    base_url="https://api.deepseek.com/v1"
                )
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=payload,
                    temperature=0.4
                )
                ans = response.choices[0].message.content
                
                # Render with color bubble
                st.markdown(f"<div class='{current_persona['css']}'>{ans}</div>", unsafe_allow_html=True)
                
                # Store
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": ans,
                    "avatar_url": current_persona["avatar_url"],
                    "persona_key": selected_key
                })
            except Exception as e:
                st.error(f"Error: {e}")
