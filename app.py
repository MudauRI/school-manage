# app.py
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
import io

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# South African subjects with levels
SUBJECTS = {
    'Home Language': ['English', 'Afrikaans', 'isiZulu', 'isiXhosa', 'Sesotho', 'Setswana'],
    'First Additional Language': ['English', 'Afrikaans', 'isiZulu', 'isiXhosa', 'Sesotho', 'Setswana'],
    'Mathematics': ['Level 4', 'Level 3', 'Level 2', 'Level 1'],
    'Mathematical Literacy': ['Level 4', 'Level 3', 'Level 2', 'Level 1'],
    'Life Orientation': ['Level 4', 'Level 3', 'Level 2', 'Level 1'],
    'Accounting': ['Level 7', 'Level 6', 'Level 5', 'Level 4', 'Level 3', 'Level 2', 'Level 1'],
    'Business Studies': ['Level 7', 'Level 6', 'Level 5', 'Level 4', 'Level 3', 'Level 2', 'Level 1'],
    'Geography': ['Level 7', 'Level 6', 'Level 5', 'Level 4', 'Level 3', 'Level 2', 'Level 1'],
    'History': ['Level 7', 'Level 6', 'Level 5', 'Level 4', 'Level 3', 'Level 2', 'Level 1'],
    'Life Sciences': ['Level 7', 'Level 6', 'Level 5', 'Level 4', 'Level 3', 'Level 2', 'Level 1'],
    'Physical Sciences': ['Level 7', 'Level 6', 'Level 5', 'Level 4', 'Level 3', 'Level 2', 'Level 1']
}

# Grade to points mapping
GRADE_TO_POINTS = {
    'A': 4.0, 'A-': 3.7, 'B+': 3.3, 'B': 3.0, 'B-': 2.7,
    'C+': 2.3, 'C': 2.0, 'C-': 1.7, 'D+': 1.3, 'D': 1.0, 'F': 0.0
}

