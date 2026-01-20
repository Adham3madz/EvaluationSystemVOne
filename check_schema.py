import pyodbc
from config import CONNECTION_STRING
import sys

try:
    print("Connecting...")
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    print("Connected!")
    
    print("\n--- TABLES ---")
    cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
    tables = [row.TABLE_NAME for row in cursor.fetchall()]
    print(tables)
    
    print("\n--- USERINFO COLUMNS ---")
    cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'USERINFO'")
    cols = [row.COLUMN_NAME for row in cursor.fetchall()]
    print(cols)

    conn.close()
except Exception as e:
    print(f"Error: {e}")
