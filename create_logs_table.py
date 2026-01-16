
import pyodbc
from config import CONNECTION_STRING

def create_app_logs_table():
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    
    table_sql = """
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[AppLogs]') AND type in (N'U'))
    BEGIN
        CREATE TABLE [dbo].[AppLogs](
            [LogID] [int] IDENTITY(1,1) NOT NULL,
            [UserID] [int] NULL,
            [Username] [nvarchar](100) NULL,
            [Module] [nvarchar](50) NULL,
            [ActionType] [nvarchar](50) NULL,
            [Description] [nvarchar](max) NULL,
            [Timestamp] [datetime] DEFAULT GETDATE(),
            PRIMARY KEY CLUSTERED ([LogID] ASC)
        )
        PRINT 'Table AppLogs created successfully.'
    END
    ELSE
    BEGIN
        PRINT 'Table AppLogs already exists.'
    END
    """
    
    try:
        cursor.execute(table_sql)
        conn.commit()
    except Exception as e:
        print(f"Error creating table: {e}")
        
    conn.close()

if __name__ == "__main__":
    create_app_logs_table()
