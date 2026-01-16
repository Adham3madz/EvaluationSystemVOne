
import pyodbc
from config import CONNECTION_STRING

def check_userinfo_schema():
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    
    try:
        print("Checking USERINFO schema...")
        cursor.execute("SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'USERINFO'")
        cols = cursor.fetchall()
        for col in cols:
            print(f"{col.COLUMN_NAME}: {col.DATA_TYPE}({col.CHARACTER_MAXIMUM_LENGTH}) Nullable:{col.IS_NULLABLE}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_userinfo_schema()
