import re

def sanitize_identifier(identifier: str) -> str:
    """
    Sanitizes a string to be used as a SQL identifier (e.g. table or column name).
    - Allows only alphanumeric characters and underscores.
    - Ensures it starts with a letter or underscore.
    - Truncates to 64 characters.
    """
    # Remove all non-alphanumeric/underscore characters
    clean = re.sub(r'[^a-zA-Z0-9_]', '', identifier)
    
    # Ensure it starts with a letter or underscore
    if not clean or not re.match(r'^[a-zA-Z_]', clean):
        clean = "t_" + clean
        
    return clean[:64].lower()

def clean_sql(raw: str) -> str:
    """
    Cleans raw LLM response to extract a valid SQL statement.
    - Strips whitespace.
    - Handles markdown code fences (```sql ... ```).
    - Checks if the response already starts with known SQL keywords.
    """
    cleaned = raw.strip()

    # Already a clean SQL statement
    if cleaned.upper().startswith(("SELECT", "WITH", "INSERT", "UPDATE", "DELETE")):
        return cleaned

    # Strip markdown code fences
    if "```" in cleaned:
        lines = cleaned.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    return cleaned
