import os
import re
import shutil
from typing import Optional

from loader import load_and_index
from langchain_chroma import Chroma
from langchain_groq import ChatGroq

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage

from prompts import prompt as PROMPT_TEMPLATE
from config import (
    CHROMA_DB_PATH,
    EMBEDDING_MODEL,
    GROQ_API_KEY,
    LLM_MODEL,
    TOP_K,
)

#initialise embeddings and LLM
embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
llm = ChatGroq(model=LLM_MODEL, temperature=0, api_key=GROQ_API_KEY)



os.makedirs(CHROMA_DB_PATH, exist_ok=True)

# Global vector database (single, shared instance)
vector_db: Optional[Chroma] = None
current_document_name: Optional[str] = None
chat_history: list = []

def _init_vector_db() -> Chroma:
    """Initialize the global vector database."""
    return Chroma(
        collection_name="documents",
        embedding_function=embeddings,
        persist_directory=CHROMA_DB_PATH,
    )

def clear_database() -> None:
    """Clear all indexed documents."""
    global vector_db, current_document_name, chat_history
    if os.path.isdir(CHROMA_DB_PATH):
        shutil.rmtree(CHROMA_DB_PATH, ignore_errors=True)
    os.makedirs(CHROMA_DB_PATH, exist_ok=True)
    vector_db = None
    current_document_name = None
    chat_history = []


def upload_document(file_path: str) -> str:
    """Upload and index a document into the global vector database."""
    global vector_db, current_document_name, chat_history
    
    # Clear previous document and reset chat history
    clear_database()
    
    # Load and split the document
    chunks = load_and_index(file_path)
    if not chunks:
        raise ValueError("Uploaded document did not contain any text")

    # Initialize fresh vector database
    vector_db = _init_vector_db()
    vector_db.add_documents(chunks)
    
    # Update global state
    current_document_name = os.path.basename(file_path)
    chat_history = []
    
    return current_document_name


def _retrieve_documents(question: str) -> list[Document]:
    #Combine semantic retrieval with exact term matching for structured data.
    semantic_results = vector_db.similarity_search(question, k=max(TOP_K, 10))
    semantic_documents = {doc.page_content: doc for doc in semantic_results}

    query_terms = {
        term.lower()
        for term in re.findall(r"[A-Za-z0-9]+", question)
        if len(term) > 2
    }
    if not query_terms:
        return list(semantic_documents.values())

    stored = vector_db.get(include=["documents", "metadatas"])
    documents = stored.get("documents") or []
    metadatas = stored.get("metadatas") or []

    exact_matches = []
    for index, text in enumerate(documents):
        normalized_text = text.lower()
        matching_terms = sum(
            1 for term in query_terms
            if re.search(rf"\b{re.escape(term)}\b", normalized_text)
        )
        if matching_terms:
            metadata = metadatas[index] if index < len(metadatas) else {}
            exact_matches.append(
                (matching_terms, Document(page_content=text, metadata=metadata or {}))
            )

    retrieved = {}
    for _, document in sorted(exact_matches, key=lambda item: item[0], reverse=True):
        retrieved.setdefault(document.page_content, document)
    for document in semantic_results:
        retrieved.setdefault(document.page_content, semantic_documents[document.page_content])

    return list(retrieved.values())[: max(TOP_K, 10)]


#ask questions
async def ask_question(question: str) -> str:
   
    global vector_db, chat_history
    
    if vector_db is None or current_document_name is None:
        raise ValueError("No document uploaded. Please upload a document first.")

    results = _retrieve_documents(question)

    if not results:
        return "No relevant information found in the document."


#build context from the retrieved documents
    context_parts = []
    for doc in results:
        content = doc.page_content.strip()
        if not content:
            continue
        source = doc.metadata.get("source", current_document_name or "uploaded document")
        context_parts.append(f"Source: {source}\n{content}")

    if not context_parts:
        return "No relevant information found in the document."

    context = "\n\n".join(context_parts)

    print(f"Context for question '{question}':\n{context}\n")

    # Generate response using LLM
    chat_prompt = PROMPT_TEMPLATE.format_prompt(question=question, context=context, chat_history=chat_history)
    response = await llm.agenerate_prompt([chat_prompt])
    

    if not response.generations or not response.generations[0]:
        return "I couldn't find that information in the uploaded documents."

    answer = response.generations[0][0].text.strip()
    if not answer:
        return "I couldn't find that information in the uploaded documents."

    # Update chat history
    chat_history.append(HumanMessage(content=question))
    chat_history.append(AIMessage(content=answer))

    return answer





