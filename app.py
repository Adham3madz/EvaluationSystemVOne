from flask import Flask, render_template, request, redirect, url_for, flash, session, json, send_file, jsonify
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
from utils.pdf_generator import generate_form_pdf


app = Flask(__name__)
app.secret_key = "super-secret-key-2025"

import traceback

UPLOAD_FOLDER = 'static/uploads/cvs'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True) # Create folder if not exists

@app.errorhandler(500)
def internal_error(exception):
    print("500 Error Caught!")
    trace = traceback.format_exc()
    print(trace)
    return jsonify({"status": "error", "message": "Internal Server Error", "trace": trace}), 500

# ========== DATABASE CONNECTION ==========

def get_db_connection():
    return pyodbc.connect(CONNECTION_STRING)

def log_system_action(module, action_type, description, user_id=None, username=None):
    """
    Helper to log actions to AppLogs table.
    """
    try:
        if not user_id and 'user_id' in session:
            user_id = session['user_id']
        if not username and 'username' in session:
            username = session['username']
            
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO AppLogs (UserID, Username, Module, ActionType, Description, Timestamp)
            VALUES (?, ?, ?, ?, ?, GETDATE())
        """, (user_id, username, module, action_type, description))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Logging Error: {e}")

# ========== AUTH HELPERS ==========

def log_system_action(module, action_type, description, user_id=None, username=None):
    """ Helper to log actions to AppLogs table. """
    try:
        if not user_id and 'user_id' in session: user_id = session['user_id']
        if not username and 'username' in session: username = session['username']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO AppLogs (UserID, Username, Module, ActionType, Description, Timestamp) VALUES (?, ?, ?, ?, ?, GETDATE())", (user_id, username, module, action_type, description))
        conn.commit()
        conn.close()
    except Exception as e: print(f"Logging Error: {e}")

def is_admin():
    return session.get('role_id') == 1  # Only Role 1 is Super Admin now

def is_officer():
    return session.get('role_id') == 2  # Role 2 is Police Officer (Audit)

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

# ========== EVALUATION LOGIC ==========

def get_available_evaluation_types(conn, employee_id, manager_dept_id):
    """
    Checks an employee and returns a list of evaluation types 
    that are currently available or disabled for them.
    Updated to prevent duplicate evaluations within the current active cycle.
    """
    try:
        cursor = conn.cursor()
        
        # Ensure we have a date object for comparison
        today = datetime.now().date()
        
        # 1. Get employee's completed evals with dates to check against cycles
        cursor.execute("SELECT EvaluationTypeID, EvaluationDate FROM [AURAHR].[dbo].[Evaluations] WHERE EmployeeUserID = ?", (employee_id,))
        completed_evals = []
        for row in cursor.fetchall():
            e_date = row.EvaluationDate
            if isinstance(e_date, datetime):
                e_date = e_date.date()
            completed_evals.append({'id': row.EvaluationTypeID, 'date': e_date})
            
        # Set of IDs for quick prerequisite checks
        completed_eval_ids = {e['id'] for e in completed_evals}
        
        # 2. Get all rules (Updated to fetch new columns)
        cursor.execute("SELECT * FROM [AURAHR].[dbo].[EvaluationTypes] ORDER BY SortOrder")
        all_types_rules = cursor.fetchall()

        # 2b. Get Employee Class and Hire Date
        cursor.execute("SELECT employee_class, HiredDay FROM [AURAHR].[dbo].[USERINFO] WHERE USERID = ?", (employee_id,))
        emp_data = cursor.fetchone()
        emp_class = emp_data.employee_class if emp_data and emp_data.employee_class else 'لم تضاف'
        hire_date = emp_data.HiredDay if emp_data and emp_data.HiredDay else None
        
        # Ensure hire_date is a date object
        if hire_date and isinstance(hire_date, datetime):
            hire_date = hire_date.date()

        # 3. Get all active, open cycles including StartDate and EndDate
        cursor.execute("""
            SELECT C.EvaluationTypeID, CD.DepartmentID, C.StartDate, C.EndDate
            FROM [AURAHR].[dbo].[EvaluationCycles] C
            LEFT JOIN [AURAHR].[dbo].[CycleDepartments] CD ON C.CycleID = CD.CycleID
            WHERE C.IsEnabled = 1 AND ? BETWEEN C.StartDate AND C.EndDate
        """, (today,))
        active_cycles = cursor.fetchall()

        # Process into a lookup { type_id: { 'depts': [], 'start': date, 'end': date } }
        open_cycle_depts = {} 
        for cycle in active_cycles:
            tid = cycle.EvaluationTypeID
            if tid not in open_cycle_depts:
                # Convert cycle dates to date objects if needed
                c_start = cycle.StartDate.date() if isinstance(cycle.StartDate, datetime) else cycle.StartDate
                c_end = cycle.EndDate.date() if isinstance(cycle.EndDate, datetime) else cycle.EndDate
                
                open_cycle_depts[tid] = {
                    'depts': [],
                    'start': c_start,
                    'end': c_end
                }
            if cycle.DepartmentID:
                open_cycle_depts[tid]['depts'].append(cycle.DepartmentID)

        available_eval_list = []
        
        for rule in all_types_rules:
            eval_id = rule.EvaluationTypeID
            prereq_id = rule.PrerequisiteTypeID
            is_repeatable = rule.IsRepeatable
            days_after = rule.DaysAfterPrerequisite 
            included_classes_str = rule.IncludedClasses
            
            # --- Check 0: Class Inclusion ---
            # IMPORTANT: Correct Logic for Mixed Classes
            # If "IncludedClasses" is set (e.g., 'A,B,C'), ONLY those classes see it.
            # If "IncludedClasses" is EMPTY or NULL, EVERYONE sees it.
            
            if included_classes_str:
                # Normalize separators (allow comma or space-comma)
                allowed_list = [c.strip() for c in included_classes_str.replace('،', ',').split(',')]
                
                # Check if current employee's class is in the allowed list
                # Use partial match or exact? Let's use exact substring check for safety
                # e.g. emp_class='مساعد مدير', allowed='مدير' -> This might be tricky.
                # Let's assume exact string match for the defined classes codes.
                
                is_allowed = False
                for allowed in allowed_list:
                    if allowed == emp_class or allowed in emp_class:
                        is_allowed = True
                        break
                
                if not is_allowed:
                    # Skip this evaluation type for this user
                    continue

            # --- Check 1: Prerequisite ---
            prereq_met = False
            prereq_date = None
            
            if prereq_id is None:
                prereq_met = True
                # If no prereq, fallback to Hire Date for timing
                prereq_date = hire_date
            else:
                 # Check if Prereq ID is in completed list
                 # We need the DATE of that completion too
                 for c in completed_evals:
                     if c['id'] == prereq_id:
                         prereq_met = True
                         prereq_date = c['date']
                         break
            
            # --- Check 2: Repeatability ---
            is_completed_ever = eval_id in completed_eval_ids
            repeat_met = is_repeatable or (not is_completed_ever)
            
            # --- Check 3: Cycle OR Auto-Time Trigger ---
            is_open = False
            already_done_in_cycle = False
            status_note = ''

            # Logic: If 'DaysAfter' is set, we use Time-Based Logic. Otherwise, we use Cycle Logic.
            if days_after is not None:
                # === TIME BASED LOGIC ===
                if prereq_met and prereq_date:
                    # Calculate Due Date
                    due_date = prereq_date + timedelta(days=days_after)
                    
                    # Logic: Is it DUE yet? (Today >= Due Date)
                    # And maybe we want a window? For now, just "Is it time?"
                    if today >= due_date:
                        is_open = True
                        status_note = '(مستحق تلقائياً)'
                    else:
                        status_note = f'(يستحق في {due_date})'
                else:
                    status_note = '(بانتظار المتطلب)'
                    
                # For time-based, "Cycle" duplication check is simple: Have we done THIS specific step?
                # If not repeatable, 'is_completed_ever' handles it.
                # If repeatable, we might need complex "time window" logic, but user said "30 days then 3 months".
                # These sound like ONE-OFF events per employee. So likely Valid only ONCE.
                if is_completed_ever and not is_repeatable:
                    already_done_in_cycle = True # Treat as done
                    
            else:
                # === TRADITIONAL CYCLE LOGIC ===
                if eval_id in open_cycle_depts:
                    cycle_info = open_cycle_depts[eval_id]
                    linked_depts = cycle_info['depts']
                    
                    if not linked_depts or manager_dept_id in linked_depts:
                        is_open = True
                    
                    if is_open:
                        for ce in completed_evals:
                            if ce['id'] == eval_id:
                                if cycle_info['start'] <= ce['date'] <= cycle_info['end']:
                                    already_done_in_cycle = True
                                    break
                else:
                    is_open = True # Always open if no cycles defined (and no days_after)

            # Final decision logic
            if already_done_in_cycle:
                available_eval_list.append({
                    'id': eval_id, 'name': rule.DisplayName, 'disabled': True, 'note': '(تم التقييم)'
                })
            elif prereq_met and repeat_met and is_open:
                available_eval_list.append({
                    'id': eval_id, 'name': rule.DisplayName, 'disabled': False, 
                    'note': status_note if status_note else '(متاح)'
                })
            else:
                # Determine why it's closed for better UI
                note = status_note
                if not note:
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
    cursor.execute("SELECT employee_class FROM [AURAHR].[dbo].[USERINFO] WHERE USERID = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result.employee_class if result and result.employee_class else 'لم تضاف'

def get_all_classes():
    """Helper to fetch all employee classes from DB"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ClassID, ClassName, DisplayName FROM [AURAHR].[dbo].[EmployeeClasses] ORDER BY ClassName")
        classes = cursor.fetchall()
        conn.close()
        return classes
    except Exception as e:
        print(f"Error fetching classes: {e}")
        return []

# ========== FILTERS ==========

