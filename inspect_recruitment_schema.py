
import pyodbc
from config import CONNECTION_STRING

def inspect_schema():
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        cursor.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Candidates'")
        columns = cursor.fetchall()
        print("Columns in RecruitmentCandidates:")
        for col in columns:
            print(f"- {col[0]} ({col[1]})")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_schema()
