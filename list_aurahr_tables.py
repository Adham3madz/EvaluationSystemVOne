
import pyodbc
import config

try:
    conn = pyodbc.connect(config.CONNECTION_STRING)
    cursor = conn.cursor()
    
    query = """
    SELECT TABLE_NAME 
    FROM INFORMATION_SCHEMA.TABLES 
    WHERE TABLE_TYPE = 'BASE TABLE' 
    ORDER BY TABLE_NAME;
    """
    
    cursor.execute(query)
    tables = cursor.fetchall()
    
    print("Tables in database 'AURAHR':")
    print("-" * 30)
    for table in tables:
        print(table[0])
        
    conn.close()

except Exception as e:
    print(f"Error connecting to database: {e}")
