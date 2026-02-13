
import pyodbc 
from config import CONNECTION_STRING
import time

def init_classes_db():
    print("⏳ Connecting to database...")
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        
        # 1. Create EmployeeClasses Table
        print("🛠️ Checking/Creating EmployeeClasses table...")
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='EmployeeClasses' AND xtype='U')
            BEGIN
                CREATE TABLE [AURAHR].[dbo].[EmployeeClasses] (
                    ClassID INT IDENTITY(1,1) PRIMARY KEY,
                    ClassName NVARCHAR(50) NOT NULL UNIQUE, -- The code, e.g., 'A', 'Manager'
                    DisplayName NVARCHAR(100) NULL          -- The label, e.g., 'A - Admin Staff'
                )
                PRINT '✅ Table EmployeeClasses created.'
            END
            ELSE
            BEGIN
                PRINT 'ℹ️ Table EmployeeClasses already exists.'
            END
        """)
        
        # 2. Seed Default Data (to ensure current system keeps working)
        print("🌱 Seeding default data...")
        default_classes = [
            ('A', 'A - موظف إداري'),
            ('B', 'B - موظف فني'),
            ('C', 'C - فئة ج'),
            ('مشرف', 'مشرف'),
            ('مدير', 'مدير')
        ]
        
        for code, display in default_classes:
            # Check if exists
            cursor.execute("SELECT Count(*) FROM [AURAHR].[dbo].[EmployeeClasses] WHERE ClassName = ?", (code,))
            if cursor.fetchone()[0] == 0:
                cursor.execute("INSERT INTO [AURAHR].[dbo].[EmployeeClasses] (ClassName, DisplayName) VALUES (?, ?)", (code, display))
                print(f"   + Added: {display}")
            
        conn.commit()
        print("✅ Database initialization complete.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'conn' in locals(): conn.close()

if __name__ == '__main__':
    init_classes_db()
