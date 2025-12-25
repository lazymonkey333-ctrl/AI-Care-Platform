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
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# --- Session State Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "retriever" not in st.session_state:
    st.session_state.retriever = None

# --- IMPORTANT NOTE ON LOGS ---
# Local logs created on Streamlit Cloud stay on the Cloud Server.
# They DO NOT sync back to GitHub. You can only see them in the 
# Streamlit "Manage App" dashboard or by connecting a database.
def log_user_query(query, response):
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_file = os.path.join(log_dir, "chat_history.log")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] USER: {query}\n[{timestamp}] AI  : {response}\n" + "-"*30 + "\n")

# --- Sidebar (Configuration & Stats) ---
with st.sidebar:
    st.header("System Configuration")
    
    # Backend KB Scan
    pdfs = _re.get_backend_pdfs()
    if pdfs:
        st.success(f"Backend Ready: {len(pdfs)} docs found.")
        st.session_state.kb_paths = pdfs
    else:
        st.warning("No documents in 'data/' folder.")
    
    st.markdown("---")
    dev_mode = st.checkbox("Dev Mode (Use Local Mock Embeddings)", value=True)
    os.environ["RAG_USE_RANDOM_EMBEDDINGS"] = "1" if dev_mode else "0"

    if st.button("Initialize / Reload Knowledge Base"):
        with st.spinner("Processing..."):
            st.session_state.retriever = _re.get_retriever(st.session_state.get('kb_paths'))
            if st.session_state.retriever:
                st.success("Indexing Complete!")

# --- Main UI ---
st.title("🤖 AI Care Assistant")
st.caption("Ask questions about the internal medical documents. The sidebar is collapsed for a cleaner experience.")

# Render Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# User Input
if prompt := st.chat_input("What would you like to know?"):
    # Store user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Consulting knowledge base..."):
            # 1. Retrieve
            context = ""
            if st.session_state.retriever:
                try:
                    docs = st.session_state.retriever.get_relevant_documents(prompt)
                    context = "\n".join([d.page_content for d in docs])
                except Exception as e:
                    st.warning(f"Retrieval Trace: {e}")

            # 2. Build Memory (Last 10 messages)
            system_prompt = "You are a professional medical AI assistant. "
            if context:
                system_prompt += f"Use the provided context to answer:\n{context}"
            else:
                system_prompt += "Answer from general knowledge if no context is applicable."

            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(st.session_state.messages[-10:])

            # 3. Call API
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
                st.write(answer)
                
                # 4. Save and Log
                st.session_state.messages.append({"role": "assistant", "content": answer})
                log_user_query(prompt, answer)
                
            except Exception as e:
                st.error(f"API Error: {e}")
