"""Render the SQLite schema built from the uploaded file for the prompts."""


def format_schema(schema: list[dict]) -> str:
    """Render tables, columns, types and sample values as the block injected into the prompts."""
    blocks = []
    for table in schema:
        lines = [f"Table: {table['table']} ({table.get('row_count', 0)} rows)"]
        for column in table["columns"]:
            line = f"  - {column['name']} ({column['data_type']})"
            original = column.get("original_name")
            if original and original != column["name"]:
                line += f'  -- source column "{original}"'
            samples = column.get("samples") or []
            if samples:
                line += "\n      sample values: " + ", ".join(samples)
            lines.append(line)
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)

'''
def schema_keywords(schema: list[dict]) -> set[str]:
    """Lowercased table and column tokens, used for cheap in-scope checks."""
    keywords = set()
    for table in schema:
        keywords.add(table["table"].lower())
        for column in table["columns"]:
            keywords.add(column["name"].lower())
            original = column.get("original_name")
            if original:
                keywords.add(original.lower())
    return keywords
'''
