
import os

db_tables = [
    "ACGroup", "ACTimeZones", "ACUnlockComb", "AlarmLog", "AppLogs", "ArchiveReasons", "ArchiveWhys", 
    "AttendanceReviews", "AttendanceSummary", "AttParam", "AuditedExc", "AUTHDEVICE", "CandidateLogs", 
    "Candidates", "CHECKEXACT", "CHECKINOUT", "CycleDepartments", "DEPARTMENTS", "DeptUsedSchs", 
    "EmOpLog", "EmployeeArchive", "EmployeeClasses", "EmployeeExtendedInfo", "EmployeeFamilyMembers", 
    "EmployeeLeaveBalances", "EmployeeLeaveRequests", "EmployeeSchedules", "EvaluationCriteria", 
    "EvaluationCycles", "EvaluationDetails", "Evaluations", "EvaluationTypeCriteria", "EvaluationTypes", 
    "EXCNOTES", "FaceTemp", "HOLIDAYS", "Jobs", "LeaveClass", "LeaveClass1", "LeaveTypes", 
    "LMS_Courses", "LMS_Sessions", "LMS_SessionTrainers", "LMS_Trainers", "Machines", "NUM_RUN", 
    "NUM_RUN_DEIL", "Places", "POSITIONS", "Recommendations", "ReportItem", "ResignationReasons", 
    "Roles", "SchClass", "ScheduleTypes", "SECURITYDETAILS", "ServerLog", "SessionInstructors", 
    "SHIFT", "SystemLog", "TBKEY", "TBSMSALLOT", "TBSMSINFO", "TEMPLATE", "TerminationReasons", 
    "TerminationTypes", "TrainingAttendance", "TrainingCourses", "TrainingEnrollments", 
    "TrainingSession_Instructors", "TrainingSessionAttendance", "TrainingSessionDays", 
    "TrainingSessions", "USER_OF_RUN", "USER_SPEDAY", "USER_TEMP_SCH", "UserACMachines", 
    "UserACPrivilege", "USERINFO", "UserLogsHr", "UserPlaces", "Users", "UsersMachines", 
    "UserUpdates", "UserUsedSClasses"
]

project_path = os.getcwd()
used_tables = set()

ignore_dirs = {'.git', 'venv', '__pycache__', 'node_modules', '.idea', 'vscode', 'output', 'db'}
ignore_files = {'list_optima_tables.py', 'find_used_tables.py', 'evaluation_system.db'}

for root, dirs, files in os.walk(project_path):
    # Filter directories
    dirs[:] = [d for d in dirs if d not in ignore_dirs]
    
    for file in files:
        if file in ignore_files:
            continue
            
        if file.endswith('.py') or file.endswith('.html') or file.endswith('.sql'):
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    # Check for each table
                    for table in db_tables:
                        # Simple check: is the table name in the file content?
                        # We can improve this with regex for exact word match if needed,
                        # but usually table names are unique enough or used clearly.
                        # Using boundaries to avoid partial matches (e.g. 'Users' inside 'AllUsers')
                        import re
                        if re.search(r'\b' + re.escape(table) + r'\b', content, re.IGNORECASE):
                            used_tables.add(table)
            except Exception as e:
                print(f"Could not read {file}: {e}")

print("Tables used in the project:")
print("-" * 30)
for table in sorted(used_tables):
    print(table)
