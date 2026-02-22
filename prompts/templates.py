from typing import Any


NORTHWIND_RELATIONSHIPS = """
Relationships:
  orders.customerID -> customers.customerID
  orders.employeeID -> employees.employeeID
  order_details.orderID -> orders.orderID
  order_details.productID -> products.productID
  products.categoryID -> categories.categoryID
"""

UIUC_EXAMPLES = """
### FEW-SHOT EXAMPLES (UIUC Datasets)

Q: Top 10 highest paid professors
A: SELECT "Employee Name", "Present Salary" 
   FROM graybook 
   WHERE LOWER("Job Title") LIKE '%professor%'
   ORDER BY "Present Salary" DESC LIMIT 10

Q: CS professors with excellent ratings
A: SELECT DISTINCT g."Employee Name", g."Present Salary"
   FROM graybook g
   JOIN uiuctredataset u 
   ON LOWER(g."Employee Name") LIKE '%' || LOWER(u.lname) || '%'
   AND g."Employee Name" LIKE '%' || u.fname || '%'
   WHERE LOWER(u.unit) = 'computer science'
   AND u.ranking = 'Excellent'

Q: Best CS courses by A grade percentage  
A: SELECT "Course Title", ROUND(("A+" + "A" + "A-") * 100.0 / Students, 1) AS a_percentage
   FROM uiucgpadataset1
   WHERE Subject = 'CS'
   ORDER BY a_percentage DESC LIMIT 10
"""


