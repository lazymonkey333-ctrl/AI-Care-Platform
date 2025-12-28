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
    page_title="AI Care Assistant", 
    page_icon="🤖",
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# --- THEME: WARM CARE (Beige/Cream) ---
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

# --- Session State Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "retriever" not in st.session_state:
    st.session_state.retriever = None

# --- Logger ---
def log_user_query(query, response):
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_file = os.path.join(log_dir, "chat_history.log")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] USER: {query}\n[{timestamp}] AI  : {response}\n" + "-"*30 + "\n")

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Backend KB Scan
    pdfs = _re.get_backend_pdfs()
    if pdfs:
        st.success(f"Backend Ready: {len(pdfs)} docs found.")
        st.session_state.kb_paths = pdfs
    else:
        st.warning("No documents in 'data/' folder.")
    
    st.markdown("---")
    dev_mode = st.checkbox("Dev Mode (Mock Embeddings)", value=True)
    os.environ["RAG_USE_RANDOM_EMBEDDINGS"] = "1" if dev_mode else "0"

    st.markdown("---")
    if st.button("Reload Knowledge Base"):
        with st.spinner("Indexing..."):
            st.session_state.retriever = _re.get_retriever(st.session_state.get('kb_paths'))
            if st.session_state.retriever:
                st.success("Indexing Complete!")

# --- Main UI ---
st.title("🤖 AI Care (Text-Only)")

# Init Retriever if needed
if st.session_state.retriever is None and st.session_state.get('kb_paths'):
    st.session_state.retriever = _re.get_retriever(st.session_state.get('kb_paths'))

# Render Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User Input
if prompt := st.chat_input("Ask a medical question..."):
    # Store user message
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
                    st.warning(f"Retrieval Trace: {e}")

            # 2. Build Prompt
            system_prompt = "You are a professional medical AI assistant. "
            if context:
                system_prompt += f"Use the provided context to answer:\n{context}"
            else:
                system_prompt += "Answer from general knowledge if no context is applicable."

            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(st.session_state.messages[-10:]) # Short memory

            # 3. Call API (DeepSeek)
            # You can also swap this to OpenRouter if DeepSeek fails
            try:
                client = openai.OpenAI(
                    api_key=os.getenv("OPENAI_API_KEY"), 
                    base_url="https://api.deepseek.com/v1" 
                    # Note: If reusing standard OPENAI_KEY for deepseek, make sure it matches. 
                    # If using OpenRouter, change base_url to "https://openrouter.ai/api/v1" and model to "deepseek/deepseek-chat"
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
                log_user_query(prompt, answer)
                
            except Exception as e:
                st.error(f"API Error: {e}")
