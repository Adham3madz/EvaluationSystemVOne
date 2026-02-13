
import os
import pyodbc
import config
import re

# 1. Get all tables from the Database
try:
    conn = pyodbc.connect(config.CONNECTION_STRING)
    cursor = conn.cursor()
    
    query = """
    SELECT TABLE_NAME 
    FROM INFORMATION_SCHEMA.TABLES 
    WHERE TABLE_TYPE = 'BASE TABLE' 
    ORDER BY TABLE_NAME;
    """
    
    cursor.execute(query)
    all_tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    print(f"Total tables in DB: {len(all_tables)}")

except Exception as e:
    print(f"Error connecting to database: {e}")
    all_tables = []

# 2. Scan project for usage
project_path = os.getcwd()
used_tables = set()

# Directories to ignore
ignore_dirs = {'.git', 'venv', '__pycache__', 'node_modules', '.idea', 'vscode', 'output', 'db'}
# Files to ignore (scripts we just made)
ignore_files = {'list_optima_tables.py', 'find_used_tables.py', 'find_unused_tables.py', 'evaluation_system.db'}

print("Scanning project files...")

for root, dirs, files in os.walk(project_path):
    # Filter directories
    dirs[:] = [d for d in dirs if d not in ignore_dirs]
    
    for file in files:
        if file in ignore_files:
            continue
            
        # Check text-based files
        if file.endswith(('.py', '.html', '.sql', '.txt', '.md', '.js', '.css')):
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    for table in all_tables:
                        if table in used_tables:
                            continue # Already found
                        
                        # Regex for whole word match to avoid partials (e.g. 'User' matching 'UserInfo')
                        # Case insensitive
                        if re.search(r'\b' + re.escape(table) + r'\b', content, re.IGNORECASE):
                            used_tables.add(table)
            except Exception as e:
                # print(f"Could not read {file}: {e}")
                pass

# 3. Determine unused tables
unused_tables = sorted(list(set(all_tables) - used_tables))

print("\n" + "="*50)
print("Tables NOT found in your project code:")
print("="*50)
for table in unused_tables:
    print(table)

print("\n" + "="*50)
print(f"Total Unused: {len(unused_tables)}")
print("WARNING: Before deleting, ensure these are not used by:")
print("1. Other applications sharing the database (e.g. ZKTime software).")
print("2. Dynamic SQL queries constructed in a way this string search missed.")
print("3. Database procedures, views, or triggers.")
print("="*50)
