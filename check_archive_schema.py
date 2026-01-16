
import pyodbc
from config import CONNECTION_STRING

def check_schema():
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    
    print("--- EmployeeArchive Columns ---")
    try:
        cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'EmployeeArchive'")
        for row in cursor.fetchall():
            print(row.COLUMN_NAME)
    except:
        print("Table EmployeeArchive not found or error.")

    print("\n--- TerminationReasons Data ---")
    try:
        cursor.execute("SELECT TOP 5 * FROM TerminationReasons")
        rows = cursor.fetchall()
        for r in rows:
            print(r)
    except:
        print("Table TerminationReasons not found.")

    conn.close()

if __name__ == "__main__":
    check_schema()
