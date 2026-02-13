import pyodbc
from config import CONNECTION_STRING

def list_tables():
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        
        # Query to get all user tables
        query = """
        SELECT TABLE_SCHEMA, TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
        
        cursor.execute(query)
        tables = cursor.fetchall()
        
        print("\n=== Database Tables in 'AURAHR' ===")
        print(f"{'Schema':<10} | {'Table Name':<30}")
        print("-" * 45)
        
        for schema, name in tables:
            print(f"{schema:<10} | {name:<30}")
            
        conn.close()
        
    except Exception as e:
        print(f"Error connecting to database: {e}")

if __name__ == "__main__":
    list_tables()
