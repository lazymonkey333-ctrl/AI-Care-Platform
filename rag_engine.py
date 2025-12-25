import os
import streamlit as st
from dotenv import load_dotenv
import glob

# 加载 .env 文件
load_dotenv()
from typing import List, Any, Union
import openai

# LangChain 兼容性检查
HAS_LANGCHAIN = True
try:
    from langchain_openai import OpenAIEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_community.vectorstores import FAISS
    from langchain_core.documents import Document
except ImportError:
    HAS_LANGCHAIN = False

# --- 配置 ---
DEEPSEEK_API_BASE = "https://api.deepseek.com/v1"
DEEPSEEK_EMBEDDING_MODEL = "deepseek-text" 
# 默认存放文献的文件夹路径
BACKEND_KB_DIR = "data"

def get_backend_pdfs() -> List[str]:
    """扫描 data 文件夹下的所有 PDF"""
    if not os.path.exists(BACKEND_KB_DIR):
        return []
    return glob.glob(os.path.join(BACKEND_KB_DIR, "*.pdf"))

@st.cache_data(show_spinner="正在读取后台文献...")
def load_and_split_documents(file_paths: List[str]) -> List[Any]:
    all_docs = []
    for fp in file_paths:
        try:
            st.write(f"正在读取: {os.path.basename(fp)}...")
            if 'PyPDFLoader' in globals() and PyPDFLoader:
                loader = PyPDFLoader(fp)
                all_docs.extend(loader.load())
            else:
                import pypdf
                reader = pypdf.PdfReader(fp)
                for i, page in enumerate(reader.pages):
                    all_docs.append(Document(page_content=page.extract_text(), metadata={"source": fp, "page": i+1}))
        except Exception as e:
            st.error(f"读取 {fp} 失败: {e}")
    
    if not all_docs: return []
    
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    return splitter.split_documents(all_docs)

@st.cache_resource(show_spinner="构建知识库索引...")
def get_vector_store_and_retriever(_splits: List[Any]):
    is_dev = os.getenv("RAG_USE_RANDOM_EMBEDDINGS") == "1"
    if is_dev:
        class SimpleRetriever:
            def __init__(self, d): self.d = d
            def get_relevant_documents(self, q): return self.d[:3]
        return SimpleRetriever(_splits)
    
    embeddings = OpenAIEmbeddings(
        model=DEEPSEEK_EMBEDDING_MODEL,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_api_base=DEEPSEEK_API_BASE
    )
    db = FAISS.from_documents(_splits, embeddings)
    return db.as_retriever(search_kwargs={"k": 3})

def get_retriever(file_paths: List[str] = None):
    targets = file_paths if file_paths else get_backend_pdfs()
    if not targets: return None
    splits = load_and_split_documents(targets)
    if not splits: return None
    return get_vector_store_and_retriever(splits)
