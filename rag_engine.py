import os
import streamlit as st
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()
from typing import List, Any, Union
import openai

# LangChain compatibility imports (LangChain 0.3+ friendly)
HAS_LANGCHAIN = True
_LANGCHAIN_IMPORT_ERRORS: list = []

# --- Standard modern imports ---
try:
    # Embeddings
    try:
        from langchain_openai import OpenAIEmbeddings
    except ImportError:
        OpenAIEmbeddings = None

    # Text Splitters
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError:
        RecursiveCharacterTextSplitter = None

    # Loaders
    try:
        from langchain_community.document_loaders import PyPDFLoader
    except ImportError:
        PyPDFLoader = None

    # Vector Stores
    try:
        from langchain_community.vectorstores import FAISS
    except ImportError:
        FAISS = None

    try:
        from langchain_community.vectorstores import Chroma
    except ImportError:
        Chroma = None

    # Documents
    try:
        from langchain_core.documents import Document
    except ImportError:
        Document = None

    # Retriever Base
    try:
        from langchain_core.vectorstores import VectorStoreRetriever
    except ImportError:
        VectorStoreRetriever = None

except Exception as e:
    _LANGCHAIN_IMPORT_ERRORS.append(str(e))
    HAS_LANGCHAIN = False

# Fallback for code logic using specific variable names
CHROMA = Chroma
_USE_INIT_EMB = False 

# Additional checks for missing dependencies
if HAS_LANGCHAIN:
    missing = []
    if not Document: missing.append("langchain_core")
    if not RecursiveCharacterTextSplitter: missing.append("langchain_text_splitters")
    if not OpenAIEmbeddings: missing.append("langchain_openai")
    if not FAISS and not Chroma: missing.append("langchain_community")
    
    if missing:
        _LANGCHAIN_IMPORT_ERRORS.append(f"Missing core components from: {', '.join(missing)}")

# Ensure optional imports exist in globals to avoid NameError
for _name in ('FAISS', 'CHROMA', 'Document', 'OpenAIEmbeddings', 'init_embeddings'):
    if _name not in globals():
        globals()[_name] = None

# --- 配置 ---
DEEPSEEK_API_BASE = "https://api.deepseek.com/v1"
DEEPSEEK_EMBEDDING_MODEL = "deepseek-text" 
KB_FILE_PATH = "sample_knowledge_base.pdf"

# --- 辅助函数：加载和分割文档（保持不变）---
@st.cache_data(show_spinner="Loading documents from PDF and splitting text...")
def load_and_split_documents(file_path: str) -> List["Document"]:
    """加载 PDF 文档并递归地分割成小块。

    Fallback behavior:
    - Use `PyPDFLoader` if available from LangChain.
    - Else use `pypdf.PdfReader` to extract page text and create Document-like objects.
    - If `RecursiveCharacterTextSplitter` is not available, do a naive chunk split.
    """
    try:
        st.write(f"Loading documents from {file_path}...")
        documents = []

        # Prefer LangChain's PyPDFLoader when available
        if 'PyPDFLoader' in globals() and PyPDFLoader is not None:
            loader = PyPDFLoader(file_path)
            documents = loader.load()
        else:
            # Fallback: use pypdf to extract text
            try:
                import pypdf
            except Exception:
                st.error("No PDF loader available. Install 'pypdf' (pip install pypdf) or the LangChain document loaders package.")
                return []

            try:
                reader = pypdf.PdfReader(file_path)
            except FileNotFoundError:
                st.error(f"Error: Knowledge Base file not found at path: {file_path}")
                return []
            except Exception as e:
                st.error(f"Error opening PDF with pypdf: {e}")
                return []

            for i, page in enumerate(reader.pages):
                try:
                    text = page.extract_text() or ""
                except Exception:
                    text = ""
                meta = {"source": file_path, "page": i + 1}
                if 'Document' in globals() and Document is not None:
                    documents.append(Document(page_content=text, metadata=meta))
                else:
                    # lightweight fallback object with expected attributes
                    from types import SimpleNamespace
                    documents.append(SimpleNamespace(page_content=text, metadata=meta))

        st.write(f"Loaded {len(documents)} pages. Splitting text...")

        # Use RecursiveCharacterTextSplitter when available
        if 'RecursiveCharacterTextSplitter' in globals() and RecursiveCharacterTextSplitter is not None:
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                separators=["\n\n", "\n", " ", ""]
            )
            splits = text_splitter.split_documents(documents)
        else:
            # Naive splitter fallback
            splits = []
            chunk_size = 1000
            overlap = 200
            for doc in documents:
                text = getattr(doc, 'page_content', '') or ''
                start = 0
                while start < len(text):
                    end = start + chunk_size
                    chunk = text[start:end]
                    meta = getattr(doc, 'metadata', {}).copy() if getattr(doc, 'metadata', None) else {}
                    meta.update({'chunk_start': start})
                    if 'Document' in globals() and Document is not None:
                        splits.append(Document(page_content=chunk, metadata=meta))
                    else:
                        from types import SimpleNamespace
                        splits.append(SimpleNamespace(page_content=chunk, metadata=meta))
                    start = max(end - overlap, end)

        st.write(f"Split into {len(splits)} chunks.")
        return splits
    except FileNotFoundError:
        st.error(f"Error: Knowledge Base file not found at path: {file_path}")
        return []
    except Exception as e:
        st.error(f"Error loading and splitting documents: {e}")
        return []


