from flask import Flask, render_template, request, redirect, url_for, flash, session, json, send_file
from config import CONNECTION_STRING
import pyodbc
import datetime
from datetime import datetime  # تأكد إن الإمبورت موجود في أعلى الملف
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import timedelta, datetime
from collections import defaultdict
import io
pyodbc.pooling = True
from functools import wraps
import pandas as pd
from PIL import Image 
import os


app = Flask(__name__)
app.secret_key = "super-secret-key-2025"

UPLOAD_FOLDER = 'static/uploads/cvs'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True) # Create folder if not exists

# ========== DATABASE CONNECTION ==========

def get_db_connection():
    return pyodbc.connect(CONNECTION_STRING)

# ========== AUTH HELPERS ==========

def is_admin():
    return session.get('role_id') in [1, 2]  # Admin + Police Officer يشوفوا كل شيء

def is_manager():
    return session.get('role_id') == 3  # Manager RoleID = 3

def admin_or_manager_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if not (is_admin() or is_manager()):
            flash('Access denied. Admins or Managers only.', 'danger')
            return redirect(url_for('dashboard'))
        return fn(*args, **kwargs)
    return wrapper


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if not is_admin():
            flash('Access denied. Admins only.', 'danger')
            return redirect(url_for('dashboard'))
        return fn(*args, **kwargs)
    return wrapper

def training_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role_id') not in [1,5, 6]:
            flash('⚠️ غير مسموح لك بالدخول إلى نظام التدريب.', 'danger')
            return redirect(url_for('dashboard'))
        return fn(*args, **kwargs)
    return wrapper

def resize_logo(input_path, output_path, max_size=(250, 250)):
    try:
        with Image.open(input_path) as img:
            # Convert to RGBA if it's not (preserves transparency)
            img = img.convert("RGBA")
            
            # Calculate new size maintaining aspect ratio
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save as optimized PNG
            img.save(output_path, "PNG", optimize=True)
            
            original_size = os.path.getsize(input_path) / (1024 * 1024)
            new_size = os.path.getsize(output_path) / 1024
            
            print(f"✅ Success!")
            print(f"Original: {original_size:.2f} MB")
            print(f"New:      {new_size:.2f} KB")
            print(f"Saved to: {output_path}")
            
    except Exception as e:
        print(f"Error: {e}")

# Usage
resize_logo('Sugar RR.png', 'Sugar_RR_Optimized.png')

# ========== EVALUATION LOGIC ==========

def get_available_evaluation_types(conn, employee_id, manager_dept_id):
    """
    Checks an employee and returns a list of evaluation types 
    that are currently available or disabled for them.
    """
    try:
        cursor = conn.cursor()
        
        # --- FIX: استخدام الطريقة الصحيحة لجلب التاريخ الحالي ---
        # بما أنك تستخدم from datetime import datetime، يجب استخدام now().date()
        today = datetime.now().date()
        
        # 1. Get employee's completed evals
        cursor.execute("SELECT DISTINCT EvaluationTypeID FROM [Zktime_Copy].[dbo].[Evaluations] WHERE EmployeeUserID = ?", (employee_id,))
        completed_eval_ids = {row.EvaluationTypeID for row in cursor.fetchall()}
        
        # 2. Get all rules
        cursor.execute("SELECT * FROM [Zktime_Copy].[dbo].[EvaluationTypes] ORDER BY SortOrder")
        all_types_rules = cursor.fetchall()
        
        # 3. Get all active, open cycles
        cursor.execute("""
            SELECT C.EvaluationTypeID, CD.DepartmentID
            FROM [Zktime_Copy].[dbo].[EvaluationCycles] C
            LEFT JOIN [Zktime_Copy].[dbo].[CycleDepartments] CD ON C.CycleID = CD.CycleID
            WHERE C.IsEnabled = 1 AND ? BETWEEN C.StartDate AND C.EndDate
        """, (today,))
        active_cycles = cursor.fetchall()

        # Process into a simple lookup { type_id: [list of dept_ids] }
        open_cycle_depts = {} 
        for cycle in active_cycles:
            if cycle.EvaluationTypeID not in open_cycle_depts:
                open_cycle_depts[cycle.EvaluationTypeID] = []
            if cycle.DepartmentID:
                open_cycle_depts[cycle.EvaluationTypeID].append(cycle.DepartmentID)

        available_eval_list = []
        
        for rule in all_types_rules:
            eval_id = rule.EvaluationTypeID
            prereq_id = rule.PrerequisiteTypeID
            is_repeatable = rule.IsRepeatable
            
            # Check 1: Prerequisite
            prereq_met = (prereq_id is None) or (prereq_id in completed_eval_ids)
            
            # Check 2: Repeatability
            is_completed = eval_id in completed_eval_ids
            repeat_met = is_repeatable or (not is_completed)
            
            # Check 3: Cycle
            is_open = False
            if eval_id in open_cycle_depts:
                linked_depts = open_cycle_depts[eval_id]
                if not linked_depts: # Empty list means "all departments"
                    is_open = True
                elif manager_dept_id in linked_depts:
                    is_open = True
            else:
                # No cycle exists = open if other rules pass (sequential non-timed)
                is_open = True
                
            # Final decision
            if prereq_met and repeat_met and is_open:
                available_eval_list.append({
                    'id': eval_id, 'name': rule.DisplayName, 'disabled': False, 'note': '(متاح)'
                })
            else:
                note = ''
                if not prereq_met:
                    prereq_name = next((t.DisplayName for t in all_types_rules if t.EvaluationTypeID == prereq_id), '')
                    note = f'(متوقف على: {prereq_name})'
                elif not repeat_met: note = '(تم إكماله)'
                elif not is_open: note = '(خارج دورة التقييم)'
                    
                available_eval_list.append({
                    'id': eval_id, 'name': rule.DisplayName, 'disabled': True, 'note': note
                })
                
        return available_eval_list
    
    except Exception as e:
        # طباعة الخطأ في التيرمينال لمعرفة السبب إذا استمرت المشكلة
        print(f"❌ Error in get_available_evaluation_types: {e}")
        return []

def get_rating_from_score(score):
    if score is None: return 'N/A'
    if score >= 90: return 'ممتاز'
    elif score >= 80: return 'جيد جدا'
    elif score >= 70: return 'جيد'
    elif score >= 60: return 'مقبول'
    else: return 'ضعيف'

def get_employee_class(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT employee_class FROM [Zktime_Copy].[dbo].[USERINFO] WHERE USERID = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result.employee_class if result and result.employee_class else 'لم تضاف'

# ========== ROUTES ==========

@app.route('/', methods=['GET', 'POST'])
def login():
    # جديد: امسح أي session قديمة فورًا عشان نضمن إن كل زيارة جديدة تبدأ من الصفر
    session.clear()

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT UserID, Username, PasswordHash, RoleID, Name FROM [Zktime_Copy].[dbo].[Users] WHERE Username = ?", (username,))
            user = cursor.fetchone()
        except Exception as e:
            flash('❌ حدث خطأ في قاعدة البيانات.', 'danger')
            return render_template('login.html')
        finally:
            if conn: 
                conn.close()

        if user and password == getattr(user, 'PasswordHash', None):
            # أعد إنشاء الـ session من جديد بعد التحقق
            session['user_id'] = int(user.UserID)
            session['role_id'] = int(user.RoleID) if user.RoleID else None
            session['username'] = user.Username
            session['name'] = user.Name

            flash('✅ تم تسجيل الدخول بنجاح!', 'success')

            # توجيه حسب الدور (تم حذف Role 5 الخاص بالتوظيف)
            if user.RoleID == 6:
                return redirect(url_for('training_sessions'))
            else:
                return redirect(url_for('dashboard'))
        else:
            flash('❌ اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')

    # GET request أو لو ما فيش بوست → اعرض صفحة الـ login (بعد ما مسحنا الـ session)
    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    # 1. Initialize Context with Defaults
    ctx = {
        'user_id': session.get('user_id'),
        'username': session.get('username'),
        'name': session.get('name'),
        'role_id': session.get('role_id'),
        'is_admin': is_admin(),
        # Default values to prevent Jinja errors if DB fails
        'users_count': 0, 'employees_count': 0, 'evals_count': 0, 'avg_score': 0,
        'rating_distribution': [], 'eval_type_distribution': [], 
        'top_performers': [], 'recent_evaluations': [], 'score_ranges': [],
        'active_evaluators': [], 'inactive_managers': [],
        'chart_data': '{}'
    }

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # ==========================================
        # PART 1: PREPARE FILTERS
        # ==========================================
        # We build SQL snippets dynamically based on role
        if is_admin():
            # Admin Global Filters
            kpi_where = "1=1" 
            chart_where = "1=1"
            kpi_params = []
            chart_params = []
            
            # KPI Logic: Count All
            sql_kpis = """
                SELECT 
                    (SELECT COUNT(*) FROM [Zktime_Copy].[dbo].[Users]) as UsersCount,
                    (SELECT COUNT(*) FROM [Zktime_Copy].[dbo].[USERINFO] WHERE DEFAULTDEPTID <> -1) as EmpCount,
                    (SELECT COUNT(*) FROM [Zktime_Copy].[dbo].[Evaluations]) as EvalsCount,
                    (SELECT AVG(OverallScore) FROM [Zktime_Copy].[dbo].[Evaluations] WHERE OverallScore IS NOT NULL) as AvgScore
            """
        else:
            # Manager Department Filters
            # Get Manager's Dept ID first
            cursor.execute("SELECT DepartmentID FROM [Zktime_Copy].[dbo].[Users] WHERE UserID = ?", (ctx['user_id'],))
            user_row = cursor.fetchone()
            dept_id = user_row.DepartmentID if user_row else None
            
            if not dept_id:
                # If manager has no dept, show 0s
                return render_template('dashboard.html', **ctx)

            kpi_where = "DepartmentID = ?"
            chart_where = "UI.DEFAULTDEPTID = ?"
            # We need to pass the parameter multiple times for the subqueries
            kpi_params = [dept_id, dept_id, dept_id, dept_id]
            chart_params = [] # We will fill this when building the chart query

            sql_kpis = """
                SELECT 
                    (SELECT COUNT(*) FROM [Zktime_Copy].[dbo].[Users] WHERE DepartmentID = ?) as UsersCount,
                    (SELECT COUNT(*) FROM [Zktime_Copy].[dbo].[USERINFO] WHERE DEFAULTDEPTID = ?) as EmpCount,
                    (SELECT COUNT(*) FROM [Zktime_Copy].[dbo].[Evaluations] E JOIN [Zktime_Copy].[dbo].[USERINFO] UI ON E.EmployeeUserID = UI.USERID WHERE UI.DEFAULTDEPTID = ?) as EvalsCount,
                    (SELECT AVG(E.OverallScore) FROM [Zktime_Copy].[dbo].[Evaluations] E JOIN [Zktime_Copy].[dbo].[USERINFO] UI ON E.EmployeeUserID = UI.USERID WHERE UI.DEFAULTDEPTID = ? AND E.OverallScore IS NOT NULL) as AvgScore
            """

        # ==========================================
        # PART 2: EXECUTE KPIs (Trip #1)
        # ==========================================
        cursor.execute(sql_kpis, kpi_params)
        kpi_row = cursor.fetchone()
        if kpi_row:
            ctx['users_count'] = kpi_row.UsersCount
            ctx['employees_count'] = kpi_row.EmpCount
            ctx['evals_count'] = kpi_row.EvalsCount
            ctx['avg_score'] = kpi_row.AvgScore if kpi_row.AvgScore else 0

        # ==========================================
        # PART 3: EXECUTE CHARTS & LISTS (Trip #2)
        # ==========================================
        # We concatenate 5 queries into one string separated by ';'
        # Note: We must ensure the params list matches the order of '?' in the string
        
        base_joins = """
            FROM [Zktime_Copy].[dbo].[Evaluations] E
            LEFT JOIN [Zktime_Copy].[dbo].[USERINFO] UI ON E.EmployeeUserID = UI.USERID
            LEFT JOIN [Zktime_Copy].[dbo].[Users] U ON E.EmployeeUserID = U.UserID
            LEFT JOIN [Zktime_Copy].[dbo].[Users] Mgr ON E.EvaluatorUserID = Mgr.UserID
            LEFT JOIN [Zktime_Copy].[dbo].[EvaluationTypes] ET ON E.EvaluationTypeID = ET.EvaluationTypeID
        """

        sql_charts = f"""
        -- 1. Rating Distribution
        SELECT OverallRating, COUNT(*) as count 
        FROM [Zktime_Copy].[dbo].[Evaluations] E 
        LEFT JOIN [Zktime_Copy].[dbo].[USERINFO] UI ON E.EmployeeUserID = UI.USERID 
        WHERE {chart_where} AND OverallRating IS NOT NULL 
        GROUP BY OverallRating;

        -- 2. Type Distribution
        SELECT COALESCE(ET.DisplayName, E.EvaluationType, 'غير محدد'), COUNT(*) as count 
        FROM [Zktime_Copy].[dbo].[Evaluations] E 
        LEFT JOIN [Zktime_Copy].[dbo].[USERINFO] UI ON E.EmployeeUserID = UI.USERID 
        LEFT JOIN [Zktime_Copy].[dbo].[EvaluationTypes] ET ON E.EvaluationTypeID = ET.EvaluationTypeID 
        WHERE {chart_where} 
        GROUP BY COALESCE(ET.DisplayName, E.EvaluationType, 'غير محدد') ORDER BY count DESC;

        -- 3. Top Performers (ADDED ALIAS BELOW)
        SELECT TOP 5 
            COALESCE(UI.NAME, U.Name, U.Username) AS EmployeeName, 
            E.OverallScore, 
            E.OverallRating, 
            E.EvaluationDate 
        {base_joins} 
        WHERE {chart_where} AND E.EvaluationDate >= DATEADD(day, -30, GETDATE()) 
        ORDER BY E.OverallScore DESC;

        -- 4. Recent Evaluations (ADDED ALIASES BELOW)
        SELECT TOP 10 
            E.EvaluationID, 
            COALESCE(UI.NAME, U.Name, U.Username) AS EmployeeName, 
            COALESCE(Mgr.Name, Mgr.Username) AS EvaluatorName, 
            E.OverallScore, 
            E.OverallRating, 
            COALESCE(ET.DisplayName, E.EvaluationType) AS EvaluationType, 
            E.EvaluationDate 
        {base_joins} 
        WHERE {chart_where} 
        ORDER BY E.EvaluationDate DESC;

        -- 5. Score Ranges
        SELECT CASE WHEN OverallScore >= 90 THEN 'ممتاز (90-100)' WHEN OverallScore >= 80 THEN 'جيد جدا (80-89)'
               WHEN OverallScore >= 70 THEN 'جيد (70-79)' WHEN OverallScore >= 60 THEN 'مقبول (60-69)' ELSE 'ضعيف (أقل من 60)' END as score_range,
               COUNT(*) as count
        FROM [Zktime_Copy].[dbo].[Evaluations] E 
        LEFT JOIN [Zktime_Copy].[dbo].[USERINFO] UI ON E.EmployeeUserID = UI.USERID
        WHERE {chart_where} AND OverallScore IS NOT NULL
        GROUP BY CASE WHEN OverallScore >= 90 THEN 'ممتاز (90-100)' WHEN OverallScore >= 80 THEN 'جيد جدا (80-89)'
                 WHEN OverallScore >= 70 THEN 'جيد (70-79)' WHEN OverallScore >= 60 THEN 'مقبول (60-69)' ELSE 'ضعيف (أقل من 60)' END
        ORDER BY MIN(OverallScore) DESC;
        """

        # Prepare params: We have 5 queries. If admin, params is empty. 
        # If manager, each query needs 'dept_id'. So we repeat dept_id 5 times.
        if is_admin():
            chart_params = []
        else:
            chart_params = [dept_id] * 5

        # Execute Batch
        cursor.execute(sql_charts, chart_params)

        # Fetch Results Sequentially using nextset()
        ctx['rating_distribution'] = cursor.fetchall()
        
        if cursor.nextset(): ctx['eval_type_distribution'] = cursor.fetchall()
        if cursor.nextset(): ctx['top_performers'] = cursor.fetchall()
        if cursor.nextset(): ctx['recent_evaluations'] = cursor.fetchall()
        if cursor.nextset(): ctx['score_ranges'] = cursor.fetchall()

        # ==========================================
        # PART 4: ADMIN ONLY EXTRAS (Trip #3 - Optional)
        # ==========================================
        if is_admin():
            sql_admin = """
            -- Inactive Managers
            SELECT U.UserID, U.Name, D.DEPTNAME,
                (SELECT COUNT(*) FROM [Zktime_Copy].[dbo].[USERINFO] WHERE DEFAULTDEPTID = U.DepartmentID AND IsActive = 1) as TotalEmployees
            FROM [Zktime_Copy].[dbo].[Users] U
            LEFT JOIN [Zktime_Copy].[dbo].[DEPARTMENTS] D ON U.DepartmentID = D.DEPTID
            WHERE U.RoleID = 3 AND U.UserID NOT IN (SELECT DISTINCT EvaluatorUserID FROM [Zktime_Copy].[dbo].[Evaluations] WHERE EvaluatorUserID IS NOT NULL)
            ORDER BY U.Name;

            -- Active Evaluators (ADDED ALIAS BELOW)
            SELECT TOP 5 
                COALESCE(Mgr.Name, Mgr.Username) AS EvaluatorName, 
                COUNT(E.EvaluationID) as evaluation_count, 
                COUNT(DISTINCT E.EmployeeUserID) as distinct_evaluated,
                (SELECT COUNT(*) FROM [Zktime_Copy].[dbo].[USERINFO] WHERE DEFAULTDEPTID = Mgr.DepartmentID AND IsActive = 1) as total_dept_employees
            FROM [Zktime_Copy].[dbo].[Evaluations] E
            LEFT JOIN [Zktime_Copy].[dbo].[Users] Mgr ON E.EvaluatorUserID = Mgr.UserID
            GROUP BY Mgr.UserID, Mgr.Name, Mgr.Username, Mgr.DepartmentID
            HAVING COALESCE(Mgr.Name, Mgr.Username) IS NOT NULL ORDER BY COUNT(E.EvaluationID) DESC;
            """

            cursor.execute(sql_admin)
            ctx['inactive_managers'] = cursor.fetchall()
            if cursor.nextset(): ctx['active_evaluators'] = cursor.fetchall()

        # ==========================================
        # PART 5: TURNOVER STATS (Trip #4)
        # ==========================================
        # Combining 4 Turnover queries into 1 batch
        sql_turnover = """
        -- 1. Hires
        SELECT YEAR(HiredDay) as Yr, COUNT(*) as Count 
        FROM (
            SELECT HiredDay FROM [Zktime_Copy].[dbo].[USERINFO] WHERE HiredDay IS NOT NULL AND DEFAULTDEPTID <> -1
            UNION ALL 
            SELECT HiredDay FROM [Zktime_Copy].[dbo].[EmployeeArchive] WHERE HiredDay IS NOT NULL
        ) as AllHires 
        WHERE YEAR(HiredDay) > 1900 GROUP BY YEAR(HiredDay) ORDER BY Yr;

        -- 2. Leavers
        SELECT YEAR(EndDay) as Yr, COUNT(*) as Count FROM [Zktime_Copy].[dbo].[EmployeeArchive] 
        WHERE EndDay IS NOT NULL AND YEAR(EndDay) > 1900 GROUP BY YEAR(EndDay) ORDER BY Yr;

        -- 3. Dept Turnover
        SELECT D.DEPTNAME, COUNT(*) as Count FROM [Zktime_Copy].[dbo].[EmployeeArchive] A 
        LEFT JOIN [Zktime_Copy].[dbo].[DEPARTMENTS] D ON A.ArchivedDeptID = D.DEPTID 
        GROUP BY D.DEPTNAME ORDER BY Count DESC;

        -- 4. Pos Turnover
        SELECT P.PositionName, COUNT(*) as Count FROM [Zktime_Copy].[dbo].[EmployeeArchive] A 
        LEFT JOIN [Zktime_Copy].[dbo].[POSITIONS] P ON A.ArchivedPosID = P.PositionID 
        GROUP BY P.PositionName ORDER BY Count DESC;
        """
        
        cursor.execute(sql_turnover)
        hires_rows = cursor.fetchall()
        
        left_rows = []
        if cursor.nextset(): left_rows = cursor.fetchall()
        
        dept_turnover = []
        if cursor.nextset(): dept_turnover = cursor.fetchall()
        
        pos_turnover = []
        if cursor.nextset(): pos_turnover = cursor.fetchall()

        # --- Data Processing for Turnover Charts (Python Logic) ---
        all_years = sorted(list(set([r.Yr for r in hires_rows] + [r.Yr for r in left_rows])))
        hires_map = {r.Yr: r.Count for r in hires_rows}
        left_map = {r.Yr: r.Count for r in left_rows}
        
        hires_data = [hires_map.get(y, 0) for y in all_years]
        left_data = [left_map.get(y, 0) for y in all_years]
        net_data = [h - l for h, l in zip(hires_data, left_data)]

        # --- Prepare JSON Data ---
        chart_data = {
            'rating_labels': [str(row.OverallRating) for row in ctx['rating_distribution']],
            'rating_data': [int(row.count) for row in ctx['rating_distribution']],
            'type_labels': [str(row[0]) for row in ctx['eval_type_distribution']], # row[0] is the Type Name
            'type_data': [int(row.count) for row in ctx['eval_type_distribution']],
            'score_range_labels': [str(row.score_range) for row in ctx['score_ranges']],
            'score_range_data': [int(row.count) for row in ctx['score_ranges']],
            'turnover_years': all_years, 
            'hires_data': hires_data, 
            'left_data': left_data, 
            'net_data': net_data,
            'dept_turnover_labels': [row.DEPTNAME or 'غير محدد' for row in dept_turnover],
            'dept_turnover_data': [row.Count for row in dept_turnover],
            'pos_turnover_labels': [row.PositionName or 'غير محدد' for row in pos_turnover],
            'pos_turnover_data': [row.Count for row in pos_turnover],
        }
        ctx['chart_data'] = json.dumps(chart_data, ensure_ascii=False)

    except Exception as e:
        print(f"Dashboard Error: {e}")
        # In production, you might want to log this to a file
    finally:
        if conn: conn.close()
    
    return render_template('dashboard.html', **ctx)




@app.route('/users')
@login_required
def users():
    search = request.args.get('search', '').strip()
    role_id_filter = request.args.get('role_id', '')
    dept_id_filter = request.args.get('dept_id', '')
    conn = get_db_connection()
    cursor = conn.cursor()
    query_base = "SELECT U.UserID, U.Username, COALESCE(U.Name, UI.NAME) AS FullName, U.DepartmentID, D.DEPTNAME, U.RoleID, R.RoleName FROM [Zktime_Copy].[dbo].[Users] U LEFT JOIN [Zktime_Copy].[dbo].[USERINFO] UI ON U.UserID = UI.USERID LEFT JOIN [Zktime_Copy].[dbo].[DEPARTMENTS] D ON U.DepartmentID = D.DEPTID LEFT JOIN [Zktime_Copy].[dbo].[Roles] R ON U.RoleID = R.RoleID"
    where_clauses = ["1=1"] 
    params = []
    if search:
        where_clauses.append("(U.Username LIKE ? OR COALESCE(U.Name, UI.NAME) LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if role_id_filter:
        where_clauses.append("U.RoleID = ?")
        params.append(role_id_filter)
    if dept_id_filter:
        where_clauses.append("U.DepartmentID = ?")
        params.append(dept_id_filter)
    query = f"{query_base} WHERE {' AND '.join(where_clauses)} ORDER BY U.UserID"
    cursor.execute(query, params)
    users = cursor.fetchall()
    cursor.execute("SELECT RoleID, RoleName FROM [Zktime_Copy].[dbo].[Roles] ORDER BY RoleID")
    roles = cursor.fetchall()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime_Copy].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    depts = cursor.fetchall()
    conn.close()
    return render_template('users.html', users=users, roles=roles, depts=depts, filters=request.args, is_admin=is_admin())

@app.route('/users/add', methods=['GET', 'POST'])
@admin_required
def add_user():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT RoleID, RoleName FROM [Zktime_Copy].[dbo].[Roles] ORDER BY RoleID")
    roles = cursor.fetchall()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime_Copy].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    depts = cursor.fetchall()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'] 
        name = request.form.get('name') or None
        role_id = request.form.get('role_id') or None
        dept_id = request.form.get('department_id') or None
        try:
            cursor.execute("INSERT INTO [Zktime_Copy].[dbo].[Users] (Username, PasswordHash, RoleID, Name, DepartmentID) VALUES (?, ?, ?, ?, ?)", (username, password, role_id, name, dept_id))
            conn.commit()
            flash('✅ User added successfully!', 'success')
            return redirect(url_for('users'))
        except Exception as e:
            flash(f'❌ Error: {e}', 'danger')
        finally:
            conn.close()
    return render_template('user_form.html', roles=roles, depts=depts, action='Add')

