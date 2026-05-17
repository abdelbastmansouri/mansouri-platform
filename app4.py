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

# --- 1. الإعدادات الأولية وإضفاء الطابع الاحترافي للوزارة ---
st.set_page_config(
    page_title="منصة تدقيق الدفاتر - الأستاذ المنصوري", 
    layout="wide",
    page_icon="🇲🇦"
)

# تصميم وتنسيقات CSS المتقدمة: دمج الزخرفة المغربية والتدرج الانسيابي والشفافية
st.markdown("""
    <style>
    /* إضافة الخلفية بالزخرفة المغربية مع التدرج الانسيابي من الأعلى */
    .stApp { 
        background: 
            linear-gradient(to bottom, rgba(30, 58, 138, 0.95) 0%, rgba(248, 250, 252, 0.85) 20%, rgba(248, 250, 252, 0.4) 100%),
            url('https://pub-c2a41d6361a74288b894ecbcf82b7b51.r2.dev/zelige_pattern.png');
        background-size: contain;
        background-repeat: repeat;
        background-attachment: fixed;
    }
    
    /* جعل القائمة الجانبية متميزة وثابتة */
    [data-testid="stSidebar"] { 
        background-color: rgba(15, 23, 42, 0.95) !important; 
        color: white; 
    }
    [data-testid="stSidebar"] * { color: white !important; }
    
    /* جعل بطاقات الإحصائيات والصناديق البيضاء شفافة وأنيقة لتظهر الخلفية من ورائها */
    .metric-card {
        background-color: rgba(255, 255, 255, 0.85);
        backdrop-filter: blur(5px);
        border-top: 4px solid #d97706;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        text-align: center;
    }
    
    /* جعل خلفيات الـ Tabs شفافة أيضاً لتنسجم مع الزليج */
    .stTabs [data-baseweb="tab-panel"] {
        background-color: rgba(255, 255, 255, 0.75);
        backdrop-filter: blur(5px);
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        margin-top: 10px;
    }

    h1, h2, h3 { color: #1e3a8a !important; font-family: 'Segoe UI', sans-serif; font-weight: bold; }
    
    .stButton>button {
        background-color: #1e3a8a !important; color: white !important;
        border-radius: 8px !important; border: none !important;
        padding: 10px 24px !important; font-weight: bold !important;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #d97706 !important;
        box-shadow: 0 4px 12px rgba(217, 119, 6, 0.3);
    }
    </style>
    """, unsafe_allow_html=True)

# إعداد مفتاح Gemini
genai.configure(api_key="AIzaSyAwhWzEseoWORwT8eBLWBNB57wkuFxaBeA")

if 'auth' not in st.session_state: st.session_state.auth = False
if 'user' not in st.session_state: st.session_state.user = {}
if 'role' not in st.session_state: st.session_state.role = None

# دالة الربط مع خدمات جوجل
def get_gcp_credentials():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    
def get_gspread_client():
    return gspread.authorize(get_gcp_credentials())

# دالة مطورة ومستقرة لرفع الملفات داخل مجلدك المشترك مع نقل الملكية لتفادي خطأ المساحة 403
def upload_pdf_to_drive(file_name, file_bytes):
    try:
        creds = get_gcp_credentials()
        drive_service = build('drive', 'v3', credentials=creds)
        
        # الـ ID النظيف الخاص بمجلدك المشترك الجديد
        SHARED_FOLDER_ID = "1SwrvnMPTYLPSiV4B3Lyr6TiDCpurx_24"
        
        file_metadata = {
            'name': file_name,
            'mimeType': 'application/pdf',
            'parents': [SHARED_FOLDER_ID]
        }
        
        fh = io.BytesIO(file_bytes)
        media = MediaIoBaseUpload(fh, mimetype='application/pdf', chunksize=1024*1024, resumable=True)
        
        # إضافة supportsAllDrives=True ليتجاوز الروبوت قيود مساحته الصفرية في المجلدات المشتركة
        request = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink',
            supportsAllDrives=True  
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            
        file_id = response.get('id')
        
        # منح صلاحية القراءة لكل من يملك الرابط
        user_permission = {'type': 'anyone', 'role': 'reader'}
        drive_service.permissions().create(
            fileId=file_id, 
            body=user_permission,
            supportsAllDrives=True
        ).execute()
        
        return response.get('webViewLink')
    except Exception as e:
        st.error(f"❌ تعذر الرفع إلى Google Drive. تفاصيل العائق الإداري: {str(e)}")
        return None

