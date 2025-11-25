from flask import Flask, render_template, request, redirect, url_for, flash, session, json, send_file
from config import CONNECTION_STRING
import pyodbc
import datetime
from werkzeug.security import check_password_hash, generate_password_hash
import io
from functools import wraps
import pandas as pd 
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
    return session.get('role_id') == 1  # Admin is RoleID = 1

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

# ========== EVALUATION LOGIC ==========

def get_available_evaluation_types(conn, employee_id, manager_dept_id):
    """
    Checks an employee and returns a list of evaluation types 
    that are currently available or disabled for them.
    """
    try:
        cursor = conn.cursor()
        today = datetime.date.today()
        
        # 1. Get employee's completed evals
        cursor.execute("SELECT DISTINCT EvaluationTypeID FROM [Zktime].[dbo].[Evaluations] WHERE EmployeeUserID = ?", (employee_id,))
        completed_eval_ids = {row.EvaluationTypeID for row in cursor.fetchall()}
        
        # 2. Get all rules
        cursor.execute("SELECT * FROM [Zktime].[dbo].[EvaluationTypes] ORDER BY SortOrder")
        all_types_rules = cursor.fetchall()
        
        # 3. Get all active, open cycles
        cursor.execute("""
            SELECT C.EvaluationTypeID, CD.DepartmentID
            FROM [Zktime].[dbo].[EvaluationCycles] C
            LEFT JOIN [Zktime].[dbo].[CycleDepartments] CD ON C.CycleID = CD.CycleID
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
        print(f"Error in get_available_evaluation_types: {e}")
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
    cursor.execute("SELECT employee_class FROM [Zktime].[dbo].[USERINFO] WHERE USERID = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result.employee_class if result and result.employee_class else 'لم تضاف'

# ========== ROUTES ==========

@app.route('/', methods=['GET', 'POST'])
def login():
    # If already logged in, redirect based on role
    if 'user_id' in session:
        if session.get('role_id') == 6:
            return redirect(url_for('recruitment_dashboard'))
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT UserID, Username, PasswordHash, RoleID, Name FROM [Zktime].[dbo].[Users] WHERE Username = ?", (username,))
            user = cursor.fetchone()
        except Exception as e:
            flash('❌ A database error occurred.', 'danger')
            return render_template('login.html')
        finally:
            if conn: conn.close()

        if user:
            db_password = getattr(user, 'PasswordHash', None)
            
            if password == db_password:
                # 1. Set Session Data
                session['user_id'] = int(user.UserID)
                session['role_id'] = int(user.RoleID) if getattr(user, 'RoleID', None) is not None else None
                session['username'] = user.Username
                session['name'] = user.Name
                
                flash('✅ Login successful!', 'success')

                # 2. Smart Redirect based on Role
                if user.RoleID == 6:
                    # HR goes to Recruitment Dashboard
                    return redirect(url_for('recruitment_dashboard'))
                else:
                    # Everyone else (Admin/Manager/Employee) goes to Standard Dashboard
                    return redirect(url_for('dashboard'))
            else:
                flash('❌ Invalid username or password', 'danger')
        else:
            flash('❌ Invalid username or password', 'danger')

    return render_template('login.html')


# ===================== RECRUITMENT TRACKER =====================

@app.route('/recruitment')
@login_required
def recruitment_list():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # --- Filtering Parameters ---
    search_query = request.args.get('search', '').strip()
    dept_id = request.args.get('dept_id', '')
    pos_id = request.args.get('pos_id', '')
    status = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    job_id = request.args.get('job_id')

    # --- Building Query ---
    query = """
        SELECT R.*, P.PositionName, D.DEPTNAME
        FROM Recruitment R
        LEFT JOIN [Zktime].[dbo].[POSITIONS] P ON R.PositionID = P.PositionID
        LEFT JOIN [Zktime].[dbo].[DEPARTMENTS] D ON R.DepartmentID = D.DEPTID
        WHERE 1=1
    """
    params = []

    if search_query:
        query += " AND (R.FullName LIKE ? OR R.Phone LIKE ? OR R.Email LIKE ? OR R.SSN LIKE ?)"
        params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])
    
    if dept_id:
        query += " AND R.DepartmentID = ?"
        params.append(dept_id)

    if pos_id:
        query += " AND R.PositionID = ?"
        params.append(pos_id)

    if status:
        query += " AND R.Status = ?"
        params.append(status)

    if date_from:
        query += " AND R.ApplicationDate >= ?"
        params.append(date_from)

    if date_to:
        query += " AND R.ApplicationDate <= ?"
        params.append(date_to)


    if job_id:
        query += " AND R.JobID = ?"
        params.append(job_id)

    query += " ORDER BY R.ApplicationDate DESC"

    cursor.execute(query, params)
    candidates = cursor.fetchall()

    # --- Fetch Lists for Dropdowns ---
    cursor.execute("SELECT DEPTID, DEPTNAME FROM DEPARTMENTS ORDER BY DEPTNAME")
    depts = cursor.fetchall()
    cursor.execute("SELECT PositionID, PositionName FROM POSITIONS ORDER BY PositionName")
    positions = cursor.fetchall()

    conn.close()
    
    return render_template('recruitment_list.html', 
                           candidates=candidates,
                           depts=depts,
                           positions=positions,
                           filters=request.args) # Pass filters back to keep state


@app.route('/recruitment/form/<action>', methods=['GET', 'POST']) # Unified route
@app.route('/recruitment/form/<action>/<int:cid>', methods=['GET', 'POST'])
@login_required
def recruitment_manage(action, cid=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        try:
            # Basic Info
            name = request.form['name']
            phone = request.form['phone']
            dept_id = request.form.get('dept_id') or None
            pos_id = request.form.get('pos_id') or None
            status_id = request.form['status_id']
            
            # Checkboxes (Returns 'on' if checked, else None)
            doc_id = 1 if request.form.get('doc_id') else 0
            doc_cert = 1 if request.form.get('doc_cert') else 0
            doc_mil = 1 if request.form.get('doc_mil') else 0
            doc_crim = 1 if request.form.get('doc_crim') else 0
            doc_photo = 1 if request.form.get('doc_photo') else 0

            # Interview 1
            int1_by = request.form.get('int1_by')
            int1_date = request.form.get('int1_date') or None
            int1_note = request.form.get('int1_note')
            
            # Interview 2
            int2_by = request.form.get('int2_by')
            int2_date = request.form.get('int2_date') or None
            int2_note = request.form.get('int2_note')

            # Handle CV Upload
            cv_filename = request.form.get('current_cv_filename') # Keep old file by default
            if 'cv_file' in request.files:
                file = request.files['cv_file']
                if file.filename != '':
                    # Save file with ID prefix to avoid duplicates
                    safe_name = f"{cid or 'new'}_{file.filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], safe_name))
                    cv_filename = safe_name

            if action == 'Add':
                cursor.execute("""
                    INSERT INTO Recruitment 
                    (FullName, Phone, DepartmentID, PositionID, Status, 
                     Doc_IDCard, Doc_Certificate, Doc_Military, Doc_Criminal, Doc_Photos,
                     Int1_Interviewer, Int1_Date, Int1_Notes,
                     Int2_Interviewer, Int2_Date, Int2_Notes, CV_FileName, ApplicationDate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
                """, (name, phone, dept_id, pos_id, status_id, 
                      doc_id, doc_cert, doc_mil, doc_crim, doc_photo,
                      int1_by, int1_date, int1_note, 
                      int2_by, int2_date, int2_note, cv_filename))
                flash('تم إضافة ملف المرشح بنجاح', 'success')
            
            else: # Edit
                cursor.execute("""
                    UPDATE Recruitment SET 
                    FullName=?, Phone=?, DepartmentID=?, PositionID=?, Status=?,
                    Doc_IDCard=?, Doc_Certificate=?, Doc_Military=?, Doc_Criminal=?, Doc_Photos=?,
                    Int1_Interviewer=?, Int1_Date=?, Int1_Notes=?,
                    Int2_Interviewer=?, Int2_Date=?, Int2_Notes=?, CV_FileName=?
                    WHERE CandidateID=?
                """, (name, phone, dept_id, pos_id, status_id, 
                      doc_id, doc_cert, doc_mil, doc_crim, doc_photo,
                      int1_by, int1_date, int1_note, 
                      int2_by, int2_date, int2_note, cv_filename, cid))
                flash('تم تحديث ملف المرشح', 'success')

            conn.commit()
            return redirect(url_for('recruitment_list'))

        except Exception as e:
            conn.rollback()
            flash(f'Error: {e}', 'danger')
            print(e)

    # GET Data
    candidate = None
    if cid:
        cursor.execute("SELECT * FROM Recruitment WHERE CandidateID = ?", (cid,))
        candidate = cursor.fetchone()

    cursor.execute("SELECT * FROM RecruitmentStatuses")
    statuses = cursor.fetchall()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM DEPARTMENTS")
    depts = cursor.fetchall()
    cursor.execute("SELECT PositionID, PositionName FROM POSITIONS")
    positions = cursor.fetchall()
    conn.close()

    return render_template('recruitment_full_form.html', 
                           action=action, candidate=candidate, 
                           statuses=statuses, depts=depts, positions=positions)

# ===================== RECRUITMENT TRACKER UPDATED =====================

@app.route('/recruitment/add', methods=['GET', 'POST'])
@login_required
def recruitment_add():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        try:
            # 1. Basic Info
            name = request.form['name']
            phone = request.form.get('phone')
            email = request.form.get('email')
            ssn = request.form.get('ssn')
            address = request.form.get('address')
            dept_id = request.form.get('dept_id') or None
            pos_id = request.form.get('pos_id') or None
            
            # NEW: Job Post Link
            job_id = request.form.get('job_id') or None
            
            status = request.form.get('status_id')
            app_date = request.form.get('app_date') or datetime.date.today()

            # 2. Documents
            doc_id = 1 if request.form.get('doc_id') else 0
            doc_cert = 1 if request.form.get('doc_cert') else 0
            doc_mil = 1 if request.form.get('doc_mil') else 0
            doc_crim = 1 if request.form.get('doc_crim') else 0
            doc_photo = 1 if request.form.get('doc_photo') else 0

            # 3. Interviews
            int1_by = request.form.get('int1_by')
            int1_date = request.form.get('int1_date') or None
            int1_note = request.form.get('int1_note')
            int2_by = request.form.get('int2_by')
            int2_date = request.form.get('int2_date') or None
            int2_note = request.form.get('int2_note')

            # 4. NEW: Evaluation & Decision
            eval_tech = request.form.get('eval_tech') or 0
            eval_comm = request.form.get('eval_comm') or 0
            eval_exp = request.form.get('eval_exp') or 0
            eval_cult = request.form.get('eval_cult') or 0
            eval_notes = request.form.get('eval_notes')
            eval_decision = request.form.get('eval_decision')
            # Calculate Total
            eval_total = int(eval_tech) + int(eval_comm) + int(eval_exp) + int(eval_cult)

            # 5. File Upload
            cv_filename = None
            if 'cv_file' in request.files:
                file = request.files['cv_file']
                if file.filename != '':
                    safe_name = f"{datetime.datetime.now().strftime('%Y%m%d%H%M')}_{file.filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], safe_name))
                    cv_filename = safe_name

            # Insert Query
            cursor.execute("""
                INSERT INTO Recruitment 
                (FullName, Phone, Email, SSN, Address, DepartmentID, PositionID, JobID, Status, ApplicationDate,
                 Doc_IDCard, Doc_Certificate, Doc_Military, Doc_Criminal, Doc_Photos,
                 Int1_Interviewer, Int1_Date, Int1_Notes,
                 Int2_Interviewer, Int2_Date, Int2_Notes, 
                 Eval_Technical, Eval_Communication, Eval_Experience, Eval_Culture, Eval_Total, Eval_Notes, Eval_Decision,
                 CV_FileName)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, phone, email, ssn, address, dept_id, pos_id, job_id, status, app_date,
                  doc_id, doc_cert, doc_mil, doc_crim, doc_photo,
                  int1_by, int1_date, int1_note,
                  int2_by, int2_date, int2_note,
                  eval_tech, eval_comm, eval_exp, eval_cult, eval_total, eval_notes, eval_decision,
                  cv_filename))
            
            conn.commit()
            flash('✅ تم إضافة المرشح بنجاح', 'success')
            return redirect(url_for('recruitment_list'))

        except Exception as e:
            conn.rollback()
            flash(f'❌ حدث خطأ: {e}', 'danger')
            print(e)
        finally:
            conn.close()

    # GET Data
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTNAME")
    depts = cursor.fetchall()
    cursor.execute("SELECT PositionID, PositionName FROM [Zktime].[dbo].[POSITIONS] ORDER BY PositionName")
    positions = cursor.fetchall()
    cursor.execute("SELECT * FROM RecruitmentStatuses")
    statuses = cursor.fetchall()
    
    # NEW: Fetch Active Job Posts
    cursor.execute("SELECT JobID, JobTitle FROM JobPosts WHERE Status = 'Active' ORDER BY JobTitle")
    active_jobs = cursor.fetchall()
    
    conn.close()
    return render_template('recruitment_full_form.html', action='Add', depts=depts, positions=positions, statuses=statuses, active_jobs=active_jobs)

