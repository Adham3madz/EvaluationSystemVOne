
import pyodbc
from app import get_db_connection

def inspect_evaluations_schema():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print("--- Columns in Evaluations Table ---")
        cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Evaluations'")
        columns = cursor.fetchall()
        for col in columns:
            print(col.COLUMN_NAME)
            
        print("\n--- Columns in EvaluationCycles Table ---")
        try:
            cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'EvaluationCycles'")
            columns = cursor.fetchall()
            for col in columns:
                print(col.COLUMN_NAME)
        except Exception as e:
            print(f"Error accessing EvaluationCycles: {e}")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_evaluations_schema()