# دالة القراءة المحدثة والمطابقة لترتيب وعناوين ملفك الفعلي 100% (تم تنظيف التكرار القديم)
def load_data():
    sh = None
    for attempt in range(4):
        try:
            client = get_gspread_client()
            sh = client.open("les classes")
            break
        except:
            if attempt == 3:
                st.warning("🔄 هناك ضغط مؤقت في الاتصال مع خادم جوجل، يرجى الانتظار بضع ثوانٍ وإعادة التحديث.")
                return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
            time.sleep(3)
            
    if sh is None:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # 1. قراءة ورقة التلاميذ (Sheet1) بتنسيقها الجديد المتوافق مع ملفك الواقعي
    try:
        data_rows = sh.sheet1.get_all_values()
        if data_rows and len(data_rows) > 1:
            headers = [h.strip() for h in data_rows[0]]
            df_students = pd.DataFrame(data_rows[1:], columns=headers)
            
            # توحيد الأسماء برمجياً لتتوافق مع بقية الكود دون الحاجة لتعديل الإكسيل يدوياً
            if "إسم التلميذ" in df_students.columns:
                df_students = df_students.rename(columns={"إسم التلميذ": "اسم التلميذ"})
        else:
            df_students = pd.DataFrame(columns=["رقم التلميذ", "اسم التلميذ", "تاريخ الإزدياد", "القسم"])
    except Exception as e:
        df_students = pd.DataFrame(columns=["رقم التلميذ", "اسم التلميذ", "تاريخ الإزدياد", "القسم"])

    # 2. قراءة ورقة التقارير (Reports)
    try:
        reports_worksheet = sh.worksheet("Reports")
        reports_rows = reports_worksheet.get_all_values()
        if reports_rows and len(reports_rows) > 1:
            reports_headers = [h.strip() for h in reports_rows[0]]
            df_reports = pd.DataFrame(reports_rows[1:], columns=reports_headers)
        else:
            df_reports = pd.DataFrame(columns=["التاريخ", "الاسم", "القسم", "الدرس", "التقرير", "النسبة"])
    except:
        df_reports = pd.DataFrame(columns=["التاريخ", "الاسم", "القسم", "الدرس", "التقرير", "النسبة"])
        
    # 3. قراءة ورقة الدروس (Lessons)
    try:
        lessons_worksheet = sh.worksheet("Lessons")
        lessons_rows = lessons_worksheet.get_all_values()
        if lessons_rows and len(lessons_rows) > 1:
            lessons_headers = [h.strip() for h in lessons_rows[0]]
            df_lessons = pd.DataFrame(lessons_rows[1:], columns=lessons_headers)
        else:
            df_lessons = pd.DataFrame(columns=["الدرس", "الملاحظات_المرجعية", "تاريخ_التحديث"])
    except:
        df_lessons = pd.DataFrame(columns=["الدرس", "الملاحظات_المرجعية", "تاريخ_التحديث"])
        
    return df_students, df_reports, df_lessons

df_students, df_reports, df_lessons = load_data()

def get_lesson_ref(lesson_name, df_lessons):
    if not df_lessons.empty and "الدرس" in df_lessons.columns:
        row = df_lessons[df_lessons["الدرس"] == lesson_name]
        if not row.empty:
            return row.iloc[0]["الملاحظات_المرجعية"]
    return "لا توجد ملاحظات مرجعية ثابتة محددة لهذا الدرس من طرف الأستاذ."