@app.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT RoleID, RoleName FROM [Zktime_Copy].[dbo].[Roles] ORDER BY RoleID")
    roles = cursor.fetchall()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime_Copy].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    depts = cursor.fetchall()
    cursor.execute("SELECT UserID, Username, RoleID, Name, DepartmentID FROM [Zktime_Copy].[dbo].[Users] WHERE UserID = ?", (user_id,))
    user = cursor.fetchone()
    if request.method == 'POST':
        username = request.form['username']
        name = request.form.get('name') or None
        role_id = request.form.get('role_id') or None
        dept_id = request.form.get('department_id') or None
        new_password = request.form.get('password') or None
        if new_password:
            cursor.execute("UPDATE [Zktime_Copy].[dbo].[Users] SET Username = ?, Name = ?, RoleID = ?, DepartmentID = ?, PasswordHash = ? WHERE UserID = ?", (username, name, role_id, dept_id, new_password, user_id))
        else:
            cursor.execute("UPDATE [Zktime_Copy].[dbo].[Users] SET Username = ?, Name = ?, RoleID = ?, DepartmentID = ? WHERE UserID = ?", (username, name, role_id, dept_id, user_id))
        conn.commit()
        conn.close()
        flash('User updated successfully!', 'success')
        return redirect(url_for('users'))
    conn.close()
    return render_template('user_form.html', user=user, roles=roles, depts=depts, action='Edit')

