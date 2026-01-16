
import pyodbc
from config import CONNECTION_STRING

def check_tables():
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    
    print("Checking for Log tables...")
    cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
    tables = [row.TABLE_NAME for row in cursor.fetchall()]
    
    for t in tables:
        if 'log' in t.lower():
            print(f"Found table: {t}")
            cursor.execute(f"SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{t}'")
            for col in cursor.fetchall():
                print(f"  - {col.COLUMN_NAME}: {col.DATA_TYPE}")
                
    conn.close()

if __name__ == "__main__":
    check_tables()