@app.route('/recruitment/edit/<int:cid>', methods=['GET', 'POST'])
@login_required
def recruitment_edit(cid):
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        try:
            # ... (Get all fields same as Add) ...
            # For brevity, I'm repeating the variables, but in your code ensure you get all of them
            name = request.form['name']
            phone = request.form.get('phone')
            email = request.form.get('email')
            ssn = request.form.get('ssn')
            address = request.form.get('address')
            dept_id = request.form.get('dept_id') or None
            pos_id = request.form.get('pos_id') or None
            job_id = request.form.get('job_id') or None
            status = request.form.get('status_id')
            app_date = request.form.get('app_date') or None
            
            doc_id = 1 if request.form.get('doc_id') else 0
            doc_cert = 1 if request.form.get('doc_cert') else 0
            doc_mil = 1 if request.form.get('doc_mil') else 0
            doc_crim = 1 if request.form.get('doc_crim') else 0
            doc_photo = 1 if request.form.get('doc_photo') else 0

            int1_by = request.form.get('int1_by')
            int1_date = request.form.get('int1_date') or None
            int1_note = request.form.get('int1_note')
            int2_by = request.form.get('int2_by')
            int2_date = request.form.get('int2_date') or None
            int2_note = request.form.get('int2_note')
            
            # Evaluation
            eval_tech = request.form.get('eval_tech') or 0
            eval_comm = request.form.get('eval_comm') or 0
            eval_exp = request.form.get('eval_exp') or 0
            eval_cult = request.form.get('eval_cult') or 0
            eval_notes = request.form.get('eval_notes')
            eval_decision = request.form.get('eval_decision')
            eval_total = int(eval_tech) + int(eval_comm) + int(eval_exp) + int(eval_cult)

            cv_filename = request.form.get('current_cv_filename')
            if 'cv_file' in request.files:
                file = request.files['cv_file']
                if file.filename != '':
                    safe_name = f"{datetime.datetime.now().strftime('%Y%m%d%H%M')}_{file.filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], safe_name))
                    cv_filename = safe_name

            cursor.execute("""
                UPDATE Recruitment SET 
                FullName=?, Phone=?, Email=?, SSN=?, Address=?, DepartmentID=?, PositionID=?, JobID=?, Status=?, ApplicationDate=?,
                Doc_IDCard=?, Doc_Certificate=?, Doc_Military=?, Doc_Criminal=?, Doc_Photos=?,
                Int1_Interviewer=?, Int1_Date=?, Int1_Notes=?,
                Int2_Interviewer=?, Int2_Date=?, Int2_Notes=?,
                Eval_Technical=?, Eval_Communication=?, Eval_Experience=?, Eval_Culture=?, Eval_Total=?, Eval_Notes=?, Eval_Decision=?,
                CV_FileName=?
                WHERE CandidateID=?
            """, (name, phone, email, ssn, address, dept_id, pos_id, job_id, status, app_date,
                  doc_id, doc_cert, doc_mil, doc_crim, doc_photo,
                  int1_by, int1_date, int1_note,
                  int2_by, int2_date, int2_note,
                  eval_tech, eval_comm, eval_exp, eval_cult, eval_total, eval_notes, eval_decision,
                  cv_filename, cid))

            conn.commit()
            flash('✅ تم تحديث بيانات المرشح بنجاح', 'success')
            return redirect(url_for('recruitment_list'))

        except Exception as e:
            conn.rollback()
            flash(f'❌ حدث خطأ: {e}', 'danger')
        finally:
            conn.close()

    # GET Data
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Recruitment WHERE CandidateID = ?", (cid,))
    candidate = cursor.fetchone()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTNAME")
    depts = cursor.fetchall()
    cursor.execute("SELECT PositionID, PositionName FROM [Zktime].[dbo].[POSITIONS] ORDER BY PositionName")
    positions = cursor.fetchall()
    cursor.execute("SELECT * FROM RecruitmentStatuses")
    statuses = cursor.fetchall()
    # Fetch ALL jobs (active or not) for Edit mode, so we don't lose the selection if job is closed
    cursor.execute("SELECT JobID, JobTitle FROM JobPosts ORDER BY JobTitle")
    active_jobs = cursor.fetchall() 
    conn.close()

    return render_template('recruitment_full_form.html', action='Edit', candidate=candidate, depts=depts, positions=positions, statuses=statuses, active_jobs=active_jobs)



@app.route('/recruitment/dashboard')
@login_required
def recruitment_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Funnel Analysis (Status Counts)
    cursor.execute("SELECT Status, COUNT(*) as cnt FROM Recruitment GROUP BY Status")
    status_rows = cursor.fetchall()

    # 2. Candidates by Department
    cursor.execute("""
        SELECT D.DEPTNAME, COUNT(*) as cnt 
        FROM Recruitment R
        LEFT JOIN [Zktime].[dbo].[DEPARTMENTS] D ON R.DepartmentID = D.DEPTID
        GROUP BY D.DEPTNAME
    """)
    dept_rows = cursor.fetchall()

    conn.close()

    # Prepare Data
    chart_data = {
        'status_labels': [r.Status for r in status_rows],
        'status_data': [r.cnt for r in status_rows],
        'dept_labels': [r.DEPTNAME or 'General' for r in dept_rows],
        'dept_data': [r.cnt for r in dept_rows]
    }

    total = sum(chart_data['status_data'])

    return render_template('recruitment_dashboard.html', 
                           total_candidates=total,
                           chart_data=json.dumps(chart_data, ensure_ascii=False))