# Ensure upload directory exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Database initialization
def init_db():
    conn = sqlite3.connect('results.db')
    c = conn.cursor()
    
    # Create users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 username TEXT UNIQUE NOT NULL,
                 password TEXT NOT NULL,
                 role TEXT NOT NULL,
                 full_name TEXT,
                 email TEXT,
                 created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    
    # Create students table
    c.execute('''CREATE TABLE IF NOT EXISTS students
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 student_id TEXT UNIQUE NOT NULL,
                 full_name TEXT NOT NULL,
                 email TEXT NOT NULL,
                 program TEXT,
                 year INTEGER,
                 date_of_birth TEXT,
                 phone_number TEXT,
                 address TEXT,
                 created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    
    # Create results table with remark field
    c.execute('''CREATE TABLE IF NOT EXISTS results
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 student_id TEXT NOT NULL,
                 course_code TEXT NOT NULL,
                 course_name TEXT NOT NULL,
                 subject_level TEXT,
                 grade TEXT NOT NULL,
                 credits INTEGER,
                 semester TEXT NOT NULL,
                 academic_year TEXT NOT NULL,
                 remark TEXT,
                 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                 updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                 FOREIGN KEY (student_id) REFERENCES students (student_id))''')
    
    # Create documents table
    c.execute('''CREATE TABLE IF NOT EXISTS documents
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 student_id TEXT NOT NULL,
                 doc_name TEXT NOT NULL,
                 doc_type TEXT NOT NULL,
                 doc_path TEXT NOT NULL,
                 upload_date TEXT NOT NULL,
                 status TEXT DEFAULT 'Pending',
                 feedback TEXT,
                 reviewed_by TEXT,
                 reviewed_at TEXT,
                 FOREIGN KEY (student_id) REFERENCES students (student_id))''')
    
    # Insert default admin user if not exists
    admin_exists = c.execute("SELECT * FROM users WHERE username='admin'").fetchone()
    if not admin_exists:
        hashed_password = generate_password_hash('admin123')
        c.execute("INSERT INTO users (username, password, role, full_name, email) VALUES (?, ?, ?, ?, ?)",
                  ('admin', hashed_password, 'admin', 'System Administrator', 'admin@izra.edu'))
        print("Admin user created successfully")
    else:
        print("Admin user already exists")
    
    # Insert some sample students
    sample_students = [
        ('S1001', 'Rendani Mudau', 'rendani.mudau@student.izra.edu', 'Grade 12', 2023, '2000-05-15', '+27123456789', '123 Main St, Johannesburg'),
        ('S1002', 'Emma Sithi', 'emma.sithi@student.izra.edu', 'Grade 12', 2023, '2001-02-20', '+27123456790', '456 Oak Ave, Pretoria'),
        ('S1003', 'Michael Tshwika', 'michael.tswika@student.izra.edu', 'Grade 11', 2022, '1999-11-10', '+27123456791', '789 Pine Rd, Cape Town')
    ]
    
    for student in sample_students:
        student_exists = c.execute("SELECT * FROM students WHERE student_id=?", (student[0],)).fetchone()
        if not student_exists:
            c.execute("INSERT INTO students (student_id, full_name, email, program, year, date_of_birth, phone_number, address) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", student)
            print(f"Student {student[0]} created successfully")
        else:
            print(f"Student {student[0]} already exists")
        
        # Also create a user account for the student if it doesn't exist
        user_exists = c.execute("SELECT * FROM users WHERE username=?", (student[0],)).fetchone()
        if not user_exists:
            hashed_password = generate_password_hash('password123')
            c.execute("INSERT INTO users (username, password, role, full_name, email) VALUES (?, ?, ?, ?, ?)",
                      (student[0], hashed_password, 'student', student[1], student[2]))
            print(f"User for student {student[0]} created successfully")
        else:
            print(f"User for student {student[0]} already exists")
    
    # Insert some sample results with South African subjects
    sample_results = [
        ('S1001', 'ENGHL', 'English Home Language', 'Level 4', 'A', 4, 'Term 1', '2023', 'Excellent performance in reading comprehension'),
        ('S1001', 'MATH', 'Mathematics', 'Level 4', 'B+', 3, 'Term 1', '2023', 'Good understanding of algebra concepts'),
        ('S1001', 'PHYSCI', 'Physical Sciences', 'Level 4', 'A-', 4, 'Term 1', '2023', 'Strong in practical experiments'),
        ('S1001', 'LIFSCI', 'Life Sciences', 'Level 4', 'B', 3, 'Term 2', '2023', 'Good grasp of biological concepts'),
        ('S1002', 'AFRHL', 'Afrikaans Home Language', 'Level 4', 'A-', 4, 'Term 1', '2023', 'Excellent written skills'),
        ('S1002', 'BUSSTU', 'Business Studies', 'Level 4', 'B', 3, 'Term 1', '2023', 'Good understanding of business concepts'),
        ('S1002', 'ACCT', 'Accounting', 'Level 4', 'B+', 3, 'Term 1', '2023', 'Needs improvement in financial statements'),
        ('S1002', 'GEOG', 'Geography', 'Level 4', 'A', 4, 'Term 2', '2023', 'Excellent map work skills'),
        ('S1003', 'ZULHL', 'isiZulu Home Language', 'Level 4', 'A', 4, 'Term 1', '2022', 'Excellent oral and written skills'),
        ('S1003', 'LIFSCI', 'Life Sciences', 'Level 4', 'A', 4, 'Term 1', '2022', 'Very good in biological concepts'),
        ('S1003', 'GEOG', 'Geography', 'Level 4', 'B+', 3, 'Term 1', '2022', 'Good mapwork skills'),
        ('S1003', 'HIST', 'History', 'Level 4', 'B', 3, 'Term 2', '2022', 'Good analytical skills')
    ]
    
    for result in sample_results:
        result_exists = c.execute("SELECT * FROM results WHERE student_id=? AND course_code=? AND semester=? AND academic_year=?", 
                                 (result[0], result[1], result[5], result[6])).fetchone()
        if not result_exists:
            c.execute("INSERT INTO results (student_id, course_code, course_name, subject_level, grade, credits, semester, academic_year, remark) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", result)
            print(f"Result for {result[0]} in {result[1]} created successfully")
        else:
            print(f"Result for {result[0]} in {result[1]} already exists")
    
    conn.commit()
    conn.close()
    print("Database initialized successfully")

init_db()

# Database connection helper
def get_db_connection():
    conn = sqlite3.connect('results.db')
    conn.row_factory = sqlite3.Row
    return conn

# Helper function to calculate GPA
def calculate_gpa(results):
    if not results:
        return 0.0
    
    grade_points = 0
    total_credits = 0
    
    for result in results:
        credit = result['credits'] or 0
        grade = result['grade']
        
        if grade in GRADE_TO_POINTS:
            points = GRADE_TO_POINTS[grade]
            grade_points += points * credit
            total_credits += credit
    
    return round(grade_points / total_credits, 2) if total_credits > 0 else 0.0

# Authentication decorators
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def admin_required(f):
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def student_required(f):
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'student':
            flash('Student access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Context processor for template functions
@app.context_processor
def utility_processor():
    def now(format='%Y-%m-%d %H:%M'):
        return datetime.now().strftime(format)
    return dict(now=now)

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND role = ?', (username, role)).fetchone()
        
        if user:
            print(f"User found: {user['username']}")
            print(f"Password check: {check_password_hash(user['password'], password)}")
            
            if check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                session['full_name'] = user['full_name']
                
                flash(f'Welcome back, {user["full_name"]}!', 'success')
                
                if user['role'] == 'admin':
                    conn.close()
                    return redirect(url_for('admin_dashboard'))
                else:
                    # For students, also get student info
                    student = conn.execute('SELECT * FROM students WHERE student_id = ?', (username,)).fetchone()
                    if student:
                        session['student_id'] = student['student_id']
                        session['program'] = student['program']
                        session['year'] = student['year']
                    conn.close()
                    return redirect(url_for('student_dashboard'))
            else:
                flash('Invalid password.', 'danger')
        else:
            flash('User not found.', 'danger')
        
        conn.close()
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    
    # Get counts for dashboard
    student_count = conn.execute('SELECT COUNT(*) FROM students').fetchone()[0]
    result_count = conn.execute('SELECT COUNT(*) FROM results').fetchone()[0]
    document_count = conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
    pending_docs = conn.execute('SELECT COUNT(*) FROM documents WHERE status = "Pending"').fetchone()[0]
    
    # Get recent documents
    recent_docs = conn.execute('''
        SELECT d.*, s.full_name 
        FROM documents d 
        JOIN students s ON d.student_id = s.student_id 
        ORDER BY d.upload_date DESC 
        LIMIT 5
    ''').fetchall()
    
    # Get recent results
    recent_results = conn.execute('''
        SELECT r.*, s.full_name 
        FROM results r 
        JOIN students s ON r.student_id = s.student_id 
        ORDER BY r.id DESC 
        LIMIT 5
    ''').fetchall()
    
    # Get grade distribution
    grade_distribution = conn.execute('''
        SELECT grade, COUNT(*) as count 
        FROM results 
        GROUP BY grade 
        ORDER BY grade
    ''').fetchall()
    
    conn.close()
    
    return render_template('admin_dashboard.html', 
                          student_count=student_count, 
                          result_count=result_count,
                          document_count=document_count,
                          pending_docs=pending_docs,
                          recent_docs=recent_docs,
                          recent_results=recent_results,
                          grade_distribution=grade_distribution,
                          subjects=SUBJECTS)

@app.route('/admin/students')
@admin_required
def manage_students():
    search = request.args.get('search', '')
    program_filter = request.args.get('program', '')
    year_filter = request.args.get('year', '')
    
    conn = get_db_connection()
    
    # Build query with filters
    query = 'SELECT * FROM students WHERE 1=1'
    params = []
    
    if search:
        query += ' AND (student_id LIKE ? OR full_name LIKE ? OR email LIKE ?)'
        search_param = f'%{search}%'
        params.extend([search_param, search_param, search_param])
    
    if program_filter:
        query += ' AND program = ?'
        params.append(program_filter)
    
    if year_filter:
        query += ' AND year = ?'
        params.append(year_filter)
    
    query += ' ORDER BY student_id'
    
    students = conn.execute(query, params).fetchall()
    
    # Get filter options
    programs = conn.execute('SELECT DISTINCT program FROM students ORDER BY program').fetchall()
    years = conn.execute('SELECT DISTINCT year FROM students ORDER BY year DESC').fetchall()
    
    conn.close()
    
    return render_template('manage_students.html', 
                          students=students,
                          programs=programs,
                          years=years,
                          current_filters={
                              'search': search,
                              'program': program_filter,
                              'year': year_filter
                          })

@app.route('/admin/student/<student_id>')
@admin_required
def view_student(student_id):
    conn = get_db_connection()
    
    # Get student details
    student = conn.execute('SELECT * FROM students WHERE student_id = ?', (student_id,)).fetchone()
    
    if not student:
        flash('Student not found.', 'danger')
        conn.close()
        return redirect(url_for('manage_students'))
    
    # Get student results with better sorting
    results = conn.execute('''
        SELECT * FROM results 
        WHERE student_id = ? 
        ORDER BY academic_year DESC, semester DESC, course_code
    ''', (student_id,)).fetchall()
    
    # Get student documents
    documents = conn.execute('''
        SELECT * FROM documents 
        WHERE student_id = ? 
        ORDER BY upload_date DESC
    ''', (student_id,)).fetchall()
    
    # Calculate GPA and other statistics
    gpa = calculate_gpa(results)
    total_credits = sum(r['credits'] or 0 for r in results)
    
    # Grade distribution
    grade_distribution = {}
    for result in results:
        grade = result['grade']
        grade_distribution[grade] = grade_distribution.get(grade, 0) + 1
    
    # Calculate additional statistics
    total_subjects = len(results)
    passed_subjects = sum(1 for r in results if r['grade'] not in ['F', 'D'])
    highest_grade = max([r['grade'] for r in results], key=lambda x: GRADE_TO_POINTS.get(x, 0)) if results else 'N/A'
    lowest_grade = min([r['grade'] for r in results], key=lambda x: GRADE_TO_POINTS.get(x, 0)) if results else 'N/A'
    
    # Document statistics
    pending_docs = sum(1 for d in documents if d['status'] == 'Pending')
    approved_docs = sum(1 for d in documents if d['status'] == 'Approved')
    rejected_docs = sum(1 for d in documents if d['status'] == 'Rejected')
    
    conn.close()
    
    return render_template('view_student.html', 
                          student=student, 
                          results=results, 
                          documents=documents,
                          gpa=gpa,
                          total_credits=total_credits,
                          total_subjects=total_subjects,
                          passed_subjects=passed_subjects,
                          highest_grade=highest_grade,
                          lowest_grade=lowest_grade,
                          grade_distribution=grade_distribution,
                          pending_docs=pending_docs,
                          approved_docs=approved_docs,
                          rejected_docs=rejected_docs,
                          subjects=SUBJECTS)

@app.route('/admin/view_result/<int:result_id>')
@admin_required
def view_result(result_id):
    """View individual result details"""
    conn = get_db_connection()
    
    # Get result with student information
    result = conn.execute('''
        SELECT r.*, s.full_name, s.email, s.program, s.year
        FROM results r 
        JOIN students s ON r.student_id = s.student_id 
        WHERE r.id = ?
    ''', (result_id,)).fetchone()
    
    if not result:
        flash('Result not found.', 'danger')
        conn.close()
        return redirect(url_for('manage_results'))
    
    # Get all results for this student to show context
    student_results = conn.execute('''
        SELECT * FROM results 
        WHERE student_id = ? 
        ORDER BY academic_year DESC, semester DESC
    ''', (result['student_id'],)).fetchall()
    
    # Calculate student's overall GPA
    student_gpa = calculate_gpa(student_results)
    
    conn.close()
    
    return render_template('view_result.html', 
                          result=result,
                          student_results=student_results,
                          student_gpa=student_gpa,
                          subjects=SUBJECTS)

@app.route('/admin/edit_student/<student_id>', methods=['GET', 'POST'])
@admin_required
def edit_student(student_id):
    conn = get_db_connection()
    
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        program = request.form['program']
        year = request.form['year']
        date_of_birth = request.form['date_of_birth']
        phone_number = request.form['phone_number']
        address = request.form['address']
        
        # Update student
        conn.execute('''
            UPDATE students 
            SET full_name = ?, email = ?, program = ?, year = ?, date_of_birth = ?, phone_number = ?, address = ?
            WHERE student_id = ?
        ''', (full_name, email, program, year, date_of_birth, phone_number, address, student_id))
        
        # Also update user info
        conn.execute('''
            UPDATE users 
            SET full_name = ?, email = ?
            WHERE username = ?
        ''', (full_name, email, student_id))
        
        conn.commit()
        conn.close()
        
        flash('Student information updated successfully!', 'success')
        return redirect(url_for('view_student', student_id=student_id))
    
    # GET request - load student data
    student = conn.execute('SELECT * FROM students WHERE student_id = ?', (student_id,)).fetchone()
    conn.close()
    
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('manage_students'))
    
    return render_template('edit_student.html', student=student)

@app.route('/admin/delete_student/<student_id>')
@admin_required
def delete_student(student_id):
    conn = get_db_connection()
    
    # Check if student exists
    student = conn.execute('SELECT * FROM students WHERE student_id = ?', (student_id,)).fetchone()
    if not student:
        flash('Student not found.', 'danger')
        conn.close()
        return redirect(url_for('manage_students'))
    
    # Delete related records first
    conn.execute('DELETE FROM results WHERE student_id = ?', (student_id,))
    conn.execute('DELETE FROM documents WHERE student_id = ?', (student_id,))
    conn.execute('DELETE FROM students WHERE student_id = ?', (student_id,))
    conn.execute('DELETE FROM users WHERE username = ?', (student_id,))
    
    conn.commit()
    conn.close()
    
    flash('Student and all related records deleted successfully!', 'success')
    return redirect(url_for('manage_students'))

@app.route('/admin/results')
@admin_required
def manage_results():
    # Get filter parameters
    course_filter = request.args.get('course', '')
    grade_filter = request.args.get('grade', '')
    semester_filter = request.args.get('semester', '')
    year_filter = request.args.get('year', '')
    subject_filter = request.args.get('subject', '')
    student_filter = request.args.get('student', '')
    
    conn = get_db_connection()
    
    # Build query with filters
    query = '''
        SELECT r.*, s.full_name 
        FROM results r 
        JOIN students s ON r.student_id = s.student_id 
        WHERE 1=1
    '''
    params = []
    
    if course_filter:
        query += ' AND (r.course_code LIKE ? OR r.course_name LIKE ?)'
        params.extend([f'%{course_filter}%', f'%{course_filter}%'])
    
    if grade_filter:
        query += ' AND r.grade = ?'
        params.append(grade_filter)
    
    if semester_filter:
        query += ' AND r.semester = ?'
        params.append(semester_filter)
    
    if year_filter:
        query += ' AND r.academic_year = ?'
        params.append(year_filter)
    
    if subject_filter:
        query += ' AND r.course_name LIKE ?'
        params.append(f'%{subject_filter}%')
    
    if student_filter:
        query += ' AND (r.student_id LIKE ? OR s.full_name LIKE ?)'
        params.extend([f'%{student_filter}%', f'%{student_filter}%'])
    
    query += ' ORDER BY r.academic_year DESC, r.semester, r.student_id'
    
    results = conn.execute(query, params).fetchall()
    
    # Get unique values for filter dropdowns
    courses = conn.execute('SELECT DISTINCT course_code, course_name FROM results ORDER BY course_code').fetchall()
    grades = conn.execute('SELECT DISTINCT grade FROM results ORDER BY grade').fetchall()
    semesters = conn.execute('SELECT DISTINCT semester FROM results ORDER BY semester').fetchall()
    years = conn.execute('SELECT DISTINCT academic_year FROM results ORDER BY academic_year DESC').fetchall()
    
    conn.close()
    
    return render_template('manage_results.html', 
                          results=results, 
                          courses=courses,
                          grades=grades,
                          semesters=semesters,
                          years=years,
                          subjects=SUBJECTS,
                          current_filters={
                              'course': course_filter,
                              'grade': grade_filter,
                              'semester': semester_filter,
                              'year': year_filter,
                              'subject': subject_filter,
                              'student': student_filter
                          })

@app.route('/admin/edit_result/<int:result_id>', methods=['GET', 'POST'])
@admin_required
def edit_result(result_id):
    conn = get_db_connection()
    
    if request.method == 'POST':
        course_code = request.form['course_code']
        course_name = request.form['course_name']
        subject_level = request.form['subject_level']
        grade = request.form['grade']
        credits = request.form['credits']
        semester = request.form['semester']
        academic_year = request.form['academic_year']
        remark = request.form['remark']
        
        # Update result
        conn.execute('''
            UPDATE results 
            SET course_code = ?, course_name = ?, subject_level = ?, grade = ?, credits = ?, 
                semester = ?, academic_year = ?, remark = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (course_code, course_name, subject_level, grade, credits, semester, academic_year, remark, result_id))
        
        conn.commit()
        conn.close()
        
        flash('Result updated successfully!', 'success')
        return redirect(url_for('view_result', result_id=result_id))
    
    # GET request - load result data
    result = conn.execute('''
        SELECT r.*, s.full_name 
        FROM results r 
        JOIN students s ON r.student_id = s.student_id 
        WHERE r.id = ?
    ''', (result_id,)).fetchone()
    
    conn.close()
    
    if not result:
        flash('Result not found.', 'danger')
        return redirect(url_for('manage_results'))
    
    return render_template('edit_result.html', result=result, subjects=SUBJECTS)

