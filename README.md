# Document Data Assistant

A FastAPI backend that lets you upload a CSV or Excel dataset and ask questions
about its data. Uploaded files are loaded into SQLite, and Azure OpenAI is used
to classify questions, generate read-only SQL, validate or repair that SQL, and
write the final natural-language answer.

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

### 3. Configure Azure OpenAI

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Then set these Azure OpenAI values in `.env`:

```env
AZURE_OPENAI_API_KEY=your_azure_openai_api_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
AZURE_OPENAI_VERSION=your_api_version
```

### 4. Start the API

```powershell
uvicorn ap:app --reload
```

The backend runs at `http://127.0.0.1:8000`.

## Supported uploads

The API accepts:

- `.csv`
- `.xlsx`
- `.xls`

Each upload replaces the previously loaded dataset. Excel worksheets are
loaded as separate SQLite tables. The generated SQLite database is local and
is not committed to Git.

## Main endpoints

- `GET /TestConnection` checks that the backend is running.
- `POST /UploadPolicy` uploads a CSV or Excel dataset and replaces the current dataset.
- `GET /UploadPolicy` returns the current dataset name.
- `DELETE /UploadPolicy` clears the current dataset and conversation history.
- `POST /Chat` asks a question about the current dataset.



Interactive API documentation is available at `http://127.0.0.1:8000/docs`.
