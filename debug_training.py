
import pyodbc
from app import get_db_connection

def debug_training_link(user_id=2):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print(f"--- Debugging Training Data for UserID: {user_id} ---")
        
        # 1. Check User Existence
        cursor.execute("SELECT USERID, NAME, BADGENUMBER FROM USERINFO WHERE USERID = ?", (user_id,))
        user = cursor.fetchone()
        if user:
            print(f"User Found: {user.NAME} (Badge: {user.BADGENUMBER})")
        else:
            print("User NOT found!")
            return

        # 2. Check Raw Enrollments
        print("\n--- Raw Enrollments (TrainingEnrollments) ---")
        cursor.execute("SELECT * FROM TrainingEnrollments WHERE EmployeeUserID = ?", (user_id,))
        enrollments = cursor.fetchall()
        for e in enrollments:
            print(f"EnrollID: {e.EnrollmentID}, SessionID: {e.SessionID}, Status: {e.PassStatus}")
            
        if not enrollments:
            print("No enrollments found for this UserID.")
            
        # 3. Check All Enrollments Top 5
        print("\n--- Recent 5 Enrollments (Any User) ---")
        cursor.execute("SELECT TOP 5 * FROM TrainingEnrollments ORDER BY EnrollmentID DESC")
        for e in enrollments:
            print(f"User: {e.EmployeeUserID} -> Session: {e.SessionID}")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_training_link()
