
import pyodbc
from config import CONNECTION_STRING

def add_columns():
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        
        # Add DaysAfterPrerequisite
        try:
            cursor.execute("ALTER TABLE EvaluationTypes ADD DaysAfterPrerequisite INT NULL")
            print("Added DaysAfterPrerequisite")
        except Exception as e:
            print(f"DaysAfterPrerequisite might already exist: {e}")
            
        # Add ExcludedClasses
        try:
            cursor.execute("ALTER TABLE EvaluationTypes ADD ExcludedClasses NVARCHAR(255) NULL")
            print("Added ExcludedClasses")
        except Exception as e:
            print(f"ExcludedClasses might already exist: {e}")

        conn.commit()
        conn.close()
        print("Schema update complete.")
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    add_columns()