# --- 2. بناء القائمة الجانبية (Sidebar) ---
with st.sidebar:
    st.markdown("""
        <div style='text-align: center; padding: 10px;'>
            <img src='https://img.icons8.com/color/120/000000/education.png' style='border-radius: 50%; background: white; padding: 10px; width: 80px;'/>
            <h3 style='color: white !important; font-size: 1.1rem; margin-top: 10px;'>وزارة التربية الوطنية والتعليم الأولي والرياضة</h3>
            <p style='color: #94a3b8 !important; font-size: 0.8rem;'>الأكاديمية الجهوية للتربية والتكوين</p>
        </div>
    """, unsafe_allow_html=True)
    st.divider()
    
    if st.session_state.auth:
        user_display = st.session_state.user.get('name', 'المستخدم')
        st.success(f"🇲🇦 مرحباً بك: \n\n**{user_display}**")
        if st.session_state.role == "student":
            st.info(f"🏫 القسم: {st.session_state.user.get('class')}")
        st.divider()
        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()
    else:
        st.write("⚙️ **توجيه المسار الرقمي:**")
        menu = st.radio("اختر الفضاء المستهدف:", ["🏠 فضاء التلميذ والطالبات", "🔑 فضاء الإدارة والأستاذ"])
        st.session_state.role = "student" if "التلميذ" in menu else "admin"

# --- 3. واجهة الأستاذ الاحترافية وحفظ الـ PDF ---
def admin_space(df_students, df_reports, df_lessons):
    st.markdown("""
        <div style='background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%); padding: 30px; border-radius: 15px; margin-bottom: 25px; color: white;'>
            <h1 style='color: #FFD700 !important; margin: 0; font-size: 2rem;'>👨‍🏫 الفضاء الرقمي للتدقيق الإداري والتربوي</h1>
            <p style='color: #cbd5e1; margin-top: 5px; font-size: 1rem;'>مرحباً بك يا أستاذ عبد الباسط المنصوري - تتبع ذكي ومقاومة شاملة لنسخ وتكرار دفاتر التلاميذ</p>
        </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 لوحة الإحصائيات", "📂 إضافة ورفع الدروس المرجعية", "👥 تتبع سجلات التلاميذ", "⚙️ الإعدادات"])
    
    with tab1:
        st.markdown("### 📈 المؤشرات التربوية العامة")
        col1, col2, col3 = st.columns(3)
        with col1: st.markdown(f"<div class='metric-card'><p style='color:#64748b; font-weight:bold;'>إجمالي التلاميذ</p><h2 style='margin:0; color:#1e3a8a;'>👥 {len(df_students)}</h2></div>", unsafe_allow_html=True)
        with col2: st.markdown(f"<div class='metric-card'><p style='color:#64748b; font-weight:bold;'>الدفاتر المدققة</p><h2 style='margin:0; color:#1e3a8a;'>📥 {len(df_reports)}</h2></div>", unsafe_allow_html=True)
        with col3: 
            num_classes = df_students['القسم'].nunique() if not df_students.empty and 'القسم' in df_students.columns else 0
            st.markdown(f"<div class='metric-card'><p style='color:#64748b; font-weight:bold;'>الأقسام</p><h2 style='margin:0; color:#1e3a8a;'>🏫 {num_classes}</h2></div>", unsafe_allow_html=True)
        
        if not df_reports.empty and 'القسم' in df_reports.columns:
            fig = px.bar(df_reports.groupby('القسم').size().reset_index(name='عدد الإرسالات'), x='القسم', y='عدد الإرسالات', title="📊 تفاعل الأقسام والالتزام بالدفاتر الرقمية", color_discrete_sequence=['#1e3a8a'])
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.markdown("### 📂 مركز إدارة المراجع السحابية")
        lesson_choice = st.selectbox("اختر الدرس المستهدف بالتحديث أو الإضافة:", ["الدرس 1", "الدرس 2", "الدرس 3"])
        
        current_ref = get_lesson_ref(lesson_choice, df_lessons)
        st.info(f"📋 المرجع الحالي المحفوظ سحابياً للدرس:\n\n{current_ref}")
        
        uploaded_ref_file = st.file_uploader("📸 📤 ارفع ملف الدرس المرجعي الرسمي (صيغة PDF للحفظ الدائم):", type=['pdf', 'jpg', 'jpeg', 'png'], key="admin_file_uploader")
        ref_note = st.text_area("أدخل عناصر الدرس الأساسية أو التوجيهات المكتوبة للذكاء الاصطناعي:", height=120, value=current_ref if "لا توجد ملاحظات" not in current_ref else "")
        
        col_btn1, col_btn2 = st.columns(2)
