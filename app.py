from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_babel import Babel, gettext, ngettext, lazy_gettext, get_locale # Correctly imported get_locale
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import csv
import random
import string
import json
import sqlite3

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///game_rural_india.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
CORS(app)
babel = Babel(app)

# Language configuration
LANGUAGES = {
    'en': 'English',
    'hi': 'हिंदी',
    'ta': 'தமிழ்',
    'or': 'ଓଡ଼ିଆ'
}

# Locale selector for Flask-Babel
# This function determines which language to use for a request.
# It checks for a 'lang' URL parameter first, then the session, and defaults to English.
def select_locale():
    return request.args.get("lang") or session.get("language") or "en"

babel = Babel(app, locale_selector=select_locale)

# Inject globals into all templates
@app.context_processor
def inject_globals():
    return dict(
        get_locale=get_locale, # This will now work correctly
        languages=LANGUAGES
    )


# Database Models
class UserProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    mobile = db.Column(db.String(20), nullable=True)
    role = db.Column(db.String(20), nullable=False)  # student or teacher
    firstname = db.Column(db.String(50), nullable=False)
    lastname = db.Column(db.String(50), nullable=False)
    grade = db.Column(db.Integer, nullable=True)  # for students
    school_udise = db.Column(db.String(20), nullable=True)
    school_name = db.Column(db.String(200), nullable=True)
    medium = db.Column(db.String(50), nullable=True)
    state = db.Column(db.String(50), nullable=True)
    district = db.Column(db.String(100), nullable=True)
    dob = db.Column(db.Date, nullable=True)
    qualification = db.Column(db.String(100), nullable=True)  # for teachers
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_verified = db.Column(db.Boolean, default=False)

class UdiseSchool(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    udise_code = db.Column(db.String(20), unique=True, nullable=False)
    school_name = db.Column(db.String(200), nullable=False)
    district = db.Column(db.String(100), nullable=False)
    block = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=True)
    area = db.Column(db.String(20), nullable=True)
    management = db.Column(db.String(50), nullable=True)

