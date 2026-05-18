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

# --- 1. الإعدادات الأولية وإضفاء الطابع الاحترافي للوزارة ---
st.set_page_config(
    page_title="منصة تدقيق الدفاتر - الأستاذ المنصوري", 
    layout="wide",
    page_icon="math🇲🇦"
)

# دالة الخلفية السحابية المحدثة مع جلب الخط العربي المطور وتطبيقه على المنصة
def get_custom_bg():
    return """
    <style>
    /* جلب الخط العربي الأميري الفخم من جوجل */
    @import url('https://fonts.googleapis.com/css2?family=Amiri:ital,wght@0,400;0,700;1,400;1,700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"], .stApp {
        background-image: linear-gradient(to bottom, rgba(245, 247, 250, 0.94) 0%, rgba(240, 244, 248, 0.88) 100%), 
        url("https://drive.google.com/thumbnail?id=1qtyRtJXUvwJe8qd8HrkC_P7phD6MBiXe&sz=w1920") !important;
        background-size: cover !important;
        background-repeat: no-repeat !important;
        background-attachment: fixed !important;
    }
    
    /* تطبيق الخط العربي الأميري الجميل على التطبيق بالكامل */
    * {
        font-family: 'Amiri', serif !important;
    }
    
    /* كلاس خاص لتنسيق العناوين باللون الذهبي الملكي اللامع مع ظلال احترافية بارزة */
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
    
    /* العناوين الجانبية وفقرات الأقسام باللون الذهبي العتيق */
    .section-title {
        color: #C5A059 !important;
        font-weight: bold !important;
        font-size: 1.6rem !important;
        border-bottom: 2px solid #C5A059;
        padding-bottom: 5px;
        margin-bottom: 15px;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
    }
    
    /* تحسين مظهر القائمة الجانبية باللون الكحلي الملكي للوزارة */
    [data-testid="stSidebar"] { 
        background-color: rgba(26, 54, 93, 0.98) !important; 
    }
    [data-testid="stSidebar"] * { color: white !important; }
    
    /* البطاقات التفاعلية وصناديق الاختيار بتأثير زجاجي شفاف ومحاطة بلمسة ذهبية خفيفة */
    .stSelectbox, .stTextInput, .metric-card, .stTextArea, div[data-testid="stExpander"], .stDateInput {
        background-color: rgba(255, 255, 255, 0.95) !important;
        backdrop-filter: blur(8px) !important;
        -webkit-backdrop-filter: blur(8px) !important;
        border-radius: 12px !important;
        border: 1px solid rgba(197, 160, 89, 0.4) !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.05) !important;
    }

    /* العناوين والنصوص التربوية باللون الأزرق الملكي الغامق */
    h1, h2, h3, label, .stMarkdown p { 
        color: #1a365d !important; 
        font-weight: bold !important; 
    }
    
    /* تنسيق خاص وعصري للأزرار تفاعلياً بجعل النص ذهبياً فخماً */
    .stButton>button {
        background-color: #1a365d !important; 
        color: #FFD700 !important;
        border-radius: 8px !important; 
        border: 1px solid #C5A059 !important;
        padding: 10px 24px !important;
        font-weight: bold !important;
        font-size: 1.2rem !important;
        transition: all 0.2s ease;
        width: 100%;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.4);
    }
    .stButton>button:hover {
        background-color: #C5A059 !important; 
        color: #1a365d !important;
        box-shadow: 0 4px 12px rgba(197, 160, 89, 0.4) !important;
    }
    </style>
    """

st.markdown(get_custom_bg(), unsafe_allow_html=True)

# تفعيل الربط السحابي الآمن مع مفتاح Gemini الجديد
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error("⚠️ لم يتم العثور على مفتاح 'GEMINI_API_KEY' في إعدادات Secrets.")

if 'auth' not in st.session_state: st.session_state.auth = False
if 'user' not in st.session_state: st.session_state.user = {}
if 'role' not in st.session_state: st.session_state.role = None

# دالة الربط مع خدمات جوجل
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
    except Exception as e:
        return "N/A"

