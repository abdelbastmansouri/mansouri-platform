import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import time
import base64
import re  
import hashlib # مكتبة توليد البصمات الرقمية الفريدة للصور لمنع الغش

# --- 1. الإعدادات الأولية وإضفاء الطابع الاحترافي للوزارة ---
st.set_page_config(
    page_title="منصة ذ عبد الباسط منصوري", 
    layout="wide",
    page_icon="math🇲🇦"
)

# دالة الخلفية السحابية المحدثة
def get_custom_bg():
    return """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Amiri:ital,wght@0,400;0,700;1,400;1,700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"], .stApp {
        background-image: linear-gradient(to bottom, rgba(245, 247, 250, 0.94) 0%, rgba(240, 244, 248, 0.88) 100%), 
        url("https://drive.google.com/thumbnail?id=1qtyRtJXUvwJe8qd8HrkC_P7phD6MBiXe&sz=w1920") !important;
        background-size: cover !important;
        background-repeat: no-repeat !important;
        background-attachment: fixed !important;
    }
    
    * { font-family: 'Amiri', serif !important; }
    
    [data-testid="stHeader"] {
        background-color: rgba(255, 255, 255, 1) !important;
        background: white !important;
        border-bottom: 1px solid rgba(197, 160, 89, 0.3) !important;
    }
    
    .golden-title {
        color: #FFD700 !important;
        text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.7) !important;
        font-weight: bold !important;
        text-align: center;
    }
    
    .golden-sub {
        color: #F1C40F !important;
        text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.6) !important;
        text-align: center;
        font-size: 1.3rem !important;
    }
    
    .section-title {
        color: #C5A059 !important;
        font-weight: bold !important;
        font-size: 1.6rem !important;
        border-bottom: 2px solid #C5A059;
        padding-bottom: 5px;
        margin-bottom: 15px;
    }
    
    [data-testid="stSidebar"] { background-color: rgba(26, 54, 93, 0.98) !important; }
    [data-testid="stSidebar"] * { color: white !important; }
    
    .stSelectbox, .stTextInput, .metric-card, .stTextArea, div[data-testid="stExpander"], .stDateInput {
        background-color: rgba(255, 255, 255, 0.95) !important;
        backdrop-filter: blur(8px) !important;
        border-radius: 12px !important;
        border: 1px solid rgba(197, 160, 89, 0.4) !important;
    }

    h1, h2, h3, label, .stMarkdown p { 
        color: #ED7F10 !important; 
        font-weight: bold !important; 
    }
    
    .stButton>button {
        background-color: #1a365d !important; 
        color: #FFD700 !important;
        border-radius: 8px !important; 
        border: 1px solid #C5A059 !important;
        padding: 10px 24px !important;
        font-size: 1.2rem !important;
    }
    .stButton>button:hover {
        background-color: #C5A059 !important; 
        color: #1a365d !important;
    }
    
    .status-box {
        background-color: rgba(26, 54, 93, 0.05);
        border-right: 5px solid #10b981;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    </style>
    """

st.markdown(get_custom_bg(), unsafe_allow_html=True)

try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error("⚠️ لم يتم العثور على مفتاح 'GEMINI_API_KEY'.")

if 'auth' not in st.session_state: st.session_state.auth = False
if 'user' not in st.session_state: st.session_state.user = {}
if 'role' not in st.session_state: st.session_state.role = None

def get_gcp_credentials():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    
def get_gspread_client():
    return gspread.authorize(get_gcp_credentials())

def upload_pdf_to_drive(file_name, file_bytes):
    try:
        creds = get_gcp_credentials()
        drive_service = build('drive', 'v3', credentials=creds)
        SHARED_FOLDER_ID = "1SwrvnMPTYLPSiV4B3Lyr6TiDCpurx_24"
        file_metadata = {'name': file_name, 'parents': [SHARED_FOLDER_ID]}
        fh = io.BytesIO(file_bytes)
        media = MediaIoBaseUpload(fh, mimetype='application/pdf', resumable=True)
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink', supportsAllDrives=True).execute()
        return file.get('webViewLink')
    except:
        return "N/A"

def calculate_image_hash(file_bytes):
    return hashlib.md5(file_bytes).hexdigest()

