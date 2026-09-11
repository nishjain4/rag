import os
import shutil
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from main import answer_question, upload_document, clear_database, get_schema, get_system_prompt

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = "uploaded_files"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

class AskRequest(BaseModel):
    userQuery: str
    conversationHistory: Optional[List[Dict[str, str]]] = None

@app.get("/TestConnection")
async def test_connection():
    return {"success": True, "message": "Connected"}

@app.get("/GetDatasets")
async def get_datasets():
    return {
        "success": True,
        "datasets": [],
        "count": 0,
        "workspacesChecked": 0
    }

@app.post("/UploadPolicy")
async def upload_policy(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")

    filename = os.path.basename(file.filename)
    save_path = os.path.join(UPLOAD_FOLDER, filename)

    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Build the DAX system prompt from the file's column names and data types
        doc_name = upload_document(save_path)
        return {
            "success": True,
            "fileName": doc_name,
            "length": os.path.getsize(save_path),
            "schema": get_schema(),
            "message": "Document uploaded and ready for questions"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        if os.path.exists(save_path):
            try:
                os.remove(save_path)
            except Exception:
                pass

@app.get("/UploadPolicy")
async def list_policies():
    # Return the currently uploaded document
    from main import current_document_name
    policies = [{"name": current_document_name}] if current_document_name else []

    
    return {"policies": policies}

@app.delete("/UploadPolicy")
async def delete_policy(name: str | None = None):
    # Clear all uploaded documents
    clear_database()
    return {"success": True, "message": "All documents cleared"}

@app.get("/Schema")
async def schema():
    return {
        "success": True,
        "schema": get_schema(),
        "systemPrompt": get_system_prompt(),
    }

@app.post("/Chat")
async def chat(req: AskRequest):
    try:
        result = await answer_question(req.userQuery)
        return {
            "success": True,
            "response": result["answer"],
            "intent": result["intent"],
            "cached": result["cached"],
            "showVisual": False,
            "visualType": "none",
            "visualData": None,
            "traceability": {
                "predictedOutput": result["predicted_output"],
                "judge": result["judge"],
            }
        }
    except ValueError as e:
        # Document not uploaded
        return {
            "success": False,
            "response": str(e),
            "error": str(e),
            "showVisual": False,
            "visualType": "none",
            "visualData": None,
            "traceability": None
        }
    except Exception as e:
        return {
            "success": False,
            "response": f"Error: {str(e)}",
            "error": str(e),
            "showVisual": False,
            "visualType": "none",
            "visualData": None,
            "traceability": None
        }

# Optional aliases for your existing app
#@app.post("/upload")
#async def upload_alias(file: UploadFile = File(...)):
#    return await upload_policy(file)
#
#@app.post("/ask")
#async def ask_alias(req: AskRequest):
#    return await chat(req)