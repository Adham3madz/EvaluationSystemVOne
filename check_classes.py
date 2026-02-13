
import pyodbc
from config import CONNECTION_STRING
try:
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    cursor.execute('SELECT ClassID, ClassName, DisplayName FROM [AURAHR].[dbo].[EmployeeClasses]')
    rows = cursor.fetchall()
    print("Existing Classes:")
    for r in rows:
        print(r)
except Exception as e:
    print(e)
