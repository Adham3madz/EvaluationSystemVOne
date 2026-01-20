
import sqlite3
import pyodbc
from app import get_db_connection

def inspect_data():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all jobs and candidate counts by status
        cursor.execute("SELECT JobID, JobTitle FROM Jobs")
        jobs = cursor.fetchall()
        
        print("--- Job Candidate Statuses ---")
        for job in jobs:
            print(f"\nJob: {job.JobTitle} (ID: {job.JobID})")
            cursor.execute("SELECT Status, COUNT(*) as Cnt FROM Candidates WHERE JobID = ? GROUP BY Status", (job.JobID,))
            statuses = cursor.fetchall()
            total = 0
            for s in statuses:
                print(f"  - {s.Status}: {s.Cnt}")
                total += s.Cnt
            print(f"  Total Candidates: {total}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_data()
