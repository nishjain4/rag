import json
import os
import re
import sqlite3
from typing import Optional

from dotenv import load_dotenv
from openai import AsyncAzureOpenAI

from config import (
    ENABLE_JUDGE,
    UPLOAD_FOLDER as DEFAULT_UPLOAD_FOLDER,
)
from prompts import (
    ANSWER_PROMPT,
    GENERAL_SYSTEM_PROMPT,
    JUDGE_PROMPT,
    REPAIR_PROMPT,
    ROUTER_PROMPT,
    SQL_SYSTEM_PROMPT,
)
from schema import format_schema
from sqlite_store import build_database, format_rows, is_read_only, reset_database, run_query

load_dotenv()


AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_VERSION = os.environ.get("AZURE_OPENAI_VERSION")

UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", DEFAULT_UPLOAD_FOLDER)

NOT_ANSWERABLE = "NOT_ANSWERABLE"


client = AsyncAzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
)


os.makedirs(UPLOAD_FOLDER, exist_ok=True)

current_document_name: Optional[str] = None
current_schema: Optional[list[dict]] = None
schema_text: str = ""
sql_system_prompt: str = ""
chat_history: list = []


# ---------------------------------------------------------------------------
# Document lifecycle
# ---------------------------------------------------------------------------

def clear_database() -> None:
    """Forget the previous upload, database contents, and chat history."""
    global current_document_name, current_schema, schema_text, sql_system_prompt, chat_history

    reset_database()

    current_document_name = None
    current_schema = None
    schema_text = ""
    sql_system_prompt = ""
    chat_history = []


def upload_document(file_path: str) -> str:
    """Load the file into SQLite, replacing any previously uploaded document."""
    global current_document_name, current_schema, schema_text, sql_system_prompt, chat_history

    clear_database()

    current_schema = build_database(file_path)
    schema_text = format_schema(current_schema)
    sql_system_prompt = SQL_SYSTEM_PROMPT.format(schema=schema_text)

    current_document_name = os.path.basename(file_path)
    chat_history = []

    return current_document_name


def get_schema() -> list[dict]:
    return current_schema or []


def get_system_prompt() -> str:
    return sql_system_prompt


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
    return "sql" if intent == "sql" else "general"


def _clean_sql(text: str) -> str:
    return _strip_fences(text).strip().rstrip(";").strip()


async def _generate_sql(question: str) -> str:
    content = await _complete([
        {"role": "system", "content": sql_system_prompt},
        {"role": "user", "content": question},
    ])
    return _clean_sql(content)


async def _judge_sql(question: str, sql: str) -> dict:
    """LLM-as-a-judge: validate the query against the schema before it is executed."""
    content = await _complete([{
        "role": "user",
        "content": JUDGE_PROMPT.format(schema=schema_text, question=question, sql=sql),
    }])
    verdict = _parse_json(content)
    return {
        "verdict": verdict.get("verdict", "valid"),
        "issues": verdict.get("issues", ""),
        "predicted_output": verdict.get("predicted_output", ""),
        "corrected_sql": _clean_sql(verdict.get("corrected_sql", "")),
    }


async def _repair_sql(question: str, sql: str, error: str) -> str:
    content = await _complete([{
        "role": "user",
        "content": REPAIR_PROMPT.format(
            schema=schema_text, question=question, sql=sql, error=error
        ),
    }])
    return _clean_sql(content)


async def _narrate(question: str, result: dict) -> str:
    """Turn the rows SQLite returned into a sentence a chatbot would say."""
    return await _complete(
        [{
            "role": "user",
            "content": ANSWER_PROMPT.format(question=question, result=format_rows(result)),
        }],
        temperature=0.2,
    )


async def _execute_with_repair(question: str, sql: str) -> tuple[str, dict]:
    """Run the query, asking the model to fix it once if SQLite rejects it."""
    try:
        return sql, run_query(sql)
    except (sqlite3.Error, ValueError) as first_error:
        repaired = await _repair_sql(question, sql, str(first_error))
        if not repaired or repaired.upper().startswith(NOT_ANSWERABLE) or not is_read_only(repaired):
            raise
        return repaired, run_query(repaired)


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

    # Anything outside the table context gets a human-like reply, never SQL.
    intent = await _classify_intent(question)
    if intent == "general":
        answer = await _general_answer(question) or (
            "I'm here to help with the uploaded dataset. Could you rephrase that?"
        )
        _record(question, answer)
        return {
            "answer": answer,
            "intent": "general",
            "cached": False,
            "sql": "",
            "result": None,
            "predicted_output": "",
            "judge": None,
        }

    # 3. generate the SQL query from the schema-only system prompt
    sql = await _generate_sql(question)

    if not sql or sql.upper().startswith(NOT_ANSWERABLE):
        answer = await _general_answer(question)
        _record(question, answer)
        return {
            "answer": answer,
            "intent": "general",
            "cached": False,
            "sql": "",
            "result": None,
            "predicted_output": "",
            "judge": None,
        }

    # 4. LLM-as-a-judge reviews the query before it touches the database
    judge = None
    predicted_output = ""
    if ENABLE_JUDGE:
        judge = await _judge_sql(question, sql)
        predicted_output = judge["predicted_output"]
        if judge["verdict"] != "valid" and judge["corrected_sql"]:
            sql = judge["corrected_sql"]

    # 5. execute against the SQLite table built from the uploaded file
    try:
        sql, result = await _execute_with_repair(question, sql)
    except (sqlite3.Error, ValueError) as error:
        return {
            "answer": (
                "I couldn't run that against the uploaded data. "
                "Could you rephrase the question?"
            ),
            "intent": "sql",
            "cached": False,
            "sql": sql,
            "result": None,
            "error": str(error),
            "predicted_output": predicted_output,
            "judge": judge,
        }

    # 6. turn the returned rows into a natural, chatbot-style answer
    answer = await _narrate(question, result) or format_rows(result)

    _record(question, answer)

    return {
        "answer": answer,
        "intent": "sql",
        "cached": False,
        "sql": sql,
        "result": result,
        "predicted_output": predicted_output,
        "judge": judge,
    }


async def ask_question(question: str) -> str:
    """Return the natural-language answer for the question."""
    result = await answer_question(question)
    return result["answer"]





