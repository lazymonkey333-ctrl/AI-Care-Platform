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
        
        /* Tiny Flush Clear Button */
        .clear-btn-container {
            position: fixed;
            bottom: 20px;
            left: 20px;
            width: 80px;
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

# --- PERSONA CONFIG --- (Updated with direct selector titles)
PERSONA_CONFIG = {
    "Dr. Vein (Medical Expert)": {
        "short_name": "Dr. Vein",
        "icon": "🩺",
        "color": "#2196F3",
        "css_class": "vein-bubble",
        "prompt": "You are Dr. Vein, a precise physician. STRICT: NO PARENTHESES. Speak directly."
    },
    "Kha (Death Priest)": {
        "short_name": "Kha",
        "icon": "🕯️",
        "color": "#FFC107",
        "css_class": "kha-bubble",
        "prompt": "You are Kha, a ritual guide. STRICT: NO PARENTHESES. Speak lyrical/symbolic."
    },
    "Echo (Resonance Child)": {
        "short_name": "Echo",
        "icon": "🫧",
        "color": "#E91E63",
        "css_class": "echo-bubble",
        "prompt": "You are Echo, a curious child. STRICT: NO PARENTHESES. Speak directly."
    },
    "Luma (Soul Listener)": {
        "short_name": "Luma",
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
    
    # 1. Guardian Selector (Now shows IDENTITY)
    selected_full_name = st.selectbox("Current Guardian", list(PERSONA_CONFIG.keys()), index=1)
    current_persona = PERSONA_CONFIG[selected_full_name]
    
    st.markdown("---")
    dev_mode = st.checkbox("Dev Mode", value=True)
    os.environ["RAG_USE_RANDOM_EMBEDDINGS"] = "1" if dev_mode else "0"

    # Quiet documents check
    pdfs = _re.get_backend_pdfs()
    if pdfs:
        st.caption(f"✓ {len(pdfs)} Archives Connected")

    # 2. Mini Clear Button at the bottom
    st.markdown("<br>" * 10, unsafe_allow_html=True)
    if st.button("🗑️ Clear Chat", help="Reset conversation state"):
        st.session_state.messages = []
        st.rerun()

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
    p_key = msg.get("persona_name") # The short name we used for display
    p_config = None
    # Find config by checking nested short_names
    for cfg in PERSONA_CONFIG.values():
        if cfg["short_name"] == p_key:
            p_config = cfg
            break

    avatar = msg.get("avatar_uri", None)
    
    with st.chat_message(m_role, avatar=avatar):
        if m_role == "assistant" and p_config:
            st.markdown(f"<div class='persona-name' style='color:{p_config['color']}'>{p_key}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='{p_config['css_class']}'>{m_content}</div>", unsafe_allow_html=True)
        else:
            st.markdown(m_content)

# User Input
if prompt := st.chat_input("Speak to the shadow..."):
    # USER AVATAR: Warm Orange (#FFB74D) instead of grey
    user_avatar_uri = generate_avatar_data_uri("👤", "#FFB74D")
    
    st.session_state.messages.append({
        "role": "user", 
        "content": prompt,
        "avatar_uri": user_avatar_uri
    })
    with st.chat_message("user", avatar=user_avatar_uri):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=current_persona["avatar_uri"]):
        st.markdown(f"<div class='persona-name' style='color:{current_persona['color']}'>{current_persona['short_name']}</div>", unsafe_allow_html=True)
        with st.spinner(f"{current_persona['short_name']} is listening..."):
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
                    "persona_name": current_persona["short_name"]
                })
            except Exception as e:
                st.error(f"Error: {e}")