def get_sql_generation_prompt(
    schema: str,
    question: str,
    dialect: str = "DuckDB",
    chat_history: list[dict] = None
) -> list[dict[str, str]]:
    history_str = "None"
    if chat_history:
        history_str = "\n".join([f"Q: {h['question']}\nSQL: {h['sql']}" for h in chat_history])

    system = f"""You are an expert {dialect} SQL generator.

Rules:
- Only use tables and columns from the provided schema
- Return ONLY the raw SQL query, no markdown, no explanation
- Never use columns that don't exist in the schema
- Always use the exact column names provided in the schema context. If the schema uses snake_case (e.g., company_name), do not use spaces.
- For revenue calculations use: unitPrice * quantity * (1 - discount)
- Always alias computed columns with clear names
- Use {dialect} specific syntax (e.g. CURRENT_DATE, INTERVAL)
- CRITICAL: Always wrap ALL table and column identifiers in double quotes (e.g., SELECT "column_name" FROM "table_name") to avoid conflicts with reserved words and handle special characters.
- ALWAYS use LOWER() for string comparisons to ensure fuzzy matching (e.g. LOWER("dept") = 'cs')
- Use IN() with multiple value forms when filtering (e.g. WHERE LOWER("dept") IN ('cs', 'computer science'))
- If the question cannot be answered with the given schema, 
  return: SELECT 'I cannot answer this question with the available data' as message

### CONVERSATIONAL CONTEXT & PRONOUNS
You will be provided with a `chat_history`. If the user's current question contains pronouns (e.g., 'those', 'them', 'it', 'this') or refers to previous results (e.g., 'filter that by...', 'who teaches those courses?'), you MUST use the `chat_history` to resolve what they are talking about.
- Do NOT throw an error saying it's not in the database.
- Instead, look at the previously generated SQL or the previous user question, extract the specific entities (e.g., the actual course names), and write a brand new, fully self-contained SQL query that answers the follow-up question.
- If the previous query was `SELECT course_name FROM courses WHERE grade = 'A'`, and the user asks 'who teaches them?', your new query should be something like `SELECT professor FROM courses WHERE grade = 'A'`.
DATASET SPECIFIC KNOWLEDGE:

uiuctredataset columns:
- term: semester e.g. 'fa2003', 'sp2024'
- unit: department name e.g. 'COMPUTER SCIENCE' (mixed case)
- lname: instructor last name ALL CAPS e.g. 'CHALLEN'
- fname: first initial or name e.g. 'G' or 'GEOFFREY'
- role: 'Instructor', 'TA'
- ranking: 'Excellent', 'Outstanding'
- course: course number e.g. 225

uiucgpadataset1 columns:
- Year, Term, Subject e.g. 'CS', 'MATH', 'ECE'
- Number: course number e.g. 225
- "Course Title": full name
- "A+", "A", "A-", "B+", etc: grade counts
- Students: total students
- "Primary Instructor": "Lastname, Firstname" format

JOIN RULE (critical):
Always join these tables on last name only:
LOWER(SPLIT_PART(u1."Primary Instructor",',',1)) = LOWER(u.lname)
Never try to match first names - too inconsistent.

FEW SHOT EXAMPLES:

Q: Which CS courses have highest A grade percentage?
A:
SELECT "Course Title", "Number",
  ROUND(("A+" + "A" + "A-") * 100.0 / "Students", 1) 
  AS a_percentage
FROM uiucgpadataset1
WHERE "Subject" = 'CS'
AND "Students" > 10
ORDER BY a_percentage DESC
LIMIT 10

Q: Which professor teaches most CS students?
A:
SELECT "Primary Instructor", SUM("Students") AS total_students
FROM uiucgpadataset1
WHERE "Subject" = 'CS'
GROUP BY "Primary Instructor"
ORDER BY total_students DESC
LIMIT 10

Q: Which CS instructors are rated Excellent?
A:
SELECT DISTINCT lname, fname, ranking
FROM uiuctredataset
WHERE LOWER(unit) = 'computer science'
AND ranking = 'Excellent'
ORDER BY lname

Q: Hardest CS courses by failure rate?
A:
SELECT "Course Title", "Number",
  ROUND("F" * 100.0 / "Students", 1) AS fail_percentage
FROM uiucgpadataset1
WHERE "Subject" = 'CS'
AND "Students" > 20
ORDER BY fail_percentage DESC
LIMIT 10

Q: Which Excellent CS instructors give most A grades?
A:
SELECT 
  u1."Primary Instructor",
  ROUND(SUM(u1."A+" + u1."A" + u1."A-") * 100.0 / 
        SUM(u1."Students"), 1) AS a_percentage,
  SUM(u1."Students") AS total_students
FROM uiucgpadataset1 u1
JOIN uiuctredataset u
  ON LOWER(SPLIT_PART(u1."Primary Instructor",',',1)) 
   = LOWER(u.lname)
WHERE u1."Subject" = 'CS'
AND LOWER(u.unit) = 'computer science'
AND u.ranking = 'Excellent'
AND u1."Students" > 10
GROUP BY u1."Primary Instructor"
ORDER BY a_percentage DESC
LIMIT 10

Q: Which CS courses have improved grade distribution over years?
A:
SELECT "Number", "Course Title", Year,
  ROUND(("A+" + "A" + "A-") * 100.0 / "Students", 1) 
  AS a_percentage
FROM uiucgpadataset1
WHERE "Subject" = 'CS'
AND "Students" > 20
ORDER BY "Number", Year

Q: Compare A grade rates across CS ECE and MATH?
A:
SELECT "Subject",
  ROUND(SUM("A+" + "A" + "A-") * 100.0 / 
        SUM("Students"), 1) AS a_percentage,
  SUM("Students") AS total_students
FROM uiucgpadataset1
WHERE "Subject" IN ('CS', 'ECE', 'MATH')
GROUP BY "Subject"
ORDER BY a_percentage DESC

CRITICAL RULES:
1. Subject column uses abbreviations: CS, MATH, ECE, PHYS
2. unit column uses full names: COMPUTER SCIENCE
3. Always filter Students > 10 to avoid tiny courses skewing results
4. Always use SPLIT_PART for name joins, never full name matching
5. Always use ROUND() for percentages
6. Grade columns have quotes: "A+", "A-", "B+"
### CONVERSATIONAL HISTORY
{history_str}

{NORTHWIND_RELATIONSHIPS}

{UIUC_EXAMPLES}"""

    user = f"""Schema:
{schema}

Question: {question}

Return only the raw SQL query with no markdown or explanation."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def get_correction_prompt(
    schema: str,
    question: str,
    failed_sql: str,
    error_message: str,
    history: list[dict] = None
) -> list[dict[str, str]]:
    
    history_str = ""
    if history:
        history_str = "\nPrevious failed attempts:\n"
        for i, attempt in enumerate(history, 1):
            history_str += f"""
Attempt {i}:
SQL: {attempt['sql']}
Error: {attempt['error']}
"""

    user = f"""Original question: {question}

Schema:
{schema}
{history_str}
Current failing SQL:
{failed_sql}

Current error:
{error_message}

Fix the SQL query. Return only the corrected query with no markdown or explanation."""

    system = """You are an expert SQL debugger for DuckDB. 
