import os

import pandas as pd


# pandas dtype -> Power BI / DAX data type
_DTYPE_MAP = {
    "int": "Whole Number",
    "float": "Decimal Number",
    "bool": "Boolean",
    "datetime": "DateTime",
    "timedelta": "Duration",
    "object": "Text",
    "string": "Text",
    "category": "Text",
}


def _dax_data_type(dtype) -> str:
    name = str(dtype).lower()
    for prefix, dax_type in _DTYPE_MAP.items():
        if name.startswith(prefix):
            return dax_type
    return "Text"


def _table_name(file_path: str, sheet_name: str) -> str:
    if sheet_name and sheet_name != "CSV":
        return str(sheet_name).strip()
    return os.path.splitext(os.path.basename(file_path))[0].strip()


def extract_schema(file_path: str) -> list[dict]:
    """Return [{"table": str, "columns": [{"name": str, "data_type": str}]}] for a CSV/Excel file."""
    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".csv":
        # only the header row is needed to derive names, a few rows give pandas enough to infer types
        dataframes = {"CSV": pd.read_csv(file_path, nrows=200)}
    elif extension in {".xlsx", ".xls"}:
        dataframes = pd.read_excel(file_path, sheet_name=None, nrows=200)
    else:
        raise ValueError(f"Unsupported file type: {extension}")

    schema = []
    for sheet_name, sheet_df in dataframes.items():
        sheet_df = sheet_df.dropna(axis=1, how="all")
        columns = [
            {"name": str(column), "data_type": _dax_data_type(sheet_df[column].dtype)}
            for column in sheet_df.columns
            if "Unnamed" not in str(column)
        ]
        if columns:
            schema.append({
                "table": _table_name(file_path, sheet_name),
                "columns": columns,
            })

    if not schema:
        raise ValueError("No columns could be read from the uploaded file")

    return schema


def format_schema(schema: list[dict]) -> str:
    """Render the schema as the column-name/data-type block injected into the system prompt."""
    blocks = []
    for table in schema:
        lines = [f"Table: '{table['table']}'"]
        lines.extend(
            f"  - [{column['name']}] : {column['data_type']}"
            for column in table["columns"]
        )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def schema_keywords(schema: list[dict]) -> set[str]:
    """Lowercased table and column tokens, used for cheap in-scope checks."""
    keywords = set()
    for table in schema:
        keywords.add(table["table"].lower())
        for column in table["columns"]:
            keywords.add(column["name"].lower())
    return keywords
