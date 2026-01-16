import pyodbc
from config import CONNECTION_STRING

def init_db():
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        
        # Create TerminationTypes Table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'TerminationTypes')
            BEGIN
                CREATE TABLE TerminationTypes (
                    TypeID INT IDENTITY(1,1) PRIMARY KEY,
                    TypeText NVARCHAR(255) NOT NULL
                )
            END
        """)
        
        # Create TerminationReasons Table
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'TerminationReasons')
            BEGIN
                CREATE TABLE TerminationReasons (
                    ReasonID INT IDENTITY(1,1) PRIMARY KEY,
                    TypeID INT NOT NULL,
                    ReasonText NVARCHAR(MAX) NOT NULL,
                    FOREIGN KEY (TypeID) REFERENCES TerminationTypes(TypeID) ON DELETE CASCADE
                )
            END
        """)
        
        # Populate with some defaults if empty
        cursor.execute("SELECT COUNT(*) FROM TerminationTypes")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO TerminationTypes (TypeText) VALUES (N'استقالة'), (N'فصل'), (N'انتهاء عقد')")
            
            # Get IDs
            cursor.execute("SELECT TypeID, TypeText FROM TerminationTypes")
            types = {row.TypeText: row.TypeID for row in cursor.fetchall()}
            
            # Add Reasons
            resignation_reasons = [
                (types.get('استقالة'), 'عرض عمل آخر'),
                (types.get('استقالة'), 'أسباب شخصية'),
                (types.get('استقالة'), 'ظروف عائلية')
            ]
            
            dismissal_reasons = [
                (types.get('فصل'), 'ضعف الأداء'),
                (types.get('فصل'), 'سوء السلوك')
            ]
            
            contract_reasons = [
                (types.get('انتهاء عقد'), 'عدم التجديد'),
                (types.get('انتهاء عقد'), 'انتهاء المشروع')
            ]
            
            all_reasons = resignation_reasons + dismissal_reasons + contract_reasons
            
            cursor.executemany("INSERT INTO TerminationReasons (TypeID, ReasonText) VALUES (?, ?)", all_reasons)
            
        conn.commit()
        print("Tables created and initialized successfully.")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    init_db()