@app.template_filter('date_format_arabic')
def date_format_arabic(value, format='%Y-%m-%d'):
    if value == 'now':
        date_obj = datetime.now()
    elif isinstance(value, str):
        try:
            date_obj = datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            return value
    else:
        date_obj = value

    months = {
        1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
        5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس",
        9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"
    }

    day = date_obj.day
    month = months[date_obj.month]
    year = date_obj.year

    return f"{day} {month} {year}"

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
            cursor.execute("SELECT UserID, Username, PasswordHash, RoleID, Name FROM [AURAHR].[dbo].[Users] WHERE Username = ?", (username,))
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
            log_system_action('Access', 'Login', 'تم تسجيل الدخول بنجاح', user_id=user.UserID, username=user.Username)

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
        'users_count': 0, 'employees_count': 0, 'archived_count': 0, 'evals_count': 0, 'avg_score': 0,
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
                    (SELECT COUNT(*) FROM [AURAHR].[dbo].[Users]) as UsersCount,
                    (SELECT COUNT(*) FROM [AURAHR].[dbo].[USERINFO] WHERE (IsActive = 1 OR IsActive IS NULL)) as ActiveCount,
                    (SELECT COUNT(*) FROM [AURAHR].[dbo].[USERINFO] WHERE IsActive = 0) as ArchivedCount,
                    (SELECT COUNT(*) FROM [AURAHR].[dbo].[Evaluations] WHERE OverallScore IS NOT NULL) as EvalsCount,
                    (SELECT AVG(OverallScore) FROM [AURAHR].[dbo].[Evaluations] WHERE OverallScore IS NOT NULL) as AvgScore
            """
        else:
            # Manager Department Filters
            # Get Manager's Dept ID first
            cursor.execute("SELECT DepartmentID FROM [AURAHR].[dbo].[Users] WHERE UserID = ?", (ctx['user_id'],))
            user_row = cursor.fetchone()
            dept_id = user_row.DepartmentID if user_row else None
            
            if not dept_id:
                # If manager has no dept, show 0s
                return render_template('dashboard.html', **ctx)

            kpi_where = "DepartmentID = ?"
            chart_where = "UI.DEFAULTDEPTID = ?"
            # We need to pass the parameter multiple times for the subqueries
            kpi_params = [dept_id, dept_id, dept_id, dept_id, dept_id]
            chart_params = [] # We will fill this when building the chart query

            sql_kpis = """
                SELECT 
                    (SELECT COUNT(*) FROM [AURAHR].[dbo].[Users] WHERE DepartmentID = ?) as UsersCount,
                    (SELECT COUNT(*) FROM [AURAHR].[dbo].[USERINFO] WHERE DEFAULTDEPTID = ? AND (IsActive = 1 OR IsActive IS NULL)) as ActiveCount,
                    (SELECT COUNT(*) FROM [AURAHR].[dbo].[USERINFO] WHERE DEFAULTDEPTID = ? AND IsActive = 0) as ArchivedCount,
                    (SELECT COUNT(*) FROM [AURAHR].[dbo].[Evaluations] E JOIN [AURAHR].[dbo].[USERINFO] UI ON E.EmployeeUserID = UI.USERID WHERE UI.DEFAULTDEPTID = ? AND E.OverallScore IS NOT NULL) as EvalsCount,
                    (SELECT AVG(E.OverallScore) FROM [AURAHR].[dbo].[Evaluations] E JOIN [AURAHR].[dbo].[USERINFO] UI ON E.EmployeeUserID = UI.USERID WHERE UI.DEFAULTDEPTID = ? AND E.OverallScore IS NOT NULL) as AvgScore
            """

        # ==========================================
        # PART 2: EXECUTE KPIs (Trip #1)
        # ==========================================
        cursor.execute(sql_kpis, kpi_params)
        kpi_row = cursor.fetchone()
        if kpi_row:
            ctx['users_count'] = kpi_row.UsersCount
            ctx['employees_count'] = kpi_row.ActiveCount
            ctx['archived_count'] = kpi_row.ArchivedCount
            ctx['evals_count'] = kpi_row.EvalsCount
            ctx['avg_score'] = kpi_row.AvgScore if kpi_row.AvgScore else 0

        # ==========================================
        # PART 3: EXECUTE CHARTS & LISTS (Trip #2)
        # ==========================================
        # We concatenate 5 queries into one string separated by ';'
        # Note: We must ensure the params list matches the order of '?' in the string
        
        base_joins = """
            FROM [AURAHR].[dbo].[Evaluations] E
            LEFT JOIN [AURAHR].[dbo].[USERINFO] UI ON E.EmployeeUserID = UI.USERID
            LEFT JOIN [AURAHR].[dbo].[Users] U ON E.EmployeeUserID = U.UserID
            LEFT JOIN [AURAHR].[dbo].[Users] Mgr ON E.EvaluatorUserID = Mgr.UserID
            LEFT JOIN [AURAHR].[dbo].[EvaluationTypes] ET ON E.EvaluationTypeID = ET.EvaluationTypeID
        """

        sql_charts = f"""
        -- 1. Rating Distribution
        SELECT OverallRating, COUNT(*) as count 
        FROM [AURAHR].[dbo].[Evaluations] E 
        LEFT JOIN [AURAHR].[dbo].[USERINFO] UI ON E.EmployeeUserID = UI.USERID 
        WHERE {chart_where} AND OverallRating IS NOT NULL 
        GROUP BY OverallRating;

        -- 2. Type Distribution
        SELECT COALESCE(ET.DisplayName, E.EvaluationType, 'غير محدد'), COUNT(*) as count 
        FROM [AURAHR].[dbo].[Evaluations] E 
        LEFT JOIN [AURAHR].[dbo].[USERINFO] UI ON E.EmployeeUserID = UI.USERID 
        LEFT JOIN [AURAHR].[dbo].[EvaluationTypes] ET ON E.EvaluationTypeID = ET.EvaluationTypeID 
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
        FROM [AURAHR].[dbo].[Evaluations] E 
        LEFT JOIN [AURAHR].[dbo].[USERINFO] UI ON E.EmployeeUserID = UI.USERID
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
            # -- Inactive Managers Pagination Logic --
            managers_page = 1
            managers_limit = 5
            managers_offset = 0

            # 1. Get Total Count
            cursor.execute("""
                SELECT COUNT(*) 
                FROM [AURAHR].[dbo].[Users] U
                WHERE U.RoleID = 3 
                AND U.UserID NOT IN (SELECT DISTINCT EvaluatorUserID FROM [AURAHR].[dbo].[Evaluations] WHERE EvaluatorUserID IS NOT NULL)
            """)
            managers_count = cursor.fetchone()[0]
            managers_total_pages = (managers_count + managers_limit - 1) // managers_limit
            ctx['managers_page'] = managers_page
            ctx['managers_total_pages'] = managers_total_pages

            sql_admin = """
            -- Inactive Managers (Paginated)
            SELECT U.UserID, U.Name, D.DEPTNAME,
                (SELECT COUNT(*) FROM [AURAHR].[dbo].[USERINFO] WHERE DEFAULTDEPTID = U.DepartmentID AND IsActive = 1) as TotalEmployees
            FROM [AURAHR].[dbo].[Users] U
            LEFT JOIN [AURAHR].[dbo].[DEPARTMENTS] D ON U.DepartmentID = D.DEPTID
            WHERE U.RoleID = 3 AND U.UserID NOT IN (SELECT DISTINCT EvaluatorUserID FROM [AURAHR].[dbo].[Evaluations] WHERE EvaluatorUserID IS NOT NULL)
            ORDER BY U.Name
            OFFSET 0 ROWS FETCH NEXT 5 ROWS ONLY;

            -- Active Evaluators
            SELECT TOP 5 
                COALESCE(Mgr.Name, Mgr.Username) AS EvaluatorName, 
                COUNT(E.EvaluationID) as evaluation_count, 
                COUNT(DISTINCT E.EmployeeUserID) as distinct_evaluated,
                (SELECT COUNT(*) FROM [AURAHR].[dbo].[USERINFO] WHERE DEFAULTDEPTID = Mgr.DepartmentID AND IsActive = 1) as total_dept_employees
            FROM [AURAHR].[dbo].[Evaluations] E
            LEFT JOIN [AURAHR].[dbo].[Users] Mgr ON E.EvaluatorUserID = Mgr.UserID
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
            SELECT HiredDay FROM [AURAHR].[dbo].[USERINFO] WHERE HiredDay IS NOT NULL AND DEFAULTDEPTID <> -1
            UNION ALL 
            SELECT HiredDay FROM [AURAHR].[dbo].[EmployeeArchive] WHERE HiredDay IS NOT NULL
        ) as AllHires 
        WHERE YEAR(HiredDay) > 1900 GROUP BY YEAR(HiredDay) ORDER BY Yr;

        -- 2. Leavers
        SELECT YEAR(EndDay) as Yr, COUNT(*) as Count FROM [AURAHR].[dbo].[EmployeeArchive] 
        WHERE EndDay IS NOT NULL AND YEAR(EndDay) > 1900 GROUP BY YEAR(EndDay) ORDER BY Yr;

        -- 3. Dept Turnover
        SELECT D.DEPTNAME, COUNT(*) as Count FROM [AURAHR].[dbo].[EmployeeArchive] A 
        LEFT JOIN [AURAHR].[dbo].[DEPARTMENTS] D ON A.ArchivedDeptID = D.DEPTID 
        GROUP BY D.DEPTNAME ORDER BY Count DESC;

        -- 4. Pos Turnover
        SELECT P.PositionName, COUNT(*) as Count FROM [AURAHR].[dbo].[EmployeeArchive] A 
        LEFT JOIN [AURAHR].[dbo].[POSITIONS] P ON A.ArchivedPosID = P.PositionID 
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

@app.route('/dashboard/managers-partial')
@admin_required
def dashboard_managers_partial():
    page = request.args.get('page', 1, type=int)
    limit = 5
    offset = (page - 1) * limit
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Get Total Count
        cursor.execute("""
            SELECT COUNT(*) 
            FROM [AURAHR].[dbo].[Users] U
            WHERE U.RoleID = 3 
            AND U.UserID NOT IN (SELECT DISTINCT EvaluatorUserID FROM [AURAHR].[dbo].[Evaluations] WHERE EvaluatorUserID IS NOT NULL)
        """)
        total_count = cursor.fetchone()[0]
        total_pages = (total_count + limit - 1) // limit
        
        # 2. Get Paginated Data
        sql = """
            SELECT U.UserID, U.Name, D.DEPTNAME,
                (SELECT COUNT(*) FROM [AURAHR].[dbo].[USERINFO] WHERE DEFAULTDEPTID = U.DepartmentID AND IsActive = 1) as TotalEmployees
            FROM [AURAHR].[dbo].[Users] U
            LEFT JOIN [AURAHR].[dbo].[DEPARTMENTS] D ON U.DepartmentID = D.DEPTID
            WHERE U.RoleID = 3 
            AND U.UserID NOT IN (SELECT DISTINCT EvaluatorUserID FROM [AURAHR].[dbo].[Evaluations] WHERE EvaluatorUserID IS NOT NULL)
            ORDER BY U.Name
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """
        cursor.execute(sql, (offset, limit))
        managers = cursor.fetchall()
        
        return render_template('partials/managers_table.html', 
                             inactive_managers=managers, 
                             managers_page=page, 
                             managers_total_pages=total_pages)
                             
    except Exception as e:
        print(f"Error in partial: {e}")
        return f"<div class='alert alert-danger'>Error loading data: {e}</div>"
    finally:
        conn.close()




@app.route('/users')
@login_required
def users():
    search = request.args.get('search', '').strip()
    role_id_filter = request.args.get('role_id', '')
    dept_id_filter = request.args.get('dept_id', '')
    conn = get_db_connection()
    cursor = conn.cursor()
    query_base = "SELECT U.UserID, U.Username, COALESCE(U.Name, UI.NAME) AS FullName, U.DepartmentID, D.DEPTNAME, U.RoleID, R.RoleName FROM [AURAHR].[dbo].[Users] U LEFT JOIN [AURAHR].[dbo].[USERINFO] UI ON U.UserID = UI.USERID LEFT JOIN [AURAHR].[dbo].[DEPARTMENTS] D ON U.DepartmentID = D.DEPTID LEFT JOIN [AURAHR].[dbo].[Roles] R ON U.RoleID = R.RoleID"
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
    cursor.execute("SELECT RoleID, RoleName FROM [AURAHR].[dbo].[Roles] ORDER BY RoleID")
    roles = cursor.fetchall()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [AURAHR].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    depts = cursor.fetchall()
    conn.close()
    return render_template('users.html', users=users, roles=roles, depts=depts, filters=request.args, is_admin=is_admin())

@app.route('/users/add', methods=['GET', 'POST'])
@admin_required
def add_user():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT RoleID, RoleName FROM [AURAHR].[dbo].[Roles] ORDER BY RoleID")
    roles = cursor.fetchall()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [AURAHR].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    depts = cursor.fetchall()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'] 
        name = request.form.get('name') or None
        role_id = request.form.get('role_id') or None
        dept_id = request.form.get('department_id') or None
        try:
            cursor.execute("INSERT INTO [AURAHR].[dbo].[Users] (Username, PasswordHash, RoleID, Name, DepartmentID) VALUES (?, ?, ?, ?, ?)", (username, password, role_id, name, dept_id))
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
    cursor.execute("SELECT RoleID, RoleName FROM [AURAHR].[dbo].[Roles] ORDER BY RoleID")
    roles = cursor.fetchall()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [AURAHR].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    depts = cursor.fetchall()
    cursor.execute("SELECT UserID, Username, RoleID, Name, DepartmentID FROM [AURAHR].[dbo].[Users] WHERE UserID = ?", (user_id,))
    user = cursor.fetchone()
    if request.method == 'POST':
        username = request.form['username']
        name = request.form.get('name') or None
        role_id = request.form.get('role_id') or None
        dept_id = request.form.get('department_id') or None
        new_password = request.form.get('password') or None
        if new_password:
            cursor.execute("UPDATE [AURAHR].[dbo].[Users] SET Username = ?, Name = ?, RoleID = ?, DepartmentID = ?, PasswordHash = ? WHERE UserID = ?", (username, name, role_id, dept_id, new_password, user_id))
        else:
            cursor.execute("UPDATE [AURAHR].[dbo].[Users] SET Username = ?, Name = ?, RoleID = ?, DepartmentID = ? WHERE UserID = ?", (username, name, role_id, dept_id, user_id))
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
    cursor.execute("DELETE FROM [AURAHR].[dbo].[Users] WHERE UserID = ?", (user_id,))
    conn.commit()
    conn.close()
    flash('User deleted successfully!', 'info')
    return redirect(url_for('users'))



@app.route('/userinfo')
@login_required 
def userinfo_list():
    # 1. Collect Filters & Pagination
    search = request.args.get('search', '').strip()
    employee_class_filter = request.args.get('employee_class', '')
    gender = request.args.get('gender', '')
    department = request.args.get('department', '')
    title = request.args.get('title', '').strip()
    badge_number = request.args.get('badge_number', '').strip()
    sort = request.args.get('sort', 'USERID')
    order = request.args.get('order', 'asc')
    
    # Pagination
    try:
        page = int(request.args.get('page', 1))
        if page < 1: page = 1
    except ValueError:
        page = 1
        
    limit = 50 
    offset = (page - 1) * limit
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    user_id = session.get('user_id')
    role_id = session.get('role_id')
    
    # 2. Security & Global Filters
    where_clauses = ["1=1"] 
    params = []
    
    if is_admin():
        where_clauses.append("(UI.IsActive = 1 OR UI.IsActive IS NULL)")
    elif is_officer():
        cursor.execute("SELECT DepartmentID FROM [AURAHR].[dbo].[Users] WHERE UserID = ?", (user_id,))
        user_row = cursor.fetchone()
        dept_id = user_row.DepartmentID if user_row else None
        
        if dept_id and dept_id != -1:
            where_clauses.append("UI.DEFAULTDEPTID = ?")
            params.append(dept_id)
            where_clauses.append("UI.employee_class LIKE ?")
            params.append('%مدير%')
        else:
            where_clauses.append("1=0")
    elif role_id == 3:
        cursor.execute("SELECT DepartmentID FROM [AURAHR].[dbo].[Users] WHERE UserID = ?", (user_id,))
        user_row = cursor.fetchone()
        dept_id = user_row.DepartmentID if user_row and user_row.DepartmentID else None
        
        if dept_id and dept_id != -1:
            hierarchy_query = """
                WITH DeptHierarchy AS (
                    SELECT DEPTID FROM [AURAHR].[dbo].[DEPARTMENTS] WHERE DEPTID = ?
                    UNION ALL
                    SELECT d.DEPTID FROM [AURAHR].[dbo].[DEPARTMENTS] d
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

    # 3. Apply User Filters
    if search:
        where_clauses.append("(UI.NAME LIKE ? OR UI.BADGENUMBER LIKE ? OR UI.SSN LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    if badge_number:
        where_clauses.append("UI.BADGENUMBER LIKE ?")
        params.append(f"%{badge_number}%")
    if employee_class_filter:
        where_clauses.append("UI.employee_class LIKE ?")
        params.append(f"%{employee_class_filter}%")
    if gender:
        if gender == 'M':
            where_clauses.append("UI.GENDER IN (?, ?, ?)")
            params.extend(['M', 'ذكر', 'Male'])
        elif gender == 'F':
            where_clauses.append("UI.GENDER IN (?, ?, ?, ?)")
            params.extend(['F', 'انثى', 'أنثى', 'Female'])
        else:
            where_clauses.append("UI.GENDER = ?")
            params.append(gender)
    if is_admin():
        if department:
            where_clauses.append("UI.DEFAULTDEPTID = ?")
            params.append(department)
        if title:
            where_clauses.append("UI.TITLE LIKE ?")
            params.append(f"%{title}%")

    where_sql = ' AND '.join(where_clauses)
    
    # Clone params for analytics since they use the same WHERE clause
    analytics_params = list(params) 

    # 4. === BATCH EXECUTION ===
    sort_field = {
        'USERID': 'UI.USERID', 'NAME': 'UI.NAME', 'HIREDDAY': 'UI.HIREDDAY',
        'BADGENUMBER': 'UI.BADGENUMBER', 'SSN': 'UI.SSN', 'employee_class': 'UI.employee_class',
        'GENDER': 'UI.GENDER', 'DEFAULTDEPTID': 'UI.DEFAULTDEPTID', 'TITLE': 'UI.TITLE'
    }.get(sort, 'UI.USERID')
    order_sql = 'ASC' if order.lower() == 'asc' else 'DESC'

    batch_sql = f"""
        -- 1. Gender Stats
        SELECT UI.GENDER, COUNT(*) 
        FROM [AURAHR].[dbo].[USERINFO] UI
        LEFT JOIN DEPARTMENTS D ON UI.DEFAULTDEPTID = D.DEPTID
        WHERE {where_sql}
        GROUP BY UI.GENDER;

        -- 2. Class Stats
        SELECT UI.employee_class, COUNT(*) 
        FROM [AURAHR].[dbo].[USERINFO] UI
        LEFT JOIN DEPARTMENTS D ON UI.DEFAULTDEPTID = D.DEPTID
        WHERE {where_sql}
        GROUP BY UI.employee_class;

        -- 3. Top Depts
        SELECT TOP 5 D.DEPTNAME, COUNT(*) as cnt
        FROM [AURAHR].[dbo].[USERINFO] UI
        LEFT JOIN DEPARTMENTS D ON UI.DEFAULTDEPTID = D.DEPTID
        WHERE {where_sql}
        GROUP BY D.DEPTNAME
        ORDER BY cnt DESC;

        -- 4. Paged Data
        SELECT UI.USERID, UI.BADGENUMBER, UI.SSN, UI.NAME, UI.GENDER, UI.TITLE, UI.HIREDDAY,
               UI.DEFAULTDEPTID, UI.employee_class, D.DEPTNAME, UI.IsActive
        FROM [AURAHR].[dbo].[USERINFO] AS UI
        LEFT JOIN DEPARTMENTS D ON UI.DEFAULTDEPTID = D.DEPTID
        WHERE {where_sql}
        ORDER BY {sort_field} {order_sql}
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY;

        -- 5. All Departments
        SELECT DEPTID, DEPTNAME FROM DEPARTMENTS ORDER BY DEPTID;
    """
    
    # Params: Analytics (x3) + Data + Pagination + Lookup (0)
    full_params = analytics_params + analytics_params + analytics_params + params + [offset, limit]
    
    cursor.execute(batch_sql, full_params)
    
    # --- Process Results ---
    analytics = {'total': 0, 'males': 0, 'females': 0, 'classes': {}, 'depts': {}}

    # 1. Gender Stats
    gender_rows = cursor.fetchall()
    for row in gender_rows:
        g_val = row[0].strip() if row[0] else ''
        count = row[1]
        analytics['total'] += count
        if g_val in ['M', 'ذكر', 'Male']: 
            analytics['males'] += count
        elif g_val in ['F', 'انثى', 'أنثى', 'Female']: 
            analytics['females'] += count

    # 2. Class Stats
    if cursor.nextset():
        class_rows = cursor.fetchall()
        for row in class_rows:
            cls_str = row[0] or "غير محدد"
            count = row[1]
            analytics['classes'][cls_str] = analytics['classes'].get(cls_str, 0) + count

    # 3. Top Depts
    if cursor.nextset():
        dept_rows = cursor.fetchall()
        for row in dept_rows:
            dname = row[0] or "غير محدد"
            analytics['depts'][dname] = row[1]

    # 4. Paged Users
    users_rows = []
    if cursor.nextset():
        users_rows = cursor.fetchall()

    # 5. All Depts
    all_departments = []
    if cursor.nextset():
        all_departments = cursor.fetchall()

    archive_reasons = []
    if is_admin():
        cursor.execute("SELECT R.ReasonID, R.ReasonText, T.TypeText FROM TerminationReasons R LEFT JOIN TerminationTypes T ON R.TypeID = T.TypeID ORDER BY T.TypeText, R.ReasonText")
        archive_reasons = cursor.fetchall()

    conn.close()
    
    total_records = analytics['total']
    total_pages = (total_records + limit - 1) // limit
    
    # 6. Get All Classes
    classes = get_all_classes()

    return render_template('userinfo.html', 
                           users=users_rows, 
                           analytics=analytics,
                           is_admin=is_admin(), 
                           role_id=role_id, 
                           departments=all_departments,
                           current_page=page,
                           total_pages=total_pages,
                           limit=limit,
                           classes=classes,
                           archive_reasons=archive_reasons)

@app.route('/userinfo/add', methods=['GET', 'POST'])
@admin_required
def userinfo_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [AURAHR].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    depts = cursor.fetchall()
    cursor.execute("SELECT PositionID, PositionName, DeptID FROM [AURAHR].[dbo].[POSITIONS] ORDER BY PositionName")
    positions_rows = cursor.fetchall()
    positions_list = [{'PositionID': p.PositionID, 'PositionName': p.PositionName, 'DeptID': p.DeptID} for p in positions_rows]
    
    classes = get_all_classes() # Get dynamic classes
    
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
    INSERT INTO [AURAHR].[dbo].[USERINFO] 
    (BADGENUMBER, SSN, NAME, GENDER, TITLE, DEFAULTDEPTID, employee_class)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (badge, ssn, name, gender, title, defaultdept, employee_class))
        conn.commit()
        conn.close()
        flash('Employee added successfully!', 'success')
        return redirect(url_for('userinfo_list'))
    conn.close()
    return render_template('userinfo_form.html', depts=depts, positions=positions_list, classes=classes, action='Add')

@app.route('/userinfo/edit/<int:uid>', methods=['GET', 'POST'])
@admin_required
def userinfo_edit(uid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [AURAHR].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    depts = cursor.fetchall()
    cursor.execute("SELECT PositionID, PositionName, DeptID FROM [AURAHR].[dbo].[POSITIONS] ORDER BY PositionName")
    positions_rows = cursor.fetchall()
    positions_list = [{'PositionID': p.PositionID, 'PositionName': p.PositionName, 'DeptID': p.DeptID} for p in positions_rows]
    cursor.execute("SELECT USERID, BADGENUMBER, SSN, NAME, GENDER, TITLE, DEFAULTDEPTID, PositionID, employee_class FROM [AURAHR].[dbo].[USERINFO] WHERE USERID = ?", (uid,))
    user = cursor.fetchone()
    
    classes = get_all_classes()

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
    UPDATE [AURAHR].[dbo].[USERINFO] SET 
    BADGENUMBER = ?, SSN = ?, NAME = ?, GENDER = ?, TITLE = ?, DEFAULTDEPTID = ?, employee_class = ?
    WHERE USERID = ?
    """, (badge, ssn, name, gender, title, defaultdept, employee_class, uid))
        conn.commit()
        conn.close()
        flash('Employee updated successfully!', 'success')
        return redirect(url_for('userinfo_list'))
    conn.close()
    return render_template('userinfo_form.html', user=user, depts=depts, positions=positions_list, classes=classes, action='Edit')

@app.route('/userinfo/view/<int:uid>')
@login_required
def userinfo_view(uid):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Fetch user data (basic info)
    cursor.execute("SELECT * FROM [AURAHR].[dbo].[USERINFO] WHERE USERID = ?", (uid,))
    user = cursor.fetchone()
    
    # Fetch department name
    dept_name = "N/A"
    if user and user.DEFAULTDEPTID:
         cursor.execute("SELECT DEPTNAME FROM [AURAHR].[dbo].[DEPARTMENTS] WHERE DEPTID = ?", (user.DEFAULTDEPTID,))
         d_row = cursor.fetchone()
         if d_row: dept_name = d_row[0]

    # Fetch Evaluations
    # FIXED: Removed Join on CycleID as it does not exist in Evaluations table
    cursor.execute("""
        SELECT E.*, U.Name as EvaluatorName
        FROM [AURAHR].[dbo].[Evaluations] E
        LEFT JOIN [AURAHR].[dbo].[Users] U ON E.EvaluatorUserID = U.UserID
        WHERE E.EmployeeUserID = ?
        ORDER BY E.EvaluationDate DESC
    """, (uid,))
    evaluations = cursor.fetchall()
    
    # Fetch Training History
    cursor.execute("""
        SELECT 
            COALESCE(TC.TrainingCourseText, 'جلسة محذوفة أو غير محددة') as CourseName,
            TS.SessionDate,
            TS.EndDate,
            TE.PassStatus,
            TE.Grade
        FROM [AURAHR].[dbo].[TrainingEnrollments] TE
        LEFT JOIN [AURAHR].[dbo].[TrainingSessions] TS ON TE.SessionID = TS.SessionID
        LEFT JOIN [AURAHR].[dbo].[TrainingCourses] TC ON TS.CourseID = TC.TrainingCourseID
        WHERE TE.EmployeeUserID = ?
        ORDER BY TS.SessionDate DESC
    """, (uid,))
    courses = cursor.fetchall()
    
    conn.close()
    return render_template('userinfo_view.html', user=user, dept_name=dept_name, evaluations=evaluations, courses=courses)


@app.route('/userinfo/archive/<int:uid>', methods=['POST'])
@admin_required
def userinfo_archive(uid):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get current info
        cursor.execute("SELECT BADGENUMBER, NAME, SSN, DEFAULTDEPTID, HIREDDAY FROM [AURAHR].[dbo].[USERINFO] WHERE USERID = ?", (uid,))
        row = cursor.fetchone()
        if not row:
            flash('User not found', 'danger')
            return redirect(url_for('userinfo_list'))
            
        old_badge = row.BADGENUMBER
        
        # Append _A to free up the badge
        new_badge_candidate = f"{old_badge}_A"
        if len(new_badge_candidate) > 24:
             new_badge_candidate = new_badge_candidate[:24]

        # Update UserInfo
        cursor.execute("UPDATE [AURAHR].[dbo].[USERINFO] SET IsActive = 0, BADGENUMBER = ? WHERE USERID = ?", (new_badge_candidate, uid))
        
        # Insert into EmployeeArchive
        reason_id = request.form.get('reason_id')
        note = request.form.get('note')
        
        if reason_id:
             cursor.execute("""
                 INSERT INTO [AURAHR].[dbo].[EmployeeArchive]
                 (UserID, Name, ArchivedSSN, ArchivedDeptID, HiredDay, EndDay, ArchiveReasonID, ArchiveComment, AdminUserID)
                 VALUES (?, ?, ?, ?, ?, GETDATE(), ?, ?, ?)
             """, (uid, row.NAME, row.SSN, row.DEFAULTDEPTID, row.HIREDDAY, reason_id, note, session.get('user_id')))

        conn.commit()
        log_system_action('Users', 'Archive', f'Archived User ID {uid}. Badge changed from {old_badge} to {new_badge_candidate}. ReasonID: {reason_id}')
        flash(f'✅ User archived successfully! Badge changed to {new_badge_candidate}', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'❌ Error archiving user: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('userinfo_list'))

@app.route('/userinfo/restore/<int:uid>', methods=['POST'])
@admin_required
def userinfo_restore(uid):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT BADGENUMBER FROM [AURAHR].[dbo].[USERINFO] WHERE USERID = ?", (uid,))
        row = cursor.fetchone()
        current_badge = row.BADGENUMBER # e.g. "100_A"
        
        # Try to restore original badge if it ends with _A
        new_badge = current_badge
        if current_badge.endswith('_A'):
            possible_original = current_badge[:-2]
            
            # Check if this original badge is taken
            cursor.execute("SELECT COUNT(*) FROM [AURAHR].[dbo].[USERINFO] WHERE BADGENUMBER = ?", (possible_original,))
            if cursor.fetchone()[0] == 0:
                new_badge = possible_original
            else:
                flash(f'⚠️ Original badge "{possible_original}" is taken. Restoring with current badge "{current_badge}". Please update manually.', 'warning')
        
        cursor.execute("UPDATE [AURAHR].[dbo].[USERINFO] SET IsActive = 1, BADGENUMBER = ? WHERE USERID = ?", (new_badge, uid))
        conn.commit()
        log_system_action('Users', 'Restore', f'Restored User ID {uid}. Badge updated to {new_badge}')
        flash('✅ User restored successfully!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'❌ Error restoring user: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('recruitment_archive'))

@app.route('/userinfo/archived')
@admin_required
def userinfo_archived_list():
    return redirect(url_for('recruitment_archive'))

@app.route('/userinfo/archive/update/<int:uid>', methods=['POST'])
@admin_required
def userinfo_archive_update(uid):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get Form Data
        hired_day = request.form.get('hired_day') or None
        dept_id = request.form.get('dept_id') or None
        end_day = request.form.get('end_day') or None
        reason_id = request.form.get('reason_id') or None
        
        # 1. Update USERINFO
        cursor.execute("UPDATE [AURAHR].[dbo].[USERINFO] SET HIREDDAY = ?, DEFAULTDEPTID = ? WHERE USERID = ?", (hired_day, dept_id, uid))
        
        # 2. Update EmployeeArchive
        # First, determine the TypeID associated with the selected ReasonID
        type_id = None
        if reason_id:
            cursor.execute("SELECT TypeID FROM [AURAHR].[dbo].[TerminationReasons] WHERE ReasonID = ?", (reason_id,))
            row = cursor.fetchone()
            if row:
                type_id = row[0]

        # Check if record exists first
        cursor.execute("SELECT COUNT(*) FROM [AURAHR].[dbo].[EmployeeArchive] WHERE UserID = ?", (uid,))
        if cursor.fetchone()[0] > 0:
            cursor.execute("""
                UPDATE [AURAHR].[dbo].[EmployeeArchive] 
                SET EndDay = ?, ArchiveReasonID = ?, ArchiveTypeID = ? 
                WHERE UserID = ?
            """, (end_day, reason_id, type_id, uid))
        else:
            # If for some reason missing, we skip.
            pass

        conn.commit()
        log_system_action('Users', 'Update Archive', f'Updated Archive Info for User {uid}')
        flash('✅ Archive information updated successfully!', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'❌ Error updating archive info: {e}', 'danger')
    finally:
        conn.close()
        
    return redirect(url_for('recruitment_archive'))


@app.route('/roles')
@login_required
def roles():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT RoleID, RoleName FROM [AURAHR].[dbo].[Roles] ORDER BY RoleID")
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
        cursor.execute("INSERT INTO [AURAHR].[dbo].[Roles] (RoleName) VALUES (?)", (name,))
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
    cursor.execute("SELECT RoleID, RoleName FROM [AURAHR].[dbo].[Roles] WHERE RoleID = ?", (rid,))
    role = cursor.fetchone()
    if request.method == 'POST':
        name = request.form['rolename']
        cursor.execute("UPDATE [AURAHR].[dbo].[Roles] SET RoleName = ? WHERE RoleID = ?", (name, rid))
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
    cursor.execute("DELETE FROM [AURAHR].[dbo].[Roles] WHERE RoleID = ?", (rid,))
    conn.commit()
    conn.close()
    flash('Role deleted successfully!', 'info')
    return redirect(url_for('roles'))

@app.route('/admin/classes')
@admin_required
def classes_list():
    classes = get_all_classes()
    return render_template('classes_list.html', classes=classes)

@app.route('/admin/classes/add', methods=['POST'])
@admin_required
def classes_add():
    class_name = request.form.get('class_name', '').strip()
    display_name = request.form.get('display_name', '').strip()
    
    if not class_name:
        flash('❌ يرجى إدخال رمز الفئة', 'danger')
        return redirect(url_for('classes_list'))
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Check uniqueness
        cursor.execute("SELECT Count(*) FROM [AURAHR].[dbo].[EmployeeClasses] WHERE ClassName = ?", (class_name,))
        if cursor.fetchone()[0] > 0:
            flash(f'❌ الفئة "{class_name}" موجودة بالفعل.', 'danger')
        else:
            cursor.execute("INSERT INTO [AURAHR].[dbo].[EmployeeClasses] (ClassName, DisplayName) VALUES (?, ?)", (class_name, display_name or class_name))
            conn.commit()
            flash('✅ تم إضافة الفئة بنجاح.', 'success')
        conn.close()
    except Exception as e:
        flash(f'❌ خطأ: {e}', 'danger')
        
    return redirect(url_for('classes_list'))

@app.route('/admin/logs')
@admin_required
def logs_dashboard():
    # 1. Filters
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    username = request.args.get('username', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    module = request.args.get('module', '')
    action_type = request.args.get('action_type', '')
    
    limit = 50
    offset = (page - 1) * limit
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 2. Build Query
    where_clauses = ["1=1"]
    params = []
    
    if search:
        where_clauses.append("(Description LIKE ? OR Username LIKE ?)")
        params.extend([f'%{search}%', f'%{search}%'])
        
    if username:
        where_clauses.append("Username = ?")
        params.append(username)

    if module:
        where_clauses.append("Module = ?")
        params.append(module)
        
    if action_type:
        where_clauses.append("ActionType = ?")
        params.append(action_type)
        
    if date_from:
        where_clauses.append("CAST(Timestamp AS DATE) >= ?")
        params.append(date_from)
        
    if date_to:
        where_clauses.append("CAST(Timestamp AS DATE) <= ?")
        params.append(date_to)
        
    where_sql = " AND ".join(where_clauses)
    
    # 3. KPIs
    # Total Logs
    cursor.execute(f"SELECT COUNT(*) FROM AppLogs WHERE {where_sql}", params)
    total_logs = cursor.fetchone()[0]
    total_pages = (total_logs + limit - 1) // limit
    
    # Active Users
    cursor.execute("SELECT DISTINCT Username FROM AppLogs WHERE Username IS NOT NULL ORDER BY Username")
    all_usernames = [row[0] for row in cursor.fetchall()]
    
    # Active Users (Filtered)
    cursor.execute(f"SELECT COUNT(DISTINCT Username) FROM AppLogs WHERE {where_sql}", params)
    active_users = cursor.fetchone()[0]
    
    # Today Actions
    cursor.execute("SELECT COUNT(*) FROM AppLogs WHERE CAST(Timestamp AS DATE) = CAST(GETDATE() AS DATE)")
    today_actions = cursor.fetchone()[0]
    
    # 4. Chart Data
    cursor.execute("""
        SELECT TOP 7 
            FORMAT(Timestamp, 'MM-dd') as Day, 
            COUNT(*) as Count 
        FROM AppLogs 
        GROUP BY FORMAT(Timestamp, 'MM-dd') 
        ORDER BY Day DESC
    """)
    chart_rows = cursor.fetchall()
    chart_data = {
        'labels': [row.Day for row in reversed(chart_rows)],
        'data': [row.Count for row in reversed(chart_rows)]
    }
    
    # 5. Fetch Logs
    query = f"""
        SELECT * FROM AppLogs 
        WHERE {where_sql} 
        ORDER BY Timestamp DESC 
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """
    params.extend([offset, limit])
    
    cursor.execute(query, params)
    logs = cursor.fetchall()
    
    conn.close()
    
    from datetime import datetime
    return render_template('logs_dashboard.html',
                           logs=logs,
                           total_logs=total_logs,
                           total_pages=total_pages,
                           current_page=page,
                           active_users=active_users,
                           today_actions=today_actions,
                           all_usernames=all_usernames,
                           today_date=datetime.now().strftime('%Y-%m-%d'),
                           chart_data=chart_data,
                           modules=['Recruitment', 'Training', 'Evaluations', 'Access', 'Users', 'Settings'],
                           action_types=['Login', 'Create', 'Update', 'Delete', 'Archive', 'Restore', 'Other'])

@app.route('/admin/classes/delete/<int:id>', methods=['POST'])
@admin_required
def classes_delete(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if it's a core class, although UI prevents it, secure backend too
        cursor.execute("SELECT ClassName FROM [AURAHR].[dbo].[EmployeeClasses] WHERE ClassID = ?", (id,))
        row = cursor.fetchone()
        if row and row.ClassName in ['A', 'B', 'C', 'مشرف', 'مدير']:
            flash('⚠️ لا يمكن حذف الفئات الأساسية للنظام.', 'warning')
        else:
            cursor.execute("DELETE FROM [AURAHR].[dbo].[EmployeeClasses] WHERE ClassID = ?", (id,))
            conn.commit()
            flash('✅ تم حذف الفئة بنجاح.', 'success')
            
        conn.close()
    except Exception as e:
        flash(f'❌ خطأ: {e}', 'danger')
        
    return redirect(url_for('classes_list'))

@app.route('/departments/manage')
@login_required
def departments_manage():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME, SUPDEPTID FROM [AURAHR].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
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
            cursor.execute("SELECT MAX(DEPTID) FROM [AURAHR].[dbo].[DEPARTMENTS]")
            row = cursor.fetchone()
            # If table is empty, start at 1, otherwise add 1 to the max ID
            new_dept_id = (row[0] or 0) + 1
            
            # 2. Insert with the manually generated DEPTID
            cursor.execute("""
                INSERT INTO [AURAHR].[dbo].[DEPARTMENTS] (DEPTID, DEPTNAME, SUPDEPTID) 
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
    cursor.execute("SELECT DEPTID, DEPTNAME, SUPDEPTID FROM [AURAHR].[dbo].[DEPARTMENTS] WHERE DEPTID = ?", (did,))
    dept = cursor.fetchone()
    if request.method == 'POST':
        name = request.form['deptname']
        sup = request.form.get('supdeptid') or None
        cursor.execute("UPDATE [AURAHR].[dbo].[DEPARTMENTS] SET DEPTNAME = ?, SUPDEPTID = ? WHERE DEPTID = ?", (name, sup, did))
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
    cursor.execute("DELETE FROM [AURAHR].[dbo].[DEPARTMENTS] WHERE DEPTID = ?", (did,))
    conn.commit()
    conn.close()
    flash('Department deleted successfully!', 'info')
    return redirect(url_for('departments_manage'))


@app.route('/recommendations')
@admin_required
def recommendations_list():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT R.RecommendationID, R.RecommendationText, R.AppliesToDeptID, D.DEPTNAME FROM [AURAHR].[dbo].[Recommendations] R LEFT JOIN [AURAHR].[dbo].[DEPARTMENTS] D ON R.AppliesToDeptID = D.DEPTID ORDER BY R.RecommendationID")
    recommendations = cursor.fetchall()
    conn.close()
    return render_template('recommendations_list.html', recommendations=recommendations)

@app.route('/recommendations/add', methods=['GET', 'POST'])
@admin_required
def recommendations_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [AURAHR].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    departments = cursor.fetchall()
    if request.method == 'POST':
        text = request.form['text']
        dept_id = request.form.get('dept_id')
        dept_id = int(dept_id) if dept_id else None
        try:
            cursor.execute("INSERT INTO [AURAHR].[dbo].[Recommendations] (RecommendationText, AppliesToDeptID) VALUES (?, ?)", (text, dept_id))
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
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [AURAHR].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    departments = cursor.fetchall()
    cursor.execute("SELECT * FROM [AURAHR].[dbo].[Recommendations] WHERE RecommendationID = ?", (rid,))
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
            cursor.execute("UPDATE [AURAHR].[dbo].[Recommendations] SET RecommendationText = ?, AppliesToDeptID = ? WHERE RecommendationID = ?", (text, dept_id, rid))
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
        cursor.execute("SELECT COUNT(*) as cnt FROM [AURAHR].[dbo].[Evaluations] WHERE RecommendationID = ?", (rid,))
        if cursor.fetchone().cnt > 0:
            flash('لا يمكن حذف توصية مستخدمة في تقييمات سابقة.', 'danger')
        else:
            cursor.execute("DELETE FROM [AURAHR].[dbo].[Recommendations] WHERE RecommendationID = ?", (rid,))
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
    # 1. Fetch Criteria (No Join on Departments)
    cursor.execute("SELECT CriteriaID, CriteriaName, CriteriaWeight, MaxScore, AppliesToDeptID, employee_class FROM [AURAHR].[dbo].[EvaluationCriteria] ORDER BY CriteriaID")
    criteria_rows = cursor.fetchall()
    
    # 2. Fetch Departments Reference
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [AURAHR].[dbo].[DEPARTMENTS]")
    depts_rows = cursor.fetchall()
    dept_map = {d.DEPTID: d.DEPTNAME for d in depts_rows}
    
    # conn.close() Moved to end

    # 3. Process Data (Convert to dicts and map Dept Names)
    criteria = []
    for row in criteria_rows:
        c_dict = {
            'CriteriaID': row.CriteriaID,
            'CriteriaName': row.CriteriaName,
            'CriteriaWeight': row.CriteriaWeight,
            'MaxScore': row.MaxScore,
            'employee_class': row.employee_class
        }
        
        # Resolve Dept Names
        if not row.AppliesToDeptID:
            c_dict['DEPTNAME'] = 'عام (كل الأقسام)'
        else:
            try:
                # Split CSV, map to names, join
                ids = [int(x) for x in str(row.AppliesToDeptID).split(',') if x.strip()]
                names = [dept_map.get(dept_id, '?') for dept_id in ids]
                c_dict['DEPTNAME'] = '، '.join(names)
            except:
                c_dict['DEPTNAME'] = row.AppliesToDeptID # Fallback
                
                
        criteria.append(c_dict)

    # 3B. Fetch Linked Types for Display
    # Efficiently fetch all links and map in Python
    cursor.execute("""
        SELECT ETC.CriteriaID, ET.DisplayName 
        FROM [AURAHR].[dbo].[EvaluationTypeCriteria] ETC
        JOIN [AURAHR].[dbo].[EvaluationTypes] ET ON ETC.EvaluationTypeID = ET.EvaluationTypeID
    """)
    links = cursor.fetchall()
    
    # Map CriteriaID -> List of Type Names
    type_map = defaultdict(list)
    for l in links:
        type_map[l.CriteriaID].append(l.DisplayName)
        
    # Attach to criteria list
    for c in criteria:
        if c['CriteriaID'] in type_map:
            c['Types'] = ", ".join(type_map[c['CriteriaID']])
        else:
            c['Types'] = "None"

    # 4. Fetch Classes for Filter
    classes = get_all_classes()

    conn.close()
    return render_template('criteria_list.html', criteria=criteria, classes=classes, departments=depts_rows)

@app.route('/evaluation/criteria/add', methods=['GET', 'POST'])
@admin_required
def criteria_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DEPTID, DEPTNAME FROM [AURAHR].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
        departments = cursor.fetchall()
        
        cursor.execute("SELECT EvaluationTypeID, DisplayName FROM [AURAHR].[dbo].[EvaluationTypes] ORDER BY SortOrder")
        all_types = cursor.fetchall()

        classes = get_all_classes() 
        
        if request.method == 'POST':
            name = request.form['name']
            weight = request.form['weight']
            max_score = request.form.get('max_score', 10)
            
            # Handle Types
            type_ids = request.form.getlist('type_ids')
            
            # --- Handle Multiple Departments ---
            dept_ids_list = request.form.getlist('dept_ids')
            if not dept_ids_list or '' in dept_ids_list:
                 applies_to_dept = None
            else:
                 clean_ids = [x for x in dept_ids_list if x.strip()]
                 applies_to_dept = ','.join(clean_ids) if clean_ids else None

            employee_levels = request.form.getlist('employee_levels')
            employee_class = ','.join(employee_levels) if employee_levels else 'لم تضاف'
            
            try:
                weight_float = float(weight)
                max_score_int = int(max_score)
                if not (0 < weight_float <= 1):
                    raise ValueError("Weight must be between 0 and 1 (e.g., 0.20 for 20%)")
                if max_score_int <= 0:
                     raise ValueError("Max score must be positive")
                if not employee_levels:
                    raise ValueError("Please select at least one employee level")
                    
                cursor.execute("INSERT INTO [AURAHR].[dbo].[EvaluationCriteria] (CriteriaName, CriteriaWeight, MaxScore, AppliesToDeptID, employee_class) OUTPUT INSERTED.CriteriaID VALUES (?, ?, ?, ?, ?)", (name, weight_float, max_score_int, applies_to_dept, employee_class))
                new_criteria_id = cursor.fetchone().CriteriaID
                
                # Insert Type Links
                if type_ids:
                    link_values = [(int(t), new_criteria_id) for t in type_ids]
                    cursor.executemany("INSERT INTO [AURAHR].[dbo].[EvaluationTypeCriteria] (EvaluationTypeID, CriteriaID) VALUES (?, ?)", link_values)
                
                conn.commit()
                flash('✅ Criterion added successfully!', 'success')
                return redirect(url_for('criteria_list'))
            except ValueError as e:
                flash(f'Invalid input: {e}', 'danger')
                # No need to return here, just fall through to render template
            except Exception as e:
                conn.rollback()
                flash(f'❌ Database error: {e}', 'danger')

        return render_template('criteria_form.html', departments=departments, classes=classes, all_types=all_types, action='Add')
    finally:
        conn.close()

@app.route('/evaluation/criteria/edit/<int:cid>', methods=['GET', 'POST'])
@admin_required
def criteria_edit(cid):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DEPTID, DEPTNAME FROM [AURAHR].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
        departments = cursor.fetchall()
        cursor.execute("SELECT * FROM [AURAHR].[dbo].[EvaluationCriteria] WHERE CriteriaID = ?", (cid,))
        row = cursor.fetchone()
        if not row:
            flash('Criterion not found!', 'warning')
            return redirect(url_for('criteria_list'))
        
        selected_depts = []
        if row.AppliesToDeptID:
            selected_depts = [x.strip() for x in str(row.AppliesToDeptID).split(',') if x.strip()]

        cursor.execute("SELECT EvaluationTypeID FROM [AURAHR].[dbo].[EvaluationTypeCriteria] WHERE CriteriaID = ?", (cid,))
        selected_type_ids = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT EvaluationTypeID, DisplayName FROM [AURAHR].[dbo].[EvaluationTypes] ORDER BY SortOrder")
        all_types = cursor.fetchall()

        classes = get_all_classes() 
        
        if request.method == 'POST':
            name = request.form['name']
            weight = request.form['weight']
            max_score = request.form.get('max_score', 10)
            
            # Handle Types
            type_ids = request.form.getlist('type_ids')

            dept_ids_list = request.form.getlist('dept_ids')
            if not dept_ids_list or '' in dept_ids_list:
                 applies_to_dept = None
            else:
                 clean_ids = [x for x in dept_ids_list if x.strip()]
                 applies_to_dept = ','.join(clean_ids) if clean_ids else None

            employee_levels = request.form.getlist('employee_levels')
            employee_class = ','.join(employee_levels) if employee_levels else 'لم تضاف'
            try:
                weight_float = float(weight)
                max_score_int = int(max_score)
                if not (0 < weight_float <= 1):
                    raise ValueError("Weight must be between 0 and 1 (e.g., 0.20 for 20%)")
                if max_score_int <= 0:
                     raise ValueError("Max score must be positive")
                if not employee_levels:
                    raise ValueError("Please select at least one employee level")
                
                cursor.execute("UPDATE [AURAHR].[dbo].[EvaluationCriteria] SET CriteriaName = ?, CriteriaWeight = ?, MaxScore = ?, AppliesToDeptID = ?, employee_class = ? WHERE CriteriaID = ?", (name, weight_float, max_score_int, applies_to_dept, employee_class, cid))
                
                # Update Links (Delete all, re-insert)
                cursor.execute("DELETE FROM [AURAHR].[dbo].[EvaluationTypeCriteria] WHERE CriteriaID = ?", (cid,))
                if type_ids:
                    link_values = [(int(t), cid) for t in type_ids]
                    cursor.executemany("INSERT INTO [AURAHR].[dbo].[EvaluationTypeCriteria] (EvaluationTypeID, CriteriaID) VALUES (?, ?)", link_values)

                conn.commit()
                flash('✅ Criterion updated successfully!', 'success')
                return redirect(url_for('criteria_list'))
            except ValueError as e:
                flash(f'Invalid input: {e}', 'danger')
                # Fall through
            except Exception as e:
                conn.rollback()
                flash(f'❌ Database error: {e}', 'danger')

        return render_template('criteria_form.html', departments=departments, criterion=row, classes=classes, selected_depts=selected_depts, all_types=all_types, selected_type_ids=selected_type_ids, action='Edit')
    finally:
        conn.close()

@app.route('/evaluation/criteria/delete/<int:cid>', methods=['POST'])
@admin_required
def criteria_delete(cid):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) as cnt FROM [AURAHR].[dbo].[EvaluationDetails] WHERE CriteriaID = ?", (cid,))
        usage_count = cursor.fetchone().cnt
        if usage_count > 0:
            flash('Cannot delete criterion, it is used in existing evaluations.', 'danger')
        else:
            cursor.execute("DELETE FROM [AURAHR].[dbo].[EvaluationCriteria] WHERE CriteriaID = ?", (cid,))
            conn.commit()
            flash('Criterion deleted successfully!', 'info')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting criterion: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('criteria_list'))



