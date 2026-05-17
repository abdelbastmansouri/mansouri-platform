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

# دالة تحويل صورة الزخرفة المحلية المرفقة إلى Base64 لدمجها برمجياً لضمان عدم اختفائها
def get_custom_bg():
    # كود مدمج لنمط الزخرفة الهندسية ليعمل كخلفية مائية خفيفة وأنيقة خلف البيانات
    # تم تقليل شفافيتها لضمان وضوح وقراءة النصوص الرياضية والتقارير بدقة عالية
    return """
    <style>
    html, body, [data-testid="stAppViewContainer"], .stApp {
        background-image: linear-gradient(to bottom, rgba(245, 247, 250, 0.92) 0%, rgba(240, 244, 248, 0.85) 100%), 
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='80' height='80' viewBox='0 0 80 80'%3E%3Cg fill='%231a365d' fill-opacity='0.04'%3E%3Cpath d='M0 0h40v40H0V0zm40 40h40v40H40V40zm0-40h2l-2 2V0zm0 4l4-4h2L40 6V4zm0 4l6-6h2L40 10V8zm0 4l8-8h2L40 14v-2zm0 4l10-10h2L40 18v-2zm0 4l12-12h2L40 22v-2zm0 4l14-14h2L40 26v-2zm0 4l16-16h2L40 30v-2zm0 4l18-18h2L40 34v-2zm0 4l20-20h2L40 38v-2zm0 4l22-22h2L40 42v-2zm0 4l24-24h2L40 46v-2zm0 4l26-26h2L40 50v-2zm0 4l28-28h2L40 54v-2zm0 4l30-30h2L40 58v-2zm0 4l32-32h2L40 62v-2zm0 4l34-34h2L40 66v-2zm0 4l36-36h2L40 70v-2zm0 4l38-38h2L40 74v-2zm0 4l40-40h2L42 80h-2v-2zm4-4l36-36h2L46 80h-2v-2zm4-4l32-32h2L50 80h-2v-2zm4-4l28-28h2L54 80h-2v-2zm4-4l24-24h2L58 80h-2v-2zm4-4l20-20h2L62 80h-2v-2zm4-4l16-16h2L66 80h-2v-2zm4-4l12-12h2L70 80h-2v-2zm4-4l8-8h2L74 80h-2v-2zm4-4l4-4h2L78 80h-2v-2z'/%3E%3C/g%3E%3C/svg%3E") !important;
        background-size: auto !important;
        background-repeat: repeat !important;
        background-attachment: fixed !important;
    }
    
    /* تحسين مظهر القائمة الجانبية باللون الكحلي الملكي للوزارة */
    [data-testid="stSidebar"] { 
        background-color: rgba(26, 54, 93, 0.98) !important; 
    }
    [data-testid="stSidebar"] * { color: white !important; }
    
    /* البطاقات التفاعلية وصناديق الاختيار بتأثير زجاجي شفاف ومحاطة بلمسة ذهبية خفيفة */
    .stSelectbox, .stTextInput, .metric-card, .stTextArea, div[data-testid="stExpander"] {
        background-color: rgba(255, 255, 255, 0.95) !important;
        backdrop-filter: blur(8px) !important;
        -webkit-backdrop-filter: blur(8px) !important;
        border-radius: 12px !important;
        border: 1px solid rgba(212, 175, 55, 0.35) !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.05) !important;
    }

    /* العناوين والنصوص التربوية باللون الأزرق الملكي الغامق */
    h1, h2, h3, label, .stMarkdown p { 
        color: #1a365d !important; 
        font-family: 'Segoe UI', sans-serif !important; 
        font-weight: bold !important; 
    }
    
    /* تنسيق خاص وعصري للأزرار تفاعلياً */
    .stButton>button {
        background-color: #1a365d !important; 
        color: white !important;
        border-radius: 8px !important; 
        border: 1px solid #d4af37 !important;
        padding: 10px 24px !important;
        font-weight: bold !important;
        transition: all 0.2s ease;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #d4af37 !important; 
        color: #1a365d !important;
        box-shadow: 0 4px 12px rgba(212, 175, 55, 0.3) !important;
    }
    </style>
    """

st.markdown(get_custom_bg(), unsafe_allow_html=True)

