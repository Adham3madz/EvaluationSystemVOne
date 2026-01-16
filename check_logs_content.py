
import pyodbc
from config import CONNECTION_STRING

def check_content():
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    
    print("Checking UserLogsHr content...")
    try:
        cursor.execute("SELECT TOP 10 * FROM UserLogsHr ORDER BY Timestamp DESC")
        rows = cursor.fetchall()
        if not rows:
            print("Table UserLogsHr is empty.")
        for row in rows:
            print(f"{row.Timestamp} | {row.Username} | {row.Action}")
    except Exception as e:
        print(f"Error: {e}")
        
    conn.close()

if __name__ == "__main__":
    check_content()
