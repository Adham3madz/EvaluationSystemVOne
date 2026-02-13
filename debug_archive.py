import pyodbc
from config import CONNECTION_STRING

def debug_archive_view():
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    
    print("--- Debugging Archived Employees Query ---")
    sql = """
        SELECT TOP 5 UI.USERID, EA.ArchiveTypeID
        FROM [AURAHR].[dbo].[USERINFO] AS UI
        LEFT JOIN [AURAHR].[dbo].[EmployeeArchive] EA ON UI.USERID = EA.UserID
        WHERE UI.IsActive = 0
        ORDER BY EA.EndDay DESC
    """
    cursor.execute(sql)
    rows = cursor.fetchall()
    
    if rows:
        print(f"Columns: {[column[0] for column in cursor.description]}")
        for r in rows:
            print(r)
    else:
        print("No archived employees found.")
        
    conn.close()

if __name__ == "__main__":
    debug_archive_view()
