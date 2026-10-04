from flask import Flask, render_template, request, redirect, url_for, flash, Response, jsonify
import cv2
import sqlite3
import os
import time
import numpy as np
from datetime import datetime, timedelta
import threading
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from werkzeug.utils import secure_filename
import shutil
import base64
from PIL import Image
import io

# Try importing YOLO - handle graceful fallback for demonstration
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("YOLO not available, using placeholder detection")

# Configuration
CONFIG = {
    'model_path': 'static/models/best.pt',
    'faces_dir': 'static/employees_faces',
    'required_gear': ['helmet', 'vest', 'gloves', 'boots'],
    'violation_deduction': 100,  # Amount in rupees to deduct per violation
    'confidence_threshold': 0.5,
    'db_path': 'safety_system.db'
}

# Create directories if they don't exist
os.makedirs(CONFIG['faces_dir'], exist_ok=True)
os.makedirs('static/reports', exist_ok=True)
os.makedirs('static/violation_images', exist_ok=True)
os.makedirs(os.path.dirname(CONFIG['model_path']), exist_ok=True)

app = Flask(__name__)
app.secret_key = 'safety_monitoring_system_secret_key'

# Global variables
camera = None
detection_active = False
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
global_frame = None

# Load YOLO model if available
if YOLO_AVAILABLE:
    try:
        model = YOLO(CONFIG['model_path'])
    except Exception as e:
        model = None
        print(f"Error loading YOLO model: {e}")
else:
    model = None

# Database setup
def setup_database():
    conn = sqlite3.connect(CONFIG['db_path'])
    c = conn.cursor()
    
    # Employees table
    c.execute('''
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        position TEXT,
        join_date TEXT,
        salary REAL,
        image_path TEXT
    )
    ''')
    
    # Violations table
    c.execute('''
    CREATE TABLE IF NOT EXISTS violations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_name TEXT,
        violation_type TEXT,
        timestamp TEXT,
        image_path TEXT,
        severity INTEGER DEFAULT 1,
        acknowledged BOOLEAN DEFAULT 0
    )
    ''')
    
    # Attendance table
    c.execute('''
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_name TEXT,
        date TEXT,
        time_in TEXT,
        time_out TEXT,
        status TEXT
    )
    ''')
    
    # Drop existing salary_deductions table if it exists
    c.execute('DROP TABLE IF EXISTS salary_deductions')
    
    # Create new salary_deductions table with updated structure
    c.execute('''
    CREATE TABLE IF NOT EXISTS salary_deductions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_name TEXT,
        date TEXT,
        amount REAL,
        reason TEXT,
        base_salary REAL,
        remaining_salary REAL
    )
    ''')
    
    # Analytics table
    c.execute('''
    CREATE TABLE IF NOT EXISTS analytics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        total_detections INTEGER,
        violations INTEGER,
        compliance_rate REAL
    )
    ''')
    
    conn.commit()
    return conn

# Initialize database
setup_database()

# Load known faces
def load_known_faces():
    known_faces = []
    known_names = []
    
    if not os.path.exists(CONFIG['faces_dir']):
        return [], []
    
    for filename in os.listdir(CONFIG['faces_dir']):
        if filename.endswith('.jpg') or filename.endswith('.png'):
            name = os.path.splitext(filename)[0]
            image_path = os.path.join(CONFIG['faces_dir'], filename)
            face_image = cv2.imread(image_path)
            
            if face_image is not None:
                known_faces.append(face_image)
                known_names.append(name)
    
    return known_faces, known_names

# Simple face recognition function
def recognize_face(frame, known_faces, known_names):
    if not known_faces or not known_names:
        return None, None
    
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    
    if len(faces) == 0:
        return None, None
    
    for (x, y, w, h) in faces:
        face_roi = frame[y:y+h, x:x+w]
        
        if face_roi.size == 0:
            continue
            
        # Resize for consistent comparison
        try:
            face_roi = cv2.resize(face_roi, (100, 100))
        except:
            continue
        
        best_match_index = -1
        best_match_score = float('inf')
        
        for i, known_face in enumerate(known_faces):
            try:
                # Resize known face to match face_roi
                resized_known_face = cv2.resize(known_face, (100, 100))
                # Calculate Mean Squared Error for simple comparison
                difference = cv2.absdiff(face_roi, resized_known_face)
                diff_score = np.sum(difference**2)
                
                if diff_score < best_match_score:
                    best_match_score = diff_score
                    best_match_index = i
            except:
                continue
        
        # Set a threshold for recognition
        if best_match_index != -1 and best_match_score < 150000000:  # This threshold needs calibration
            return known_names[best_match_index], (x, y, w, h)
    
    return None, None

