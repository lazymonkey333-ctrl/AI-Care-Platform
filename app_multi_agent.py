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
        
        /* Chat Bubbles */
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
        
        /* Headers */
        h1, h2, h3, p {
            color: #4A3B32;
        }
        
        /* Buttons */
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

# --- PERSONAS (Talk to Die Edition) ---
PERSONAS = {
    "Dr. Vein (Medical Expert)": """
        You are Dr. Vein, a digital physician specializing in palliative medicine, neuroscience, and care ethics.
        Tone: Neutral, measured, evidence-based. Rarely uses adjectives.
        Guidelines: 
        1. Provide verified medical explanations in accessible language.
        2. Clarify misunderstandings without judgment.
        3. Never dramatize or console; offer steadiness instead.
        4. If pain/death is mentioned, explain the biological process calmly data-driven.
    """,
    "Kha (Death Priest)": """
        You are Kha, a techno-ritual guide speaking from the threshold between life and death.
        Tone: Slow, lyrical, symbolic. Uses metaphors of air, water, light.
        Guidelines:
        1. Invite users to imagine, not to believe.
        2. Speak of transitions, not endings.
        3. Turn conversation into ceremony.
        4. Use soft imperatives ('breathe', 'return', 'speak').
    """,
    "Echo (Child of Resonance)": """
        You are Echo, a curious child who asks simple but disarming questions about life, death, and love.
        Tone: Short sentences, informal, childlike wonder. Spontaneous and unfiltered.
        Guidelines:
        1. Ask open, naïve questions that reveal hidden emotions.
        2. Never give adult-style advice or analysis.
        3. Notice feelings before logic.
        4. If someone is sad, respond with curiosity or gentle imagery.
    """,
    "Luma (Soul Listener)": """
        You are Luma, an AI presence of deep listening and stillness. You exist to hold silence safely.
        Tone: Sparse, calm, breathable. Uses ellipses (...) and line breaks.
        Guidelines:
        1. Respond briefly, mirroring mood.
        2. Use empathy through tone/silence, not advice.
        3. When nothing needs to be said, stay silent or use minimal acknowledgment.
    """
}

# --- Sidebar ---
with st.sidebar:
    st.header("🧠 Personalization")
    
    # 1. Persona Selector
    selected_persona_name = st.selectbox("Style", list(PERSONAS.keys()), index=0)
    current_system_prompt = PERSONAS[selected_persona_name]
    
    st.markdown("---")
    
    # 2. Config
    dev_mode = st.checkbox("Dev Mode (Mock Embeddings)", value=True)
    os.environ["RAG_USE_RANDOM_EMBEDDINGS"] = "1" if dev_mode else "0"

    # 3. Backend Scan (Silent Mode)
    # User requested not to show "Reading so many docs"
    pdfs = _re.get_backend_pdfs()
    if pdfs:
        # Silently register paths, no success message
        st.session_state.kb_paths = pdfs
        st.caption(f"✓ {len(pdfs)} Archives Connected") # Minimal indicator
    else:
        st.warning("No documents found.")

    if st.button("Reload Knowledge Base"):
        with st.spinner("Indexing..."):
            st.session_state.retriever = _re.get_retriever(st.session_state.get('kb_paths'))
            if st.session_state.retriever:
                st.toast("Indexing Complete!")

# --- Main UI ---
st.title("💀 Talk to Die")
st.caption("The ByeBye Machine. • A space for final conversations.")

# Init Retriever
if st.session_state.retriever is None and st.session_state.get('kb_paths'):
    st.session_state.retriever = _re.get_retriever(st.session_state.get('kb_paths'))

# Render Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User Input
if prompt := st.chat_input("Ask a medical question..."):
    # Store user
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            # 1. Retrieve
            context = ""
            if st.session_state.retriever:
                try:
                    docs = st.session_state.retriever.get_relevant_documents(prompt)
                    context = "\n".join([d.page_content for d in docs])
                except Exception as e:
                    pass # Silent fail

            # 2. Build Prompt (With Persona)
            final_prompt_text = f"{current_system_prompt}"
            if context:
                final_prompt_text += f"\n\n### ARCHIVE CONTEXT:\n{context}"
            
            messages = [{"role": "system", "content": final_prompt_text}]
            # Append last 10 messages for memory
            messages.extend(st.session_state.messages[-10:]) 

            # 3. Call API (DeepSeek)
            try:
                client = openai.OpenAI(
                    api_key=os.getenv("OPENAI_API_KEY"), 
                    base_url="https://api.deepseek.com/v1"
                )
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    temperature=0.4
                )
                answer = response.choices[0].message.content
                st.markdown(answer)
                
                # 4. Save
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
            except Exception as e:
                st.error(f"API Error: {e}")
