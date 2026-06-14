import sqlite3
import requests
import re
from structured_parser import get_db_connection, get_table_schema

OLLAMA_URL = "http://localhost:11434/api/generate"

# Words that signal the question needs arithmetic or aggregation
ANALYTICAL_SIGNALS = [
    r'\btotal\b', r'\bsum\b', r'\baverage\b', r'\bavg\b',
    r'\bcount\b', r'\bmaximum\b', r'\bminimum\b', r'\bmax\b', r'\bmin\b',
    r'\bhow many\b', r'\bhow much\b', r'\bpercentage\b', r'\bpercent\b',
    r'\bcompare\b', r'\btrend\b', r'\bhighest\b', r'\blowest\b',
    r'\bmost\b', r'\bleast\b', r'\brank\b', r'\btop \d+\b',
]


def has_structured_data() -> bool:
    """
    Check if any structured data has been ingested.
    If SQLite DB doesn't exist or has no tables, skip SQL routing.
    """
    try:
        conn = get_db_connection()
        schema = get_table_schema(conn)
        conn.close()
        return len(schema) > 0
    except Exception:
        return False


def natural_language_to_sql(query: str, schema: dict) -> str | None:
    """
    Updated prompt handles both:
    - Analytical: "total revenue" → SELECT SUM(revenue) FROM ...
    - Semantic:   "passenger 13 name" → SELECT * FROM ... WHERE passenger_id = 13
    - Lookup:     "who survived" → SELECT * FROM ... WHERE survived = 1
    """
    schema_text = ""
    for table, columns in schema.items():
        schema_text += f"\nTable '{table}' columns: {', '.join(columns)}"

    prompt = f"""You are a SQL expert working with SQLite.
Convert the user's question into a SQL SELECT query.

Available tables:
{schema_text}

Rules:
- Return ONLY the SQL query. Nothing else. No explanation. No second line.
- Stop after the semicolon. Do not write anything after the SQL ends.
- Only SELECT statements.
- Use exact table and column names from the schema.
- For lookup/search questions: SELECT * FROM table WHERE column LIKE '%value%'
- For analytical questions: use SUM(), COUNT(), AVG(), MAX(), MIN()
- LIMIT results to 20 rows unless asking for totals/counts
- If truly unanswerable, return exactly: CANNOT_ANSWER

Question: {query}

SQL (one statement only, nothing after the semicolon):"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": "mistral", "prompt": prompt, "stream": False},
            timeout=30
        )
        sql = response.json()["response"].strip()

        # Strip markdown fences
        sql = re.sub(r'```sql|```', '', sql).strip()

        # ── NEW: take only the first statement ───────────────────────
        # LLMs sometimes append explanation after the semicolon
        # Split on semicolon, take first part, re-add semicolon
        if ';' in sql:
            sql = sql.split(';')[0].strip() + ';'

        # Strip any remaining newlines or text after the SQL
        # (catches cases where LLM adds text without a semicolon)
        lines = sql.strip().split('\n')
        sql_lines = []
        for line in lines:
            stripped = line.strip()
            # Stop collecting if we hit a non-SQL line
            if stripped and not stripped.upper().startswith(('SELECT','FROM','WHERE',
               'JOIN','LEFT','RIGHT','INNER','GROUP','ORDER','HAVING','LIMIT',
               'AND','OR','ON','AS','DISTINCT','COUNT','SUM','AVG','MAX','MIN',
               'LIKE','IN','NOT','IS','NULL','BY','ASC','DESC','CASE','WHEN',
               'THEN','ELSE','END','UNION','WITH','--')):
                # Check if it looks like SQL continuation or explanation
                if any(sql_lines):  # only break if we already have SQL
                    break
            sql_lines.append(line)

        sql = '\n'.join(sql_lines).strip()
        if not sql.endswith(';'):
            sql = sql + ';'
        # ── END NEW ───────────────────────────────────────────────────

        if sql.upper().startswith("CANNOT_ANSWER"):
            return None

        if not sql.upper().strip().startswith("SELECT"):
            return None

        return sql

    except Exception as e:
        print(f"SQL generation failed: {e}")
        return None


def execute_sql(sql: str) -> dict:
    """
    Execute a SELECT query against SQLite.
    Returns rows as list of dicts, or error information.
    Never crashes — all exceptions caught and returned as structured errors.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql)

        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchmany(50)  # Limit to 50 rows for LLM context

        conn.close()

        return {
            "success": True,
            "columns": columns,
            "rows": [dict(zip(columns, row)) for row in rows],
            "row_count": len(rows)
        }

    except sqlite3.Error as e:
        return {
            "success": False,
            "error": str(e),
            "failed_sql": sql
        }

