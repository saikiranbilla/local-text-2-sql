import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import asyncio

import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import re
import shutil
from pathlib import Path

from core.orchestrator import Orchestrator
from core.llm_client import stream_chat
from core.utils import sanitize_identifier

router = APIRouter()

# Single orchestrator instance - initialized once
orchestrator = Orchestrator()


class QueryRequest(BaseModel):
    question: str
    selectedTables: list[str]
    chat_history: list[dict] = []


def make_event(type: str, **kwargs) -> str:
    return f"data: {json.dumps({'type': type, **kwargs}, default=str)}\n\n"


@router.post("/query")
async def query(request: QueryRequest):
    async def stream():
        question = request.question

        # 1. Immediately signal receipt
        yield make_event("thinking", content="Analyzing your question...")
        # Relevance check — skip if we are mid-conversation. Follow-up questions
        # use pronouns like "those" or "them" that look off-topic in isolation.
        if not request.chat_history:
            is_relevant = await asyncio.to_thread(
                orchestrator._is_database_question, question
            )
            if not is_relevant:
                yield make_event(
                    "error",
                    content=(
                        "I can only answer questions about your database. "
                        "Try asking about orders, customers, products, or employees."
                    ),
                )
                return

        selected_tables = list(request.selectedTables)
        
        if not selected_tables:
            # Fallback: if no tables selected, fetch all available tables
            df_tables = await asyncio.to_thread(
                orchestrator.engine.execute, 
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main';"
            )
            if "table_name" in df_tables.columns:
                selected_tables = df_tables["table_name"].tolist()

        if not selected_tables:
             yield make_event("error", content="No tables found in the database.")
             return

        # 2. Relevance passed
        yield make_event("thinking", content="Searching schema for relevant tables...")

        # Run resolver
        schema = await asyncio.to_thread(orchestrator.engine.get_schema)
        
        # Schema Pruning: Filter full schema to only include user-selected tables
        pruned_schema = {
            t: cols for t, cols in schema.items() 
            if t in selected_tables
        }
        
        enriched = await asyncio.to_thread(
            orchestrator.resolver.enrich, question, pruned_schema
        )

        # 3. Schema resolved
        table_list = ", ".join(enriched["relevant_tables"]) or "none found"
        yield make_event("thinking", content=f"Found relevant tables: {table_list}")

        # Generate SQL
        # Building the strict schema string explicitly per user instructions
        schema_parts = []
        for t in selected_tables:
            try:
                df_info = await asyncio.to_thread(orchestrator.engine.execute, f'PRAGMA table_info("{t}")')
                cols = [f"{row['name']} ({row['type']})" for _, row in df_info.iterrows()]
                schema_parts.append(f"Table: {t} | Columns: {', '.join(cols)}")
            except Exception as e:
                print(f"Warning: could not get PRAGMA for {t}: {e}")
                
        strict_schema_string = "\n".join(schema_parts)

        # Pass chat_history to the generator
        sql = await orchestrator.generator.generate_from_context(
            question, 
            strict_schema_string, 
            chat_history=request.chat_history
        )

        # 4. SQL generated
        yield make_event("sql", content=sql)

        # Execute with critic retry loop
        result = await orchestrator.critic.execute_with_retry(
            sql,
            question,
            enriched["original_schema"],
        )

        # 5. Refinement notice if retries were needed
        if result.get("attempts", 1) > 1:
            yield make_event(
                "thinking",
                content=f"Refining query... (attempt {result['attempts']})",
            )

        # 6. Final result
        if result["success"]:
            df: pd.DataFrame = result["data"]
            records = df.astype(object).where(pd.notna(df), None).to_dict(orient="records")
            yield make_event(
                "result",
                content=records,
                row_count=len(records),
                attempts=result["attempts"],
            )

            # 7. Natural Language Insight Summary
            try:
                yield make_event("thinking", content="Generating insight summary...")
                
                # Truncate records for context limit
                context_records = records[:50]
                
                system_prompt = "You are a data analyst. Given the user's original question and this JSON result set, provide exactly ONE sentence summarizing the core insight in plain English. Do not explain the SQL. Keep it punchy."
                # default=str handles datetime/date objects returned from DuckDB
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Question: {question}\n\nResults:\n{json.dumps(context_records, default=str)}"}
                ]
                
                # Proper async streaming loop: await each token without blocking the ASGI event loop
                stream_gen = stream_chat(messages, temperature=0.7, max_tokens=200)
                async for chunk in stream_gen:
                    yield make_event("summary", content=chunk)
                
                yield make_event("summary_done")
            except Exception as e:
                print(f"Summary streaming error: {e}")
                yield make_event("error", content=f"Insight generation failed: {str(e)}")

        else:
            yield make_event("error", content=result["error"])

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/tables")
async def get_tables():
    """Return all loaded tables with row counts and schema"""
    tables_info = []
    
    schema = await asyncio.to_thread(orchestrator.engine.get_schema)
    
    for table_name in orchestrator.engine._tables:
        try:
            # Get row count
            count_df = await asyncio.to_thread(
                orchestrator.engine.execute, f'SELECT COUNT(*) as count FROM "{table_name}"'
            )
            row_count = int(count_df.iloc[0]["count"])
            
            # Get columns from schema
            columns = schema.get(table_name, [])
            
            tables_info.append({
                "name": table_name,
                "row_count": row_count,
                "columns": columns
            })
        except Exception as e:
            print(f"Error getting info for table {table_name}: {e}")
            
    return {"tables": tables_info}


