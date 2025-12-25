import os
# Force CPU usage
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import streamlit as st
import sys
import openai
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 导入 RAG 引擎
try:
    from rag_engine import get_retriever 
except ImportError:
    pass 

# --- Session State Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "retriever" not in st.session_state:
    st.session_state.retriever = None

# --- Configuration ---
def get_openai_client():
    """配置并返回 OpenAI 客户端 (DeepSeek)"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    
    base_url = os.getenv("OPENAI_API_BASE", "https://api.deepseek.com/v1")
    return openai.OpenAI(api_key=api_key, base_url=base_url)

def configure_openai():
    """旧版配置函数的占位符，用于侧边栏状态检查"""
    return os.getenv("OPENAI_API_KEY") is not None

# --- Streamlit UI Components ---
st.set_page_config(page_title="AI Care Platform", layout="wide")
st.title("🤖 AI Care Platform")
st.markdown("---")

# --- Sidebar for Status and Settings ---
with st.sidebar:
    st.header("Status & Configuration")
    
    # --- API key / KB uploader ---
    st.subheader("0. API Key & Knowledge Base")
    # API key input and save/clear
    saved_key = os.getenv('OPENAI_API_KEY')
    masked = None
    if saved_key:
        masked = saved_key[:4] + '...' + saved_key[-4:]
        st.write(f"Saved API key: {masked}")
        if st.button("Clear saved API key"):
            try:
                # Remove line from .env if present
                if os.path.exists('.env'):
                    with open('.env','r') as f:
                        lines = f.readlines()
                    with open('.env','w') as f:
                        for line in lines:
                            if not line.strip().startswith('OPENAI_API_KEY='):
                                f.write(line)
                os.environ.pop('OPENAI_API_KEY', None)
                st.success('Cleared saved API key')
            except Exception as e:
                st.error(f'Failed to clear .env: {e}')

    api_input = st.text_input("Enter OPENAI_API_KEY (overrides saved key)", type="password", key='api_input')
    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("Save API key to .env"):
            if api_input:
                try:
                    # Replace existing key if present, else append
                    new_line = f'OPENAI_API_KEY={api_input}\n'
                    if os.path.exists('.env'):
                        with open('.env','r') as f:
                            lines = f.readlines()
                        found = False
                        for i,l in enumerate(lines):
                            if l.strip().startswith('OPENAI_API_KEY='):
                                lines[i] = new_line
                                found = True
                                break
                        if not found:
                            lines.append(new_line)
                        with open('.env','w') as f:
                            f.writelines(lines)
                    else:
                        with open('.env','w') as f:
                            f.write(new_line)
                    os.environ['OPENAI_API_KEY'] = api_input
                    st.success('Saved OPENAI_API_KEY to .env')
                except Exception as e:
                    st.error(f'Failed to write .env: {e}')
            else:
                st.warning('No key entered to save.')
    with col2:
        if st.button('Show saved key in session'):
            st.write('Session key:', os.getenv('OPENAI_API_KEY'))

    # KB upload
    uploaded_file = st.file_uploader("Upload KB PDF", type=['pdf'], help="Upload a PDF to use as the knowledge base")
    if uploaded_file is not None:
        uploaded_kb_path = os.path.join(os.getcwd(), "uploaded_kb.pdf")
        with open(uploaded_kb_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Uploaded KB saved to {uploaded_kb_path}")
        st.session_state.kb_path = uploaded_kb_path
    else:
        if 'kb_path' not in st.session_state:
            st.session_state.kb_path = None

    # 1. LLM Status
    st.subheader("1. LLM Status (DeepSeek)")
    if configure_openai():
        st.success("DeepSeek LLM configured (via OpenAI API).")
    else:
        st.warning("LLM configuration incomplete. Enter API key above to enable embeddings.")
        st.info("Tip: For offline testing without an API key, set environment variable RAG_USE_RANDOM_EMBEDDINGS=1 and then Initialize Knowledge Base.")
    
    # 2. RAG Initialization
    st.subheader("2. Knowledge Base Setup")

    dev_mode = st.checkbox("Dev Mode (Local Embeddings)", value=os.getenv("RAG_USE_RANDOM_EMBEDDINGS") == "1", help="Use local random embeddings instead of calling the API. Useful if you get 404 errors.")
    if dev_mode:
        os.environ["RAG_USE_RANDOM_EMBEDDINGS"] = "1"
    else:
        os.environ["RAG_USE_RANDOM_EMBEDDINGS"] = "0"
    
    if 'init_in_progress' not in st.session_state:
        st.session_state.init_in_progress = False

    init_disabled = st.session_state.get('init_in_progress', False)
    if st.button("Initialize Knowledge Base", disabled=init_disabled):
        st.session_state.retriever = None
        st.session_state.messages = []
        st.session_state.init_in_progress = True
        try:
            st.cache_resource.clear()
        except Exception:
            pass

    if 'get_retriever' in globals():
        if st.session_state.retriever is None:
            status_text = "Retriever Initializing (Local)..." if dev_mode else "Retriever Initializing (Embeddings API Call)..."
            with st.spinner(status_text):
                try:
                    # If user uploaded a KB, tell rag_engine to use it
                    try:
                        import rag_engine as _re
                        if st.session_state.get('kb_path'):
                            _re.KB_FILE_PATH = st.session_state.kb_path
                    except Exception:
                        pass

                    st.session_state.retriever = get_retriever()
                    if st.session_state.retriever:
                        st.success("Knowledge Base loaded and Retriever is ready.")
                    else:
                        st.error("Knowledge Base Initialization Failed.")
                except Exception as e:
                    st.error(f"Knowledge Base Error: {e}")
                finally:
                    st.session_state.init_in_progress = False

        elif st.session_state.retriever is not None:
            st.success("Knowledge Base is Active.")
    else:
        st.warning("Skipping Knowledge Base Setup: 'rag_engine.py' import failed.")

st.markdown("## Multi-Turn Q&A")

# --- Chat History Display ---
for message in st.session_state.messages:
    role = message["role"]
    content = message["content"]
    if role == "user":
        st.markdown(f"**You:** {content}")
    else:
        st.markdown(f"**AI:** {content}")

# --- Chat Input and Logic ---
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_input("Ask a question:", key="user_input")
    submit_button = st.form_submit_button(label="Send")

if submit_button and user_input:
    prompt = user_input
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.markdown(f"**You:** {prompt}")

    with st.spinner("Thinking..."):
        try:
            # 1. Retrieve Context if available
            context_text = ""
            if st.session_state.retriever:
                try:
                    # LangChain 0.0.27 retriever.get_relevant_documents
                    docs = st.session_state.retriever.get_relevant_documents(prompt)
                    if docs:
                        context_text = "\n\n".join([f"Source: {doc.metadata.get('source', 'Unknown')}\nContent: {doc.page_content}" for doc in docs])
                except Exception as e:
                    st.warning(f"Retrieval failed: {e}")

            # 2. Construct Messages
            system_prompt = "You are an AI assistant. "
            if context_text:
                system_prompt += f"Use the following context to answer the user's question.\n\nContext:\n{context_text}\n\n"
            else:
                system_prompt += "Answer based on your general knowledge."

            messages = [{"role": "system", "content": system_prompt}]
            
            # Add history (limit to last 10 to avoid token limits)
            for msg in st.session_state.messages[:-1][-10:]:
                messages.append(msg)
            
            messages.append({"role": "user", "content": prompt})

            # 3. Call OpenAI API
            client = get_openai_client()
            if not client:
                st.error("OpenAI client not configured. Please set API Key.")
            else:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    temperature=0.0,
                    stream=False
                )
                
                final_answer = response.choices[0].message.content
                st.markdown(f"**AI:** {final_answer}")
            
            st.session_state.messages.append({"role": "assistant", "content": final_answer})

        except Exception as e:
            error_message = f"An error occurred: {e}"
            st.error(error_message)
            st.session_state.messages.append({"role": "assistant", "content": error_message})
