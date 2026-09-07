import os
import pandas as pd
from langchain_core.documents import Document
from config import CHUNK_SIZE, CHUNK_OVERLAP
from parser import read_txt_file, read_pdf_file, read_docx_file, read_pptx_file


def get_loader(file_path: str):
    extension = os.path.splitext(file_path)[1].lower()

    if extension ==".txt":
        return read_txt_file(file_path)

    elif extension == ".pdf":
        return read_pdf_file(file_path)

    elif extension == ".docx":
        return read_docx_file(file_path)


    elif extension in {".ppt", ".pptx"}:
        return read_pptx_file(file_path)


    raise ValueError(f"Unsupported file type: {extension}")




# 3. NEW: row-wise hierarchical chunking for CSV/Excel
def create_structured_chunks(
    file_path: str,
    rows_per_parent: int = 3
):
    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".csv":
        df = pd.read_csv(file_path)

    elif extension in {".xlsx", ".xls"}:
        dataframes = pd.read_excel(file_path, sheet_name=None)

    else:
        raise ValueError("Not a CSV or Excel file")

    if extension == ".csv":
        dataframes = {"CSV": df}

    chunks = []
    for sheet_name, sheet_df in dataframes.items():
        sheet_df = sheet_df.dropna(axis=1, how="all").dropna(axis=0, how="all")
        columns = [str(column) for column in sheet_df.columns]

        for start in range(0, len(sheet_df), rows_per_parent):
            parent_df = sheet_df.iloc[start:start + rows_per_parent]
            rows = [f"Sheet: {sheet_name}", "Columns: " + ", ".join(columns)]

            for row_index, row in parent_df.iterrows():
                values = []
                for column in sheet_df.columns:
                    value = row[column]
                    if pd.notna(value):
                        values.append(f"{column}: {value}")
                if values:
                    rows.append(f"Row {row_index}: " + " | ".join(values))

            if len(rows) > 2:
                chunks.append("\n".join(rows))

    return chunks



def split_documents(text):
    words = text.split()
    chunks = []
    start = 0
    step = CHUNK_SIZE - CHUNK_OVERLAP

    while start < len(words):
        chunk_text = " ".join(words[start:start + CHUNK_SIZE])
        if chunk_text:
            chunks.append(Document(page_content=chunk_text))
        start += step

    return chunks


def load_and_index(file_path):

    extension = os.path.splitext(file_path)[1].lower()

    if extension in [".csv", ".xlsx", ".xls"]:
        chunks = [
            Document(
                page_content=chunk,
                metadata={"source": os.path.basename(file_path)},
            )
            for chunk in create_structured_chunks(file_path)
        ]

    else:
        text = get_loader(file_path)

        chunks = split_documents(text)
        for chunk in chunks:
            chunk.metadata["source"] = os.path.basename(file_path)

    return chunks
    
