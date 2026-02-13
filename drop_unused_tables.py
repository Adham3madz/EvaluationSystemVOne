
import pyodbc
import config

# List of tables identified as unused in the previous step
tables_to_drop = [
    "ACGroup", "ACTimeZones", "ACUnlockComb", "AlarmLog", "AppLogs", "ArchiveReasons", "ArchiveWhys", 
    "AttendanceReviews", "AttendanceSummary", "AttParam", "AuditedExc", "AUTHDEVICE", 
    "CHECKEXACT", "CHECKINOUT", "DeptUsedSchs", "EmOpLog", "EmployeeLeaveBalances", 
    "EmployeeLeaveRequests", "EXCNOTES", "FaceTemp", "HOLIDAYS", "LeaveClass", "LeaveClass1", 
    "LeaveTypes", "LMS_Courses", "LMS_Sessions", "LMS_SessionTrainers", "LMS_Trainers", "Machines", 
    "NUM_RUN", "NUM_RUN_DEIL", "Places", "ReportItem", "ResignationReasons", "SchClass", 
    "ScheduleTypes", "SECURITYDETAILS", "ServerLog", "SessionInstructors", "SystemLog", "TBKEY", 
    "TBSMSALLOT", "TBSMSINFO", "TrainingSessionAttendance", "TrainingSession_Instructors", 
    "USER_OF_RUN", "USER_SPEDAY", "USER_TEMP_SCH", "UserACMachines", "UserACPrivilege", 
    "UserPlaces", "UsersMachines", "UserUpdates", "UserUsedSClasses"
]

def drop_tables():
    conn = None
    try:
        conn = pyodbc.connect(config.CONNECTION_STRING)
        cursor = conn.cursor()
        
        print(f"Attempting to drop {len(tables_to_drop)} tables...")
        
        # Disable constraints? No, let's remove referencing keys first.
        
        for table in tables_to_drop:
            print(f"Processing {table}...")
            
            # 1. Check if table exists
            check_query = "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = ?"
            cursor.execute(check_query, (table,))
            if cursor.fetchone()[0] == 0:
                print(f"  - Table {table} does not exist. Skipping.")
                continue
                
            # 2. Find and drop Foreign Keys referencing this table
            # This query finds FKs where the *referenced* table is the current table
            fk_query = """
            SELECT 
                fk.name AS ForeignKeyName,
                tp.name AS ParentTable
            FROM sys.foreign_keys AS fk
            INNER JOIN sys.tables AS tp ON fk.parent_object_id = tp.object_id
            INNER JOIN sys.tables AS tr ON fk.referenced_object_id = tr.object_id
            WHERE tr.name = ?
            """
            
            cursor.execute(fk_query, (table,))
            fks = cursor.fetchall()
            
            for fk_name, parent_table in fks:
                print(f"  - Dropping constraint {fk_name} on table {parent_table}...")
                drop_fk_sql = f"ALTER TABLE [{parent_table}] DROP CONSTRAINT [{fk_name}]"
                cursor.execute(drop_fk_sql)
                
            # 3. Drop the table
            print(f"  - Dropping table {table}...")
            drop_table_sql = f"DROP TABLE [{table}]"
            cursor.execute(drop_table_sql)
            print(f"  > Successfully dropped {table}")
            
        conn.commit()
        print("\nAll operations completed successfully.")
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"\nCRITICAL ERROR: {e}")
        print("Transaction rolled back.")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    confirm = input("Type 'DELETE' to confirm dropping these 50+ tables from the database: ")
    if confirm == "DELETE":
        drop_tables()
    else:
        print("Operation cancelled.")
