import os
import streamlit as st
import openai
from dotenv import load_dotenv
import rag_engine as _re

load_dotenv()

# --- 初始化状态 ---
if "messages" not in st.session_state: st.session_state.messages = []
if "retriever" not in st.session_state: st.session_state.retriever = None

st.set_page_config(page_title="AI Care Private Platform", layout="wide")
st.title("🛡️ AI Care - 私有知识库平台")

with st.sidebar:
    st.header("后台状态")
    
    # 自动扫描 data 文件夹
    pdfs = _re.get_backend_pdfs()
    if pdfs:
        st.success(f"✅ 已检测到 {len(pdfs)} 份后台文献")
        st.session_state.kb_paths = pdfs
    else:
        st.warning("⚠️ data 文件夹中未发现 PDF")
        st.info("提示：请在 GitHub 的 data/ 目录下上传文件")
    
    st.markdown("---")
    dev_mode = st.checkbox("开发测试模式 (不消耗 Token)", value=True)
    os.environ["RAG_USE_RANDOM_EMBEDDINGS"] = "1" if dev_mode else "0"

    if st.button("🔄 更新/初始化知识库"):
        st.session_state.retriever = _re.get_retriever(st.session_state.get('kb_paths'))
        if st.session_state.retriever:
            st.success("知识库已就绪！")

# --- 对话界面 ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.write(msg["content"])

if prompt := st.chat_input("请问关于文献的内容..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("正在检索文献并思考..."):
            context = ""
            if st.session_state.retriever:
                docs = st.session_state.retriever.get_relevant_documents(prompt)
                context = "\n".join([d.page_content for d in docs])
            
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url="https://api.deepseek.com/v1")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": f"基于文献回答：\n{context}"},
                    {"role": "user", "content": prompt}
                ]
            )
            answer = response.choices[0].message.content
            st.write(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
