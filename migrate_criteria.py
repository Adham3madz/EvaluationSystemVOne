
import pyodbc
from config import CONNECTION_STRING

def migrate():
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    
    try:
        print("Starting migration...")
        
        # 1. Check if Foreign Key exists on AppliesToDeptID
        cursor.execute("""
            SELECT name 
            FROM sys.foreign_keys 
            WHERE parent_object_id = OBJECT_ID('EvaluationCriteria')
            AND referenced_object_id = OBJECT_ID('DEPARTMENTS')
        """)
        fks = cursor.fetchall()
        
        for fk in fks:
            fk_name = fk[0]
            print(f"Dropping Constraint: {fk_name}")
            cursor.execute(f"ALTER TABLE EvaluationCriteria DROP CONSTRAINT {fk_name}")
        
        # 2. Alter Column to NVARCHAR(MAX) to store comma separated IDs
        print("Altering AppliesToDeptID to NVARCHAR(MAX)...")
        cursor.execute("ALTER TABLE EvaluationCriteria ALTER COLUMN AppliesToDeptID NVARCHAR(MAX)")
        
        conn.commit()
        print("Migration successful: EvaluationCriteria.AppliesToDeptID is now NVARCHAR(MAX) and supports multiple departments.")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
