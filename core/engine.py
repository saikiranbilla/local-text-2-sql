import os
import duckdb
import pandas as pd
from pathlib import Path
from core.utils import sanitize_identifier


class DuckDBEngine:
    def __init__(self, data_dir: str):
        self.conn = duckdb.connect(database=":memory:")
        self._tables: list[str] = []

        for csv_path in Path(data_dir).glob("*.csv"):
            name = sanitize_identifier(csv_path.stem)
            self.conn.execute(
                f"CREATE TABLE \"{name}\" AS SELECT * FROM read_csv_auto('{csv_path.as_posix()}')"
            )
            row_count = self.conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            self._tables.append(name)
            print(f"Loaded table: {name} ({row_count} rows)")

    def execute(self, sql: str) -> pd.DataFrame:
        try:
            return self.conn.execute(sql).df()
        except Exception as e:
            raise ValueError(f"SQL execution failed: {e}") from e

    def get_schema(self) -> dict:
        schema = {}
        for table in self._tables:
            df = self.conn.execute(f'DESCRIBE "{table}"').df()
            schema[table] = [
                {"column": row["column_name"], "type": str(row["column_type"])}
                for _, row in df.iterrows()
            ]
        return schema

    def get_table_sample(self, table_name: str, n: int = 3) -> pd.DataFrame:
        return self.conn.execute(f'SELECT * FROM "{table_name}" LIMIT {n}').df()

    def get_schema_as_string(self) -> str:
        parts = []
        for table, columns in self.get_schema().items():
            col_str = ", ".join(f"{c['column']} ({c['type']})" for c in columns)
            parts.append(f"Table: {table}\nColumns: {col_str}")
        return "\n\n".join(parts)

    def detect_relationships(self) -> list[str]:
        from thefuzz import fuzz
        schema = self.get_schema()
        tables = list(schema.keys())
        relationships = []
        
        for i, t1 in enumerate(tables):
            for t2 in tables[i+1:]:
                for c1 in schema[t1]:
                    for c2 in schema[t2]:
                        # Require at least 85 ratio to avoid spurious joins
                        if fuzz.ratio(c1["column"].lower(), c2["column"].lower()) >= 85:
                            relationships.append(f"{t1}.{c1['column']} <-> {t2}.{c2['column']}")
        return relationships

    def get_categorical_values(self) -> dict[str, list[str]]:
        schema = self.get_schema()
        categoricals = {}
        for table, cols in schema.items():
            for col in cols:
                if col["type"] in ["VARCHAR", "TEXT", "STRING"]:
                    try:
                        count = self.conn.execute(f"SELECT COUNT(DISTINCT \"{col['column']}\") FROM \"{table}\"").fetchone()[0]
                        if count > 0 and count <= 50:
                            vals = self.conn.execute(f"SELECT DISTINCT \"{col['column']}\" FROM \"{table}\" WHERE \"{col['column']}\" IS NOT NULL").fetchall()
                            categoricals[f"{table}.{col['column']}"] = [v[0] for v in vals]
                    except Exception:
                        pass
        return categoricals


if __name__ == "__main__":
    engine = DuckDBEngine("data/")

    print("\n--- Schema ---")
    print(engine.get_schema_as_string())

    first_table = engine._tables[0]
    print(f"\n--- Sample rows from '{first_table}' ---")
    print(engine.get_table_sample(first_table))

    print("\n--- Test query ---")
    result = engine.execute("SELECT COUNT(*) as total_orders FROM orders")
    print(result)
