import streamlit as st
import pandas as pd
import os
import io
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import hashlib
import uuid
from datetime import datetime
import sqlite3

# --- Streamlit Page Config ---
st.set_page_config(
    page_title="HireSense AI",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Database Setup ---
def init_db():
    """Initialize SQLite database with necessary tables"""
    conn = sqlite3.connect('Resume.db')
    c = conn.cursor()
    
    # Create users table
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        email TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        name TEXT,
        job_title TEXT,
        company TEXT,
        date_joined TEXT,
        last_login TEXT
    )
    ''')
    
    # Create ranking history table
    c.execute('''
    CREATE TABLE IF NOT EXISTS ranking_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        job_title TEXT,
        description TEXT,
        results TEXT,
        FOREIGN KEY (email) REFERENCES users (email)
    )
    ''')
    
    conn.commit()
    conn.close()

# --- Initialize Session State ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["user_email"] = None
    st.session_state["user_name"] = None
    st.session_state["profile_tab"] = "profile"
    st.session_state["current_page"] = "login"  # Default page: login, register, dashboard, profile

# --- Security Functions ---
def hash_password(password, salt=None):
    """Hash a password for storing."""
    if salt is None:
        salt = uuid.uuid4().hex
    hashed = hashlib.sha256(salt.encode() + password.encode()).hexdigest()
    return f"{salt}${hashed}"

def verify_password(stored_password, provided_password):
    """Verify a stored password against one provided by user"""
    salt, hashed = stored_password.split('$')
    return hashed == hashlib.sha256(salt.encode() + provided_password.encode()).hexdigest()

# --- User Management Functions ---
def save_user(email, password, name=""):
    """Registers a new user in the database."""
    conn = sqlite3.connect('Resume.db')
    c = conn.cursor()
    
    # Check if user exists
    c.execute("SELECT email FROM users WHERE email = ?", (email,))
    if c.fetchone():
        conn.close()
        return False  # User already exists
    
    # Hash the password
    hashed_password = hash_password(password)
    
    # Create new user with timestamp
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)",
        (email, hashed_password, name, "", "", current_date, current_date)
    )
    
    conn.commit()
    conn.close()
    return True

def authenticate_user(email, password):
    """Authenticate a user with email and password."""
    conn = sqlite3.connect('Resume.db')
    c = conn.cursor()
    
    c.execute("SELECT password FROM users WHERE email = ?", (email,))
    result = c.fetchone()
    
    if not result:
        conn.close()
        return False
    
    stored_password = result[0]
    
    if verify_password(stored_password, password):
        # Update last login time
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("UPDATE users SET last_login = ? WHERE email = ?", (current_date, email))
        conn.commit()
        conn.close()
        return True
    
    conn.close()
    return False

def update_profile(email, name, job_title, company):
    """Update user profile information."""
    conn = sqlite3.connect('Resume.db')
    c = conn.cursor()
    
    c.execute(
        "UPDATE users SET name = ?, job_title = ?, company = ? WHERE email = ?",
        (name, job_title, company, email)
    )
    
    conn.commit()
    conn.close()
    return True

def get_user_profile(email):
    """Get user profile data."""
    conn = sqlite3.connect('Resume.db')
    c = conn.cursor()
    
    c.execute(
        "SELECT email, name, job_title, company, date_joined, last_login FROM users WHERE email = ?",
        (email,)
    )
    
    result = c.fetchone()
    conn.close()
    
    if not result:
        return None
    
    return {
        "email": result[0],
        "name": result[1],
        "job_title": result[2],
        "company": result[3],
        "date_joined": result[4],
        "last_login": result[5]
    }

def change_password(email, current_password, new_password):
    """Change user password."""
    conn = sqlite3.connect('Resume.db')
    c = conn.cursor()
    
    c.execute("SELECT password FROM users WHERE email = ?", (email,))
    result = c.fetchone()
    
    if not result:
        conn.close()
        return False, "User not found"
    
    stored_password = result[0]
    
    if not verify_password(stored_password, current_password):
        conn.close()
        return False, "Current password is incorrect"
    
    # Hash the new password
    hashed_password = hash_password(new_password)
    
    # Update password
    c.execute("UPDATE users SET password = ? WHERE email = ?", (hashed_password, email))
    conn.commit()
    conn.close()
    
    return True, "Password changed successfully"

# --- Resume History Functions ---
def save_ranking_history(email, job_title, description, results):
    """Save resume ranking history for the user."""
    conn = sqlite3.connect('Resume.db')
    c = conn.cursor()
    
    # Create new history entry
    c.execute(
        "INSERT INTO ranking_history (email, timestamp, job_title, description, results) VALUES (?, ?, ?, ?, ?)",
        (
            email,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            job_title,
            description,
            results.to_json()
        )
    )
    
    conn.commit()
    conn.close()

def get_user_history(email):
    """Get resume ranking history for the user."""
    conn = sqlite3.connect('Resume.db')
    
    # Get all history records for the user
    query = "SELECT id, timestamp, job_title, description, results FROM ranking_history WHERE email = ? ORDER BY timestamp DESC"
    history_df = pd.read_sql_query(query, conn, params=(email,))
    
    conn.close()
    
    return history_df

# --- Resume Processing Functions ---
def extract_text_from_pdf(file):
    """Extracts text from an uploaded PDF file."""
    try:
        pdf = PdfReader(file)
        text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip() if text else "No readable text found."
    except Exception as e:
        return f"Error extracting text: {str(e)}"

def rank_resumes(job_description, resumes):
    """Ranks resumes based on their similarity to the job description."""
    documents = [job_description] + resumes
    vectorizer = TfidfVectorizer().fit_transform(documents)
    vectors = vectorizer.toarray()
    job_description_vector = vectors[0]
    resume_vectors = vectors[1:]
    cosine_similarities = cosine_similarity([job_description_vector], resume_vectors).flatten()
    return cosine_similarities


# Add custom CSS for better styling
st.markdown("""
    <style>
        .stButton>button {
            background-color: #1e90ff;
            color: white;
            font-size: 16px;
            border-radius: 5px;
            padding: 10px;
            transition: background-color 0.3s ease;
        }
        .stButton>button:hover {
            background-color: #4682b4;
        }
        .sidebar .sidebar-content {
            padding: 20px;
        }
        .stTextInput>div>div>input {
            font-size: 16px;
            border-radius: 5px;
        }
        .stTextArea>div>div>textarea {
            font-size: 16px;
            border-radius: 5px;
        }
        .stTabs>div>div>button {
            font-size: 18px;
            font-weight: bold;
            color: #1e90ff;
        }
        .stTabs>div>div>button:hover {
            color: #4682b4;
        }
        .stExpander>div>div>button {
            font-size: 16px;
            font-weight: bold;
            color: #1e90ff;
        }
    </style>
""", unsafe_allow_html=True)

# --- Main Navigation --- 
def show_login_page():
    st.sidebar.title("📝 User Login")
    st.sidebar.markdown("### Please enter your credentials to login.")
    
    login_email = st.sidebar.text_input("📧 Email", key="login_email", placeholder="Enter your email")
    login_password = st.sidebar.text_input("🔑 Password", type="password", key="login_password", placeholder="Enter your password")
    
    st.sidebar.markdown("---")
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if st.button("🔐 Login", use_container_width=True):
            if authenticate_user(login_email, login_password):
                st.session_state["authenticated"] = True
                st.session_state["user_email"] = login_email
                profile = get_user_profile(login_email)
                st.session_state["user_name"] = profile["name"]
                st.session_state["current_page"] = "dashboard"
                st.rerun()
            else:
                st.sidebar.error("❌ Invalid email or password")
    
    with col2:
        if st.button("📝 Register", use_container_width=True):
            st.session_state["current_page"] = "register"
            st.rerun()

def show_register_page():
    st.sidebar.title("📝 User Registration")
    st.sidebar.markdown("### Create a new account to get started.")
    
    reg_email = st.sidebar.text_input("📧 Email*", key="reg_email", placeholder="Enter your email")
    reg_name = st.sidebar.text_input("👤 Full Name", key="reg_name", placeholder="Enter your full name")
    reg_password = st.sidebar.text_input("🔑 Password*", type="password", key="reg_password", placeholder="Enter your password")
    reg_confirm_password = st.sidebar.text_input("🔑 Confirm Password*", type="password", key="reg_confirm_password", placeholder="Confirm your password")
    
    st.sidebar.markdown("---")
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if st.button("✅ Register", use_container_width=True):
            if not reg_email or not reg_password:
                st.sidebar.error("❌ Email and password are required")
            elif "@" not in reg_email or "." not in reg_email:
                st.sidebar.error("❌ Invalid email format")
            elif reg_password != reg_confirm_password:
                st.sidebar.error("❌ Passwords do not match")
            else:
                if save_user(reg_email, reg_password, reg_name):
                    st.sidebar.success("✅ Registration successful! You can now log in.")
                    st.session_state["current_page"] = "login"
                    st.rerun()
                else:
                    st.sidebar.warning("⚠ Email already registered. Please log in instead.")
                    st.session_state["current_page"] = "login"
                    st.rerun()
    
    with col2:
        if st.button("↩️ Back to Login", use_container_width=True):
            st.session_state["current_page"] = "login"
            st.rerun()

def show_profile_page():
    st.title("👤 User Profile")
    st.markdown("### Manage your profile information and preferences.")
    
    profile = get_user_profile(st.session_state["user_email"])
    if not profile:
        st.error("❌ Error loading profile data")
        return
    
    # Profile tabs
    profile_tab, password_tab, history_tab = st.tabs(["✏️ Edit Profile", "🔐 Change Password", "📊 History"])
    
    with profile_tab:
        st.subheader("Personal Information")
        
        name = st.text_input("Full Name", value=profile["name"] if profile["name"] else "")
        job_title = st.text_input("Job Title", value=profile["job_title"] if profile["job_title"] else "")
        company = st.text_input("Company", value=profile["company"] if profile["company"] else "")
        
        if st.button("💾 Save Profile"):
            if update_profile(profile["email"], name, job_title, company):
                st.session_state["user_name"] = name
                st.success("✅ Profile updated successfully!")
                st.rerun()
            else:
                st.error("❌ Error updating profile")
    
    with password_tab:
        st.subheader("Change Password")
        
        current_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password")
        confirm_new_password = st.text_input("Confirm New Password", type="password")
        
        if st.button("🔄 Update Password"):
            if not current_password or not new_password or not confirm_new_password:
                st.error("❌ All fields are required")
            elif new_password != confirm_new_password:
                st.error("❌ New passwords do not match")
            else:
                success, message = change_password(profile["email"], current_password, new_password)
                if success:
                    st.success(f"✅ {message}")
                else:
                    st.error(f"❌ {message}")
    
    with history_tab:
        st.subheader("Resume Ranking History")
        
        history = get_user_history(profile["email"])
        if history.empty:
            st.info("📝 No ranking history found")
        else:
            for idx, row in history.iterrows():
                with st.expander(f"Job: {row['job_title']} - {row['timestamp']}"):
                    st.text_area("Job Description", value=row["description"], height=100, disabled=True, key=f"job_desc_{idx}")
        try:
            results = pd.read_json(row["results"])
            st.dataframe(results, hide_index=True)
        except:
            st.warning("⚠ Error loading results data")



def show_dashboard():
    welcome_name = st.session_state["user_name"] or st.session_state["user_email"]

    # Title with gradient effect using HTML
    st.markdown("""
        <h2 style="
            background: -webkit-linear-gradient(45deg, #1FA2FF, #12D8FA);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
            text-align: center;
            font-size: 2.5rem;">
            🚀 Welcome to HireSense AI
        </h2>
    """, unsafe_allow_html=True)

    st.markdown(f"<div style='text-align:center; font-size:18px;'>Welcome back, <b style='color:#4CAF50'>{welcome_name}</b> 👋</div>", unsafe_allow_html=True)
    st.markdown("### ")

    # --- Job Information Section ---
    with st.container():
        st.subheader("📄 Job Information")
        st.markdown("Fill in the job details to start screening candidates.")
        job_title = st.text_input("Job Title", placeholder="e.g., Trainee Engineer", label_visibility="visible")

    st.markdown("---")

    # --- Job Description & Resume Upload ---
    st.subheader("📋 Job Description & 📂 Resume Upload")

    col1, col2 = st.columns([1.2, 1])

    with col1:
        job_description = st.text_area(
            "Job Description",
            placeholder="Paste or write the full job description here...",
            height=220,
            key="job_desc"
        )

    with col2:
        st.markdown("#### Upload Resumes")
        uploaded_files = st.file_uploader(
            "Select PDF resumes",
            type=["pdf"],
            accept_multiple_files=True,
            key="resume_files"
        )

        if uploaded_files:
            st.success(f"✅ {len(uploaded_files)} resume(s) uploaded successfully")

    st.markdown("---")

    # Optional: Next step / action button
    st.markdown("### Ready to rank candidates?")

    # --- Processing & Ranking ---
    if st.button("🔍 Rank Resumes", disabled=not (uploaded_files and job_description)):
        with st.spinner("🔍 Processing resumes..."):
            resumes = []
            file_names = []
            error_files = []
            
            # Process each resume
            for file in uploaded_files:
                text = extract_text_from_pdf(file)
                if "Error extracting text" in text:
                    error_files.append(file.name)
                else:
                    resumes.append(text)
                    file_names.append(file.name)
            
            if error_files:
                st.warning(f"⚠ Could not process {len(error_files)} files: {', '.join(error_files)}")
            
            if resumes:
                scores = rank_resumes(job_description, resumes)
                ranked_resumes = sorted(zip(file_names, scores), key=lambda x: x[1], reverse=True)
                
                # Create results dataframe
                results_df = pd.DataFrame({
                    "Rank": range(1, len(ranked_resumes) + 1),
                    "Resume Name": [name for name, _ in ranked_resumes],
                    "Match Score": [f"{round(score * 100, 1)}%" for _, score in ranked_resumes],
                    "Raw Score": [round(score, 4) for _, score in ranked_resumes]
                })
                
                # Display results
                st.subheader("🏆 Ranked Resumes")
                st.dataframe(results_df.drop(columns=["Raw Score"]), hide_index=True)
                
                # Visualize top candidates
                st.subheader("📊 Top Candidates Visualization")
                top_n = min(len(results_df), 10)  # Show top 10 or all if less than 10
                chart_data = results_df.head(top_n).copy()
                st.bar_chart(chart_data.set_index("Resume Name")["Raw Score"])
                
                # Save ranking history
                save_ranking_history(
                    st.session_state["user_email"],
                    job_title if job_title else "Unnamed Job",
                    job_description,
                    results_df
                )
                
                # Download options
                col1, col2 = st.columns(2)
                with col1:
                    csv = results_df.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Download CSV", csv, "ranked_resumes.csv", "text/csv")
                with col2:
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        results_df.to_excel(writer, index=False)
                    buffer.seek(0)
                    st.download_button("📥 Download Excel", buffer, "ranked_resumes.xlsx", 
                                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.error("❌ No valid resumes to process")

# --- App Sidebar ---
def render_sidebar():
    st.sidebar.markdown("""
<h2 style="
    text-align: center;
    font-weight: bold;
    font-size: 48px;
    background: linear-gradient(90deg, #4CAF50, #2196F3);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
">
    HireSense AI
</h2>
                        """, unsafe_allow_html=True)
    
    if st.session_state["authenticated"]:
        st.sidebar.subheader(f"👤 {st.session_state['user_email']}")
        
        # Navigation
        st.sidebar.markdown("---")
        st.sidebar.subheader("📱 Navigation")
        
        if st.sidebar.button("🏠 Dashboard", use_container_width=True):
            st.session_state["current_page"] = "dashboard"
            st.rerun()
            
        if st.sidebar.button("👤 My Profile", use_container_width=True):
            st.session_state["current_page"] = "profile"
            st.rerun()
            
        # Logout Button
        st.sidebar.markdown("---")
        if st.sidebar.button("🚪 Logout", use_container_width=True):
            st.session_state["authenticated"] = False
            st.session_state["user_email"] = None
            st.session_state["user_name"] = None
            st.session_state["current_page"] = "login"
            st.sidebar.success("👋 Logged out successfully!")
            st.rerun()

# --- Global Footer (outside sidebar) ---
def render_footer():
    st.markdown("""
        <style>
        .footer {
            position: fixed;
            left: 0;
            bottom: 0;
            width: 100%;
            background-color: #f1f1f1;
            color: #555;
            text-align: center;
            padding: 10px 0;
            font-size: 14px;
            border-top: 1px solid #ccc;
        }
        </style>
        <div class="footer">
            © 2025 AI HireSense AI
        </div>
    """, unsafe_allow_html=True)


# --- Main App Logic ---
def main():
    # Initialize database
    init_db()
    
    render_sidebar()
    
    if not st.session_state.get("authenticated", False):
        # Landing page for unauthenticated users
        st.markdown("""
<h1 style='
    text-align: left;
    font-weight: bold;
    font-size: 48px;
    background: linear-gradient(90deg, #4CAF50, #2196F3);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
'>
📄 Welcome to HireSense AI
</h1>
""", unsafe_allow_html=True)
        st.subheader("Your AI-powered hiring assistant")

        st.markdown("""
        ### 🚀 Why Use HireSense AI?
        - 🔍 **Intelligent Resume Matching**: Find candidates who truly match your job criteria.
        - ⚡ **Boost Efficiency**: Save hours of manual screening.
        - 📈 **Data-Driven Ranking**: Make fair, unbiased decisions.
        - 🧾 **Track & Compare**: Store ranking history for better long-term hiring strategy.
        """)

        # Advanced section
        st.markdown("### 🛠️ Advanced Features")
        st.markdown("""
        - 🧠 **AI-Powered Resume Parsing**
        - 📊 **Similarity Score Visualizations**
        - 💾 **Exportable Reports**
        - 🗂️ **Job Description Templates**
        - 🔐 **Secure User Profiles**
        """)

        st.markdown("---")

        # Layout for login/register
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.session_state["current_page"] == "login":
                show_login_page()
        with col2:
            if st.session_state["current_page"] == "register":
                show_register_page()
    
    else:
        # Authenticated pages
        if st.session_state["current_page"] == "dashboard":
            show_dashboard()
        elif st.session_state["current_page"] == "profile":
            show_profile_page()

if __name__ == "__main__":
    main()