@app.route('/admin/delete_result/<int:result_id>')
@admin_required
def delete_result(result_id):
    conn = get_db_connection()
    
    # Check if result exists and get student info for redirect
    result = conn.execute('''
        SELECT r.*, s.full_name 
        FROM results r 
        JOIN students s ON r.student_id = s.student_id 
        WHERE r.id = ?
    ''', (result_id,)).fetchone()
    
    if not result:
        flash('Result not found.', 'danger')
        conn.close()
        return redirect(url_for('manage_results'))
    
    student_id = result['student_id']
    
    # Delete result
    conn.execute('DELETE FROM results WHERE id = ?', (result_id,))
    conn.commit()
    conn.close()
    
    flash(f'Result for {result["course_name"]} deleted successfully!', 'success')
    
    # Check if we came from student view
    if request.referrer and 'student' in request.referrer:
        return redirect(url_for('view_student', student_id=student_id))
    else:
        return redirect(url_for('manage_results'))

@app.route('/admin/documents')
@admin_required
def manage_documents():
    status_filter = request.args.get('status', '')
    doc_type_filter = request.args.get('doc_type', '')
    student_filter = request.args.get('student', '')
    
    conn = get_db_connection()
    
    # Build query with filters
    query = '''
        SELECT d.*, s.full_name 
        FROM documents d 
        JOIN students s ON d.student_id = s.student_id 
        WHERE 1=1
    '''
    params = []
    
    if status_filter:
        query += ' AND d.status = ?'
        params.append(status_filter)
    
    if doc_type_filter:
        query += ' AND d.doc_type = ?'
        params.append(doc_type_filter)
    
    if student_filter:
        query += ' AND (d.student_id LIKE ? OR s.full_name LIKE ?)'
        params.extend([f'%{student_filter}%', f'%{student_filter}%'])
    
    query += ' ORDER BY d.upload_date DESC'
    
    documents = conn.execute(query, params).fetchall()
    
    # Get filter options
    status_options = ['Pending', 'Approved', 'Rejected']
    doc_types = conn.execute('SELECT DISTINCT doc_type FROM documents ORDER BY doc_type').fetchall()
    
    conn.close()
    
    return render_template('manage_documents.html', 
                          documents=documents,
                          status_options=status_options,
                          doc_types=doc_types,
                          current_filters={
                              'status': status_filter,
                              'doc_type': doc_type_filter,
                              'student': student_filter
                          })

