import json
import os
import re
from typing import Optional

import chromadb
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI

from config import (
    CHROMA_DB_PATH as DEFAULT_CHROMA_DB_PATH,
    COLLECTION_NAME as DEFAULT_COLLECTION_NAME,
    ENABLE_JUDGE,
    UPLOAD_FOLDER as DEFAULT_UPLOAD_FOLDER,
)
from prompts import (
    DAX_SYSTEM_PROMPT,
    GENERAL_SYSTEM_PROMPT,
    JUDGE_PROMPT,
    ROUTER_PROMPT,
)
from query_cache import QueryCache
from schema import extract_schema, format_schema

load_dotenv()


AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_VERSION = os.environ.get("AZURE_OPENAI_VERSION")

CHROMA_DB_PATH = os.environ.get("CHROMA_DB_PATH", DEFAULT_CHROMA_DB_PATH)
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", DEFAULT_UPLOAD_FOLDER)
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", DEFAULT_COLLECTION_NAME)

NOT_ANSWERABLE = "NOT_ANSWERABLE"


client = AsyncAzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
)


os.makedirs(CHROMA_DB_PATH, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
query_cache = QueryCache(chroma_client)

current_document_name: Optional[str] = None
current_schema: Optional[list[dict]] = None
schema_text: str = ""
dax_system_prompt: str = ""
chat_history: list = []


# ---------------------------------------------------------------------------
# Document lifecycle
# ---------------------------------------------------------------------------

def clear_database() -> None:
    global current_document_name, current_schema, schema_text, dax_system_prompt, chat_history

    try:
        chroma_client.delete_collection(COLLECTION_NAME)
    except chromadb.errors.NotFoundError:
        pass

    query_cache.reset()

    current_document_name = None
    current_schema = None
    schema_text = ""
    dax_system_prompt = ""
    chat_history = []


def upload_document(file_path: str) -> str:
    """Read the table headers and build the DAX system prompt from column names and types."""
    global current_document_name, current_schema, schema_text, dax_system_prompt, chat_history

    clear_database()

    current_schema = extract_schema(file_path)
    schema_text = format_schema(current_schema)
    dax_system_prompt = DAX_SYSTEM_PROMPT.format(schema=schema_text)

    current_document_name = os.path.basename(file_path)
    chat_history = []

    return current_document_name


def get_schema() -> list[dict]:
    return current_schema or []


def get_system_prompt() -> str:
    return dax_system_prompt


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------

_FENCE_PATTERN = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


def _strip_fences(text: str) -> str:
    return _FENCE_PATTERN.sub("", (text or "").strip()).strip()


def _parse_json(content: str) -> dict:
    cleaned = _strip_fences(content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}


async def _complete(messages: list[dict], temperature: float = 0.0) -> str:
    response = await client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT_NAME,
        messages=messages,
        temperature=temperature,
    )
    return (response.choices[0].message.content or "").strip()


async def _classify_intent(question: str) -> str:
    content = await _complete([{
        "role": "user",
        "content": ROUTER_PROMPT.format(schema=schema_text, question=question),
    }])
    intent = _parse_json(content).get("intent", "general")
    return "dax" if intent == "dax" else "general"


async def _generate_dax(question: str) -> str:
    content = await _complete([
        {"role": "system", "content": dax_system_prompt},
        {"role": "user", "content": question},
    ])
    return _strip_fences(content)


async def _judge_dax(question: str, dax: str) -> dict:
    """LLM-as-a-judge: validate the query against the schema and predict its output."""
    content = await _complete([{
        "role": "user",
        "content": JUDGE_PROMPT.format(schema=schema_text, question=question, dax=dax),
    }])
    verdict = _parse_json(content)
    return {
        "verdict": verdict.get("verdict", "valid"),
        "issues": verdict.get("issues", ""),
        "predicted_output": verdict.get("predicted_output", ""),
        "corrected_dax": _strip_fences(verdict.get("corrected_dax", "")),
    }


async def _general_answer(question: str) -> str:
    return await _complete(
        [
            {"role": "system", "content": GENERAL_SYSTEM_PROMPT.format(schema=schema_text)},
            *chat_history[-6:],
            {"role": "user", "content": question},
        ],
        temperature=0.4,
    )


def _record(question: str, answer: str) -> None:
    chat_history.extend([
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    ])


# ---------------------------------------------------------------------------
# Question answering
# ---------------------------------------------------------------------------

async def answer_question(question: str) -> dict:
    if current_document_name is None or not schema_text:
        raise ValueError("No document uploaded. Please upload a document first.")

    # 1. reuse a previously answered, semantically equivalent question
    cached = query_cache.lookup(question, current_document_name)
    if cached and cached["answer"]:
        _record(question, cached["answer"])
        return {
            "answer": cached["answer"],
            "intent": cached["intent"],
            "cached": True,
            "predicted_output": cached.get("predicted_output", ""),
            "judge": None,
        }

    # 2. anything outside the table context gets a human-like reply, never DAX
    intent = await _classify_intent(question)
    if intent == "general":
        answer = await _general_answer(question) or (
            "I'm here to help with the uploaded dataset. Could you rephrase that?"
        )
        query_cache.store(question, answer, current_document_name, "general")
        _record(question, answer)
        return {
            "answer": answer,
            "intent": "general",
            "cached": False,
            "predicted_output": "",
            "judge": None,
        }

    # 3. generate the DAX query from the schema-only system prompt
    dax = await _generate_dax(question)

    if not dax or dax.upper().startswith(NOT_ANSWERABLE):
        answer = await _general_answer(question)
        _record(question, answer)
        return {
            "answer": answer,
            "intent": "general",
            "cached": False,
            "predicted_output": "",
            "judge": None,
        }

    # 4. LLM-as-a-judge reviews the query and predicts the output it would return
    judge = None
    predicted_output = ""
    if ENABLE_JUDGE:
        judge = await _judge_dax(question, dax)
        predicted_output = judge["predicted_output"]
        if judge["verdict"] != "valid" and judge["corrected_dax"]:
            dax = judge["corrected_dax"]

    query_cache.store(question, dax, current_document_name, "dax", predicted_output)
    _record(question, dax)

    return {
        "answer": dax,
        "intent": "dax",
        "cached": False,
        "predicted_output": predicted_output,
        "judge": judge,
    }


async def ask_question(question: str) -> str:
    """Return only the DAX query for data questions, or a plain answer for anything else."""
    result = await answer_question(question)
    return result["answer"]