@app.route('/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM [Zktime_Copy].[dbo].[Users] WHERE UserID = ?", (user_id,))
    conn.commit()
    conn.close()
    flash('User deleted successfully!', 'info')
    return redirect(url_for('users'))



@app.route('/userinfo')
@login_required 
def userinfo_list():
    # 1. Collect Filters
    search = request.args.get('search', '').strip()
    employee_class_filter = request.args.get('employee_class', '')
    gender = request.args.get('gender', '')
    department = request.args.get('department', '')
    title = request.args.get('title', '').strip() # Added Title filter capture
    sort = request.args.get('sort', 'USERID')
    order = request.args.get('order', 'asc')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    user_id = session.get('user_id')
    role_id = session.get('role_id')
    
    # 2. Security & Global Filters (Same logic as before)
    where_clauses = ["UI.DEFAULTDEPTID <> -1"] 
    params = []
    
    if is_admin():
        where_clauses.append("1=1")
    elif role_id == 3:
        # Manager Hierarchy Logic
        cursor.execute("SELECT DepartmentID FROM [Zktime_Copy].[dbo].[Users] WHERE UserID = ?", (user_id,))
        user_row = cursor.fetchone()
        dept_id = user_row.DepartmentID if user_row and user_row.DepartmentID else None
        
        if dept_id and dept_id != -1:
            hierarchy_query = """
                WITH DeptHierarchy AS (
                    SELECT DEPTID FROM [Zktime_Copy].[dbo].[DEPARTMENTS] WHERE DEPTID = ?
                    UNION ALL
                    SELECT d.DEPTID FROM [Zktime_Copy].[dbo].[DEPARTMENTS] d
                    INNER JOIN DeptHierarchy dh ON d.SUPDEPTID = dh.DEPTID
                )
                SELECT DEPTID FROM DeptHierarchy
            """
            cursor.execute(hierarchy_query, (dept_id,))
            dept_ids_rows = cursor.fetchall()
            target_dept_ids = [row[0] for row in dept_ids_rows]
            
            if target_dept_ids:
                placeholders = ','.join(['?'] * len(target_dept_ids))
                where_clauses.append(f"UI.DEFAULTDEPTID IN ({placeholders})")
                params.extend(target_dept_ids)
            else:
                where_clauses.append("UI.DEFAULTDEPTID = ?")
                params.append(dept_id)
        else:
            where_clauses.append("1=0") 

    # 3. Apply Filters
    if search:
        where_clauses.append("(UI.NAME LIKE ? OR UI.BADGENUMBER LIKE ? OR UI.SSN LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    if employee_class_filter:
        where_clauses.append("UI.employee_class LIKE ?")
        params.append(f"%{employee_class_filter}%")
    if gender:
        where_clauses.append("UI.GENDER = ?")
        params.append(gender)
    if is_admin():
        if department:
            where_clauses.append("UI.DEFAULTDEPTID = ?")
            params.append(department)
        if title:
            where_clauses.append("UI.TITLE LIKE ?")
            params.append(f"%{title}%")

    # Construct the WHERE string
    where_sql = ' AND '.join(where_clauses)

    # 4. === OPTIMIZATION: Calculate Analytics in SQL ===
    # We run specific GROUP BY queries using the EXACT SAME filters
    
    analytics = {'total': 0, 'males': 0, 'females': 0, 'classes': {}, 'depts': {}}

    # A. Total & Gender
    stats_query = f"""
        SELECT UI.GENDER, COUNT(*) 
        FROM [Zktime_Copy].[dbo].[USERINFO] UI
        LEFT JOIN DEPARTMENTS D ON UI.DEFAULTDEPTID = D.DEPTID
        WHERE {where_sql}
        GROUP BY UI.GENDER
    """
    cursor.execute(stats_query, params)
    for row in cursor.fetchall():
        count = row[1]
        analytics['total'] += count
        if row[0] == 'M': analytics['males'] = count
        elif row[0] == 'F': analytics['females'] = count

    # B. Class Distribution
    # Note: SQL handles the splitting of comma-separated values poorly, 
    # so we group by the raw string and process simple cases here.
    class_query = f"""
        SELECT UI.employee_class, COUNT(*) 
        FROM [Zktime_Copy].[dbo].[USERINFO] UI
        LEFT JOIN DEPARTMENTS D ON UI.DEFAULTDEPTID = D.DEPTID
        WHERE {where_sql}
        GROUP BY UI.employee_class
    """
    cursor.execute(class_query, params)
    for row in cursor.fetchall():
        cls_str = row[0] or "غير محدد"
        count = row[1]
        # Simple logic: just take the whole string as a key for chart
        analytics['classes'][cls_str] = analytics['classes'].get(cls_str, 0) + count

    # C. Top Departments
    dept_query = f"""
        SELECT TOP 5 D.DEPTNAME, COUNT(*) as cnt
        FROM [Zktime_Copy].[dbo].[USERINFO] UI
        LEFT JOIN DEPARTMENTS D ON UI.DEFAULTDEPTID = D.DEPTID
        WHERE {where_sql}
        GROUP BY D.DEPTNAME
        ORDER BY cnt DESC
    """
    cursor.execute(dept_query, params)
    for row in cursor.fetchall():
        dname = row[0] or "غير محدد"
        analytics['depts'][dname] = row[1]

    # 5. Fetch Table Data (Limit to 500 for speed if needed, or paginate)
    sort_field = {
        'USERID': 'UI.USERID', 'NAME': 'UI.NAME', 'HIREDDAY': 'UI.HIREDDAY'
    }.get(sort, 'UI.USERID')
    order_sql = 'ASC' if order.lower() == 'asc' else 'DESC'

    full_query = f"""
        SELECT UI.USERID, UI.BADGENUMBER, UI.SSN, UI.NAME, UI.GENDER, UI.TITLE, UI.HIREDDAY,
               UI.DEFAULTDEPTID, UI.employee_class, D.DEPTNAME
        FROM [Zktime_Copy].[dbo].[USERINFO] AS UI
        LEFT JOIN DEPARTMENTS D ON UI.DEFAULTDEPTID = D.DEPTID
        WHERE {where_sql}
        ORDER BY {sort_field} {order_sql}
    """
    
    cursor.execute(full_query, params)
    rows = cursor.fetchall()
    
    # 6. Fetch Dropdowns
    cursor.execute("SELECT DEPTID, DEPTNAME FROM DEPARTMENTS ORDER BY DEPTID")
    all_departments = cursor.fetchall()
    
    conn.close()
    
    return render_template('userinfo.html', 
                           users=rows, 
                           analytics=analytics,  # <--- Pass the calculated stats here
                           is_admin=is_admin(), 
                           role_id=role_id, 
                           departments=all_departments)

@app.route('/userinfo/add', methods=['GET', 'POST'])
@admin_required
def userinfo_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime_Copy].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    depts = cursor.fetchall()
    cursor.execute("SELECT PositionID, PositionName, DeptID FROM [Zktime_Copy].[dbo].[POSITIONS] ORDER BY PositionName")
    positions_rows = cursor.fetchall()
    positions_list = [{'PositionID': p.PositionID, 'PositionName': p.PositionName, 'DeptID': p.DeptID} for p in positions_rows]
    if request.method == 'POST':
        badge = request.form.get('badgenumber') or None
        ssn = request.form.get('ssn') or None
        name = request.form.get('name') or None
        gender = request.form.get('gender') or None
        title = request.form.get('title') or None
        defaultdept = request.form.get('defaultdept') or None
        positionid = request.form.get('positionid') or None
        levels_list = request.form.getlist('employee_levels')
        employee_class = ",".join(levels_list) if levels_list else 'لم تضاف'
        cursor.execute("""
    INSERT INTO [Zktime_Copy].[dbo].[USERINFO] 
    (BADGENUMBER, SSN, NAME, GENDER, TITLE, DEFAULTDEPTID, employee_class)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (badge, ssn, name, gender, title, defaultdept, employee_class))
        conn.commit()
        conn.close()
        flash('Employee added successfully!', 'success')
        return redirect(url_for('userinfo_list'))
    conn.close()
    return render_template('userinfo_form.html', depts=depts, positions=positions_list, action='Add')

@app.route('/userinfo/edit/<int:uid>', methods=['GET', 'POST'])
@admin_required
def userinfo_edit(uid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime_Copy].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    depts = cursor.fetchall()
    cursor.execute("SELECT PositionID, PositionName, DeptID FROM [Zktime_Copy].[dbo].[POSITIONS] ORDER BY PositionName")
    positions_rows = cursor.fetchall()
    positions_list = [{'PositionID': p.PositionID, 'PositionName': p.PositionName, 'DeptID': p.DeptID} for p in positions_rows]
    cursor.execute("SELECT USERID, BADGENUMBER, SSN, NAME, GENDER, TITLE, DEFAULTDEPTID, PositionID, employee_class FROM [Zktime_Copy].[dbo].[USERINFO] WHERE USERID = ?", (uid,))
    user = cursor.fetchone()
    if request.method == 'POST':
        badge = request.form.get('badgenumber') or None
        ssn = request.form.get('ssn') or None
        name = request.form.get('name') or None
        gender = request.form.get('gender') or None
        title = request.form.get('title') or None
        defaultdept = request.form.get('defaultdept') or None
        positionid = request.form.get('positionid') or None
        levels_list = request.form.getlist('employee_levels')
        employee_class = ",".join(levels_list) if levels_list else 'لم تضاف'
        cursor.execute("""
    UPDATE [Zktime_Copy].[dbo].[USERINFO] SET 
    BADGENUMBER = ?, SSN = ?, NAME = ?, GENDER = ?, TITLE = ?, DEFAULTDEPTID = ?, employee_class = ?
    WHERE USERID = ?
    """, (badge, ssn, name, gender, title, defaultdept, employee_class, uid))
        conn.commit()
        conn.close()
        flash('Employee updated successfully!', 'success')
        return redirect(url_for('userinfo_list'))
    conn.close()
    return render_template('userinfo_form.html', user=user, depts=depts, positions=positions_list, action='Edit')

@app.route('/userinfo/view/<int:uid>')
@login_required
def userinfo_view(uid):
    conn = get_db_connection()
    cursor = conn.cursor()
    avg_stats = None
    history = []
    training_history = []

    try:
        # Query 1: Get User Info - استخدم TITLE بدل PositionName
        cursor.execute("""
            SELECT UI.*, 
                   D.DEPTNAME, 
                   UI.TITLE AS PositionName,
                   (SELECT COUNT(*) FROM TrainingEnrollments TE 
                    WHERE TE.EmployeeUserID = UI.USERID 
                    AND (TE.PassStatus IS NULL OR TE.PassStatus NOT IN ('Excuse', 'Canceled'))) AS TotalSessions
            FROM [Zktime_Copy].[dbo].[USERINFO] UI 
            LEFT JOIN [Zktime_Copy].[dbo].[DEPARTMENTS] D ON UI.DEFAULTDEPTID = D.DEPTID 
            WHERE UI.USERID = ?
        """, (uid,))
        user = cursor.fetchone()

        if not user:
            flash('❌ لم يتم العثور على بيانات الموظف.', 'danger')
            return redirect(url_for('userinfo_list'))

        # باقي الكود زي ما هو (مش محتاج تغيير)
        cursor.execute("""
            SELECT AVG(OverallScore) as avg_score, COUNT(*) as eval_count 
            FROM [Zktime_Copy].[dbo].[Evaluations] WHERE EmployeeUserID = ?
        """, (uid,))
        avg_stats = cursor.fetchone()

        cursor.execute("""
            SELECT TE.Grade, TE.PassStatus, TE.EnrollmentDate, 
                   TC.TrainingCourseText, 
                   TS.SessionDate, TS.IsExternal, TS.ExternalTrainerName, TS.ExternalCompany, 
                   TS.InstructorID
            FROM TrainingEnrollments TE
            JOIN TrainingSessions TS ON TE.SessionID = TS.SessionID
            JOIN TrainingCourses TC ON TS.CourseID = TC.TrainingCourseID
            WHERE TE.EmployeeUserID = ?
            AND (TE.PassStatus IS NULL OR TE.PassStatus NOT IN ('Excuse', 'Canceled'))
            ORDER BY TS.SessionDate DESC
        """, (uid,))
        training_history_raw = cursor.fetchall()

        if not training_history_raw:
            training_history = []
        else:
            # جمع InstructorIDs
            all_instructor_ids = set()
            for row in training_history_raw:
                # row[5] = IsExternal, row[8] = InstructorID (حسب ترتيب الـ SELECT)
                if row[5] == 0 and row[8]:  # IsExternal = 0 (False) وفي InstructorID
                    try:
                        ids = [int(x.strip()) for x in str(row[8]).split(',') if x.strip().isdigit()]
                        all_instructor_ids.update(ids)
                    except:
                        pass

            # جلب أسماء المدربين
            instructor_map = {}
            if all_instructor_ids:
                placeholders = ','.join(['?'] * len(all_instructor_ids))
                cursor.execute(f"SELECT USERID, Name FROM Users WHERE USERID IN ({placeholders})", list(all_instructor_ids))
                instructor_map = {r.USERID: r.Name for r in cursor.fetchall()}

            # بناء training_history بالـ index (آمن 100%)
            training_history = []
            for row in training_history_raw:
                # ترتيب الـ columns حسب الـ SELECT:
                # 0: Grade, 1: PassStatus, 2: EnrollmentDate, 3: TrainingCourseText
                # 4: SessionDate, 5: IsExternal, 6: ExternalTrainerName, 7: ExternalCompany, 8: InstructorID
                training_row = {
                    'Grade': row[0],
                    'PassStatus': row[1],
                    'EnrollmentDate': row[2],
                    'TrainingCourseText': row[3],
                    'SessionDate': row[4],
                    'IsExternal': row[5],
                    'ExternalTrainerName': row[6],
                    'ExternalCompany': row[7],
                    'InstructorID': row[8],
                    'IntTrainer': ''
                }

                # معالجة المدربين الداخليين
                if training_row['IsExternal'] == 0 and training_row['InstructorID']:
                    try:
                        ids = [int(x.strip()) for x in str(training_row['InstructorID']).split(',') if x.strip().isdigit()]
                        names = [instructor_map.get(id, 'غير معروف') for id in ids]
                        training_row['IntTrainer'] = ', '.join(names) if names else 'غير معروف'
                    except:
                        training_row['IntTrainer'] = 'خطأ في قراءة المدربين'

                training_history.append(training_row)

    except Exception as e:
        flash(f"Error fetching employee details: {e}", "danger")
        print(f"Error in userinfo_view: {e}")
    finally:
        if conn:
            conn.close()

    # أضف السطر ده هنا (خارج الـ try)
    current_date = datetime.now().strftime('%d/%m/%Y')

    return render_template('employee_profile.html',
                           user=user if 'user' in locals() else None,
                           is_admin=is_admin(),
                           avg_stats=avg_stats if 'avg_stats' in locals() else None,
                           history=history if 'history' in locals() else [],
                           training_history=training_history if 'training_history' in locals() else [],
                           current_date=current_date)




@app.route('/roles')
@login_required
def roles():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT RoleID, RoleName FROM [Zktime_Copy].[dbo].[Roles] ORDER BY RoleID")
    rows = cursor.fetchall()
    conn.close()
    return render_template('roles.html', roles=rows)

@app.route('/roles/add', methods=['GET', 'POST'])
@admin_required
def roles_add():
    if request.method == 'POST':
        name = request.form['rolename']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO [Zktime_Copy].[dbo].[Roles] (RoleName) VALUES (?)", (name,))
        conn.commit()
        conn.close()
        flash('Role added successfully!', 'success')
        return redirect(url_for('roles'))
    return render_template('role_form.html', action='Add')

@app.route('/roles/edit/<int:rid>', methods=['GET', 'POST'])
@admin_required
def roles_edit(rid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT RoleID, RoleName FROM [Zktime_Copy].[dbo].[Roles] WHERE RoleID = ?", (rid,))
    role = cursor.fetchone()
    if request.method == 'POST':
        name = request.form['rolename']
        cursor.execute("UPDATE [Zktime_Copy].[dbo].[Roles] SET RoleName = ? WHERE RoleID = ?", (name, rid))
        conn.commit()
        conn.close()
        flash('Role updated successfully!', 'success')
        return redirect(url_for('roles'))
    conn.close()
    return render_template('role_form.html', role=role, action='Edit')

@app.route('/roles/delete/<int:rid>', methods=['POST'])
@admin_required
def roles_delete(rid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM [Zktime_Copy].[dbo].[Roles] WHERE RoleID = ?", (rid,))
    conn.commit()
    conn.close()
    flash('Role deleted successfully!', 'info')
    return redirect(url_for('roles'))

@app.route('/departments/manage')
@login_required
def departments_manage():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME, SUPDEPTID FROM [Zktime_Copy].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    rows = cursor.fetchall()
    conn.close()
    return render_template('departments.html', departments=rows)

@app.route('/departments/add', methods=['GET', 'POST'])
@admin_required
def departments_add():
    if request.method == 'POST':
        name = request.form['deptname']
        sup = request.form.get('supdeptid') or None
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # 1. Calculate the next available DEPTID
            cursor.execute("SELECT MAX(DEPTID) FROM [Zktime_Copy].[dbo].[DEPARTMENTS]")
            row = cursor.fetchone()
            # If table is empty, start at 1, otherwise add 1 to the max ID
            new_dept_id = (row[0] or 0) + 1
            
            # 2. Insert with the manually generated DEPTID
            cursor.execute("""
                INSERT INTO [Zktime_Copy].[dbo].[DEPARTMENTS] (DEPTID, DEPTNAME, SUPDEPTID) 
                VALUES (?, ?, ?)
            """, (new_dept_id, name, sup))
            
            conn.commit()
            flash('Department added successfully!', 'success')
            return redirect(url_for('departments_manage'))
            
        except Exception as e:
            conn.rollback()
            flash(f'Error adding department: {e}', 'danger')
            # It's helpful to print the error to console for debugging
            print(f"Database Error: {e}") 
            return redirect(url_for('departments_add'))
            
        finally:
            conn.close()

    return render_template('department_form.html', action='Add')

@app.route('/departments/edit/<int:did>', methods=['GET', 'POST'])
@admin_required
def departments_edit(did):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME, SUPDEPTID FROM [Zktime_Copy].[dbo].[DEPARTMENTS] WHERE DEPTID = ?", (did,))
    dept = cursor.fetchone()
    if request.method == 'POST':
        name = request.form['deptname']
        sup = request.form.get('supdeptid') or None
        cursor.execute("UPDATE [Zktime_Copy].[dbo].[DEPARTMENTS] SET DEPTNAME = ?, SUPDEPTID = ? WHERE DEPTID = ?", (name, sup, did))
        conn.commit()
        conn.close()
        flash('Department updated successfully!', 'success')
        return redirect(url_for('departments_manage'))
    conn.close()
    return render_template('department_form.html', dept=dept, action='Edit')

@app.route('/departments/delete/<int:did>', methods=['POST'])
@admin_required
def departments_delete(did):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM [Zktime_Copy].[dbo].[DEPARTMENTS] WHERE DEPTID = ?", (did,))
    conn.commit()
    conn.close()
    flash('Department deleted successfully!', 'info')
    return redirect(url_for('departments_manage'))


@app.route('/recommendations')
@admin_required
def recommendations_list():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT R.RecommendationID, R.RecommendationText, R.AppliesToDeptID, D.DEPTNAME FROM [Zktime_Copy].[dbo].[Recommendations] R LEFT JOIN [Zktime_Copy].[dbo].[DEPARTMENTS] D ON R.AppliesToDeptID = D.DEPTID ORDER BY R.RecommendationID")
    recommendations = cursor.fetchall()
    conn.close()
    return render_template('recommendations_list.html', recommendations=recommendations)

@app.route('/recommendations/add', methods=['GET', 'POST'])
@admin_required
def recommendations_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime_Copy].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    departments = cursor.fetchall()
    if request.method == 'POST':
        text = request.form['text']
        dept_id = request.form.get('dept_id')
        dept_id = int(dept_id) if dept_id else None
        try:
            cursor.execute("INSERT INTO [Zktime_Copy].[dbo].[Recommendations] (RecommendationText, AppliesToDeptID) VALUES (?, ?)", (text, dept_id))
            conn.commit()
            flash('✅ تم إضافة التوصية بنجاح!', 'success')
            return redirect(url_for('recommendations_list'))
        except Exception as e:
            conn.rollback()
            flash(f'❌ خطأ في قاعدة البيانات: {e}', 'danger')
        finally:
            conn.close()
    conn.close()
    return render_template('recommendation_form.html', departments=departments, action='Add')

@app.route('/recommendations/edit/<int:rid>', methods=['GET', 'POST'])
@admin_required
def recommendations_edit(rid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime_Copy].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    departments = cursor.fetchall()
    cursor.execute("SELECT * FROM [Zktime_Copy].[dbo].[Recommendations] WHERE RecommendationID = ?", (rid,))
    recommendation = cursor.fetchone()
    if not recommendation:
        flash('لم يتم العثور على التوصية!', 'warning')
        conn.close()
        return redirect(url_for('recommendations_list'))
    if request.method == 'POST':
        text = request.form['text']
        dept_id = request.form.get('dept_id')
        dept_id = int(dept_id) if dept_id else None
        try:
            cursor.execute("UPDATE [Zktime_Copy].[dbo].[Recommendations] SET RecommendationText = ?, AppliesToDeptID = ? WHERE RecommendationID = ?", (text, dept_id, rid))
            conn.commit()
            flash('✅ تم تحديث التوصية بنجاح!', 'success')
            return redirect(url_for('recommendations_list'))
        except Exception as e:
            conn.rollback()
            flash(f'❌ خطأ في قاعدة البيانات: {e}', 'danger')
        finally:
            conn.close()
    conn.close()
    return render_template('recommendation_form.html', departments=departments, recommendation=recommendation, action='Edit')

@app.route('/recommendations/delete/<int:rid>', methods=['POST'])
@admin_required
def recommendations_delete(rid):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) as cnt FROM [Zktime_Copy].[dbo].[Evaluations] WHERE RecommendationID = ?", (rid,))
        if cursor.fetchone().cnt > 0:
            flash('لا يمكن حذف توصية مستخدمة في تقييمات سابقة.', 'danger')
        else:
            cursor.execute("DELETE FROM [Zktime_Copy].[dbo].[Recommendations] WHERE RecommendationID = ?", (rid,))
            conn.commit()
            flash('تم حذف التوصية بنجاح!', 'info')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting recommendation: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('recommendations_list'))



@app.route('/evaluation/criteria')
@admin_required
def criteria_list():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT C.CriteriaID, C.CriteriaName, C.CriteriaWeight, C.MaxScore, C.AppliesToDeptID, C.employee_class, D.DEPTNAME FROM [Zktime_Copy].[dbo].[EvaluationCriteria] C LEFT JOIN [Zktime_Copy].[dbo].[DEPARTMENTS] D ON C.AppliesToDeptID = D.DEPTID ORDER BY C.CriteriaID")
    criteria = cursor.fetchall()
    conn.close()
    return render_template('criteria_list.html', criteria=criteria)

@app.route('/evaluation/criteria/add', methods=['GET', 'POST'])
@admin_required
def criteria_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime_Copy].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    departments = cursor.fetchall()
    if request.method == 'POST':
        name = request.form['name']
        weight = request.form['weight']
        max_score = request.form.get('max_score', 10)
        dept_id = request.form.get('dept_id')
        dept_id = int(dept_id) if dept_id else None
        employee_levels = request.form.getlist('employee_levels')
        employee_class = ','.join(employee_levels) if employee_levels else 'لم تضاف'
        try:
            weight_float = float(weight)
            max_score_int = int(max_score)
            if not (0 < weight_float <= 1):
                raise ValueError("Weight must be between 0 and 1 (e.g., 0.20 for 20%)")
            if max_score_int <= 0:
                 raise ValueError("Max score must be positive")
            valid_classes = ['A', 'B', 'C', 'مشرف', 'مدير']
            if not employee_levels:
                raise ValueError("Please select at least one employee level")
            for level in employee_levels:
                if level not in valid_classes:
                    raise ValueError(f"Invalid employee level: {level}")
        except ValueError as e:
            flash(f'Invalid input: {e}', 'danger')
            conn.close()
            return render_template('criteria_form.html', departments=departments, action='Add')
        try:
            cursor.execute("INSERT INTO [Zktime_Copy].[dbo].[EvaluationCriteria] (CriteriaName, CriteriaWeight, MaxScore, AppliesToDeptID, employee_class) VALUES (?, ?, ?, ?, ?)", (name, weight_float, max_score_int, dept_id, employee_class))
            conn.commit()
            flash('✅ Criterion added successfully!', 'success')
            return redirect(url_for('criteria_list'))
        except Exception as e:
            conn.rollback()
            flash(f'❌ Database error: {e}', 'danger')
        finally:
            conn.close()
    conn.close()
    return render_template('criteria_form.html', departments=departments, action='Add')

@app.route('/evaluation/criteria/edit/<int:cid>', methods=['GET', 'POST'])
@admin_required
def criteria_edit(cid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime_Copy].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    departments = cursor.fetchall()
    cursor.execute("SELECT * FROM [Zktime_Copy].[dbo].[EvaluationCriteria] WHERE CriteriaID = ?", (cid,))
    criterion = cursor.fetchone()
    if not criterion:
        flash('Criterion not found!', 'warning')
        conn.close()
        return redirect(url_for('criteria_list'))
    if request.method == 'POST':
        name = request.form['name']
        weight = request.form['weight']
        max_score = request.form.get('max_score', 10)
        dept_id = request.form.get('dept_id')
        dept_id = int(dept_id) if dept_id else None
        employee_levels = request.form.getlist('employee_levels')
        employee_class = ','.join(employee_levels) if employee_levels else 'لم تضاف'
        try:
            weight_float = float(weight)
            max_score_int = int(max_score)
            if not (0 < weight_float <= 1):
                raise ValueError("Weight must be between 0 and 1 (e.g., 0.20 for 20%)")
            if max_score_int <= 0:
                 raise ValueError("Max score must be positive")
            valid_classes = ['A', 'B', 'C', 'مشرف', 'مدير']
            if not employee_levels:
                raise ValueError("Please select at least one employee level")
            for level in employee_levels:
                if level not in valid_classes:
                    raise ValueError(f"Invalid employee level: {level}")
        except ValueError as e:
            flash(f'Invalid input: {e}', 'danger')
            conn.close()
            return render_template('criteria_form.html', departments=departments, criterion=criterion, action='Edit')
        try:
            cursor.execute("UPDATE [Zktime_Copy].[dbo].[EvaluationCriteria] SET CriteriaName = ?, CriteriaWeight = ?, MaxScore = ?, AppliesToDeptID = ?, employee_class = ? WHERE CriteriaID = ?", (name, weight_float, max_score_int, dept_id, employee_class, cid))
            conn.commit()
            flash('✅ Criterion updated successfully!', 'success')
            return redirect(url_for('criteria_list'))
        except Exception as e:
            conn.rollback()
            flash(f'❌ Database error: {e}', 'danger')
        finally:
            conn.close()
    conn.close()
    return render_template('criteria_form.html', departments=departments, criterion=criterion, action='Edit')

@app.route('/evaluation/criteria/delete/<int:cid>', methods=['POST'])
@admin_required
def criteria_delete(cid):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) as cnt FROM [Zktime_Copy].[dbo].[EvaluationDetails] WHERE CriteriaID = ?", (cid,))
        usage_count = cursor.fetchone().cnt
        if usage_count > 0:
            flash('Cannot delete criterion, it is used in existing evaluations.', 'danger')
        else:
            cursor.execute("DELETE FROM [Zktime_Copy].[dbo].[EvaluationCriteria] WHERE CriteriaID = ?", (cid,))
            conn.commit()
            flash('Criterion deleted successfully!', 'info')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting criterion: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('criteria_list'))



@app.template_filter('format_date')
def format_date(value, format='%Y-%m-%d'):
    """Format a date whether it's a string or datetime object."""
    if value is None:
        return ''
    
    # If it's already a datetime/date object, format it
    if hasattr(value, 'strftime'):
        return value.strftime(format)
    
    # If it's a string, try to parse it to ensure it looks right
    if isinstance(value, str):
        # If it's already a string, usually just return it, or strip time if needed
        try:
            # Quick cleanup if string looks like '2025-10-01 00:00:00'
            return value.split(' ')[0] 
        except:
            return value
            
    return str(value)



@app.route('/evaluation/select_user')
@login_required
def select_user_for_evaluation():
    role_id = session.get('role_id')
    evaluator_user_id = session.get('user_id')
    search_query = request.args.get('search', '').strip()
    
    if role_id not in [2, 3]:
        flash('ليس لديك الصلاحية لإنشاء تقييم.', 'danger')
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    users_to_evaluate = []
    page_title = "اختر موظف للتقييم"
    
    if role_id == 3:
        cursor.execute("SELECT DepartmentID FROM [Zktime_Copy].[dbo].[Users] WHERE UserID = ?", (evaluator_user_id,))
        user_record = cursor.fetchone()
        manager_dept_id = user_record.DepartmentID if user_record else None
        
        if manager_dept_id:
            # UPDATED QUERY: Now selects UI.BADGENUMBER
            query = "SELECT UI.USERID, UI.NAME, UI.TITLE, UI.PositionID, P.PositionName, D.DEPTNAME, UI.BADGENUMBER FROM [Zktime_Copy].[dbo].[USERINFO] UI LEFT JOIN [dbo].[POSITIONS] P ON UI.PositionID = P.PositionID LEFT JOIN [dbo].[DEPARTMENTS] D ON UI.DEFAULTDEPTID = D.DEPTID WHERE UI.DEFAULTDEPTID = ? AND UI.USERID != ?"
            params = [manager_dept_id, evaluator_user_id]
            
            if search_query:
                query += " AND (UI.NAME LIKE ? OR UI.TITLE LIKE ? OR P.PositionName LIKE ?)"
                params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])
            
            cursor.execute(query, params)
            users_to_evaluate = cursor.fetchall()
        else:
             flash('لم يتم تحديد قسم لهذا المدير.', 'warning')
             
    elif role_id == 2:
        page_title = "اختر مدير للتقييم"
        # UPDATED QUERY: Now selects UI.BADGENUMBER logic
        query = "SELECT U.UserID, U.Name, U.Username, U.DepartmentID, D.DEPTNAME, UI.BADGENUMBER FROM [Zktime_Copy].[dbo].[Users] U LEFT JOIN [dbo].[DEPARTMENTS] D ON U.DepartmentID = D.DEPTID LEFT JOIN [Zktime_Copy].[dbo].[USERINFO] UI ON U.UserID = UI.USERID WHERE U.RoleID = 3 AND U.UserID != ?"
        params = [evaluator_user_id]
        
        if search_query:
            query += " AND (U.Name LIKE ? OR U.Username LIKE ? OR D.DEPTNAME LIKE ?)"
            params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])
            
        cursor.execute(query, params)
        managers = cursor.fetchall()
        for mgr in managers:
            users_to_evaluate.append({
                'USERID': mgr.UserID, 
                'NAME': mgr.Name or mgr.Username, 
                'TITLE': 'Manager', 
                'PositionName': None, 
                'DEPTNAME': mgr.DEPTNAME or 'غير محدد', 
                'IsManager': True,
                'BADGENUMBER': mgr.BADGENUMBER # Added this
            })
            
    conn.close()
    return render_template('select_user_for_evaluation.html', users=users_to_evaluate, role_id=role_id, page_title=page_title, filters=request.args)

