import pyodbc
from config import CONNECTION_STRING

def create_tables():
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()

    try:
        # 1. Table for General Extended Info (One-to-One with UserID)
        print("Creating EmployeeExtendedInfo table...")
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[EmployeeExtendedInfo]') AND type in (N'U'))
            BEGIN
                CREATE TABLE [dbo].[EmployeeExtendedInfo](
                    [UserID] [int] NOT NULL,
                    [SubDepartment] [nvarchar](255) NULL,
                    [PreviousAddress] [nvarchar](500) NULL,
                    [JobNature] [nvarchar](255) NULL,
                    [NationalID] [nvarchar](50) NULL,
                    CONSTRAINT [PK_EmployeeExtendedInfo] PRIMARY KEY CLUSTERED ([UserID] ASC)
                )
            END
        """)

        # 2. Table for Family Members (One-to-Many with UserID)
        # RelationType examples: 'spouse', 'parent', 'sibling', 'child', 'p_uncle', 'p_cousin', 'm_uncle', 'm_cousin'
        print("Creating EmployeeFamilyMembers table...")
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[EmployeeFamilyMembers]') AND type in (N'U'))
            BEGIN
                CREATE TABLE [dbo].[EmployeeFamilyMembers](
                    [MemberID] [int] IDENTITY(1,1) NOT NULL,
                    [UserID] [int] NOT NULL,
                    [RelationType] [nvarchar](50) NOT NULL,
                    [SortOrder] [int] DEFAULT 0,  -- To keep them in order (e.g. Sibling 1, Sibling 2)
                    [Name] [nvarchar](255) NULL,
                    [DOB] [date] NULL,
                    [Job] [nvarchar](255) NULL,
                    [Address] [nvarchar](500) NULL,
                    [Phone] [nvarchar](50) NULL,
                    CONSTRAINT [PK_EmployeeFamilyMembers] PRIMARY KEY CLUSTERED ([MemberID] ASC)
                )
            END
        """)

        conn.commit()
        print("✅ Tables created successfully.")

    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    create_tables()