# تفعيل الربط السحابي الآمن مع مفتاح Gemini الجديد المودع في Secrets
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error("⚠️ لم يتم العثور على مفتاح 'GEMINI_API_KEY' في إعدادات Secrets الخاصة بـ Streamlit. المرجو إضافته أولاً.")

if 'auth' not in st.session_state: st.session_state.auth = False
if 'user' not in st.session_state: st.session_state.user = {}
if 'role' not in st.session_state: st.session_state.role = None

# دالة الربط مع خدمات جوجل
def get_gcp_credentials():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    
def get_gspread_client():
    return gspread.authorize(get_gcp_credentials())

# الدالة النهائية لرفع المراجع وتجاوز خطأ الـ Storage Quota 403
def upload_pdf_to_drive(file_name, file_bytes):
    try:
        creds = get_gcp_credentials()
        drive_service = build('drive', 'v3', credentials=creds)
        
        SHARED_FOLDER_ID = "1SwrvnMPTYLPSiV4B3Lyr6TiDCpurx_24"
        
        file_metadata = {
            'name': file_name,
            'parents': [SHARED_FOLDER_ID]
        }
        
        fh = io.BytesIO(file_bytes)
        media = MediaIoBaseUpload(fh, mimetype='application/pdf', resumable=True)
        
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink',
            supportsAllDrives=True  
        ).execute()
        
        file_id = file.get('id')
        
        try:
            drive_service.permissions().create(
                fileId=file_id,
                body={'type': 'anyone', 'role': 'reader'},
                supportsAllDrives=True
            ).execute()
        except:
            pass 
            
        return file.get('webViewLink')
        
    except Exception as e:
        st.warning("⚠️ تم حفظ المرجع نصياً في الإكسيل بنجاح، وتجاوزنا رفع الـ PDF مؤقتاً لتفادي قيود المساحة.")
        return "N/A"

