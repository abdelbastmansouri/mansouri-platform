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

# --- 1. الإعدادات الأولية وإضفاء الطابع الاحترافي للوزارة ---
st.set_page_config(
    page_title="منصة تدقيق الدفاتر - الأستاذ المنصوري", 
    layout="wide",
    page_icon="🇲🇦"
)

# تصميم وتنسيقات CSS الوزارية
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stSidebar"] { background-color: #0f172a; color: white; }
    [data-testid="stSidebar"] * { color: white !important; }
    .metric-card {
        background-color: white;
        border-top: 4px solid #d97706;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        text-align: center;
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

# دالة الربط مع خدمات جوجل (Sheets + Drive)
def get_gcp_credentials():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)

def get_gspread_client():
    return gspread.authorize(get_gcp_credentials())

# دالة مخصصة لرفع ملف الـ PDF إلى الـ Google Drive الخاص بك وجعله عاماً للقراءة
def upload_pdf_to_drive(file_name, file_bytes):
    try:
        creds = get_gcp_credentials()
        drive_service = build('drive', 'v3', credentials=creds)
        
        file_metadata = {
            'name': file_name,
            'mimeType': 'application/pdf'
        }
        
        fh = io.BytesIO(file_bytes)
        media = MediaIoBaseUpload(fh, mimeType='application/pdf', resumable=True)
        
        # رفع الملف
        uploaded_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        file_id = uploaded_file.get('id')
        
        # جعل الملف متاحاً لأي شخص لديه الرابط ليتمكن الـ AI والتلاميذ من قراءته
        user_permission = {
            'type': 'anyone',
            'role': 'reader',
        }
        drive_service.permissions().create(
            fileId=file_id,
            body=user_permission
        ).execute()
        
        return uploaded_file.get('webViewLink')
    except Exception as e:
        st.error(f"خطأ أثناء الرفع إلى Google Drive: {e}")
        return None

def load_data():
    client = get_gspread_client()
    sh = client.open("les classes")
    df_students = pd.DataFrame(sh.sheet1.get_all_records())
    
    try:
        df_reports = pd.DataFrame(sh.worksheet("Reports").get_all_records())
    except:
        df_reports = pd.DataFrame(columns=["التاريخ", "الاسم", "القسم", "الدرس", "التقرير", "النسبة"])
        
    try:
        ws_lessons = sh.worksheet("Lessons")
        df_lessons = pd.DataFrame(ws_lessons.get_all_records())
    except:
        ws_lessons = sh.add_worksheet(title="Lessons", rows="10", cols="3")
        ws_lessons.append_row(["الدرس", "الملاحظات_المرجعية", "تاريخ_التحديث"])
        ws_lessons.append_row(["الدرس 1", "لا توجد ملاحظات مرجعية حالياً", ""])
        ws_lessons.append_row(["الدرس 2", "لا توجد ملاحظات مرجعية حالياً", ""])
        ws_lessons.append_row(["الدرس 3", "لا توجد ملاحظات مرجعية حالياً", ""])
        df_lessons = pd.DataFrame(ws_lessons.get_all_records())
        
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

