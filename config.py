
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

QUERY_CACHE_COLLECTION = "query_cache"

# ===========================
# Chunk Settings
# ===========================

CHUNK_SIZE = 500

CHUNK_OVERLAP = 50

# ===========================
# Retrieval
# ===========================

TOP_K = 4

# ===========================
# Query Cache
# ===========================

# cosine distance below which a past question is treated as the same question
CACHE_DISTANCE_THRESHOLD = 0.12

# ===========================
# LLM-as-a-judge
# ===========================

ENABLE_JUDGE = True

