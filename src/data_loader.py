import pandas as pd
import duckdb as ddb
from pathlib import Path

def load_and_inspect():
    """
    Load sales data from CSV into DuckDB, inspect schema, 
    and run test queries.
    """
    csv_path = Path('data/sales_data.csv')

    try:
        # Load CSV
        df = pd.read_csv(csv_path)
        print("Data loaded successfully!")
        print("First 5 rows of the dataset:")
        print(df.head())
        
        # Convert date column to datetime
        df['date'] = pd.to_datetime(df['date'])
        
        # Create in-memory DuckDB connection
        con = ddb.connect(":memory:")
        
        try:
            # Load DataFrame into DuckDB
            con.register("df", df)
            con.execute("CREATE TABLE sales AS SELECT * FROM df")
            
            # Inspect schema
            schema_info = con.execute("PRAGMA table_info('sales')").fetchall()
            print("\nTable schema:")
            for row in schema_info:
                print(f"- {row[1]}: {row[2]}")
            
            # Get unique categorical values
            customer_types = con.execute(
                "SELECT DISTINCT customer_type FROM sales ORDER BY customer_type"
            ).fetchall()
            print(f"\nUnique customer types:\n{[row[0] for row in customer_types]}")
            
            unique_regions = con.execute(
                "SELECT DISTINCT region FROM sales ORDER BY region"
            ).fetchall()
            print(f"\nUnique regions:\n{[row[0] for row in unique_regions]}")
            
            # Query 1: Total revenue by customer_type
            query_1 = """
                SELECT customer_type, SUM(revenue) as total_revenue
                FROM sales
                GROUP BY customer_type
                ORDER BY total_revenue DESC
            """
            print("\nQuery 1 - Total revenue by customer type:")
            print(con.execute(query_1).df())
            
            # Query 2: Sales count by region
            query_2 = """
                SELECT region, COUNT(*) as sales_count
                FROM sales
                GROUP BY region
                ORDER BY sales_count DESC
            """
            print("\nQuery 2 - Sales count by region:")
            print(con.execute(query_2).df())
            
            # Query 3: High-value sales
            query_3 = """
                SELECT * FROM sales 
                WHERE revenue > 20000
                ORDER BY date
            """
            print("\nQuery 3 - High-value sales (>20000):")
            print(con.execute(query_3).df())
            
        finally:
            con.close()
            
    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found.")
        return
    except Exception as e:
        print(f"Error: {e}")
        return

if __name__ == "__main__":
    load_and_inspect()