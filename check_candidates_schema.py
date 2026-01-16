
import pyodbc
from config import CONNECTION_STRING

def check_candidates():
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    print("--- Candidates Columns ---")
    cursor.execute("SELECT COLUMN_NAME, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Candidates'")
    for row in cursor.fetchall():
        print(row)
    conn.close()

if __name__ == "__main__":
    check_candidates()