@app.route('/admin/update_document_status/<int:doc_id>', methods=['POST'])
@admin_required
def update_document_status(doc_id):
    new_status = request.form['status']
    feedback = request.form.get('feedback', '')
    
    conn = get_db_connection()
    conn.execute('''
        UPDATE documents 
        SET status = ?, feedback = ?, reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP 
        WHERE id = ?
    ''', (new_status, feedback, session['username'], doc_id))
    conn.commit()
    conn.close()
    
    flash(f'Document status updated to {new_status}!', 'success')
    
    # Check if we came from student view
    if request.referrer and 'student' in request.referrer:
        # Extract student ID from referrer URL
        import re
        student_match = re.search(r'/student/([^/]+)', request.referrer)
        if student_match:
            return redirect(url_for('view_student', student_id=student_match.group(1)))
    
    return redirect(url_for('manage_documents'))

@app.route('/admin/analytics')
@admin_required
def analytics():
    conn = get_db_connection()
    
    # Overall statistics
    total_students = conn.execute('SELECT COUNT(*) FROM students').fetchone()[0]
    total_results = conn.execute('SELECT COUNT(*) FROM results').fetchone()[0]
    total_documents = conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
    
    # Grade distribution
    grade_distribution = conn.execute('''
        SELECT grade, COUNT(*) as count 
        FROM results 
        GROUP BY grade 
        ORDER BY 
            CASE grade 
                WHEN 'A' THEN 1 
                WHEN 'A-' THEN 2 
                WHEN 'B+' THEN 3 
                WHEN 'B' THEN 4 
                WHEN 'B-' THEN 5 
                WHEN 'C+' THEN 6 
                WHEN 'C' THEN 7 
                WHEN 'C-' THEN 8 
                WHEN 'D+' THEN 9 
                WHEN 'D' THEN 10 
                WHEN 'F' THEN 11 
                ELSE 12 
            END
    ''').fetchall()
    
    # Program statistics
    program_stats = conn.execute('''
        SELECT program, COUNT(*) as student_count 
        FROM students 
        GROUP BY program 
        ORDER BY student_count DESC
    ''').fetchall()
    
    # Semester performance
    semester_stats = conn.execute('''
        SELECT semester, academic_year, 
               AVG(CASE 
                   WHEN grade = 'A' THEN 4.0
                   WHEN grade = 'A-' THEN 3.7
                   WHEN grade = 'B+' THEN 3.3
                   WHEN grade = 'B' THEN 3.0
                   WHEN grade = 'B-' THEN 2.7
                   WHEN grade = 'C+' THEN 2.3
                   WHEN grade = 'C' THEN 2.0
                   WHEN grade = 'C-' THEN 1.7
                   WHEN grade = 'D+' THEN 1.3
                   WHEN grade = 'D' THEN 1.0
                   ELSE 0.0
               END) as avg_gpa,
               COUNT(*) as total_results
        FROM results 
        GROUP BY semester, academic_year 
        ORDER BY academic_year DESC, semester
    ''').fetchall()
    
    # Subject performance
    subject_performance = conn.execute('''
        SELECT course_name, course_code,
               COUNT(*) as total_students,
               SUM(CASE WHEN grade IN ('F', 'D', 'D+') THEN 1 ELSE 0 END) as struggling_students,
               AVG(CASE 
                   WHEN grade = 'A' THEN 4.0
                   WHEN grade = 'A-' THEN 3.7
                   WHEN grade = 'B+' THEN 3.3
                   WHEN grade = 'B' THEN 3.0
                   WHEN grade = 'B-' THEN 2.7
                   WHEN grade = 'C+' THEN 2.3
                   WHEN grade = 'C' THEN 2.0
                   WHEN grade = 'C-' THEN 1.7
                   WHEN grade = 'D+' THEN 1.3
                   WHEN grade = 'D' THEN 1.0
                   ELSE 0.0
               END) as avg_gpa
        FROM results
        GROUP BY course_name, course_code
        ORDER BY avg_gpa DESC
    ''').fetchall()
    
    # Student performance overview
    student_performance = conn.execute('''
        SELECT s.student_id, s.full_name, s.program,
               COUNT(r.id) as total_subjects,
               AVG(CASE 
                   WHEN r.grade = 'A' THEN 4.0
                   WHEN r.grade = 'A-' THEN 3.7
                   WHEN r.grade = 'B+' THEN 3.3
                   WHEN r.grade = 'B' THEN 3.0
                   WHEN r.grade = 'B-' THEN 2.7
                   WHEN r.grade = 'C+' THEN 2.3
                   WHEN r.grade = 'C' THEN 2.0
                   WHEN r.grade = 'C-' THEN 1.7
                   WHEN r.grade = 'D+' THEN 1.3
                   WHEN r.grade = 'D' THEN 1.0
                   ELSE 0.0
               END) as gpa
        FROM students s
        LEFT JOIN results r ON s.student_id = r.student_id
        GROUP BY s.student_id, s.full_name, s.program
        ORDER BY gpa DESC
    ''').fetchall()
    
    conn.close()
    
    return render_template('analytics.html',
                         total_students=total_students,
                         total_results=total_results,
                         total_documents=total_documents,
                         grade_distribution=grade_distribution,
                         program_stats=program_stats,
                         semester_stats=semester_stats,
                         subject_performance=subject_performance,
                         student_performance=student_performance,
                         subjects=SUBJECTS)

