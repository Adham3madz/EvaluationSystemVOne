
import pyodbc
from config import CONNECTION_STRING

def check_statuses():
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    
    print("Checking Candidate Statuses for Job 1052...")
    cursor.execute("SELECT CandidateID, FullName, Status FROM Candidates WHERE JobID = 1052")
    rows = cursor.fetchall()
    
    for row in rows:
        print(f"ID: {row.CandidateID}, Name: {row.FullName}, Status: '{row.Status}'")
        
    conn.close()

if __name__ == "__main__":
    check_statuses()