@app.route('/userinfo/sync', methods=['POST'])
@admin_required
def userinfo_sync():
    print(">>> CALLING userinfo_sync")
    if not is_admin():
         return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    local_conn = None
    remote_conn = None
    
    try:
        # 1. Local Connection
        local_conn = get_db_connection()
        local_cursor = local_conn.cursor()
        print(">>> LOCAL CONNECTED")
        
        # 2. Remote Connection
        # We confirmed Driver 17 is installed
        REMOTE_STR = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=192.168.50.5;"
            "DATABASE=Zktime;"
            "UID=sa;"
            "PWD=comsys@123;"
            "TrustServerCertificate=yes;"
            "Timeout=10;"
        )
        print(f">>> CONNECTING REMOTE: {REMOTE_STR}")
        remote_conn = pyodbc.connect(REMOTE_STR)
        remote_cursor = remote_conn.cursor()
        print(">>> REMOTE CONNECTED")

        # 3. Existing IDs
        local_cursor.execute("SELECT USERID FROM [AURAHR].[dbo].[USERINFO]")
        existing_ids = set(row[0] for row in local_cursor.fetchall())
        
        # 4. Fetch Remote
        remote_cursor.execute("SELECT USERID, BADGENUMBER, SSN, NAME, GENDER, TITLE, DEFAULTDEPTID, HIREDDAY FROM [Zktime].[dbo].[USERINFO]")
        remote_users = remote_cursor.fetchall()
        
        missing = [u for u in remote_users if u.USERID not in existing_ids]
        
        details = []
        added = 0
        
        if missing:
            local_cursor.execute("SET IDENTITY_INSERT [AURAHR].[dbo].[USERINFO] ON")
            for u in missing:
                try:
                    local_cursor.execute("""
                        INSERT INTO [AURAHR].[dbo].[USERINFO] 
                        (USERID, BADGENUMBER, SSN, NAME, GENDER, TITLE, DEFAULTDEPTID, HIREDDAY, employee_class) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'لم تضاف')
                    """, (u.USERID, u.BADGENUMBER, u.SSN, u.NAME, u.GENDER, u.TITLE, u.DEFAULTDEPTID, u.HIREDDAY))
                    added += 1
                    details.append(f"Added: {u.NAME}")
                except Exception as e_row:
                    details.append(f"Row Error {u.USERID}: {e_row}")
            local_cursor.execute("SET IDENTITY_INSERT [AURAHR].[dbo].[USERINFO] OFF")
            local_conn.commit()
        else:
            details.append("No new users found.")
            
        print(">>> SYNC COMPLETE")
        return jsonify({'status': 'success', 'added_count': added, 'details': details})

    except Exception as e:
        print(f">>> CRITICAL SYNC ERROR: {e}")
        # Return 200 with error details so JS can read it
        return jsonify({'status': 'error', 'message': f"Sync Error: {str(e)}", 'trace': str(e)}), 200
    finally:
        try:
            if local_conn: local_conn.close()
            if remote_conn: remote_conn.close()
        except: pass

