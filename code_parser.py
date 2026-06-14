import ast
import os
import re
import requests
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/generate"

TREE_SITTER_LANGUAGES = {
    '.js': 'javascript', '.jsx': 'javascript',
    '.ts': 'typescript', '.tsx': 'typescript',
    '.java': 'java',
    '.cpp': 'cpp', '.cc': 'cpp',
    '.c': 'c', '.h': 'c',
    '.cs': 'c_sharp',
    '.go': 'go',
    '.rs': 'rust',
    '.rb': 'ruby',
    '.php': 'php',
    '.swift': 'swift',
    '.kt': 'kotlin',
    '.r': 'r',
    '.sh': 'bash',
}

# These need special handling — no functions/classes
MARKUP_EXTENSIONS = {'.html', '.css', '.sql'}


# ── Description generation ────────────────────────────────────────────────

def generate_description(name: str, code: str, language: str) -> str:
    """
    Generate a plain English description of a function/class.
    Used as the embedded text — captures intent not syntax.

    Falls back to name-based description if Ollama is unavailable.
    """
    # Truncate very long functions — first 500 chars convey purpose
    code_sample = code[:500] if len(code) > 500 else code

    prompt = f"""In one sentence, describe what this {language} function or class does.
Focus on its PURPOSE, not its implementation details.
Return ONLY the description sentence. No preamble, no explanation.

{language} code:
{code_sample}

Description:"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": "mistral", "prompt": prompt, "stream": False},
            timeout=5  # don't block ingestion for slow LLM
        )
        desc = response.json()["response"].strip()
        # Clean up — remove quotes, truncate if too long
        desc = desc.strip('"\'')
        return desc[:300] if len(desc) > 300 else desc

    except Exception:
        # Fallback — use function name as description
        clean_name = re.sub(r'([A-Z])', r' \1', name).strip()
        return f"Function that handles {clean_name.lower()} operations"


# ── Python AST parser ─────────────────────────────────────────────────────

def parse_python(source: str, filename: str) -> list[dict]:
    """
    Parse Python source using built-in AST module.
    Extracts: functions, async functions, classes.
    Returns list of code unit dicts.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [{"error": f"Python syntax error: {e}"}]

    units = []
    imports = []

    # Extract imports first
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.append(module)

    # Extract top-level functions and classes
    for node in ast.iter_child_nodes(tree):

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            unit = extract_python_function(node, source, filename)
            units.append(unit)

        elif isinstance(node, ast.ClassDef):
            unit = extract_python_class(node, source, filename)
            units.append(unit)

    return units, imports


