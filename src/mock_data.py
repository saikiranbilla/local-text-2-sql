import pandas as pd
import numpy as np

# Create mock data
data = {
    'date': pd.date_range(start='2023-01-01', periods=50),
    'customer_type': np.random.choice(['Enterprise', 'SMB', 'Startup'], 50),
    'product': np.random.choice(['Widget A', 'Widget B', 'Gadget X'], 50),
    'revenue': np.random.randint(5000, 50000, 50),
    'region': np.random.choice(['North America', 'Europe', 'Asia', 'South America'], 50)
}

df_mock = pd.DataFrame(data)

# Create the directory if it doesn't exist
from pathlib import Path
Path("data").mkdir(exist_ok=True)

# Save to CSV
df_mock.to_csv("data/sales_data.csv", index=False)
print("File 'data/sales_data.csv' created successfully!")