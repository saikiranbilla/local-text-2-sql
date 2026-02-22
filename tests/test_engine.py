import pytest
import pandas as pd
from core.engine import DuckDBEngine
import os
import shutil

@pytest.fixture
def test_engine():
    # Create a temp data dir
    test_dir = "test_data"
    os.makedirs(test_dir, exist_ok=True)
    
    # Create a dummy CSV
    csv_path = os.path.join(test_dir, "test_table.csv")
    pd.DataFrame({"id": [1, 2], "name": ["a", "b"]}).to_csv(csv_path, index=False)
    
    engine = DuckDBEngine(test_dir)
    yield engine
    
    # Cleanup
    shutil.rmtree(test_dir)

def test_engine_schema(test_engine):
    schema = test_engine.get_schema()
    assert "test_table" in schema
    assert schema["test_table"][0]["column"] == "id"
    assert schema["test_table"][1]["column"] == "name"

def test_engine_execute(test_engine):
    df = test_engine.execute('SELECT * FROM "test_table"')
    assert len(df) == 2
    assert df.iloc[0]["name"] == "a"
