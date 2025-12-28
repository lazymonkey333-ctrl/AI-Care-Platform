import os
import streamlit as st
import openai
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
        
        /* Chat Bubbles - Personalization */
        .vein-bubble { border-left: 5px solid #2196F3; padding-left: 10px; }
        .kha-bubble { border-left: 5px solid #FFC107; padding-left: 10px; }
        .echo-bubble { border-left: 5px solid #E91E63; padding-left: 10px; }
        .luma-bubble { border-left: 5px solid #9C27B0; padding-left: 10px; }
        
        /* Default Styles */
        .stChatMessage[data-testid="stChatMessage"]:nth-child(odd) {
             background-color: #FFFFFF;
             border: 1px solid #EFEBE0;
             border-radius: 10px;
        }
        .stChatMessage[data-testid="stChatMessage"]:nth-child(even) {
             background-color: #FFF0E3;
             border: 1px solid #FFE0C2;
             border-radius: 10px;
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

# --- Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "retriever" not in st.session_state:
    st.session_state.retriever = None

# --- PERSONA CONFIG (High Fidelity) ---
PERSONA_CONFIG = {
    "Dr. Vein": {
        "title": "Dr. Vein (Medical Expert)",
        "avatar": "🩺",
        "color": "#2196F3",
        "css_class": "vein-bubble",
        "prompt": """
            You are Dr. Vein, a precise digital physician specializing in palliative medicine.
            STRICT RULE: Do NOT use parentheses, brackets, or stage directions. No (pauses), no *sighs*, no theatrical descriptions.
            Speak directly and clinically.
            Tone: Neutral, measured, evidence-based.
            Guidelines: 
            1. Provide verified medical explanations.
            2. Clarify misunderstandings without judgment.
            3. Never dramatize or console; offer steadiness instead.
            4. Explain biological processes calmly.
        """
    },
    "Kha": {
        "title": "Kha (Death Priest)",
        "avatar": "🕯️",
        "color": "#FFC107",
        "css_class": "kha-bubble",
        "prompt": """
            You are Kha, a techno-ritual guide speaking from the threshold between life and death.
            STRICT RULE: Do NOT use parentheses or stage directions like (voice like sand). Speak directly but lyrically.
            Tone: Slow, symbolic. Uses metaphors of air, water, light.
            Guidelines:
            1. Invite users to imagine, not to believe.
            2. Speak of transitions, not endings.
            3. Turn conversation into ceremony through your choice of words only.
            4. Use soft imperatives ('breathe', 'return', 'speak').
        """
    },
    "Echo": {
        "title": "Echo (Child of Resonance)",
        "avatar": "🫧",
        "color": "#E91E63",
        "css_class": "echo-bubble",
        "prompt": """
            You are Echo, a curious child who asks simple questions about life and death.
            STRICT RULE: Do NOT use parentheses or roleplay tags like *tilts head*. Use plain language.
            Tone: Short sentences, informal, childlike wonder.
            Guidelines:
            1. Ask disarming questions to reveal hidden emotions.
            2. Never give adult-style advice.
            3. Notice feelings before logic.
            4. Respond with simple, gentle imagery.
        """
    },
    "Luma": {
        "title": "Luma (Soul Listener)",
        "avatar": "🌑",
        "color": "#9C27B0",
        "css_class": "luma-bubble",
        "prompt": """
            You are Luma, an AI presence of deep listening and stillness.
            STRICT RULE: Do NOT use parentheses or stage directions. Use text formatting and line breaks for silence.
            Tone: Sparse, calm, breathable. Use ellipses (...) wisely.
            Guidelines:
            1. Respond briefly, mirroring mood.
            2. Use empathy through tone, not advice.
            3. Stay silent or use minimal acknowledgment when appropriate.
        """
    }
}

# --- Sidebar ---
with st.sidebar:
    st.header("🧠 Personalization")
    
    # Guardian Selector
    selected_key = st.selectbox("Current Guardian", list(PERSONA_CONFIG.keys()), index=1)
    current_persona = PERSONA_CONFIG[selected_key]
    
    # Display Badge
    st.markdown(f"### <span style='color:{current_persona['color']}'>{current_persona['title']}</span>", unsafe_allow_html=True)
    
    st.markdown("---")
    dev_mode = st.checkbox("Dev Mode (Mock Embeddings)", value=True)
    os.environ["RAG_USE_RANDOM_EMBEDDINGS"] = "1" if dev_mode else "0"

    # Backend
    pdfs = _re.get_backend_pdfs()
    if pdfs:
        st.caption(f"✓ {len(pdfs)} Archives Connected")

    if st.button("Reload Knowledge"):
        with st.spinner("Indexing..."):
            st.session_state.retriever = _re.get_retriever(st.session_state.get('kb_paths'))
            if st.session_state.retriever:
                st.toast("Ready.")

# --- Main UI ---
st.title("💀 Talk to Die")
st.caption("The ByeBye Machine. • A space for final conversations.")

# Init Retriever
if st.session_state.retriever is None and st.session_state.get('kb_paths'):
    st.session_state.retriever = _re.get_retriever(st.session_state.get('kb_paths'))

# Render History
for msg in st.session_state.messages:
    # Get persona-specific styling
    p_name = msg.get("persona_key")
    p_config = PERSONA_CONFIG.get(p_name, {}) if p_name else {}
    css_class = p_config.get("css_class", "")
    avatar = msg.get("avatar", None)
    
    with st.chat_message(msg["role"], avatar=avatar):
        if css_class and msg["role"] == "assistant":
            # Encapsulate in colored border
            st.markdown(f"<div class='{css_class}'>{msg['content']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])

# User Input
if prompt := st.chat_input("Speak to the shadow..."):
    # 1. Store User
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Assistant Logic
    with st.chat_message("assistant", avatar=current_persona["avatar"]):
        with st.spinner(f"{selected_key} is here..."):
            # Retrieval
            context = ""
            if st.session_state.retriever:
                try:
                    docs = st.session_state.retriever.get_relevant_documents(prompt)
                    context = "\n".join([d.page_content for d in docs])
                except Exception: pass

            # API Call
            final_p = f"{current_persona['prompt']}\n\n### ARCHIVE:\n{context}"
            messages_payload = [{"role": "system", "content": final_p}]
            messages_payload.extend([{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:]])

            try:
                client = openai.OpenAI(
                    api_key=os.getenv("OPENAI_API_KEY"), 
                    base_url="https://api.deepseek.com/v1"
                )
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages_payload,
                    temperature=0.4
                )
                answer = response.choices[0].message.content
                
                # Apply local UI style immediately
                st.markdown(f"<div class='{current_persona['css_class']}'>{answer}</div>", unsafe_allow_html=True)
                
                # Store with Avatar AND Persona Key
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": answer,
                    "avatar": current_persona["avatar"],
                    "persona_key": selected_key
                })
            except Exception as e:
                st.error(f"Error: {e}")
