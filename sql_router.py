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
Convert the user's question into a SQL SELECT query using the available tables.

Available tables:
{schema_text}

Rules:
- Return ONLY the SQL. No explanation, no markdown, no backticks.
- Only SELECT statements. Never INSERT, UPDATE, DELETE, DROP.
- Use exact table and column names from the schema.
- For lookup/search questions use: SELECT * FROM table WHERE column LIKE '%value%'
- For name/identity questions use LIKE with % wildcards for fuzzy matching
- For ID-based questions use: WHERE id_column = number
- For analytical questions use: SUM(), COUNT(), AVG(), MAX(), MIN()
- If truly unanswerable from schema, return: CANNOT_ANSWER
- LIMIT results to 20 rows unless asking for totals/counts

Question: {query}

SQL:"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": "mistral", "prompt": prompt, "stream": False},
            timeout=30
        )
        sql = response.json()["response"].strip()
        sql = re.sub(r'```sql|```', '', sql).strip()

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