@app.route('/userinfo/import', methods=['POST'])
@admin_required
def userinfo_import():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No file selected'})

    conn = None
    try:
        # Read file using Pandas
        # Expected columns in Excel/CSV: USERID, BADGENUMBER, SSN, NAME, GENDER, TITLE, DEFAULTDEPTID, HIREDDAY
        # We try to be flexible with column names (case insensitive)
        
        filename = file.filename.lower()
        if filename.endswith('.csv'):
            df = pd.read_csv(file)
        elif filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file)
        else:
             return jsonify({'status': 'error', 'message': 'Invalid file type. Use .csv or .xlsx'})
             
        # Normalize columns to uppercase
        df.columns = [c.upper().strip() for c in df.columns]
        
        required_cols = ['USERID', 'NAME'] 
        # Check basic requirements
        for col in required_cols:
            if col not in df.columns:
                 return jsonify({'status': 'error', 'message': f'Missing required column: {col}'})

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get existing IDs
        cursor.execute("SELECT USERID FROM [AURAHR].[dbo].[USERINFO]")
        existing_ids = set(row[0] for row in cursor.fetchall())
        
        added_count = 0
        details = []
        
        cursor.execute("SET IDENTITY_INSERT [AURAHR].[dbo].[USERINFO] ON")
        
        for index, row in df.iterrows():
            uid = int(row['USERID'])
            if uid in existing_ids:
                continue # Skip existing
            
            try:
                # Helper functions for sanitization
                def clean_str(val):
                    if pd.isna(val) or val is None or str(val).strip() == '':
                        return None
                    return str(val).strip()

                def clean_int(val, default=1):
                    if pd.isna(val) or val is None or str(val).strip() == '':
                        return default
                    try:
                        return int(float(val))
                    except:
                        return default

                # Safely get other fields or Default
                badge = clean_str(row.get('BADGENUMBER'))
                ssn = clean_str(row.get('SSN'))
                name = row.get('NAME')
                gender = clean_str(row.get('GENDER'))
                title = clean_str(row.get('TITLE'))
                dept = clean_int(row.get('DEFAULTDEPTID'), 1)
                
                hired = row.get('HIREDDAY')
                if pd.isna(hired) or str(hired).strip() == '':
                    hired = None
                
                cursor.execute("""
                    INSERT INTO [AURAHR].[dbo].[USERINFO] 
                    (USERID, BADGENUMBER, SSN, NAME, GENDER, TITLE, DEFAULTDEPTID, HIREDDAY, employee_class) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'لم تضاف')
                """, (uid, badge, ssn, name, gender, title, dept, hired))
                
                added_count += 1
                details.append(f"Added: {name}")
            except Exception as e_row:
                details.append(f"Error Row {index}: {e_row}")
                
        cursor.execute("SET IDENTITY_INSERT [AURAHR].[dbo].[USERINFO] OFF")
        conn.commit()
        
        return jsonify({'status': 'success', 'added_count': added_count, 'details': details})

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'status': 'error', 'message': f"Import Error: {str(e)}"}), 200
    finally:
        if conn: conn.close()



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
        cursor.execute("SELECT DepartmentID FROM [AURAHR].[dbo].[Users] WHERE UserID = ?", (evaluator_user_id,))
        user_record = cursor.fetchone()
        manager_dept_id = user_record.DepartmentID if user_record else None
        
        if manager_dept_id:
            # UPDATED QUERY: Now selects UI.BADGENUMBER
            query = "SELECT UI.USERID, UI.NAME, UI.TITLE, UI.PositionID, P.PositionName, D.DEPTNAME, UI.BADGENUMBER FROM [AURAHR].[dbo].[USERINFO] UI LEFT JOIN [dbo].[POSITIONS] P ON UI.PositionID = P.PositionID LEFT JOIN [dbo].[DEPARTMENTS] D ON UI.DEFAULTDEPTID = D.DEPTID WHERE UI.DEFAULTDEPTID = ? AND UI.USERID != ?"
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
        query = "SELECT U.UserID, U.Name, U.Username, U.DepartmentID, D.DEPTNAME, UI.BADGENUMBER FROM [AURAHR].[dbo].[Users] U LEFT JOIN [dbo].[DEPARTMENTS] D ON U.DepartmentID = D.DEPTID LEFT JOIN [AURAHR].[dbo].[USERINFO] UI ON U.UserID = UI.USERID WHERE U.RoleID = 3 AND U.UserID != ?"
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
    cursor.execute("SELECT DepartmentID FROM [AURAHR].[dbo].[Users] WHERE UserID = ?", (evaluator_user_id,))
    manager_record = cursor.fetchone()
    manager_dept_id = manager_record.DepartmentID if manager_record else None

    # Variables for the target employee's information
    employee_info = None
    target_user_dept_id = None
    employee_user_id = None  

    is_manager = request.args.get('is_manager', 'false').lower() == 'true'

    # 2. Employee Lookup based on BADGENUMBER
    # 2. Employee Lookup based on BADGENUMBER
    # For Officers (Role 2) evaluating Managers (who are just Employees in UserInfo with 'Manager' class)
    # OR for Managers (Role 3) evaluating their team.
    
    # We essentially want the same UserInfo lookup for both, but with different permission checks.
    
    cursor.execute("""
        SELECT UI.USERID, UI.NAME, UI.DEFAULTDEPTID, UI.TITLE, D.DEPTNAME, UI.employee_class,
                (SELECT COUNT(*) FROM TrainingEnrollments TE WHERE TE.EmployeeUserID = UI.USERID) AS TotalSessions
        FROM [AURAHR].[dbo].[USERINFO] UI
        LEFT JOIN [dbo].[DEPARTMENTS] D ON UI.DEFAULTDEPTID = D.DEPTID
        WHERE UI.BADGENUMBER = ?
    """, (badgenumber_str,))
    employee_info = cursor.fetchone()

    if employee_info:
        employee_user_id = employee_info.USERID
        
    # Validation logic specific to roles
    if employee_info:
        # If Officer (Role 2), ensure target is in same department & is Manager/Supervisor
        if role_id == 2:
            if manager_dept_id and employee_info.DEFAULTDEPTID != manager_dept_id:
                 flash('⚠️ هذا المدير ليس في قسمك.', 'danger')
                 return redirect(url_for('select_user_for_evaluation'))
                 
            # Optional: Ensure they are actually a Manager/Supervisor class
            # classes = employee_info.employee_class or ''
            # if 'مدير' not in classes and 'مشرف' not in classes and 'Manager' not in classes:
            #    flash('⚠️ هذا الموظف ليس مديراً.', 'warning')
            #    return redirect(url_for('select_user_for_evaluation'))

        # If Manager (Role 3), ensure target is in same department (already checked below but good to keep clean)
        elif role_id == 3:
             pass # Will be checked in step 3
    
    # (Skip the old big if/else block)

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
    
    # --- MODIFIED CRITERIA FILTERING FOR MULTI-DEPT ---
    # Fetch ALL criteria matching the class (ignoring dept in SQL for now)
    
    criteria_query = f"SELECT CriteriaID, CriteriaName, CriteriaWeight, MaxScore, AppliesToDeptID FROM [AURAHR].[dbo].[EvaluationCriteria] WHERE {class_clause} ORDER BY CriteriaID"
    # We remove (AppliesToDeptID = ? OR AppliesToDeptID IS NULL) from SQL because we need to check CSV in Python
    
    cursor.execute(criteria_query, class_params)
    all_class_criteria = cursor.fetchall()

    # Filter by Department in Python
    criteria = []
    for c in all_class_criteria:
        # Rules:
        # 1. If AppliesToDeptID is None => General (Keep)
        # 2. If AppliesToDeptID contains employee_dept_id => Keep
        
        keep = False
        if not c.AppliesToDeptID:
            keep = True
        else:
            # Check if employee_dept_id is in the CSV list
            try:
                allowed_depts = [int(x.strip()) for x in str(c.AppliesToDeptID).split(',') if x.strip()]
                if employee_dept_id in allowed_depts:
                    keep = True
            except:
                pass # If parsing fail, ignore
        
        if keep:
            criteria.append(c)

    if not criteria:
        flash(f'⚠️ لم يتم تعريف معايير تقييم للفئة "{employee_class_string}" في هذا القسم.', 'warning')
        conn.close()
        return redirect(url_for('select_user_for_evaluation'))

    cursor.execute("SELECT RecommendationID, RecommendationText FROM [AURAHR].[dbo].[Recommendations] WHERE AppliesToDeptID = ? OR AppliesToDeptID IS NULL ORDER BY RecommendationText", (employee_dept_id,))
    recommendations = cursor.fetchall()
    
    cursor.execute("""
        SELECT TrainingCourseID, TrainingCourseText 
        FROM [AURAHR].[dbo].[TrainingCourses] 
        WHERE (AppliesToDeptID = ? OR AppliesToDeptID IS NULL) 
        AND IsActive = 1 
        ORDER BY TrainingCourseText
    """, (employee_dept_id,))
    training_courses = cursor.fetchall()
    
    available_evals = get_available_evaluation_types(conn, employee_user_id, manager_dept_id)
    
    # 5B. Handle Eval Type Selection (Refined Logic)
    selected_eval_type_id = request.args.get('eval_type_id')
    selected_eval_type_id = int(selected_eval_type_id) if selected_eval_type_id and selected_eval_type_id.isdigit() else None

    # Filter Criteria based on Selected Type
    final_criteria = []
    
    if selected_eval_type_id:
        # Check if valid type
        valid_type = any(e['id'] == selected_eval_type_id for e in available_evals)
        # Note: We might want to allow viewing criteria even if disabled (e.g. for review), but for NEW evaluation, it should be enabled.
        # However, let's just filter for now.
        
        # Helper list of criteria IDs linked to this type
        cursor.execute("SELECT CriteriaID FROM [AURAHR].[dbo].[EvaluationTypeCriteria] WHERE EvaluationTypeID = ?", (selected_eval_type_id,))
        linked_criteria_ids = {row[0] for row in cursor.fetchall()}
        
        # If no specific links exist (legacy support), maybe show all? 
        # But we seeded links, so we should rely on links.
        # If links exist, we intersect.
        
        if not linked_criteria_ids:
            # Fallback: If table empty for this type, show NOTHING or ALL?
            # User wants "different" evaluations. So showing NOTHING is correct if not configured.
            pass
        else:
            for c in criteria:
                if c.CriteriaID in linked_criteria_ids:
                    final_criteria.append(c)
    else:
        # If no type selected, show NO criteria (force selection)
        final_criteria = []

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

            cursor.execute("INSERT INTO [AURAHR].[dbo].[Evaluations] (EmployeeUserID, EvaluatorUserID, EvaluationTypeID, ManagerComments, RecommendationID, TrainingCourseID) OUTPUT INSERTED.EvaluationID VALUES (?, ?, ?, ?, ?, ?)", (employee_user_id, evaluator_user_id, eval_type_id, comments, recommendation_id, training_course_id))
            evaluation_id = cursor.fetchone().EvaluationID

            total_weighted_score = 0.0
            total_max_weighted_score = 0.0
            scores_data = []

            total_weighted_score = 0.0
            total_max_weighted_score = 0.0
            scores_data = []

            # Re-fetch criteria for validation (security) to ensure we check against what was actually valid for this type
            # We can reuse the logic above efficiently if we trust the form, but double checking is better.
            # Simplified: We just iterate over the form keys that match criteria pattern, 
            # OR better, re-run the filter logic.
            
            # Re-filter 'criteria' list based on submitted ID
            validation_criteria_ids = set()
            cursor.execute("SELECT CriteriaID FROM [AURAHR].[dbo].[EvaluationTypeCriteria] WHERE EvaluationTypeID = ?", (eval_type_id,))
            linked_ids = {row[0] for row in cursor.fetchall()}
            
            valid_criteria_for_type = [c for c in criteria if c.CriteriaID in linked_ids]
            
            for item in valid_criteria_for_type:
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
                cursor.executemany("INSERT INTO [AURAHR].[dbo].[EvaluationDetails] (EvaluationID, CriteriaID, ScoreGiven) VALUES (?, ?, ?)", scores_data)

            final_percentage = (total_weighted_score / total_max_weighted_score) * 100 if total_max_weighted_score > 0 else 0
            final_rating = get_rating_from_score(final_percentage)

            cursor.execute("UPDATE [AURAHR].[dbo].[Evaluations] SET OverallScore = ?, OverallRating = ? WHERE EvaluationID = ?", (final_percentage, final_rating, evaluation_id))
            
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
                           criteria=final_criteria, 
                           selected_eval_type_id=selected_eval_type_id, 
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
    taken_course_id = request.args.get('taken_course_id', '')
    overall_rating = request.args.get('overall_rating', '')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        role_id = session.get('role_id')
        user_id = session.get('user_id')
        cursor.execute("SELECT RecommendationID, RecommendationText FROM [AURAHR].[dbo].[Recommendations] ORDER BY RecommendationText")
        all_recommendations = cursor.fetchall()
        cursor.execute("SELECT TrainingCourseID, TrainingCourseText FROM [AURAHR].[dbo].[TrainingCourses] ORDER BY TrainingCourseText")
        all_training_courses = cursor.fetchall()
        cursor.execute("SELECT EvaluationTypeID, DisplayName FROM [AURAHR].[dbo].[EvaluationTypes] ORDER BY SortOrder")
        all_evaluation_types = cursor.fetchall()
        query = """
            SELECT E.EvaluationID, E.EvaluationDate, COALESCE(ET.DisplayName, E.EvaluationType) as EvaluationType,
                E.OverallScore, E.OverallRating, E.ManagerComments, E.EmployeeUserID,
                COALESCE(EmpInfo.NAME, EmpUser.Name, EmpUser.Username) AS EmployeeName, 
                COALESCE(Mgr.Name, Mgr.Username) AS EvaluatorName, EmpInfo.employee_class,
                R.RecommendationText, TC.TrainingCourseText,
                (
                    SELECT STUFF((
                        SELECT '###' + TC_Sub.TrainingCourseText
                        FROM [AURAHR].[dbo].[TrainingEnrollments] TE_Sub 
                        JOIN [AURAHR].[dbo].[TrainingSessions] TS_Sub ON TE_Sub.SessionID = TS_Sub.SessionID
                        JOIN [AURAHR].[dbo].[TrainingCourses] TC_Sub ON TS_Sub.CourseID = TC_Sub.TrainingCourseID
                        WHERE TE_Sub.EmployeeUserID = EmpInfo.USERID
                        ORDER BY TC_Sub.TrainingCourseText
                        FOR XML PATH('')
                    ), 1, 3, '')
                ) as CoursesTaken
            FROM [AURAHR].[dbo].[Evaluations] E
            LEFT JOIN [AURAHR].[dbo].[Users] Mgr ON E.EvaluatorUserID = Mgr.UserID 
            LEFT JOIN [AURAHR].[dbo].[USERINFO] EmpInfo ON E.EmployeeUserID = EmpInfo.USERID
            LEFT JOIN [AURAHR].[dbo].[Users] EmpUser ON E.EmployeeUserID = EmpUser.UserID
            LEFT JOIN [AURAHR].[dbo].[Recommendations] R ON E.RecommendationID = R.RecommendationID
            LEFT JOIN [AURAHR].[dbo].[TrainingCourses] TC ON E.TrainingCourseID = TC.TrainingCourseID
            LEFT JOIN [AURAHR].[dbo].[EvaluationTypes] ET ON E.EvaluationTypeID = ET.EvaluationTypeID
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
        if taken_course_id:
            where_clauses.append("""
                EXISTS (
                    SELECT 1 FROM [AURAHR].[dbo].[TrainingEnrollments] TE_F
                    JOIN [AURAHR].[dbo].[TrainingSessions] TS_F ON TE_F.SessionID = TS_F.SessionID
                    WHERE TE_F.EmployeeUserID = E.EmployeeUserID AND TS_F.CourseID = ?
                )
            """)
            params.append(taken_course_id)
            
        if overall_rating:
            where_clauses.append("E.OverallRating = ?")
            params.append(overall_rating)

        query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY E.EvaluationDate DESC"
        cursor.execute(query, params)
        raw_reports = cursor.fetchall()
        
        # --- Grouping Logic: Aggregate by EmployeeUserID ---
        reports_map = defaultdict(list)
        for r in raw_reports:
            reports_map[r.EmployeeUserID].append(r)
            
        # Transform map to list of objects { latest: ..., history: [...] }
        # Preserve the order of appearance (based on latest evaluation date)
        seen_employees = set()
        reports = []
        print(f"DEBUG: Processing {len(raw_reports)} raw reports into groups...")
        for r in raw_reports:
            emp_id = r.EmployeeUserID
            if emp_id not in seen_employees:
                seen_employees.add(emp_id)
                emp_list = reports_map[emp_id]
                reports.append({
                    'latest': emp_list[0],
                    'history': emp_list[1:]
                })

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
    cursor.execute("SELECT ET.EvaluationTypeID, ET.TypeName, ET.DisplayName, ET.IsRepeatable, ET.SortOrder, Pre.DisplayName as PrerequisiteName FROM [AURAHR].[dbo].[EvaluationTypes] ET LEFT JOIN [AURAHR].[dbo].[EvaluationTypes] Pre ON ET.PrerequisiteTypeID = Pre.EvaluationTypeID ORDER BY ET.SortOrder")
    types = cursor.fetchall()
    conn.close()
    return render_template('evaluation_types_list.html', types=types)

@app.route('/evaluation-types/add', methods=['GET', 'POST'])
@admin_required
def evaluation_types_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT EvaluationTypeID, DisplayName FROM [AURAHR].[dbo].[EvaluationTypes] ORDER BY SortOrder")
    all_types = cursor.fetchall()
    if request.method == 'POST':
        try:
            type_name = request.form['type_name']
            display_name = request.form['display_name']
            is_repeatable = 'is_repeatable' in request.form
            prerequisite_id = request.form.get('prerequisite_id') or None
            sort_order = request.form.get('sort_order', 100)
            days_after = request.form.get('days_after') or None
            # Handle Checkbox List for Classes
            selected_classes = request.form.getlist('included_classes_list')
            included_classes = ','.join(selected_classes) if selected_classes else None
            
            cursor.execute("INSERT INTO [AURAHR].[dbo].[EvaluationTypes] (TypeName, DisplayName, IsRepeatable, PrerequisiteTypeID, SortOrder, DaysAfterPrerequisite, IncludedClasses) VALUES (?, ?, ?, ?, ?, ?, ?)", (type_name, display_name, is_repeatable, prerequisite_id, sort_order, days_after, included_classes))
            conn.commit()
            flash('✅ تم إضافة نوع التقييم بنجاح', 'success')
            return redirect(url_for('evaluation_types_list'))
        except Exception as e:
            conn.rollback()
            flash(f'❌ خطأ في قاعدة البيانات: {e}', 'danger')
        finally:
            conn.close()
    conn.close()
    all_classes = get_all_classes()
    print(f"DEBUG: Found {len(all_classes)} classes for form.")
    return render_template('evaluation_type_form.html', action='Add', all_types=all_types, all_classes=all_classes)

@app.route('/evaluation-types/edit/<int:type_id>', methods=['GET', 'POST'])
@admin_required
def evaluation_types_edit(type_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT EvaluationTypeID, DisplayName FROM [AURAHR].[dbo].[EvaluationTypes] WHERE EvaluationTypeID != ? ORDER BY SortOrder", (type_id,))
    all_types = cursor.fetchall()
    cursor.execute("SELECT * FROM [AURAHR].[dbo].[EvaluationTypes] WHERE EvaluationTypeID = ?", (type_id,))
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
            days_after = request.form.get('days_after') or None
            # Handle Checkbox List for Classes
            selected_classes = request.form.getlist('included_classes_list')
            included_classes = ','.join(selected_classes) if selected_classes else None
            
            cursor.execute("UPDATE [AURAHR].[dbo].[EvaluationTypes] SET TypeName = ?, DisplayName = ?, IsRepeatable = ?, PrerequisiteTypeID = ?, SortOrder = ?, DaysAfterPrerequisite = ?, IncludedClasses = ? WHERE EvaluationTypeID = ?", (type_name, display_name, is_repeatable, prerequisite_id, sort_order, days_after, included_classes, type_id))
            conn.commit()
            flash('✅ تم تحديث نوع التقييم بنجاح', 'success')
            return redirect(url_for('evaluation_types_list'))
        except Exception as e:
            conn.rollback()
            flash(f'❌ خطأ في قاعدة البيانات: {e}', 'danger')
        finally:
            conn.close()
    conn.close()
    all_classes = get_all_classes()
    return render_template('evaluation_type_form.html', action='Edit', eval_type=eval_type, all_types=all_types, all_classes=all_classes)

@app.route('/evaluation-types/delete/<int:type_id>', methods=['POST'])
@admin_required
def evaluation_types_delete(type_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) as cnt FROM [AURAHR].[dbo].[Evaluations] WHERE EvaluationTypeID = ?", (type_id,))
        if cursor.fetchone().cnt > 0:
            flash('❌ لا يمكن الحذف، هذا النوع مستخدم في تقييمات سابقة.', 'danger')
            conn.close()
            return redirect(url_for('evaluation_types_list'))
        cursor.execute("SELECT COUNT(*) as cnt FROM [AURAHR].[dbo].[EvaluationTypes] WHERE PrerequisiteTypeID = ?", (type_id,))
        if cursor.fetchone().cnt > 0:
            flash('❌ لا يمكن الحذف، هذا النوع هو متطلب لنوع آخر.', 'danger')
            conn.close()
            return redirect(url_for('evaluation_types_list'))
        cursor.execute("DELETE FROM [AURAHR].[dbo].[EvaluationTypes] WHERE EvaluationTypeID = ?", (type_id,))
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
    cursor.execute("SELECT C.CycleID, C.CycleName, C.StartDate, C.EndDate, C.IsEnabled, ET.DisplayName as EvaluationTypeName FROM [AURAHR].[dbo].[EvaluationCycles] C JOIN [AURAHR].[dbo].[EvaluationTypes] ET ON C.EvaluationTypeID = ET.EvaluationTypeID ORDER BY C.StartDate DESC")
    cycles = cursor.fetchall()
    conn.close()
    return render_template('evaluation_cycles_list.html', cycles=cycles)


@app.route('/evaluation-cycles/add', methods=['GET', 'POST'])
@admin_required
def evaluation_cycles_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT EvaluationTypeID, DisplayName FROM [AURAHR].[dbo].[EvaluationTypes] ORDER BY SortOrder")
    all_types = cursor.fetchall()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [AURAHR].[dbo].[DEPARTMENTS] ORDER BY DEPTNAME")
    all_depts = cursor.fetchall()
    if request.method == 'POST':
        try:
            cycle_name = request.form['cycle_name']
            type_id = request.form['type_id']
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            is_enabled = 'is_enabled' in request.form
            dept_ids = request.form.getlist('dept_ids')
            cursor.execute("INSERT INTO [AURAHR].[dbo].[EvaluationCycles] (CycleName, EvaluationTypeID, StartDate, EndDate, IsEnabled) OUTPUT INSERTED.CycleID VALUES (?, ?, ?, ?, ?)", (cycle_name, type_id, start_date, end_date, is_enabled))
            new_cycle_id = cursor.fetchone().CycleID
            if dept_ids:
                dept_data = [(new_cycle_id, int(dept_id)) for dept_id in dept_ids]
                cursor.executemany("INSERT INTO [AURAHR].[dbo].[CycleDepartments] (CycleID, DepartmentID) VALUES (?, ?)", dept_data)
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
    cursor.execute("SELECT EvaluationTypeID, DisplayName FROM [AURAHR].[dbo].[EvaluationTypes] ORDER BY SortOrder")
    all_types = cursor.fetchall()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [AURAHR].[dbo].[DEPARTMENTS] ORDER BY DEPTNAME")
    all_depts = cursor.fetchall()
    if request.method == 'POST':
        try:
            cycle_name = request.form['cycle_name']
            type_id = request.form['type_id']
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            is_enabled = 'is_enabled' in request.form
            dept_ids = request.form.getlist('dept_ids')
            cursor.execute("UPDATE [AURAHR].[dbo].[EvaluationCycles] SET CycleName = ?, EvaluationTypeID = ?, StartDate = ?, EndDate = ?, IsEnabled = ? WHERE CycleID = ?", (cycle_name, type_id, start_date, end_date, is_enabled, cycle_id))
            cursor.execute("DELETE FROM [AURAHR].[dbo].[CycleDepartments] WHERE CycleID = ?", (cycle_id,))
            if dept_ids:
                dept_data = [(cycle_id, int(dept_id)) for dept_id in dept_ids]
                cursor.executemany("INSERT INTO [AURAHR].[dbo].[CycleDepartments] (CycleID, DepartmentID) VALUES (?, ?)", dept_data)
            conn.commit()
            flash('✅ تم تحديث دورة التقييم بنجاح', 'success')
            return redirect(url_for('evaluation_cycles_list'))
        except Exception as e:
            conn.rollback()
            flash(f'❌ خطأ في قاعدة البيانات: {e}', 'danger')
        finally:
            conn.close()
    cursor.execute("SELECT * FROM [AURAHR].[dbo].[EvaluationCycles] WHERE CycleID = ?", (cycle_id,))
    cycle = cursor.fetchone()
    if not cycle:
        flash('❌ لم يتم العثور على الدورة', 'danger')
        conn.close()
        return redirect(url_for('evaluation_cycles_list'))
    cursor.execute("SELECT DepartmentID FROM [AURAHR].[dbo].[CycleDepartments] WHERE CycleID = ?", (cycle_id,))
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
        cursor.execute("DELETE FROM [AURAHR].[dbo].[CycleDepartments] WHERE CycleID = ?", (cycle_id,))
        cursor.execute("DELETE FROM [AURAHR].[dbo].[EvaluationCycles] WHERE CycleID = ?", (cycle_id,))
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
        cursor.execute("""
            SELECT E.EvaluationID, E.EvaluationDate, COALESCE(ET.DisplayName, E.EvaluationType) as EvaluationType, 
                E.OverallScore, E.OverallRating, E.ManagerComments, E.EmployeeUserID, E.EvaluatorUserID, 
                COALESCE(EmpInfo.NAME, EmpUser.Name, EmpUser.Username) AS EmployeeName, 
                COALESCE(Mgr.Name, Mgr.Username) AS EvaluatorName, 
                COALESCE(EmpInfo.TITLE, EmpUser.Name, EmpUser.Username) AS EmployeeTitle, 
                DeptEmp.DEPTNAME as EmployeeDeptName, EmpInfo.employee_class, 
                R.RecommendationText, TC.TrainingCourseText,
                (
                    SELECT STUFF((
                        SELECT '###' + TC_Sub.TrainingCourseText
                        FROM [AURAHR].[dbo].[TrainingEnrollments] TE_Sub 
                        JOIN [AURAHR].[dbo].[TrainingSessions] TS_Sub ON TE_Sub.SessionID = TS_Sub.SessionID
                        JOIN [AURAHR].[dbo].[TrainingCourses] TC_Sub ON TS_Sub.CourseID = TC_Sub.TrainingCourseID
                        WHERE TE_Sub.EmployeeUserID = EmpInfo.USERID
                        ORDER BY TC_Sub.TrainingCourseText
                        FOR XML PATH('')
                    ), 1, 3, '')
                ) as CoursesTaken
            FROM [AURAHR].[dbo].[Evaluations] E 
            LEFT JOIN [AURAHR].[dbo].[Users] Mgr ON E.EvaluatorUserID = Mgr.UserID 
            LEFT JOIN [AURAHR].[dbo].[USERINFO] EmpInfo ON E.EmployeeUserID = EmpInfo.USERID 
            LEFT JOIN [AURAHR].[dbo].[Users] EmpUser ON E.EmployeeUserID = EmpUser.UserID 
            LEFT JOIN [AURAHR].[dbo].[DEPARTMENTS] DeptEmp ON COALESCE(EmpInfo.DEFAULTDEPTID, EmpUser.DepartmentID) = DeptEmp.DEPTID 
            LEFT JOIN [AURAHR].[dbo].[Recommendations] R ON E.RecommendationID = R.RecommendationID 
            LEFT JOIN [AURAHR].[dbo].[TrainingCourses] TC ON E.TrainingCourseID = TC.TrainingCourseID 
            LEFT JOIN [AURAHR].[dbo].[EvaluationTypes] ET ON E.EvaluationTypeID = ET.EvaluationTypeID 
            WHERE E.EvaluationID = ?
        """, (evaluation_id,))
        evaluation_data = cursor.fetchone()
        if not evaluation_data:
            flash("Evaluation not found.", "warning")
            return redirect(url_for('evaluation_reports'))
        can_view = False
        if role_id in [1, 4]: can_view = True
        elif role_id in [2, 3] and evaluation_data.EvaluatorUserID == user_id: can_view = True
        elif role_id == 5 and evaluation_data.EmployeeUserID == user_id: can_view = True
        elif role_id == 3:
            cursor.execute("SELECT DepartmentID FROM [AURAHR].[dbo].[Users] WHERE UserID = ?", (user_id,))
            manager_dept = cursor.fetchone()
            cursor.execute("SELECT DEFAULTDEPTID FROM [AURAHR].[dbo].[USERINFO] WHERE USERID = ?", (evaluation_data.EmployeeUserID,))
            emp_dept = cursor.fetchone()
            if manager_dept and emp_dept and manager_dept.DepartmentID == emp_dept.DEFAULTDEPTID:
                can_view = True
        if not can_view:
             flash("You do not have permission to view this evaluation.", "danger")
             return redirect(url_for('evaluation_reports'))
        cursor.execute("SELECT ED.ScoreGiven, EC.CriteriaName, EC.CriteriaWeight, EC.MaxScore FROM [AURAHR].[dbo].[EvaluationDetails] ED JOIN [AURAHR].[dbo].[EvaluationCriteria] EC ON ED.CriteriaID = EC.CriteriaID WHERE ED.EvaluationID = ? ORDER BY EC.CriteriaID", (evaluation_id,))
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
        cursor.execute("DELETE FROM [AURAHR].[dbo].[Evaluations] WHERE EvaluationID = ?", (evaluation_id,))
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
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [AURAHR].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
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
               S.ExternalTrainerName, S.MaxSeats,
               (SELECT COUNT(*) FROM TrainingEnrollments WHERE SessionID = S.SessionID) AS EnrolledCount
        FROM TrainingSessions S
        LEFT JOIN TrainingCourses C ON S.CourseID = C.TrainingCourseID
        ORDER BY S.SessionDate DESC
    """)
    sessions = cursor.fetchall()
    # --- Fetch Pending Recommendations ---
    cursor.execute("""
        SELECT 
            E.EvaluationID,
            E.EvaluationDate,
            U_Emp.Name AS EmployeeName,
            U_Mgr.Name AS ManagerName,
            TC.TrainingCourseText AS CourseName,
            E.TrainingCourseID
        FROM Evaluations E
        JOIN USERINFO U_Emp ON E.EmployeeUserID = U_Emp.USERID
        LEFT JOIN USERINFO U_Mgr ON E.EvaluatorUserID = U_Mgr.USERID
        JOIN TrainingCourses TC ON E.TrainingCourseID = TC.TrainingCourseID
        WHERE E.TrainingCourseID IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM TrainingEnrollments EN
            JOIN TrainingSessions S ON EN.SessionID = S.SessionID
            WHERE EN.EmployeeUserID = E.EmployeeUserID
            AND S.CourseID = E.TrainingCourseID
            AND (EN.PassStatus = 'Passed' OR EN.PassStatus IS NULL) -- Filter if passed or currently enrolled (NULL usually means active)
        )
    """)
    pending_recommendations = cursor.fetchall()
    conn.close()

    return render_template('training_dashboard.html', 
                         sessions=sessions, 
                         recommendations=pending_recommendations)

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

    # 2. Base Filter Logic (Reused for Analytics & Main List)
    where_clauses = ["U.IsActive = 1", "U.TITLE IS NOT NULL", "U.TITLE <> ''", "U.TITLE <> 'None'"]
    params = []

    if search:
        where_clauses.append("(U.NAME LIKE ? OR U.BADGENUMBER LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    
    if dept_id:
        where_clauses.append("U.DEFAULTDEPTID = ?")
        params.append(dept_id)
        
    if course_id:
        where_clauses.append("TS.CourseID = ?")
        params.append(course_id)
        
    if date_from:
        where_clauses.append("TS.SessionDate >= ?")
        params.append(date_from)
        
    if date_to:
        where_clauses.append("TS.SessionDate <= ?")
        params.append(date_to)

    where_sql = " AND ".join(where_clauses)
    
    # --- PAGINATION LOGIC ---
    page = request.args.get('page', 1, type=int)
    if page < 1: page = 1
    per_page = 10 # Reduced for safety and performance
    offset = (page - 1) * per_page

    # 3. Count Total Matching Employees (Distinct)
    count_query = f"""
        SELECT COUNT(DISTINCT U.USERID)
        FROM [AURAHR].[dbo].[USERINFO] U
        LEFT JOIN [AURAHR].[dbo].[DEPARTMENTS] D ON U.DEFAULTDEPTID = D.DEPTID
        LEFT JOIN [AURAHR].[dbo].[TrainingEnrollments] TE ON U.USERID = TE.EmployeeUserID
        LEFT JOIN [AURAHR].[dbo].[TrainingSessions] TS ON TE.SessionID = TS.SessionID
        LEFT JOIN [AURAHR].[dbo].[TrainingCourses] TC ON TS.CourseID = TC.TrainingCourseID
        WHERE {where_sql}
    """
    cursor.execute(count_query, params)
    total_users = cursor.fetchone()[0]
    total_pages = (total_users + per_page - 1) // per_page
    
    # 4. Fetch Paged User IDs
    # We must order by something unique to ensure stable pagination
    ids_query = f"""
        SELECT DISTINCT U.USERID, U.NAME
        FROM [AURAHR].[dbo].[USERINFO] U
        LEFT JOIN [AURAHR].[dbo].[DEPARTMENTS] D ON U.DEFAULTDEPTID = D.DEPTID
        LEFT JOIN [AURAHR].[dbo].[TrainingEnrollments] TE ON U.USERID = TE.EmployeeUserID
        LEFT JOIN [AURAHR].[dbo].[TrainingSessions] TS ON TE.SessionID = TS.SessionID
        LEFT JOIN [AURAHR].[dbo].[TrainingCourses] TC ON TS.CourseID = TC.TrainingCourseID
        WHERE {where_sql}
        ORDER BY U.NAME, U.USERID
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """
    # Params for ID query: Original filters + pagination params
    paged_params = params + [offset, per_page]
    cursor.execute(ids_query, paged_params)
    paged_users = cursor.fetchall()
    
    paged_user_ids = [row.USERID for row in paged_users]
    
    # 5. Fetch Full Data for Paged IDs
    rows = []
    if paged_user_ids:
        placeholders = ','.join(['?'] * len(paged_user_ids))
        # We re-use where_sql to ensure we still filter courses/sessions correctly (e.g. by date)
        # But we restrict the USER pool to just our paged set
        final_query = f"""
            SELECT 
                U.USERID, U.BADGENUMBER, U.NAME, U.TITLE,
                D.DEPTNAME,
                TE.EnrollmentID, TE.PassStatus, TE.Grade, TE.AttendanceStatus,
                TS.SessionDate, TS.SessionID,
                TC.TrainingCourseText
            FROM [AURAHR].[dbo].[USERINFO] U
            LEFT JOIN [AURAHR].[dbo].[DEPARTMENTS] D ON U.DEFAULTDEPTID = D.DEPTID
            LEFT JOIN [AURAHR].[dbo].[TrainingEnrollments] TE ON U.USERID = TE.EmployeeUserID
            LEFT JOIN [AURAHR].[dbo].[TrainingSessions] TS ON TE.SessionID = TS.SessionID
            LEFT JOIN [AURAHR].[dbo].[TrainingCourses] TC ON TS.CourseID = TC.TrainingCourseID
            WHERE U.USERID IN ({placeholders}) AND {where_sql}
            ORDER BY U.NAME, TS.SessionDate DESC
        """
        # Params: IDs first, then the original filter params
        final_params = paged_user_ids + params
        cursor.execute(final_query, final_params)
        rows = cursor.fetchall()
    
    # 4. Process Users
    employees = defaultdict(lambda: {'info': None, 'courses': [], 'stats': {'total': 0, 'passed': 0, 'failed': 0}})
    
    for row in rows:
        uid = row.USERID
        if employees[uid]['info'] is None:
            employees[uid]['info'] = {
                'id': row.USERID,
                'badge': row.BADGENUMBER,
                'name': row.NAME,
                'title': row.TITLE,
                'dept': row.DEPTNAME,
                'has_pic': False # details: pic column removed for performance
            }
        
        if row.EnrollmentID:
            # Skip invalid course names
            if not row.TrainingCourseText or str(row.TrainingCourseText).strip().lower() == 'none':
                 continue

            employees[uid]['courses'].append({
                'course_name': row.TrainingCourseText,
                'date': row.SessionDate,
                'status': row.PassStatus,
                'grade': row.Grade,
                'attendance': row.AttendanceStatus
            })
            employees[uid]['stats']['total'] += 1
            if row.PassStatus == 'Passed':
                employees[uid]['stats']['passed'] += 1
            elif row.PassStatus == 'Failed':
                employees[uid]['stats']['failed'] += 1

    # 5. Dropdowns
    cursor.execute("SELECT DEPTID, DEPTNAME FROM DEPARTMENTS ORDER BY DEPTNAME")
    all_depts = cursor.fetchall()
    
    cursor.execute("SELECT TrainingCourseID, TrainingCourseText FROM TrainingCourses ORDER BY TrainingCourseText")
    all_courses = cursor.fetchall()

    conn.close()

    # Pagination Window Logic (Server-Side)
    iter_pages = []
    if total_pages > 1:
        if total_pages <= 9:
            iter_pages = list(range(1, total_pages + 1))
        else:
            s_pages = {1, total_pages}
            for i in range(page - 2, page + 3):
                if 1 <= i <= total_pages:
                    s_pages.add(i)
            sorted_p = sorted(list(s_pages))
            for i, p in enumerate(sorted_p):
                iter_pages.append(p)
                if i < len(sorted_p) - 1 and sorted_p[i+1] > p + 1:
                    iter_pages.append(None)

    # Prepare filters for pagination links (exclude 'page' to avoid duplications)
    filters_dict = {k: v for k, v in request.args.items() if k != 'page'}

    return render_template('training_employee_report.html', 
                           employees=employees, 
                           all_depts=all_depts, 
                           all_courses=all_courses,
                           filters=filters_dict,
                           analytics={},     # Unused by template (calculated in JS)
                           global_stats={},  # Unused by template
                           page=page,
                           total_pages=total_pages,
                           iter_pages=iter_pages)

@app.route('/training/print_card/<int:user_id>')
@login_required
def training_print_card(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Get Employee Info
    cursor.execute("""
        SELECT U.NAME, U.TITLE, D.DEPTNAME 
        FROM USERINFO U
        LEFT JOIN DEPARTMENTS D ON U.DEFAULTDEPTID = D.DEPTID
        WHERE U.USERID = ?
    """, (user_id,))
    employee = cursor.fetchone()
    
    if not employee:
        flash("الموظف غير موجود", "danger")
        conn.close()
        return redirect(url_for('training_employee_report'))

    # 2. Get Training History
    # Filter out 'None' courses and sort by date ascending (chronological for a card)
    cursor.execute("""
        SELECT 
            TC.TrainingCourseText, 
            TS.SessionDate, 
            TS.EndDate, 
            TS.Location,
            TE.PassStatus,
            TE.Grade
        FROM TrainingEnrollments TE
        JOIN TrainingSessions TS ON TE.SessionID = TS.SessionID
        JOIN TrainingCourses TC ON TS.CourseID = TC.TrainingCourseID
        WHERE TE.EmployeeUserID = ?
        AND TC.TrainingCourseText IS NOT NULL 
        AND TC.TrainingCourseText <> 'None'
        ORDER BY TS.SessionDate ASC
    """, (user_id,))
    courses = cursor.fetchall()
    
    conn.close()
    
    return render_template('training_card_print.html', employee=employee, courses=courses)

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
        SELECT TE.*, UI.NAME, UI.BADGENUMBER, D.DEPTNAME, UI.TITLE
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
        # logic: Recommended in Evaluations AND NOT (Enrolled/Passed previously)
        cursor.execute("""
            SELECT DISTINCT E.EmployeeUserID 
            FROM Evaluations E
            WHERE E.TrainingCourseID = ?
            AND NOT EXISTS (
                SELECT 1 FROM TrainingEnrollments EN
                JOIN TrainingSessions S ON EN.SessionID = S.SessionID
                WHERE EN.EmployeeUserID = E.EmployeeUserID
                AND S.CourseID = E.TrainingCourseID
                AND (EN.PassStatus = 'Passed') -- Only exclude if they actually PASSED.
            )
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

    # 7. Average Time to Hire (Days)
    # Calculated as diff between ApplicationDate and the log date when they became 'Hired'
    cursor.execute("""
        SELECT AVG(DATEDIFF(day, C.ApplicationDate, L.ActionDate)) 
        FROM CandidateLogs L
        JOIN Candidates C ON L.CandidateID = C.CandidateID
        WHERE L.ToStage = 'Hired'
    """)
    avg_hire_time = cursor.fetchone()[0] or 0
    
    # 8. Monthly Applicant Trend (Last 6 Months)
    cursor.execute("""
        SELECT FORMAT(ApplicationDate, 'yyyy-MM') as Month, COUNT(*) 
        FROM Candidates 
        WHERE ApplicationDate >= DATEADD(month, -6, GETDATE())
        GROUP BY FORMAT(ApplicationDate, 'yyyy-MM')
        ORDER BY Month
    """)
    trend_data = cursor.fetchall()

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
        },
        'trend': {
            'labels': [row.Month for row in trend_data], 
            'data': [row[1] for row in trend_data]
        }
    }

    return render_template('recruitment/recruitment_analytics.html', 
                           analytics=analytics,
                           total_candidates=total_candidates,
                           open_positions=open_positions,
                           total_hired=total_hired,
                           avg_hire_time=int(avg_hire_time),
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

    # Define Stages (Visual Order)
    stages = ['New', 'HR_Interview', 'Tech_Interview', 'Test', 'Offer', 'Waiting', 'Training', 'Hired', 'Rejected', 'Resigned']
    
    # Group candidates for the Kanban board (handling legacy statuses)
    candidates_by_stage = {s: [] for s in stages}
    
    for c in candidates:
        status = c.Status
        
        # Legacy Mappings
        if status == 'Screening':
            status = 'HR_Interview'
        elif status == 'Interview':
            status = 'Tech_Interview'
            
        # Safety check
        if status in candidates_by_stage:
            candidates_by_stage[status].append(c)
        else:
            # Fallback for unknown statuses
            if 'New' in candidates_by_stage:
                candidates_by_stage['New'].append(c)

    return render_template('recruitment/job_pipeline.html', 
                           job=job, 
                           candidates=candidates, 
                           candidates_by_stage=candidates_by_stage,
                           stages=stages,
                           other_jobs=other_jobs)

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
    type_id = request.form['termination_type_id']
    reason_id = request.form['termination_reason_id']
    notes = request.form['notes']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get Text for Logging
    cursor.execute("SELECT TypeText FROM TerminationTypes WHERE TypeID = ?", (type_id,))
    type_text = cursor.fetchone()[0]
    
    cursor.execute("SELECT ReasonText FROM TerminationReasons WHERE ReasonID = ?", (reason_id,))
    reason_text = cursor.fetchone()[0]
    
    # 1. Update Candidate Status (Generalizing status to 'Terminated' or keeping 'Resigned'?)
    # For backward compatibility and clarity, let's stick to 'Resigned' if it's resignation, 
    # but maybe we should use 'Terminated' or the actual Type Text?
    # The user asked to "merge it". Let's update status to 'Terminated' or 'Resigned' 
    # depending on what makes sense. But the Kanban only had 'Resigned'. 
    # Let's decide to map everything to 'Resigned' status in the pipeline for now, 
    # or better, add 'Terminated' status validation.
    # Given the complexity, let's assume 'Resigned' acts as a catch-all "Left the company" status 
    # in the UI, or we change the status in DB to 'Terminated' and update template to show it green/red/etc.
    # Let's stick to 'Resigned' as the status key for now to avoid breaking other parts, 
    # but log the specific type.
    
    cursor.execute("UPDATE Candidates SET Status = 'Resigned' WHERE CandidateID = ?", (candidate_id,))
    
    # 2. Add to Log
    log_note = f"{type_text}: {reason_text} - {notes}"
    cursor.execute("""
        INSERT INTO CandidateLogs (CandidateID, FromStage, ToStage, EvaluationScore, Note, ActionDate)
        VALUES (?, 'Hired', 'Resigned', 0, ?, GETDATE())
    """, (candidate_id, log_note))
    
    conn.commit()
    conn.close()
    
    flash(f'🚪 تم تسجيل {type_text} بنجاح.', 'warning')
    return redirect(url_for('recruitment_history'))

from datetime import timedelta, datetime

@app.route('/recruitment/training')
def recruitment_training():
    """ Dedicated Dashboard for Active Trainees with Countdown """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch all candidates currently in 'Training'
    cursor.execute("""
        SELECT C.CandidateID, C.FullName, C.Phone, C.TrainingStartDate, C.TrainingEndDate,
               C.TrainerName, J.JobTitle, C.NationalID,
               C.TrainingStartTime, C.TrainingEndTime
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
        
        # Use DB end date if exists
        if row.TrainingEndDate:
            end_date = row.TrainingEndDate.date()
        else:
            end_date = start_date + timedelta(days=90) # Default 3 Months Rule
        
        # Calculate Progress
        total_days = (end_date - start_date).days
        if total_days <= 0: total_days = 90
        
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
        'national_id': row.NationalID,
        'start_date': start_date,
        'end_date': end_date,
        'start_time': row.TrainingStartTime,
        'end_time': row.TrainingEndTime,
        'days_left': days_left,
        'percent': int(percent),
        'color': color
    })

    return render_template('recruitment/recruitment_training.html', trainees=trainees)

# --- 2. Update Candidate Training Info Route ---
@app.route('/recruitment/update_training_info', methods=['POST'])
def update_candidate_training_info():
    """
    Updates the training dates and times for a specific candidate.
    Expected form data: candidate_id, start_date, end_date, start_time, end_time
    """
    try:
        candidate_id = request.form.get('candidate_id')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')

        if not candidate_id:
            flash("خطأ: لم يتم تحديد المرشح.", "danger")
            return redirect(url_for('recruitment_training'))

        conn = get_db_connection()
        cursor = conn.cursor()

        # Update SQL
        sql = """UPDATE Candidates 
                 SET TrainingStartDate = ?, TrainingEndDate = ?, 
                     TrainingStartTime = ?, TrainingEndTime = ?
                 WHERE CandidateID = ?"""
        
        # Handle empty strings
        sd = start_date if start_date else None
        ed = end_date if end_date else None
        st = start_time if start_time else None
        et = end_time if end_time else None
        
        cursor.execute(sql, (sd, ed, st, et, candidate_id))
        conn.commit()
        conn.close()
        
        flash("تم تحديث بيانات التدريب بنجاح.", "success")
        
    except Exception as e:
        print(f"Error updating training info: {e}")
        flash("حدث خطأ أثناء تحديث البيانات.", "danger")
    
    return redirect(url_for('recruitment_training'))

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
    Also records the Start Date if moving to 'Training' (Manual or Default).
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Get Data from Modal
    candidate_id = request.form['candidate_id']
    new_stage = request.form['new_stage']
    score = request.form.get('score') or 0
    note = request.form.get('note')
    
    # New: Manual Training Date
    training_date_str = request.form.get('training_start_date')

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
        # Use provided date or fallback to GETDATE()
        t_date = training_date_str if training_date_str else datetime.now()
        
        cursor.execute("""
            UPDATE Candidates 
            SET Status = ?, TrainingStartDate = ? 
            WHERE CandidateID = ?
        """, (new_stage, t_date, candidate_id))
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

    # Fetch Termination Types and Reasons
    try:
        cursor.execute("SELECT * FROM TerminationTypes")
        types = cursor.fetchall()
        
        cursor.execute("SELECT * FROM TerminationReasons")
        reasons = cursor.fetchall()
    except:
        types = []
        reasons = [] 


    conn.close()
    return render_template('recruitment/recruitment_history.html', logs=logs, types=types, reasons=reasons)

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
    """ Page to manage Termination Types and Reasons """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Handle Adding a New Type
    if request.method == 'POST' and 'new_type' in request.form:
        new_type = request.form['new_type'].strip()
        if new_type:
            cursor.execute("INSERT INTO TerminationTypes (TypeText) VALUES (?)", (new_type,))
            conn.commit()
            flash('✅ تم إضافة نوع الإنهاء بنجاح', 'success')
            
    # 2. Handle Deleting a Type
    if request.method == 'POST' and 'delete_type_id' in request.form:
        delete_id = request.form['delete_type_id']
        try:
            cursor.execute("DELETE FROM TerminationTypes WHERE TypeID = ?", (delete_id,))
            conn.commit()
            flash('🗑️ تم حذف نوع الإنهاء', 'warning')
        except Exception as e:
            flash(f'❌ لا يمكن حذف هذا النوع لوجود أسباب مرتبطة به.', 'danger')

    # 3. Handle Adding a New Reason
    if request.method == 'POST' and 'new_reason' in request.form:
        new_reason = request.form['new_reason'].strip()
        type_id = request.form['type_id']
        if new_reason and type_id:
            cursor.execute("INSERT INTO TerminationReasons (ReasonText, TypeID) VALUES (?, ?)", (new_reason, type_id))
            conn.commit()
            flash('✅ تم إضافة السبب بنجاح', 'success')

    # 4. Handle Deleting a Reason
    if request.method == 'POST' and 'delete_reason_id' in request.form:
        delete_id = request.form['delete_reason_id']
        cursor.execute("DELETE FROM TerminationReasons WHERE ReasonID = ?", (delete_id,))
        conn.commit()
        flash('🗑️ تم حذف السبب', 'warning')

    # Fetch All Data
    cursor.execute("SELECT * FROM TerminationTypes")
    types = cursor.fetchall()
    
    cursor.execute("""
        SELECT R.*, T.TypeText 
        FROM TerminationReasons R
        JOIN TerminationTypes T ON R.TypeID = T.TypeID
        ORDER BY T.TypeText, R.ReasonText
    """)
    reasons = cursor.fetchall()
    
    conn.close()
    return render_template('recruitment/recruitment_settings.html', types=types, reasons=reasons)

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
    """ Displays the unified Archive (Candidates + Employees) """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Fetch Archived Candidates
    cursor.execute("""
        SELECT C.CandidateID, C.FullName, C.Phone, C.Email, C.ApplicationDate, 
               J.JobTitle, D.DEPTNAME, C.HireDate, C.EndDate, C.NationalID,
               (SELECT TOP 1 Note FROM CandidateLogs L WHERE L.CandidateID = C.CandidateID ORDER BY L.ActionDate DESC) as LastNote
        FROM Candidates C
        LEFT JOIN Jobs J ON C.JobID = J.JobID
        LEFT JOIN DEPARTMENTS D ON J.DepartmentID = D.DEPTID
        WHERE C.Status = 'Archived'
        ORDER BY C.ApplicationDate DESC
    """)
    candidates = cursor.fetchall()
    
    # 2. Fetch Archived Employees
    cursor.execute("""
        SELECT UI.USERID, UI.BADGENUMBER, UI.NAME, UI.HIREDDAY, D.DEPTNAME, EA.EndDay, 
               TR.ReasonText, TT.TypeText, EA.ArchiveComment, EA.ArchiveReasonID, 
               EA.ArchiveTypeID AS TheArchiveTypeID, 
               UI.DEFAULTDEPTID
        FROM [AURAHR].[dbo].[USERINFO] AS UI
        LEFT JOIN DEPARTMENTS D ON UI.DEFAULTDEPTID = D.DEPTID
        LEFT JOIN [AURAHR].[dbo].[EmployeeArchive] EA ON UI.USERID = EA.UserID
        LEFT JOIN [AURAHR].[dbo].[TerminationReasons] TR ON EA.ArchiveReasonID = TR.ReasonID
        LEFT JOIN [AURAHR].[dbo].[TerminationTypes] TT ON EA.ArchiveTypeID = TT.TypeID
        WHERE UI.IsActive = 0
        ORDER BY EA.EndDay DESC
    """)
    archived_employees = cursor.fetchall()

    # 3. Fetch Jobs for Manual Add (Candidates)
    cursor.execute("SELECT JobID, JobTitle FROM Jobs WHERE Status = 'Open'")
    jobs = cursor.fetchall()

    # 4. Fetch Lookups for Employee Edit/Filters
    cursor.execute("SELECT DEPTID, DEPTNAME FROM DEPARTMENTS ORDER BY DEPTID")
    departments = cursor.fetchall()
    
    cursor.execute("""
        SELECT R.ReasonID, R.ReasonText, T.TypeText 
        FROM TerminationReasons R
        JOIN TerminationTypes T ON R.TypeID = T.TypeID
        ORDER BY T.TypeText, R.ReasonText
    """)
    reasons = cursor.fetchall()
    
    conn.close()
    
    classes = get_all_classes()
    
    return render_template('recruitment/recruitment_archive.html', 
                           candidates=candidates, 
                           archived_employees=archived_employees,
                           jobs=jobs,
                           departments=departments,
                           reasons=reasons,
                           classes=classes)

@app.route('/recruitment/archive/add', methods=['POST'])
def recruitment_archive_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        fullname = request.form.get('fullname')
        phone = request.form.get('phone')
        email = request.form.get('email') or None
        national_id = request.form.get('national_id') or None
        job_id = request.form.get('job_id') or None
        note = request.form.get('note')
        hire_date = request.form.get('hire_date') or None
        end_date = request.form.get('end_date') or None

        if not fullname:
             flash('❌ Full Name is required', 'danger')
        else:
            cursor.execute("""
               INSERT INTO Candidates (FullName, Phone, Email, NationalID, JobID, Status, ApplicationDate, HireDate, EndDate, Source)
               OUTPUT INSERTED.CandidateID
               VALUES (?, ?, ?, ?, ?, 'Archived', GETDATE(), ?, ?, 'Manual Archive')
            """, (fullname, phone, email, national_id, job_id, hire_date, end_date))
            
            cid = cursor.fetchone()[0]
            
            if note:
                cursor.execute("INSERT INTO CandidateLogs (CandidateID, Note, ActionDate) VALUES (?, ?, GETDATE())", (cid, note))
                
            conn.commit()
            flash('✅ Candidate manually added to archive.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'❌ Error adding candidate: {e}', 'danger')
    finally:
        conn.close()
        
    return redirect(url_for('recruitment_archive'))

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




# ==========================================
# DAR AL-DIYAFA ROUTES (Admin Only)
# ==========================================

@app.route('/dar_al_diyafa')
@admin_required
def dar_al_diyafa():
    return render_template('dar_al_diyafa.html')

@app.route('/generate_pdf', methods=['POST'])
@admin_required
def generate_pdf():
    try:
        data = request.form.to_dict()
        pdf_path = generate_form_pdf(data)
        return send_file(pdf_path, as_attachment=True, download_name='filled_form.pdf')
    except Exception as e:
        return f"Error occurred: {str(e)}", 500

# ==========================================
# DAR AL-DIYAFA API (Search & Helper)
# ==========================================

@app.route('/api/employee/get_full_data')
@login_required # Allow logged-in users to search
def get_employee_full_data():
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({'found': False})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Helper for safe date formatting
        def format_date(d):
            if not d: return ''
            if hasattr(d, 'strftime'):
                return d.strftime('%Y-%m-%d')
            return str(d)

        # A. SEARCH (Name or Badge)
        # We prefer finding by exact Badge first, then Name
        sql_search = """
            SELECT TOP 1 U.USERID, U.NAME, U.BADGENUMBER, U.SSN, 
                   U.HIREDDAY, U.BIRTHDAY, U.OPHONE, U.FPHONE, 
                   U.TITLE, U.STREET, D.DEPTNAME
            FROM [AURAHR].[dbo].[USERINFO] U
            LEFT JOIN [AURAHR].[dbo].[DEPARTMENTS] D ON U.DEFAULTDEPTID = D.DEPTID
            WHERE (U.BADGENUMBER = ?) OR (U.NAME LIKE ?) OR (TRY_CAST(U.BADGENUMBER AS BIGINT) = TRY_CAST(? AS BIGINT))
            ORDER BY U.IsActive DESC -- Prefer active if matches multiple
        """
        print(f"SEARCH QUERY: {query}")
        print(f"PARAMS: ('{query}', '%{query}%', '{query}')")
        cursor.execute(sql_search, (query, f"%{query}%", query))
        user_row = cursor.fetchone()

        if not user_row:
            return jsonify({'found': False})

        user_id = user_row.USERID
        
        # B. GET EXTENDED INFO
        cursor.execute("SELECT * FROM [EmployeeExtendedInfo] WHERE UserID = ?", (user_id,))
        extended_row = cursor.fetchone()

        # C. GET FAMILY info
        cursor.execute("SELECT * FROM [EmployeeFamilyMembers] WHERE UserID = ? ORDER BY RelationType, SortOrder", (user_id,))
        family_rows = cursor.fetchall()
        
        # Structure the family data by type
        # relation_types: spouse, parent, sibling, child, p_uncle, p_cousin, m_uncle, m_cousin
        family_data = defaultdict(list)
        for f in family_rows:
            family_data[f.RelationType].append({
                'name': f.Name,
                'dob': format_date(f.DOB),
                'job': f.Job,
                'address': f.Address,
                'phone': f.Phone
            })

        # Construct Response
        response = {
            'found': True,
            'user_id': user_id,
            'name': user_row.NAME,
            'badge': user_row.BADGENUMBER,
            'ssn': extended_row.NationalID if extended_row and extended_row.NationalID else user_row.SSN,
            'hired_date': format_date(user_row.HIREDDAY),
            'birth_date': format_date(user_row.BIRTHDAY),
            'phone': user_row.OPHONE or user_row.FPHONE,
            'title': user_row.TITLE,
            'address': user_row.STREET,
            'department': user_row.DEPTNAME,
            
            # Extended
            'sub_department': extended_row.SubDepartment if extended_row else '',
            'previous_address': extended_row.PreviousAddress if extended_row else '',
            'job_nature': extended_row.JobNature if extended_row else (user_row.TITLE or ''), # Fallback
            
            # Family
            'family': family_data
        }
        
        return jsonify(response)

    except Exception as e:
        print(f"Error in get_employee_full_data: {e}")
        return jsonify({'found': False, 'error': str(e)}) # Return empty on error so frontend doesn't break
    finally:
        conn.close()

@app.route('/api/employee/save_full_data', methods=['POST'])
@login_required
def save_employee_full_data():
    try:
        data = request.json
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'No User ID provided'})

        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Update USERINFO (Basic fields that are allowed to be updated)
        # Note: Be careful what we update here. Let's update Phone, Address if changed.
        cursor.execute("""
            UPDATE [AURAHR].[dbo].[USERINFO] 
            SET OPHONE = ?, STREET = ?, SSN = ?
            WHERE USERID = ?
        """, (data.get('phone'), data.get('address'), data.get('national_id'), user_id))

        # 2. Update/Insert EmployeeExtendedInfo
        # Check if exists
        cursor.execute("SELECT 1 FROM EmployeeExtendedInfo WHERE UserID = ?", (user_id,))
        exists = cursor.fetchone()
        
        if exists:
            cursor.execute("""
                UPDATE EmployeeExtendedInfo
                SET SubDepartment = ?, PreviousAddress = ?, JobNature = ?, NationalID = ?
                WHERE UserID = ?
            """, (data.get('sub_department'), data.get('previous_address'), data.get('job_nature'), data.get('national_id'), user_id))
        else:
            cursor.execute("""
                INSERT INTO EmployeeExtendedInfo (UserID, SubDepartment, PreviousAddress, JobNature, NationalID)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, data.get('sub_department'), data.get('previous_address'), data.get('job_nature'), data.get('national_id')))

        # 3. Update Family Members
        # Strategy: Delete all for this user and re-insert. Simplest way to handle edits/deletes/adds.
        cursor.execute("DELETE FROM EmployeeFamilyMembers WHERE UserID = ?", (user_id,))
        
        # Re-insert
        family_groups = data.get('family', {})
        
        for r_type, members in family_groups.items():
            for idx, m in enumerate(members):
                if not m.get('name'): continue # Skip empty rows
                
                cursor.execute("""
                    INSERT INTO EmployeeFamilyMembers (UserID, RelationType, SortOrder, Name, DOB, Job, Address, Phone)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, 
                    r_type, 
                    idx + 1, 
                    m.get('name'), 
                    m.get('dob') or None, 
                    m.get('job'), 
                    m.get('address'), 
                    m.get('phone')
                ))

        conn.commit()
        return jsonify({'status': 'success'})

    except Exception as e:
        print(f"Error saving data: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()


if __name__ == '__main__':
    # Default values
    port = 8080
    host = '0.0.0.0'
    
    # Try to read config from server_config.txt
    config_file = 'server_config.txt'
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                content = f.read().strip()
                
                # Check if it's the old strict number format or new KEY=VALUE format
                is_key_value = any('=' in line for line in content.splitlines())
                
                if is_key_value:
                    for line in content.splitlines():
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip().upper()
                            value = value.strip()
                            if key == 'PORT':
                                port = int(value)
                            elif key == 'HOST':
                                host = value
                elif content.isdigit():
                    # Fallback for just a number in the file
                    port = int(content)
                    
            print(f"✅ Loaded configuration: Running on {host}:{port}")
        except Exception as e:
            print(f"⚠️ Error reading {config_file}, using defaults {host}:{port}. Error: {e}")
    else:
        # Create the file with defaults if it doesn't exist
        try:
            with open(config_file, 'w') as f:
                f.write(f"HOST={host}\nPORT={port}")
            print(f"ℹ️ Created {config_file} with defaults")
        except:
            pass

    # use_reloader=False prevents the crash
    # debug=True allows you to see the error pages
    app.run(host=host, port=port, debug=True, use_reloader=False)
