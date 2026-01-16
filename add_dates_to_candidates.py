
import pyodbc
from config import CONNECTION_STRING

def add_columns():
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    
    # Check if EndDate exists
    cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Candidates' AND COLUMN_NAME = 'EndDate'")
    if not cursor.fetchone():
        print("Adding EndDate column...")
        cursor.execute("ALTER TABLE Candidates ADD EndDate DATETIME")
        conn.commit()
    else:
        print("EndDate already exists.")

    # Check if HireDate exists
    cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Candidates' AND COLUMN_NAME = 'HireDate'")
    if not cursor.fetchone():
        print("Adding HireDate column...")
        cursor.execute("ALTER TABLE Candidates ADD HireDate DATETIME")
        conn.commit()
    else:
        print("HireDate already exists.")
        
    conn.close()

if __name__ == "__main__":
    add_columns()
