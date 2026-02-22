import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
from typing import Any

from thefuzz import fuzz

from core.engine import DuckDBEngine
from agents.generator import SQLGeneratorAgent
from agents.critic import CriticAgent
from agents.resolver import SemanticResolver

# Business keywords are now derived dynamically from the schema in Orchestrator._is_database_question



class Orchestrator:
    def __init__(self, data_dir: str = "data/", model: str = None):
        self.engine = DuckDBEngine(data_dir)
        self.resolver = SemanticResolver(self.engine)
        self.generator = SQLGeneratorAgent(model=model)
        self.critic = CriticAgent(self.engine)

    async def run(self, question: str) -> dict:
        if not self._is_database_question(question):
            schema = self.engine.get_schema()
            table_examples = ", ".join(list(schema.keys())[:3])
            return {
                "success": False,
                "error": (
                    "I can only answer questions about your database. "
                    f"Try asking about {table_examples if table_examples else 'your data'}."
                ),
                "attempts": 0,
            }

        schema = self.engine.get_schema()
        enriched = self.resolver.enrich(question, schema)
        context = self.resolver.format_enriched_context(enriched)

        relationships = self.engine.detect_relationships()
        if relationships:
            context += "\n\nDetected Join Relationships:\n" + "\n".join(relationships)

        categoricals = self.engine.get_categorical_values()
        if categoricals:
            context += "\n\nCategorical Values:\n"
            for k, v in categoricals.items():
                context += f"{k}: {', '.join(v)}\n"

        sql = await self.generator.generate_from_context(question, context)
        result = await self.critic.execute_with_retry(sql, question, enriched["original_schema"])

        result["question"] = question
        result["relevant_tables"] = enriched["relevant_tables"]
        result["column_matches"] = enriched["column_matches"]

        return result

    def _is_database_question(self, question: str) -> bool:
        words = re.split(r"[\s\W]+", question.lower())
        words = [w for w in words if w]

        schema = self.engine.get_schema()
        table_names = list(schema.keys())
        
        # Derive "business keywords" dynamically from column names
        dynamic_keywords = set()
        for table in table_names:
            for col_info in schema[table]:
                # Split column names by underscore and add to keywords
                parts = col_info["column"].lower().split("_")
                dynamic_keywords.update(parts)
        
        # Also add table names to dynamic keywords
        for table in table_names:
            dynamic_keywords.update(table.lower().split("_"))

        for word in words:
            # Check against dynamic keywords
            if word in dynamic_keywords:
                return True
            # Fuzzy match against table names
            for table in table_names:
                if fuzz.partial_ratio(word, table) >= 70:
                    return True

        return False


async def main():
    orchestrator = Orchestrator("data/")

    questions = [
        "How many orders were placed in 1997?",
        "Show me total revenue per customer sorted highest first",
        "Which product category generates most revenue",
        "What is the meaning of life",
    ]

    for question in questions:
        print("=" * 60)
        print(f"Q: {question}")
        print("=" * 60)

        result = await orchestrator.run(question)

        if result["success"]:
            print(f"Success after {result['attempts']} attempt(s)")
            print(f"Relevant tables: {result.get('relevant_tables', [])}")
            print(f"\nSQL:\n{result['sql']}\n")
            print("Results (first 5 rows):")
            print(result["data"].head(5).to_string(index=False))
        else:
            print(f"Failed after {result['attempts']} attempt(s)")
            print(f"Error: {result['error']}")

        print()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
