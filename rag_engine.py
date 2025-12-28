import os
import streamlit as st
from dotenv import load_dotenv
import glob

# 加载 .env 文件
load_dotenv()
from typing import List, Any, Union
import openai

# LangChain compatibility imports
HAS_LANGCHAIN = True
_LANGCHAIN_IMPORT_ERRORS: list = []

try:
    try:
        from langchain_openai import OpenAIEmbeddings
    except ImportError:
        OpenAIEmbeddings = None

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError:
        RecursiveCharacterTextSplitter = None

    try:
        from langchain_community.document_loaders import PyPDFLoader
    except ImportError:
        PyPDFLoader = None

    try:
        from langchain_community.vectorstores import FAISS
    except ImportError:
        FAISS = None

    try:
        from langchain_community.vectorstores import Chroma
    except ImportError:
        Chroma = None

    try:
        from langchain_core.documents import Document
    except ImportError:
        Document = None

    try:
        from langchain_core.vectorstores import VectorStoreRetriever
    except ImportError:
        VectorStoreRetriever = None

except Exception as e:
    _LANGCHAIN_IMPORT_ERRORS.append(str(e))
    HAS_LANGCHAIN = False

# Fallback names
CHROMA = Chroma
_USE_INIT_EMB = False 

if HAS_LANGCHAIN:
    missing = []
    if not Document: missing.append("langchain_core")
    if not RecursiveCharacterTextSplitter: missing.append("langchain_text_splitters")
    if not OpenAIEmbeddings: missing.append("langchain_openai")
    if not FAISS and not Chroma: missing.append("langchain_community")
    if missing:
        _LANGCHAIN_IMPORT_ERRORS.append(f"Missing components: {', '.join(missing)}")

for _name in ('FAISS', 'CHROMA', 'Document', 'OpenAIEmbeddings', 'init_embeddings'):
    if _name not in globals():
        globals()[_name] = None

# --- 配置 ---
DEEPSEEK_API_BASE = "https://api.deepseek.com/v1"
DEEPSEEK_EMBEDDING_MODEL = "deepseek-text" 
# Default directory for "Backend" knowledge base
BACKEND_KB_DIR = "data"

# --- 辅助函数：扫面文件夹中的 PDF ---
def get_backend_pdfs() -> List[str]:
    """获取 data 文件夹下所有的 PDF 文件路径。"""
    if not os.path.exists(BACKEND_KB_DIR):
        return []
    pattern = os.path.join(BACKEND_KB_DIR, "*.pdf")
    return glob.glob(pattern)

# --- 辅助函数：加载和分割文档 ---
@st.cache_data(show_spinner="Loading documents from PDFs and splitting text...")
def load_and_split_documents(file_paths: List[str]) -> List["Document"]:
    """加载一个或多个 PDF 文档并递归地分割成小块。"""
    if not file_paths:
        return []
        
    all_documents = []
    for file_path in file_paths:
        try:
            # st.write(f"Processing: {os.path.basename(file_path)}...") # Silence logs
            documents = []
            if 'PyPDFLoader' in globals() and PyPDFLoader is not None:
                loader = PyPDFLoader(file_path)
                documents = loader.load()
            else:
                try:
                    import pypdf
                except Exception:
                    st.error("Missing 'pypdf'.")
                    continue
                try:
                    reader = pypdf.PdfReader(file_path)
                except Exception as e:
                    st.error(f"Error opening {file_path}: {e}")
                    continue
                for i, page in enumerate(reader.pages):
                    text = page.extract_text() or ""
                    meta = {"source": file_path, "page": i + 1}
                    if 'Document' in globals() and Document is not None:
                        documents.append(Document(page_content=text, metadata=meta))
                    else:
                        from types import SimpleNamespace
                        documents.append(SimpleNamespace(page_content=text, metadata=meta))
            all_documents.extend(documents)
        except Exception as e:
            st.error(f"Failed to process {file_path}: {e}")

    if not all_documents:
        return []

    # st.write(f"Total pages loaded: {len(all_documents)}. Splitting...") # Silence logs
    if 'RecursiveCharacterTextSplitter' in globals() and RecursiveCharacterTextSplitter is not None:
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(all_documents)
    else:
        splits = []
        for doc in all_documents:
            text = getattr(doc, 'page_content', '')
            for i in range(0, len(text), 800):
                chunk = text[i:i+1000]
                meta = getattr(doc, 'metadata', {}).copy()
                if 'Document' in globals() and Document is not None:
                    splits.append(Document(page_content=chunk, metadata=meta))
                else:
                    from types import SimpleNamespace
                    splits.append(SimpleNamespace(page_content=chunk, metadata=meta))
    return splits

@st.cache_resource(show_spinner="Initializing Vector Store...")
def get_vector_store_and_retriever(_splits: List["Document"]) -> Union["VectorStoreRetriever", Any]:
    DEEPSEEK_API_KEY = os.getenv("OPENAI_API_KEY")
    is_dev = os.getenv("RAG_USE_RANDOM_EMBEDDINGS") == "1"
    
    if not DEEPSEEK_API_KEY and not is_dev:
        st.error("OPENAI_API_KEY not set.")
        return None

    try:
        embeddings = None
        if not is_dev:
            embeddings = OpenAIEmbeddings(
                model=DEEPSEEK_EMBEDDING_MODEL, 
                openai_api_key=DEEPSEEK_API_KEY,
                openai_api_base=DEEPSEEK_API_BASE
            )

        if FAISS is not None and not is_dev:
            db = FAISS.from_documents(_splits, embeddings)
            return db.as_retriever(search_kwargs={"k": 3})

        # Fallback to in-memory random retriever if dev mode or no FAISS
        def _get_random_emb(texts):
            import numpy as np
            out = []
            for t in texts:
                seed = abs(hash(t)) % (2**32)
                out.append(np.random.RandomState(seed).rand(1536).tolist())
            return out

        class SimpleRetriever:
            def __init__(self, docs): self.docs = docs
            def get_relevant_documents(self, query):
                # Just return top 3 docs for dev mode
                return self.docs[:3]

        return SimpleRetriever(_splits)

    except Exception as e:
        st.error(f"Init Error: {e}")
        return None

def get_retriever(file_paths: List[str] = None) -> Any:
    """主入口：如果没传路径，则尝试扫描 data 文件夹。"""
    targets = file_paths if file_paths else get_backend_pdfs()
    if not targets:
        st.warning("No PDF files found in 'data/' folder.")
        return None
        
    splits = load_and_split_documents(targets)
    if not splits: return None
    return get_vector_store_and_retriever(splits)