You fix broken SQL queries.
Study all previous attempts to avoid repeating the same mistakes.
Return ONLY the raw SQL query."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def format_schema_for_prompt(schema: dict[str, list[dict[str, Any]]]) -> str:
    parts = []
    
    tables_lower = [t.lower() for t in schema.keys()]
    has_graybook = any("graybook" in t for t in tables_lower)
    has_tre = any("uiuctredataset" in t for t in tables_lower)
    has_gpa = any("uiucgpadataset1" in t for t in tables_lower)
    
    for table, columns in schema.items():
        col_lines = "\n".join(f"    {c['column']} ({c['type']})" for c in columns)
        
        table_note = ""
        t_lower = table.lower()
        if "graybook" in t_lower:
            table_note = "\n    NOTE: 'Job Title' is ALL CAPS ('PROFESSOR', 'ASST PROFESSOR'). 'Employee Name' format: 'Lastname, Firstname'. Always use LOWER() or ILIKE for string matching."
        elif "uiuctredataset" in t_lower:
            table_note = "\n    NOTE: Department is in column 'unit' (ALL CAPS e.g. 'COMPUTER SCIENCE'). 'role' column: 'Instructor', 'TA', 'Professor'. 'ranking' column: 'Excellent', 'Good', 'Fair'. 'lname' and 'fname' are separate columns (ALL CAPS)."
        elif "uiucgpadataset1" in t_lower:
            table_note = "\n    NOTE: 'Subject' uses abbreviations ('CS', 'MATH') NOT full names. 'Primary Instructor' format: 'Lastname, Firstname'. Grade columns ('A+', 'A', 'A-') are separate."

        parts.append(f"Table: {table}\n{col_lines}{table_note}")
        
    res = "\n\n".join(parts) + "\n" + NORTHWIND_RELATIONSHIPS
    
    cross_rules = []
    if has_graybook and has_tre:
        cross_rules.append("- graybook <-> uiuctredataset: Match on LOWER(graybook.\"Employee Name\") LIKE '%' || LOWER(uiuctredataset.lname) || '%' AND graybook.\"Employee Name\" LIKE '%' || uiuctredataset.fname || '%'")
    if has_graybook and has_gpa:
        cross_rules.append("- graybook <-> uiucgpadataset1: Match on graybook.\"Employee Name\" LIKE '%' || split_part(uiucgpadataset1.\"Primary Instructor\",',',1) || '%'")
        
    if cross_rules:
        res += "\n\n### CROSS TABLE JOIN RULES:\n" + "\n".join(cross_rules)
        
    return res


if __name__ == "__main__":
    sample_schema = {
        "orders": [
            {"column": "orderID", "type": "BIGINT"},
            {"column": "customerID", "type": "VARCHAR"},
            {"column": "employeeID", "type": "BIGINT"},
            {"column": "orderDate", "type": "TIMESTAMP"},
        ],
        "order_details": [
            {"column": "orderID", "type": "BIGINT"},
            {"column": "productID", "type": "BIGINT"},
            {"column": "unitPrice", "type": "DOUBLE"},
            {"column": "quantity", "type": "BIGINT"},
            {"column": "discount", "type": "DOUBLE"},
        ],
        "customers": [
            {"column": "customerID", "type": "VARCHAR"},
            {"column": "companyName", "type": "VARCHAR"},
            {"column": "country", "type": "VARCHAR"},
        ],
    }

    schema_str = format_schema_for_prompt(sample_schema)

    print("=" * 60)
    print("FORMATTED SCHEMA")
    print("=" * 60)
    print(schema_str)

    question = "What is the total revenue per customer, sorted highest first?"

    print("=" * 60)
    print("SQL GENERATION PROMPT")
    print("=" * 60)
    for msg in get_sql_generation_prompt(schema_str, question):
        print(f"[{msg['role'].upper()}]\n{msg['content']}\n")

    failed_sql = "SELECT customerID, SUM(total) FROM orders GROUP BY customerID"
    error_message = "Binder Error: Referenced column \"total\" not found in FROM clause!"

    print("=" * 60)
    print("CORRECTION PROMPT")
    print("=" * 60)
    for msg in get_correction_prompt(schema_str, question, failed_sql, error_message):
        print(f"[{msg['role'].upper()}]\n{msg['content']}\n")
