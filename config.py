
import os

from dotenv import load_dotenv

load_dotenv()

# ===========================
# API Key
# ===========================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# ===========================
# Embedding Model
# ===========================

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


# ===========================
# LLM
# ===========================

LLM_MODEL = "openai/gpt-oss-120b"

# ===========================
# Paths
# ===========================

UPLOAD_FOLDER = "uploaded_files"

CHROMA_DB_PATH = "chroma_index"

COLLECTION_NAME = "documents"

# ===========================
# Chunk Settings
# ===========================

CHUNK_SIZE = 500

CHUNK_OVERLAP = 50

# ===========================
# Retrieval
# ===========================

TOP_K = 4
