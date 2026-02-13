
import pyodbc
from config import CONNECTION_STRING

def fix_schema():
    print("Connecting to database...")
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        conn.autocommit = True
        cursor = conn.cursor()

        print("Altering USERINFO table columns...")
        
        # 1. Increase STREET (Address) to 255 chars
        try:
            print("Increasing STREET column size...")
            cursor.execute("ALTER TABLE [USERINFO] ALTER COLUMN [STREET] NVARCHAR(255)")
            print("✅ STREET column altered to NVARCHAR(255)")
        except Exception as e:
            print(f"⚠️ Error altering STREET: {e}")

        # 2. Increase OPHONE (Phone) to 50 chars
        try:
            print("Increasing OPHONE column size...")
            cursor.execute("ALTER TABLE [USERINFO] ALTER COLUMN [OPHONE] NVARCHAR(50)")
            print("✅ OPHONE column altered to NVARCHAR(50)")
        except Exception as e:
            print(f"⚠️ Error altering OPHONE: {e}")

        conn.close()
        print("\nSchema update process completed.")
    except Exception as e:
        print(f"❌ Critical Error: {e}")

if __name__ == "__main__":
    fix_schema()