def extract_python_function(node, source: str, filename: str) -> dict:
    """Extract one Python function into a code unit dict."""
    name = node.name

    # Parameters
    args = [arg.arg for arg in node.args.args]
    params = ', '.join(args)

    # Return annotation if present
    returns = ""
    if node.returns:
        try:
            returns = ast.unparse(node.returns)
        except Exception:
            returns = ""

    # Docstring — prefer over AI description
    docstring = ast.get_docstring(node) or ""

    # Raw source code
    try:
        raw_code = ast.get_source_segment(source, node) or ""
    except Exception:
        raw_code = f"def {name}({params}): ..."

    # Function calls within this function
    calls = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                calls.append(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                calls.append(child.func.attr)

    is_async = isinstance(node, ast.AsyncFunctionDef)

    return {
        "type": "function",
        "name": name,
        "language": "python",
        "filename": filename,
        "parameters": args,
        "returns": returns,
        "docstring": docstring,
        "raw_code": raw_code,
        "calls": list(set(calls))[:20],  # cap at 20
        "line_start": node.lineno,
        "line_end": node.end_lineno,
        "is_async": is_async
    }


def extract_python_class(node, source: str, filename: str) -> dict:
    """Extract one Python class and all its methods."""
    name = node.name
    docstring = ast.get_docstring(node) or ""

    # Extract methods
    methods = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(child.name)

    try:
        raw_code = ast.get_source_segment(source, node) or ""
    except Exception:
        raw_code = f"class {name}: ..."

    return {
        "type": "class",
        "name": name,
        "language": "python",
        "filename": filename,
        "methods": methods,
        "docstring": docstring,
        "raw_code": raw_code,
        "line_start": node.lineno,
        "line_end": node.end_lineno,
        "parameters": [],
        "returns": "",
        "calls": [],
        "is_async": False
    }


# ── Tree-sitter parser ────────────────────────────────────────────────────

def parse_with_tree_sitter(source: str, filename: str, language_name: str) -> tuple:
    """
    Parse any supported language using tree-sitter.
    Returns (units, imports) same format as parse_python.
    """
    try:
        from tree_sitter_languages import get_parser
        parser = get_parser(language_name)
    except Exception as e:
        # tree-sitter not available or language not supported
        return [], []

    try:
        tree = parser.parse(bytes(source, 'utf-8'))
    except Exception:
        return [], []

    units = []
    imports = []

    # Node types that represent functions/classes per language
    function_types = {
        'javascript': ['function_declaration', 'arrow_function',
                       'function_expression', 'method_definition'],
        'typescript': ['function_declaration', 'arrow_function',
                       'method_definition', 'function_expression'],
        'java': ['method_declaration', 'constructor_declaration'],
        'cpp': ['function_definition'],
        'c': ['function_definition'],
        'c_sharp': ['method_declaration', 'constructor_declaration'],
        'go': ['function_declaration', 'method_declaration'],
        'rust': ['function_item', 'impl_item'],
        'ruby': ['method', 'singleton_method'],
        'php': ['function_definition', 'method_declaration'],
        'swift': ['function_declaration', 'init_declaration'],
        'kotlin': ['function_declaration', 'anonymous_function'],
        'r': ['function_definition'],
        'bash': ['function_definition'],
    }

    class_types = {
        'javascript': ['class_declaration', 'class_expression'],
        'typescript': ['class_declaration', 'interface_declaration'],
        'java': ['class_declaration', 'interface_declaration'],
        'cpp': ['class_specifier', 'struct_specifier'],
        'c_sharp': ['class_declaration', 'interface_declaration'],
        'go': ['type_declaration'],
        'rust': ['struct_item', 'trait_item'],
        'php': ['class_declaration', 'interface_declaration'],
        'swift': ['class_declaration', 'struct_declaration'],
        'kotlin': ['class_declaration', 'interface_declaration'],
    }

    target_func_types = set(function_types.get(language_name, []))
    target_class_types = set(class_types.get(language_name, []))

    source_lines = source.split('\n')

    def extract_node_text(node) -> str:
        """Extract source text for a tree-sitter node."""
        start_line = node.start_point[0]
        end_line = node.end_point[0]
        if start_line == end_line:
            return source_lines[start_line][node.start_point[1]:node.end_point[1]]
        lines = [source_lines[start_line][node.start_point[1]:]]
        lines.extend(source_lines[start_line+1:end_line])
        if end_line < len(source_lines):
            lines.append(source_lines[end_line][:node.end_point[1]])
        return '\n'.join(lines)

    def find_name(node) -> str:
        """Find the name child node of a function/class node."""
        for child in node.children:
            if child.type == 'identifier':
                return extract_node_text(child)
        return "anonymous"

    def traverse(node):
        node_type = node.type

        if node_type in target_func_types:
            name = find_name(node)
            raw_code = extract_node_text(node)
            units.append({
                "type": "function",
                "name": name,
                "language": language_name,
                "filename": filename,
                "raw_code": raw_code,
                "line_start": node.start_point[0] + 1,
                "line_end": node.end_point[0] + 1,
                "docstring": "",
                "parameters": [],
                "returns": "",
                "calls": [],
                "is_async": False
            })

        elif node_type in target_class_types:
            name = find_name(node)
            raw_code = extract_node_text(node)
            units.append({
                "type": "class",
                "name": name,
                "language": language_name,
                "filename": filename,
                "raw_code": raw_code,
                "line_start": node.start_point[0] + 1,
                "line_end": node.end_point[0] + 1,
                "docstring": "",
                "methods": [],
                "parameters": [],
                "returns": "",
                "calls": [],
                "is_async": False
            })

        for child in node.children:
            traverse(child)

    traverse(tree.root_node)
    return units, imports


# ── Markup and SQL special cases ──────────────────────────────────────────

def parse_html(source: str, filename: str) -> tuple:
    """Extract text content from HTML — strip tags."""
    import html2text
    converter = html2text.HTML2Text()
    converter.ignore_links = True
    converter.ignore_images = True
    converter.body_width = 0
    text = converter.handle(source)
    return [{"type": "html_content", "name": filename,
             "raw_code": text, "language": "html",
             "filename": filename, "docstring": "",
             "line_start": 1, "line_end": source.count('\n'),
             "parameters": [], "returns": "", "calls": [],
             "is_async": False}], []


def parse_css(source: str, filename: str) -> tuple:
    """Extract CSS selectors as a summary."""
    selectors = re.findall(r'^([^{]+)\s*\{', source, re.MULTILINE)
    selectors = [s.strip() for s in selectors if s.strip()]
    summary = f"CSS file with {len(selectors)} rules.\nSelectors: {', '.join(selectors[:30])}"
    return [{"type": "css_content", "name": filename,
             "raw_code": summary + '\n\n' + source[:1000],
             "language": "css", "filename": filename,
             "docstring": "", "line_start": 1,
             "line_end": source.count('\n'),
             "parameters": [], "returns": "", "calls": [],
             "is_async": False}], []


def parse_sql(source: str, filename: str) -> tuple:
    """Split SQL file into individual statements."""
    statements = [s.strip() for s in source.split(';') if s.strip()]
    units = []
    for i, stmt in enumerate(statements):
        # Get first line as name
        first_line = stmt.split('\n')[0][:80]
        units.append({
            "type": "sql_statement",
            "name": f"Statement {i+1}: {first_line}",
            "raw_code": stmt,
            "language": "sql",
            "filename": filename,
            "docstring": "",
            "line_start": 0,
            "line_end": 0,
            "parameters": [],
            "returns": "",
            "calls": [],
            "is_async": False
        })
    return units, []


# ── Main entry point ──────────────────────────────────────────────────────

def parse_code(file_path: str, filename: str) -> dict:
    """
    Main code parsing function.
    Detects language from extension, calls correct parser,
    generates AI descriptions for all extracted units.
    Returns structured result ready for ingestion.
    """
    ext = os.path.splitext(filename)[1].lower()

    # Read source
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()
    except Exception as e:
        return {"error": f"Could not read file: {e}"}

    if not source.strip():
        return {"error": "File is empty"}

    # Route to correct parser
    if ext == '.py':
        try:
            units, imports = parse_python(source, filename)
        except Exception as e:
            units, imports = [], []

    elif ext == '.html':
        units, imports = parse_html(source, filename)

    elif ext == '.css':
        units, imports = parse_css(source, filename)

    elif ext == '.sql':
        units, imports = parse_sql(source, filename)

    elif ext in TREE_SITTER_LANGUAGES:
        lang = TREE_SITTER_LANGUAGES[ext]
        units, imports = parse_with_tree_sitter(source, filename, lang)

    else:
        units, imports = [], []

    # If no units extracted — fall back to text chunking
    if not units:
        return {
            "type": "code_text_fallback",
            "filename": filename,
            "language": ext.lstrip('.'),
            "text": source,
            "imports": imports
        }

    # Generate descriptions for all units
    SKIP_AI_DESCRIPTIONS_THRESHOLD = 10  # more than 10 units → skip LLM calls

    if len(units) > SKIP_AI_DESCRIPTIONS_THRESHOLD:
        print(f"Large file ({len(units)} units) — skipping AI descriptions for speed")
        for unit in units:
            if "error" not in unit:
                if unit.get("docstring"):
                    unit["description"] = unit["docstring"]
                else:
                    # Use function name as description — no LLM call
                    unit["description"] = f"{unit['type']} named {unit['name']}"
    else:
        # Small file — generate proper descriptions
        for unit in units:
            if "error" not in unit:
                if unit.get("docstring"):
                    unit["description"] = unit["docstring"]
                else:
                    unit["description"] = generate_description(
                        unit["name"], unit["raw_code"], unit.get("language", "code")
                    )

    # Build file-level summary
    unit_names = [u["name"] for u in units if "error" not in u]
    file_summary = (
        f"Code file: {filename}\n"
        f"Language: {ext.lstrip('.')}\n"
        f"Contains {len(units)} code units: {', '.join(unit_names[:20])}\n"
    )
    if imports:
        file_summary += f"Imports: {', '.join(set(imports[:15]))}\n"

    return {
        "type": "code",
        "filename": filename,
        "language": ext.lstrip('.'),
        "units": units,
        "imports": imports,
        "file_summary": file_summary,
        "total_units": len(units)
    }