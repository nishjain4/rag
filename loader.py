import os
import uuid
import pandas as pd


def _summarize_parent(sheet_name: str, columns: list[str], parent_df) -> str:
    lines = [
        f"Sheet: {sheet_name}",
        "Columns: " + ", ".join(columns),
        f"Row range: {parent_df.index.min()}-{parent_df.index.max()} ({len(parent_df)} rows)",
    ]

    # surface value counts so aggregate questions can be answered from the summary alone
    for column in parent_df.columns:
        if str(column).strip().lower() in {"category", "availability"}:
            counts = parent_df[column].dropna().astype(str).str.strip().value_counts()
            if not counts.empty:
                breakdown = ", ".join(f"{value}: {count}" for value, count in counts.items())
                lines.append(f"{column} summary: {breakdown}")

    return "\n".join(lines)


# hierarchical chunking for CSV/Excel: parent chunks summarize a row block, child chunks hold row detail
def create_structured_chunks(
    file_path: str,
    rows_per_child: int = 5,
    children_per_parent: int = 4,
):
    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".csv":
        dataframes = {"CSV": pd.read_csv(file_path)}

    elif extension in {".xlsx", ".xls"}:
        dataframes = pd.read_excel(file_path, sheet_name=None)

    else:
        raise ValueError("Not a CSV or Excel file")

    rows_per_parent = rows_per_child * children_per_parent
    chunks = []
    for sheet_name, sheet_df in dataframes.items():
        sheet_df = sheet_df.dropna(axis=1, how="all").dropna(axis=0, how="all")
        columns = [str(column) for column in sheet_df.columns]

        for parent_start in range(0, len(sheet_df), rows_per_parent):
            parent_df = sheet_df.iloc[parent_start:parent_start + rows_per_parent]
            if parent_df.empty:
                continue

            parent_id = str(uuid.uuid4())
            chunks.append({
                "content": _summarize_parent(sheet_name, columns, parent_df),
                "metadata": {"level": "parent", "chunk_id": parent_id},
            })

            for child_start in range(0, len(parent_df), rows_per_child):
                child_df = parent_df.iloc[child_start:child_start + rows_per_child]
                rows = [f"Sheet: {sheet_name}", "Columns: " + ", ".join(columns)]

                for row_index, row in child_df.iterrows():
                    values = []
                    for column in sheet_df.columns:
                        value = row[column]
                        if pd.notna(value):
                            values.append(f"{column}: {value}")
                    if values:
                        rows.append(f"Row {row_index}: " + " | ".join(values))

                if len(rows) > 2:
                    chunks.append({
                        "content": "\n".join(rows),
                        "metadata": {"level": "child", "parent_id": parent_id},
                    })

    return chunks


def load_and_index(file_path):
    extension = os.path.splitext(file_path)[1].lower()

    if extension not in {".csv", ".xlsx", ".xls"}:
        raise ValueError(f"Unsupported file type: {extension}")

    chunks = []
    for chunk_index, chunk in enumerate(create_structured_chunks(file_path)):
        metadata = {
            "source": os.path.basename(file_path),
            "chunk_index": chunk_index,
            **chunk["metadata"],
        }
        chunks.append({"content": chunk["content"], "metadata": metadata})

    return chunks