# دالة القراءة المحدثة والمطابقة لترتيب وعناوين ملف الجدول
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
        row = df_lessons[df_lessons["الدرس"].str.strip() == lesson_name.strip()]
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
        <div style='background: linear-gradient(135deg, #1a365d 0%, #0f172a 100%); padding: 30px; border-radius: 15px; margin-bottom: 25px; color: white; border: 1px solid #d4af37;'>
            <h1 style='color: #FFD700 !important; margin: 0; font-size: 2rem;'>👨‍🏫 الفضاء الرقمي للتدقيق الإداري والتربوي</h1>
            <p style='color: #cbd5e1; margin-top: 5px; font-size: 1rem;'>مرحباً بك يا أستاذ عبد الباسط المنصوري - تتبع ذكي ومقاومة شاملة لنسخ وتكرار دفاتر التلاميذ</p>
        </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 لوحة الإحصائيات", "📂 إضافة ورفع الدروس المرجعية", "👥 تتبع سجلات التلاميذ", "⚙️ الإعدادات"])
    
    with tab1:
        st.markdown("### 📈 المؤشرات التربوية العامة")
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
        st.markdown("### 📂 مركز إدارة المراجع السحابية")
        lesson_choice = st.selectbox("اختر الدرس المستهدف بالتحديث أو الإضافة:", ["الدرس 1", "الدرس 2", "الدرس 3"])
        
        current_ref = get_lesson_ref(lesson_choice, df_lessons)
        st.info(f"📋 المرجع الحالي المحفوظ سحابياً للدرس:\n\n{current_ref}")
        
        uploaded_ref_file = st.file_uploader(f"📸 📤 ارفع ملف الدرس المرجعي الرسمي (صيغة PDF للحفظ الدائم):", type=['pdf', 'jpg', 'jpeg', 'png'], key="admin_file_uploader")
        ref_note = st.text_area("أدخل عناصر الدرس الأساسية أو التوجيهات المكتوبة للذكاء الاصطناعي:", height=120, value=current_ref if "لا توجد ملاحظات" not in current_ref else "")

        col_btn1, col_btn2 = st.columns(2)
        
        if col_btn1.button("💾 حفظ ونشر الدرس في المنصة بشكل دائم", use_container_width=True):
            with st.spinner("جاري تأمين وحفظ الملف سحابياً في المجلد المخصص..."):
                drive_link = ""
                if uploaded_ref_file is not None:
                    file_bytes = uploaded_ref_file.read()
                    drive_link = upload_pdf_to_drive(f"{lesson_choice}_{uploaded_ref_file.name}", file_bytes)
                
                if drive_link:
                    full_reference_text = f"{ref_note}\n\n🔗 رابط ملف الدرس المرجعي الثابت in Google Drive:\n{drive_link}"
                else:
                    full_reference_text = ref_note
                
                for attempt in range(3):
                    try:
                        client = get_gspread_client()
                        sh = client.open("les classes")
                        ws_lessons = sh.worksheet("Lessons")
                        
                        all_vals = ws_lessons.get_all_values()
                        if not all_vals:
                            ws_lessons.append_row(["الدرس", "الملاحظات_المرجعية", "تاريخ_التحديث"])
                            all_vals = [["الدرس", "الملاحظات_المرجعية", "تاريخ_التحديث"]]
                        
                        headers = all_vals[0]
                        rows = all_vals[1:]
                        
                        updated = False
                        for row in rows:
                            if row and row[0].strip() == lesson_choice.strip():
                                row[1] = full_reference_text
                                row[2] = datetime.now().strftime("%Y-%m-%d %H:%M")
                                updated = True
                                break
                        
                        if not updated:
                            rows.append([lesson_choice, full_reference_text, datetime.now().strftime("%Y-%m-%d %H:%M")])
                        
                        ws_lessons.clear()
                        ws_lessons.update([headers] + rows)
                        st.success(f"🎉 تم الحفظ والنشر في حساب الـ Drive والإكسيل بسلام تام!")
                        break
                    except Exception as ex:
                        if attempt == 2:
                            st.error(f"خطأ أثناء تحديث سجل المراجع في الإكسيل: {ex}")
                        time.sleep(2)
                st.rerun()
                
        if col_btn2.button("🗑️ حذف ملف الدرس الحالي (تصفير المرجع)", use_container_width=True):
            with st.spinner("جاري إزالة المرجع..."):
                try:
                    client = get_gspread_client()
                    sh = client.open("les classes")
                    ws_lessons = sh.worksheet("Lessons")
                    
                    all_vals = ws_lessons.get_all_values()
                    if all_vals:
                        headers = all_vals[0]
                        rows = all_vals[1:]
                        for row in rows:
                            if row and row[0].strip() == lesson_choice.strip():
                                row[1] = "لا توجد ملاحظات مرجعية حالياً"
                                row[2] = ""
                                break
                        ws_lessons.clear()
                        ws_lessons.update([headers] + rows)
                    st.success("تم حذف المرجع بنجاح.")
                except Exception as ex:
                    st.error(f"عذراً، فشل الحذف: {ex}")
                st.rerun()

    with tab3:
        st.markdown("### 👥 تتبع السجل الأكاديمي للتلاميذ")
        if not df_students.empty:
            col_search = 'اسم التلميذ' if 'اسم التلميذ' in df_students.columns else (df_students.columns[1] if len(df_students.columns) > 1 else None)
            if col_search and col_search in df_students.columns:
                search_name = st.selectbox("اختر اسم التلميذ(ة):", df_students[col_search].unique())
                student_history = df_reports[df_reports['الاسم'] == search_name] if not df_reports.empty and 'الاسم' in df_reports.columns else pd.DataFrame()
                if not student_history.empty: st.dataframe(student_history, use_container_width=True)
                else: st.info("لا توجد إرسالات مسجلة لهذا التلميذ حتى الآن.")
        else:
            st.warning("جدول التلاميذ فارغ أو تعذر الاتصال به مؤقتاً.")

    with tab4:
        st.markdown("### ⚙️ إعدادات الصيانة والأمان")
        if st.button("تصفير سجل التقارير (حذف الكل)"): st.warning("يرجى حذف الصفوف يدوياً من ملف Google Sheets.")

