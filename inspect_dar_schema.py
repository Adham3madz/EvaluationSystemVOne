
import pyodbc
from config import CONNECTION_STRING

def get_db_connection():
    return pyodbc.connect(CONNECTION_STRING)

def inspect_table_schema(table_name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print(f"\n--- Columns in {table_name} Table ---")
        query = """
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = ?
        """
        cursor.execute(query, (table_name,))
        columns = cursor.fetchall()
        
        if not columns:
            print(f"No columns found for {table_name}. Check if table exists.")
        
        for col in columns:
            print(f"{col.COLUMN_NAME}: {col.DATA_TYPE}({col.CHARACTER_MAXIMUM_LENGTH})")
            
        conn.close()
    except Exception as e:
        print(f"Error inspecting {table_name}: {e}")

if __name__ == "__main__":
    inspect_table_schema('USERINFO')
    inspect_table_schema('EmployeeExtendedInfo')
    inspect_table_schema('EmployeeFamilyMembers')