class OTPVerification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    otp_code = db.Column(db.String(10), nullable=False)
    otp_hash = db.Column(db.String(200), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class StudentMarks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user_profile.id'), nullable=False)
    subject = db.Column(db.String(50), nullable=False)
    marks = db.Column(db.Integer, nullable=False)
    max_marks = db.Column(db.Integer, default=100)
    exam_date = db.Column(db.Date, nullable=False)
    grade = db.Column(db.Integer, nullable=False)

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user_profile.id'), nullable=False)
    activity_id = db.Column(db.String(50), nullable=False)
    skill_id = db.Column(db.String(50), nullable=False)
    correct = db.Column(db.Boolean, nullable=False)
    time_spent_sec = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class MasteryEstimate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user_profile.id'), nullable=False)
    skill_id = db.Column(db.String(50), nullable=False)
    mastery_prob = db.Column(db.Float, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class TeacherAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user_profile.id'), nullable=False)
    school_udise = db.Column(db.String(20), nullable=False)
    grade = db.Column(db.Integer, nullable=False)

# Utility functions
def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def send_otp_email(email, otp):
    # In production, integrate with SMS/Email service
    print(f"OTP for {email}: {otp}")
    return True

# Routes
@app.route('/')
def index():
    return render_template('index.html', languages=LANGUAGES)

@app.route('/set_language/<language>')
def set_language(language):
    # This route sets the user's preferred language in the session.
    # For this to work, your HTML links must point to this URL.
    # Example for a template: <a href="{{ url_for('set_language', language='hi') }}">हिंदी</a>
    session['language'] = language
    return redirect(request.referrer or url_for('index'))

# Authentication Routes
@app.route('/api/otp/request', methods=['POST'])
def request_otp():
    data = request.get_json()
    email = data.get('email')
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    otp_code = generate_otp()
    otp_hash = generate_password_hash(otp_code)
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    
    # Clean up old OTPs
    OTPVerification.query.filter_by(email=email).delete()
    
    otp_record = OTPVerification(
        email=email,
        otp_code=otp_code,
        otp_hash=otp_hash,
        expires_at=expires_at
    )
    
    db.session.add(otp_record)
    db.session.commit()
    
    # Send OTP (mock implementation)
    if send_otp_email(email, otp_code):
        return jsonify({'success': True, 'message': 'OTP sent successfully'})
    else:
        return jsonify({'error': 'Failed to send OTP'}), 500

@app.route('/api/otp/verify', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email')
    otp_code = data.get('otp')
    
    if not email or not otp_code:
        return jsonify({'error': 'Email and OTP are required'}), 400
    
    otp_record = OTPVerification.query.filter_by(
        email=email, 
        is_used=False
    ).first()
    
    if not otp_record or otp_record.expires_at < datetime.utcnow():
        return jsonify({'error': 'Invalid or expired OTP'}), 400
    
    if not check_password_hash(otp_record.otp_hash, otp_code):
        return jsonify({'error': 'Invalid OTP'}), 400
    
    # Mark OTP as used
    otp_record.is_used = True
    db.session.commit()
    
    # Check if user exists
    user = UserProfile.query.filter_by(email=email).first()
    if user:
        session['user_id'] = user.id
        session['user_role'] = user.role
        return jsonify({
            'success': True, 
            'user_exists': True, 
            'role': user.role,
            'redirect_url': f'/dashboard/{user.role}'
        })
    else:
        session['verified_email'] = email
        return jsonify({
            'success': True, 
            'user_exists': False,
            'redirect_url': '/register'
        })

# UDISE API
@app.route('/api/udise/')
def udise_lookup():
    query = request.args.get('q', '')
    if len(query) < 3:
        return jsonify([])
    
    schools = UdiseSchool.query.filter(
        (UdiseSchool.udise_code.like(f'%{query}%')) |
        (UdiseSchool.school_name.like(f'%{query}%')) |
        (UdiseSchool.district.like(f'%{query}%'))
    ).limit(20).all()
    
    results = []
    for school in schools:
        results.append({
            'udise_code': school.udise_code,
            'school_name': school.school_name,
            'district': school.district,
            'block': school.block
        })
    
    return jsonify(results)

# Registration Routes
@app.route('/register')
def register():
    if 'verified_email' not in session:
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/api/register/student', methods=['POST'])
def register_student():
    if 'verified_email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    
    user = UserProfile(
        email=session['verified_email'],
        role='student',
        firstname=data.get('firstname'),
        lastname=data.get('lastname'),
        grade=int(data.get('grade')),
        school_udise=data.get('udise_code'),
        school_name=data.get('school_name'),
        medium=data.get('medium'),
        state=data.get('state'),
        district=data.get('district'),
        dob=datetime.strptime(data.get('dob'), '%Y-%m-%d').date(),
        is_verified=True
    )
    
    db.session.add(user)
    db.session.commit()
    
    session['user_id'] = user.id
    session['user_role'] = 'student'
    session.pop('verified_email', None)
    
    return jsonify({'success': True, 'redirect_url': '/dashboard/student'})

@app.route('/api/register/teacher', methods=['POST'])
def register_teacher():
    if 'verified_email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    
    user = UserProfile(
        email=session['verified_email'],
        role='teacher',
        firstname=data.get('firstname'),
        lastname=data.get('lastname'),
        school_udise=data.get('udise_code'),
        school_name=data.get('school_name'),
        medium=data.get('medium'),
        state=data.get('state'),
        district=data.get('district'),
        dob=datetime.strptime(data.get('dob'), '%Y-%m-%d').date(),
        qualification=data.get('qualification'),
        is_verified=True
    )
    
    db.session.add(user)
    db.session.commit()
    
    # Create teacher assignment
    assignment = TeacherAssignment(
        teacher_id=user.id,
        school_udise=data.get('udise_code'),
        grade=int(data.get('grade'))
    )
    db.session.add(assignment)
    db.session.commit()
    
    session['user_id'] = user.id
    session['user_role'] = 'teacher'
    session.pop('verified_email', None)
    
    return jsonify({'success': True, 'redirect_url': '/dashboard/teacher'})

# Student Dashboard
@app.route('/dashboard/student')
def student_dashboard():
    if 'user_id' not in session or session.get('user_role') != 'student':
        return redirect(url_for('index'))
    
    user = UserProfile.query.get(session['user_id'])
    return render_template('student_dashboard.html', user=user)

@app.route('/student/grade/<int:grade>')
def student_grade_content(grade):
    if 'user_id' not in session or session.get('user_role') != 'student':
        return redirect(url_for('index'))
    
    user = UserProfile.query.get(session['user_id'])
    return render_template('grade_content.html', user=user, grade=grade)

# Teacher Dashboard
@app.route('/dashboard/teacher')
def teacher_dashboard():
    if 'user_id' not in session or session.get('user_role') != 'teacher':
        return redirect(url_for('index'))
    
    user = UserProfile.query.get(session['user_id'])
    
    # Get teacher's assignments
    assignments = TeacherAssignment.query.filter_by(teacher_id=user.id).all()
    
    # Get students data for each assignment
    students_data = []
    for assignment in assignments:
        students = UserProfile.query.filter_by(
            role='student',
            school_udise=assignment.school_udise,
            grade=assignment.grade
        ).all()
        students_data.extend(students)
    
    return render_template('teacher_dashboard.html', user=user, students=students_data)

# API Routes for PWA
@app.route('/api/grades/<int:grade>/content')
def get_grade_content(grade):
    # Mock content data - in production, load from database
    content = {
        'grade': grade,
        'subjects': [
            {'id': 1, 'name': 'Mathematics', 'icon': '📊', 'color': '#4F46E5'},
            {'id': 2, 'name': 'Science', 'icon': '🔬', 'color': '#059669'},
            {'id': 3, 'name': 'English', 'icon': '📚', 'color': '#DC2626'},
            {'id': 4, 'name': 'Hindi', 'icon': '🇮🇳', 'color': '#EA580C'},
            {'id': 5, 'name': 'Social Studies', 'icon': '🌍', 'color': '#7C3AED'}
        ],
        'activities': [
            {'id': 1, 'title': 'Algebra Basics', 'subject': 'Mathematics', 'difficulty': 'Easy'},
            {'id': 2, 'title': 'Chemical Reactions', 'subject': 'Science', 'difficulty': 'Medium'}
        ]
    }
    return jsonify(content)

@app.route('/api/logs/', methods=['POST'])
def upload_logs():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    logs = data.get('logs', [])
    
    for log_data in logs:
        log = ActivityLog(
            student_id=session['user_id'],
            activity_id=log_data.get('activity_id'),
            skill_id=log_data.get('skill_id'),
            correct=log_data.get('correct'),
            time_spent_sec=log_data.get('time_spent_sec')
        )
        db.session.add(log)
    
    db.session.commit()
    return jsonify({'success': True, 'synced_logs': len(logs)})

# PWA Routes
@app.route('/manifest.json')
def manifest():
    return jsonify({
        'name': 'GAME RURAL INDIA',
        'short_name': 'GameRural',
        'description': 'Gamified Learning Platform for Rural Students',
        'start_url': '/',
        'display': 'standalone',
        'background_color': '#ffffff',
        'theme_color': '#4F46E5',
        'icons': [
            {
                'src': '/static/icons/icon-192x192.png',
                'sizes': '192x192',
                'type': 'image/png'
            },
            {
                'src': '/static/icons/icon-512x512.png',
                'sizes': '512x512',
                'type': 'image/png'
            }
        ]
    })

@app.route('/sw.js')
def service_worker():
    return app.send_static_file('sw.js')

# Initialize database and import UDISE data
def init_db():
    with app.app_context():
        db.create_all()
        
        # Import UDISE data if not already imported
        if UdiseSchool.query.count() == 0:
            import_udise_data()

def import_udise_data():
    """Import UDISE data from CSV file"""
    csv_path = 'backend/data/a.csv'
    if os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                school = UdiseSchool(
                    udise_code=row['UDISE_Code'],
                    school_name=row['School_Name'],
                    district=row['District'],
                    block=row['Block'],
                    category=row.get('Category', ''),
                    area=row.get('Area', ''),
                    management=row.get('Management', '')
                )
                db.session.add(school)
            
            db.session.commit()
            print(f"Imported {UdiseSchool.query.count()} schools from UDISE data")

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)

