import pytest
from core.engine import DuckDBEngine
from agents.resolver import SemanticResolver
import os
import pandas as pd
import shutil

@pytest.fixture
def test_setup():
    test_dir = "test_resolver_data"
    os.makedirs(test_dir, exist_ok=True)
    pd.DataFrame({"customer_id": [1], "order_date": ["2023-01-01"]}).to_csv(os.path.join(test_dir, "orders.csv"), index=False)
    engine = DuckDBEngine(test_dir)
    resolver = SemanticResolver(engine)
    yield engine, resolver
    shutil.rmtree(test_dir)

def test_resolver_keywords(test_setup):
    engine, resolver = test_setup
    keywords = resolver._extract_keywords("Show me orders")
    assert "orders" in keywords
    assert "show" not in keywords

def test_resolver_enrich(test_setup):
    engine, resolver = test_setup
    schema = engine.get_schema()
    # keyword 'customer' fuzzy matches 'customer_id' column
    enriched = resolver.enrich("Get all customers", schema)
    assert "orders" in enriched["relevant_tables"]
    assert any(m["column"] == "customer_id" for m in enriched["column_matches"])