@app.route('/admin/add_result', methods=['GET', 'POST'])
@admin_required
def add_result():
    if request.method == 'POST':
        student_id = request.form['student_id']
        course_code = request.form['course_code']
        course_name = request.form['course_name']
        subject_level = request.form['subject_level']
        grade = request.form['grade']
        credits = request.form['credits']
        semester = request.form['semester']
        academic_year = request.form['academic_year']
        remark = request.form['remark']
        
        conn = get_db_connection()
        
        # Check if student exists
        student = conn.execute('SELECT * FROM students WHERE student_id = ?', (student_id,)).fetchone()
        if not student:
            flash('Student ID does not exist.', 'danger')
            conn.close()
            return render_template('add_result.html', subjects=SUBJECTS)
        
        # Check if result already exists for this student, course, semester, and year
        existing = conn.execute('''
            SELECT * FROM results 
            WHERE student_id = ? AND course_code = ? AND semester = ? AND academic_year = ?
        ''', (student_id, course_code, semester, academic_year)).fetchone()
        
        if existing:
            flash('Result for this course already exists for this student in the specified semester and year.', 'warning')
            conn.close()
            return render_template('add_result.html', subjects=SUBJECTS)
        
        # Insert new result
        conn.execute('''
            INSERT INTO results (student_id, course_code, course_name, subject_level, grade, credits, semester, academic_year, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, course_code, course_name, subject_level, grade, credits, semester, academic_year, remark))
        
        conn.commit()
        conn.close()
        
        flash(f'Result added successfully for {student["full_name"]}!', 'success')
        
        # Check if we should redirect to student view
        redirect_to_student = request.form.get('redirect_to_student')
        if redirect_to_student == 'true':
            return redirect(url_for('view_student', student_id=student_id))
        else:
            return redirect(url_for('manage_results'))
    
    # Pre-populate student_id if provided in query params
    default_student_id = request.args.get('student_id', '')
    
    return render_template('add_result.html', subjects=SUBJECTS, default_student_id=default_student_id)

@app.route('/admin/add_student', methods=['GET', 'POST'])
@admin_required
def add_student():
    if request.method == 'POST':
        student_id = request.form['student_id']
        full_name = request.form['full_name']
        email = request.form['email']
        program = request.form['program']
        year = request.form['year']
        date_of_birth = request.form['date_of_birth']
        phone_number = request.form['phone_number']
        address = request.form['address']
        
        conn = get_db_connection()
        
        # Check if student already exists
        existing = conn.execute('SELECT * FROM students WHERE student_id = ?', (student_id,)).fetchone()
        if existing:
            flash('Student ID already exists.', 'danger')
            conn.close()
            return render_template('add_student.html')
        
        # Check if email already exists
        existing_email = conn.execute('SELECT * FROM students WHERE email = ?', (email,)).fetchone()
        if existing_email:
            flash('Email already exists.', 'danger')
            conn.close()
            return render_template('add_student.html')
        
        # Insert new student
        conn.execute('''
            INSERT INTO students (student_id, full_name, email, program, year, date_of_birth, phone_number, address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, full_name, email, program, year, date_of_birth, phone_number, address))
        
        # Also create a user account for the student
        default_password = 'password123'
        conn.execute('''
            INSERT INTO users (username, password, role, full_name, email)
            VALUES (?, ?, ?, ?, ?)
        ''', (student_id, generate_password_hash(default_password), 'student', full_name, email))
        
        conn.commit()
        conn.close()
        
        flash(f'Student {full_name} added successfully! Default password is "{default_password}"', 'success')
        return redirect(url_for('manage_students'))
    
    return render_template('add_student.html')