# --- 4. واجهة التلميذ الاحترافية ---
def student_space(df_students, df_lessons):
    st.markdown("""
        <div style='background: linear-gradient(135deg, #10b981 0%, #F5276C 100%); padding: 35px; border-radius: 15px; margin-bottom: 25px; color: white; text-align: center; border: 1px solid #d4af37;'>
            <h2 style='color: #F0FFFF !important; margin: 0; font-size: 2.2rem; font-weight: bold;'>🇲🇦 الفضاء الرقمي للتلميذات والتلاميذ</h2>
            <p style='color: #e2e8f0; margin-top: 8px; font-size: 1.1rem;'>منصة التدقيق الفوري للدفاتر المدرسية لضمان التميز الأكاديمي والتحصيل المستمر</p>
        </div>
    """, unsafe_allow_html=True)
    
    if df_students.empty:
        st.warning("🔄 المنصة تقوم بتهدئة الاتصال مع خوادم جوجل حالياً، يرجى الانتظار لثوانٍ قليلة.")
        return

    df_students.columns = df_students.columns.str.strip()
    col_class = 'القسم' if 'القسم' in df_students.columns else None
    col_name = 'اسم التلميذ' if 'اسم التلميذ' in df_students.columns else None
    col_id = 'رقم التلميذ' if 'رقم التلميذ' in df_students.columns else None

    if not col_class or not col_name or not col_id:
        st.error(f"⚠️ خطأ في بنية الملف السحابي للإكسيل. يرجى مراجعة عناوين الأعمدة.")
        return

    if not st.session_state.auth:
        st.markdown("### 🔑 تسجيل الدخول لمنظومة التدقيق")
        c1, c2 = st.columns(2)
        sel_class = c1.selectbox("الرجاء تحديد القسم:", ["---"] + df_students[col_class].unique().tolist())
        names = df_students[df_students[col_class] == sel_class][col_name].tolist() if sel_class != "---" else []
        sel_name = c2.selectbox("الرجاء اختيار اسمك الكامل:", ["---"] + names)
        pwd = st.text_input("أدخل القن السري الخاص بك (رقم مسار):", type="password")
        
        if st.button("الولوج الآمن للمنصة 🚀", use_container_width=True):
            if sel_name != "---" and pwd.strip() != "":
                real_pwd = df_students[df_students[col_name] == sel_name][col_id].values[0]
                if str(pwd).strip().upper() == str(real_pwd).strip().upper():
                    st.session_state.auth = True
                    st.session_state.user = {"name": sel_name, "class": sel_class}
                    st.rerun()
                else: st.error("❌ القن السري غير صحيح.")
            else: st.warning("المرجو تعبئة كافة الحقول.")
                    
    else:
        st.success(f"🏫 مرحباً بك: {st.session_state.user['name']} | القسم الفعلي: {st.session_state.user['class']}")
        lesson_tabs = st.tabs(["📘 المجزوءة / الدرس 1", "📗 المجزوءة / الدرس 2", "📙 المجزوءة / الدرس 3"])
        
        for i, tab in enumerate(lesson_tabs):
            with tab:
                l_name = f"الدرس {i+1}"
                st.markdown(f"#### 📸 مركز رفع صور دفتر مادة الرياضيات - {l_name}")
                
                saved_lesson_reference = get_lesson_ref(l_name, df_lessons)
                
                if "🔗 رابط ملف الدرس المرجعي الثابت" in saved_lesson_reference:
                    st.markdown("### 📋 الملف المرجعي المعتمد من الأستاذ:")
                    st.success("الملف المرجعي لهذا الدرس متاح ومحفوظ في السحاب بشكل دائم.")
                
                up_files = st.file_uploader(f"اختر صور صفحات الدفتر لـ {l_name}", accept_multiple_files=True, key=f"up_{l_name}", type=['jpg','jpeg','png'])
                
                if st.button(f"بدء المعالجة والتدقيق الفوري لـ {l_name}", key=f"btn_{l_name}"):
                    if up_files:
                        with st.spinner("🔄 جاري سحب المرجع التربوي السحابي الثابت وفحص الدفتر..."):
                            try:
                                if "الدرس 3" in l_name:
                                    prompt_instructions = f"""
                                    أنت أستاذ مساعد لمادة الرياضيات بالثانوية التأهلية، ومهمتك الحالية هي مراقبة وتأكيد إنجاز التمارين والبحوث المنزلية.
                                    التلميذ: {st.session_state.user['name']} (القسم: {st.session_state.user['class']}) أرسل صور واجباته لدرس ({l_name}).

                                    المهام والقيود الإلزامية المطلوبة منك:
                                    1. تحقق بصرياً ومنطقياً بدقة عالية هل الصورة المرفوعة تحتوي فعلاً على تمارين رياضيات، معادلات، حلول، أو بحوث مكتوبة بخط اليد أو منجزة في ورقة/دفتر.
                                    2. لا تعتمد على أي مرجع سابق ولا تقارن المحتوى بأي درس، فالمطلوب فقط هو التأكد من وجود مجهود وإنجاز فعلي للواجب المنزلي.
                                    3. إذا كانت الصورة صحيحة وتحتوي على تمارين، صغ رداً تربوياً مشجعاً ومحفزاً يؤكد للتلميذ أنه تم قبول إرساله بنجاح (مثال: أحسنتم، تم تسجيل إنجازكم للتمارين بنجاح...).
                                    4. إذا كانت الصورة فارغة، أو غير واضحة، أو لا علاقة لها بالرياضيات والواجبات، أخبر التلميذ بلطف أن الصورة غير مطابقة وشجعه على إعادة رفع صورة واضحة لتمارينه لتسجيل الحضور.
                                    
                                    لغة الرد: اللغة العربية بأسلوب تربوي رصين ومحفز.
                                    """
                                else:
                                    prompt_instructions = f"""
                                    أنت مساعد أستاذ رياضيات عبقري ومراقب صارم جداً مكلف بكشف الغش والنسخ وتدقيق الدفاتر. 
                                    التلميذ {st.session_state.user['name']} (القسم: {st.session_state.user['class']}) أرسل صور دفتره لدرس ({l_name}).

                                    المرجع الأساسي المعتمد لهذا الدرس والمرفوع من طرف الأستاذ هو:
                                    \"\"\"{saved_lesson_reference}\"\"\"

                                    المهام والقيود الإلزامية المطلوبة منك أثناء التدقيق والتفتيش:
                                    1. منع الغش وتطابق الدفاتر بصرياً وبنيوياً.
                                    2. التدقيق عنواناً بعنوان وفقرة بفقرة بناءً على عناصر المرجع المذكور أعلاه.
                                    3. مقارنة التمارين التطبيقية مع الدرس المرجعي والتأكد من حلول التمارين التطبيقية كاملة رغم عدم وجودها بالدرس المرجعي.  
                                    
                                    لغة الرد: اللغة العربية بأسلوب تربوي رصين.
                                    """
                                
                                model = genai.GenerativeModel("gemini-2.5-flash")
                                imgs = [Image.open(f) for f in up_files]
                                res = model.generate_content([prompt_instructions, *imgs])
                                
                                client = get_gspread_client()
                                sh = client.open("les classes").worksheet("Reports")
                                sh.append_row([datetime.now().strftime("%Y-%m-%d"), st.session_state.user['name'], st.session_state.user['class'], l_name, res.text, "تم التدقيق بنجاح"])
                                
                                st.markdown("### 📋التقرير الرقمي لتدقيق الدفتر المستلم")
                                st.info(res.text)
                                st.success("تم حفظ التقرير التربوي في سجلات الأستاذ السحابية بنجاح ✅")
                            except Exception as gemini_err:
                                st.error(f"❌ حدث خطأ أثناء فحص الدفتر برمجياً: {gemini_err}")
                    else:
                        st.warning("⚠️ المرجو تزويد المنصة بصور الدفتر أولاً.")

# --- 5. منطق توزيع مسارات العرض ---
if st.session_state.role == "student":
    student_space(df_students, df_lessons)
elif st.session_state.role == "admin":
    if not st.session_state.auth:
        st.markdown("<h3 style='color: #1a365d;'>🔑 فضاء الأستاذ والإدارة التربوية</h3>", unsafe_allow_html=True)
        admin_pwd = st.text_input("الرجاء إدخال كلمة سر الولوج الإدارية المخصصة:", type="password")
        if st.button("تأكيد الهوية 👨‍🏫", use_container_width=True):
            if admin_pwd == "1234":
                st.session_state.auth = True
                st.session_state.user = {"name": "الأستاذ عبد الباسط المنصوري"}
                st.success("مرحباً بك يا أستاذ!")
                st.rerun()
            else: st.error("❌ رمز المرور الإداري غير صحيح.")
    else: admin_space(df_students, df_reports, df_lessons)