def describe_structured_data(query: str) -> dict | None:
    """
    For 'tell me about this file' type questions —
    describe the tables and columns directly from schema.
    """
    if not is_document_level_question(query):
        return None

    if not has_structured_data():
        return None

    conn = get_db_connection()
    schema = get_table_schema(conn)

    # Get row counts per table
    descriptions = []
    cursor = conn.cursor()
    for table, columns in schema.items():
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cursor.fetchone()[0]
        descriptions.append(
            f"Table '{table}': {row_count} rows, "
            f"columns: {', '.join(columns)}"
        )
    conn.close()

    schema_summary = "\n".join(descriptions)

    prompt = f"""A user asked: "{query}"

The uploaded structured data contains:
{schema_summary}

Write a clear description of what this data contains based on the table and column names.
Mention the number of rows and what kinds of information are available.
Answer:"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": "mistral", "prompt": prompt, "stream": False},
            timeout=30
        )
        answer = response.json()["response"].strip()
    except Exception:
        answer = f"This file contains: {schema_summary}"

    return {
        "answer": answer,
        "route": "schema_description",
        "sources": [{"filename": "structured_data", "type": "schema"}]
    }

def explain_sql_result(query: str, sql: str, result: dict) -> str:
    """
    Ask Ollama to explain the SQL result in plain English.
    The LLM sees: original question + SQL executed + raw result.
    Returns a natural language answer.
    """
    if not result["success"]:
        return f"I found relevant data but encountered an error: {result['error']}"

    if result["row_count"] == 0:
        return "The query returned no results. The data may not exist in your uploaded files."

    # Format rows for the prompt
    rows_text = "\n".join([str(row) for row in result["rows"][:10]])

    prompt = f"""A user asked: "{query}"

I executed this SQL query:
{sql}

The result was:
{rows_text}

Write a clear, concise answer to the user's question based on this result.
Use specific numbers from the data. Do not mention SQL in your answer.
Answer:"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": "mistral", "prompt": prompt, "stream": False},
            timeout=30
        )
        return response.json()["response"].strip()
    except Exception:
        # If explanation fails, return raw result as fallback
        return f"Query result: {result['rows']}"


def try_sql_route(query: str) -> dict | None:
    """
    Updated: tries SQL for ALL questions when structured data exists.
    Not just analytical ones.
    
    For analytical questions: generates SUM/COUNT/AVG queries
    For semantic questions: generates SELECT * WHERE LIKE lookups
    """
    # Skip if no structured data at all
    if not has_structured_data():
        return None

    # Don't SQL-route questions about the file itself
    if is_document_level_question(query):
        return None
    
    # Get schema
    conn = get_db_connection()
    schema = get_table_schema(conn)
    conn.close()

    if not schema:
        return None

    # Generate SQL — updated prompt handles both analytical + semantic
    sql = natural_language_to_sql(query, schema)
    if not sql:
        return None

    # Execute
    result = execute_sql(sql)

    # If SQL returned nothing, don't return a dead answer
    if result["success"] and result["row_count"] == 0:
        return {
            "answer": "No matching records found in the uploaded data for that query.",
            "route": "sql",
            "sql_executed": sql,
            "sources": [{"filename": "structured_data", "type": "sql_query"}]
        }

    # Explain result
    answer = explain_sql_result(query, sql, result)

    return {
        "answer": answer,
        "route": "sql",
        "sql_executed": sql,
        "raw_result": result.get("rows", [])[:5],
        "sources": [{"filename": "structured_data", "type": "sql_query"}]
    }

# Questions about the file/document itself — NOT SQL territory
DOCUMENT_SIGNALS = [
    r'\babout this file\b', r'\babout the file\b',
    r'\babout this data\b', r'\babout the dataset\b',
    r'\bwhat is this\b', r'\bdescribe this\b',
    r'\bsummarise\b', r'\bsummarize\b', r'\boverview\b',
    r'\bwhat does this contain\b', r'\bwhat kind of data\b',
]

def is_document_level_question(query: str) -> bool:
    """Questions about the file itself, not its data values."""
    query_lower = query.lower()
    return any(re.search(p, query_lower) for p in DOCUMENT_SIGNALS)