# Record employee attendance
def record_attendance(employee_name):
    conn = sqlite3.connect(CONFIG['db_path'])
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M:%S")
    
    # Check if attendance record exists for today
    c.execute('SELECT * FROM attendance WHERE employee_name = ? AND date = ?', (employee_name, today))
    exists = c.fetchone()
    
    if exists:
        # Update time_out for existing record
        c.execute('UPDATE attendance SET time_out = ? WHERE employee_name = ? AND date = ?',
                 (current_time, employee_name, today))
    else:
        # Create new attendance record
        c.execute('INSERT INTO attendance (employee_name, date, time_in, status) VALUES (?, ?, ?, ?)',
                 (employee_name, today, current_time, 'present'))
    
    conn.commit()
    conn.close()

# Record violation in the database
def record_violation(employee_name, violation_type, frame):
    conn = sqlite3.connect(CONFIG['db_path'])
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Save violation image
    image_path = f"static/violation_images/{employee_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    cv2.imwrite(image_path, frame)
    
    # Insert violation record
    c.execute('''
    INSERT INTO violations (employee_name, violation_type, timestamp, image_path)
    VALUES (?, ?, ?, ?)
    ''', (employee_name, violation_type, timestamp, image_path))
    
    # Check if deduction already exists for this employee today
    c.execute('''
    SELECT COUNT(*) FROM salary_deductions 
    WHERE employee_name = ? AND date = ?
    ''', (employee_name, today))
    
    if c.fetchone()[0] == 0:  # No deduction yet for today
        # Get employee's current salary
        c.execute('SELECT salary FROM employees WHERE name = ?', (employee_name,))
        result = c.fetchone()
        if result:
            current_salary = result[0]
            deduction_amount = CONFIG['violation_deduction']
            remaining_salary = current_salary - deduction_amount
            
            # Insert salary deduction record
            c.execute('''
            INSERT INTO salary_deductions (employee_name, date, amount, reason, base_salary, remaining_salary)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (employee_name, today, deduction_amount, f"Safety violation: {violation_type}", 
                  current_salary, remaining_salary))
    
    conn.commit()
    conn.close()

# Update analytics data
def update_analytics(detected=0, violated=0):
    conn = sqlite3.connect(CONFIG['db_path'])
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Check if analytics entry exists for today
    c.execute('SELECT * FROM analytics WHERE date = ?', (today,))
    exists = c.fetchone()
    
    compliance_rate = 0
    if detected > 0:
        compliance_rate = round(((detected - violated) / detected) * 100, 2)
    
    if exists:
        # Update existing record
        c.execute('''
        UPDATE analytics 
        SET total_detections = total_detections + ?,
            violations = violations + ?,
            compliance_rate = (total_detections - violations) * 100.0 / total_detections
        WHERE date = ?
        ''', (detected, violated, today))
    else:
        # Create new record
        c.execute('''
        INSERT INTO analytics (date, total_detections, violations, compliance_rate)
        VALUES (?, ?, ?, ?)
        ''', (today, detected, violated, compliance_rate))
    
    conn.commit()
    conn.close()

# Camera handling function
def generate_frames():
    global camera, global_frame
    known_faces, known_names = load_known_faces()
    
    if camera is None:
        camera = cv2.VideoCapture(0)  # Use 0 for default webcam
    
    while detection_active:
        success, frame = camera.read()
        if not success:
            break
        
        # Store a copy of the current frame for global access
        global_frame = frame.copy()
        
        # Process frame with safety detection if YOLO is available
        if model is not None and YOLO_AVAILABLE:
            # Recognize employee
            name, face_coords = recognize_face(frame, known_faces, known_names)
            
            # Run YOLO detection
            results = model(frame)
            
            # Track safety compliance
            person_detected = False
            safety_violation = False
            missing_gear = []
            
            # Check detected objects from YOLO
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    cls_name = model.names[cls_id]
                    
                    # Draw bounding box
                    color = (0, 255, 0)  # Green by default
                    
                    # If it's a person
                    if cls_name == 'person':
                        person_detected = True
                        
                        # Check if required gear is missing
                        detected_gear = [model.names[int(b.cls[0])] for b in boxes]
                        for gear in CONFIG['required_gear']:
                            if gear not in detected_gear:
                                missing_gear.append(gear)
                        
                        if missing_gear:
                            color = (0, 0, 255)  # Red for safety violation
                            safety_violation = True
                        
                        # Record attendance and violation if person is identified
                        if name:
                            # Draw face box and name
                            if face_coords:
                                fx, fy, fw, fh = face_coords
                                cv2.rectangle(frame, (fx, fy), (fx+fw, fy+fh), (255, 0, 0), 2)
                            
                            cv2.putText(frame, name, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)
                            
                            # Record attendance (only once per camera session)
                            record_attendance(name)
                            
                            # Record violation if safety gear is missing
                            if safety_violation:
                                violation_type = f"Missing: {', '.join(missing_gear)}"
                                record_violation(name, violation_type, frame)
                    
                    # Draw bounding box for detected object
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(frame, f"{cls_name}: {conf:.2f}", (x1, y1-10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            # Update analytics if person detected
            if person_detected:
                update_analytics(detected=1, violated=1 if safety_violation else 0)
            
            # Display safety status
            if person_detected:
                if safety_violation:
                    status = "SAFETY VIOLATION DETECTED"
                    status_color = (0, 0, 255)  # Red
                else:
                    status = "SAFETY COMPLIANT"
                    status_color = (0, 255, 0)  # Green
                
                cv2.putText(frame, status, (10, frame.shape[0] - 20), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        else:
            # Simple face recognition without YOLO
            name, face_coords = recognize_face(frame, known_faces, known_names)
            
            if name:
                if face_coords:
                    x, y, w, h = face_coords
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
                    cv2.putText(frame, name, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)
                
                # Record attendance
                record_attendance(name)
                
                # Display demo message since YOLO isn't available
                cv2.putText(frame, "Demo Mode: YOLO not available", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # Display current date and time
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, current_datetime, (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # Convert to JPEG for streaming
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

# Flask routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/detection')
def detection():
    return render_template('detection.html')

@app.route('/employees')
def employees():
    conn = sqlite3.connect(CONFIG['db_path'])
    employees_df = pd.read_sql_query("SELECT * FROM employees", conn)
    conn.close()
    
    employees_list = employees_df.to_dict('records')
    return render_template('employees.html', employees=employees_list)

@app.route('/check_employee_name')
def check_employee_name():
    name = request.args.get('name')
    conn = sqlite3.connect(CONFIG['db_path'])
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM employees WHERE name = ?", (name,))
    exists = c.fetchone()[0] > 0
    conn.close()
    return jsonify({'exists': exists})

@app.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        name = request.form['name']
        position = request.form['position']
        salary = request.form['salary']
        
        # Check if employee already exists
        conn = sqlite3.connect(CONFIG['db_path'])
        c = conn.cursor()
        c.execute("SELECT * FROM employees WHERE name = ?", (name,))
        if c.fetchone():
            flash('Employee already exists!')
            conn.close()
            return redirect(url_for('add_employee'))
        
        # Process the photo
        photo_data = request.form.get('photo')
        photo_file = request.files.get('photo_file')
        
        if photo_data or photo_file:
            filename = secure_filename(f"{name}.jpg")
            photo_path = os.path.join(CONFIG['faces_dir'], filename)
            
            if photo_data:  # Camera capture
                # Remove header from base64 data
                photo_data = photo_data.split(',')[1]
                image_bytes = base64.b64decode(photo_data)
                image = Image.open(io.BytesIO(image_bytes))
                image.save(photo_path)
            else:  # File upload
                photo_file.save(photo_path)
            
            # Insert employee into database
            join_date = datetime.now().strftime("%Y-%m-%d")
            c.execute('''
            INSERT INTO employees (name, position, join_date, salary, image_path)
            VALUES (?, ?, ?, ?, ?)
            ''', (name, position, join_date, salary, photo_path))
            
            conn.commit()
            flash('Employee added successfully!')
        else:
            flash('Photo is required!')
        
        conn.close()
        return redirect(url_for('employees'))
    
    return render_template('add_employee.html')

@app.route('/remove_employee/<int:employee_id>', methods=['POST'])
def remove_employee(employee_id):
    conn = sqlite3.connect(CONFIG['db_path'])
    c = conn.cursor()
    
    # Get employee info
    c.execute("SELECT name, image_path FROM employees WHERE id = ?", (employee_id,))
    employee = c.fetchone()
    
    if employee:
        name, image_path = employee
        
        # Delete employee from database
        c.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
        
        # Remove employee image
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
        
        conn.commit()
        flash(f'Employee "{name}" removed successfully!')
    else:
        flash('Employee not found!')
    
    conn.close()
    return redirect(url_for('employees'))

@app.route('/violations')
def violations():
    conn = sqlite3.connect(CONFIG['db_path'])
    violations_df = pd.read_sql_query("""
        SELECT v.*, e.position FROM violations v
        LEFT JOIN employees e ON v.employee_name = e.name
        ORDER BY timestamp DESC
    """, conn)
    conn.close()
    
    violations_list = violations_df.to_dict('records')
    return render_template('violations.html', violations=violations_list)

@app.route('/attendance')
def attendance():
    conn = sqlite3.connect(CONFIG['db_path'])
    attendance_df = pd.read_sql_query("""
        SELECT a.*, e.position FROM attendance a
        LEFT JOIN employees e ON a.employee_name = e.name
        ORDER BY date DESC, time_in DESC
    """, conn)
    conn.close()
    
    attendance_list = attendance_df.to_dict('records')
    return render_template('attendance.html', attendance=attendance_list)

@app.route('/salary_deductions')
def salary_deductions():
    conn = sqlite3.connect(CONFIG['db_path'])
    deductions_df = pd.read_sql_query("""
        SELECT sd.*, e.salary FROM salary_deductions sd
        LEFT JOIN employees e ON sd.employee_name = e.name
        ORDER BY date DESC
    """, conn)
    conn.close()
    
    deductions_list = deductions_df.to_dict('records')
    return render_template('salary_deductions.html', deductions=deductions_list)

@app.route('/analytics')
def analytics():
    conn = sqlite3.connect(CONFIG['db_path'])
    
    # Get overall stats
    analytics_df = pd.read_sql_query("""
        SELECT a.*, 
               (SELECT COUNT(CASE WHEN status = 'present' THEN 1 END) * 100.0 / COUNT(*)
                FROM attendance 
                WHERE date = a.date) as attendance_rate
        FROM analytics a
        ORDER BY date DESC
    """, conn)
    
    # Get employee count
    employees_count = int(pd.read_sql_query("SELECT COUNT(*) as count FROM employees", conn).iloc[0]['count'])
    
    # Calculate compliance rate
    if not analytics_df.empty:
        compliance_rate = round(float(analytics_df['compliance_rate'].mean()), 2)
    else:
        compliance_rate = 0
    
    # Get total violations
    total_violations = int(pd.read_sql_query("SELECT COUNT(*) as count FROM violations", conn).iloc[0]['count'])
    
    # Calculate average attendance
    attendance_stats = pd.read_sql_query("""
        SELECT 
            COUNT(CASE WHEN status = 'present' THEN 1 END) * 100.0 / COUNT(*) as attendance_rate
        FROM attendance
    """, conn)
    avg_attendance = round(float(attendance_stats.iloc[0]['attendance_rate']), 2) if not attendance_stats.empty else 0
    
    # Get violation types
    violation_types = pd.read_sql_query("""
        SELECT violation_type, COUNT(*) as count
        FROM violations
        GROUP BY violation_type
        ORDER BY count DESC
    """, conn)
    
    # Get top violators
    top_violators = pd.read_sql_query("""
        SELECT employee_name, COUNT(*) as violation_count
        FROM violations
        GROUP BY employee_name
        ORDER BY violation_count DESC
        LIMIT 5
    """, conn)
    
    # Get attendance distribution
    attendance_dist = pd.read_sql_query("""
        SELECT 
            COUNT(CASE WHEN status = 'present' THEN 1 END) as present,
            COUNT(CASE WHEN status = 'absent' THEN 1 END) as absent,
            COUNT(CASE WHEN status = 'late' THEN 1 END) as late
        FROM attendance
    """, conn)
    
    conn.close()
    
    # Prepare data for charts
    dates = analytics_df['date'].tolist() if not analytics_df.empty else []
    compliance_rates = [float(x) for x in analytics_df['compliance_rate'].tolist()] if not analytics_df.empty else []
    violation_types_list = violation_types['violation_type'].tolist() if not violation_types.empty else []
    violation_counts = [int(x) for x in violation_types['count'].tolist()] if not violation_types.empty else []
    top_violators_names = top_violators['employee_name'].tolist() if not top_violators.empty else []
    top_violators_counts = [int(x) for x in top_violators['violation_count'].tolist()] if not top_violators.empty else []
    
    # Prepare attendance distribution
    if not attendance_dist.empty:
        attendance_distribution = [
            int(attendance_dist.iloc[0]['present']),
            int(attendance_dist.iloc[0]['absent']),
            int(attendance_dist.iloc[0]['late'])
        ]
    else:
        attendance_distribution = [0, 0, 0]
    
    return render_template('analytics.html',
                         analytics=analytics_df.to_dict('records'),
                         employees_count=employees_count,
                         compliance_rate=compliance_rate,
                         total_violations=total_violations,
                         avg_attendance=avg_attendance,
                         dates=dates,
                         compliance_rates=compliance_rates,
                         violation_types=violation_types_list,
                         violation_counts=violation_counts,
                         top_violators_names=top_violators_names,
                         top_violators_counts=top_violators_counts,
                         attendance_distribution=attendance_distribution)

@app.route('/video_feed')
def video_feed():
    global detection_active
    detection_active = True
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start_detection')
def start_detection():
    global detection_active
    detection_active = True
    return jsonify({'status': 'started'})

@app.route('/stop_detection')
def stop_detection():
    global detection_active, camera
    detection_active = False
    if camera:
        camera.release()
        camera = None
    return jsonify({'status': 'stopped'})

@app.route('/capture_employee_photo', methods=['POST'])
def capture_employee_photo():
    global global_frame
    
    if global_frame is None:
        return jsonify({'success': False, 'message': 'No camera frame available'})
    
    # Convert frame to JPEG for display
    _, buffer = cv2.imencode('.jpg', global_frame)
    image_bytes = buffer.tobytes()
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    
    return jsonify({
        'success': True,
        'image': f'data:image/jpeg;base64,{image_base64}'
    })

@app.route('/take_snapshot', methods=['POST'])
def take_snapshot():
    data = request.json
    image_data = data.get('image')
    employee_name = data.get('name')
    
    if not image_data or not employee_name:
        return jsonify({'success': False, 'message': 'Missing image data or employee name'})
    
    try:
        # Remove header from base64 data
        image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)
        
        # Convert to image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Save to file
        filename = secure_filename(f"{employee_name}.jpg")
        file_path = os.path.join(CONFIG['faces_dir'], filename)
        image.save(file_path)
        
        return jsonify({'success': True, 'message': 'Image saved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error saving image: {str(e)}'})

@app.route('/about')
def about():
    return render_template('about.html')

# Add this after the app initialization
@app.template_filter('to_datetime')
def to_datetime(value):
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%H:%M:%S")
        except ValueError:
            return None
    return value

@app.route('/salary_details')
def salary_details():
    conn = sqlite3.connect(CONFIG['db_path'])
    
    # Get detailed salary information with deductions
    salary_details = pd.read_sql_query("""
        SELECT 
            e.name as employee_name,
            e.salary as base_salary,
            COALESCE(sd.amount, 0) as deduction_amount,
            CASE 
                WHEN sd.remaining_salary IS NOT NULL THEN sd.remaining_salary
                ELSE e.salary
            END as remaining_salary,
            sd.date as deduction_date,
            sd.reason as deduction_reason
        FROM employees e
        LEFT JOIN salary_deductions sd ON e.name = sd.employee_name
        ORDER BY e.name, sd.date DESC
    """, conn)
    
    conn.close()
    
    # Convert to list of dictionaries for template
    salary_list = salary_details.to_dict('records')
    
    return render_template('salary_details.html', salary_details=salary_list)

if __name__ == '__main__':
    app.run(debug=True)