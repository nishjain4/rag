


# ===========================
# Paths
# ===========================

UPLOAD_FOLDER = "uploaded_files"

# ===========================
# SQLite
# ===========================

# the uploaded file is loaded into this database; it is rebuilt on every upload
SQLITE_DB_PATH = "uploaded_data.db"

# hard cap on the rows a generated query may return
MAX_QUERY_ROWS = 200

# distinct sample values shown per column in the schema prompt
SAMPLE_VALUES_PER_COLUMN = 5

# ===========================
# LLM-as-a-judge
# ===========================

ENABLE_JUDGE = True

