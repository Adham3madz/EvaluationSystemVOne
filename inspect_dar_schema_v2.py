
import pyodbc
from config import CONNECTION_STRING

def get_db_connection():
    return pyodbc.connect(CONNECTION_STRING)

def inspect_userinfo():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print("\n--- Columns in USERINFO Table (Specific) ---")
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'USERINFO' 
            AND COLUMN_NAME IN ('OPHONE', 'STREET', 'SSN', 'TITLE')
        """)
        columns = cursor.fetchall()
        
        for col in columns:
            print(f"{col.COLUMN_NAME}: {col.DATA_TYPE}({col.CHARACTER_MAXIMUM_LENGTH})")
            
        print("\n--- Checking EmployeeFamilyMembers RelationType length ---")
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'EmployeeFamilyMembers' AND COLUMN_NAME = 'RelationType'
        """)
        col = cursor.fetchone()
        if col:
            print(f"{col.COLUMN_NAME}: {col.DATA_TYPE}({col.CHARACTER_MAXIMUM_LENGTH})")

        conn.close()
    except Exception as e:
        print(f"Error inspecting USERINFO: {e}")

if __name__ == "__main__":
    inspect_userinfo()
