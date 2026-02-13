
import pyodbc 
from config import CONNECTION_STRING

try:
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    
    print("\n--- Candidate Status Distribution ---")
    cursor.execute("SELECT Status, Count(*) FROM Candidates GROUP BY Status")
    for row in cursor.fetchall():
        print(f"Status: {row.Status}, Count: {row[1]}")
        
except Exception as e:
    print(f"Error: {e}")
finally:
    if 'conn' in locals():
        conn.close()
