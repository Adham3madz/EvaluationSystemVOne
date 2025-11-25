# import sqlite3
# import os

# def reset_database():
#     # Remove existing database file
#     if os.path.exists('evaluation_system.db'):
#         os.remove('evaluation_system.db')
#         print("Old database removed")
    
#     # Create new database
#     conn = sqlite3.connect('evaluation_system.db')
#     cursor = conn.cursor()
    
#     # Create tables
#     cursor.execute('''
#         CREATE TABLE IF NOT EXISTS Users (
#             UserID INTEGER PRIMARY KEY AUTOINCREMENT,
#             Username TEXT UNIQUE NOT NULL,
#             PasswordHash TEXT NOT NULL,
#             RoleID INTEGER,
#             Name TEXT,
#             DepartmentID INTEGER,
#             employee_class TEXT DEFAULT 'لم تضاف'
#         )
#     ''')
    
#     cursor.execute('''
#         CREATE TABLE IF NOT EXISTS USERINFO (
#             USERID INTEGER PRIMARY KEY AUTOINCREMENT,
#             BADGENUMBER TEXT,
#             SSN TEXT,
#             NAME TEXT NOT NULL,
#             GENDER TEXT,
#             TITLE TEXT,
#             DEFAULTDEPTID INTEGER,
#             PositionID INTEGER,
#             employee_class TEXT DEFAULT 'لم تضاف',
#             pic BLOB
#         )
#     ''')
    
#     cursor.execute('''
#         CREATE TABLE IF NOT EXISTS Roles (
#             RoleID INTEGER PRIMARY KEY AUTOINCREMENT,
#             RoleName TEXT NOT NULL
#         )
#     ''')
    
#     cursor.execute('''
#         CREATE TABLE IF NOT EXISTS DEPARTMENTS (
#             DEPTID INTEGER PRIMARY KEY AUTOINCREMENT,
#             DEPTNAME TEXT NOT NULL,
#             SUPDEPTID INTEGER
#         )
#     ''')
    
#     # Insert default roles
#     roles = [
#         (1, 'Admin'),
#         (2, 'PoliceOfficer'), 
#         (3, 'Manager'),
#         (4, 'Viewer'),
#         (5, 'Employee')
#     ]
#     cursor.executemany("INSERT INTO Roles (RoleID, RoleName) VALUES (?, ?)", roles)
    
#     # Insert admin user with plain text password
#     cursor.execute(
#         "INSERT INTO Users (Username, PasswordHash, RoleID, Name) VALUES (?, ?, ?, ?)",
#         ('admin', 'admin123', 1, 'System Administrator')
#     )
    
#     # Insert test employee
#     cursor.execute('''
#         INSERT INTO USERINFO (NAME, GENDER, TITLE, employee_class) 
#         VALUES (?, ?, ?, ?)
#     ''', ('John Doe', 'Male', 'Developer', 'A'))
    
#     conn.commit()
#     conn.close()
#     print("Database reset successfully!")
#     print("Default login: admin / admin123")

# if __name__ == '__main__':
#     reset_database()