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
        
        /* Name Header Style */
        .persona-name {
            font-weight: 600;
            font-size: 0.85em;
            margin-bottom: 2px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
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
            width: 100%;
        }
        </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# --- Helper: Robust Colored Circle Avatars ---
def generate_avatar_data_uri(emoji, bg_color):
    svg_code = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">
        <circle cx="32" cy="32" r="30" fill="{bg_color}" />
        <text x="32" y="42" font-size="34" text-anchor="middle" font-family="Arial">{emoji}</text>
    </svg>
    """
    b64_encoded = base64.b64encode(svg_code.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64_encoded}"

# --- Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "retriever" not in st.session_state:
    st.session_state.retriever = None

# --- PERSONA CONFIG ---
PERSONA_CONFIG = {
    "Dr. Vein": {
        "title": "Dr. Vein",
        "icon": "🩺",
        "color": "#2196F3",
        "css_class": "vein-bubble",
        "prompt": "You are Dr. Vein, a precise physician. STRICT: NO PARENTHESES. Speak directly."
    },
    "Kha": {
        "title": "Kha",
        "icon": "🕯️",
        "color": "#FFC107",
        "css_class": "kha-bubble",
        "prompt": "You are Kha, a ritual guide. STRICT: NO PARENTHESES. Speak lyrical/symbolic."
    },
    "Echo": {
        "title": "Echo",
        "icon": "🫧",
        "color": "#E91E63",
        "css_class": "echo-bubble",
        "prompt": "You are Echo, a curious child. STRICT: NO PARENTHESES. Speak directly."
    },
    "Luma": {
        "title": "Luma",
        "icon": "🌑",
        "color": "#9C27B0",
        "css_class": "luma-bubble",
        "prompt": "You are Luma, an AI of stillness. STRICT: NO PARENTHESES. Speak sparse."
    }
}

for key in PERSONA_CONFIG:
    PERSONA_CONFIG[key]["avatar_uri"] = generate_avatar_data_uri(
        PERSONA_CONFIG[key]["icon"], 
        PERSONA_CONFIG[key]["color"]
    )

# --- Sidebar ---
with st.sidebar:
    st.header("🧠 Personalization")
    selected_key = st.selectbox("Guardian", list(PERSONA_CONFIG.keys()), index=1)
    current_persona = PERSONA_CONFIG[selected_key]
    
    st.markdown(f"### <span style='color:{current_persona['color']}'>{selected_key} {current_persona['icon']}</span>", unsafe_allow_html=True)
    
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    dev_mode = st.checkbox("Dev Mode", value=True)
    os.environ["RAG_USE_RANDOM_EMBEDDINGS"] = "1" if dev_mode else "0"

# --- Main UI ---
st.title("💀 Talk to Die")
st.caption("The ByeBye Machine. • A space for final conversations.")

# Init Retriever
if st.session_state.retriever is None and st.session_state.get('kb_paths'):
    st.session_state.retriever = _re.get_retriever(st.session_state.get('kb_paths'))

# Render History
for msg in st.session_state.messages:
    m_role = msg["role"]
    m_content = msg["content"]
    p_key = msg.get("persona_key")
    p_config = PERSONA_CONFIG.get(p_key, {}) if p_key else {}
    avatar = msg.get("avatar_uri", None)
    
    with st.chat_message(m_role, avatar=avatar):
        if m_role == "assistant" and p_key:
            # Added name label next to avatar inside the message
            st.markdown(f"<div class='persona-name' style='color:{p_config['color']}'>{p_key}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='{p_config['css_class']}'>{m_content}</div>", unsafe_allow_html=True)
        else:
            st.markdown(m_content)

# User Input
if prompt := st.chat_input("Speak to the shadow..."):
    user_avatar = generate_avatar_data_uri("👤", "#4A3B32")
    st.session_state.messages.append({
        "role": "user", 
        "content": prompt,
        "avatar_uri": user_avatar
    })
    with st.chat_message("user", avatar=user_avatar):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=current_persona["avatar_uri"]):
        st.markdown(f"<div class='persona-name' style='color:{current_persona['color']}'>{selected_key}</div>", unsafe_allow_html=True)
        with st.spinner(f"{selected_key} is here..."):
            context = ""
            if st.session_state.retriever:
                try:
                    docs = st.session_state.retriever.get_relevant_documents(prompt)
                    context = "\n".join([d.page_content for d in docs])
                except Exception: pass

            refined_system = f"{current_persona['prompt']}\n\nSTRICT: No stage directions or parentheses.\n\n### ARCHIVE:\n{context}"
            payload = [{"role": "system", "content": refined_system}]
            payload.extend([{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:]])

            try:
                client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url="https://api.deepseek.com/v1")
                res = client.chat.completions.create(model="deepseek-chat", messages=payload, temperature=0.4)
                ans = res.choices[0].message.content
                st.markdown(f"<div class='{current_persona['css_class']}'>{ans}</div>", unsafe_allow_html=True)
                
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": ans,
                    "avatar_uri": current_persona["avatar_uri"],
                    "persona_key": selected_key
                })
            except Exception as e:
                st.error(f"Error: {e}")
