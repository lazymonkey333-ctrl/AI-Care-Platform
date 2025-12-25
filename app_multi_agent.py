import os
import streamlit as st
import openai
from dotenv import load_dotenv
import rag_engine as _re
from datetime import datetime

# Load environment variables
load_dotenv()

# --- Page Configuration ---
# initial_sidebar_state="collapsed" hides the sidebar by default
st.set_page_config(
    page_title="AI Care Platform", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# --- Session State Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "retriever" not in st.session_state:
    st.session_state.retriever = None

# --- Helper: Backend Logger ---
def log_user_query(query, response):
    """Save user queries and AI responses to a backend log file."""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, "chat_history.log")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] USER: {query}\n")
        f.write(f"[{timestamp}] AI  : {response}\n")
        f.write("-" * 50 + "\n")

# --- Sidebar (Hidden by default, used for Backend Stats) ---
with st.sidebar:
    st.header("Backend Status")
    
    # Auto-scan backend data folder
    pdfs = _re.get_backend_pdfs()
    if pdfs:
        st.success(f"✅ Found {len(pdfs)} documents in backend.")
        st.session_state.kb_paths = pdfs
    else:
        st.warning("⚠️ No documents found in 'data/' folder.")
    
    st.markdown("---")
    # Dev mode toggle
    dev_mode = st.checkbox("Dev Mode (Local Embeddings)", value=True)
    os.environ["RAG_USE_RANDOM_EMBEDDINGS"] = "1" if dev_mode else "0"

    if st.button("🔄 Reload Knowledge Base"):
        with st.spinner("Initializing..."):
            st.session_state.retriever = _re.get_retriever(st.session_state.get('kb_paths'))
            if st.session_state.retriever:
                st.success("Knowledge Base Ready")

# --- Main UI ---
st.title("🤖 AI Care Assistant")
st.info("The sidebar is collapsed by default. You can open it using the arrow in the top left if you need to reload the Knowledge Base.")

# Display Chat History (Visual Memory)
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Chat Input
if prompt := st.chat_input("Ask me anything about the healthcare documents..."):
    # Add User Message to State
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing documents..."):
            # 1. Context Retrieval
            context = ""
            if st.session_state.retriever:
                try:
                    docs = st.session_state.retriever.get_relevant_documents(prompt)
                    context = "\n".join([d.page_content for d in docs])
                except Exception as e:
                    st.warning(f"Retrieval Error: {e}")

            # 2. Prepare Messages for API (Providing Memory)
            # We pass the last 5 exchanges to the LLM so it has "memory"
            chat_memory = st.session_state.messages[-10:] # Last 10 messages (5 turns)
            
            system_instruction = "You are a professional healthcare assistant. "
            if context:
                system_instruction += f"Answer based on the following context:\n{context}"
            else:
                system_instruction += "Answer based on your general knowledge."

            api_messages = [{"role": "system", "content": system_instruction}]
            api_messages.extend(chat_memory)

            # 3. Call DeepSeek API
            try:
                client = openai.OpenAI(
                    api_key=os.getenv("OPENAI_API_KEY"), 
                    base_url="https://api.deepseek.com/v1"
                )
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=api_messages,
                    temperature=0.3
                )
                answer = response.choices[0].message.content
                st.write(answer)
                
                # 4. Save to State and Log to Backend
                st.session_state.messages.append({"role": "assistant", "content": answer})
                log_user_query(prompt, answer)
                
            except Exception as e:
                st.error(f"API Error: {e}")
