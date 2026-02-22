import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import asyncio
from typing import Any

from thefuzz import fuzz
from sklearn.metrics.pairwise import cosine_similarity

from core.engine import DuckDBEngine
from prompts.templates import format_schema_for_prompt

_STOP_WORDS = {
    "the", "a", "an", "is", "in", "of", "for", "by", "and",
    "or", "to", "show", "me", "what", "how", "many", "which",
    "who", "where", "get", "find", "list", "give", "with", "per",
}


class SemanticResolver:
    def __init__(self, engine: DuckDBEngine, fuzzy_threshold: int = 70):
        self.engine = engine
        self.fuzzy_threshold = fuzzy_threshold
        self._schema = engine.get_schema()
        self._samples: dict[str, Any] = {
            table: engine.get_table_sample(table) for table in self._schema
        }
        self._all_columns: list[dict[str, str]] = [
            {"table": table, "column": col["column"], "type": col["type"]}
            for table, cols in self._schema.items()
            for col in cols
        ]

        try:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer('all-MiniLM-L6-v2')
            column_names = [e["column"].lower() for e in self._all_columns]
            self._column_embeddings = self._embedder.encode(column_names)
            self._mode = "hybrid"
            print("Hybrid matching enabled (fuzzy + semantic)")
        except ImportError:
            self._embedder = None
            self._column_embeddings = None
            self._mode = "fuzzy"
            print("Using fuzzy matching only")

    async def refresh_schema(self, new_schema: dict):
        self._schema = new_schema
        self._samples = {
            table: await asyncio.to_thread(self.engine.get_table_sample, table) for table in self._schema
        }
        self._all_columns = [
            {"table": table, "column": col["column"], "type": col["type"]}
            for table, cols in self._schema.items()
            for col in cols
        ]
        if self._embedder:
            column_names = [e["column"].lower() for e in self._all_columns]
            self._column_embeddings = await asyncio.to_thread(self._embedder.encode, column_names)

    def _get_semantic_scores(self, keyword: str) -> list[float]:
        keyword_embedding = self._embedder.encode([keyword])
        scores = cosine_similarity(
            keyword_embedding,
            self._column_embeddings
        )[0]
        return (scores * 100).tolist()

    def _extract_keywords(self, question: str) -> list[str]:
        tokens = re.split(r"[\s\W]+", question.lower())
        return [t for t in tokens if t and t not in _STOP_WORDS]

    def enrich(self, question: str, schema: dict) -> dict:
        keywords = self._extract_keywords(question)

        # Best match per (table, column) pair across all keywords
        best: dict[tuple[str, str], dict] = {}
        active_tables = set(schema.keys())

        for kw in keywords:
            semantic_scores = (
                self._get_semantic_scores(kw)
                if self._embedder else None
            )
            for i, entry in enumerate(self._all_columns):
                if entry["table"] not in active_tables:
                    continue
                    
                fuzzy_score = fuzz.partial_ratio(kw, entry["column"].lower())
                if semantic_scores is not None:
                    score = max(fuzzy_score, semantic_scores[i])
                else:
                    score = fuzzy_score
                if score >= self.fuzzy_threshold:
                    key = (entry["table"], entry["column"])
                    if key not in best or score > best[key]["score"]:
                        best[key] = {
                            "keyword": kw,
                            "column": entry["column"],
                            "table": entry["table"],
                            "score": score,
                        }

        column_matches = list(best.values())

        # Sample distinct values for each matched column
        value_hints: dict[str, list] = {}
        for match in column_matches:
            table, col = match["table"], match["column"]
            key = f"{table}.{col}"
            try:
                df = self.engine.execute(
                    f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL LIMIT 5"
                )
                value_hints[key] = df[col].tolist()
            except Exception:
                value_hints[key] = []

        relevant_tables = list(dict.fromkeys(m["table"] for m in column_matches))

        return {
            "original_schema": schema,
            "column_matches": column_matches,
            "value_hints": value_hints,
            "relevant_tables": relevant_tables,
        }

    def format_enriched_context(self, enriched: dict) -> str:
        relevant_tables = enriched.get("relevant_tables", [])
        original_schema = enriched.get("original_schema", {})
        
        # Filter schema to only relevant tables to reduce context size and latency
        filtered_schema = {
            t: original_schema[t] 
            for t in relevant_tables 
            if t in original_schema
        }
        
        # Fallback to full schema if no relevant tables found
        if not filtered_schema:
            filtered_schema = original_schema
            
        parts = [f"Matching mode: {self._mode}\n" + format_schema_for_prompt(filtered_schema)]

        if enriched["column_matches"]:
            parts.append("Semantic Hints:")

            for match in enriched["column_matches"]:
                parts.append(
                    f"  '{match['keyword']}' likely refers to "
                    f"{match['table']}.{match['column']}"
                )

            for key, values in enriched["value_hints"].items():
                if values:
                    sample = ", ".join(str(v) for v in values)
                    parts.append(f"  Sample values for {key}: {sample}")

        return "\n".join(parts)


if __name__ == "__main__":
    engine = DuckDBEngine("data/")
    resolver = SemanticResolver(engine)
    schema = engine.get_schema()

    questions = [
        "show me total revenue by customer",
        "which employees made the most sales",
        "what are the top product categories",
    ]

    for question in questions:
        print("=" * 60)
        print(f"Question: {question}")
        print("=" * 60)
        start = time.time()
        enriched = resolver.enrich(question, schema)
        elapsed = time.time() - start
        print(f"Resolved in {elapsed:.2f}s")
        print(f"Relevant tables: {enriched['relevant_tables']}")
        print(f"Column matches:  {[(m['keyword'], m['table']+'.'+m['column'], m['score']) for m in enriched['column_matches']]}")
        print()
        print(resolver.format_enriched_context(enriched))
        print()