# Student Routes
@app.route('/student/dashboard')
@student_required
def student_dashboard():
    conn = get_db_connection()
    
    # Get student results
    results = conn.execute('''
        SELECT * FROM results 
        WHERE student_id = ? 
        ORDER BY academic_year DESC, semester DESC, course_code
    ''', (session['student_id'],)).fetchall()
    
    # Calculate GPA
    gpa = calculate_gpa(results)
    total_credits = sum(r['credits'] or 0 for r in results)
    
    # Get uploaded documents
    documents = conn.execute('''
        SELECT * FROM documents 
        WHERE student_id = ? 
        ORDER BY upload_date DESC
    ''', (session['student_id'],)).fetchall()
    
    conn.close()
    
    return render_template('student_dashboard.html', 
                          results=results, 
                          documents=documents,
                          gpa=gpa,
                          total_credits=total_credits)

@app.route('/student/upload', methods=['GET', 'POST'])
@student_required
def upload_document():
    if request.method == 'POST':
        if 'document' not in request.files:
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        file = request.files['document']
        doc_type = request.form['doc_type']
        
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        if file:
            # Check file extension
            allowed_extensions = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'txt'}
            file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            
            if file_extension not in allowed_extensions:
                flash('File type not allowed. Please upload PDF, DOC, DOCX, JPG, PNG, or TXT files only.', 'danger')
                return redirect(request.url)
            
            # Secure filename and create path
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{session['student_id']}_{timestamp}_{file.filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Save to database
            conn = get_db_connection()
            conn.execute('''
                INSERT INTO documents (student_id, doc_name, doc_type, doc_path, upload_date)
                VALUES (?, ?, ?, ?, ?)
            ''', (session['student_id'], file.filename, doc_type, filepath, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            conn.close()
            
            flash('Document uploaded successfully!', 'success')
            return redirect(url_for('student_dashboard'))
    
    return render_template('upload_document.html')

@app.route('/student/query', methods=['GET', 'POST'])
@student_required
def submit_query():
    if request.method == 'POST':
        query_type = request.form['query_type']
        message = request.form['message']
        
        # In a real application, you would save this to a database
        # For now, we'll just flash a message
        flash('Your query has been submitted successfully. We will get back to you soon.', 'success')
        return redirect(url_for('student_dashboard'))
    
    return render_template('submit_query.html')

@app.route('/student/results')
@student_required
def student_results():
    """Student view of their own results"""
    conn = get_db_connection()
    
    # Get student results with filtering options
    year_filter = request.args.get('year', '')
    semester_filter = request.args.get('semester', '')
    
    query = 'SELECT * FROM results WHERE student_id = ?'
    params = [session['student_id']]
    
    if year_filter:
        query += ' AND academic_year = ?'
        params.append(year_filter)
    
    if semester_filter:
        query += ' AND semester = ?'
        params.append(semester_filter)
    
    query += ' ORDER BY academic_year DESC, semester DESC, course_code'
    
    results = conn.execute(query, params).fetchall()
    
    # Get filter options
    years = conn.execute('''
        SELECT DISTINCT academic_year 
        FROM results 
        WHERE student_id = ? 
        ORDER BY academic_year DESC
    ''', (session['student_id'],)).fetchall()
    
    semesters = conn.execute('''
        SELECT DISTINCT semester 
        FROM results 
        WHERE student_id = ? 
        ORDER BY semester
    ''', (session['student_id'],)).fetchall()
    
    # Calculate statistics
    gpa = calculate_gpa(results)
    total_credits = sum(r['credits'] or 0 for r in results)
    
    conn.close()
    
    return render_template('student_results.html',
                          results=results,
                          years=years,
                          semesters=semesters,
                          gpa=gpa,
                          total_credits=total_credits,
                          current_filters={
                              'year': year_filter,
                              'semester': semester_filter
                          })

# Utility Routes
@app.route('/download/<int:doc_id>')
@login_required
def download_document(doc_id):
    conn = get_db_connection()
    document = conn.execute('SELECT * FROM documents WHERE id = ?', (doc_id,)).fetchone()
    conn.close()
    
    if document:
        # Check if user has permission to download
        if session['role'] == 'admin' or (session['role'] == 'student' and document['student_id'] == session['student_id']):
            try:
                return send_file(document['doc_path'], as_attachment=True, download_name=document['doc_name'])
            except FileNotFoundError:
                flash('File not found on server.', 'danger')
        else:
            flash('Access denied.', 'danger')
    else:
        flash('Document not found.', 'danger')
    
    return redirect(url_for('student_dashboard' if session['role'] == 'student' else 'admin_dashboard'))

# API Routes for AJAX calls
@app.route('/api/student/<student_id>')
@admin_required
def get_student_info(student_id):
    """API endpoint to get student information"""
    conn = get_db_connection()
    student = conn.execute('SELECT * FROM students WHERE student_id = ?', (student_id,)).fetchone()
    conn.close()
    
    if student:
        return jsonify({
            'success': True,
            'student': dict(student)
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Student not found'
        })

@app.route('/api/subjects/<subject_category>')
@admin_required
def get_subject_levels(subject_category):
    """API endpoint to get subject levels for a category"""
    if subject_category in SUBJECTS:
        return jsonify({
            'success': True,
            'levels': SUBJECTS[subject_category]
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Subject category not found'
        })

# Debug and Utility Routes
@app.route('/reset-db')
def reset_db():
    """Reset database - USE WITH CAUTION"""
    import os
    if os.path.exists('results.db'):
        os.remove('results.db')
    
    init_db()
    
    return "Database reset successfully! <a href='/'>Go to homepage</a>"

@app.route('/debug/users')
def debug_users():
    """Debug route to show all users"""
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    
    result = "<h1>Users in Database</h1><table border='1'><tr><th>ID</th><th>Username</th><th>Role</th><th>Full Name</th><th>Email</th></tr>"
    for user in users:
        result += f"<tr><td>{user['id']}</td><td>{user['username']}</td><td>{user['role']}</td><td>{user['full_name']}</td><td>{user['email']}</td></tr>"
    result += "</table>"
    
    return result

@app.route('/debug/students')
def debug_students():
    """Debug route to show all students"""
    conn = get_db_connection()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    
    result = "<h1>Students in Database</h1><table border='1'><tr><th>ID</th><th>Student ID</th><th>Full Name</th><th>Email</th><th>Program</th></tr>"
    for student in students:
        result += f"<tr><td>{student['id']}</td><td>{student['student_id']}</td><td>{student['full_name']}</td><td>{student['email']}</td><td>{student['program']}</td></tr>"
    result += "</table>"
    
    return result

# Error Handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500

@app.errorhandler(413)
def too_large(error):
    flash('File too large. Maximum file size is 16MB.', 'danger')
    return redirect(request.url)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
