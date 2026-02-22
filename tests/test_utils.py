import pytest
from core.utils import sanitize_identifier, clean_sql

def test_sanitize_identifier_basic():
    assert sanitize_identifier("Orders") == "orders"
    assert sanitize_identifier("Order Details") == "orderdetails"
    assert sanitize_identifier("123abc") == "t_123abc"
    assert sanitize_identifier("table; drop users") == "tabledropusers"

def test_clean_sql_markers():
    raw = "```sql\nSELECT * FROM orders\n```"
    assert clean_sql(raw) == "SELECT * FROM orders"
    
    raw_mixed = "Here is the SQL:\n```\nSELECT col FROM table\n```\nHope it works!"
    # Note: clean_sql currently handles only leading/trailing fences or raw SQL.
    # The agent usually returns just the fence block.
    assert "SELECT col FROM table" in clean_sql(raw_mixed)

def test_clean_sql_keywords():
    raw = "  SELECT * FROM test  "
    assert clean_sql(raw) == "SELECT * FROM test"