# 2. 缓存 VectorStore 和 Retriever 初始化
@st.cache_resource(show_spinner="Creating vector store and generating embeddings (API Call)...")
def get_vector_store_and_retriever(_splits: List["Document"]) -> Union["VectorStoreRetriever", None]:
    """初始化 DeepSeek 嵌入模型，创建内存 VectorStore，并返回 Retriever。"""
    
    DEEPSEEK_API_KEY = os.getenv("OPENAI_API_KEY")
    # Allow running in dev mode without a real API key when RAG_USE_RANDOM_EMBEDDINGS=1
    if not DEEPSEEK_API_KEY and os.getenv("RAG_USE_RANDOM_EMBEDDINGS") != "1":
        st.error("Error: OPENAI_API_KEY (DeepSeek Key) is not set.")
        return None

    if not _splits:
        st.error("Document splits list is empty. Cannot initialize vector store.")
        return None

    try:
        # 1. 初始化 DeepSeek 嵌入模型
        st.write(f"Initializing Embeddings using model: {DEEPSEEK_EMBEDDING_MODEL}...")

        # 兼容性检查
        # Allow running in dev mode (RAG_USE_RANDOM_EMBEDDINGS=1) without full LangChain
        if not HAS_LANGCHAIN and os.getenv("RAG_USE_RANDOM_EMBEDDINGS") != "1":
            st.error("LangChain package is not available or has incompatible API. Install a compatible LangChain integration.")
            st.error("Import errors: " + " | ".join(_LANGCHAIN_IMPORT_ERRORS))
            return None

        # Dev mode: if requested, skip external embeddings init and use deterministic random vectors
        embeddings = None
        if os.getenv("RAG_USE_RANDOM_EMBEDDINGS") == "1":
            st.write("RAG dev mode: skipping external embeddings initialization and using deterministic local embeddings.")
            print('DEBUG: RAG dev mode active — skipping provider embeddings init')
        else:
            # 使用现代或传统嵌入 API
            if _USE_INIT_EMB:
                st.write("Using modern LangChain 'init_embeddings' API to create embeddings...")
                embeddings = init_embeddings(
                    DEEPSEEK_EMBEDDING_MODEL, 
                    provider="openai",
                    openai_api_key=DEEPSEEK_API_KEY,
                    openai_api_base=DEEPSEEK_API_BASE,
                )
            else:
                st.write("Using legacy OpenAIEmbeddings API to create embeddings...")
                embeddings = OpenAIEmbeddings(
                    model=DEEPSEEK_EMBEDDING_MODEL, 
                    openai_api_key=DEEPSEEK_API_KEY,
                    openai_api_base=DEEPSEEK_API_BASE
                )

        # Use FAISS/Chroma if available AND NOT in dev mode.
        # Dev mode uses a custom in-memory retriever designed for local random embeddings.
        db = None
        if FAISS is not None and os.getenv("RAG_USE_RANDOM_EMBEDDINGS") != "1":
            st.write("Using FAISS's Python-based memory store (no C++ compilation required for in-memory).")
            db = FAISS.from_documents(_splits, embeddings)
            retriever = db.as_retriever(search_kwargs={"k": 3})
            return retriever

        # Try Chroma fallback
        if Chroma is not None and os.getenv("RAG_USE_RANDOM_EMBEDDINGS") != "1":
            st.write("FAISS is not available — using Chroma as a fallback vectorstore.")
            try:
                db = Chroma.from_documents(_splits, embeddings)
            except TypeError:
                db = Chroma.from_documents(_splits, embedding=embeddings)
            retriever = db.as_retriever(search_kwargs={"k": 3})
            return retriever

        # 最后回退：纯 Python 内存向量检索器（使用 embeddings API 生成嵌入并在内存中做相似度检索）
        print('DEBUG: no FAISS and no CHROMA — falling back to in-memory retriever')
        st.write("Neither FAISS nor Chroma available — using in-memory retriever fallback.")
        try:
            import numpy as np
        except Exception:
            st.error("NumPy is required for in-memory retriever fallback. Install it with 'pip install numpy'.")
            return None

        # Helper: get embeddings for list of texts using available embeddings object or openai directly
        def _embed_texts(texts: list) -> list:
            # Dev mode: generate deterministic random embeddings locally without external API
            if os.getenv("RAG_USE_RANDOM_EMBEDDINGS") == "1":
                try:
                    import numpy as _np
                except Exception:
                    st.error("NumPy is required for RAG_USE_RANDOM_EMBEDDINGS. Install it with 'pip install numpy'.")
                    raise
                out = []
                dim = int(os.getenv("RAG_FAKE_EMB_DIM", 1536))
                for t in texts:
                    seed = abs(hash(t)) % (2 ** 32)
                    rng = _np.random.RandomState(seed)
                    out.append(rng.rand(dim).tolist())
                return out

            # Prefer embeddings object if it exposes expected methods
            if 'init_embeddings' in globals() and _USE_INIT_EMB:
                try:
                    emb = init_embeddings(
                        DEEPSEEK_EMBEDDING_MODEL,
                        provider="openai",
                        openai_api_key=DEEPSEEK_API_KEY,
                        openai_api_base=DEEPSEEK_API_BASE,
                    )
                    if hasattr(emb, 'embed_documents'):
                        # batch documents to avoid large single request
                        batch_size = 64
                        out = []
                        for i in range(0, len(texts), batch_size):
                            chunk = texts[i:i+batch_size]
                            out.extend(emb.embed_documents(chunk))
                        return out
                    elif hasattr(emb, 'embed_query') or hasattr(emb, 'embed_documents'):
                        return [emb.embed_query(t) if hasattr(emb, 'embed_query') else emb.embed_documents([t])[0] for t in texts]
                except Exception as e:
                    st.warning(f"Modern embeddings init failed: {e}")
            if 'OpenAIEmbeddings' in globals() and OpenAIEmbeddings is not None:
                try:
                    emb = OpenAIEmbeddings(model=DEEPSEEK_EMBEDDING_MODEL, openai_api_key=DEEPSEEK_API_KEY, openai_api_base=DEEPSEEK_API_BASE)
                    if hasattr(emb, 'embed_documents'):
                        batch_size = 64
                        out = []
                        for i in range(0, len(texts), batch_size):
                            chunk = texts[i:i+batch_size]
                            out.extend(emb.embed_documents(chunk))
                        return out
                    elif hasattr(emb, 'embed_query'):
                        return [emb.embed_query(t) for t in texts]
                except Exception as e:
                    st.warning(f"Legacy OpenAIEmbeddings call failed: {e}")

            # Final fallback: call OpenAI/DeepSeek embeddings API directly
            try:
                openai.api_key = DEEPSEEK_API_KEY
                openai.api_base = DEEPSEEK_API_BASE
                batch_size = 64
                out = []
                for i in range(0, len(texts), batch_size):
                    chunk = texts[i:i+batch_size]
                    resp = openai.Embedding.create(model=DEEPSEEK_EMBEDDING_MODEL, input=chunk)
                    out.extend([d['embedding'] for d in resp['data']])
                return out
            except Exception as e:
                st.error(f"Failed to generate embeddings for documents: {e}")
                raise

        # Create document embeddings
        try:
            texts = [getattr(d, 'page_content', '') for d in _splits]
            st.write(f"Generating embeddings for {len(texts)} chunks (this may take a while)...")
            print('DEBUG: calling _embed_texts with', len(texts), 'texts')
            doc_embs = _embed_texts(texts)
            print('DEBUG: _embed_texts returned', None if doc_embs is None else len(doc_embs))
            if not doc_embs or len(doc_embs) != len(texts):
                st.error("Failed to generate embeddings for documents (count mismatch).")
                return None
            emb_matrix = np.array(doc_embs, dtype=float)
            print('DEBUG: emb_matrix shape', getattr(emb_matrix, 'shape', None))
        except Exception as e:
            import traceback; traceback.print_exc()
            st.error(f"Embedding generation failed — ensure your API key and embeddings provider are available. Internal error: {e}")
            return None

        # Build a simple in-memory retriever
        class InMemoryRetriever:
            def __init__(self, docs, embeddings_matrix, embed_fn):
                self.docs = docs
                self.emb = embeddings_matrix
                self.embed_fn = embed_fn

            def get_relevant_documents(self, query, k=3):
                try:
                    q_emb = np.array(self.embed_fn([query])[0], dtype=float)
                    # cosine similarity
                    q_norm = np.linalg.norm(q_emb)
                    if q_norm == 0 or self.emb.size == 0:
                        return []
                    sims = (self.emb @ q_emb) / (np.linalg.norm(self.emb, axis=1) * q_norm + 1e-12)
                    idx = list(np.argsort(-sims)[:k])
                    return [self.docs[i] for i in idx]
                except Exception as e:
                    st.warning(f"In-memory retrieval failed: {e}")
                    return []

        # Create and return the in-memory retriever
        try:
            retriever = InMemoryRetriever(_splits, emb_matrix, lambda texts: _embed_texts(texts))
            return retriever
        except Exception as e:
            st.error(f"Failed to create in-memory retriever: {e}")
            return None

    except openai.APIError as e:
        error_message = (
            f"Failed to generate embeddings via API. Final Error: {getattr(e, 'status_code', 'N/A')}\n"
            "Action Required: Check DeepSeek API documentation for supported embedding model names, or confirm your API Key has access to the embedding service."
        )
        st.error(error_message)
        return None
    except Exception as e:
        st.error(f"Error during VectorStore initialization: {e}")
        return None

# --- 主函数和测试（保持不变）---
def get_retriever() -> Union["VectorStoreRetriever", Any]:
    """主入口函数，用于初始化并获取 VectorStoreRetriever。"""
    
    st.info("Starting knowledge base initialization...")

    splits = load_and_split_documents(KB_FILE_PATH)
    if not splits:
        st.error("Document loading failed. Skipping Retriever setup.")
        return None 

    retriever = get_vector_store_and_retriever(splits)
    
    if retriever is None:
        st.error("Knowledge Base Initialization Failed.")
        return None

    return retriever

if __name__ == '__main__':
    print("--- Running RAG Engine Test Placeholder ---")
    if "OPENAI_API_KEY" not in os.environ:
        print("Please set the OPENAI_API_KEY environment variable.")
    print("Run 'streamlit run app_multi_agent.py' to test the RAG system.")
