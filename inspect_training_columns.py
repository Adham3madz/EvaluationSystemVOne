import pyodbc
from config import CONNECTION_STRING

def inspect_training_schema():
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        
        tables = ['TrainingCourses', 'TrainingSessions', 'TrainingEnrollments']
        
        for table in tables:
            print(f"\n=== Columns in {table} ===")
            cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table}'")
            columns = cursor.fetchall()
            for col in columns:
                print(f"- {col.COLUMN_NAME}")
            
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_training_schema()
