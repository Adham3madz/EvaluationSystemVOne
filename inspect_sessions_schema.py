
import pyodbc
from app import get_db_connection

def inspect_sessions_schema():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print("--- Columns in TrainingSessions Table ---")
        cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'TrainingSessions'")
        columns = cursor.fetchall()
        for col in columns:
            print(col.COLUMN_NAME)

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_sessions_schema()
