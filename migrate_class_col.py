
import pyodbc
from config import CONNECTION_STRING

def migrate_class_column():
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    
    try:
        print("Increasing size of employee_class column in EvaluationCriteria...")
        cursor.execute("ALTER TABLE EvaluationCriteria ALTER COLUMN employee_class NVARCHAR(MAX)")
        conn.commit()
        print("Migration successful: employee_class is now NVARCHAR(MAX).")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_class_column()
