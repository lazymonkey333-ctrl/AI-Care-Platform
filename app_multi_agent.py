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

# --- THEME: WARM CARE (V7 - Bright Pastels & Reliable Colors) ---
def inject_custom_css(active_color):
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600&display=swap');
        
        html, body, [class*="css"] {{
            font-family: 'Nunito', sans-serif;
        }}
        
        .stApp {{
            background-color: #FDFCF8 !important;
        }}
        
        [data-testid="stSidebar"] {{
            background-color: #F6F3E6 !important;
        }}
        
        /* Force Dark Brown Text */
        h1, h2, h3, p, span, .stMarkdown {{
            color: #4A3B32 !important;
        }}
        
        /* PERSONA NAME TAGS - ALWAYS WHITE BACKGROUND */
        .persona-name-tag {{
            font-weight: 700;
            font-size: 0.75em;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            background-color: #ffffff !important;
            padding: 5px 12px;
            border-radius: 8px;
            display: inline-block;
            margin-bottom: 8px;
            border: 2px solid #EFEBE0;
        }}
        
        /* SIDEBAR BUTTONS - GLOBAL OVERRIDE */
        div.stButton > button {{
            height: 56px !important;
            border-radius: 14px !important;
            transition: all 0.2s ease-in-out !important;
            border: 1px solid #E0DBC4 !important;
        }}
        
        /* Inactive Buttons */
        div.stButton > button[data-testid="baseButton-secondary"] {{
            background-color: #ffffff !important;
            color: #B0A69D !important;
            opacity: 0.8;
        }}
        
        /* ACTIVE BUTTON - ELIMINATE RED */
        /* We target the primary button state and its child elements */
        div.stButton > button[data-testid="baseButton-primary"] {{
            border: 2.5px solid {active_color} !important;
            color: {active_color} !important;
            background-color: {active_color}1a !important; /* Soft 10% tint */
            font-weight: 700 !important;
            box-shadow: 0 4px 12px {active_color}33 !important;
        }}
        
        /* Prevent Streamlit Red Hover/Active states */
        div.stButton > button[data-testid="baseButton-primary"]:hover,
        div.stButton > button[data-testid="baseButton-primary"]:focus,
        div.stButton > button[data-testid="baseButton-primary"]:active {{
            border-color: {active_color} !important;
            color: {active_color} !important;
            background-color: {active_color}22 !important;
        }}

        /* Chat History */
        .stChatMessage[data-testid="stChatMessage"] {{
             border-radius: 16px;
             border: 1px solid #EFEBE0;
             margin-bottom: 16px;
             background-color: #ffffff !important;
        }}
        </style>
    """, unsafe_allow_html=True)

# --- Helper: Robust Avatar Generator ---
def generate_avatar_data_uri(content, bg_color, text_color="white", is_user=False):
    if is_user:
        # Drawing a custom person silhouette (CREAM WHITE: #FFFDF5)
        inner_svg = f'''
            <circle cx="32" cy="22" r="10" fill="#FFFDF5" />
            <path d="M12 56 C12 40 52 40 52 56 L52 64 L12 64 Z" fill="#FFFDF5" />
        '''
    else:
        # Standard Emoji rendering for AI
        inner_svg = f'<text x="32" y="44" font-size="34" text-anchor="middle" font-family="Arial" fill="{text_color}">{content}</text>'
        
    svg_code = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">
        <circle cx="32" cy="32" r="30" fill="{bg_color}" />
        {inner_svg}
    </svg>
    """
    b64_encoded = base64.b64encode(svg_code.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64_encoded}"

