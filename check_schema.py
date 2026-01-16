
import pyodbc
from config import CONNECTION_STRING

def check_schema():
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    
    try:
        print("Checking EvaluationCriteria schema...")
        cursor.execute("SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'EvaluationCriteria'")
        cols = cursor.fetchall()
        for col in cols:
            print(f"{col.COLUMN_NAME}: {col.DATA_TYPE}({col.CHARACTER_MAXIMUM_LENGTH})")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_schema()