@app.route('/evaluation/new/<string:badgenumber_str>', methods=['GET', 'POST'])
@login_required
def new_evaluation(badgenumber_str):
    """
    Handles the creation of a new performance evaluation, using the employee's
    BADGENUMBER from the URL to look up the internal UserID.
    """
    role_id = session.get('role_id')
    evaluator_user_id = session.get('user_id')

    # 1. Authorization Check
    if role_id not in [2, 3]:
        flash('ليس لديك الصلاحية لإنشاء تقييم.', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get evaluator's department ID
    cursor.execute("SELECT DepartmentID FROM [Zktime_Copy].[dbo].[Users] WHERE UserID = ?", (evaluator_user_id,))
    manager_record = cursor.fetchone()
    manager_dept_id = manager_record.DepartmentID if manager_record else None

    # Variables for the target employee's information
    employee_info = None
    target_user_dept_id = None
    employee_user_id = None  

    is_manager = request.args.get('is_manager', 'false').lower() == 'true'

    # 2. Employee Lookup based on BADGENUMBER
    if is_manager and role_id == 2:
        cursor.execute("""
            SELECT U.UserID, U.Name, U.Username, U.DepartmentID, D.DEPTNAME, UI.DEFAULTDEPTID,
                   (SELECT COUNT(*) FROM TrainingEnrollments TE WHERE TE.EmployeeUserID = U.UserID) AS TotalSessions
            FROM [Zktime_Copy].[dbo].[Users] U
            LEFT JOIN [dbo].[DEPARTMENTS] D ON U.DepartmentID = D.DEPTID
            INNER JOIN [Zktime_Copy].[dbo].[USERINFO] UI ON U.UserID = UI.USERID
            WHERE UI.BADGENUMBER = ? AND U.RoleID = 3
        """, (badgenumber_str,))
        user_record = cursor.fetchone()

        if user_record:
            employee_user_id = user_record.UserID 
            target_user_dept_id = user_record.DEFAULTDEPTID
            class Row: pass
            employee_info = Row()
            employee_info.USERID = user_record.UserID
            employee_info.NAME = user_record.Name or user_record.Username
            employee_info.DEPTNAME = user_record.DEPTNAME or 'غير محدد'
            employee_info.TITLE = 'Manager'
            employee_info.DEFAULTDEPTID = user_record.DEFAULTDEPTID

    elif not is_manager and role_id == 3:
        cursor.execute("""
            SELECT UI.USERID, UI.NAME, UI.DEFAULTDEPTID, UI.TITLE, D.DEPTNAME,
                   (SELECT COUNT(*) FROM TrainingEnrollments TE WHERE TE.EmployeeUserID = UI.USERID) AS TotalSessions
            FROM [Zktime_Copy].[dbo].[USERINFO] UI
            LEFT JOIN [dbo].[DEPARTMENTS] D ON UI.DEFAULTDEPTID = D.DEPTID
            WHERE UI.BADGENUMBER = ?
        """, (badgenumber_str,))
        employee_info = cursor.fetchone()
        if employee_info:
            employee_user_id = employee_info.USERID

    if not employee_info or not employee_user_id:
        flash('لم يتم العثور على المستخدم المطلوب.', 'danger')
        conn.close()
        return redirect(url_for('select_user_for_evaluation'))

    # 3. Department and Permission Checks
    employee_dept_id = employee_info.DEFAULTDEPTID
    if role_id == 3 and manager_dept_id != employee_dept_id:
        flash('لا يمكنك تقييم موظف ليس في قسمك.', 'danger')
        conn.close()
        return redirect(url_for('select_user_for_evaluation'))

    # ===================== FETCH TRAINING HISTORY (CORRECTED) =====================
    # 1. جلب خريطة بأسماء المدربين أولاً لتفادي مشاكل الـ JOIN
    cursor.execute("SELECT UserID, Name FROM Users")
    all_instructors = {row.UserID: row.Name for row in cursor.fetchall()}

    # 2. الاستعلام بدون JOIN مع جدول Users لتجنب خطأ التحويل
    cursor.execute("""
        SELECT 
            TC.TrainingCourseText AS CourseName,
            TS.SessionDate AS StartDate,
            TE.PassStatus AS Status,
            TE.Grade,
            TE.InstructorFeedback AS TrainerNotes,
            TS.IsExternal,
            TS.ExternalTrainerName,
            TS.InstructorID, -- نجلب الآيدي الخام
            (SELECT COUNT(*) FROM TrainingSessionDays TSD WHERE TSD.SessionID = TS.SessionID) AS TotalSessions,
            (SELECT COUNT(*) FROM TrainingAttendance TA WHERE TA.SessionID = TS.SessionID AND TA.EnrollmentID = TE.EnrollmentID) AS SessionsAttended
        FROM TrainingEnrollments TE
        JOIN TrainingSessions TS ON TE.SessionID = TS.SessionID
        JOIN TrainingCourses TC ON TS.CourseID = TC.TrainingCourseID
        WHERE TE.EmployeeUserID = ?
        ORDER BY TS.SessionDate DESC
    """, (employee_user_id,))
    
    training_rows_raw = cursor.fetchall()
    training_history = []

    # 3. معالجة البيانات وبناء القائمة النهائية
    for row in training_rows_raw:
        # تحديد اسم المدرب (سواء خارجي أو داخلي متعدد)
        trainers_str = ""
        if row.IsExternal:
            trainers_str = row.ExternalTrainerName or "مدرب خارجي"
        else:
            if row.InstructorID:
                try:
                    # تقسيم النص '5,18' إلى أرقام والبحث عن الأسماء
                    ids = [int(x.strip()) for x in str(row.InstructorID).split(',') if x.strip().isdigit()]
                    names = [all_instructors.get(uid, 'غير معروف') for uid in ids]
                    trainers_str = "، ".join(names)
                except:
                    trainers_str = "خطأ في البيانات"
            else:
                trainers_str = "غير محدد"

        training_history.append({
            'CourseName': row.CourseName,
            'StartDate': row.StartDate,
            'Status': row.Status,
            'Grade': row.Grade,
            'TrainerNotes': row.TrainerNotes,
            'Trainers': trainers_str, # الحقل الجاهز للعرض
            'TotalSessions': row.TotalSessions,
            'SessionsAttended': row.SessionsAttended
        })
    # ==============================================================================

    # 4. Fetch Evaluation Criteria
    employee_class_string = get_employee_class(employee_user_id) 
    class_likes = []
    class_params = []
    if employee_class_string and employee_class_string != 'لم تضاف':
        for cls in employee_class_string.split(','):
            cls_clean = cls.strip()
            if cls_clean:
                class_likes.append("employee_class LIKE ?")
                class_params.append(f"%{cls_clean}%")

    class_clause = "(" + " OR ".join(class_likes) + ")" if class_likes else "employee_class = 'لم تضاف'"
    
    criteria_query = f"SELECT CriteriaID, CriteriaName, CriteriaWeight, MaxScore FROM [Zktime_Copy].[dbo].[EvaluationCriteria] WHERE {class_clause} AND (AppliesToDeptID = ? OR AppliesToDeptID IS NULL) ORDER BY CriteriaID"
    criteria_params = class_params + [employee_dept_id]
    
    cursor.execute(criteria_query, criteria_params)
    criteria = cursor.fetchall()

    if not criteria:
        flash(f'⚠️ لم يتم تعريف معايير تقييم للفئة "{employee_class_string}" في هذا القسم.', 'warning')
        conn.close()
        return redirect(url_for('select_user_for_evaluation'))

    cursor.execute("SELECT RecommendationID, RecommendationText FROM [Zktime_Copy].[dbo].[Recommendations] WHERE AppliesToDeptID = ? OR AppliesToDeptID IS NULL ORDER BY RecommendationText", (employee_dept_id,))
    recommendations = cursor.fetchall()
    
    cursor.execute("""
        SELECT TrainingCourseID, TrainingCourseText 
        FROM [Zktime_Copy].[dbo].[TrainingCourses] 
        WHERE (AppliesToDeptID = ? OR AppliesToDeptID IS NULL) 
        AND IsActive = 1 
        ORDER BY TrainingCourseText
    """, (employee_dept_id,))
    training_courses = cursor.fetchall()
    
    available_evals = get_available_evaluation_types(conn, employee_user_id, manager_dept_id)

    # 5. POST Request Handling
    if request.method == 'POST':
        try:
            eval_type_id = request.form['evaluation_type_id']
            if not eval_type_id or not any(e['id'] == int(eval_type_id) and not e['disabled'] for e in available_evals):
                flash('❌ نوع التقييم المختار غير متاح أو غير صحيح.', 'danger')
                raise ValueError("Invalid or disabled evaluation type submitted.")

            comments = request.form.get('comments', '').strip()
            recommendation_id = request.form.get('recommendation_id') or None
            training_course_id = request.form.get('training_course_id') or None

            cursor.execute("INSERT INTO [Zktime_Copy].[dbo].[Evaluations] (EmployeeUserID, EvaluatorUserID, EvaluationTypeID, ManagerComments, RecommendationID, TrainingCourseID) OUTPUT INSERTED.EvaluationID VALUES (?, ?, ?, ?, ?, ?)", (employee_user_id, evaluator_user_id, eval_type_id, comments, recommendation_id, training_course_id))
            evaluation_id = cursor.fetchone().EvaluationID

            total_weighted_score = 0.0
            total_max_weighted_score = 0.0
            scores_data = []

            for item in criteria:
                score_str = request.form.get(f'score_{item.CriteriaID}')
                if score_str is None or not score_str.isdigit():
                    raise ValueError(f"الدرجة المدخلة للبند '{item.CriteriaName}' غير صحيحة.")
                
                score = int(score_str)
                max_score = int(item.MaxScore)
                
                if not (0 <= score <= max_score):
                    raise ValueError(f"الدرجة للبند '{item.CriteriaName}' يجب أن تكون بين 0 و {max_score}.")
                
                scores_data.append((evaluation_id, item.CriteriaID, score))
                weight = float(item.CriteriaWeight)
                
                total_weighted_score += (score / max_score) * weight 
                total_max_weighted_score += weight

            if scores_data:
                cursor.executemany("INSERT INTO [Zktime_Copy].[dbo].[EvaluationDetails] (EvaluationID, CriteriaID, ScoreGiven) VALUES (?, ?, ?)", scores_data)

            final_percentage = (total_weighted_score / total_max_weighted_score) * 100 if total_max_weighted_score > 0 else 0
            final_rating = get_rating_from_score(final_percentage)

            cursor.execute("UPDATE [Zktime_Copy].[dbo].[Evaluations] SET OverallScore = ?, OverallRating = ? WHERE EvaluationID = ?", (final_percentage, final_rating, evaluation_id))
            
            conn.commit()
            flash('تم إرسال التقييم بنجاح!', 'success')
            return redirect(url_for('dashboard'))

        except ValueError as ve:
            conn.rollback()
            flash(f'خطأ في الإدخال: {ve}', 'danger')
        except Exception as e:
            conn.rollback()
            flash(f'حدث خطأ غير متوقع: {e}', 'danger')
        finally:
            conn.close() 

    conn.close() # تأكد من إغلاق الاتصال في حالة GET أيضاً
    return render_template('new_evaluation_form.html', 
                           employee=employee_info, 
                           criteria=criteria, 
                           recommendations=recommendations, 
                           training_courses=training_courses, 
                           employee_class=employee_class_string, 
                           available_evals=available_evals,
                           training_history=training_history)

@app.route('/evaluation/reports')
@login_required
def evaluation_reports():
    conn = None
    reports = []
    search_employee = request.args.get('search_employee', '').strip()
    search_evaluator = request.args.get('search_evaluator', '').strip()
    eval_type_id = request.args.get('eval_type_id', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    recommendation_id = request.args.get('recommendation_id', '')
    training_course_id = request.args.get('training_course_id', '')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        role_id = session.get('role_id')
        user_id = session.get('user_id')
        cursor.execute("SELECT RecommendationID, RecommendationText FROM [Zktime_Copy].[dbo].[Recommendations] ORDER BY RecommendationText")
        all_recommendations = cursor.fetchall()
        cursor.execute("SELECT TrainingCourseID, TrainingCourseText FROM [Zktime_Copy].[dbo].[TrainingCourses] ORDER BY TrainingCourseText")
        all_training_courses = cursor.fetchall()
        cursor.execute("SELECT EvaluationTypeID, DisplayName FROM [Zktime_Copy].[dbo].[EvaluationTypes] ORDER BY SortOrder")
        all_evaluation_types = cursor.fetchall()
        query = """
            SELECT E.EvaluationID, E.EvaluationDate, COALESCE(ET.DisplayName, E.EvaluationType) as EvaluationType,
                E.OverallScore, E.OverallRating, E.ManagerComments,
                COALESCE(EmpInfo.NAME, EmpUser.Name, EmpUser.Username) AS EmployeeName, 
                COALESCE(Mgr.Name, Mgr.Username) AS EvaluatorName, EmpInfo.employee_class,
                R.RecommendationText, TC.TrainingCourseText
            FROM [Zktime_Copy].[dbo].[Evaluations] E
            LEFT JOIN [Zktime_Copy].[dbo].[Users] Mgr ON E.EvaluatorUserID = Mgr.UserID 
            LEFT JOIN [Zktime_Copy].[dbo].[USERINFO] EmpInfo ON E.EmployeeUserID = EmpInfo.USERID
            LEFT JOIN [Zktime_Copy].[dbo].[Users] EmpUser ON E.EmployeeUserID = EmpUser.UserID
            LEFT JOIN [Zktime_Copy].[dbo].[Recommendations] R ON E.RecommendationID = R.RecommendationID
            LEFT JOIN [Zktime_Copy].[dbo].[TrainingCourses] TC ON E.TrainingCourseID = TC.TrainingCourseID
            LEFT JOIN [Zktime_Copy].[dbo].[EvaluationTypes] ET ON E.EvaluationTypeID = ET.EvaluationTypeID
        """
        where_clauses = []
        params = []
        if role_id == 5:
            where_clauses.append("E.EmployeeUserID = ?")
            params.append(user_id)
        elif role_id == 3 or role_id == 2:
            where_clauses.append("E.EvaluatorUserID = ?")
            params.append(user_id)
        elif role_id in [1, 4]:
             where_clauses.append("1=1")
        else:
             where_clauses.append("1=0") 
        if search_employee:
            where_clauses.append("(COALESCE(EmpInfo.NAME, EmpUser.Name, EmpUser.Username) LIKE ?)")
            params.append(f"%{search_employee}%")
        if is_admin():
            if search_evaluator:
                where_clauses.append("(COALESCE(Mgr.Name, Mgr.Username) LIKE ?)")
                params.append(f"%{search_evaluator}%")
        elif role_id != 5:
            if search_evaluator:
                 where_clauses.append("(COALESCE(Mgr.Name, Mgr.Username) LIKE ? AND E.EvaluatorUserID = ?)")
                 params.append(f"%{search_evaluator}%")
                 params.append(user_id)
        if eval_type_id:
            where_clauses.append("E.EvaluationTypeID = ?")
            params.append(eval_type_id)
        if date_from:
            where_clauses.append("E.EvaluationDate >= ?")
            params.append(date_from)
        if date_to:
            where_clauses.append("E.EvaluationDate < DATEADD(day, 1, ?)") 
            params.append(date_to)
        if recommendation_id:
            where_clauses.append("E.RecommendationID = ?")
            params.append(recommendation_id)
        if training_course_id:
            where_clauses.append("E.TrainingCourseID = ?")
            params.append(training_course_id)
        query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY E.EvaluationDate DESC"
        cursor.execute(query, params)
        reports = cursor.fetchall()
    except Exception as e:
        flash(f"Error fetching reports: {e}", "danger")
    finally:
        if conn: conn.close()
    return render_template('evaluation_reports.html', reports=reports, is_admin=is_admin(), filters=request.args, all_recommendations=all_recommendations, all_training_courses=all_training_courses, all_evaluation_types=all_evaluation_types)

@app.route('/evaluation-types')
@admin_required
def evaluation_types_list():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ET.EvaluationTypeID, ET.TypeName, ET.DisplayName, ET.IsRepeatable, ET.SortOrder, Pre.DisplayName as PrerequisiteName FROM [Zktime_Copy].[dbo].[EvaluationTypes] ET LEFT JOIN [Zktime_Copy].[dbo].[EvaluationTypes] Pre ON ET.PrerequisiteTypeID = Pre.EvaluationTypeID ORDER BY ET.SortOrder")
    types = cursor.fetchall()
    conn.close()
    return render_template('evaluation_types_list.html', types=types)

@app.route('/evaluation-types/add', methods=['GET', 'POST'])
@admin_required
def evaluation_types_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT EvaluationTypeID, DisplayName FROM [Zktime_Copy].[dbo].[EvaluationTypes] ORDER BY SortOrder")
    all_types = cursor.fetchall()
    if request.method == 'POST':
        try:
            type_name = request.form['type_name']
            display_name = request.form['display_name']
            is_repeatable = 'is_repeatable' in request.form
            prerequisite_id = request.form.get('prerequisite_id') or None
            sort_order = request.form.get('sort_order', 100)
            cursor.execute("INSERT INTO [Zktime_Copy].[dbo].[EvaluationTypes] (TypeName, DisplayName, IsRepeatable, PrerequisiteTypeID, SortOrder) VALUES (?, ?, ?, ?, ?)", (type_name, display_name, is_repeatable, prerequisite_id, sort_order))
            conn.commit()
            flash('✅ تم إضافة نوع التقييم بنجاح', 'success')
            return redirect(url_for('evaluation_types_list'))
        except Exception as e:
            conn.rollback()
            flash(f'❌ خطأ في قاعدة البيانات: {e}', 'danger')
        finally:
            conn.close()
    conn.close()
    return render_template('evaluation_type_form.html', action='Add', all_types=all_types)

@app.route('/evaluation-types/edit/<int:type_id>', methods=['GET', 'POST'])
@admin_required
def evaluation_types_edit(type_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT EvaluationTypeID, DisplayName FROM [Zktime_Copy].[dbo].[EvaluationTypes] WHERE EvaluationTypeID != ? ORDER BY SortOrder", (type_id,))
    all_types = cursor.fetchall()
    cursor.execute("SELECT * FROM [Zktime_Copy].[dbo].[EvaluationTypes] WHERE EvaluationTypeID = ?", (type_id,))
    eval_type = cursor.fetchone()
    if not eval_type:
        flash('❌ لم يتم العثور على نوع التقييم', 'danger')
        conn.close()
        return redirect(url_for('evaluation_types_list'))
    if request.method == 'POST':
        try:
            type_name = request.form['type_name']
            display_name = request.form['display_name']
            is_repeatable = 'is_repeatable' in request.form
            prerequisite_id = request.form.get('prerequisite_id') or None
            sort_order = request.form.get('sort_order', 100)
            cursor.execute("UPDATE [Zktime_Copy].[dbo].[EvaluationTypes] SET TypeName = ?, DisplayName = ?, IsRepeatable = ?, PrerequisiteTypeID = ?, SortOrder = ? WHERE EvaluationTypeID = ?", (type_name, display_name, is_repeatable, prerequisite_id, sort_order, type_id))
            conn.commit()
            flash('✅ تم تحديث نوع التقييم بنجاح', 'success')
            return redirect(url_for('evaluation_types_list'))
        except Exception as e:
            conn.rollback()
            flash(f'❌ خطأ في قاعدة البيانات: {e}', 'danger')
        finally:
            conn.close()
    conn.close()
    return render_template('evaluation_type_form.html', action='Edit', eval_type=eval_type, all_types=all_types)

@app.route('/evaluation-types/delete/<int:type_id>', methods=['POST'])
@admin_required
def evaluation_types_delete(type_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) as cnt FROM [Zktime_Copy].[dbo].[Evaluations] WHERE EvaluationTypeID = ?", (type_id,))
        if cursor.fetchone().cnt > 0:
            flash('❌ لا يمكن الحذف، هذا النوع مستخدم في تقييمات سابقة.', 'danger')
            conn.close()
            return redirect(url_for('evaluation_types_list'))
        cursor.execute("SELECT COUNT(*) as cnt FROM [Zktime_Copy].[dbo].[EvaluationTypes] WHERE PrerequisiteTypeID = ?", (type_id,))
        if cursor.fetchone().cnt > 0:
            flash('❌ لا يمكن الحذف، هذا النوع هو متطلب لنوع آخر.', 'danger')
            conn.close()
            return redirect(url_for('evaluation_types_list'))
        cursor.execute("DELETE FROM [Zktime_Copy].[dbo].[EvaluationTypes] WHERE EvaluationTypeID = ?", (type_id,))
        conn.commit()
        flash('✅ تم حذف نوع التقييم بنجاح', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'❌ خطأ في قاعدة البيانات: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('evaluation_types_list'))

@app.route('/evaluation-cycles')
@admin_required
def evaluation_cycles_list():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT C.CycleID, C.CycleName, C.StartDate, C.EndDate, C.IsEnabled, ET.DisplayName as EvaluationTypeName FROM [Zktime_Copy].[dbo].[EvaluationCycles] C JOIN [Zktime_Copy].[dbo].[EvaluationTypes] ET ON C.EvaluationTypeID = ET.EvaluationTypeID ORDER BY C.StartDate DESC")
    cycles = cursor.fetchall()
    conn.close()
    return render_template('evaluation_cycles_list.html', cycles=cycles)


@app.route('/evaluation-cycles/add', methods=['GET', 'POST'])
@admin_required
def evaluation_cycles_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT EvaluationTypeID, DisplayName FROM [Zktime_Copy].[dbo].[EvaluationTypes] ORDER BY SortOrder")
    all_types = cursor.fetchall()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime_Copy].[dbo].[DEPARTMENTS] ORDER BY DEPTNAME")
    all_depts = cursor.fetchall()
    if request.method == 'POST':
        try:
            cycle_name = request.form['cycle_name']
            type_id = request.form['type_id']
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            is_enabled = 'is_enabled' in request.form
            dept_ids = request.form.getlist('dept_ids')
            cursor.execute("INSERT INTO [Zktime_Copy].[dbo].[EvaluationCycles] (CycleName, EvaluationTypeID, StartDate, EndDate, IsEnabled) OUTPUT INSERTED.CycleID VALUES (?, ?, ?, ?, ?)", (cycle_name, type_id, start_date, end_date, is_enabled))
            new_cycle_id = cursor.fetchone().CycleID
            if dept_ids:
                dept_data = [(new_cycle_id, int(dept_id)) for dept_id in dept_ids]
                cursor.executemany("INSERT INTO [Zktime_Copy].[dbo].[CycleDepartments] (CycleID, DepartmentID) VALUES (?, ?)", dept_data)
            conn.commit()
            flash('✅ تم إنشاء دورة التقييم بنجاح', 'success')
            return redirect(url_for('evaluation_cycles_list'))
        except Exception as e:
            conn.rollback()
            flash(f'❌ خطأ في قاعدة البيانات: {e}', 'danger')
        finally:
            conn.close()
    conn.close()
    return render_template('evaluation_cycle_form.html', action='Add', all_types=all_types, all_depts=all_depts, cycle_depts=[])

@app.route('/evaluation-cycles/edit/<int:cycle_id>', methods=['GET', 'POST'])
@admin_required
def evaluation_cycles_edit(cycle_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT EvaluationTypeID, DisplayName FROM [Zktime_Copy].[dbo].[EvaluationTypes] ORDER BY SortOrder")
    all_types = cursor.fetchall()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime_Copy].[dbo].[DEPARTMENTS] ORDER BY DEPTNAME")
    all_depts = cursor.fetchall()
    if request.method == 'POST':
        try:
            cycle_name = request.form['cycle_name']
            type_id = request.form['type_id']
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            is_enabled = 'is_enabled' in request.form
            dept_ids = request.form.getlist('dept_ids')
            cursor.execute("UPDATE [Zktime_Copy].[dbo].[EvaluationCycles] SET CycleName = ?, EvaluationTypeID = ?, StartDate = ?, EndDate = ?, IsEnabled = ? WHERE CycleID = ?", (cycle_name, type_id, start_date, end_date, is_enabled, cycle_id))
            cursor.execute("DELETE FROM [Zktime_Copy].[dbo].[CycleDepartments] WHERE CycleID = ?", (cycle_id,))
            if dept_ids:
                dept_data = [(cycle_id, int(dept_id)) for dept_id in dept_ids]
                cursor.executemany("INSERT INTO [Zktime_Copy].[dbo].[CycleDepartments] (CycleID, DepartmentID) VALUES (?, ?)", dept_data)
            conn.commit()
            flash('✅ تم تحديث دورة التقييم بنجاح', 'success')
            return redirect(url_for('evaluation_cycles_list'))
        except Exception as e:
            conn.rollback()
            flash(f'❌ خطأ في قاعدة البيانات: {e}', 'danger')
        finally:
            conn.close()
    cursor.execute("SELECT * FROM [Zktime_Copy].[dbo].[EvaluationCycles] WHERE CycleID = ?", (cycle_id,))
    cycle = cursor.fetchone()
    if not cycle:
        flash('❌ لم يتم العثور على الدورة', 'danger')
        conn.close()
        return redirect(url_for('evaluation_cycles_list'))
    cursor.execute("SELECT DepartmentID FROM [Zktime_Copy].[dbo].[CycleDepartments] WHERE CycleID = ?", (cycle_id,))
    cycle_depts_rows = cursor.fetchall()
    cycle_depts = [row.DepartmentID for row in cycle_depts_rows]
    conn.close()
    return render_template('evaluation_cycle_form.html', action='Edit', cycle=cycle, all_types=all_types, all_depts=all_depts, cycle_depts=cycle_depts)

@app.route('/evaluation-cycles/delete/<int:cycle_id>', methods=['POST'])
@admin_required
def evaluation_cycles_delete(cycle_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM [Zktime_Copy].[dbo].[CycleDepartments] WHERE CycleID = ?", (cycle_id,))
        cursor.execute("DELETE FROM [Zktime_Copy].[dbo].[EvaluationCycles] WHERE CycleID = ?", (cycle_id,))
        conn.commit()
        flash('✅ تم حذف الدورة بنجاح', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'❌ خطأ في قاعدة البيانات: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('evaluation_cycles_list'))

@app.route('/evaluation/details/<int:evaluation_id>')
@login_required 
def evaluation_details(evaluation_id):
    conn = None
    evaluation_data = None
    details = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        role_id = session.get('role_id')
        user_id = session.get('user_id')
        cursor.execute("SELECT E.EvaluationID, E.EvaluationDate, COALESCE(ET.DisplayName, E.EvaluationType) as EvaluationType, E.OverallScore, E.OverallRating, E.ManagerComments, E.EmployeeUserID, E.EvaluatorUserID, COALESCE(EmpInfo.NAME, EmpUser.Name, EmpUser.Username) AS EmployeeName, COALESCE(Mgr.Name, Mgr.Username) AS EvaluatorName, COALESCE(EmpInfo.TITLE, EmpUser.Name, EmpUser.Username) AS EmployeeTitle, DeptEmp.DEPTNAME as EmployeeDeptName, EmpInfo.employee_class, R.RecommendationText, TC.TrainingCourseText FROM [Zktime_Copy].[dbo].[Evaluations] E LEFT JOIN [Zktime_Copy].[dbo].[Users] Mgr ON E.EvaluatorUserID = Mgr.UserID LEFT JOIN [Zktime_Copy].[dbo].[USERINFO] EmpInfo ON E.EmployeeUserID = EmpInfo.USERID LEFT JOIN [Zktime_Copy].[dbo].[Users] EmpUser ON E.EmployeeUserID = EmpUser.UserID LEFT JOIN [Zktime_Copy].[dbo].[DEPARTMENTS] DeptEmp ON COALESCE(EmpInfo.DEFAULTDEPTID, EmpUser.DepartmentID) = DeptEmp.DEPTID LEFT JOIN [Zktime_Copy].[dbo].[Recommendations] R ON E.RecommendationID = R.RecommendationID LEFT JOIN [Zktime_Copy].[dbo].[TrainingCourses] TC ON E.TrainingCourseID = TC.TrainingCourseID LEFT JOIN [Zktime_Copy].[dbo].[EvaluationTypes] ET ON E.EvaluationTypeID = ET.EvaluationTypeID WHERE E.EvaluationID = ?", (evaluation_id,))
        evaluation_data = cursor.fetchone()
        if not evaluation_data:
            flash("Evaluation not found.", "warning")
            return redirect(url_for('evaluation_reports'))
        can_view = False
        if role_id in [1, 4]: can_view = True
        elif role_id in [2, 3] and evaluation_data.EvaluatorUserID == user_id: can_view = True
        elif role_id == 5 and evaluation_data.EmployeeUserID == user_id: can_view = True
        elif role_id == 3:
            cursor.execute("SELECT DepartmentID FROM [Zktime_Copy].[dbo].[Users] WHERE UserID = ?", (user_id,))
            manager_dept = cursor.fetchone()
            cursor.execute("SELECT DEFAULTDEPTID FROM [Zktime_Copy].[dbo].[USERINFO] WHERE USERID = ?", (evaluation_data.EmployeeUserID,))
            emp_dept = cursor.fetchone()
            if manager_dept and emp_dept and manager_dept.DepartmentID == emp_dept.DEFAULTDEPTID:
                can_view = True
        if not can_view:
             flash("You do not have permission to view this evaluation.", "danger")
             return redirect(url_for('evaluation_reports'))
        cursor.execute("SELECT ED.ScoreGiven, EC.CriteriaName, EC.CriteriaWeight, EC.MaxScore FROM [Zktime_Copy].[dbo].[EvaluationDetails] ED JOIN [Zktime_Copy].[dbo].[EvaluationCriteria] EC ON ED.CriteriaID = EC.CriteriaID WHERE ED.EvaluationID = ? ORDER BY EC.CriteriaID", (evaluation_id,))
        details = cursor.fetchall()
    except Exception as e:
        flash(f"Error fetching evaluation details: {e}", "danger")
        return redirect(url_for('evaluation_reports')) 
    finally:
        if conn: conn.close()
    return render_template('evaluation_details.html', eval=evaluation_data, details=details)


@app.route('/evaluation/delete/<int:evaluation_id>', methods=['POST'])
@admin_required
def evaluation_delete(evaluation_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # الحذف سيتم تلقائياً من جدول التفاصيل أيضاً بسبب خاصية CASCADE في قاعدة البيانات
        cursor.execute("DELETE FROM [Zktime_Copy].[dbo].[Evaluations] WHERE EvaluationID = ?", (evaluation_id,))
        conn.commit()
        flash('✅ تم حذف تقرير التقييم بنجاح.', 'success')
    except Exception as e:
        conn.rollback()
        print(f"Delete Error: {e}")
        flash(f'❌ حدث خطأ أثناء الحذف: {e}', 'danger')
    finally:
        conn.close()
    
    # العودة لنفس الصفحة مع الحفاظ على الفلاتر إن أمكن (أو للصفحة الرئيسية للتقارير)
    return redirect(url_for('evaluation_reports'))

@app.route('/user_pic/<int:user_id>')
def user_pic(user_id):
    conn = get_db_connection() 
    cursor = conn.cursor()
    cursor.execute("SELECT pic FROM USERINFO WHERE USERID = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row.pic: return send_file(io.BytesIO(row.pic), mimetype='image/jpeg')
    else: return redirect("https://placehold.co/150x150/0d6efd/white?text=No+Image", code=302)
    
@app.route('/admin/upload_pic/<int:user_id>', methods=['POST'])
def upload_pic(user_id):
    if 'user_pic' not in request.files: return redirect(request.referrer)
    file = request.files['user_pic']
    if file.filename == '': return redirect(request.referrer)
    if file:
        pic_data = file.read()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE USERINFO SET pic = ? WHERE USERID = ?", (pic_data, user_id))
        conn.commit()
        conn.close()
    return redirect(request.referrer)    


# ===================== LMS: TRAINING MODULE =====================



@app.route('/training/calendar')
@login_required
def training_calendar():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Get courses for dropdown
    cursor.execute("SELECT TrainingCourseID, TrainingCourseText FROM TrainingCourses")
    courses = cursor.fetchall()
    # Get internal instructors
    cursor.execute("""
    SELECT UI.USERID, UI.NAME, D.DEPTNAME
    FROM USERINFO UI
    LEFT JOIN DEPARTMENTS D ON UI.DEFAULTDEPTID = D.DEPTID
    WHERE UI.IsActive = 1
""")
    instructors = cursor.fetchall()
    conn.close()
    return render_template('training_calendar.html', courses=courses, instructors=instructors)

# 1. API: Get Events (Updated to include End Date)
@app.route('/api/training/events')
@login_required
def get_training_events():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT S.SessionID, S.SessionDate, S.EndDate, S.IsExternal, S.EventType,
               TC.TrainingCourseText,
               U.Name as IntTrainer, S.ExternalTrainerName, S.ExternalCompany
        FROM TrainingSessions S
        LEFT JOIN TrainingCourses TC ON S.CourseID = TC.TrainingCourseID
        LEFT JOIN USERINFO U ON S.InstructorID = U.USERID
        LEFT JOIN DEPARTMENTS D ON U.DEFAULTDEPTID = D.DEPTID

    """)
    rows = cursor.fetchall()
    conn.close()
    
    events = []
    for r in rows:
        trainer = f"{r.ExternalTrainerName}" if r.IsExternal else r.IntTrainer
        title = f"{r.TrainingCourseText} - {trainer}"
        
        # Color Logic
        if r.IsExternal: color = '#e67e22' # Orange
        elif r.EventType == 'Course': color = '#27ae60' # Green
        else: color = '#004d7a' # Blue
        
        # Handle End Date for FullCalendar (It requires end date to be +1 day to show correctly)
        start = r.SessionDate.strftime('%Y-%m-%d')
        end = None
        if r.EndDate:
            # Add 1 day because FullCalendar end date is exclusive
            end_obj = r.EndDate + datetime.timedelta(days=1)
            end = end_obj.strftime('%Y-%m-%d')
            
        events.append({
            'id': r.SessionID,
            'title': title,
            'start': start,
            'end': end,  # Pass the calculated end date
            'backgroundColor': color,
            'url': url_for('training_session_detail', sid=r.SessionID)
        })
    return json.dumps(events)

# 2. API: Add Event (Updated to save End Date)
@app.route('/training/add_event', methods=['POST'])
@login_required
def training_add_event():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        course_id = request.form['course_id']
        
        # Get Start and End Dates
        start_date = request.form['start_date']
        end_date = request.form.get('end_date') # Could be empty if single day
        
        # If no end date selected, make it same as start date
        if not end_date:
            end_date = start_date

        location = request.form['location']
        event_type = request.form.get('event_type', 'Session')
        trainer_type = request.form['trainer_type']
        
        if trainer_type == 'external':
            is_external = 1
            instructor_id = None
            ext_name = request.form['ext_name']
            ext_comp = request.form['ext_company']
        else:
            is_external = 0
            instructor_id = request.form['instructor_id']
            ext_name = None
            ext_comp = None

        cursor.execute("""
            INSERT INTO TrainingSessions 
            (CourseID, SessionDate, EndDate, Location, IsExternal, InstructorID, ExternalTrainerName, ExternalCompany, EventType, MaxCapacity) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 20)
        """, (course_id, start_date, end_date, location, is_external, instructor_id, ext_name, ext_comp, event_type))
        
        conn.commit()
        flash('✅ تم جدولة التدريب بنجاح', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('training_calendar'))


@app.route('/training/grade', methods=['POST'])
@login_required
def training_grade():
    enrollment_id = request.form['enrollment_id']
    grade = request.form['grade']
    feedback = request.form['feedback']
    
    status = 'Passed' if float(grade) >= 50 else 'Failed'
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE TrainingEnrollments 
        SET Grade = ?, PassStatus = ?, InstructorFeedback = ?, AttendanceStatus = 'Present'
        WHERE EnrollmentID = ?
    """, (grade, status, feedback, enrollment_id))
    conn.commit()
    conn.close()
    return redirect(request.referrer)

@app.route('/training/course/edit/<int:cid>', methods=['GET', 'POST'])
@login_required
def training_course_edit(cid):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        title = request.form.get('title')
        desc = request.form.get('description')
        
        # Get Department ID
        dept_id = request.form.get('department')
        dept_id = int(dept_id) if dept_id else None

        duration = request.form.get('duration') or None
        diff = request.form.get('difficulty') or None
        is_active = 1 if request.form.get('is_active') else 0
        
        # UPDATE AppliesToDeptID
        cursor.execute("""
            UPDATE TrainingCourses
            SET TrainingCourseText=?, Description=?, AppliesToDeptID=?, 
                DurationHours=?, Difficulty=?, IsActive=?
            WHERE TrainingCourseID=?
        """, (title, desc, dept_id, duration, diff, is_active, cid))
        conn.commit()
        conn.close()
        
        flash("✅ تم تحديث الدورة بنجاح", "success")
        return redirect(url_for('training_courses'))

    cursor.execute("SELECT * FROM TrainingCourses WHERE TrainingCourseID = ?", (cid,))
    course = cursor.fetchone()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM DEPARTMENTS ORDER BY DEPTNAME")
    depts = cursor.fetchall()
    conn.close()
    
    return render_template('course_form.html', action="تعديل", depts=depts, course=course)

@app.route('/training/course/delete/<int:cid>', methods=['POST'])
@login_required
def training_course_delete(cid):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check usage before delete
        cursor.execute("SELECT COUNT(*) as cnt FROM Evaluations WHERE TrainingCourseID = ?", (cid,))
        if cursor.fetchone().cnt > 0:
             flash('❌ لا يمكن حذف دورة مستخدمة في تقييمات سابقة.', 'danger')
        else:
            cursor.execute("DELETE FROM TrainingCourses WHERE TrainingCourseID = ?", (cid,))
            conn.commit()
            flash("✅ تم حذف الدورة", "success")
    except Exception as e:
        conn.rollback()
        flash(f"❌ حدث خطأ: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('training_courses')) # Redirects to the list


@app.route('/training/session/<int:sid>/print')
@login_required
def training_session_print(sid):
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Session Info
    cursor.execute("""
        SELECT S.*, C.TrainingCourseText 
        FROM TrainingSessions S
        LEFT JOIN TrainingCourses C ON S.CourseID = C.TrainingCourseID
        WHERE SessionID = ?
    """, (sid,))
    session_data = cursor.fetchone()

    if not session_data:
        flash("الجلسة غير موجودة.", "danger")
        conn.close()
        return redirect(url_for('training_sessions'))

    # 2. Trainer Names (دعم متعدد المدربين + خارجي)
    trainer_display = ""
    if session_data.IsExternal:
        trainer_display = session_data.ExternalTrainerName or "مدرب خارجي"
        if session_data.ExternalCompany:
            trainer_display += f" - {session_data.ExternalCompany}"
    else:
        if session_data.InstructorID:
            try:
                instructor_ids = [int(x.strip()) for x in session_data.InstructorID.split(',') if x.strip()]
                if instructor_ids:
                    placeholders = ','.join(['?'] * len(instructor_ids))
                    cursor.execute(f"SELECT NAME FROM USERINFO WHERE USERID IN ({placeholders}) ORDER BY NAME", instructor_ids)
                    names = [row.NAME for row in cursor.fetchall()]
                    trainer_display = "، ".join(names)
                else:
                    trainer_display = "غير محدد"
            except:
                trainer_display = "خطأ في بيانات المدربين"
        else:
            trainer_display = "غير محدد"

    # 3. Enrollments
    cursor.execute("""
        SELECT E.EnrollmentID, UI.NAME, UI.BADGENUMBER, D.DEPTNAME
        FROM TrainingEnrollments E
        LEFT JOIN USERINFO UI ON E.EmployeeUserID = UI.USERID
        LEFT JOIN DEPARTMENTS D ON UI.DEFAULTDEPTID = D.DEPTID
        WHERE E.SessionID = ?
        ORDER BY UI.Name
    """, (sid,))
    enrollments = cursor.fetchall()

    conn.close()

    # === أضف التاريخ الحالي ===
    print_date = datetime.now().strftime('%d/%m/%Y')

    return render_template('training_print.html', 
                           training_session=session_data,
                           trainer_display=trainer_display,
                           enrollments=enrollments,
                           print_date=print_date)  # ← مرّر التاريخ هنا

@app.route('/training_courses/add', methods=['GET', 'POST'])
@login_required
def training_courses_add():
    conn = get_db_connection(); cursor = conn.cursor()  
    cursor.execute("SELECT DEPTID, DEPTNAME FROM DEPARTMENTS ORDER BY DEPTID"); depts = cursor.fetchall()
    if request.method == 'POST':
        text = request.form['text']; dept_id = request.form.get('dept_id') or None
        cursor.execute("INSERT INTO TrainingCourses (TrainingCourseText, AppliesToDeptID) VALUES (?, ?)", (text, dept_id)); conn.commit(); conn.close()
        return redirect(url_for('training_courses_list'))
    conn.close()
    return render_template('training_course_form.html', departments=depts, action='Add')

@app.route('/training/session/delete/<int:sid>', methods=['POST'])
@login_required  # فقط الـ Admin يقدر يحذف
def training_session_delete(sid):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # حذف الجلسة (الحذف المتسلسل cascade هيحذف الأيام والحضور والتسجيلات تلقائيًا إذا كانت الـ FK مظبوطة)
        cursor.execute("DELETE FROM TrainingSessions WHERE SessionID = ?", (sid,))
        
        if cursor.rowcount == 0:
            flash("❌ الجلسة غير موجودة أو تم حذفها مسبقًا", "danger")
        else:
            conn.commit()
            flash("✅ تم حذف الجلسة التدريبية بنجاح مع كل البيانات المرتبطة", "success")
    except Exception as e:
        conn.rollback()
        flash(f"❌ حدث خطأ أثناء الحذف: {e}", "danger")
        print(f"Delete Session Error: {e}")
    finally:
        conn.close()
    
    return redirect(url_for('training_sessions'))

@app.route('/training_courses')
@login_required
def training_courses_list():
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("SELECT TC.TrainingCourseID, TC.TrainingCourseText, D.DEPTNAME FROM TrainingCourses TC LEFT JOIN DEPARTMENTS D ON TC.AppliesToDeptID = D.DEPTID"); rows = cursor.fetchall(); conn.close()
    return render_template('training_courses_list.html', courses=rows)

# ===================== MANUAL TRAINING HISTORY ENTRY =====================

@app.route('/training/manual_history', methods=['GET', 'POST'])
@login_required
def training_manual_history():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        try:
            user_id = request.form['user_id']
            course_id = request.form['course_id']
            date = request.form['date']
            grade = request.form.get('grade') or None
            feedback = request.form.get('feedback') or 'Legacy Data'
            
            # 1. Create a "Ghost" Session for this past record
            # We mark it as 'Completed' and 'Legacy' so it doesn't clutter the main calendar too much
            cursor.execute("""
                INSERT INTO TrainingSessions 
                (CourseID, SessionDate, Location, Status, MaxCapacity, IsExternal, EventType)
                VALUES (?, ?, 'Historical Record', 'Completed', 1, 0, 'History')
            """, (course_id, date))
            
            # Get the ID of the session we just created
            cursor.execute("SELECT @@IDENTITY")
            session_id = cursor.fetchone()[0]

            # 2. Enroll the employee immediately
            status = 'Passed' if grade and float(grade) >= 50 else 'Completed'
            
            cursor.execute("""
                INSERT INTO TrainingEnrollments 
                (SessionID, EmployeeUserID, AttendanceStatus, Grade, PassStatus, InstructorFeedback)
                VALUES (?, ?, 'Present', ?, ?, ?)
            """, (session_id, user_id, grade, status, feedback))
            
            conn.commit()
            flash('✅ تم إضافة السجل التاريخي بنجاح', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'❌ حدث خطأ: {e}', 'danger')
        finally:
            conn.close()
            
        return redirect(url_for('training_manual_history'))

    # GET: Fetch dropdown data
    cursor.execute("SELECT USERID, NAME FROM USERINFO WHERE IsActive = 1 ORDER BY NAME")
    employees = cursor.fetchall()
    
    cursor.execute("SELECT TrainingCourseID, TrainingCourseText FROM TrainingCourses ORDER BY TrainingCourseText")
    courses = cursor.fetchall()
    
    conn.close()
    return render_template('training_manual_history.html', employees=employees, courses=courses)


# =========================================
# SUB-SESSIONS (DAILY SCHEDULE) LOGIC
# =========================================
@app.route('/training/day/add/<int:sid>', methods=['POST'])
@login_required
def training_day_add(sid):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        day_date = request.form.get('day_date')
        
        # --- 🛡️ SAFETY CHECK (New) ---
        # Blocks dates starting with '00' (like 0025) to prevent crashes
        if not day_date or str(day_date).startswith('00'):
            flash("❌ خطأ: التاريخ غير صحيح. يرجى التأكد من السنة (مثلاً 2025).", "danger")
            return redirect(url_for('training_session_detail', sid=sid))

        # --- Handle Empty Time Fields (Convert "" to None) ---
        start_time = request.form.get('start_time')
        if not start_time: start_time = None
        
        end_time = request.form.get('end_time')
        if not end_time: end_time = None
        
        topic = request.form.get('topic')

        # --- Insert Data ---
        cursor.execute("INSERT INTO TrainingSessionDays (SessionID, DayDate, StartTime, EndTime, Topic) VALUES (?, ?, ?, ?, ?)", 
                       (sid, day_date, start_time, end_time, topic))
        conn.commit()
        flash("✅ تم إضافة اليوم للجدول بنجاح", "success")

    except Exception as e:
        conn.rollback()
        flash(f"❌ خطأ أثناء الحفظ: {e}", "danger")
    finally:
        conn.close()
    
    # --- Correct Redirect ---
    return redirect(url_for('training_session_detail', sid=sid))







@app.route('/training/day/delete/<int:did>', methods=['POST'])
@login_required
def training_day_delete(did):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM TrainingSessionDays WHERE DayID = ?", (did,))
        conn.commit()
        flash("✅ تم حذف اليوم من الجدول", "success")
    except Exception as e:
        flash(f"❌ خطأ: {e}", "danger")
    finally:
        conn.close()
    return redirect(request.referrer)

@app.route('/training/attendance/save/<int:sid>', methods=['POST'])
@login_required
def training_attendance_save(sid):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. احذف كل سجلات الحضور السابقة لهذه الجلسة (لنبدأ من الصفر)
        cursor.execute("DELETE FROM TrainingAttendance WHERE SessionID = ?", (sid,))

        # 2. جلب عدد الأيام المجدولة لهذه الجلسة (للحساب لاحقًا)
        cursor.execute("SELECT COUNT(*) FROM TrainingSessionDays WHERE SessionID = ?", (sid,))
        total_days = cursor.fetchone()[0]

        # 3. معالجة الـ checkboxes المرسلة
        attendance_count = {}  # {EnrollmentID: عدد الأيام الحاضر فيها}

        for key in request.form:
            if key.startswith('attend_'):
                # التنسيق: attend_{DayID}_{EnrollmentID}
                parts = key.split('_')[1:]
                if len(parts) == 2:
                    try:
                        day_id = int(parts[0])
                        enrollment_id = int(parts[1])

                        # إضافة السجل في جدول الحضور
                        cursor.execute("""
                            INSERT INTO TrainingAttendance (SessionID, DayID, EnrollmentID)
                            VALUES (?, ?, ?)
                        """, (sid, day_id, enrollment_id))

                        # عدّ الأيام الحاضرة لكل موظف
                        attendance_count[enrollment_id] = attendance_count.get(enrollment_id, 0) + 1

                    except ValueError:
                        continue  # تجاهل أي قيم غير صالحة

        # 4. تحديث نسبة الحضور في جدول TrainingEnrollments
        if total_days > 0:
            for enrollment_id, present_days in attendance_count.items():
                percent = round((present_days / total_days) * 100, 1)
                cursor.execute("""
                    UPDATE TrainingEnrollments
                    SET AttendancePercent = ?
                    WHERE EnrollmentID = ? AND SessionID = ?
                """, (percent, enrollment_id, sid))
        else:
            # إذا لم تكن هناك أيام مجدولة، اجعل النسبة 0
            cursor.execute("""
                UPDATE TrainingEnrollments
                SET AttendancePercent = 0
                WHERE SessionID = ?
            """, (sid,))

        conn.commit()
        flash("✅ تم حفظ الحضور وتحديث نسب الحضور بنجاح", "success")

    except Exception as e:
        conn.rollback()
        print(f"Error saving attendance: {e}")
        flash("❌ حدث خطأ أثناء حفظ الحضور", "danger")

    finally:
        conn.close()

    return redirect(url_for('training_session_detail', sid=sid))

# ========================================================

@app.route('/debug/userinfo')
def debug_userinfo():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime_Copy].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    departments = cursor.fetchall()
    result = f"<h1>UserInfo Debug</h1><h2>Departments Query Result:</h2><p>Found {len(departments)} departments:</p><table border='1'><tr><th>DEPTID</th><th>DEPTNAME</th></tr>"
    for dept in departments: result += f"<tr><td>{dept.DEPTID}</td><td>{dept.DEPTNAME}</td></tr>"
    result += "</table>"
    from flask import render_template_string
    template_test = "<h2>Template Test:</h2>Departments count: {{ departments|length }}{% for dept in departments %}Dept: {{ dept.DEPTID }} - {{ dept.DEPTNAME }}<br>{% endfor %}"
    rendered = render_template_string(template_test, departments=departments)
    result += rendered
    conn.close()
    return result


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# =========================================
# TRAINING COURSES (ADMIN ONLY)
# =========================================

@app.route('/training/courses')
@training_required
def training_courses():
    conn = get_db_connection()
    cursor = conn.cursor()
    # ADDED: WHERE TC.IsActive = 1
    cursor.execute("""
        SELECT TC.TrainingCourseID, TC.TrainingCourseText, TC.Description, 
               TC.DepartmentID, TC.DurationHours, TC.Difficulty, TC.IsActive,
               D.DEPTNAME
        FROM TrainingCourses TC
        LEFT JOIN DEPARTMENTS D ON TC.DepartmentID = D.DEPTID
        WHERE TC.IsActive = 1
        ORDER BY TC.TrainingCourseText
    """)
    courses = cursor.fetchall()
    conn.close()
    return render_template('courses_list.html', courses=courses)

# =========================================
# 2. Archive List (Stopped Only)
# =========================================
@app.route('/training/courses/archive')
@training_required
def training_courses_archive():
    conn = get_db_connection()
    cursor = conn.cursor()
    # ADDED: WHERE TC.IsActive = 0 OR TC.IsActive IS NULL
    cursor.execute("""
        SELECT TC.TrainingCourseID, TC.TrainingCourseText, TC.Description, 
               TC.DepartmentID, TC.DurationHours, TC.Difficulty, TC.IsActive,
               D.DEPTNAME
        FROM TrainingCourses TC
        LEFT JOIN DEPARTMENTS D ON TC.DepartmentID = D.DEPTID
        WHERE TC.IsActive = 0 OR TC.IsActive IS NULL
        ORDER BY TC.TrainingCourseText
    """)
    courses = cursor.fetchall()
    conn.close()
    return render_template('courses_archive.html', courses=courses)


@app.route('/training/course/add', methods=['GET', 'POST'])
@training_required
def training_course_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        title = request.form.get('title')
        desc = request.form.get('description')
        
        # Get Department ID (Handle empty value as None for "General")
        dept_id = request.form.get('department')
        dept_id = int(dept_id) if dept_id else None 

        duration = request.form.get('duration') or None
        diff = request.form.get('difficulty') or None
        is_active = 1 if request.form.get('is_active') else 0
        
        # SAVE TO AppliesToDeptID
        cursor.execute("""
            INSERT INTO TrainingCourses
            (TrainingCourseText, Description, AppliesToDeptID, DurationHours, Difficulty, IsActive, CreatedBy)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, desc, dept_id, duration, diff, is_active, session.get('user_id')))
        conn.commit()
        conn.close()
        
        flash("✅ تم إضافة الدورة بنجاح", "success")
        return redirect(url_for('training_courses'))

    cursor.execute("SELECT DEPTID, DEPTNAME FROM DEPARTMENTS ORDER BY DEPTNAME")
    depts = cursor.fetchall()
    conn.close()
    
    return render_template('course_form.html', action="إضافة", depts=depts, course=None)

# =========================================
# TRAINING SESSIONS (ADMIN ONLY)
# =========================================

@app.route('/training/sessions')
@training_required
def training_sessions():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT S.SessionID, C.TrainingCourseText, S.SessionDate, S.EndDate,
               S.Location, S.InstructorID, S.IsExternal,
               S.ExternalTrainerName, S.MaxSeats
        FROM TrainingSessions S
        LEFT JOIN TrainingCourses C ON S.CourseID = C.TrainingCourseID
        ORDER BY S.SessionDate DESC
    """)
    sessions = cursor.fetchall()
    conn.close()
    return render_template('sessions_list.html', sessions=sessions)

@app.route('/training/employee_report')
@login_required
def training_employee_report():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Get Filters from URL
    search = request.args.get('search', '').strip()
    dept_id = request.args.get('dept_id')
    course_id = request.args.get('course_id')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    # 2. Build Query
    # We start with USERINFO so we can see employees even if they have no training (optional, but good for reports)
    # If a specific course/date filter is applied, we switch to inner join logic implicitly by the WHERE clause
    
    query = """
        SELECT 
            U.USERID, U.BADGENUMBER, U.NAME, U.TITLE, U.pic, 
            D.DEPTNAME,
            TE.EnrollmentID, TE.PassStatus, TE.Grade, TE.AttendanceStatus,
            TS.SessionDate, TS.SessionID,
            TC.TrainingCourseText
        FROM [Zktime_Copy].[dbo].[USERINFO] U
        LEFT JOIN [Zktime_Copy].[dbo].[DEPARTMENTS] D ON U.DEFAULTDEPTID = D.DEPTID
        LEFT JOIN [Zktime_Copy].[dbo].[TrainingEnrollments] TE ON U.USERID = TE.EmployeeUserID
        LEFT JOIN [Zktime_Copy].[dbo].[TrainingSessions] TS ON TE.SessionID = TS.SessionID
        LEFT JOIN [Zktime_Copy].[dbo].[TrainingCourses] TC ON TS.CourseID = TC.TrainingCourseID
        WHERE U.IsActive = 1
    """
    
    params = []
    
    # Apply Filters
    if search:
        query += " AND (U.NAME LIKE ? OR U.BADGENUMBER LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    
    if dept_id:
        query += " AND U.DEFAULTDEPTID = ?"
        params.append(dept_id)
        
    # For Course/Date filters, we filter the *Trainings*. 
    # Note: This might exclude employees who didn't take that specific course.
    if course_id:
        query += " AND TS.CourseID = ?"
        params.append(course_id)
        
    if date_from:
        query += " AND TS.SessionDate >= ?"
        params.append(date_from)
        
    if date_to:
        query += " AND TS.SessionDate <= ?"
        params.append(date_to)

    query += " ORDER BY U.NAME, TS.SessionDate DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    # 3. Process Data into a Structured Dictionary
    # Structure: employees[user_id] = { 'info': user_obj, 'courses': [list_of_courses] }
    
    employees = defaultdict(lambda: {'info': None, 'courses': [], 'stats': {'total': 0, 'passed': 0, 'failed': 0}})
    
    for row in rows:
        uid = row.USERID
        
        # Set User Info (only needs to be done once per user, but doing it every loop is safe/fast enough)
        if employees[uid]['info'] is None:
            employees[uid]['info'] = {
                'id': row.USERID,
                'badge': row.BADGENUMBER,
                'name': row.NAME,
                'title': row.TITLE,
                'dept': row.DEPTNAME,
                'has_pic': True if row.pic else False
            }
        
        # Add Course Detail (only if enrollment exists)
        if row.EnrollmentID:
            employees[uid]['courses'].append({
                'course_name': row.TrainingCourseText,
                'date': row.SessionDate,
                'status': row.PassStatus,
                'grade': row.Grade,
                'attendance': row.AttendanceStatus
            })
            
            # Update Stats
            employees[uid]['stats']['total'] += 1
            if row.PassStatus == 'Passed':
                employees[uid]['stats']['passed'] += 1
            elif row.PassStatus == 'Failed':
                employees[uid]['stats']['failed'] += 1

    # 4. Get Dropdown Data
    cursor.execute("SELECT DEPTID, DEPTNAME FROM DEPARTMENTS ORDER BY DEPTNAME")
    all_depts = cursor.fetchall()
    
    cursor.execute("SELECT TrainingCourseID, TrainingCourseText FROM TrainingCourses ORDER BY TrainingCourseText")
    all_courses = cursor.fetchall()

    conn.close()

    return render_template('training_employee_report.html', 
                           employees=employees, 
                           all_depts=all_depts, 
                           all_courses=all_courses,
                           filters=request.args)

@app.route('/training/session/edit/<int:sid>', methods=['GET', 'POST'])
@training_required
def training_session_edit(sid):
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        course_id = request.form.get('course_id')
        session_date = request.form.get('session_date')
        end_date = request.form.get('end_date') or None
        location = request.form.get('location')
        instructor = request.form.get('instructor') or None
        is_external = 1 if request.form.get('is_external') else 0
        ext_name = request.form.get('external_name')
        ext_company = request.form.get('external_company')
        max_seats = request.form.get('max_seats') or None

        cursor.execute("""
            UPDATE TrainingSessions
            SET CourseID=?, SessionDate=?, EndDate=?, Location=?, InstructorID=?,
                IsExternal=?, ExternalTrainerName=?, ExternalCompany=?, MaxSeats=?
            WHERE SessionID=?
        """, (course_id, session_date, end_date, location, instructor,
              is_external, ext_name, ext_company, max_seats, sid))
        conn.commit()
        conn.close()
        flash("✅ تم تحديث بيانات الجلسة", "success")
        return redirect(url_for('training_sessions'))

    # --- GET REQUEST (Updated to match Add Screen) ---

    # 1. Get Session Data
    cursor.execute("SELECT * FROM TrainingSessions WHERE SessionID = ?", (sid,))
    s_obj = cursor.fetchone()
    
    # 2. Get Courses
    cursor.execute("SELECT TrainingCourseID, TrainingCourseText FROM TrainingCourses WHERE IsActive = 1")
    courses = cursor.fetchall()

    # 3. Get Departments (For Filter)
    cursor.execute("SELECT DEPTID, DEPTNAME FROM DEPARTMENTS ORDER BY DEPTNAME")
    depts = cursor.fetchall()

    # 4. Get Instructors (With Department ID for filtering)
    cursor.execute("SELECT USERID, NAME, DEFAULTDEPTID FROM USERINFO WHERE IsActive = 1 ORDER BY NAME")
    instructors = cursor.fetchall()
    
    conn.close()

    return render_template('training_session_detail.html', action="تعديل", 
                           courses=courses, 
                           depts=depts,             # <--- Now passing departments
                           instructors=instructors, # <--- Now passing rich user data
                           training_session=s_obj)


@app.route('/training/session/add', methods=['GET', 'POST'])
@training_required
def training_session_add():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        course_id = request.form.get('course_id')
        session_date = request.form.get('session_date')
        end_date = request.form.get('end_date') or None
        location = request.form.get('location')
        
        # Multiple instructors
        instructor_ids = request.form.getlist('instructors[]')
        instructor_csv = ','.join(instructor_ids) if instructor_ids else None
        
        is_external = 1 if request.form.get('is_external') else 0
        ext_name = request.form.get('external_name') if is_external else None
        ext_company = request.form.get('external_company') if is_external else None
        max_seats = request.form.get('max_seats') or None
        
        cursor.execute("""
            INSERT INTO TrainingSessions
            (CourseID, SessionDate, EndDate, Location, InstructorID, IsExternal,
             ExternalTrainerName, ExternalCompany, MaxSeats)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (course_id, session_date, end_date, location, instructor_csv,
              is_external, ext_name, ext_company, max_seats))
        
        conn.commit()
        conn.close()

        flash("✅ تم إنشاء الجلسة بنجاح.", "success")
        return redirect(url_for('training_sessions'))

    # GET: Load dropdown data
    cursor.execute("SELECT TrainingCourseID, TrainingCourseText FROM TrainingCourses WHERE IsActive = 1")
    courses = cursor.fetchall()

    cursor.execute("SELECT DEPTID, DEPTNAME FROM DEPARTMENTS ORDER BY DEPTNAME")
    depts = cursor.fetchall()

    # === CHANGED: Include ALL employees (active and inactive) ===
    cursor.execute("""
        SELECT u.USERID, u.NAME, u.DEFAULTDEPTID, d.DEPTNAME, u.IsActive
        FROM USERINFO u 
        LEFT JOIN DEPARTMENTS d ON u.DEFAULTDEPTID = d.DEPTID 
        ORDER BY u.NAME
    """)
    instructors = cursor.fetchall()

    conn.close()

    return render_template('session_form.html',
                           action="إضافة",
                           courses=courses,
                           depts=depts,
                           instructors=instructors,
                           training_session=None,
                           selected_instructor_ids=[])

# =========================================
# TRAINING ENROLLMENTS (ADMIN + MANAGER)
# =========================================


@app.route('/training/session/<int:sid>', methods=['GET', 'POST'])
@training_required
def training_session_detail(sid):
    conn = get_db_connection()
    cursor = conn.cursor()

    # ========================
    # 1. HANDLE POST ACTIONS
    # ========================
    if request.method == 'POST':
        # A. Auto Enroll
        if 'auto_enroll' in request.form:
            cursor.execute("SELECT CourseID, MaxCapacity FROM TrainingSessions WHERE SessionID = ?", (sid,))
            session_info = cursor.fetchone()
            if session_info:
                course_id = session_info.CourseID
                max_cap = session_info.MaxCapacity
                
                cursor.execute("SELECT COUNT(*) FROM TrainingEnrollments WHERE SessionID = ? AND PassStatus != 'Canceled'", (sid,))
                current_count = cursor.fetchone()[0]
                
                cursor.execute("""
                    SELECT DISTINCT E.EmployeeUserID 
                    FROM Evaluations E 
                    WHERE E.TrainingCourseID = ? 
                    AND E.EmployeeUserID NOT IN (
                        SELECT TE.EmployeeUserID FROM TrainingEnrollments TE 
                        JOIN TrainingSessions TS ON TE.SessionID = TS.SessionID 
                        WHERE TS.CourseID = ? AND TE.PassStatus != 'Canceled'
                    )
                """, (course_id, course_id))
                candidates = cursor.fetchall()
                
                for cand in candidates:
                    status = 'Registered' if current_count < max_cap else 'Waitlist'
                    if status == 'Registered': current_count += 1
                    cursor.execute("INSERT INTO TrainingEnrollments (SessionID, EmployeeUserID, AttendanceStatus, PassStatus) VALUES (?, ?, ?, 'Registered')", (sid, cand.EmployeeUserID, status))
                
                conn.commit()
                flash('✅ تم سحب المرشحين بنجاح', 'info')

        # B. Manual Enroll
        elif 'manual_enroll' in request.form:
             user_id = request.form.get('user_id')
             if user_id:
                 cursor.execute("INSERT INTO TrainingEnrollments (SessionID, EmployeeUserID, AttendanceStatus, PassStatus) VALUES (?, ?, 'Registered', 'Registered')", (sid, user_id))
                 conn.commit()
                 flash('✅ تم إضافة الموظف بنجاح', 'success')

        # C. Mark Attendance (Quick Actions)
        elif 'mark_attendance' in request.form:
            eid = request.form.get('enrollment_id')
            status = request.form.get('status')
            if eid and status:
                cursor.execute("UPDATE TrainingEnrollments SET AttendanceStatus = ? WHERE EnrollmentID = ?", (status, eid))
                conn.commit()
                flash('✅ تم تحديث الحضور', 'success')
        
        conn.close()
        return redirect(url_for('training_session_detail', sid=sid))

    # ========================
    # 2. GET: Fetch Session Data
    # ========================
    cursor.execute("""
        SELECT S.*, TC.TrainingCourseText
        FROM TrainingSessions S
        LEFT JOIN TrainingCourses TC ON S.CourseID = TC.TrainingCourseID
        WHERE S.SessionID = ?
    """, (sid,))
    training_session = cursor.fetchone()

    if not training_session:
        flash("❌ الجلسة غير موجودة.", "danger")
        conn.close()
        return redirect(url_for('training_sessions'))

    # جلب أسماء المدربين الداخليين يدويًا (يدعم متعدد المدربين)
    instructor_names = []
    if training_session.InstructorID:
        try:
            instructor_ids = [int(x.strip()) for x in training_session.InstructorID.split(',') if x.strip()]
            if instructor_ids:
                placeholders = ','.join(['?'] * len(instructor_ids))
                cursor.execute(f"SELECT NAME FROM USERINFO WHERE USERID IN ({placeholders}) ORDER BY NAME", instructor_ids)
                instructor_names = [row.NAME for row in cursor.fetchall()]
        except:
            instructor_names = ["خطأ في قراءة المدربين"]

    # جلب الأيام
    cursor.execute("SELECT * FROM TrainingSessionDays WHERE SessionID = ? ORDER BY DayDate", (sid,))
    session_days = cursor.fetchall()

    # جلب التسجيلات مع استبعاد الملغاة (Canceled)
    # جلب التسجيلات مع استبعاد الملغاة (Canceled)
    cursor.execute("""
        SELECT TE.*, UI.NAME, UI.BADGENUMBER, D.DEPTNAME
        FROM TrainingEnrollments TE
        LEFT JOIN USERINFO UI ON TE.EmployeeUserID = UI.USERID
        LEFT JOIN DEPARTMENTS D ON UI.DEFAULTDEPTID = D.DEPTID
        WHERE TE.SessionID = ? AND (TE.PassStatus IS NULL OR TE.PassStatus != 'Canceled')
        ORDER BY UI.NAME
    """, (sid,))
    enrollments = cursor.fetchall()

    # جلب الحضور فقط للتسجيلات النشطة (غير الملغاة)
    # جلب الحضور فقط للتسجيلات النشطة
    cursor.execute("""
        SELECT TA.DayID, TA.EnrollmentID 
        FROM TrainingAttendance TA
        JOIN TrainingEnrollments TE ON TA.EnrollmentID = TE.EnrollmentID
        WHERE TA.SessionID = ? AND (TE.PassStatus IS NULL OR TE.PassStatus != 'Canceled')
    """, (sid,))
    attendance_set = {(row.DayID, row.EnrollmentID) for row in cursor.fetchall()}

    # جلب كل الموظفين للإضافة اليدوية
    cursor.execute("SELECT USERID, NAME FROM USERINFO WHERE IsActive = 1 ORDER BY NAME")
    all_employees = cursor.fetchall()

    conn.close()

    return render_template('training_session_detail.html',
                           training_session=training_session,
                           instructor_names=instructor_names,
                           session_days=session_days,
                           enrollments=enrollments,
                           attendance_set=attendance_set,
                           all_employees=all_employees)

@app.route('/training/enrollment/cancel/<int:eid>', methods=['POST'])
@training_required
def training_enrollment_cancel(eid):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Safe Delete: Mark as Canceled instead of DELETE
        # This preserves the record for history but hides it from the active session list
        cursor.execute("""
            UPDATE TrainingEnrollments 
            SET PassStatus = 'Canceled', 
                AttendanceStatus = 'Excused',
                Grade = NULL
            WHERE EnrollmentID = ?
        """, (eid,))
        
        conn.commit()
        flash("✅ تم إلغاء تسجيل الموظف بنجاح (تم حفظه في الأرشيف كـ ملغى)", "success")
        
    except Exception as e:
        conn.rollback()
        flash(f"❌ حدث خطأ: {e}", "danger")
    finally:
        conn.close()
    
    # Return to the same page
    return redirect(request.referrer)


@app.route('/training/session/<int:sid>/enroll', methods=['GET', 'POST'])
@training_required
def training_enroll(sid):
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        employee_ids = request.form.getlist('employee_ids')
        count = 0
        for emp_id in employee_ids:
            try:
                emp_id = int(emp_id)
                # Check if already enrolled
                cursor.execute("SELECT COUNT(*) FROM TrainingEnrollments WHERE SessionID=? AND EmployeeUserID=?", (sid, emp_id))
                if cursor.fetchone()[0] == 0:
                    cursor.execute("INSERT INTO TrainingEnrollments (EmployeeUserID, SessionID, AttendanceStatus) VALUES (?, ?, 'Registered')", (emp_id, sid))
                    count += 1
            except Exception as e:
                print(f"Error enrolling {emp_id}: {e}")
        
        conn.commit()
        conn.close()
        if count > 0:
            flash(f"✅ تم تسجيل {count} موظف بنجاح", "success")
        else:
            flash("⚠️ لم يتم تسجيل أي موظف جديد (ربما مسجلين بالفعل)", "warning")
        return redirect(url_for('training_enroll', sid=sid))

    # --- GET REQUEST ---
    role_id = session.get('role_id')
    manager_id = session.get('user_id')

    # 1. Get Session & Course Info (To find recommendations)
    cursor.execute("SELECT CourseID, MaxCapacity FROM TrainingSessions WHERE SessionID = ?", (sid,))
    session_info = cursor.fetchone()
    recommended_ids = []
    
    if session_info:
        course_id = session_info.CourseID
        # Find employees recommended for this SPECIFIC course
        cursor.execute("""
            SELECT DISTINCT EmployeeUserID 
            FROM Evaluations 
            WHERE TrainingCourseID = ?
        """, (course_id,))
        recommended_ids = [row.EmployeeUserID for row in cursor.fetchall()]

    # 2. Get Departments
    if role_id == 1 or role_id == 6:
        cursor.execute("SELECT DEPTID, DEPTNAME FROM DEPARTMENTS ORDER BY DEPTNAME")
    else:
        cursor.execute("SELECT DepartmentID FROM Users WHERE UserID = ?", (manager_id,))
        dept_row = cursor.fetchone()
        if dept_row and dept_row.DepartmentID:
            cursor.execute("SELECT DEPTID, DEPTNAME FROM DEPARTMENTS WHERE DEPTID = ?", (dept_row.DepartmentID,))
        else:
            cursor.execute("SELECT DEPTID, DEPTNAME FROM DEPARTMENTS WHERE 1=0")
    
    depts = cursor.fetchall()

    # 3. Get Employees (Not yet enrolled in this session)
    if role_id == 1 or role_id == 6:
        cursor.execute("""
            SELECT u.USERID, u.NAME, COALESCE(u.DEFAULTDEPTID, 0) AS DEFAULTDEPTID, u.IsActive
            FROM USERINFO u
            LEFT JOIN TrainingEnrollments te ON u.USERID = te.EmployeeUserID AND te.SessionID = ?
            WHERE te.EnrollmentID IS NULL
            ORDER BY u.NAME
        """, (sid,))
    else:
        cursor.execute("SELECT DepartmentID FROM Users WHERE UserID = ?", (manager_id,))
        dept_row = cursor.fetchone()
        if dept_row and dept_row.DepartmentID:
            cursor.execute("""
                SELECT u.USERID, u.NAME, u.DEFAULTDEPTID, u.IsActive
                FROM USERINFO u
                LEFT JOIN TrainingEnrollments te ON u.USERID = te.EmployeeUserID AND te.SessionID = ?
                WHERE u.DEFAULTDEPTID = ? AND te.EnrollmentID IS NULL
                ORDER BY u.NAME
            """, (sid, dept_row.DepartmentID))
        else:
            cursor.execute("SELECT USERID, NAME, DEFAULTDEPTID, IsActive FROM USERINFO WHERE 1=0")

    employees = cursor.fetchall()
    conn.close()

    # Pass 'recommended_ids' to the template
    # Pass 'recommended_ids' to the template
    return render_template('enroll_form.html', 
                           employees=employees, 
                           depts=depts, 
                           sid=sid, 
                           recommended_ids=recommended_ids,
                           # Now both Admin (1) and Training Manager (6) have full control
                           is_admin=(role_id == 1 or role_id == 6))

@app.route('/training/enrollment/update/<int:eid>', methods=['POST'])
@training_required
def training_enrollment_update(eid):
    # 1. Get form data
    grade = request.form.get('grade')
    if grade == '' or grade is None: 
        grade = None
    else: 
        try: 
            grade = float(grade)
        except ValueError: 
            grade = None

    pass_status = request.form.get('pass_status') or None

    conn = get_db_connection()
    cursor = conn.cursor()

    # ======================================================
    # CRITICAL STEP: Get the SessionID BEFORE doing anything else
    # This ensures we know exactly where to go back to.
    # ======================================================
    cursor.execute("SELECT SessionID FROM TrainingEnrollments WHERE EnrollmentID = ?", (eid,))
    row = cursor.fetchone()
    
    # If the enrollment doesn't exist, we must go to the main list (Safety)
    if not row:
        conn.close()
        flash("❌ لم يتم العثور على سجل الطالب", "danger")
        return redirect(url_for('training_sessions'))

    session_id = row.SessionID

    try:
        # 2. Now attempt the update
        cursor.execute("""
            UPDATE TrainingEnrollments
            SET Grade = ?, PassStatus = ?
            WHERE EnrollmentID = ?
        """, (grade, pass_status, eid))

        conn.commit()
        flash("✅ تم تحديث النتيجة بنجاح", "success")

    except Exception as e:
        conn.rollback()
        # Even if there is an error, we can still go back to the correct page now!
        flash(f"❌ حدث خطأ أثناء التحديث: {e}", "danger")

    finally:
        conn.close()

    # 3. Redirect explicitly to the Session Detail Page
    return redirect(url_for('training_session_detail', sid=session_id))

@app.route('/training/session/<int:sid>/bulk_update_grades', methods=['POST'])
@training_required
def training_session_bulk_update_grades(sid):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Get all enrollment IDs for this session so we know what to look for
    cursor.execute("SELECT EnrollmentID FROM TrainingEnrollments WHERE SessionID = ?", (sid,))
    rows = cursor.fetchall()
    
    try:
        for row in rows:
            eid = row.EnrollmentID
            # We expect inputs named like "grade_101" and "pass_status_101"
            grade_key = f"grade_{eid}"
            status_key = f"pass_status_{eid}"
            
            # Only update if this student is in the submitted form
            if grade_key in request.form:
                raw_grade = request.form.get(grade_key)
                pass_status = request.form.get(status_key) or None
                
                # Safe conversion for Grade
                grade = None
                if raw_grade and raw_grade.strip():
                    try: 
                        grade = float(raw_grade)
                    except ValueError: 
                        grade = None
                
                cursor.execute("""
                    UPDATE TrainingEnrollments
                    SET Grade = ?, PassStatus = ?
                    WHERE EnrollmentID = ?
                """, (grade, pass_status, eid))
                
        conn.commit()
        flash("✅ تم حفظ جميع التغييرات بنجاح", "success")
        
    except Exception as e:
        conn.rollback()
        flash(f"❌ حدث خطأ أثناء الحفظ: {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for('training_session_detail', sid=sid))

@app.route('/training/enrollment/delete/<int:eid>', methods=['POST'])
@training_required
def training_enrollment_delete(eid):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM TrainingEnrollments WHERE EnrollmentID = ?", (eid,))
        conn.commit()
        flash("✅ تم حذف الموظف من الجلسة بنجاح", "success")
    except Exception as e:
        conn.rollback()
        flash(f"❌ حدث خطأ أثناء الحذف: {e}", "danger")
    finally:
        conn.close()
    
    # Return to the same page
    return redirect(request.referrer)

@app.route('/training/history/add', methods=['GET', 'POST'])
@training_required
def training_history_add():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        course_id = request.form.get('course_id')
        date_str = request.form.get('date')
        grade = request.form.get('grade') or None
        feedback = request.form.get('feedback')

        if not user_id or not course_id or not date_str:
            flash("❌ يرجى ملء جميع الحقول المطلوبة", "danger")
        else:
            try:
                # 1. Create a "Fake/Historical" Session for this record
                # We use a special location 'Historical Record' to distinguish it
                cursor.execute("""
                    INSERT INTO TrainingSessions (CourseID, SessionDate, Location, IsExternal, ExternalTrainerName)
                    VALUES (?, ?, 'سجل تاريخي', 1, 'Manual Entry')
                """, (course_id, date_str))
                
                # Get the ID of the session we just made
                cursor.execute("SELECT @@IDENTITY") 
                fake_session_id = cursor.fetchone()[0]

                # 2. Enroll the user in it immediately with 'Passed' status
                cursor.execute("""
                    INSERT INTO TrainingEnrollments (SessionID, EmployeeUserID, Grade, PassStatus, ManagerComments)
                    VALUES (?, ?, ?, 'Passed', ?)
                """, (fake_session_id, user_id, grade, feedback))
                
                conn.commit()
                flash("✅ تم إضافة السجل التاريخي بنجاح", "success")
                return redirect(url_for('training_history_add'))
                
            except Exception as e:
                conn.rollback()
                flash(f"❌ حدث خطأ: {e}", "danger")

    # GET Request: Load data for dropdowns
    cursor.execute("SELECT USERID, NAME FROM USERINFO WHERE IsActive=1 ORDER BY NAME")
    employees = cursor.fetchall()
    
    cursor.execute("SELECT TrainingCourseID, TrainingCourseText FROM TrainingCourses WHERE IsActive=1")
    courses = cursor.fetchall()
    
    conn.close()
    return render_template('training_manual_history.html', employees=employees, courses=courses)

# ========================================================
# 🚀 RECRUITMENT TRACKER (ATS)
# ========================================================

@app.route('/recruitment/analytics')
def recruitment_analytics():
    """ Displays professional charts and stats for recruitment """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Pipeline Stages (Funnel)
    cursor.execute("SELECT Status, COUNT(*) as cnt FROM Candidates GROUP BY Status")
    stage_data = cursor.fetchall()
    
    # 2. Sourcing Channels (Pie Chart)
    cursor.execute("SELECT Source, COUNT(*) as cnt FROM Candidates WHERE Source IS NOT NULL GROUP BY Source")
    source_data = cursor.fetchall()

    # 3. Top Jobs by Applicants (Bar Chart)
    cursor.execute("""
        SELECT TOP 5 J.JobTitle, COUNT(C.CandidateID) as cnt 
        FROM Jobs J 
        LEFT JOIN Candidates C ON J.JobID = C.JobID 
        GROUP BY J.JobTitle 
        ORDER BY cnt DESC
    """)
    job_data = cursor.fetchall()

    # --- NEW: 4. Department Performance (Total vs Hired vs Rejected) ---
    cursor.execute("""
        SELECT 
            COALESCE(D.DEPTNAME, 'General') as DeptName,
            COUNT(C.CandidateID) as Total,
            SUM(CASE WHEN C.Status = 'Hired' THEN 1 ELSE 0 END) as Hired,
            SUM(CASE WHEN C.Status = 'Rejected' THEN 1 ELSE 0 END) as Rejected
        FROM Jobs J
        LEFT JOIN Candidates C ON J.JobID = C.JobID
        LEFT JOIN DEPARTMENTS D ON J.DepartmentID = D.DEPTID
        GROUP BY D.DEPTNAME
    """)
    dept_stats = cursor.fetchall()

    # --- NEW: 5. Recent Rejection Reasons (from Logs) ---
    cursor.execute("""
        SELECT TOP 5 L.Note, J.JobTitle, D.DEPTNAME, L.ActionDate
        FROM CandidateLogs L
        JOIN Candidates C ON L.CandidateID = C.CandidateID
        JOIN Jobs J ON C.JobID = J.JobID
        LEFT JOIN DEPARTMENTS D ON J.DepartmentID = D.DEPTID
        WHERE L.ToStage = 'Rejected' AND L.Note IS NOT NULL
        ORDER BY L.ActionDate DESC
    """)
    rejection_logs = cursor.fetchall()

    # 6. Summary Cards (KPIs)
    cursor.execute("SELECT COUNT(*) FROM Candidates")
    total_candidates = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Jobs WHERE Status = 'Open'")
    open_positions = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Candidates WHERE Status = 'Hired'")
    total_hired = cursor.fetchone()[0]

    conn.close()

    # Convert data to JSON for JavaScript
    analytics = {
        'stages': {'labels': [row.Status for row in stage_data], 'data': [row.cnt for row in stage_data]},
        'sources': {'labels': [row.Source for row in source_data], 'data': [row.cnt for row in source_data]},
        'jobs': {'labels': [row.JobTitle for row in job_data], 'data': [row.cnt for row in job_data]},
        
        # New Data for Department Chart
        'depts': {
            'labels': [row.DeptName for row in dept_stats],
            'total': [row.Total for row in dept_stats],
            'hired': [row.Hired for row in dept_stats],
            'rejected': [row.Rejected for row in dept_stats]
        }
    }

    return render_template('recruitment/recruitment_analytics.html', 
                           analytics=analytics,
                           total_candidates=total_candidates,
                           open_positions=open_positions,
                           total_hired=total_hired,
                           rejection_logs=rejection_logs) # Pass logs to template

@app.route('/recruitment/jobs')
def recruitment_jobs():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT J.*, COALESCE(D.DEPTNAME, 'عام') AS DEPTNAME_DISPLAY, D.DEPTNAME,
               (SELECT COUNT(*) FROM Candidates C WHERE C.JobID = J.JobID) AS TotalCandidates
        FROM Jobs J
        LEFT JOIN DEPARTMENTS D ON J.DepartmentID = D.DEPTID
        ORDER BY J.PostDate DESC
    """)
    jobs = cursor.fetchall()
    
    # Get unique departments safely
    dept_set = {job.DEPTNAME for job in jobs if job.DEPTNAME}
    unique_departments = sorted(dept_set)
    
    conn.close()
    
    return render_template('recruitment/jobs_dashboard.html', 
                           jobs=jobs,
                           unique_departments=unique_departments)


@app.route('/recruitment/job/delete/<int:job_id>', methods=['POST'])
@training_required  # أو أي decorator للتحقق من الصلاحية (مثل @admin_required)
def job_delete(job_id):
    """ Safely delete a job and all its related data """
    conn = get_db_connection()
    cursor = conn.cursor()

    # First, check if the job exists and get its title for the flash message
    cursor.execute("SELECT JobTitle FROM Jobs WHERE JobID = ?", (job_id,))
    job = cursor.fetchone()

    if not job:
        conn.close()
        flash("⚠️ الوظيفة المطلوبة غير موجودة.", "warning")
        return redirect(url_for('recruitment_jobs'))

    job_title = job[0]  # لأن fetchone() يرجع tuple في pyodbc

    def table_exists(table_name):
        """ تحقق لو الجدول موجود في قاعدة البيانات """
        cursor.execute("SELECT COUNT(*) FROM sys.tables WHERE name = ?", (table_name,))
        return cursor.fetchone()[0] > 0

    try:
        # قائمة الجداول الفرعية المحتملة
        related_tables = [
            "Candidates",
            "JobStages",
            "JobApplications",
            # أضف أي جدول تاني لو عايز (مثل Interviews لو موجود)
        ]

        # احذف من كل جدول لو موجود فقط
        for table in related_tables:
            if table_exists(table):
                cursor.execute(f"DELETE FROM {table} WHERE JobID = ?", (job_id,))

        # أخيرًا احذف الوظيفة نفسها (الجدول Jobs لازم يكون موجود دايمًا)
        cursor.execute("DELETE FROM Jobs WHERE JobID = ?", (job_id,))

        conn.commit()
        flash(f"🗑️ تم حذف الوظيفة \"{job_title}\" وجميع بياناتها بنجاح.", "success")
    except Exception as e:
        conn.rollback()
        flash("❌ حدث خطأ أثناء حذف الوظيفة. يرجى المحاولة مرة أخرى.", "danger")
        
        # أضف ده مؤقتًا عشان تشوف الخطأ في الـ console (احذفه بعد الاختبار)
        print("="*60)
        print(f"خطأ في حذف الوظيفة {job_id}: {str(e)}")
        print("="*60)
    finally:
        conn.close()

    return redirect(url_for('recruitment_jobs'))

@app.route('/recruitment/job/<int:job_id>/pipeline')
def job_pipeline(job_id):
    """ The Kanban Board for a specific Job """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get Job Info
    cursor.execute("SELECT * FROM Jobs WHERE JobID = ?", (job_id,))
    job = cursor.fetchone()

    # Get All Candidates with the LATEST Note using a Subquery
    # We also order by Application Date
    cursor.execute("""
        SELECT C.*, 
               (SELECT TOP 1 Note 
                FROM CandidateLogs L 
                WHERE L.CandidateID = C.CandidateID 
                ORDER BY L.ActionDate DESC) AS LastNote
        FROM Candidates C 
        WHERE C.JobID = ?
        ORDER BY C.ApplicationDate DESC
    """, (job_id,))
    candidates = cursor.fetchall()

    # Get OTHER Active Jobs for the transfer dropdown (exclude current job)
    cursor.execute("SELECT JobID, JobTitle FROM Jobs WHERE Status = 'Open' AND JobID != ?", (job_id,))
    other_jobs = cursor.fetchall()

    conn.close()

    # Define Stages
    stages = ['New', 'Screening', 'Interview', 'Training', 'Offer', 'Hired', 'Rejected']
    
    return render_template('recruitment/job_pipeline.html', 
                           job=job, 
                           candidates=candidates, 
                           stages=stages,
                           other_jobs=other_jobs) # Pass active jobs to template

# ... (Place this near your other recruitment routes in app.py) ...

# Inside app.py

@app.route('/recruitment/candidate/edit', methods=['POST'])
def edit_candidate():
    """ Edit candidate personal details including Application Date """
    candidate_id = request.form['candidate_id']
    name = request.form['name']
    phone = request.form['phone']
    email = request.form['email']
    national_id = request.form['national_id']
    source = request.form['source']
    
    # === NEW: Get Application Date ===
    app_date = request.form['application_date']
    # =================================
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # === UPDATED QUERY: Added ApplicationDate = ? ===
        cursor.execute("""
            UPDATE Candidates 
            SET FullName = ?, Phone = ?, Email = ?, NationalID = ?, Source = ?, ApplicationDate = ?
            WHERE CandidateID = ?
        """, (name, phone, email, national_id, source, app_date, candidate_id))
        
        conn.commit()
        flash('✅ تم تحديث بيانات المرشح وتاريخ التقديم بنجاح', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'❌ حدث خطأ أثناء التحديث: {e}', 'danger')
    finally:
        conn.close()
    
    return redirect(request.referrer)

@app.route('/recruitment/candidate/transfer', methods=['POST'])
def transfer_candidate_to_job():
    candidate_id = request.form['candidate_id']
    new_job_id = request.form['new_job_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Get Old Job Title (for logging)
    cursor.execute("""
        SELECT J.JobTitle, C.JobID 
        FROM Candidates C 
        JOIN Jobs J ON C.JobID = J.JobID 
        WHERE C.CandidateID = ?
    """, (candidate_id,))
    row = cursor.fetchone()
    old_job_title = row.JobTitle if row else "Unknown"
    old_job_id = row.JobID

    # 2. Get New Job Title
    cursor.execute("SELECT JobTitle FROM Jobs WHERE JobID = ?", (new_job_id,))
    new_job_title = cursor.fetchone()[0]

    # 3. Update Candidate (Change JobID and reset Status to 'New')
    cursor.execute("""
        UPDATE Candidates 
        SET JobID = ?, Status = 'New' 
        WHERE CandidateID = ?
    """, (new_job_id, candidate_id))

    # 4. Log the transfer
    log_text = f"تم النقل من وظيفة ({old_job_title}) إلى ({new_job_title})"
    cursor.execute("""
        INSERT INTO CandidateLogs (CandidateID, FromStage, ToStage, Note, ActionDate)
        VALUES (?, 'Transfer', 'New', ?, GETDATE())
    """, (candidate_id, log_text))

    conn.commit()
    conn.close()

    flash(f'✅ تم نقل المرشح بنجاح إلى وظيفة {new_job_title}', 'success')
    return redirect(url_for('job_pipeline', job_id=old_job_id))

# Inside app.py

@app.route('/recruitment/candidate/add/<int:job_id>', methods=['POST'])
def add_candidate_to_job(job_id):
    """ Add candidate with National ID Check and Manual Date """
    name = request.form['name']
    phone = request.form['phone']
    email = request.form['email']
    source = request.form['source']
    national_id = request.form['national_id']
    
    # === NEW: Get the date from the form ===
    app_date_str = request.form.get('application_date')
    
    # If for some reason it's empty, fallback to current time
    if not app_date_str:
        app_date = datetime.now()
    else:
        app_date = app_date_str 
    # =======================================
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # --- SMART DUPLICATE CHECK ---
    cursor.execute("""
        SELECT C.FullName, C.Status, J.JobTitle 
        FROM Candidates C
        JOIN Jobs J ON C.JobID = J.JobID
        WHERE C.NationalID = ? OR C.Phone = ?
    """, (national_id, phone))
    
    existing = cursor.fetchone()
    
    if existing:
        msg = f"⚠️ تنبيه: هذا المرشح موجود بالفعل! (الاسم: {existing[0]} - الوظيفة: {existing[2]} - الحالة: {existing[1]})"
        flash(msg, 'warning')
        conn.close()
        return redirect(url_for('job_pipeline', job_id=job_id))

    # --- INSERT (Updated Query) ---
    # Replaced GETDATE() with ? and added app_date to parameters
    cursor.execute("""
        INSERT INTO Candidates (JobID, FullName, Phone, Email, Source, NationalID, Status, ApplicationDate)
        VALUES (?, ?, ?, ?, ?, ?, 'New', ?)
    """, (job_id, name, phone, email, source, national_id, app_date))
    
    conn.commit()
    conn.close()
    
    flash('✅ تم إضافة المرشح بنجاح!', 'success')
    return redirect(url_for('job_pipeline', job_id=job_id))

@app.route('/recruitment/candidate/update_docs', methods=['POST'])
def update_candidate_docs():
    candidate_id = request.form['candidate_id']
    
    # Get Checkbox values (returns '1' if checked, else None)
    doc_birth = 1 if 'doc_birth' in request.form else 0
    doc_degree = 1 if 'doc_degree' in request.form else 0
    doc_military = 1 if 'doc_military' in request.form else 0
    doc_criminal = 1 if 'doc_criminal' in request.form else 0
    doc_photo = 1 if 'doc_photo' in request.form else 0
    doc_id = 1 if 'doc_id' in request.form else 0
    doc_sheet = 1 if 'doc_sheet' in request.form else 0
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE Candidates 
        SET DocBirthCert = ?, DocDegree = ?, DocMilitary = ?, 
            DocCriminalRecord = ?, DocPersonalPhoto = ?, DocIDCard = ?, DocInfoSheet = ?
        WHERE CandidateID = ?
    """, (doc_birth, doc_degree, doc_military, doc_criminal, doc_photo, doc_id, doc_sheet, candidate_id))
    
    conn.commit()
    conn.close()
    
    flash('✅ تم تحديث ملفات المرشح بنجاح', 'success')
    return redirect(request.referrer)

@app.route('/recruitment/waiting')
def recruitment_waiting():
    """ Dashboard for candidates in Waiting List with Filters & Notes """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Get Filters
    search_query = request.args.get('search', '').strip()
    job_filter = request.args.get('job_id')

    # 2. Build Query
    # We use a Subquery (or OUTER APPLY) to get the *latest* note added when they were moved to 'Waiting'
    sql = """
        SELECT 
            C.CandidateID, C.FullName, C.Phone, C.ApplicationDate, C.Status,
            J.JobTitle, J.HiringManager, D.DEPTNAME,
            (
                SELECT TOP 1 Note 
                FROM CandidateLogs L 
                WHERE L.CandidateID = C.CandidateID 
                ORDER BY L.ActionDate DESC
            ) AS LastNote
        FROM Candidates C
        JOIN Jobs J ON C.JobID = J.JobID
        LEFT JOIN DEPARTMENTS D ON J.DepartmentID = D.DEPTID
        WHERE C.Status = 'Waiting'
    """
    
    params = []

    # 3. Apply Filters
    if search_query:
        sql += " AND (C.FullName LIKE ? OR C.Phone LIKE ?)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])
    
    if job_filter and job_filter.isdigit():
        sql += " AND C.JobID = ?"
        params.append(job_filter)

    sql += " ORDER BY C.ApplicationDate DESC"

    cursor.execute(sql, params)
    candidates = cursor.fetchall()

    # 4. Fetch Jobs for Filter Dropdown
    cursor.execute("SELECT JobID, JobTitle FROM Jobs ORDER BY JobTitle")
    all_jobs = cursor.fetchall()

    conn.close()
    
    return render_template('recruitment/waiting.html', 
                           candidates=candidates, 
                           all_jobs=all_jobs,
                           current_filters=request.args)


@app.route('/recruitment/resign', methods=['POST'])
def submit_resignation():
    candidate_id = request.form['candidate_id']
    reason_id = request.form['reason_id']
    notes = request.form['notes']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get Reason Text
    cursor.execute("SELECT ReasonText FROM ResignationReasons WHERE ReasonID = ?", (reason_id,))
    reason_text = cursor.fetchone()[0]
    
    # 1. Update Candidate Status
    cursor.execute("UPDATE Candidates SET Status = 'Resigned' WHERE CandidateID = ?", (candidate_id,))
    
    # 2. Add to Log
    log_note = f"استقالة: {reason_text} - {notes}"
    cursor.execute("""
        INSERT INTO CandidateLogs (CandidateID, FromStage, ToStage, EvaluationScore, Note, ActionDate)
        VALUES (?, 'Hired', 'Resigned', 0, ?, GETDATE())
    """, (candidate_id, log_note))
    
    conn.commit()
    conn.close()
    
    flash('🚪 تم تسجيل الاستقالة بنجاح.', 'warning')
    return redirect(url_for('recruitment_history'))

from datetime import timedelta, datetime

@app.route('/recruitment/training')
def recruitment_training():
    """ Dedicated Dashboard for Active Trainees with Countdown """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch all candidates currently in 'Training'
    cursor.execute("""
        SELECT C.CandidateID, C.FullName, C.Phone, C.TrainingStartDate, C.TrainerName, J.JobTitle, C.NationalID 
        FROM Candidates C
        JOIN Jobs J ON C.JobID = J.JobID
        WHERE C.Status = 'Training'
        ORDER BY C.TrainingStartDate DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    trainees = []
    today = datetime.now().date()

    for row in rows:
        start_date = row.TrainingStartDate.date() if row.TrainingStartDate else today
        end_date = start_date + timedelta(days=90) # 3 Months Rule
        
        # Calculate Progress
        total_days = 90
        days_passed = (today - start_date).days
        days_left = (end_date - today).days
        
        # Calculate Percentage for the Bar (0% to 100%)
        percent = (days_passed / total_days) * 100
        if percent > 100: percent = 100
        if percent < 0: percent = 0

        # Determine Color based on urgency
        color = "success" # Green (Early)
        if percent > 50: color = "warning" # Yellow (Halfway)
        if percent > 85: color = "danger"  # Red (Almost done)

        trainees.append({
        'id': row.CandidateID,
        'name': row.FullName,
        'job': row.JobTitle,
        'phone': row.Phone,
        'trainer': row.TrainerName,
        'national_id': row.NationalID,  # <--- Add this line
        'start_date': start_date,
        'end_date': end_date,
        'days_left': days_left,
        'percent': int(percent),
        'color': color
    })

    return render_template('recruitment/recruitment_training.html', trainees=trainees)

@app.route('/recruitment/assign_trainer', methods=['POST'])
def assign_trainer():
    """ Assign a trainer to a candidate """
    candidate_id = request.form['candidate_id']
    trainer_name = request.form['trainer_name']
    
    conn = get_db_connection()
    conn.execute("UPDATE Candidates SET TrainerName = ? WHERE CandidateID = ?", (trainer_name, candidate_id))
    conn.commit()
    conn.close()
    
    flash('✅ تم تعيين المدرب بنجاح', 'success')
    return redirect(url_for('recruitment_training'))

@app.route('/recruitment/move_with_eval', methods=['POST'])
def move_candidate_with_eval():
    """ 
    Moves candidate to a new stage AND saves the Score/Reason.
    Also records the Start Date if moving to 'Training'.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Get Data from Modal
    candidate_id = request.form['candidate_id']
    new_stage = request.form['new_stage']
    score = request.form.get('score') or 0
    note = request.form.get('note')

    # 2. Get Current Stage (for history)
    cursor.execute("SELECT Status, JobID FROM Candidates WHERE CandidateID = ?", (candidate_id,))
    row = cursor.fetchone()
    current_stage = row.Status
    job_id = row.JobID

    # 3. Save to History Log
    cursor.execute("""
        INSERT INTO CandidateLogs (CandidateID, FromStage, ToStage, EvaluationScore, Note, ActionDate)
        VALUES (?, ?, ?, ?, ?, GETDATE())
    """, (candidate_id, current_stage, new_stage, score, note))

    # 4. Update Status (WITH TRAINING LOGIC)
    # If moving TO Training, we must save the Start Date for the countdown
    if new_stage == 'Training':
        cursor.execute("""
            UPDATE Candidates 
            SET Status = ?, TrainingStartDate = GETDATE() 
            WHERE CandidateID = ?
        """, (new_stage, candidate_id))
    else:
        # Normal move for other stages
        cursor.execute("UPDATE Candidates SET Status = ? WHERE CandidateID = ?", (new_stage, candidate_id))

    conn.commit()
    conn.close()
    
    flash(f'✅ Candidate moved to {new_stage} successfully!', 'success')
    
    # If we are on the Training Dashboard, go back there. Otherwise, go to Pipeline.
    if 'recruitment/training' in request.referrer:
        return redirect(url_for('recruitment_training'))
    else:
        return redirect(url_for('job_pipeline', job_id=job_id))

@app.route('/recruitment/history')
def recruitment_history():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # جلب آخر إجراء لكل مرشح فقط (باستخدام ROW_NUMBER)
    cursor.execute("""
        SELECT 
            L.LogID, L.FromStage, L.ToStage, L.EvaluationScore, L.Note, L.ActionDate,
            C.CandidateID, C.FullName, C.Phone, C.Email, C.Status as CurrentStatus, C.NationalID,
            J.JobTitle, D.DEPTNAME
        FROM (
            SELECT 
                L.*,
                ROW_NUMBER() OVER (PARTITION BY L.CandidateID ORDER BY L.ActionDate DESC, L.LogID DESC) as rn
            FROM CandidateLogs L
        ) L
        INNER JOIN Candidates C ON L.CandidateID = C.CandidateID
        LEFT JOIN Jobs J ON C.JobID = J.JobID
        LEFT JOIN DEPARTMENTS D ON J.DepartmentID = D.DEPTID
        WHERE L.rn = 1
        ORDER BY L.ActionDate DESC
    """)
    logs = cursor.fetchall()

    # Fetch Resignation Reasons
    try:
        cursor.execute("SELECT * FROM ResignationReasons")
        reasons = cursor.fetchall()
    except:
        reasons = [] 

    conn.close()
    return render_template('recruitment/recruitment_history.html', logs=logs, reasons=reasons)

@app.route('/recruitment/job/toggle/<int:job_id>', methods=['POST'])
@login_required  # Or @admin_required depending on your needs
def job_toggle_status(job_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Toggle logic: If Open -> Closed, If Closed -> Open
        cursor.execute("""
            UPDATE Jobs 
            SET Status = CASE WHEN Status = 'Open' THEN 'Closed' ELSE 'Open' END 
            OUTPUT INSERTED.Status
            WHERE JobID = ?
        """, (job_id,))
        
        row = cursor.fetchone()
        if row:
            new_status = row[0]
            conn.commit()
            return json.jsonify({'success': True, 'new_status': new_status})
        else:
            return json.jsonify({'success': False, 'error': 'Job not found'})

    except Exception as e:
        conn.rollback()
        return json.jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/recruitment/settings', methods=['GET', 'POST'])
def recruitment_settings():
    """ Page to manage Resignation Reasons """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Handle Adding a New Reason
    if request.method == 'POST' and 'new_reason' in request.form:
        new_reason = request.form['new_reason'].strip()
        if new_reason:
            cursor.execute("INSERT INTO ResignationReasons (ReasonText) VALUES (?)", (new_reason,))
            conn.commit()
            flash('✅ تم إضافة السبب بنجاح', 'success')

    # 2. Handle Deleting a Reason
    if request.method == 'POST' and 'delete_id' in request.form:
        delete_id = request.form['delete_id']
        cursor.execute("DELETE FROM ResignationReasons WHERE ReasonID = ?", (delete_id,))
        conn.commit()
        flash('🗑️ تم حذف السبب', 'warning')

    # 3. Fetch All Reasons
    cursor.execute("SELECT * FROM ResignationReasons")
    reasons = cursor.fetchall()
    
    conn.close()
    return render_template('recruitment/recruitment_settings.html', reasons=reasons)

@app.route('/recruitment/job/add', methods=['GET', 'POST'])
def job_create():
    """ 
    Form to create a new Job Requisition.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        # 1. Get Data from Form
        title = request.form['title']
        manager = request.form['manager']
        dept_id = request.form.get('dept_id') # Can be empty
        desc = request.form['description']
        
        # Handle empty department
        if not dept_id:
            dept_id = None

        # 2. Insert into Database
        cursor.execute("""
            INSERT INTO Jobs (JobTitle, DepartmentID, HiringManager, Description, Status, PostDate)
            VALUES (?, ?, ?, ?, 'Open', GETDATE())
        """, (title, dept_id, manager, desc))
        
        conn.commit()
        conn.close()
        
        flash('✅ Job Requisition Created Successfully!', 'success')
        return redirect(url_for('recruitment_jobs'))

    # GET Request: Show the form
    cursor.execute("SELECT DEPTID, DEPTNAME FROM DEPARTMENTS ORDER BY DEPTNAME")
    depts = cursor.fetchall()
    conn.close()
    
    return render_template('job_form.html', depts=depts)

# =========================================
# 📦 ARCHIVE MODULE (Add this to app.py)
# =========================================

@app.route('/recruitment/archive')
def recruitment_archive():
    """ Displays the list of Archived Candidates """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch archived candidates with their Job Title
    cursor.execute("""
        SELECT C.CandidateID, C.FullName, C.Phone, C.Email, C.ApplicationDate, 
               J.JobTitle, D.DEPTNAME,
               (SELECT TOP 1 Note FROM CandidateLogs L WHERE L.CandidateID = C.CandidateID ORDER BY L.ActionDate DESC) as LastNote
        FROM Candidates C
        LEFT JOIN Jobs J ON C.JobID = J.JobID
        LEFT JOIN DEPARTMENTS D ON J.DepartmentID = D.DEPTID
        WHERE C.Status = 'Archived'
        ORDER BY C.ApplicationDate DESC
    """)
    candidates = cursor.fetchall()
    conn.close()
    
    return render_template('recruitment/recruitment_archive.html', candidates=candidates)

@app.route('/recruitment/archive_action', methods=['POST'])
def archive_candidate():
    """ Moves a candidate to the Archive status from anywhere """
    candidate_id = request.form['candidate_id']
    note = request.form.get('note', 'Moved to Archive')
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get current status to log it properly
    cursor.execute("SELECT Status, FullName FROM Candidates WHERE CandidateID = ?", (candidate_id,))
    row = cursor.fetchone()
    
    if row:
        old_status = row.Status
        name = row.FullName

        # Update Status to 'Archived'
        cursor.execute("UPDATE Candidates SET Status = 'Archived' WHERE CandidateID = ?", (candidate_id,))

        # Log the action
        cursor.execute("""
            INSERT INTO CandidateLogs (CandidateID, FromStage, ToStage, Note, ActionDate)
            VALUES (?, ?, 'Archived', ?, GETDATE())
        """, (candidate_id, old_status, note))

        flash(f'📦 Candidate "{name}" archived successfully.', 'success')

    conn.commit()
    conn.close()
    return redirect(request.referrer)

@app.route('/recruitment/restore', methods=['POST'])
def restore_candidate():
    """ Restores candidate from Archive back to 'New' """
    candidate_id = request.form['candidate_id']
    target_stage = 'New' # Default restore to New
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE Candidates SET Status = ? WHERE CandidateID = ?", (target_stage, candidate_id))
    
    cursor.execute("""
        INSERT INTO CandidateLogs (CandidateID, FromStage, ToStage, Note, ActionDate)
        VALUES (?, 'Archived', ?, 'Restored from Archive', GETDATE())
    """, (candidate_id, target_stage))
    
    conn.commit()
    conn.close()
    
    flash('♻️ Candidate restored successfully!', 'success')
    return redirect(url_for('recruitment_archive'))



if __name__ == '__main__':
    # use_reloader=False prevents the crash
    # debug=True allows you to see the error pages
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)