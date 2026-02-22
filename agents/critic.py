import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from core.llm_client import chat as llm_chat
from core.utils import clean_sql
from prompts.templates import get_correction_prompt, format_schema_for_prompt
from core.engine import DuckDBEngine


class CriticAgent:
    def __init__(self, engine: DuckDBEngine, model: str = None, max_retries: int = 3):
        self.engine = engine
        # model param kept for API compatibility; active model is set in core/llm_client.py
        self.max_retries = max_retries

    async def execute_with_retry(self, sql: str, question: str, schema: dict) -> dict:
        schema_str = format_schema_for_prompt(schema)
        current_sql = sql
        history = []  # track all attempts

        for attempt in range(1, self.max_retries + 1):
            try:
                data = self.engine.execute(current_sql)
                return {
                    "success": True,
                    "sql": current_sql,
                    "data": data,
                    "attempts": attempt,
                }
            except ValueError as e:
                error_message = str(e)

                # Add to history before correcting
                history.append({
                    "sql": current_sql,
                    "error": error_message
                })

                if attempt == self.max_retries:
                    return {
                        "success": False,
                        "sql": current_sql,
                        "error": error_message,
                        "attempts": attempt,
                    }

                # Pass full history to correction prompt
                messages = get_correction_prompt(
                    schema_str, question, current_sql,
                    error_message, history
                )
                raw = await llm_chat(messages)
                current_sql = clean_sql(raw)

        return {
            "success": False,
            "sql": current_sql,
            "error": "Max retries exceeded",
            "attempts": self.max_retries,
        }


async def main():
    engine = DuckDBEngine("data/")
    critic = CriticAgent(engine)
    schema = engine.get_schema()
    question = "What is the total revenue per customer?"

    print("=" * 60)
    print("Scenario 1: Intentionally broken SQL")
    print("=" * 60)
    bad_sql = "SELECT customerName, SUM(total) FROM orders GROUP BY customerName"
    print(f"Input SQL:\n{bad_sql}\n")

    result = await critic.execute_with_retry(bad_sql, question, schema)

    if result["success"]:
        print(f"Corrected after {result['attempts']} attempt(s)")
        print(f"Final SQL:\n{result['sql']}\n")
        print(f"Result:\n{result['data']}")
    else:
        print(f"Failed after {result['attempts']} attempt(s)")
        print(f"Last SQL:\n{result['sql']}")
        print(f"Error: {result['error']}")

    print()
    print("=" * 60)
    print("Scenario 2: Valid SQL")
    print("=" * 60)
    good_sql = "SELECT COUNT(*) as total FROM orders"
    print(f"Input SQL:\n{good_sql}\n")

    result = await critic.execute_with_retry(good_sql, question, schema)

    if result["success"]:
        print(f"Succeeded on attempt {result['attempts']}")
        print(f"Result:\n{result['data']}")
    else:
        print(f"Failed after {result['attempts']} attempt(s)")
        print(f"Error: {result['error']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
