
import pyodbc
from config import CONNECTION_STRING

def debug_archive():
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    
    print("--- 1. Recent EmployeeArchive Entries ---")
    cursor.execute("SELECT TOP 5 * FROM EmployeeArchive ORDER BY EndDay DESC")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
        
    print("\n--- 2. TerminationReasons ---")
    cursor.execute("SELECT * FROM TerminationReasons")
    rows = cursor.fetchall()
    for row in rows:
        print(row)

    conn.close()

if __name__ == "__main__":
    debug_archive()