@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Upload a CSV file and load it as a new DuckDB table"""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")

    # Clean and sanitize table name
    base_name = os.path.splitext(file.filename)[0]
    table_name = sanitize_identifier(base_name)

    # Check if table already exists
    if table_name in orchestrator.engine._tables:
        try:
           # Wrap in double quotes for safety
           await asyncio.to_thread(orchestrator.engine.execute, f'DROP TABLE "{table_name}"')
           orchestrator.engine._tables.remove(table_name)
        except Exception:
           pass

    # Save to data directory
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    file_path = data_dir / f"{table_name}.csv"
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Load into DuckDB - wrap table name in double quotes
        load_sql = f'CREATE TABLE "{table_name}" AS SELECT * FROM read_csv_auto(\'{file_path.as_posix()}\', normalize_names=True)'
                   # Note: read_csv_auto path is already as_posix() and single-quoted, which is safe enough for internal paths.
        await asyncio.to_thread(orchestrator.engine.execute, load_sql)
        
        # Add to engine's tracking list
        orchestrator.engine._tables.append(table_name)
        
        # Get table info to return
        count_df = await asyncio.to_thread(
            orchestrator.engine.execute, f'SELECT COUNT(*) as count FROM "{table_name}"'
        )
        row_count = int(count_df.iloc[0]["count"])
        
        # Fresh schema
        schema = await asyncio.to_thread(orchestrator.engine.get_schema)
        await orchestrator.resolver.refresh_schema(schema)
        columns = schema.get(table_name, [])
        
        return {
            "success": True,
            "table_name": table_name,
            "row_count": row_count,
            "columns": columns
        }
    except Exception as e:
        # Clean up the file if it failed
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to load CSV: {str(e)}")
@router.delete("/tables/{table_name}")
async def delete_table(table_name: str):
    """Drop a table from DuckDB engine."""
    # Sanitize table name from URL
    table_name = sanitize_identifier(table_name)
    try:
        await asyncio.to_thread(orchestrator.engine.execute, f'DROP TABLE IF EXISTS "{table_name}"')
        if table_name in orchestrator.engine._tables:
            orchestrator.engine._tables.remove(table_name)
            
        file_path = Path("data") / f"{table_name}.csv"
        if file_path.exists():
            file_path.unlink()
            
        return {"success": True, "message": f"Table {table_name} deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete table: {str(e)}")
