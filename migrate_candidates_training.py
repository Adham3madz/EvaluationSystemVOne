
import pyodbc
from config import CONNECTION_STRING

def migrate_candidates_table():
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        
        # Check existing columns
        cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Candidates'")
        columns = [row[0] for row in cursor.fetchall()]

        # Add TrainingEndDate if not exists
        if 'TrainingEndDate' not in columns:
            print("Adding TrainingEndDate...")
            cursor.execute("ALTER TABLE Candidates ADD TrainingEndDate DATETIME NULL")
        else:
            print("TrainingEndDate already exists.")

        # Add TrainingStartTime if not exists
        if 'TrainingStartTime' not in columns:
            print("Adding TrainingStartTime...")
            # Using VARCHAR to store "09:00" or "09:00 AM" flexibly
            cursor.execute("ALTER TABLE Candidates ADD TrainingStartTime NVARCHAR(20) NULL")
        else:
            print("TrainingStartTime already exists.")

        # Add TrainingEndTime if not exists
        if 'TrainingEndTime' not in columns:
            print("Adding TrainingEndTime...")
            cursor.execute("ALTER TABLE Candidates ADD TrainingEndTime NVARCHAR(20) NULL")
        else:
            print("TrainingEndTime already exists.")

        conn.commit()
        print("Migration complete!")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    migrate_candidates_table()
