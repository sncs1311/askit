import pandas as pd
import json
import xml.etree.ElementTree as ET
import sqlite3
import os
import re

SQLITE_DB_PATH = "./structured_data.db"


def get_db_connection():
    return sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)


def sanitize_table_name(filename: str) -> str:
    """
    Convert filename to valid SQLite table name.
    'Q3 Sales Report!.xlsx' → 'tbl_q3_sales_report_xlsx'
    """
    name = os.path.splitext(filename)[0].lower()
    name = re.sub(r'[^a-z0-9_]', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')

    # Prefix if starts with digit or is empty
    if not name or name[0].isdigit():
        name = 'tbl_' + name

    return name


def get_table_schema(conn: sqlite3.Connection) -> dict:
    """
    Returns all table names and their column names from SQLite.
    Used by the SQL router so the LLM knows what tables exist.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()

    schema = {}
    for (table_name,) in tables:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        schema[table_name] = columns

    return schema


# ── Parsers per file type ─────────────────────────────────────────────────

def parse_excel(file_path: str, filename: str) -> dict:
    """
    Every sheet → separate SQLite table.
    Multi-sheet workbooks fully supported.
    """
    conn = get_db_connection()
    tables_created = []

    try:
        xl = pd.ExcelFile(file_path)

        for sheet_name in xl.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name, header=0)

            # Clean column names — remove whitespace, make SQL-safe
            df.columns = [
                re.sub(r'[^a-z0-9_]', '_', str(col).lower().strip())
                for col in df.columns
            ]

            # Table name = filename_sheetname
            base = sanitize_table_name(filename)
            sheet_safe = re.sub(r'[^a-z0-9_]', '_', sheet_name.lower())
            table_name = f"{base}_{sheet_safe}"

            df.to_sql(table_name, conn, if_exists='replace', index=False)
            tables_created.append({
                "table": table_name,
                "rows": len(df),
                "columns": list(df.columns)
            })

    finally:
        conn.close()

    return {
        "filename": filename,
        "type": "excel",
        "tables_created": tables_created
    }


def parse_csv(file_path: str, filename: str) -> dict:
    """
    CSV → single SQLite table.
    Tries UTF-8 encoding first, falls back to latin-1.
    """
    try:
        df = pd.read_csv(file_path, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, encoding='latin-1')

    # Clean column names
    df.columns = [
        re.sub(r'[^a-z0-9_]', '_', str(col).lower().strip())
        for col in df.columns
    ]

    table_name = sanitize_table_name(filename)

    conn = get_db_connection()
    try:
        df.to_sql(table_name, conn, if_exists='replace', index=False)
    finally:
        conn.close()

    return {
        "filename": filename,
        "type": "csv",
        "tables_created": [{
            "table": table_name,
            "rows": len(df),
            "columns": list(df.columns)
        }]
    }


def parse_json(file_path: str, filename: str) -> dict:
    """
    JSON array of objects → SQLite table.
    Nested objects flattened with dot notation.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Wrap non-list JSON in a list
    if isinstance(data, dict):
        data = [data]

    df = pd.json_normalize(data)

    # Clean column names
    df.columns = [
        re.sub(r'[^a-z0-9_]', '_', str(col).lower().strip())
        for col in df.columns
    ]

    table_name = sanitize_table_name(filename)

    conn = get_db_connection()
    try:
        df.to_sql(table_name, conn, if_exists='replace', index=False)
    finally:
        conn.close()

    return {
        "filename": filename,
        "type": "json",
        "tables_created": [{
            "table": table_name,
            "rows": len(df),
            "columns": list(df.columns)
        }]
    }


def parse_xml(file_path: str, filename: str) -> dict:
    """
    XML → SQLite table.
    Each child of root element becomes a row.
    Child sub-elements become columns.
    """
    tree = ET.parse(file_path)
    root = tree.getroot()

    rows = []
    for child in root:
        row = {}
        for subelem in child:
            row[subelem.tag] = subelem.text
        # Also capture attributes
        row.update(child.attrib)
        if row:
            rows.append(row)

    if not rows:
        return {"filename": filename, "type": "xml",
                "error": "No parseable rows found in XML"}

    df = pd.DataFrame(rows)
    df.columns = [
        re.sub(r'[^a-z0-9_]', '_', str(col).lower().strip())
        for col in df.columns
    ]

    table_name = sanitize_table_name(filename)

    conn = get_db_connection()
    try:
        df.to_sql(table_name, conn, if_exists='replace', index=False)
    finally:
        conn.close()

    return {
        "filename": filename,
        "type": "xml",
        "tables_created": [{
            "table": table_name,
            "rows": len(df),
            "columns": list(df.columns)
        }]
    }