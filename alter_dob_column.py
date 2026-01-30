import pyodbc
from config import CONNECTION_STRING

def alter_columns():
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()

    try:
        print("Alterting EmployeeFamilyMembers table...")
        # We need to alter the DOB column to NVARCHAR to support text like "30 years"
        # First, we might need to drop dependencies if any, but likely none for a simple column.
        # However, you can't alter a column type easily if there is data that conflicts, but DATE to NVARCHAR is usually fine or requires drop/add.
        # Since it's a new system, simplistic ALTER COLUMN should work if data is compatible (YYYY-MM-DD fits in string).
        
        cursor.execute("""
            ALTER TABLE [dbo].[EmployeeFamilyMembers]
            ALTER COLUMN [DOB] [nvarchar](255) NULL
        """)
        
        print("✅ Column DOB altered successfully to NVARCHAR(255).")
        conn.commit()

    except Exception as e:
        print(f"❌ Error altering table: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    alter_columns()