# التخزين المؤقت لحل مشكلة الـ Quota
@st.cache_data(ttl=15)
def load_data():
    sh = None
    for attempt in range(4):
        try:
            client = get_gspread_client()
            sh = client.open("les classes")
            break
        except:
            if attempt == 3: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
            time.sleep(3)
            
    if sh is None: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    try:
        data_rows = sh.sheet1.get_all_values()
        if data_rows and len(data_rows) > 1:
            headers = [h.strip() for h in data_rows[0]]
            df_students = pd.DataFrame(data_rows[1:], columns=headers)
            df_students.columns = df_students.columns.str.strip()
            if "إسم التلميذ" in df_students.columns:
                df_students = df_students.rename(columns={"إسم التلميذ": "اسم التلميذ"})
        else:
            df_students = pd.DataFrame(columns=["رقم التلميذ", "اسم التلميذ", "تاريخ الإزدياد", "القسم"])
    except:
        df_students = pd.DataFrame(columns=["رقم التلميذ", "اسم التلميذ", "تاريخ الإزدياد", "القسم"])

    try:
        reports_worksheet = sh.worksheet("Reports")
        reports_rows = reports_worksheet.get_all_values()
        if reports_rows and len(reports_rows) > 1:
            reports_headers = [h.strip() for h in reports_rows[0]]
            df_reports = pd.DataFrame(reports_rows[1:], columns=reports_headers)
            
            df_reports.columns = df_reports.columns.str.strip()
            if "إسم" in df_reports.columns: df_reports = df_reports.rename(columns={"إسم": "الاسم"})
            if "اسم" in df_reports.columns: df_reports = df_reports.rename(columns={"اسم": "الاسم"})
            if "اسم التلميذ" in df_reports.columns: df_reports = df_reports.rename(columns={"اسم التلميذ": "الاسم"})
            if "إسم التلميذ" in df_reports.columns: df_reports = df_reports.rename(columns={"إسم التلميذ": "الاسم"})
        else:
            df_reports = pd.DataFrame(columns=["التاريخ", "الاسم", "القسم", "الدرس", "التقرير", "النسبة", "بصمات_الصور"])
    except:
        df_reports = pd.DataFrame(columns=["التاريخ", "الاسم", "القسم", "الدرس", "التقرير", "النسبة", "بصمات_الصور"])
        
    try:
        lessons_worksheet = sh.worksheet("Lessons")
        lessons_rows = lessons_worksheet.get_all_values()
        if lessons_rows and len(lessons_rows) > 1:
            lessons_headers = [h.strip() for h in lessons_rows[0]]
            df_lessons = pd.DataFrame(lessons_rows[1:], columns=lessons_headers)
            df_lessons.columns = df_lessons.columns.str.strip()
        else:
            df_lessons = pd.DataFrame(columns=["الدرس", "الملاحظات_المرجعية", "تاريخ_التحديث"])
    except:
        df_lessons = pd.DataFrame(columns=["الدرس", "الملاحظات_المرجعية", "تاريخ_التحديث"])
        
    return df_students, df_reports, df_lessons

df_students, df_reports, df_lessons = load_data()

def get_lesson_ref(lesson_name, df_lessons):
    DRIVE_LINKS = {
        "الدرس 1": "https://drive.google.com/file/d/1WiHUq1rTQPX-VdzKvB6BT50K_vP3ZaQt/view?usp=sharing",
        "الدرس 2": "https://drive.google.com/file/d/1XMLhrjUkjzTQuUYKqNGj-BslSFSztKyz/view?usp=sharing",
        "الدرس 3": "" 
    }
    clean_name = lesson_name.strip()
    if clean_name in DRIVE_LINKS and DRIVE_LINKS[clean_name] != "":
        return f"🔗 رابط ملف الدرس المرجعي الثابت المعتمد في Google Drive:\n{DRIVE_LINKS[clean_name]}"
    if not df_lessons.empty and "الدرس" in df_lessons.columns:
        clean_target = clean_name.replace(" ", "")
        for _, row in df_lessons.iterrows():
            clean_db_name = str(row["الدرس"]).strip().replace(" ", "")
            if clean_target in clean_db_name or clean_db_name in clean_target:
                return row["الملاحظات_المرجعية"]
    return "لا توجد ملاحظات مرجعية ثابتة محددة لهذا الدرس من طرف الأستاذ."

