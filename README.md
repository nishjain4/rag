# Document RAG Backend

A FastAPI backend that lets you upload a document and ask questions about it.

## Run the backend

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure the API key

Copy `.env.example` to `.env` and add your Groq API key:

```powershell
Copy-Item .env.example .env
```

Then edit `.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
```

### 4. Start the API

```powershell
uvicorn ap:app --reload
```

The backend runs at `http://127.0.0.1:8000`.

## Main endpoints

- `GET /TestConnection` checks that the backend is running.
- `POST /UploadPolicy` uploads and indexes a document.
- `POST /Chat` asks a question about the uploaded document.
- `DELETE /UploadPolicy` clears the indexed document.

Interactive API documentation is available at `http://127.0.0.1:8000/docs`.
