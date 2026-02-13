import pyodbc
from config import CONNECTION_STRING

def show_training_data():
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        
        print("\n=== 1. Searching for 'Training' in Departments ===")
        cursor.execute("SELECT * FROM DEPARTMENTS WHERE DEPTNAME LIKE N'%تدريب%' OR DEPTNAME LIKE N'%تأهيل%'")
        depts = cursor.fetchall()
        for dept in depts:
            print(f"ID: {dept.DEPTID}, Name: {dept.DEPTNAME}")
            
        print("\n=== 2. Sample Courses (Last 5) ===")
        cursor.execute("SELECT TOP 5 CourseID, CourseName, CourseType FROM TrainingCourses ORDER BY CourseID DESC")
        courses = cursor.fetchall()
        for c in courses:
            print(f"ID: {c.CourseID}, Name: {c.CourseName}, Type: {c.CourseType}")

        print("\n=== 3. Sample Sessions (Last 5) ===")
        cursor.execute("SELECT TOP 5 SessionID, CourseID, StartDate, EndDate, Location FROM TrainingSessions ORDER BY SessionID DESC")
        sessions = cursor.fetchall()
        for s in sessions:
            print(f"SessionID: {s.SessionID}, CourseID: {s.CourseID}, Start: {s.StartDate}, Loc: {s.Location}")

        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    show_training_data()