# --- القائمة الجانبية ---
with st.sidebar:
    st.markdown("""
        <div style='text-align: center; padding: 10px;'>
        <span style='font-size: 1.9rem;'>🎓</span>
        <h3 style='color: #FFD700 !important; font-size: 1.3rem; margin-top: 10px; text-shadow: 1px 1px 2px black;'>وزارة التربية الوطنية والتعليم الأولي والرياضة</h3>
            <p style='color: #cbd5e1 !important; font-size: 0.95rem;'>ثانوية الزرقطوني التأهيلية</p>
        </div>
    """, unsafe_allow_html=True)
    st.divider()
    
    if st.session_state.auth:
        user_display = st.session_state.user.get('name', 'المستخدم')
        st.success(f" مرحباً ب: \n\n**{user_display}**")
        if st.session_state.role == "student":
            st.info(f"🏫 القسم: {st.session_state.user.get('class')}")
        st.divider()
        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.cache_data.clear()
            st.rerun()
    else:
        menu = st.radio(label="اختر الفضاء المستهدف:", options=["فضاء التلميذات والتلاميذ", "فضاء الإدارة والأستاذ"])
        st.session_state.role = "student" if "التلميذ" in menu else "admin"

# --- واجهة الأستاذ ---
def admin_space(df_students, df_reports, df_lessons):
    st.markdown("""
        <div style='background: linear-gradient(#008E8E, #1a365d 0%, #C72C48 100%); padding: 30px; border-radius: 15px; margin-bottom: 25px; color: white; border: 2px solid #C5A059;'>
            <h1 class='golden-title' style='font-size: 2.3rem;'>👨‍🏫 الفضاء الرقمي للتدقيق الإداري والتربوي</h1>
            <p class='golden-sub'>مرحباً بك ذ.عبد الباسط منصوري - تتبع ذكي لمراقبة وتصحيح دفاتر التلاميذ</p>
        </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 لوحة الإحصائيات", "📂 إضافة ورفع الدروس المرجعية", "👥 تتبع سجلات التلاميذ", "⚙️ الإعدادات"])
    
    with tab1:
        st.markdown("<div class='section-title'>📈 المؤشرات التربوية العامة</div>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1: st.markdown(f"<div class='metric-card'><p style='color:#64748b; font-weight:bold;'>إجمالي التلاميذ</p><h2 style='margin:0; color:#1a365d;'>👥 {len(df_students)}</h2></div>", unsafe_allow_html=True)
        with col2: st.markdown(f"<div class='metric-card'><p style='color:#64748b; font-weight:bold;'>الدفاتر المدققة</p><h2 style='margin:0; color:#1a365d;'>📥 {len(df_reports)}</h2></div>", unsafe_allow_html=True)
        with col3: 
            num_classes = df_students['القسم'].nunique() if not df_students.empty and 'القسم' in df_students.columns else 0
            st.markdown(f"<div class='metric-card'><p style='color:#64748b; font-weight:bold;'>الأقسام</p><h2 style='margin:0; color:#1a365d;'>🏫 {num_classes}</h2></div>", unsafe_allow_html=True)
        
        if not df_reports.empty and 'القسم' in df_reports.columns:
            fig = px.bar(df_reports.groupby('القسم').size().reset_index(name='عدد الإرسالات'), x='القسم', y='عدد الإرسالات', title="📊 تفاعل الأقسام والالتزام بالدفاتر الرقمية", color_discrete_sequence=['#1a365d'])
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.markdown("<div class='section-title'>📂 مركز إدارة المراجع السحابية</div>", unsafe_allow_html=True)
        lesson_choice = st.selectbox("اختر الدرس المستهدف بالتحديث أو الإضافة:", ["الدرس 1", "الدرس 2", "الدرس 3"])
        current_ref = get_lesson_ref(lesson_choice, df_lessons)
        st.info(f"📋 المرجع الحالي المحفوظ سحابياً للدرس:\n\n{current_ref}")
        
        uploaded_ref_file = st.file_uploader(f"📸 📤 ارفع ملف الدرس المرجعي الرسمي:", type=['pdf', 'jpg', 'jpeg', 'png'], key="admin_file_uploader")
        ref_note = st.text_area("أدخل عناصر الدرس الأساسية أو التوجيهات المكتوبة للذكاء الاصطناعي:", height=120, value=current_ref if "لا توجد ملاحظات" not in current_ref else "")

        if st.button("💾 حفظ ونشر الدرس في المنصة بشكل دائم", use_container_width=True):
            with st.spinner("جاري التحديث..."):
                drive_link = ""
                if uploaded_ref_file is not None:
                    drive_link = upload_pdf_to_drive(f"{lesson_choice}_{uploaded_ref_file.name}", uploaded_ref_file.read())
                
                full_reference_text = f"{ref_note}\n\n🔗 رابط ملف الدرس المرجعي الثابت in Google Drive:\n{drive_link}" if drive_link else ref_note
                
                try:
                    client = get_gspread_client()
                    sh = client.open("les classes")
                    ws_lessons = sh.worksheet("Lessons")
                    all_vals = ws_lessons.get_all_values()
                    headers = all_vals[0] if all_vals else ["الدرس", "الملاحظات_المرجعية", "تاريخ_التحديث"]
                    rows = all_vals[1:] if all_vals else []
                    
                    updated = False
                    for row in rows:
                        if row and row[0].strip() == lesson_choice.strip():
                            row[1] = full_reference_text
                            row[2] = datetime.now().strftime("%Y-%m-%d %H:%M")
                            updated = True
                            break
                    if not updated: rows.append([lesson_choice, full_reference_text, datetime.now().strftime("%Y-%m-%d %H:%M")])
                    ws_lessons.clear()
                    ws_lessons.update([headers] + rows)
                    st.cache_data.clear()
                    st.success(f"🎉 تم تحديث سجل المرجع بنجاح!")
                except Exception as ex:
                    st.error(f"خطأ أثناء تحديث الإكسيل: {ex}")
                st.rerun()

    with tab3:
        st.markdown("<div class='section-title'>👥 تتبع السجل الأكاديمي للتلاميذ</div>", unsafe_allow_html=True)
        if not df_reports.empty:
            st.dataframe(df_reports, use_container_width=True)

    with tab4:
        st.markdown("<div class='section-title'>⚙️ إعدادات الصيانة والأمان</div>", unsafe_allow_html=True)
        st.info("لإدارة وحذف السجلات يرجى مراجعة ملف Google Sheets مباشرة لضمان حماية البيانات.")

# --- واجهة التلميذ ---
def student_space(df_students, df_reports, df_lessons):
    st.markdown("""
        <div style='background: linear-gradient(135deg, #10b981 0%, #1a365d 100%); padding: 35px; border-radius: 15px; margin-bottom: 25px; text-align: center; border: 2px solid #C5A059;'>
            <h2 class='golden-title' style='font-size: 2.5rem;'>🇲🇦 الفضاء الرقمي للتلميذات والتلاميذ</h2>
            <p class='golden-sub'>منصة ذ.منصوري للتدقيق الفوري للدفاتر المدرسية مدعومة بالذكاء الاصطناعي (AI)</p>
        </div>
    """, unsafe_allow_html=True)
    
    if df_students.empty:
        st.warning("🔄 جاري تهيئة الاتصال السحابي الآمن...")
        return

    col_class = 'القسم'
    col_name = 'اسم التلميذ'
    col_id = 'رقم التلميذ'  
    col_birth = 'تاريخ الإزدياد' 

    if not st.session_state.auth:
        st.markdown("<div class='section-title'>🔑 تسجيل الدخول الآمن لمنظومة التدقيق</div>", unsafe_allow_html=True)
        sel_class = st.selectbox("الرجاء تحديد قسمك الفعلي:", ["---"] + df_students[col_class].unique().tolist())
        col_input1, col_input2 = st.columns(2)
        input_massar = col_input1.text_input("أدخل رقم مسار الخاص بك:").strip()
        input_birth = col_input2.text_input("أدخل تاريخ ازديادك الموثق (سنة-شهر-يوم):").strip()
        
        if st.button("التحقق والولوج الآمن للمنصة 🚀", use_container_width=True):
            if sel_class != "---" and input_massar and input_birth:
                matched_student = df_students[
                    (df_students[col_class] == sel_class) & 
                    (df_students[col_id].str.strip().str.upper() == input_massar.upper()) & 
                    (df_students[col_birth].str.strip() == input_birth)
                ]
                if not matched_student.empty:
                    st.session_state.auth = True
                    st.session_state.user = {"name": matched_student.iloc[0][col_name], "class": sel_class}
                    st.success("🎉 تم التحقق من الهوية بنجاح!")
                    st.rerun()
                else:
                    st.error("❌ عذراً، المعلومات المدخلة غير متطابقة.")
    else:
        student_name = st.session_state.user['name']
        st.success(f"🏫 مرحباً بالتلميذ(ة): **{student_name}** | من قسم: **{st.session_state.user['class']}**")
        
        student_all_submissions = df_reports[df_reports['الاسم'] == student_name] if not df_reports.empty and 'الاسم' in df_reports.columns else pd.DataFrame()
        submitted_lessons = student_all_submissions['الدرس'].tolist() if not student_all_submissions.empty else []
        
        lesson_percentages = {}
        lesson_full_reports = {}
        if not student_all_submissions.empty:
            for _, row in student_all_submissions.iterrows():
                lesson_percentages[row['الدرس']] = row['النسبة']
                lesson_full_reports[row['الدرس']] = row['التقرير']
        
        st.markdown("<div class='section-title'>📊 وضعيتك الحالية في السجل الرقمي:</div>", unsafe_allow_html=True)
        
        if "الدرس 1" in submitted_lessons and "الدرس 2" in submitted_lessons:
            p1 = lesson_percentages.get("الدرس 1", "N/A")
            p2 = lesson_percentages.get("الدرس 2", "N/A")
            st.markdown(f"""
            <div class='status-box' style='border-right-color: #10b981;'>
                📢 <b>لقد قمت بإرسال صور الدرس الأول والدرس الثاني معاً مسبقاً.</b><br>
                📉 نسبة إنجازك لـ <b>الدرس الأول</b> هي: <span style='color:#e0f2fe; background:#1e3a8a; padding:2px 8px; border-radius:5px;'><b>{p1}</b></span><br>
                📉 نسبة إنجازك لـ <b>الدرس الثاني</b> هي: <span style='color:#e0f2fe; background:#1e3a8a; padding:2px 8px; border-radius:5px;'><b>{p2}</b></span>
            </div>
            """, unsafe_allow_html=True)
            
        elif "الدرس 1" in submitted_lessons:
            p1 = lesson_percentages.get("الدرس 1", "N/A")
            st.markdown(f"""
            <div class='status-box' style='border-right-color: #f59e0b;'>
                📢 <b>لقد قمت بإرسال صور الدرس الأول مسبقاً.</b><br>
                📉 نسبة إنجازك للدرس الأول هي: <span style='color:#e0f2fe; background:#1e3a8a; padding:2px 8px; border-radius:5px;'><b>{p1}</b></span><br>
                ⚠️ <i>المرجو الانتقال إلى تبويب الدرس الثاني لإكمال إرسال بقية الواجبات.</i>
            </div>
            """, unsafe_allow_html=True)
            
        elif "الدرس 2" in submitted_lessons:
            p2 = lesson_percentages.get("الدرس 2", "N/A")
            st.markdown(f"""
            <div class='status-box' style='border-right-color: #f59e0b;'>
                📢 <b>لقد قمت بإرسال صور الدرس الثاني مسبقاً.</b><br>
                📉 نسبة إنجازك للدرس الثاني هي: <span style='color:#e0f2fe; background:#1e3a8a; padding:2px 8px; border-radius:5px;'><b>{p2}</b></span><br>
                ⚠️ <i>المرجو الانتقال إلى تبويب الدرس الأول لإكمال إرسال بقية الواجبات.</i>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.warning("ℹ️ لم تقم بإرسال أي دروس بعد. المرجو اختيار الدرس من التبويبات أسفله ورفع 14 صورة على الأقل.")

        lesson_tabs = st.tabs(["📘 المجزوءة / الدرس 1", "📗 المجزوءة / الدرس 2", "📙 المجزوءة / الدرس 3"])
        
        for i, tab in enumerate(lesson_tabs):
            with tab:
                l_name = f"الدرس {i+1}"
                
                if "الدرس 1" in submitted_lessons and "الدرس 2" in submitted_lessons:
                    st.error(f"❌ **تنبيه الإدارة:** لقد أرسلت صور الدرس الأول والدرس الثاني مسبقاً.")
                    st.markdown(f"### 📋 تقرير التدقيق المخزن لـ {l_name}:")
                    st.info(lesson_full_reports.get(l_name, "لا يوجد نص تقرير محفوظ."))
                
                elif l_name in submitted_lessons:
                    current_p = lesson_percentages.get(l_name, "N/A")
                    st.warning(f"ℹ️ **لقد أرسلت صور {l_name} مسبقاً** بنجاح، ونسبة إنجازك المحفوظة هي: **{current_p}**.")
                    st.markdown(f"### 📋 تقرير التدقيق المخزن لـ {l_name}:")
                    st.info(lesson_full_reports.get(l_name, "لا يوجد نص تقرير محفوظ."))
                
                else:
                    st.markdown(f"#### 📸 مركز رفع صور دفتر مادة الرياضيات - {l_name}")
                    saved_lesson_reference = get_lesson_ref(l_name, df_lessons)
                    
                    up_files = st.file_uploader(
                        f"اختر صور صفحات الدفتر لـ {l_name} (🚨 تنبيه: يشترط تحميل 13 صورة على الأقل)", 
                        accept_multiple_files=True, 
                        key=f"up_{l_name}", 
                        type=['jpg','jpeg','png']
                    )
                    
                    if st.button(f"بدء المعالجة والتدقيق الفوري لـ {l_name}", key=f"btn_{l_name}"):
                        if up_files:
                            if len(up_files) < 13:
                                st.error(f"⚠️ **خطأ في معايير قبول الدفتر:** لقد قمت برفع ({len(up_files)}) صور فقط! ميثاق المادة يشترط رفع **14 صورة على الأقل** للدرس لضمان تدقيق المحتوى كاملاً.")
                            else:
                                with st.spinner("🔄 جاري التحقق الفوري من سجلاتك وفحص جودة الصور..."):
                                    current_hashes = []
                                    for f in up_files:
                                        f_bytes = f.read()
                                        f.seek(0)
                                        current_hashes.append(calculate_image_hash(f_bytes))
                                    
                                    try:
                                        client = get_gspread_client()
                                        live_sh = client.open("les classes").worksheet("Reports")
                                        live_rows = live_sh.get_all_values()
                                        
                                        if live_rows and len(live_rows) > 1:
                                            live_headers = [h.strip() for h in live_rows[0]]
                                            df_live_reports = pd.DataFrame(live_rows[1:], columns=live_headers)
                                            df_live_reports.columns = df_live_reports.columns.str.strip()
                                            if "اسم" in df_live_reports.columns: df_live_reports = df_live_reports.rename(columns={"اسم": "الاسم"})
                                            if "إسم" in df_live_reports.columns: df_live_reports = df_live_reports.rename(columns={"إسم": "الاسم"})
                                        else:
                                            df_live_reports = pd.DataFrame(columns=["التاريخ", "الاسم", "القسم", "الدرس", "التقرير", "النسبة", "بصمات_الصور"])
                                    except Exception as check_err:
                                        st.error(f"❌ تعذر الاتصال بالسيرفر للتحقق: {check_err}")
                                        st.stop()
                                
                                cheater_detected = False
                                original_student_name = ""
                                
                                if "بصمات_الصور" in df_live_reports.columns:
                                    for idx, row in df_live_reports.iterrows():
                                        if row['الاسم'] == student_name:
                                            continue
                                        saved_hashes_str = str(row['بصمات_الصور']).strip()
                                        if saved_hashes_str:
                                            saved_hashes_list = saved_hashes_str.split(",")
                                            for current_h in current_hashes:
                                                if current_h in saved_hashes_list:
                                                    cheater_detected = True
                                                    original_student_name = row['الاسم']
                                                    break
                                        if cheater_detected: break

                                if cheater_detected:
                                    st.error(
                                        f"🚨 **نظام كشف الغش والسرقة الرقمية:** \n\n"
                                        f"عذراً، هذه الصور تم إرسالها مسبقاً من طرف التلميذ(ة): **{original_student_name}**. \n"
                                        f"لا يمكن لتلميذين إرسال نفس صور الدفتر! تم رصد محاولة التكرار وإلغاء العملية."
                                    )
                                else:
                                    with st.spinner("🔄 البصمات والعدد سليم تماماً! جاري قياس نسبة الإنجاز..."):
                                        try:
                                            # 🛠️ [تحديث الـ Prompt لكشف التكرار البصري]:
                                            prompt_instructions = f"""
                                            أنت مساعد أستاذ الرياضيات عبد الباسط منصوري بالثانوية التأهلية المغربية. 
                                            التلميذ {student_name} (القسم: {st.session_state.user['class']}) أرسل صور دفتره لدرس ({l_name}).
                                            
                                            المرجع والمخطط الملزم الذي حدده الأستاذ لك هو:
                                            \"\"\"{saved_lesson_reference}\"\"\"
                  
                                            🚨 معيار صارم وحاسم ضد الغش: 
                                            قم بفحص الصور المرفوعة بصرياً بدقة. إذا لاحظت أن التلميذ قام برفع "صورتين أو أكثر مكررتين لنفس الصفحة تماماً" (سواء أخذ لقطة شاشة مرتين، أو صور نفس الصفحة من زاويتين مختلفتين لخداع النظام وزيادة عدد الصور لكي يصل لـ 14 صورة)، فقم فوراً بما يلي:
                                            1. اكتب تقريراً حازماً وموجزاً تخبره فيه بأنه تم رصد محاولة تكرار صور لخداع النظام.
                                            2. ضع العبارة الأخيرة تماماً هكذا بدون زيادة أو نقصان:
                                            النسبة النهائية: 0%
                                            
                                            إذا كانت الصور كلها سليمة ومختلفة تتابعياً للدفتر، فنفذ المهام التربوية التالية:
                                            1. تفقد العناوين والفقرات والتمارين المكتوبة بدقة وقارنها بالدرس المرجعي.
                                            2. احسب بدقة "نسبة مئوية تقديرية" لإنجاز التلميذ لكتابة الدرس وحل التمارين.
                                            3. صغ تقريراً تربوياً مشجعاً وموجزاً باللغة العربية.
                                            
                                            🚨 شرط أساسي صارم للبرمجة: يجب أن تنهي تقريرك بكتابة هذه العبارة بالنص في السطر الأخير تماماً:
                                            النسبة النهائية: X%
                                            """
                                            
                                            model = genai.GenerativeModel("gemini-2.5-flash")
                                            imgs = [Image.open(f) for f in up_files]
                                            res = model.generate_content([prompt_instructions, *imgs])
                                            report_text = res.text
                                            
                                            calculated_percentage = "100%"
                                            match = re.search(r"النسبة\s+النهائية:\s*(\d+%)", report_text)
                                            if match: calculated_percentage = match.group(1)

                                            hashes_to_save = ",".join(current_hashes)

                                            live_sh.append_row([
                                                datetime.now().strftime("%Y-%m-%d"), 
                                                student_name, 
                                                st.session_state.user['class'], 
                                                l_name, 
                                                report_text, 
                                                calculated_percentage,
                                                hashes_to_save
                                            ])
                                            
                                            st.cache_data.clear()
                                            st.success(f"تم حفظ التقرير بنجاح! نسبة الإنجاز المسجلة للأستاذ: {calculated_percentage} ✅")
                                            st.rerun() 
                                            
                                        except Exception as gemini_err:
                                            st.error(f"❌ حدث خطأ أثناء فحص الدفتر: {gemini_err}")
                        else:
                            st.warning("⚠️ المرجو تزويد المنصة بصور الدفتر أولاً.")                        

# --- توزيع مسارات العرض ---
if st.session_state.role == "student":
    student_space(df_students, df_reports, df_lessons)
elif st.session_state.role == "admin":
    if not st.session_state.auth:
        st.markdown("<div class='section-title'>🔑 فضاء الأستاذ والإدارة التربوية</div>", unsafe_allow_html=True)
        admin_pwd = st.text_input("الرجاء إدخال كلمة سر الولوج الإدارية المخصصة:", type="password")
        if st.button("تأكيد الهوية 👨‍🏫", use_container_width=True):
            try:
                if admin_pwd == st.secrets["credentials"]["prof_password"]:
                    st.session_state.auth = True
                    st.session_state.user = {"name": "الأستاذ عبد الباسط المنصوري"}
                    st.success("مرحباً بك يا أستاذ!")
                    st.rerun()
                else: st.error("❌ رمز المرور الإداري غير صحيح.")
            except KeyError:
                st.error("⚙️ خطأ في النظام في لوحة التحكم.")
    else: 
        admin_space(df_students, df_reports, df_lessons)
