from app import get_db_connection

def create_applogs_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='AppLogs' AND xtype='U')
            BEGIN
                CREATE TABLE AppLogs (
                    LogID INT IDENTITY(1,1) PRIMARY KEY,
                    UserID INT,
                    Username NVARCHAR(100),
                    Module NVARCHAR(100),
                    ActionType NVARCHAR(100),
                    Description NVARCHAR(MAX),
                    Timestamp DATETIME DEFAULT GETDATE()
                )
                PRINT 'AppLogs table created.'
            END
            ELSE
            BEGIN
                PRINT 'AppLogs table already exists.'
            END
        """)
        conn.commit()
    except Exception as e:
        print(f"Error creating table: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    create_applogs_table()
