
import pyodbc
from config import CONNECTION_STRING

def seed_classes():
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        
        # Check if table exists, create if not
        try:
             cursor.execute("SELECT TOP 1 * FROM [AURAHR].[dbo].[EmployeeClasses]")
             print("Table exists.")
        except:
             print("Table does not exist. Creating...")
             cursor.execute("""
                CREATE TABLE [AURAHR].[dbo].[EmployeeClasses] (
                    ClassID INT IDENTITY(1,1) PRIMARY KEY,
                    ClassName NVARCHAR(50),
                    DisplayName NVARCHAR(100)
                )
             """)
             conn.commit()

        # Check count
        cursor.execute("SELECT COUNT(*) FROM [AURAHR].[dbo].[EmployeeClasses]")
        count = cursor.fetchone()[0]
        
        if count == 0:
            print("Seeding classes...")
            classes = [
                ('A', 'A - موظف إداري'),
                ('B', 'B - موظف فني'),
                ('C', 'C - فئة ج'),
                ('مشرف', 'مشرف'),
                ('مدير', 'مدير'),
                ('اداري', 'اداري B'),
                ('اداري C', 'اداري C'),
                ('فني', 'فني C'),
                ('فني A', 'فني A')
            ]
            
            for cls_code, cls_name in classes:
                cursor.execute("INSERT INTO [AURAHR].[dbo].[EmployeeClasses] (ClassName, DisplayName) VALUES (?, ?)", (cls_code, cls_name))
            
            conn.commit()
            print("Seeded successfully.")
        else:
            print(f"Table already has {count} rows.")
            # Print them just to be sure
            cursor.execute("SELECT * FROM [AURAHR].[dbo].[EmployeeClasses]")
            rows = cursor.fetchall()
            for r in rows:
                print(r)

        conn.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    seed_classes()
