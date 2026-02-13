
import pyodbc
from config import CONNECTION_STRING

try:
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    
    print("--- Checking Candidates with Status = 'Training' ---")
    cursor.execute("SELECT Count(*) FROM Candidates WHERE Status = 'Training'")
    count = cursor.fetchone()[0]
    print(f"Total Trainees found: {count}")
    
    if count > 0:
        print("\n--- Sample Trainee Data ---")
        cursor.execute("SELECT TOP 5 CandidateID, FullName, Status, JobID FROM Candidates WHERE Status = 'Training'")
        for row in cursor.fetchall():
            print(row)
            
        print("\n--- Checking Job Join ---")
        cursor.execute("""
            SELECT C.CandidateID, C.FullName, J.JobTitle 
            FROM Candidates C 
            LEFT JOIN Jobs J ON C.JobID = J.JobID 
            WHERE C.Status = 'Training'
        """)
        for row in cursor.fetchall():
            print(f"Candidate: {row.FullName}, Job: {row.JobTitle}")
            if row.JobTitle is None:
                print("!! WARNING: JobTitle is None. Inner Join would exclude this record !!")

except Exception as e:
    print(f"Error: {e}")
finally:
    if 'conn' in locals():
        conn.close()