# --- 3. واجهة الأستاذ الاحترافية وحفظ الـ PDF بشكل دائم ---
def admin_space(df_students, df_reports, df_lessons):
    st.markdown("""
        <div style='background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%); padding: 30px; border-radius: 15px; margin-bottom: 25px; color: white;'>
            <h1 style='color: #ffffff !important; margin: 0; font-size: 2rem;'>👨‍🏫 الفضاء الرقمي للتدقيق الإداري والتربوي</h1>
            <p style='color: #cbd5e1; margin-top: 5px; font-size: 1rem;'>مرحباً بك يا أستاذ عبد الباسط المنصوري - تتبع ذكي ومقاومة شاملة لنسخ وتكرار دفاتر التلاميذ</p>
        </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 لوحة الإحصائيات", "📂 إضافة ورفع الدروس المرجعية", "👥 تتبع سجلات التلاميذ", "⚙️ الإعدادات"])
    
    with tab1:
        st.markdown("### 📈 المؤشرات التربوية العامة")
        col1, col2, col3 = st.columns(3)
        with col1: st.markdown(f"<div class='metric-card'><p style='color:#64748b; font-weight:bold;'>إجمالي التلاميذ</p><h2 style='margin:0; color:#1e3a8a;'>👥 {len(df_students)}</h2></div>", unsafe_allow_html=True)
        with col2: st.markdown(f"<div class='metric-card'><p style='color:#64748b; font-weight:bold;'>الدفاتر المدققة</p><h2 style='margin:0; color:#1e3a8a;'>📥 {len(df_reports)}</h2></div>", unsafe_allow_html=True)
        with col3: st.markdown(f"<div class='metric-card'><p style='color:#64748b; font-weight:bold;'>الأقسام</p><h2 style='margin:0; color:#1e3a8a;'>🏫 {df_students['القسم'].nunique()}</h2></div>", unsafe_allow_html=True)
        
        if not df_reports.empty:
            fig = px.bar(df_reports.groupby('القسم').size().reset_index(name='عدد الإرسالات'), x='القسم', y='عدد الإرسالات', title="📊 تفاعل الأقسام والالتزام بالدفاتر الرقمية", color_discrete_sequence=['#1e3a8a'])
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.markdown("### 📂 مركز إدارة المراجع السحابية الثابتة")
        lesson_choice = st.selectbox("اختر الدرس المستهدف بالتحديث أو الإضافة:", ["الدرس 1", "الدرس 2", "الدرس 3"])
        
        current_ref = get_lesson_ref(lesson_choice, df_lessons)
        st.info(f"📋 المرجع الحالي المحفوظ سحابياً للدرس:\n\n{current_ref}")
        
        # أداة رفع الـ PDF المرجعي للأستاذ
        uploaded_ref_file = st.file_uploader(f"📸 📤 ارفع ملف الدرس المرجعي الرسمي (يُفضل صيغة PDF للحفظ الدائم):", type=['pdf', 'jpg', 'jpeg', 'png'], key="admin_file_uploader")
        
        ref_note = st.text_area("أدخل عناصر الدرس الأساسية أو التوجيهات المكتوبة للذكاء الاصطناعي:", height=120, value=current_ref if "لا توجد ملاحظات" not in current_ref else "")
        
        col_btn1, col_btn2 = st.columns(2)
        
        if col_btn1.button("💾 حفظ ونشر الدرس في المنصة بشكل دائم", use_container_width=True):
            with st.spinner("جاري رفع الملف إلى Google Drive وتأمين الرابط الدائم..."):
                drive_link = ""
                if uploaded_ref_file is not None:
                    # قراءة محتوى الملف المرفوع كبايتات ورفعه فوراً للـ Drive
                    file_bytes = uploaded_ref_file.read()
                    drive_link = upload_pdf_to_drive(f"{lesson_choice}_{uploaded_ref_file.name}", file_bytes)
                
                client = get_gspread_client()
                sh = client.open("les classes")
                ws_lessons = sh.worksheet("Lessons")
                
                # دمج الرابط الثابت من جوجل درايف مع النص والملاحظات حتى لا يضيع أبداً
                if drive_link:
                    full_reference_text = f"{ref_note}\n\n🔗 رابط ملف الدرس المرجعي الثابت في Google Drive:\n{drive_link}"
                else:
                    full_reference_text = ref_note
                
                cell = ws_lessons.find(lesson_choice)
                if cell:
                    ws_lessons.update_cell(cell.row, 2, full_reference_text)
                    ws_lessons.update_cell(cell.row, 3, datetime.now().strftime("%Y-%m-%d %H:%M"))
                else:
                    ws_lessons.append_row([lesson_choice, full_reference_text, datetime.now().strftime("%Y-%m-%d %H:%M")])
                
                st.success(f"🎉 ممتاز يا أستاذ! تم رفع ملف الـ PDF إلى Google Drive بنجاح، وتم حفظ الرابط بشكل دائم في قاعدة البيانات سحابياً.")
                st.rerun()
                
        if col_btn2.button("🗑️ حذف ملف الدرس الحالي (تصفير المرجع)", use_container_width=True):
            with st.spinner("جاري إزالة المرجع..."):
                client = get_gspread_client()
                sh = client.open("les classes")
                ws_lessons = sh.worksheet("Lessons")
                cell = ws_lessons.find(lesson_choice)
                if cell:
                    ws_lessons.update_cell(cell.row, 2, "لا توجد ملاحظات مرجعية حالياً")
                    ws_lessons.update_cell(cell.row, 3, "")
                st.success("تم حذف المرجع بنجاح.")
                st.rerun()

    with tab3:
        st.markdown("### 👥 تتبع السجل الأكاديمي للتلاميذ")
        search_name = st.selectbox("اختر اسم التلميذ(ة):", df_students['اسم التلميذ'].unique() if 'اسم التلميذ' in df_students.columns else df_students.iloc[:,1].unique())
        student_history = df_reports[df_reports['الاسم'] == search_name]
        if not student_history.empty: st.dataframe(student_history, use_container_width=True)
        else: st.info("لا توجد إرسالات مسجلة لهذا التلميذ حتى الآن.")

    with tab4:
        st.markdown("### ⚙️ إعدادات الصيانة والأمان")
        if st.button("تصفير سجل التقارير (حذف الكل)"): st.warning("يرجى حذف الصفوف يدوياً من ملف Google Sheets.")

# --- 4. واجهة التلميذ الاحترافية ---
def student_space(df_students, df_lessons):
    st.markdown("""
        <div style='background: linear-gradient(135deg, #10b981 0%, #1e3a8a 100%); padding: 35px; border-radius: 15px; margin-bottom: 25px; color: white; text-align: center;'>
            <h2 style='color: #ffffff !important; margin: 0; font-size: 2.2rem; font-weight: bold;'>🇲🇦 الفضاء الرقمي للتلميذات والتلاميذ</h2>
            <p style='color: #e2e8f0; margin-top: 8px; font-size: 1.1rem;'>منصة التدقيق الفوري للدفاتر المدرسية لضمان التميز الأكاديمي والتحصيل المستمر</p>
        </div>
    """, unsafe_allow_html=True)
    
    df_students.columns = df_students.columns.str.strip()
    col_class = 'القسم' if 'القسم' in df_students.columns else None
    col_name = 'إسم التلميذ' if 'إسم التلميذ' in df_students.columns else ('اسم التلميذ' if 'اسم التلميذ' in df_students.columns else None)
    col_id = 'رقم التلميذ' if 'رقم التلميذ' in df_students.columns else None

    if not col_class or not col_name or not col_id:
        st.error(f"⚠️ خطأ في بنية الأعمدة بملف التلاميذ السحابي.")
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
                
                # إذا كان هناك رابط مسبق للـ PDF مرفوع من طرف الأستاذ، نعرضه للتلميذ للمراجعة والتحميل
                if "🔗 رابط ملف الدرس المرجعي الثابت" in saved_lesson_reference:
                    st.markdown("### 📋 الملف المرجعي المعتمد من الأستاذ:")
                    st.success("الملف المرجعي لهذا الدرس متاح ومحفوظ في السحاب بشكل دائم.")
                
                up_files = st.file_uploader(f"اختر صور صفحات الدفتر لـ {l_name}", accept_multiple_files=True, key=f"up_{l_name}", type=['jpg','jpeg','png'])
                
                if st.button(f"بدء المعالجة والتدقيق الفوري لـ {l_name}", key=f"btn_{l_name}"):
                    if up_files:
                        with st.spinner("🔄 جاري سحب المرجع التربوي السحابي الثابت وفحص الدفتر..."):
                            prompt_instructions = f"""
                            أنت مساعد أستاذ رياضيات عبقري ومراقب صارم جداً مكلف بكشف الغش والنسخ وتدقيق الدفاتر. 
                            التلميذ {st.session_state.user['name']} (القسم: {st.session_state.user['class']}) أرسل صور دفتره لدرس ({l_name}).

                            المرجع الأساسي المعتمد لهذا الدرس والمرفوع من طرف الأستاذ (ويشمل الملاحظات ورابط ملف الـ PDF الأصلي الثابت للرجوع إليه) هو:
                            \"\"\"{saved_lesson_reference}\"\"\"

                            المهام والقيود الإلزامية المطلوبة منك أثناء التدقيق والتفتيش (ركز بدقة عالية):
                            1. منع الغش وتطابق الدفاتر بصرياً وبنيوياً.
                            2. التدقيق عنواناً بعنوان وفقرة بفقرة بناءً على عناصر المرجع المذكور أعلاه.
                            3. تدقيق حلول التمارين التطبيقية وتصحيحها كاملة ومقارنتها بالدرس المرجعي.

                            أعط تقريراً منظماً وبليغاً باللغة العربية كالتالي:
                            - 🚨 حالة الأمان ومكافحة الغش:
                            - 📊 نسبة اكتمال الدرس الإجمالية:
                            - 📝 جرد الفقرات والعناوين المكتوبة والناقصة:
                            - 🧮 وضعية التمارين التطبيقية وتصحيحها المتكامل:
                            - 🎨 ملاحظة التنظيم والترتيب الهيكلي للدفتر:
                            """
                            
                            model = genai.GenerativeModel("gemini-2.5-flash")
                            imgs = [Image.open(f) for f in up_files]
                            res = model.generate_content([prompt_instructions, *imgs])
                            
                            client = get_gspread_client()
                            sh = client.open("les classes").worksheet("Reports")
                            sh.append_row([datetime.now().strftime("%Y-%m-%d"), st.session_state.user['name'], st.session_state.user['class'], l_name, res.text, "تم التدقيق بنجاح"])
                            
                            st.markdown("### 📋 تقرير الوزارة الرقمي لتدقيق الدفتر المستلم")
                            st.info(res.text)
                            st.success("تم حفظ التقرير التربوي في سجلات الأستاذ السحابية بنجاح ✅")
                    else: st.warning("⚠️ المرجو تزويد المنصة بصور الدفتر أولاً.")

# --- 5. منطق توزيع مسارات العرض ---
if st.session_state.role == "student":
    student_space(df_students, df_lessons)
elif st.session_state.role == "admin":
    if not st.session_state.auth:
        st.markdown("<h3 style='color: #1e3a8a;'>🔑 فضاء الأستاذ والإدارة التربوية</h3>")
        admin_pwd = st.text_input("الرجاء إدخال كلمة سر الولوج الإدارية المخصصة:", type="password")
        if st.button("تأكيد الهوية 👨‍🏫", use_container_width=True):
            if admin_pwd == "1234":
                st.session_state.auth = True
                st.session_state.user = {"name": "الأستاذ عبد الباسط المنصوري"}
                st.success("مرحباً بك يا أستاذ!")
                st.rerun()
            else: st.error("❌ رمز المرور الإداري غير صحيح.")
    else: admin_space(df_students, df_reports, df_lessons)
