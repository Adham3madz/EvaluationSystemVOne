from app import get_db_connection

def check_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    tables = ['EmployeeExtendedInfo', 'EmployeeFamilyMembers', 'AppLogs']
    for t in tables:
        try:
            cursor.execute(f"SELECT TOP 1 * FROM {t}")
            print(f"Table '{t}' exists.")
        except Exception as e:
            print(f"Table '{t}' MISSING or Error: {e}")
    conn.close()

if __name__ == "__main__":
    check_tables()