# --- PERSONA CONFIG (TRUE PASTELS - Brighter & Cleaner) ---
PERSONA_CONFIG = {
    "Dr. Vein (Medical Expert)": {
        "short_name": "Dr. Vein",
        "icon": "🩺",
        "color": "#7FB5D1", # Bright Sky Pastel
        "prompt": "You are Dr. Vein. STRICT: NO PARENTHESES. Speak directly."
    },
    "Kha (Death Priest)": {
        "short_name": "Kha",
        "icon": "🕯️",
        "color": "#D4AC6E", # Warm Golden Sand
        "prompt": "You are Kha. STRICT: NO PARENTHESES. Speak directly."
    },
    "Echo (Resonance Child)": {
        "short_name": "Echo",
        "icon": "✨",
        "color": "#E5A0B0", # Soft Rose Blossom
        "prompt": "You are Echo. STRICT: NO PARENTHESES. Speak directly."
    },
    "Luma (Soul Listener)": {
        "short_name": "Luma",
        "icon": "🌑",
        "color": "#A294C2", # Muted Amethyst
        "prompt": "You are Luma. STRICT: NO PARENTHESES. Speak directly."
    }
}

# Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_persona_key" not in st.session_state:
    st.session_state.selected_persona_key = "Kha (Death Priest)"

# --- INJECT CSS ---
current_persona = PERSONA_CONFIG[st.session_state.selected_persona_key]
inject_custom_css(current_persona["color"])

# Pre-generate Avatars
for key in PERSONA_CONFIG:
    PERSONA_CONFIG[key]["avatar_uri"] = generate_avatar_data_uri(
        PERSONA_CONFIG[key]["icon"], 
        PERSONA_CONFIG[key]["color"]
    )

# --- Sidebar ---
with st.sidebar:
    st.header("🧠 Guardians")
    st.caption("Select your guide:")
    
    for p_key in PERSONA_CONFIG.keys():
        is_active = (st.session_state.selected_persona_key == p_key)
        btn_type = "primary" if is_active else "secondary"
        
        # Use a versioned key to force-refresh DOM
        if st.button(f"{PERSONA_CONFIG[p_key]['icon']}   {p_key}", key=f"p_btn_V7_{p_key}", type=btn_type, use_container_width=True):
            st.session_state.selected_persona_key = p_key
            st.rerun()

    st.markdown("---")
    if st.button("🗑️ Reset Application", key="deep_reset_V7", help="Force clear all cache"):
        st.session_state.clear()
        st.rerun()

# --- Main UI ---
st.title("💀 Talk to Die")
# FIXED SUBTITLE - WILL NOT CHANGE
st.caption("The ByeBye Machine. • Conversations across the boundary.")

# Render History
for msg in st.session_state.messages:
    m_role = msg["role"]
    m_content = msg["content"]
    p_name = msg.get("persona_name")
    p_config = None
    for cfg in PERSONA_CONFIG.values():
        if cfg["short_name"] == p_name:
            p_config = cfg
            break

    avatar = msg.get("avatar_uri", None)
    
    with st.chat_message(m_role, avatar=avatar):
        if m_role == "assistant" and p_config:
            st.markdown(f"<div class='persona-name-tag' style='color:{p_config['color']}'>{p_name}</div>", unsafe_allow_html=True)
            st.markdown(m_content)
        else:
            st.markdown(m_content)

# User Input
if prompt := st.chat_input("Speak to the shadow..."):
    # USER AVATAR: Bright Red (#FF4B4B) + Cream (#FFFDF5)
    user_avatar_uri = generate_avatar_data_uri(None, "#FF4B4B", "#FFFDF5", is_user=True)
    
    st.session_state.messages.append({
        "role": "user", 
        "content": prompt,
        "avatar_uri": user_avatar_uri
    })
    with st.chat_message("user", avatar=user_avatar_uri):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=current_persona["avatar_uri"]):
        st.markdown(f"<div class='persona-name-tag' style='color:{current_persona['color']}'>{current_persona['short_name']}</div>", unsafe_allow_html=True)
        
        with st.spinner(f"{current_persona['short_name']} is here..."):
            refined_system = f"{current_persona['prompt']}\n\nSTRICT: No stage directions or parentheses."
            payload = [{"role": "system", "content": refined_system}]
            payload.extend([{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:]])

            try:
                client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url="https://api.deepseek.com/v1")
                res = client.chat.completions.create(model="deepseek-chat", messages=payload, temperature=0.4)
                ans = res.choices[0].message.content
                st.markdown(ans)
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": ans,
                    "avatar_uri": current_persona["avatar_uri"],
                    "persona_name": current_persona["short_name"]
                })
            except Exception as e:
                st.error(f"Error: {e}")
