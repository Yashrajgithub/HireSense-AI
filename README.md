# 🤖 HireSense AI – Intelligent Resume Screening & Ranking System

## 📌 Overview  
**HireSense AI** is an intelligent recruitment tool that uses **AI and NLP** to automatically screen, evaluate, and rank resumes based on job-specific requirements. It helps recruiters identify the most suitable candidates with minimal effort.

## 🚀 Features  
- **📄 Resume Parsing** – Extracts skills, education, and experience from uploaded files.  
- **🧠 AI-Powered Scoring** – Evaluates resumes based on job-match relevance.  
- **📝 NLP Keyword Analysis** – Matches job description terms to resume content.  
- **⚡ Instant Shortlisting** – Displays top candidates automatically.  
- **📊 User Dashboard** – Shows ranked results with insights.  
- **🔧 Custom Filters** – Adjust scoring weights for different roles.

## 🛠️ Technologies Used  
- **Python** (Streamlit for frontend)  
- **SQLite** (Lightweight backend database)  
- **NLP** (spaCy, Scikit-learn)  
- **PDF Parsing** (PyMuPDF)  

## 📂 How It Works  
1. **Upload Resumes** – Drop PDF resumes into the uploader.  
2. **Job Input** – Enter job title and description.  
3. **Match & Score** – AI processes and ranks resumes.  
4. **Review Results** – See top candidates in the dashboard.

## 🎯 Use Cases  
✅ Recruiters hiring for tech and non-tech roles.  
✅ HR teams processing bulk applications.  
✅ Organizations adopting data-driven hiring.

## 📦 Installation  
### 🔹 Prerequisites  
- Python 3.8+  
- pip (Python package manager)  

### 🔹 Steps  
```bash
git clone https://github.com/Yashrajgithub/HireSense-AI.git
cd HireSense-AI  
pip install -r requirements.txt  
streamlit run app.py  