# دالة قراءة وتحديث البيانات من جوجل شيت
def load_data():
    sh = None
    for attempt in range(4):
        try:
            client = get_gspread_client()
            sh = client.open("les classes")
            break
        except:
            if attempt == 3:
                return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
            time.sleep(3)
            
    if sh is None: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # 1. قراءة ورقة التلاميذ (Sheet1)
    try:
        data_rows = sh.sheet1.get_all_values()
        if data_rows and len(data_rows) > 1:
            headers = [h.strip() for h in data_rows[0]]
            df_students = pd.DataFrame(data_rows[1:], columns=headers)
            if "إسم التلميذ" in df_students.columns:
                df_students = df_students.rename(columns={"إسم التلميذ": "اسم التلميذ"})
        else:
            df_students = pd.DataFrame(columns=["رقم التلميذ", "اسم التلميذ", "تاريخ الإزدياد", "القسم"])
    except:
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

# دالة جلب رابط الدرس المباشر والثابت سحابياً
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

# --- 2. بناء القائمة الجانبية (Sidebar) ---
with st.sidebar:
    st.markdown("""
        <div style='text-align: center; padding: 10px;'>
            <img src='https://img.icons8.com/color/120/000000/education.png' style='border-radius: 50%; background: white; padding: 10px; width: 80px;'/>
            <h3 style='color: #FFD700 !important; font-size: 1.3rem; margin-top: 10px; text-shadow: 1px 1px 2px black;'>وزارة التربية الوطنية والتعليم الأولي والرياضة</h3>
            <p style='color: #cbd5e1 !important; font-size: 0.95rem;'>الأكاديمية الجهوية للتربية والتكوين</p>
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
        # تطبيق التنسيق والخط العربي واللون الذهبي على "توجيه المسار الرقمي"
        st.markdown("<p style='color: #FFD700 !important; font-size: 1.3rem; text-shadow: 1px 1px 2px black; font-weight: bold; margin-bottom:0px;'>⚙️ توجيه المسار الرقمي:</p>", unsafe_allow_html=True)
        menu = st.radio("", ["🏠 فضاء التلميذ والطالبات", "🔑 فضاء الإدارة والأستاذ"])
        st.session_state.role = "student" if "التلميذ" in menu else "admin"

# --- 3. واجهة الأستاذ ---
def admin_space(df_students, df_reports, df_lessons):
    st.markdown("""
        <div style='background: linear-gradient(##008E8E, #1a365d 0%, #FF0921 100%); padding: 30px; border-radius: 15px; margin-bottom: 25px; color: white; border: 2px solid #C5A059;'>
            <h1 class='golden-title' style='font-size: 2.3rem;'>👨‍🏫 الفضاء الرقمي للتدقيق الإداري والتربوي</h1>
            <p class='golden-sub'>مرحباً بك يا أستاذ عبد الباسط المنصوري - تتبع ذكي ومقاومة شاملة لنسخ وتكرار دفاتر التلاميذ</p>
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
        
        uploaded_ref_file = st.file_uploader(f"📸 📤 ارفع ملف الدرس المرجعي الرسمي (صيغة PDF للحفظ الدائم):", type=['pdf', 'jpg', 'jpeg', 'png'], key="admin_file_uploader")
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
                    st.success(f"🎉 تم تحديث سجل المرجع بنجاح!")
                except Exception as ex:
                    st.error(f"خطأ أثناء تحديث الإكسيل: {ex}")
                st.rerun()

    with tab3:
        st.markdown("<div class='section-title'>👥 تتبع السجل الأكاديمي للتلاميذ</div>", unsafe_allow_html=True)
        if not df_students.empty:
            col_search = 'اسم التلميذ' if 'اسم التلميذ' in df_students.columns else df_students.columns[1]
            search_name = st.selectbox("اختر اسم التلميذ(ة):", df_students[col_search].unique())
            student_history = df_reports[df_reports['الاسم'] == search_name] if not df_reports.empty else pd.DataFrame()
            if not student_history.empty: st.dataframe(student_history, use_container_width=True)
            else: st.info("لا توجد إرسالات مسجلة لهذا التلميذ حتى الآن.")

    with tab4:
        st.markdown("<div class='section-title'>⚙️ إعدادات الصيانة والأمان</div>", unsafe_allow_html=True)
        st.info("لإدارة وحذف السجلات يرجى مراجعة ملف Google Sheets مباشرة لضمان حماية البيانات.")

# --- 4. واجهة التلميذ الاحترافية والأمنة (بالحفاظ على الخصوصية) ---
def