@app.route('/recruitment/analytics')
@login_required  # <--- تغيير هذا السطر من @admin_required إلى @login_required
def recruitment_analytics():
    # التحقق من الصلاحية (سماح للأدمن 1 وموظف التوظيف 6)
    if session.get('role_id') not in [1, 6]:
        flash('عذراً، ليس لديك صلاحية لدخول هذه الصفحة.', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Total Stats
    cursor.execute("SELECT COUNT(*) FROM Recruitment")
    total_candidates = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM Recruitment WHERE Status = 'Hired'")
    total_hired = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM Recruitment WHERE Status = 'Rejected'")
    total_rejected = cursor.fetchone()[0]
    
    # 2. Funnel Data (For Chart)
    stages = ['New', 'Screening', 'Interview', 'Offer', 'Hired']
    funnel_data = []
    for stage in stages:
        cursor.execute(f"SELECT COUNT(*) FROM Recruitment WHERE Status = ?", (stage,))
        count = cursor.fetchone()[0]
        funnel_data.append(count)

    # 3. FUTURE VIEW: Upcoming Interviews
    today = datetime.date.today()
    cursor.execute("""
        SELECT CandidateID, FullName, PositionName, 'Interview 1' as Stage, Int1_Date as InterviewDate, Int1_Interviewer as Interviewer
        FROM Recruitment R 
        LEFT JOIN [Zktime].[dbo].[POSITIONS] P ON R.PositionID = P.PositionID
        WHERE Int1_Date >= ?
        UNION ALL
        SELECT CandidateID, FullName, PositionName, 'Interview 2' as Stage, Int2_Date as InterviewDate, Int2_Interviewer as Interviewer
        FROM Recruitment R 
        LEFT JOIN [Zktime].[dbo].[POSITIONS] P ON R.PositionID = P.PositionID
        WHERE Int2_Date >= ?
        ORDER BY InterviewDate ASC
    """, (today, today))
    upcoming_interviews = cursor.fetchall()

    # 4. Department Analysis
    cursor.execute("""
        SELECT TOP 5 D.DEPTNAME, COUNT(*) as cnt 
        FROM Recruitment R
        LEFT JOIN [Zktime].[dbo].[DEPARTMENTS] D ON R.DepartmentID = D.DEPTID
        GROUP BY D.DEPTNAME
        ORDER BY cnt DESC
    """)
    dept_stats = cursor.fetchall()

    conn.close()

    # Prepare Chart JSON
    analytics_data = {
        'funnel_labels': ['New', 'Screening', 'Interview', 'Offer', 'Hired'],
        'funnel_counts': funnel_data,
        'dept_labels': [r.DEPTNAME for r in dept_stats],
        'dept_counts': [r.cnt for r in dept_stats]
    }

    return render_template('recruitment_analytics.html', 
                           total=total_candidates, 
                           hired=total_hired, 
                           rejected=total_rejected,
                           upcoming=upcoming_interviews,
                           analytics_data=json.dumps(analytics_data))

@app.route('/recruitment/import', methods=['GET', 'POST'])
@login_required
def recruitment_import():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('❌ لا يوجد ملف', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('❌ لم يتم اختيار ملف', 'danger')
            return redirect(request.url)

        try:
            # 1. Read the Excel File
            df = pd.read_excel(file)
            
            # 2. Connect to DB
            conn = get_db_connection()
            cursor = conn.cursor()

            # 3. Cache Departments and Positions for ID Lookup
            cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS]")
            dept_map = {row.DEPTNAME: row.DEPTID for row in cursor.fetchall()}

            cursor.execute("SELECT PositionID, PositionName FROM [Zktime].[dbo].[POSITIONS]")
            pos_map = {row.PositionName: row.PositionID for row in cursor.fetchall()}

            count = 0
            
            # 4. Loop through rows and insert
            for index, row in df.iterrows():
                dept_id = dept_map.get(str(row.get('Department', '')).strip()) 
                pos_id = pos_map.get(str(row.get('Position', '')).strip())
                
                full_name = row.get('Name')
                phone = str(row.get('Phone', ''))
                status = row.get('Status', 'New') 
                notes = str(row.get('Notes', '')) # <--- جديد: قراءة الملاحظات
                
                if full_name: 
                    cursor.execute("""
                        INSERT INTO Recruitment (FullName, Phone, DepartmentID, PositionID, Status, ApplicationDate, Notes)
                        VALUES (?, ?, ?, ?, ?, GETDATE(), ?)
                    """, (full_name, phone, dept_id, pos_id, status, notes)) # <--- تمرير الملاحظات
                    count += 1

            conn.commit()
            conn.close()
            flash(f'✅ تم استيراد {count} مرشح بنجاح!', 'success')
            return redirect(url_for('recruitment_list'))

        except Exception as e:
            flash(f'❌ حدث خطأ أثناء الاستيراد: {e}', 'danger')
            return redirect(request.url)

    return render_template('recruitment_import.html')

@app.route('/dashboard')
@login_required
def dashboard():
    ctx = {
        'user_id': session.get('user_id'),
        'username': session.get('username'),
        'name': session.get('name'),
        'role_id': session.get('role_id'),
        'is_admin': is_admin(),
        'users_count': 0, 'employees_count': 0, 'evals_count': 0, 'avg_score': 0,
        'rating_distribution': [], 'eval_type_distribution': [], 'monthly_trends': [],
        'top_performers': [], 'active_evaluators': [], 'score_ranges': [],
        'recent_evaluations': [], 'inactive_managers': [], 'dept_eval_percentage': []
    }
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # --- Base SQL for joining tables ---
        base_query_joins = """
            FROM [Zktime].[dbo].[Evaluations] E
            LEFT JOIN [Zktime].[dbo].[USERINFO] UI ON E.EmployeeUserID = UI.USERID
            LEFT JOIN [Zktime].[dbo].[Users] U ON E.EmployeeUserID = U.UserID
            LEFT JOIN [Zktime].[dbo].[Users] Mgr ON E.EvaluatorUserID = Mgr.UserID
            LEFT JOIN [Zktime].[dbo].[EvaluationTypes] ET ON E.EvaluationTypeID = ET.EvaluationTypeID
        """
        where_clause = " WHERE 1=1 "
        params = []

        if is_admin():
            # --- ADMIN QUERIES (COMPANY-WIDE) ---
            cursor.execute("SELECT COUNT(*) AS cnt FROM [Zktime].[dbo].[Users]")
            ctx['users_count'] = cursor.fetchone().cnt or 0
            cursor.execute("SELECT COUNT(*) AS cnt FROM [Zktime].[dbo].[USERINFO]")
            ctx['employees_count'] = cursor.fetchone().cnt or 0
            cursor.execute("SELECT COUNT(*) AS cnt FROM [Zktime].[dbo].[Evaluations]")
            ctx['evals_count'] = cursor.fetchone().cnt or 0
            cursor.execute("SELECT AVG(OverallScore) AS avg_score FROM [Zktime].[dbo].[Evaluations] WHERE OverallScore IS NOT NULL")
            ctx['avg_score'] = cursor.fetchone().avg_score

            where_clause = " WHERE 1=1 "
            params = []

            # 1. Inactive Managers (FIXED: Added DEPTNAME)
            cursor.execute("""
                SELECT 
                    U.UserID, U.Name, D.DEPTNAME,
                    (SELECT COUNT(*) FROM [Zktime].[dbo].[USERINFO] WHERE DEFAULTDEPTID = U.DepartmentID AND IsActive = 1) as TotalEmployees
                FROM [Zktime].[dbo].[Users] U
                LEFT JOIN [Zktime].[dbo].[DEPARTMENTS] D ON U.DepartmentID = D.DEPTID
                WHERE U.RoleID = 3 AND U.UserID NOT IN (
                    SELECT DISTINCT EvaluatorUserID FROM [Zktime].[dbo].[Evaluations] WHERE EvaluatorUserID IS NOT NULL
                )
                ORDER BY U.Name
            """)
            ctx['inactive_managers'] = cursor.fetchall()
            
            # 2. Active Evaluators
            cursor.execute("""
                SELECT TOP 5 COALESCE(Mgr.Name, Mgr.Username) as EvaluatorName,
                    COUNT(E.EvaluationID) as evaluation_count,
                    COUNT(DISTINCT E.EmployeeUserID) as distinct_evaluated,
                    (SELECT COUNT(*) FROM [Zktime].[dbo].[USERINFO] WHERE DEFAULTDEPTID = Mgr.DepartmentID AND IsActive = 1) as total_dept_employees
                FROM [Zktime].[dbo].[Evaluations] E
                LEFT JOIN [Zktime].[dbo].[Users] Mgr ON E.EvaluatorUserID = Mgr.UserID
                WHERE 1=1 GROUP BY Mgr.UserID, Mgr.Name, Mgr.Username, Mgr.DepartmentID
                HAVING COALESCE(Mgr.Name, Mgr.Username) IS NOT NULL ORDER BY evaluation_count DESC
            """)
            ctx['active_evaluators'] = cursor.fetchall()

        else:
            # --- NON-ADMIN QUERIES (DEPARTMENT-SPECIFIC) ---
            cursor.execute("SELECT DepartmentID FROM [Zktime].[dbo].[Users] WHERE UserID = ?", (ctx['user_id'],))
            user = cursor.fetchone()
            dept_id = user.DepartmentID if user and user.DepartmentID else None

            if dept_id:
                cursor.execute("SELECT COUNT(*) AS cnt FROM [Zktime].[dbo].[Users] WHERE DepartmentID = ?", (dept_id,))
                ctx['users_count'] = cursor.fetchone().cnt or 0
                cursor.execute("SELECT COUNT(*) AS cnt FROM [Zktime].[dbo].[USERINFO] WHERE DEFAULTDEPTID = ?", (dept_id,))
                ctx['employees_count'] = cursor.fetchone().cnt or 0
                cursor.execute("SELECT COUNT(E.EvaluationID) AS cnt FROM [Zktime].[dbo].[Evaluations] E JOIN [Zktime].[dbo].[USERINFO] UI ON E.EmployeeUserID = UI.USERID WHERE UI.DEFAULTDEPTID = ?", (dept_id,))
                ctx['evals_count'] = cursor.fetchone().cnt or 0
                cursor.execute("SELECT AVG(E.OverallScore) AS avg_score FROM [Zktime].[dbo].[Evaluations] E JOIN [Zktime].[dbo].[USERINFO] UI ON E.EmployeeUserID = UI.USERID WHERE UI.DEFAULTDEPTID = ? AND E.OverallScore IS NOT NULL", (dept_id,))
                ctx['avg_score'] = cursor.fetchone().avg_score
                where_clause = " WHERE UI.DEFAULTDEPTID = ? "
                params = [dept_id]
            else:
                where_clause = " WHERE 1=0 "
                params = []

        # --- CHARTS & LISTS ---
        cursor.execute(f"SELECT OverallRating, COUNT(*) as count FROM [Zktime].[dbo].[Evaluations] E LEFT JOIN [Zktime].[dbo].[USERINFO] UI ON E.EmployeeUserID = UI.USERID {where_clause} AND OverallRating IS NOT NULL GROUP BY OverallRating ORDER BY CASE OverallRating WHEN 'ممتاز' THEN 1 WHEN 'جيد جدا' THEN 2 WHEN 'جيد' THEN 3 WHEN 'مقبول' THEN 4 ELSE 5 END", params)
        ctx['rating_distribution'] = cursor.fetchall()

        cursor.execute(f"SELECT COALESCE(ET.DisplayName, E.EvaluationType, 'غير محدد') as EvaluationType, COUNT(*) as count FROM [Zktime].[dbo].[Evaluations] E LEFT JOIN [Zktime].[dbo].[USERINFO] UI ON E.EmployeeUserID = UI.USERID LEFT JOIN [Zktime].[dbo].[EvaluationTypes] ET ON E.EvaluationTypeID = ET.EvaluationTypeID {where_clause} GROUP BY COALESCE(ET.DisplayName, E.EvaluationType, 'غير محدد') ORDER BY count DESC", params)
        ctx['eval_type_distribution'] = cursor.fetchall()

        cursor.execute(f"SELECT TOP 5 COALESCE(UI.NAME, U.Name, U.Username) as EmployeeName, E.OverallScore, E.OverallRating, E.EvaluationDate {base_query_joins} {where_clause} AND E.EvaluationDate >= DATEADD(day, -30, GETDATE()) ORDER BY E.OverallScore DESC", params)
        ctx['top_performers'] = cursor.fetchall()

        cursor.execute(f"SELECT TOP 10 E.EvaluationID, COALESCE(UI.NAME, U.Name, U.Username) as EmployeeName, COALESCE(Mgr.Name, Mgr.Username) as EvaluatorName, E.OverallScore, E.OverallRating, COALESCE(ET.DisplayName, E.EvaluationType) as EvaluationType, E.EvaluationDate {base_query_joins} {where_clause} ORDER BY E.EvaluationDate DESC", params)
        ctx['recent_evaluations'] = cursor.fetchall()

        cursor.execute(f"""
            SELECT CASE WHEN OverallScore >= 90 THEN 'ممتاز (90-100)' WHEN OverallScore >= 80 THEN 'جيد جدا (80-89)'
                   WHEN OverallScore >= 70 THEN 'جيد (70-79)' WHEN OverallScore >= 60 THEN 'مقبول (60-69)' ELSE 'ضعيف (أقل من 60)' END as score_range,
            COUNT(*) as count
            FROM [Zktime].[dbo].[Evaluations] E LEFT JOIN [Zktime].[dbo].[USERINFO] UI ON E.EmployeeUserID = UI.USERID
            {where_clause} AND OverallScore IS NOT NULL
            GROUP BY CASE WHEN OverallScore >= 90 THEN 'ممتاز (90-100)' WHEN OverallScore >= 80 THEN 'جيد جدا (80-89)'
                     WHEN OverallScore >= 70 THEN 'جيد (70-79)' WHEN OverallScore >= 60 THEN 'مقبول (60-69)' ELSE 'ضعيف (أقل من 60)' END
            ORDER BY MIN(OverallScore) DESC
        """, params)
        ctx['score_ranges'] = cursor.fetchall()

        # --- TURNOVER ANALYSIS ---
        cursor.execute("SELECT YEAR(HiredDay) as Yr, COUNT(*) as Count FROM (SELECT HiredDay FROM [Zktime].[dbo].[USERINFO] WHERE HiredDay IS NOT NULL UNION ALL SELECT HiredDay FROM [Zktime].[dbo].[EmployeeArchive] WHERE HiredDay IS NOT NULL) as AllHires WHERE YEAR(HiredDay) > 1900 GROUP BY YEAR(HiredDay) ORDER BY Yr")
        hires_rows = cursor.fetchall()
        
        cursor.execute("SELECT YEAR(EndDay) as Yr, COUNT(*) as Count FROM [Zktime].[dbo].[EmployeeArchive] WHERE EndDay IS NOT NULL AND YEAR(EndDay) > 1900 GROUP BY YEAR(EndDay) ORDER BY Yr")
        left_rows = cursor.fetchall()
        
        cursor.execute("SELECT D.DEPTNAME, COUNT(*) as Count FROM [Zktime].[dbo].[EmployeeArchive] A LEFT JOIN [Zktime].[dbo].[DEPARTMENTS] D ON A.ArchivedDeptID = D.DEPTID GROUP BY D.DEPTNAME ORDER BY Count DESC")
        dept_turnover = cursor.fetchall()
        
        cursor.execute("SELECT P.PositionName, COUNT(*) as Count FROM [Zktime].[dbo].[EmployeeArchive] A LEFT JOIN [Zktime].[dbo].[POSITIONS] P ON A.ArchivedPosID = P.PositionID GROUP BY P.PositionName ORDER BY Count DESC")
        pos_turnover = cursor.fetchall()

    except Exception as e:
        print(f"Dashboard Error: {e}")
    finally:
        if conn: conn.close()

    # Process Data
    all_years = sorted(list(set([r.Yr for r in hires_rows] + [r.Yr for r in left_rows])))
    hires_map = {r.Yr: r.Count for r in hires_rows}
    left_map = {r.Yr: r.Count for r in left_rows}
    hires_data = [hires_map.get(y, 0) for y in all_years]
    left_data = [left_map.get(y, 0) for y in all_years]
    net_data = [h - l for h, l in zip(hires_data, left_data)]

    chart_data = {
        'rating_labels': [str(row.OverallRating) for row in ctx.get('rating_distribution', [])],
        'rating_data': [int(row.count) for row in ctx.get('rating_distribution', [])],
        'type_labels': [str(row.EvaluationType) for row in ctx.get('eval_type_distribution', [])],
        'type_data': [int(row.count) for row in ctx.get('eval_type_distribution', [])],
        'score_range_labels': [str(row.score_range) for row in ctx.get('score_ranges', [])],
        'score_range_data': [int(row.count) for row in ctx.get('score_ranges', [])],
        'turnover_years': all_years, 'hires_data': hires_data, 'left_data': left_data, 'net_data': net_data,
        'dept_turnover_labels': [row.DEPTNAME or 'غير محدد' for row in dept_turnover],
        'dept_turnover_data': [row.Count for row in dept_turnover],
        'pos_turnover_labels': [row.PositionName or 'غير محدد' for row in pos_turnover],
        'pos_turnover_data': [row.Count for row in pos_turnover],
    }
    ctx['chart_data'] = json.dumps(chart_data, ensure_ascii=False)
    
    return render_template('dashboard.html', **ctx)

@app.route('/users')
@login_required
def users():
    search = request.args.get('search', '').strip()
    role_id_filter = request.args.get('role_id', '')
    dept_id_filter = request.args.get('dept_id', '')
    conn = get_db_connection()
    cursor = conn.cursor()
    query_base = "SELECT U.UserID, U.Username, COALESCE(U.Name, UI.NAME) AS FullName, U.DepartmentID, D.DEPTNAME, U.RoleID, R.RoleName FROM [Zktime].[dbo].[Users] U LEFT JOIN [Zktime].[dbo].[USERINFO] UI ON U.UserID = UI.USERID LEFT JOIN [Zktime].[dbo].[DEPARTMENTS] D ON U.DepartmentID = D.DEPTID LEFT JOIN [Zktime].[dbo].[Roles] R ON U.RoleID = R.RoleID"
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
    cursor.execute("SELECT RoleID, RoleName FROM [Zktime].[dbo].[Roles] ORDER BY RoleID")
    roles = cursor.fetchall()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    depts = cursor.fetchall()
    conn.close()
    return render_template('users.html', users=users, roles=roles, depts=depts, filters=request.args, is_admin=is_admin())

@app.route('/users/add', methods=['GET', 'POST'])
@admin_required
def add_user():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT RoleID, RoleName FROM [Zktime].[dbo].[Roles] ORDER BY RoleID")
    roles = cursor.fetchall()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    depts = cursor.fetchall()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'] 
        name = request.form.get('name') or None
        role_id = request.form.get('role_id') or None
        dept_id = request.form.get('department_id') or None
        try:
            cursor.execute("INSERT INTO [Zktime].[dbo].[Users] (Username, PasswordHash, RoleID, Name, DepartmentID) VALUES (?, ?, ?, ?, ?)", (username, password, role_id, name, dept_id))
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
    cursor.execute("SELECT RoleID, RoleName FROM [Zktime].[dbo].[Roles] ORDER BY RoleID")
    roles = cursor.fetchall()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    depts = cursor.fetchall()
    cursor.execute("SELECT UserID, Username, RoleID, Name, DepartmentID FROM [Zktime].[dbo].[Users] WHERE UserID = ?", (user_id,))
    user = cursor.fetchone()
    if request.method == 'POST':
        username = request.form['username']
        name = request.form.get('name') or None
        role_id = request.form.get('role_id') or None
        dept_id = request.form.get('department_id') or None
        new_password = request.form.get('password') or None
        if new_password:
            cursor.execute("UPDATE [Zktime].[dbo].[Users] SET Username = ?, Name = ?, RoleID = ?, DepartmentID = ?, PasswordHash = ? WHERE UserID = ?", (username, name, role_id, dept_id, new_password, user_id))
        else:
            cursor.execute("UPDATE [Zktime].[dbo].[Users] SET Username = ?, Name = ?, RoleID = ?, DepartmentID = ? WHERE UserID = ?", (username, name, role_id, dept_id, user_id))
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
    cursor.execute("DELETE FROM [Zktime].[dbo].[Users] WHERE UserID = ?", (user_id,))
    conn.commit()
    conn.close()
    flash('User deleted successfully!', 'info')
    return redirect(url_for('users'))

@app.route('/userinfo')
@login_required 
def userinfo_list():
    search = request.args.get('search', '').strip()
    employee_class_filter = request.args.get('employee_class', '')
    gender = request.args.get('gender', '')
    department = request.args.get('department', '')
    position = request.args.get('position', '')
    sort = request.args.get('sort', 'USERID')
    order = request.args.get('order', 'asc')
    conn = get_db_connection()
    cursor = conn.cursor()
    user_id = session.get('user_id')
    role_id = session.get('role_id')
    query_base = """
        SELECT UI.USERID, UI.BADGENUMBER, UI.SSN, UI.NAME, UI.GENDER, UI.TITLE, UI.HIREDDAY,
               UI.DEFAULTDEPTID, UI.PositionID, UI.employee_class, D.DEPTNAME, P.PositionName
        FROM [Zktime].[dbo].[USERINFO] AS UI
        LEFT JOIN [Zktime].[dbo].[DEPARTMENTS] AS D ON UI.DEFAULTDEPTID = D.DEPTID
        LEFT JOIN [Zktime].[dbo].[POSITIONS] AS P ON UI.PositionID = P.PositionID
    """
    where_clauses = ["UI.IsActive = 1"]
    params = []
    if is_admin():
        where_clauses.append("1=1")
    elif role_id == 3:
        cursor.execute("SELECT DepartmentID FROM [Zktime].[dbo].[Users] WHERE UserID = ?", (user_id,))
        user = cursor.fetchone()
        dept_id = user.DepartmentID if user and user.DepartmentID else None
        if dept_id:
            where_clauses.append("UI.DEFAULTDEPTID = ?")
            params.append(dept_id)
        else:
            where_clauses.append("1=0") 
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
        if position:
            where_clauses.append("UI.PositionID = ?")
            params.append(position)
    allowed_sorts = {'USERID': 'UI.USERID', 'BADGENUMBER': 'UI.BADGENUMBER', 'SSN': 'UI.SSN', 'NAME': 'UI.NAME', 'employee_class': 'UI.employee_class', 'GENDER': 'UI.GENDER', 'TITLE': 'UI.TITLE', 'DEFAULTDEPTID': 'UI.DEFAULTDEPTID', 'PositionID': 'UI.PositionID', 'HIREDDAY': 'UI.HIREDDAY'}
    sort_field = allowed_sorts.get(sort, 'UI.USERID')
    order_sql = 'ASC' if order.lower() == 'asc' else 'DESC'
    query = f"{query_base} WHERE {' AND '.join(where_clauses)} ORDER BY {sort_field} {order_sql}"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    all_departments = cursor.fetchall()
    cursor.execute("SELECT PositionID, PositionName FROM [Zktime].[dbo].[POSITIONS] ORDER BY PositionID")
    all_positions = cursor.fetchall()
    conn.close()
    return render_template('userinfo.html', users=rows, is_admin=is_admin(), role_id=role_id, departments=all_departments, positions=all_positions)

@app.route('/userinfo/add', methods=['GET', 'POST'])
@admin_required
def userinfo_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    depts = cursor.fetchall()
    cursor.execute("SELECT PositionID, PositionName, DeptID FROM [Zktime].[dbo].[POSITIONS] ORDER BY PositionName")
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
        cursor.execute("INSERT INTO [Zktime].[dbo].[USERINFO] (BADGENUMBER, SSN, NAME, GENDER, TITLE, DEFAULTDEPTID, PositionID, employee_class) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (badge, ssn, name, gender, title, defaultdept, positionid, employee_class))
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
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    depts = cursor.fetchall()
    cursor.execute("SELECT PositionID, PositionName, DeptID FROM [Zktime].[dbo].[POSITIONS] ORDER BY PositionName")
    positions_rows = cursor.fetchall()
    positions_list = [{'PositionID': p.PositionID, 'PositionName': p.PositionName, 'DeptID': p.DeptID} for p in positions_rows]
    cursor.execute("SELECT USERID, BADGENUMBER, SSN, NAME, GENDER, TITLE, DEFAULTDEPTID, PositionID, employee_class FROM [Zktime].[dbo].[USERINFO] WHERE USERID = ?", (uid,))
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
        cursor.execute("UPDATE [Zktime].[dbo].[USERINFO] SET BADGENUMBER = ?, SSN = ?, NAME = ?, GENDER = ?, TITLE = ?, DEFAULTDEPTID = ?, PositionID = ?, employee_class = ? WHERE USERID = ?", (badge, ssn, name, gender, title, defaultdept, positionid, employee_class, uid))
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
    training_history = []  # <--- 1. Initialize variable

    try:
        # Query 1: Get User Info
        cursor.execute("SELECT UI.*, D.DEPTNAME, P.PositionName FROM [Zktime].[dbo].[USERINFO] UI LEFT JOIN [Zktime].[dbo].[DEPARTMENTS] D ON UI.DEFAULTDEPTID = D.DEPTID LEFT JOIN [Zktime].[dbo].[POSITIONS] P ON UI.PositionID = P.PositionID WHERE UI.USERID = ?", (uid,))
        user = cursor.fetchone()

        if not user:
            flash('❌ لم يتم العثور على بيانات الموظف.', 'danger')
            return redirect(url_for('userinfo_list'))

        # Query 2: Get Average Score & Count
        cursor.execute("""
            SELECT AVG(OverallScore) as avg_score, COUNT(*) as eval_count 
            FROM [Zktime].[dbo].[Evaluations] WHERE EmployeeUserID = ?
        """, (uid,))
        avg_stats = cursor.fetchone()

        # Query 3: Get Evaluation History
        cursor.execute("""
            SELECT E.EvaluationID, E.EvaluationDate, E.OverallScore, E.OverallRating,
                COALESCE(ET.DisplayName, E.EvaluationType) as EvaluationType, 
                COALESCE(Mgr.Name, Mgr.Username) AS EvaluatorName
            FROM [Zktime].[dbo].[Evaluations] E
            LEFT JOIN [Zktime].[dbo].[Users] Mgr ON E.EvaluatorUserID = Mgr.UserID
            LEFT JOIN [Zktime].[dbo].[EvaluationTypes] ET ON E.EvaluationTypeID = ET.EvaluationTypeID
            WHERE E.EmployeeUserID = ?
            ORDER BY E.EvaluationDate DESC
        """, (uid,))
        history = cursor.fetchall()

        # --- NEW: Query 4: Get Training History ---
        cursor.execute("""
            SELECT TE.Grade, TE.PassStatus, TE.EnrollmentDate, 
                   TC.TrainingCourseText, 
                   TS.SessionDate, TS.IsExternal, TS.ExternalTrainerName, TS.ExternalCompany, 
                   U.Name as IntTrainer
            FROM TrainingEnrollments TE
            JOIN TrainingSessions TS ON TE.SessionID = TS.SessionID
            JOIN TrainingCourses TC ON TS.CourseID = TC.TrainingCourseID
            LEFT JOIN Users U ON TS.InstructorID = U.UserID
            WHERE TE.EmployeeUserID = ?
            ORDER BY TS.SessionDate DESC
        """, (uid,))
        training_history = cursor.fetchall()
        # ------------------------------------------

    except Exception as e:
        flash(f"Error fetching employee details: {e}", "danger")
        print(f"Error in userinfo_view: {e}") 
    finally:
        if conn:
            conn.close()

    return render_template('employee_profile.html', 
                           user=user, 
                           is_admin=is_admin(),
                           avg_stats=avg_stats, 
                           history=history,
                           training_history=training_history) # <--- 2. Pass to template

@app.route('/archive-whys')
@admin_required
def whys_list():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ArchiveWhys ORDER BY WhyText")
    whys = cursor.fetchall()
    conn.close()
    return render_template('whys_list.html', whys=whys)

@app.route('/archive-whys/add', methods=['GET', 'POST'])
@admin_required
def whys_add():
    if request.method == 'POST':
        text = request.form['why_text']
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO ArchiveWhys (WhyText) VALUES (?)", (text,))
            conn.commit()
            flash('تم إضافة السبب التفصيلي بنجاح', 'success')
            return redirect(url_for('whys_list'))
        except Exception as e:
            conn.rollback()
            flash(f'حدث خطأ: {e}', 'danger')
        finally:
            conn.close()     
    return render_template('why_form.html', action='Add', why=None)

@app.route('/archive-whys/edit/<int:wid>', methods=['GET', 'POST'])
@admin_required
def whys_edit(wid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ArchiveWhys WHERE WhyID = ?", (wid,))
    why = cursor.fetchone()
    if request.method == 'POST':
        text = request.form['why_text']
        try:
            cursor.execute("UPDATE ArchiveWhys SET WhyText = ? WHERE WhyID = ?", (text, wid))
            conn.commit()
            flash('تم تعديل السبب التفصيلي بنجاح', 'success')
            return redirect(url_for('whys_list'))
        except Exception as e:
            conn.rollback()
            flash(f'حدث خطأ: {e}', 'danger')
        finally:
            conn.close()
    conn.close()
    return render_template('why_form.html', action='Edit', why=why)

@app.route('/archive-whys/delete/<int:wid>', methods=['POST'])
@admin_required
def whys_delete(wid):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) as cnt FROM EmployeeArchive WHERE ArchiveWhyID = ?", (wid,))
        if cursor.fetchone().cnt > 0:
            flash('لا يمكن حذف هذا السبب، إنه مستخدم في سجلات الأرشيف.', 'danger')
        else:
            cursor.execute("DELETE FROM ArchiveWhys WHERE WhyID = ?", (wid,))
            conn.commit()
            flash('تم حذف السبب التفصيلي بنجاح', 'info')
    except Exception as e:
        conn.rollback()
        flash(f'حدث خطأ: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('whys_list'))

@app.route('/userinfo/archive/<int:uid>', methods=['GET', 'POST'])
@admin_required
def userinfo_archive(uid):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM [Zktime].[dbo].[USERINFO] WHERE USERID = ?", (uid,))
        user = cursor.fetchone()
        if not user:
            flash('لم يتم العثور على الموظف.', 'danger')
            conn.close()
            return redirect(url_for('userinfo_list'))
        if request.method == 'POST':
            try:
                reason_id = request.form['reason_id'] 
                why_id = request.form['why_id']
                comment = request.form['comment']
                admin_user_id = session.get('user_id')
                date_mode = request.form.get('date_mode')
                end_date = request.form.get('manual_date') if date_mode == 'manual' else datetime.date.today()

                cursor.execute("INSERT INTO EmployeeArchive (UserID, Name, HiredDay, ArchiveReasonID, ArchiveWhyID, ArchiveComment, AdminUserID, EndDay, ArchivedSSN) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (user.USERID, user.NAME, user.HIREDDAY, reason_id, why_id, comment, admin_user_id, end_date, user.SSN))
                archived_badge = f"DEL_{user.USERID}"
                archived_ssn = f"DEL_{user.USERID}"
                cursor.execute("UPDATE [Zktime].[dbo].[USERINFO] SET IsActive = 0, BADGENUMBER = ?, SSN = ? WHERE USERID = ?", (archived_badge, archived_ssn, uid))
                conn.commit()
                flash(f'تم أرشفة الموظف "{user.NAME}" بنجاح.', 'success')
                conn.close()
                return redirect(url_for('userinfo_list'))
            except Exception as e:
                conn.rollback()
                print(f"Archive Error: {e}") 
                flash(f'حدث خطأ أثناء الأرشفة: {e}', 'danger')

        cursor.execute("SELECT * FROM ArchiveReasons ORDER BY ReasonText")
        reasons = cursor.fetchall()
        cursor.execute("SELECT * FROM ArchiveWhys ORDER BY WhyText")
        whys = cursor.fetchall()
        return render_template('archive_form.html', user=user, reasons=reasons, whys=whys)
    finally:
        try: conn.close() 
        except: pass

@app.route('/userinfo/archive_report')
@admin_required
def userinfo_archive_report():
    conn = get_db_connection()
    cursor = conn.cursor()
    reason_filter = request.args.get('reason_id')
    why_filter = request.args.get('why_id')
    search_term = request.args.get('search', '').strip()
    dept_filter = request.args.get('dept_id')
    pos_filter = request.args.get('pos_id')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    where_clause = "1=1"
    params = []
    if reason_filter:
        where_clause += " AND A.ArchiveReasonID = ?"
        params.append(reason_filter)
    if why_filter:
        where_clause += " AND A.ArchiveWhyID = ?"
        params.append(why_filter)
    if dept_filter:
        where_clause += " AND D.DEPTID = ?"
        params.append(dept_filter)
    if pos_filter:
        where_clause += " AND P.PositionID = ?"
        params.append(pos_filter)
    if search_term:
        where_clause += " AND (A.Name LIKE ? OR A.ArchivedSSN LIKE ?)"
        params.append(f"%{search_term}%")
        params.append(f"%{search_term}%")
    if date_from:
        where_clause += " AND A.EndDay >= ?"
        params.append(date_from)
    if date_to:
        where_clause += " AND A.EndDay < DATEADD(day, 1, ?)" 
        params.append(date_to)
    
    cursor.execute(f"SELECT A.ArchiveID, A.UserID, A.Name, A.HiredDay, A.EndDay, R.ReasonText, W.WhyText, A.ArchivedSSN, A.ArchiveComment, U.Name as AdminName, D.DEPTNAME, P.PositionName FROM [Zktime].[dbo].[EmployeeArchive] A LEFT JOIN [Zktime].[dbo].[Users] U ON A.AdminUserID = U.UserID LEFT JOIN [Zktime].[dbo].[ArchiveReasons] R ON A.ArchiveReasonID = R.ReasonID LEFT JOIN [Zktime].[dbo].[ArchiveWhys] W ON A.ArchiveWhyID = W.WhyID LEFT JOIN [Zktime].[dbo].[USERINFO] UI ON A.UserID = UI.USERID LEFT JOIN [Zktime].[dbo].[DEPARTMENTS] D ON COALESCE(A.ArchivedDeptID, UI.DEFAULTDEPTID) = D.DEPTID LEFT JOIN [Zktime].[dbo].[POSITIONS] P ON COALESCE(A.ArchivedPosID, UI.PositionID) = P.PositionID WHERE {where_clause} ORDER BY A.EndDay DESC", params)
    archived_employees = cursor.fetchall()
    cursor.execute("SELECT ReasonID, ReasonText FROM ArchiveReasons ORDER BY ReasonText")
    all_reasons = cursor.fetchall()
    cursor.execute("SELECT WhyID, WhyText FROM ArchiveWhys ORDER BY WhyText")
    all_whys = cursor.fetchall()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTNAME")
    all_depts = cursor.fetchall()
    cursor.execute("SELECT PositionID, PositionName FROM [Zktime].[dbo].[POSITIONS] ORDER BY PositionName")
    all_positions = cursor.fetchall()
    
    cursor.execute(f"SELECT COALESCE(R.ReasonText, 'غير محدد') as Label, COUNT(A.ArchiveID) as Count FROM [Zktime].[dbo].[EmployeeArchive] A LEFT JOIN [Zktime].[dbo].[ArchiveReasons] R ON A.ArchiveReasonID = R.ReasonID LEFT JOIN [Zktime].[dbo].[USERINFO] UI ON A.UserID = UI.USERID LEFT JOIN [Zktime].[dbo].[DEPARTMENTS] D ON COALESCE(A.ArchivedDeptID, UI.DEFAULTDEPTID) = D.DEPTID LEFT JOIN [Zktime].[dbo].[POSITIONS] P ON COALESCE(A.ArchivedPosID, UI.PositionID) = P.PositionID WHERE {where_clause} GROUP BY COALESCE(R.ReasonText, 'غير محدد')", params)
    reason_stats = cursor.fetchall()
    cursor.execute(f"SELECT COALESCE(D.DEPTNAME, 'غير محدد') as Label, COUNT(A.ArchiveID) as Count FROM [Zktime].[dbo].[EmployeeArchive] A LEFT JOIN [Zktime].[dbo].[USERINFO] UI ON A.UserID = UI.USERID LEFT JOIN [Zktime].[dbo].[DEPARTMENTS] D ON COALESCE(A.ArchivedDeptID, UI.DEFAULTDEPTID) = D.DEPTID LEFT JOIN [Zktime].[dbo].[POSITIONS] P ON COALESCE(A.ArchivedPosID, UI.PositionID) = P.PositionID WHERE {where_clause} GROUP BY COALESCE(D.DEPTNAME, 'غير محدد')", params)
    dept_stats = cursor.fetchall()
    cursor.execute(f"SELECT COALESCE(P.PositionName, 'غير محدد') as Label, COUNT(A.ArchiveID) as Count FROM [Zktime].[dbo].[EmployeeArchive] A LEFT JOIN [Zktime].[dbo].[USERINFO] UI ON A.UserID = UI.USERID LEFT JOIN [Zktime].[dbo].[DEPARTMENTS] D ON COALESCE(A.ArchivedDeptID, UI.DEFAULTDEPTID) = D.DEPTID LEFT JOIN [Zktime].[dbo].[POSITIONS] P ON COALESCE(A.ArchivedPosID, UI.PositionID) = P.PositionID WHERE {where_clause} GROUP BY COALESCE(P.PositionName, 'غير محدد')", params)
    pos_stats = cursor.fetchall()
    conn.close()

    chart_data = {'reason_labels': [row.Label for row in reason_stats], 'reason_data': [row.Count for row in reason_stats], 'dept_labels': [row.Label for row in dept_stats], 'dept_data': [row.Count for row in dept_stats], 'pos_labels': [row.Label for row in pos_stats], 'pos_data': [row.Count for row in pos_stats]}
    return render_template('archive_report.html', archived_employees=archived_employees, total_archived=len(archived_employees), all_reasons=all_reasons, all_whys=all_whys, all_depts=all_depts, all_positions=all_positions, selected_reason=reason_filter, selected_why=why_filter, selected_dept=dept_filter, selected_pos=pos_filter, search_term=search_term, date_from=date_from, date_to=date_to, chart_data=json.dumps(chart_data, ensure_ascii=False))

@app.route('/archive/manual/add', methods=['GET', 'POST'])
@admin_required
def archive_manual_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        try:
            name = request.form['name']
            ssn = request.form['ssn']
            hired_day = request.form['hired_day'] or None
            end_day = request.form['end_day']
            reason_id = request.form['reason_id']
            why_id = request.form['why_id']
            dept_id = request.form.get('dept_id') or None
            pos_id = request.form.get('pos_id') or None
            comment = request.form['comment']
            admin_user_id = session.get('user_id')
            cursor.execute("INSERT INTO EmployeeArchive (Name, ArchivedSSN, HiredDay, EndDay, ArchiveReasonID, ArchiveWhyID, ArchivedDeptID, ArchivedPosID, ArchiveComment, AdminUserID) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (name, ssn, hired_day, end_day, reason_id, why_id, dept_id, pos_id, comment, admin_user_id))
            conn.commit()
            flash('✅ تم إضافة سجل الأرشيف يدوياً بنجاح.', 'success')
            return redirect(url_for('userinfo_archive_report'))
        except Exception as e:
            conn.rollback()
            flash(f'❌ حدث خطأ: {e}', 'danger')
    cursor.execute("SELECT * FROM ArchiveReasons ORDER BY ReasonText")
    reasons = cursor.fetchall()
    cursor.execute("SELECT * FROM ArchiveWhys ORDER BY WhyText")
    whys = cursor.fetchall()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTNAME")
    depts = cursor.fetchall()
    cursor.execute("SELECT PositionID, PositionName FROM [Zktime].[dbo].[POSITIONS] ORDER BY PositionName")
    positions = cursor.fetchall()
    conn.close()
    return render_template('archive_manual_form.html', reasons=reasons, whys=whys, depts=depts, positions=positions)

@app.route('/userinfo/restore/<int:archive_id>')
@admin_required
def userinfo_restore(archive_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT UserID, Name, HiredDay FROM EmployeeArchive WHERE ArchiveID = ?", (archive_id,))
        archive_record = cursor.fetchone()
        if archive_record:
            user_id = archive_record.UserID
            name = archive_record.Name
            hired_day = archive_record.HiredDay
            cursor.execute("SELECT CAST(COALESCE(MAX(CAST(BADGENUMBER AS BIGINT)), 0) + 1 AS NVARCHAR(20)) FROM [Zktime].[dbo].[USERINFO] WHERE ISNUMERIC(BADGENUMBER) = 1")
            new_badge = cursor.fetchone()[0]
            if not new_badge: new_badge = "1"
            cursor.execute("UPDATE [Zktime].[dbo].[USERINFO] SET IsActive = 1, BADGENUMBER = ? WHERE USERID = ?", (new_badge, user_id))
            if cursor.rowcount == 0:
                try:
                    cursor.execute("SET IDENTITY_INSERT [Zktime].[dbo].[USERINFO] ON")
                    cursor.execute("INSERT INTO [Zktime].[dbo].[USERINFO] (USERID, BADGENUMBER, NAME, HIREDDAY, IsActive) VALUES (?, ?, ?, ?, 1)", (user_id, new_badge, name, hired_day))
                    cursor.execute("SET IDENTITY_INSERT [Zktime].[dbo].[USERINFO] OFF")
                except Exception as insert_err:
                    raise Exception(f"فشل في إعادة إنشاء السجل: {insert_err}")
            cursor.execute("DELETE FROM EmployeeArchive WHERE ArchiveID = ?", (archive_id,))
            conn.commit()
            flash(f'تم استعادة الموظف "{name}" بنجاح، وتم إزالته من الأرشيف. الرقم الوظيفي الجديد: {new_badge}', 'success')
        else:
            flash('لم يتم العثور على سجل الأرشيف.', 'danger')
    except Exception as e:
        conn.rollback()
        print(f"Restore Error: {e}")
        flash(f'خطأ في الاستعادة: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('userinfo_archive_report'))

@app.route('/archive-reasons')
@admin_required
def archive_reasons_list():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ArchiveReasons ORDER BY ReasonID")
    reasons = cursor.fetchall()
    return render_template('archive_reasons_list.html', reasons=reasons)

@app.route('/archive-reasons/add', methods=['GET', 'POST'])
@admin_required
def archive_reasons_add():
    if request.method == 'POST':
        text = request.form['reason_text']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO ArchiveReasons (ReasonText) VALUES (?)", (text,))
        conn.commit()
        flash('تم إضافة السبب بنجاح', 'success')
        return redirect(url_for('archive_reasons_list'))
    return render_template('archive_reason_form.html', action='Add', reason=None)

@app.route('/archive-reasons/edit/<int:rid>', methods=['GET', 'POST'])
@admin_required
def archive_reasons_edit(rid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ArchiveReasons WHERE ReasonID = ?", (rid,))
    reason = cursor.fetchone()
    if request.method == 'POST':
        text = request.form['reason_text']
        cursor.execute("UPDATE ArchiveReasons SET ReasonText = ? WHERE ReasonID = ?", (text, rid))
        conn.commit()
        flash('تم تعديل السبب بنجاح', 'success')
        return redirect(url_for('archive_reasons_list'))
    return render_template('archive_reason_form.html', action='Edit', reason=reason)

@app.route('/archive-reasons/delete/<int:rid>', methods=['POST'])
@admin_required
def archive_reasons_delete(rid):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) as cnt FROM EmployeeArchive WHERE ArchiveReasonID = ?", (rid,))
        if cursor.fetchone().cnt > 0:
            flash('لا يمكن حذف هذا السبب، إنه مستخدم في أرشيف الموظفين.', 'danger')
        else:
            cursor.execute("DELETE FROM ArchiveReasons WHERE ReasonID = ?", (rid,))
            conn.commit()
            flash('تم حذف السبب بنجاح', 'info')
    except Exception as e:
        conn.rollback()
        flash(f'حدث خطأ: {e}', 'danger')
    return redirect(url_for('archive_reasons_list'))

@app.route('/roles')
@login_required
def roles():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT RoleID, RoleName FROM [Zktime].[dbo].[Roles] ORDER BY RoleID")
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
        cursor.execute("INSERT INTO [Zktime].[dbo].[Roles] (RoleName) VALUES (?)", (name,))
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
    cursor.execute("SELECT RoleID, RoleName FROM [Zktime].[dbo].[Roles] WHERE RoleID = ?", (rid,))
    role = cursor.fetchone()
    if request.method == 'POST':
        name = request.form['rolename']
        cursor.execute("UPDATE [Zktime].[dbo].[Roles] SET RoleName = ? WHERE RoleID = ?", (name, rid))
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
    cursor.execute("DELETE FROM [Zktime].[dbo].[Roles] WHERE RoleID = ?", (rid,))
    conn.commit()
    conn.close()
    flash('Role deleted successfully!', 'info')
    return redirect(url_for('roles'))

@app.route('/departments/manage')
@login_required
def departments_manage():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME, SUPDEPTID FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
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
        cursor.execute("INSERT INTO [Zktime].[dbo].[DEPARTMENTS] (DEPTNAME, SUPDEPTID) VALUES (?, ?)", (name, sup))
        conn.commit()
        conn.close()
        flash('Department added successfully!', 'success')
        return redirect(url_for('departments_manage'))
    return render_template('department_form.html', action='Add')

@app.route('/departments/edit/<int:did>', methods=['GET', 'POST'])
@admin_required
def departments_edit(did):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME, SUPDEPTID FROM [Zktime].[dbo].[DEPARTMENTS] WHERE DEPTID = ?", (did,))
    dept = cursor.fetchone()
    if request.method == 'POST':
        name = request.form['deptname']
        sup = request.form.get('supdeptid') or None
        cursor.execute("UPDATE [Zktime].[dbo].[DEPARTMENTS] SET DEPTNAME = ?, SUPDEPTID = ? WHERE DEPTID = ?", (name, sup, did))
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
    cursor.execute("DELETE FROM [Zktime].[dbo].[DEPARTMENTS] WHERE DEPTID = ?", (did,))
    conn.commit()
    conn.close()
    flash('Department deleted successfully!', 'info')
    return redirect(url_for('departments_manage'))

@app.route('/positions')
@login_required
def positions():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT P.PositionID, P.PositionName, P.DeptID, D.DEPTNAME FROM [Zktime].[dbo].[POSITIONS] P LEFT JOIN [Zktime].[dbo].[DEPARTMENTS] D ON P.DeptID = D.DEPTID ORDER BY P.PositionID")
    rows = cursor.fetchall()
    conn.close()
    return render_template('positions.html', positions=rows)

@app.route('/positions/add', methods=['GET', 'POST'])
@admin_required
def positions_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    depts = cursor.fetchall()
    if request.method == 'POST':
        pname = request.form['positionname']
        deptid = request.form.get('deptid') or None
        cursor.execute("INSERT INTO [Zktime].[dbo].[POSITIONS] (PositionName, DeptID) VALUES (?, ?)", (pname, deptid))
        conn.commit()
        conn.close()
        flash('Position added successfully!', 'success')
        return redirect(url_for('positions'))
    conn.close()
    return render_template('position_form.html', depts=depts, action='Add')

@app.route('/positions/edit/<int:pid>', methods=['GET', 'POST'])
@admin_required
def positions_edit(pid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    depts = cursor.fetchall()
    cursor.execute("SELECT PositionID, PositionName, DeptID FROM [Zktime].[dbo].[POSITIONS] WHERE PositionID = ?", (pid,))
    pos = cursor.fetchone()
    if request.method == 'POST':
        pname = request.form['positionname']
        deptid = request.form.get('deptid') or None
        cursor.execute("UPDATE [Zktime].[dbo].[POSITIONS] SET PositionName = ?, DeptID = ? WHERE PositionID = ?", (pname, deptid, pid))
        conn.commit()
        conn.close()
        flash('Position updated successfully!', 'success')
        return redirect(url_for('positions'))
    conn.close()
    return render_template('position_form.html', pos=pos, depts=depts, action='Edit')

@app.route('/positions/delete/<int:pid>', methods=['POST'])
@admin_required
def positions_delete(pid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM [Zktime].[dbo].[POSITIONS] WHERE PositionID = ?", (pid,))
    conn.commit()
    conn.close()
    flash('Position deleted successfully!', 'info')
    return redirect(url_for('positions'))

@app.route('/recommendations')
@admin_required
def recommendations_list():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT R.RecommendationID, R.RecommendationText, R.AppliesToDeptID, D.DEPTNAME FROM [Zktime].[dbo].[Recommendations] R LEFT JOIN [Zktime].[dbo].[DEPARTMENTS] D ON R.AppliesToDeptID = D.DEPTID ORDER BY R.RecommendationID")
    recommendations = cursor.fetchall()
    conn.close()
    return render_template('recommendations_list.html', recommendations=recommendations)

@app.route('/recommendations/add', methods=['GET', 'POST'])
@admin_required
def recommendations_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    departments = cursor.fetchall()
    if request.method == 'POST':
        text = request.form['text']
        dept_id = request.form.get('dept_id')
        dept_id = int(dept_id) if dept_id else None
        try:
            cursor.execute("INSERT INTO [Zktime].[dbo].[Recommendations] (RecommendationText, AppliesToDeptID) VALUES (?, ?)", (text, dept_id))
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
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    departments = cursor.fetchall()
    cursor.execute("SELECT * FROM [Zktime].[dbo].[Recommendations] WHERE RecommendationID = ?", (rid,))
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
            cursor.execute("UPDATE [Zktime].[dbo].[Recommendations] SET RecommendationText = ?, AppliesToDeptID = ? WHERE RecommendationID = ?", (text, dept_id, rid))
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
        cursor.execute("SELECT COUNT(*) as cnt FROM [Zktime].[dbo].[Evaluations] WHERE RecommendationID = ?", (rid,))
        if cursor.fetchone().cnt > 0:
            flash('لا يمكن حذف توصية مستخدمة في تقييمات سابقة.', 'danger')
        else:
            cursor.execute("DELETE FROM [Zktime].[dbo].[Recommendations] WHERE RecommendationID = ?", (rid,))
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
    cursor.execute("SELECT C.CriteriaID, C.CriteriaName, C.CriteriaWeight, C.MaxScore, C.AppliesToDeptID, C.employee_class, D.DEPTNAME FROM [Zktime].[dbo].[EvaluationCriteria] C LEFT JOIN [Zktime].[dbo].[DEPARTMENTS] D ON C.AppliesToDeptID = D.DEPTID ORDER BY C.CriteriaID")
    criteria = cursor.fetchall()
    conn.close()
    return render_template('criteria_list.html', criteria=criteria)

@app.route('/evaluation/criteria/add', methods=['GET', 'POST'])
@admin_required
def criteria_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
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
            cursor.execute("INSERT INTO [Zktime].[dbo].[EvaluationCriteria] (CriteriaName, CriteriaWeight, MaxScore, AppliesToDeptID, employee_class) VALUES (?, ?, ?, ?, ?)", (name, weight_float, max_score_int, dept_id, employee_class))
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
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    departments = cursor.fetchall()
    cursor.execute("SELECT * FROM [Zktime].[dbo].[EvaluationCriteria] WHERE CriteriaID = ?", (cid,))
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
            cursor.execute("UPDATE [Zktime].[dbo].[EvaluationCriteria] SET CriteriaName = ?, CriteriaWeight = ?, MaxScore = ?, AppliesToDeptID = ?, employee_class = ? WHERE CriteriaID = ?", (name, weight_float, max_score_int, dept_id, employee_class, cid))
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
        cursor.execute("SELECT COUNT(*) as cnt FROM [Zktime].[dbo].[EvaluationDetails] WHERE CriteriaID = ?", (cid,))
        usage_count = cursor.fetchone().cnt
        if usage_count > 0:
            flash('Cannot delete criterion, it is used in existing evaluations.', 'danger')
        else:
            cursor.execute("DELETE FROM [Zktime].[dbo].[EvaluationCriteria] WHERE CriteriaID = ?", (cid,))
            conn.commit()
            flash('Criterion deleted successfully!', 'info')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting criterion: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('criteria_list'))

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
        cursor.execute("SELECT DepartmentID FROM [Zktime].[dbo].[Users] WHERE UserID = ?", (evaluator_user_id,))
        user_record = cursor.fetchone()
        manager_dept_id = user_record.DepartmentID if user_record else None
        if manager_dept_id:
            query = "SELECT UI.USERID, UI.NAME, UI.TITLE, UI.PositionID, P.PositionName, D.DEPTNAME FROM [Zktime].[dbo].[USERINFO] UI LEFT JOIN [dbo].[POSITIONS] P ON UI.PositionID = P.PositionID LEFT JOIN [dbo].[DEPARTMENTS] D ON UI.DEFAULTDEPTID = D.DEPTID WHERE UI.DEFAULTDEPTID = ? AND UI.USERID != ?"
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
        query = "SELECT U.UserID, U.Name, U.Username, U.DepartmentID, D.DEPTNAME FROM [Zktime].[dbo].[Users] U LEFT JOIN [dbo].[DEPARTMENTS] D ON U.DepartmentID = D.DEPTID WHERE U.RoleID = 3 AND U.UserID != ?"
        params = [evaluator_user_id]
        if search_query:
            query += " AND (U.Name LIKE ? OR U.Username LIKE ? OR D.DEPTNAME LIKE ?)"
            params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])
        cursor.execute(query, params)
        managers = cursor.fetchall()
        for mgr in managers:
            users_to_evaluate.append({'USERID': mgr.UserID, 'NAME': mgr.Name or mgr.Username, 'TITLE': 'Manager', 'PositionName': None, 'DEPTNAME': mgr.DEPTNAME or 'غير محدد', 'IsManager': True})
    conn.close()
    return render_template('select_user_for_evaluation.html', users=users_to_evaluate, role_id=role_id, page_title=page_title, filters=request.args) 

@app.route('/evaluation/new/<int:employee_id>', methods=['GET', 'POST'])
@login_required
def new_evaluation(employee_id):
    role_id = session.get('role_id')
    evaluator_user_id = session.get('user_id')
    if role_id not in [2, 3]:
        flash('ليس لديك الصلاحية لإنشاء تقييم.', 'danger')
        return redirect(url_for('dashboard'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DepartmentID FROM [Zktime].[dbo].[Users] WHERE UserID = ?", (evaluator_user_id,))
    manager_record = cursor.fetchone()
    manager_dept_id = manager_record.DepartmentID if manager_record else None
    target_user_dept_id = None
    employee_info = None
    is_manager = request.args.get('is_manager', 'false').lower() == 'true'
    if is_manager and role_id == 2:
        cursor.execute("SELECT U.UserID, U.Name, U.Username, U.DepartmentID, D.DEPTNAME FROM [Zktime].[dbo].[Users] U LEFT JOIN [dbo].[DEPARTMENTS] D ON U.DepartmentID = D.DEPTID WHERE U.UserID = ? AND U.RoleID = 3", (employee_id,))
        user_record = cursor.fetchone()
        if user_record:
            target_user_dept_id = user_record.DepartmentID
            class Row: pass
            employee_info = Row()
            employee_info.USERID = user_record.UserID
            employee_info.NAME = user_record.Name or user_record.Username
            employee_info.DEPTNAME = user_record.DEPTNAME or 'غير محدد'
            employee_info.TITLE = 'Manager'
            employee_info.DEFAULTDEPTID = user_record.DepartmentID
    elif not is_manager and role_id == 3:
        cursor.execute("SELECT UI.USERID, UI.NAME, UI.DEFAULTDEPTID, UI.TITLE, D.DEPTNAME FROM [Zktime].[dbo].[USERINFO] UI LEFT JOIN [dbo].[DEPARTMENTS] D ON UI.DEFAULTDEPTID = D.DEPTID WHERE UI.USERID = ?", (employee_id,))
        employee_info = cursor.fetchone()
    if not employee_info:
        flash('لم يتم العثور على المستخدم المطلوب.', 'danger')
        return redirect(url_for('select_user_for_evaluation'))
    employee_dept_id = employee_info.DEFAULTDEPTID if hasattr(employee_info, 'DEFAULTDEPTID') else target_user_dept_id
    if role_id == 3 and manager_dept_id != employee_dept_id:
         flash('لا يمكنك تقييم موظف ليس في قسمك.', 'danger')
         return redirect(url_for('select_user_for_evaluation'))
    employee_class_string = get_employee_class(employee_id)
    class_likes = []
    class_params = []
    if employee_class_string and employee_class_string != 'لم تضاف':
        for cls in employee_class_string.split(','):
            cls_clean = cls.strip()
            if cls_clean:
                class_likes.append("employee_class LIKE ?")
                class_params.append(f"%{cls_clean}%")
    class_clause = "(" + " OR ".join(class_likes) + ")" if class_likes else "employee_class = 'لم تضاف'"
    criteria_query = f"SELECT CriteriaID, CriteriaName, CriteriaWeight, MaxScore FROM [Zktime].[dbo].[EvaluationCriteria] WHERE {class_clause} AND (AppliesToDeptID = ? OR AppliesToDeptID IS NULL) ORDER BY CriteriaID"
    criteria_params = class_params + [employee_dept_id]
    cursor.execute(criteria_query, criteria_params)
    criteria = cursor.fetchall()
    if not criteria:
        flash(f'⚠️ لم يتم تعريف معايير تقييم للفئة "{employee_class_string}" في هذا القسم.', 'warning')
        return redirect(url_for('select_user_for_evaluation'))
    cursor.execute("SELECT RecommendationID, RecommendationText FROM [Zktime].[dbo].[Recommendations] WHERE AppliesToDeptID = ? OR AppliesToDeptID IS NULL ORDER BY RecommendationText", (employee_dept_id,))
    recommendations = cursor.fetchall()
    cursor.execute("SELECT TrainingCourseID, TrainingCourseText FROM [Zktime].[dbo].[TrainingCourses] WHERE AppliesToDeptID = ? OR AppliesToDeptID IS NULL ORDER BY TrainingCourseText", (employee_dept_id,))
    training_courses = cursor.fetchall()
    available_evals = get_available_evaluation_types(conn, employee_id, manager_dept_id)
    if request.method == 'POST':
        try:
            eval_type_id = request.form['evaluation_type_id']
            if not eval_type_id or not any(e['id'] == int(eval_type_id) and not e['disabled'] for e in available_evals):
                 flash('❌ نوع التقييم المختار غير متاح أو غير صحيح.', 'danger')
                 raise ValueError("Invalid or disabled evaluation type submitted.")
            comments = request.form.get('comments', '').strip()
            recommendation_id = request.form.get('recommendation_id') or None
            training_course_id = request.form.get('training_course_id') or None
            cursor.execute("INSERT INTO [Zktime].[dbo].[Evaluations] (EmployeeUserID, EvaluatorUserID, EvaluationTypeID, ManagerComments, RecommendationID, TrainingCourseID) OUTPUT INSERTED.EvaluationID VALUES (?, ?, ?, ?, ?, ?)", (employee_id, evaluator_user_id, eval_type_id, comments, recommendation_id, training_course_id))
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
                cursor.executemany("INSERT INTO [Zktime].[dbo].[EvaluationDetails] (EvaluationID, CriteriaID, ScoreGiven) VALUES (?, ?, ?)", scores_data)
            final_percentage = (total_weighted_score / total_max_weighted_score) * 100 if total_max_weighted_score > 0 else 0
            final_rating = get_rating_from_score(final_percentage)
            cursor.execute("UPDATE [Zktime].[dbo].[Evaluations] SET OverallScore = ?, OverallRating = ? WHERE EvaluationID = ?", (final_percentage, final_rating, evaluation_id))
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
            pass 
    return render_template('new_evaluation_form.html', employee=employee_info, criteria=criteria, recommendations=recommendations, training_courses=training_courses, employee_class=employee_class_string, available_evals=available_evals)

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
        cursor.execute("SELECT RecommendationID, RecommendationText FROM [Zktime].[dbo].[Recommendations] ORDER BY RecommendationText")
        all_recommendations = cursor.fetchall()
        cursor.execute("SELECT TrainingCourseID, TrainingCourseText FROM [Zktime].[dbo].[TrainingCourses] ORDER BY TrainingCourseText")
        all_training_courses = cursor.fetchall()
        cursor.execute("SELECT EvaluationTypeID, DisplayName FROM [Zktime].[dbo].[EvaluationTypes] ORDER BY SortOrder")
        all_evaluation_types = cursor.fetchall()
        query = """
            SELECT E.EvaluationID, E.EvaluationDate, COALESCE(ET.DisplayName, E.EvaluationType) as EvaluationType,
                E.OverallScore, E.OverallRating, E.ManagerComments,
                COALESCE(EmpInfo.NAME, EmpUser.Name, EmpUser.Username) AS EmployeeName, 
                COALESCE(Mgr.Name, Mgr.Username) AS EvaluatorName, EmpInfo.employee_class,
                R.RecommendationText, TC.TrainingCourseText
            FROM [Zktime].[dbo].[Evaluations] E
            LEFT JOIN [Zktime].[dbo].[Users] Mgr ON E.EvaluatorUserID = Mgr.UserID 
            LEFT JOIN [Zktime].[dbo].[USERINFO] EmpInfo ON E.EmployeeUserID = EmpInfo.USERID
            LEFT JOIN [Zktime].[dbo].[Users] EmpUser ON E.EmployeeUserID = EmpUser.UserID
            LEFT JOIN [Zktime].[dbo].[Recommendations] R ON E.RecommendationID = R.RecommendationID
            LEFT JOIN [Zktime].[dbo].[TrainingCourses] TC ON E.TrainingCourseID = TC.TrainingCourseID
            LEFT JOIN [Zktime].[dbo].[EvaluationTypes] ET ON E.EvaluationTypeID = ET.EvaluationTypeID
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
    cursor.execute("SELECT ET.EvaluationTypeID, ET.TypeName, ET.DisplayName, ET.IsRepeatable, ET.SortOrder, Pre.DisplayName as PrerequisiteName FROM [Zktime].[dbo].[EvaluationTypes] ET LEFT JOIN [Zktime].[dbo].[EvaluationTypes] Pre ON ET.PrerequisiteTypeID = Pre.EvaluationTypeID ORDER BY ET.SortOrder")
    types = cursor.fetchall()
    conn.close()
    return render_template('evaluation_types_list.html', types=types)

@app.route('/evaluation-types/add', methods=['GET', 'POST'])
@admin_required
def evaluation_types_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT EvaluationTypeID, DisplayName FROM [Zktime].[dbo].[EvaluationTypes] ORDER BY SortOrder")
    all_types = cursor.fetchall()
    if request.method == 'POST':
        try:
            type_name = request.form['type_name']
            display_name = request.form['display_name']
            is_repeatable = 'is_repeatable' in request.form
            prerequisite_id = request.form.get('prerequisite_id') or None
            sort_order = request.form.get('sort_order', 100)
            cursor.execute("INSERT INTO [Zktime].[dbo].[EvaluationTypes] (TypeName, DisplayName, IsRepeatable, PrerequisiteTypeID, SortOrder) VALUES (?, ?, ?, ?, ?)", (type_name, display_name, is_repeatable, prerequisite_id, sort_order))
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
    cursor.execute("SELECT EvaluationTypeID, DisplayName FROM [Zktime].[dbo].[EvaluationTypes] WHERE EvaluationTypeID != ? ORDER BY SortOrder", (type_id,))
    all_types = cursor.fetchall()
    cursor.execute("SELECT * FROM [Zktime].[dbo].[EvaluationTypes] WHERE EvaluationTypeID = ?", (type_id,))
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
            cursor.execute("UPDATE [Zktime].[dbo].[EvaluationTypes] SET TypeName = ?, DisplayName = ?, IsRepeatable = ?, PrerequisiteTypeID = ?, SortOrder = ? WHERE EvaluationTypeID = ?", (type_name, display_name, is_repeatable, prerequisite_id, sort_order, type_id))
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
        cursor.execute("SELECT COUNT(*) as cnt FROM [Zktime].[dbo].[Evaluations] WHERE EvaluationTypeID = ?", (type_id,))
        if cursor.fetchone().cnt > 0:
            flash('❌ لا يمكن الحذف، هذا النوع مستخدم في تقييمات سابقة.', 'danger')
            conn.close()
            return redirect(url_for('evaluation_types_list'))
        cursor.execute("SELECT COUNT(*) as cnt FROM [Zktime].[dbo].[EvaluationTypes] WHERE PrerequisiteTypeID = ?", (type_id,))
        if cursor.fetchone().cnt > 0:
            flash('❌ لا يمكن الحذف، هذا النوع هو متطلب لنوع آخر.', 'danger')
            conn.close()
            return redirect(url_for('evaluation_types_list'))
        cursor.execute("DELETE FROM [Zktime].[dbo].[EvaluationTypes] WHERE EvaluationTypeID = ?", (type_id,))
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
    cursor.execute("SELECT C.CycleID, C.CycleName, C.StartDate, C.EndDate, C.IsEnabled, ET.DisplayName as EvaluationTypeName FROM [Zktime].[dbo].[EvaluationCycles] C JOIN [Zktime].[dbo].[EvaluationTypes] ET ON C.EvaluationTypeID = ET.EvaluationTypeID ORDER BY C.StartDate DESC")
    cycles = cursor.fetchall()
    conn.close()
    return render_template('evaluation_cycles_list.html', cycles=cycles)

@app.route('/evaluation-cycles/add', methods=['GET', 'POST'])
@admin_required
def evaluation_cycles_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT EvaluationTypeID, DisplayName FROM [Zktime].[dbo].[EvaluationTypes] ORDER BY SortOrder")
    all_types = cursor.fetchall()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTNAME")
    all_depts = cursor.fetchall()
    if request.method == 'POST':
        try:
            cycle_name = request.form['cycle_name']
            type_id = request.form['type_id']
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            is_enabled = 'is_enabled' in request.form
            dept_ids = request.form.getlist('dept_ids')
            cursor.execute("INSERT INTO [Zktime].[dbo].[EvaluationCycles] (CycleName, EvaluationTypeID, StartDate, EndDate, IsEnabled) OUTPUT INSERTED.CycleID VALUES (?, ?, ?, ?, ?)", (cycle_name, type_id, start_date, end_date, is_enabled))
            new_cycle_id = cursor.fetchone().CycleID
            if dept_ids:
                dept_data = [(new_cycle_id, int(dept_id)) for dept_id in dept_ids]
                cursor.executemany("INSERT INTO [Zktime].[dbo].[CycleDepartments] (CycleID, DepartmentID) VALUES (?, ?)", dept_data)
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
    cursor.execute("SELECT EvaluationTypeID, DisplayName FROM [Zktime].[dbo].[EvaluationTypes] ORDER BY SortOrder")
    all_types = cursor.fetchall()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTNAME")
    all_depts = cursor.fetchall()
    if request.method == 'POST':
        try:
            cycle_name = request.form['cycle_name']
            type_id = request.form['type_id']
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            is_enabled = 'is_enabled' in request.form
            dept_ids = request.form.getlist('dept_ids')
            cursor.execute("UPDATE [Zktime].[dbo].[EvaluationCycles] SET CycleName = ?, EvaluationTypeID = ?, StartDate = ?, EndDate = ?, IsEnabled = ? WHERE CycleID = ?", (cycle_name, type_id, start_date, end_date, is_enabled, cycle_id))
            cursor.execute("DELETE FROM [Zktime].[dbo].[CycleDepartments] WHERE CycleID = ?", (cycle_id,))
            if dept_ids:
                dept_data = [(cycle_id, int(dept_id)) for dept_id in dept_ids]
                cursor.executemany("INSERT INTO [Zktime].[dbo].[CycleDepartments] (CycleID, DepartmentID) VALUES (?, ?)", dept_data)
            conn.commit()
            flash('✅ تم تحديث دورة التقييم بنجاح', 'success')
            return redirect(url_for('evaluation_cycles_list'))
        except Exception as e:
            conn.rollback()
            flash(f'❌ خطأ في قاعدة البيانات: {e}', 'danger')
        finally:
            conn.close()
    cursor.execute("SELECT * FROM [Zktime].[dbo].[EvaluationCycles] WHERE CycleID = ?", (cycle_id,))
    cycle = cursor.fetchone()
    if not cycle:
        flash('❌ لم يتم العثور على الدورة', 'danger')
        conn.close()
        return redirect(url_for('evaluation_cycles_list'))
    cursor.execute("SELECT DepartmentID FROM [Zktime].[dbo].[CycleDepartments] WHERE CycleID = ?", (cycle_id,))
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
        cursor.execute("DELETE FROM [Zktime].[dbo].[CycleDepartments] WHERE CycleID = ?", (cycle_id,))
        cursor.execute("DELETE FROM [Zktime].[dbo].[EvaluationCycles] WHERE CycleID = ?", (cycle_id,))
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
        cursor.execute("SELECT E.EvaluationID, E.EvaluationDate, COALESCE(ET.DisplayName, E.EvaluationType) as EvaluationType, E.OverallScore, E.OverallRating, E.ManagerComments, E.EmployeeUserID, E.EvaluatorUserID, COALESCE(EmpInfo.NAME, EmpUser.Name, EmpUser.Username) AS EmployeeName, COALESCE(Mgr.Name, Mgr.Username) AS EvaluatorName, COALESCE(EmpInfo.TITLE, EmpUser.Name, EmpUser.Username) AS EmployeeTitle, DeptEmp.DEPTNAME as EmployeeDeptName, EmpInfo.employee_class, R.RecommendationText, TC.TrainingCourseText FROM [Zktime].[dbo].[Evaluations] E LEFT JOIN [Zktime].[dbo].[Users] Mgr ON E.EvaluatorUserID = Mgr.UserID LEFT JOIN [Zktime].[dbo].[USERINFO] EmpInfo ON E.EmployeeUserID = EmpInfo.USERID LEFT JOIN [Zktime].[dbo].[Users] EmpUser ON E.EmployeeUserID = EmpUser.UserID LEFT JOIN [Zktime].[dbo].[DEPARTMENTS] DeptEmp ON COALESCE(EmpInfo.DEFAULTDEPTID, EmpUser.DepartmentID) = DeptEmp.DEPTID LEFT JOIN [Zktime].[dbo].[Recommendations] R ON E.RecommendationID = R.RecommendationID LEFT JOIN [Zktime].[dbo].[TrainingCourses] TC ON E.TrainingCourseID = TC.TrainingCourseID LEFT JOIN [Zktime].[dbo].[EvaluationTypes] ET ON E.EvaluationTypeID = ET.EvaluationTypeID WHERE E.EvaluationID = ?", (evaluation_id,))
        evaluation_data = cursor.fetchone()
        if not evaluation_data:
            flash("Evaluation not found.", "warning")
            return redirect(url_for('evaluation_reports'))
        can_view = False
        if role_id in [1, 4]: can_view = True
        elif role_id in [2, 3] and evaluation_data.EvaluatorUserID == user_id: can_view = True
        elif role_id == 5 and evaluation_data.EmployeeUserID == user_id: can_view = True
        elif role_id == 3:
            cursor.execute("SELECT DepartmentID FROM [Zktime].[dbo].[Users] WHERE UserID = ?", (user_id,))
            manager_dept = cursor.fetchone()
            cursor.execute("SELECT DEFAULTDEPTID FROM [Zktime].[dbo].[USERINFO] WHERE USERID = ?", (evaluation_data.EmployeeUserID,))
            emp_dept = cursor.fetchone()
            if manager_dept and emp_dept and manager_dept.DepartmentID == emp_dept.DEFAULTDEPTID:
                can_view = True
        if not can_view:
             flash("You do not have permission to view this evaluation.", "danger")
             return redirect(url_for('evaluation_reports'))
        cursor.execute("SELECT ED.ScoreGiven, EC.CriteriaName, EC.CriteriaWeight, EC.MaxScore FROM [Zktime].[dbo].[EvaluationDetails] ED JOIN [Zktime].[dbo].[EvaluationCriteria] EC ON ED.CriteriaID = EC.CriteriaID WHERE ED.EvaluationID = ? ORDER BY EC.CriteriaID", (evaluation_id,))
        details = cursor.fetchall()
    except Exception as e:
        flash(f"Error fetching evaluation details: {e}", "danger")
        return redirect(url_for('evaluation_reports')) 
    finally:
        if conn: conn.close()
    return render_template('evaluation_details.html', eval=evaluation_data, details=details)

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

@app.route('/recruitment/statuses')
@admin_required
def recruitment_statuses():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM RecruitmentStatuses ORDER BY StatusID")
    statuses = cursor.fetchall()
    conn.close()
    return render_template('recruitment_statuses.html', statuses=statuses)

@app.route('/recruitment/statuses/add', methods=['POST'])
@admin_required
def add_recruitment_status():
    name = request.form['name']
    color = request.form['color']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO RecruitmentStatuses (StatusName, ColorCode) VALUES (?, ?)", (name, color))
    conn.commit()
    conn.close()
    flash('Status added successfully', 'success')
    return redirect(url_for('recruitment_statuses'))

@app.route('/recruitment/statuses/delete/<int:sid>', methods=['POST'])
@admin_required
def delete_recruitment_status(sid):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if this status is used by any candidate
        cursor.execute("SELECT COUNT(*) as cnt FROM Recruitment WHERE Status = (SELECT StatusName FROM RecruitmentStatuses WHERE StatusID = ?)", (sid,))
        if cursor.fetchone().cnt > 0:
             flash('❌ لا يمكن حذف هذه الحالة لأنها مستخدمة في سجلات المرشحين.', 'danger')
        else:
            cursor.execute("DELETE FROM RecruitmentStatuses WHERE StatusID = ?", (sid,))
            conn.commit()
            flash('✅ تم حذف الحالة بنجاح.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error: {e}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('recruitment_statuses'))

@app.route('/recruitment/stage/<path:status_name>')
@login_required
def recruitment_stage(status_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # --- Filtering Parameters ---
    search_query = request.args.get('search', '').strip()
    dept_id = request.args.get('dept_id', '')
    pos_id = request.args.get('pos_id', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    # --- Base Query ---
    query = """
        SELECT R.*, P.PositionName, D.DEPTNAME
        FROM Recruitment R
        LEFT JOIN [Zktime].[dbo].[POSITIONS] P ON R.PositionID = P.PositionID
        LEFT JOIN [Zktime].[dbo].[DEPARTMENTS] D ON R.DepartmentID = D.DEPTID
        WHERE R.Status = ?
    """
    params = [status_name]

    # --- Apply Filters ---
    if search_query:
        query += " AND (R.FullName LIKE ? OR R.Phone LIKE ? OR R.Email LIKE ? OR R.SSN LIKE ?)"
        params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])
    
    if dept_id:
        query += " AND R.DepartmentID = ?"
        params.append(dept_id)

    if pos_id:
        query += " AND R.PositionID = ?"
        params.append(pos_id)

    if date_from:
        query += " AND R.ApplicationDate >= ?"
        params.append(date_from)

    if date_to:
        query += " AND R.ApplicationDate <= ?"
        params.append(date_to)

    query += " ORDER BY R.ApplicationDate DESC"
    
    cursor.execute(query, params)
    candidates = cursor.fetchall()

    # --- Fetch Dropdowns for Filters ---
    cursor.execute("SELECT DEPTID, DEPTNAME FROM DEPARTMENTS ORDER BY DEPTNAME")
    depts = cursor.fetchall()
    cursor.execute("SELECT PositionID, PositionName FROM POSITIONS ORDER BY PositionName")
    positions = cursor.fetchall()
    
    conn.close()
    
    # Page Info Logic
    page_info = {'title': status_name, 'color': '#0d6efd', 'icon': 'fa-list'} # Default
    if 'New' in status_name:
        page_info = {'title': 'مرحلة الفرز (New)', 'color': '#0d6efd', 'icon': 'fa-star'}
    elif 'Interview 1' in status_name:
        page_info = {'title': 'المقابلة الأولى (HR)', 'color': '#ffc107', 'icon': 'fa-comments'}
    elif 'Interview 2' in status_name:
        page_info = {'title': 'المقابلة الثانية (Technical)', 'color': '#fd7e14', 'icon': 'fa-user-check'}
    elif 'Offer' in status_name:
        page_info = {'title': 'عروض العمل (Offer)', 'color': '#198754', 'icon': 'fa-file-contract'}
    elif 'Rejected' in status_name:
        page_info = {'title': 'المرفوضين (Rejected)', 'color': '#dc3545', 'icon': 'fa-ban'}

    return render_template('recruitment_stage.html', 
                           candidates=candidates, 
                           status_filter=status_name,
                           page_info=page_info,
                           depts=depts,       # Pass for filter
                           positions=positions, # Pass for filter
                           filters=request.args) # Pass current filters

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
    cursor.execute("SELECT UserID, Name FROM Users WHERE RoleID IN (1, 3, 6)")
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
        LEFT JOIN Users U ON S.InstructorID = U.UserID
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
            'url': url_for('training_session_view', sid=r.SessionID)
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

@app.route('/training_courses/edit/<int:tcid>', methods=['GET', 'POST'])
@admin_required
def training_courses_edit(tcid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
    departments = cursor.fetchall()
    
    cursor.execute("SELECT * FROM [Zktime].[dbo].[TrainingCourses] WHERE TrainingCourseID = ?", (tcid,))
    course = cursor.fetchone()
    
    if not course:
        flash('لم يتم العثور على الدورة!', 'warning')
        conn.close()
        return redirect(url_for('training_courses_list'))

    if request.method == 'POST':
        text = request.form['text']
        dept_id = request.form.get('dept_id')
        dept_id = int(dept_id) if dept_id else None

        try:
            cursor.execute("""
                UPDATE [Zktime].[dbo].[TrainingCourses]
                SET TrainingCourseText = ?, AppliesToDeptID = ?
                WHERE TrainingCourseID = ?
            """, (text, dept_id, tcid))
            conn.commit()
            flash('✅ تم تحديث الدورة بنجاح!', 'success')
            return redirect(url_for('training_courses_list'))
        except Exception as e:
            conn.rollback()
            flash(f'❌ خطأ في قاعدة البيانات: {e}', 'danger')
        finally:
            conn.close()

    conn.close()
    return render_template('training_course_form.html', 
                         departments=departments,
                         course=course, 
                         action='Edit')

@app.route('/training_courses/delete/<int:tcid>', methods=['POST'])
@admin_required
def training_courses_delete(tcid):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if course is in use
        cursor.execute("SELECT COUNT(*) as cnt FROM [Zktime].[dbo].[Evaluations] WHERE TrainingCourseID = ?", (tcid,))
        if cursor.fetchone().cnt > 0:
            flash('لا يمكن حذف دورة مستخدمة في تقييمات سابقة.', 'danger')
        else:
            cursor.execute("DELETE FROM [Zktime].[dbo].[TrainingCourses] WHERE TrainingCourseID = ?", (tcid,))
            conn.commit()
            flash('تم حذف الدورة بنجاح!', 'info')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting course: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('training_courses_list'))

@app.route('/training/session/<int:sid>', methods=['GET', 'POST'])
@login_required
def training_session_view(sid):
    conn = get_db_connection()
    cursor = conn.cursor()

    # A. Auto Enroll
    if request.method == 'POST' and 'auto_enroll' in request.form:
        cursor.execute("SELECT CourseID, MaxCapacity FROM TrainingSessions WHERE SessionID = ?", (sid,))
        session_info = cursor.fetchone()
        course_id = session_info.CourseID
        max_cap = session_info.MaxCapacity
        
        cursor.execute("SELECT COUNT(*) FROM TrainingEnrollments WHERE SessionID = ?", (sid,))
        current_count = cursor.fetchone()[0]
        
        # Find recommended employees not yet enrolled
        cursor.execute("""
            SELECT DISTINCT E.EmployeeUserID 
            FROM Evaluations E 
            WHERE E.TrainingCourseID = ? 
            AND E.EmployeeUserID NOT IN (
                SELECT TE.EmployeeUserID FROM TrainingEnrollments TE 
                JOIN TrainingSessions TS ON TE.SessionID = TS.SessionID 
                WHERE TS.CourseID = ?
            )
        """, (course_id, course_id))
        candidates = cursor.fetchall()
        
        for cand in candidates:
            status = 'Registered' if current_count < max_cap else 'Waitlist'
            if status == 'Registered': current_count += 1
            cursor.execute("INSERT INTO TrainingEnrollments (SessionID, EmployeeUserID, AttendanceStatus) VALUES (?, ?, ?)", (sid, cand.EmployeeUserID, status))
        
        conn.commit()
        flash('✅ تم سحب المرشحين بنجاح', 'info')

    # B. Manual Enroll
    if request.method == 'POST' and 'manual_enroll' in request.form:
         user_id = request.form.get('user_id')
         cursor.execute("INSERT INTO TrainingEnrollments (SessionID, EmployeeUserID, AttendanceStatus) VALUES (?, ?, 'Registered')", (sid, user_id))
         conn.commit()
         flash('✅ تم إضافة الموظف بنجاح', 'success')

    # C. Mark Attendance (Quick Actions)
    if request.method == 'POST' and 'mark_attendance' in request.form:
        eid = request.form.get('enrollment_id')
        status = request.form.get('status')
        cursor.execute("UPDATE TrainingEnrollments SET AttendanceStatus = ? WHERE EnrollmentID = ?", (status, eid))
        conn.commit()
        flash('✅ تم تحديث الحضور', 'success')

    # D. Session Data
    cursor.execute("""
        SELECT S.*, TC.TrainingCourseText, 
               COALESCE(S.ExternalTrainerName + ' (Ext)', U.Name) as InstructorName 
        FROM TrainingSessions S
        LEFT JOIN TrainingCourses TC ON S.CourseID = TC.TrainingCourseID
        LEFT JOIN Users U ON S.InstructorID = U.UserID
        WHERE S.SessionID = ?
    """, (sid,))
    session_data = cursor.fetchone()

    # E. Enrollments Data (With Grades)
    cursor.execute("""
        SELECT TE.*, UI.NAME, UI.BADGENUMBER, D.DEPTNAME
        FROM TrainingEnrollments TE
        LEFT JOIN USERINFO UI ON TE.EmployeeUserID = UI.USERID
        LEFT JOIN DEPARTMENTS D ON UI.DEFAULTDEPTID = D.DEPTID
        WHERE TE.SessionID = ?
        ORDER BY UI.NAME
    """, (sid,))
    enrollments = cursor.fetchall()
    
    # F. All Employees (For Manual Add Dropdown)
    cursor.execute("SELECT USERID, NAME FROM USERINFO WHERE IsActive = 1 ORDER BY NAME")
    all_employees = cursor.fetchall()

    conn.close()
    
    return render_template('training_details.html', 
                           training_session=session_data, 
                           enrollments=enrollments,
                           all_employees=all_employees)

@app.route('/training/session/<int:sid>/print')
@login_required
def training_session_print(sid):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT S.*, TC.TrainingCourseText, 
               COALESCE(S.ExternalTrainerName + ' (Ext)', U.Name) as InstructorName 
        FROM TrainingSessions S
        LEFT JOIN TrainingCourses TC ON S.CourseID = TC.TrainingCourseID
        LEFT JOIN Users U ON S.InstructorID = U.UserID
        WHERE S.SessionID = ?
    """, (sid,))
    session_data = cursor.fetchone()

    cursor.execute("""
        SELECT TE.*, UI.NAME, UI.BADGENUMBER, D.DEPTNAME, UI.TITLE
        FROM TrainingEnrollments TE
        LEFT JOIN USERINFO UI ON TE.EmployeeUserID = UI.USERID
        LEFT JOIN DEPARTMENTS D ON UI.DEFAULTDEPTID = D.DEPTID
        WHERE TE.SessionID = ? AND TE.AttendanceStatus != 'Cancelled'
        ORDER BY UI.NAME
    """, (sid,))
    enrollments = cursor.fetchall()

    conn.close()
    return render_template('training_print.html', training_session=session_data, enrollments=enrollments)

@app.route('/training_courses/add', methods=['GET', 'POST'])
@admin_required
def training_courses_add():
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM DEPARTMENTS ORDER BY DEPTID"); depts = cursor.fetchall()
    if request.method == 'POST':
        text = request.form['text']; dept_id = request.form.get('dept_id') or None
        cursor.execute("INSERT INTO TrainingCourses (TrainingCourseText, AppliesToDeptID) VALUES (?, ?)", (text, dept_id)); conn.commit(); conn.close()
        return redirect(url_for('training_courses_list'))
    conn.close()
    return render_template('training_course_form.html', departments=depts, action='Add')

@app.route('/training_courses')
@admin_required
def training_courses_list():
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("SELECT TC.TrainingCourseID, TC.TrainingCourseText, D.DEPTNAME FROM TrainingCourses TC LEFT JOIN DEPARTMENTS D ON TC.AppliesToDeptID = D.DEPTID"); rows = cursor.fetchall(); conn.close()
    return render_template('training_courses_list.html', courses=rows)

# ===================== MANUAL TRAINING HISTORY ENTRY =====================

@app.route('/training/manual_history', methods=['GET', 'POST'])
@admin_required
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


# ===================== JOB LISTINGS (ATS) =====================

@app.route('/jobs')
@login_required
def job_list():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get Jobs with Applicant Counts
    cursor.execute("""
        SELECT J.*, D.DEPTNAME,
               (SELECT COUNT(*) FROM Recruitment R WHERE R.JobID = J.JobID) as ApplicantCount
        FROM JobPosts J
        LEFT JOIN DEPARTMENTS D ON J.DepartmentID = D.DEPTID
        ORDER BY J.PostDate DESC
    """)
    jobs = cursor.fetchall()
    conn.close()
    return render_template('jobs_list.html', jobs=jobs)

@app.route('/jobs/add', methods=['GET', 'POST'])
@login_required
def job_add():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        title = request.form['title']
        dept_id = request.form['dept_id']
        desc = request.form['description']
        reqs = request.form['requirements']
        salary = request.form['salary']
        deadline = request.form['deadline'] or None
        
        cursor.execute("""
            INSERT INTO JobPosts (JobTitle, DepartmentID, Description, Requirements, SalaryRange, Deadline, Status)
            VALUES (?, ?, ?, ?, ?, ?, 'Active')
        """, (title, dept_id, desc, reqs, salary, deadline))
        conn.commit()
        conn.close()
        flash('✅ تم نشر الوظيفة بنجاح', 'success')
        return redirect(url_for('job_list'))

    cursor.execute("SELECT DEPTID, DEPTNAME FROM DEPARTMENTS ORDER BY DEPTNAME")
    depts = cursor.fetchall()
    conn.close()
    return render_template('job_form.html', depts=depts, action='Add')

@app.route('/jobs/edit/<int:jid>', methods=['GET', 'POST'])
@login_required
def job_edit(jid):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        title = request.form['title']
        dept_id = request.form['dept_id']
        desc = request.form['description']
        reqs = request.form['requirements']
        salary = request.form['salary']
        deadline = request.form['deadline'] or None
        status = request.form['status']
        
        cursor.execute("""
            UPDATE JobPosts SET 
            JobTitle=?, DepartmentID=?, Description=?, Requirements=?, SalaryRange=?, Deadline=?, Status=?
            WHERE JobID=?
        """, (title, dept_id, desc, reqs, salary, deadline, status, jid))
        conn.commit()
        conn.close()
        flash('✅ تم تحديث الوظيفة', 'success')
        return redirect(url_for('job_list'))

    cursor.execute("SELECT * FROM JobPosts WHERE JobID = ?", (jid,))
    job = cursor.fetchone()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM DEPARTMENTS ORDER BY DEPTNAME")
    depts = cursor.fetchall()
    conn.close()
    return render_template('job_form.html', job=job, depts=depts, action='Edit')

@app.route('/jobs/delete/<int:jid>', methods=['POST'])
@login_required
def job_delete(jid):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Optional: Check if there are applicants first
        cursor.execute("DELETE FROM JobPosts WHERE JobID = ?", (jid,))
        conn.commit()
        flash('✅ تم حذف الوظيفة بنجاح', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('job_list'))

@app.route('/debug/userinfo')
def debug_userinfo():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DEPTID, DEPTNAME FROM [Zktime].[dbo].[DEPARTMENTS] ORDER BY DEPTID")
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')