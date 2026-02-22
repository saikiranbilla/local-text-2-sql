from dotenv import load_dotenv
load_dotenv()

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm_client import chat as llm_chat
from core.utils import clean_sql
from prompts.templates import get_sql_generation_prompt, format_schema_for_prompt


class SQLGeneratorAgent:
    def __init__(self, model: str = None):
        # model param kept for API compatibility; active model is set in core/llm_client.py
        pass

    async def generate(self, question: str, schema: dict, chat_history: list[dict] = None) -> str:
        schema_str = format_schema_for_prompt(schema)
        messages = get_sql_generation_prompt(schema_str, question, chat_history=chat_history)
        raw = await llm_chat(messages)
        return clean_sql(raw)

    async def generate_from_context(self, question: str, context: str, chat_history: list[dict] = None) -> str:
        messages = get_sql_generation_prompt(context, question, chat_history=chat_history)
        raw = await llm_chat(messages)
        return clean_sql(raw)


async def main():
    from core.engine import DuckDBEngine

    engine = DuckDBEngine("data/")
    agent = SQLGeneratorAgent()

    question = "How many orders does each customer have? Show top 10 by order count"

    print("Question:", question)
    print()

    sql = await agent.generate(question, engine.get_schema())
    print("Generated SQL:")
    print(sql)
    print()

    result = engine.execute(sql)
    print("Results:")
    print(result)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
