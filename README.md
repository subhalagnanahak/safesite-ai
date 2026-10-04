# 🦺 Autonomous Workers Safety System for On-Site Hazard Prevention  

## 📌 Overview  
This project is a **Final Year Project (FYP)** for BSCS, focusing on construction site safety using **AI, Computer Vision, and Robotics**.  

The system integrates **YOLOv8 for PPE detection**, **facial recognition for attendance tracking**, and a **Arduino-based autonomous patrolling robot** to monitor construction sites. It stores attendance, violation logs, and analytics in an **SQLite database** with a **Flask-based web dashboard** for visualization and management.  

---

## ✨ Key Features  
- **🔍 PPE Detection (YOLOv8)** – Detects helmets, vests, and other PPE in real-time.  
- **🧑‍🤝‍🧑 Facial Recognition Attendance** – Automates employee attendance marking.  
- **🤖 Autonomous Patrolling Robot (Arduino)** – Patrols the site, captures video, and detects hazards.  
- **📊 Web Dashboard (Flask + HTML Templates)** – Displays analytics, attendance, violations, employee details, and salary reports.  
- **🗄️ Database (SQLite)** – Stores attendance logs, PPE violations, and employee records.  
- **📷 Violation Evidence** – Captures and stores images of violations in `/static/violation_images`.  

---

## 📂 Project Structure  
```
Autonomous-Workers-Safety-System/
│
├── Notebook/
│   └── Construction_Site_Workers_PPE_Detection.ipynb   # Training/Testing Notebook
│
├── Path memorizer robot/
│   ├── path_memorizer arduino code/
│   │   └── path_memorizer.ino                          # Arduino code for robot
│   └── Circuit diagram.jpg                             # Robot wiring diagram
│
├── Results/                                            # Model results & evaluation
│
├── static/                                             # Static assets
│   ├── employees_faces/                                # Employee face dataset
│   ├── images/                                         # General images
│   ├── models/                                         # Trained YOLOv8 models
│   ├── reports/                                        # Reports & charts
│   └── violation_images/                               # Captured violation evidence
│
├── templates/                                          # Flask HTML templates
│   ├── about.html
│   ├── add_employee.html
│   ├── analytics.html
│   ├── attendance.html
│   ├── base.html
│   ├── detection.html
│   ├── employees.html
│   ├── index.html
│   ├── salary_details.html
│   └── violations.html
│
├── app.py                                              # Flask app entry point
├── requirements.txt                                    # Python dependencies
├── safety_system.db                                    # SQLite database
├── LICENSE
└── README.md
```

---

## ⚙️ Installation & Setup  

### 1️⃣ Clone the Repository  
```bash
git clone https://github.com/username/autonomous-safety-system.git
cd autonomous-safety-system
```

### 2️⃣ Create Virtual Environment (Optional but Recommended)  
```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows
```

### 3️⃣ Install Dependencies  
```bash
pip install -r requirements.txt
```

### 4️⃣ Run the Flask Web App  
```bash
python app.py
```
Now open **http://127.0.0.1:5000/** in your browser.  

---

## 🖥️ Web Dashboard Pages  
- **Home (`index.html`)** – Overview of the system.  
- **Add Employee (`add_employee.html`)** – Register new workers.  
- **Attendance (`attendance.html`)** – View daily attendance logs.  
- **Analytics (`analytics.html`)** – Charts and reports of safety compliance.  
- **Detection (`detection.html`)** – Real-time PPE detection stream.  
- **Violations (`violations.html`)** – List of recorded violations with evidence.  
- **Employees (`employees.html`)** – Employee database.  
- **Salary Details (`salary_details.html`)** – Worker salary/attendance report.  

---

## 🛠️ Technologies Used  
- **Computer Vision:** YOLOv8, OpenCV, Face Recognition  
- **Backend:** Flask (Python)  
- **Database:** SQLite  
- **Frontend:** HTML, CSS (Flask templates)  
- **Robotics:** Arduino 
- **Programming:** Python, Arduino C  

---

## 📈 Results & Reports  
- Real-time detection accuracy using **YOLOv8**.  
- Attendance tracking via facial recognition.  
- Violation images captured & stored for audits.  
- Reports generated and displayed in **analytics dashboard**.  

---

## 🚀 Future Scope  
- Cloud integration for large-scale deployment.  
- IoT sensors for hazard detection (fire, gas leaks).  
- SMS/Email alerts for violations.  
- Multi-robot patrolling.  

---

## 👨‍💻 Author  
**Ahmed Islam**  
BSCS – Final Year Project  

---

🔥 If you like this project, don’t forget to **⭐ star the repository** and **share with others**!  
