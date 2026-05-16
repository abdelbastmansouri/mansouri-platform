import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import io

# --- 1. الإعدادات الأولية وإضفاء الطابع الاحترافي للوزارة ---
st.set_page_config(
    page_title="منصة تدقيق الدفاتر - الأستاذ المنصوري", 
    layout="wide",
    page_icon="🇲🇦"
)

# تصميم خلفية وتنسيقات CSS احترافية مستوحاة من مواقع الوزارة الرسمية
st.markdown("""
    <style>
    /* تغيير الخلفية العامة للموقع */
    .stApp {
        background-color: #f8fafc;
    }
    /* تحسين مظهر القائمة الجانبية */
    [data-testid="stSidebar"] {
        background-color: #0f172a;
        color: white;
    }
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    /* تصميم البطاقات الإحصائية للأستاذ */
    .metric-card {
        background-color: white;
        border-top: 4px solid #d97706; /* خط ذهبي رسمي */
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        text-align: center;
    }
    /* العناوين الرئيسية */
    h1, h2, h3 {
        color: #1e3a8a !important; /* الأزرق الملكي للوزارة */
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        font-weight: bold;
    }
    /* تحسين مظهر الأزرار */
    .stButton>button {
        background-color: #1e3a8a !important;
        color: white !important;
        border-radius: 8px !important;
        border: none !important;
        padding: 10px 24px !important;
        font-weight: bold !important;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #d97706 !important; /* التحول للذهبي عند التمرير */
        box-shadow: 0 4px 12px rgba(217, 119, 6, 0.3);
    }
    </style>
    """, unsafe_allow_html=True)

# إعداد مفتاح Gemini
genai.configure(api_key="AIzaSyAwhWzEseoWORwT8eBLWBNB57wkuFxaBeA")

# تهيئة متغيرات الجلسة (Session State)
if 'auth' not in st.session_state:
    st.session_state.auth = False
if 'user' not in st.session_state:
    st.session_state.user = {}
if 'role' not in st.session_state:
    st.session_state.role = None

def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

def load_data():
    client = get_gspread_client()
    sh = client.open("les classes")
    
    # قراءة بيانات التلاميذ
    df_students = pd.DataFrame(sh.sheet1.get_all_records())
    
    # قراءة التقارير
    try:
        df_reports = pd.DataFrame(sh.worksheet("Reports").get_all_records())
    except:
        df_reports = pd.DataFrame(columns=["التاريخ", "الاسم", "القسم", "الدرس", "التقرير", "النسبة"])
        
    # قراءة المراجع الثابتة من ورقة Lessons
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

# تحميل البيانات الشاملة من السحاب
df_students, df_reports, df_lessons = load_data()

def get_lesson_ref(lesson_name, df_lessons):
    if not df_lessons.empty and "الدرس" in df_lessons.columns:
        row = df_lessons[df_lessons["الدرس"] == lesson_name]
        if not row.empty:
            return row.iloc[0]["الملاحظات_المرجعية"]
    return "لا توجد ملاحظات مرجعية ثابتة محددة لهذا الدرس من طرف الأستاذ."

# --- 2. بناء القائمة الجانبية (Sidebar) بهوية الوزارة الرقمية ---
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
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    else:
        st.write("⚙️ **توجيه المسار الرقمي:**")
        menu = st.radio("اختر الفضاء المستهدف:", ["🏠 فضاء التلميذ والطالبات", "🔑 فضاء الإدارة والأستاذ"])
        st.session_state.role = "student" if "التلميذ" in menu else "admin"

    st.divider()
    st.markdown("<p style='text-align: center; color: #64748b !important; font-size: 0.75rem;'>منصة تتبع ومراقبة الدفاتر الرقمية © 2026</p>", unsafe_allow_html=True)

# --- 3. واجهة الأستاذ الاحترافية والمبيانات الجميلة ---
def admin_space(df_students, df_reports, df_lessons):
    st.markdown("""
        <div style='background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%); padding: 30px; border-radius: 15px; margin-bottom: 25px; color: white;'>
            <h1 style='color: #ffffff !important; margin: 0; font-size: 2rem;'>👨‍🏫 الفضاء الرقمي للتدقيق الإداري والتربوي</h1>
            <p style='color: #cbd5e1; margin-top: 5px; font-size: 1rem;'>مرحباً بك يا أستاذ عبد الباسط المنصوري - تتبع ذكي ومقاومة شاملة لنسخ وتكرار دفاتر التلاميذ</p>
        </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 لوحة الإحصائيات والمبيانات", "📂 إضافة ورفع الدروس المرجعية", "👥 تتبع سجلات التلاميذ", "⚙️ الإعدادات"])
    
    with tab1:
        st.markdown("### 📈 المؤشرات التربوية العامة")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"<div class='metric-card'><p style='color:#64748b; font-weight:bold;'>إجمالي التلاميذ المسجلين</p><h2 style='margin:0; color:#1e3a8a;'>👥 {len(df_students)}</h2></div>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div class='metric-card'><p style='color:#64748b; font-weight:bold;'>عدد الدفاتر المرفوعة والمدققة</p><h2 style='margin:0; color:#1e3a8a;'>📥 {len(df_reports)}</h2></div>", unsafe_allow_html=True)
        with col3:
            st.markdown(f"<div class='metric-card'><p style='color:#64748b; font-weight:bold;'>البنية التربوية (الأقسام)</p><h2 style='margin:0; color:#1e3a8a;'>🏫 {df_students['القسم'].nunique()}</h2></div>", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if not df_reports.empty:
            fig = px.bar(
                df_reports.groupby('القسم').size().reset_index(name='عدد الإرسالات'), 
                x='القسم', 
                y='عدد الإرسالات', 
                title="📊 تفاعل الأقسام والالتزام بالدفاتر الرقمية",
                color_discrete_sequence=['#1e3a8a']
            )
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font_family="Segoe UI",
                title_font_size=18
            )
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.markdown("### 📂 مركز إدارة المراجع السحابية الثابتة")
        lesson_choice = st.selectbox("اختر الدرس المستهدف بالتحديث أو الإضافة:", ["الدرس 1", "الدرس 2", "الدرس 3"])
        
        current_ref = get_lesson_ref(lesson_choice, df_lessons)
        st.info(f"📋 الوضع الحالي للمرجع المخزن سحابياً للدرس المختار:\n\n{current_ref}")
        
        uploaded_ref_file = st.file_uploader(f"📸 📤 ارفع ملف الدرس المرجعي الرسمي (صور أو PDF):", type=['jpg', 'jpeg', 'png', 'pdf'], accept_multiple_files=True, key="admin_file_uploader")
        
        ref_note = st.text_area("أدخل عناصر الدرس الأساسية والتوجيهات الصارمة للتدقيق عنواناً بعنوان وفقرة بفقرة:", height=150, value=current_ref if "لا توجد ملاحظات" not in current_ref else "")
        
        col_btn1, col_btn2 = st.columns(2)
        
        if col_btn1.button("💾 حفظ ونشر الدرس في المنصة بشكل دائم", use_container_width=True):
            with st.spinner("جاري المزامنة المشفرة مع السحاب..."):
                client = get_gspread_client()
                sh = client.open("les classes")
                ws_lessons = sh.worksheet("Lessons")
                
                file_status = f" [تم إرفاق {len(uploaded_ref_file)} ملف مرجعي بنجاح]" if uploaded_ref_file else ""
                full_reference_text = ref_note + file_status
                
                cell = ws_lessons.find(lesson_choice)
                if cell:
                    ws_lessons.update_cell(cell.row, 2, full_reference_text)
                    ws_lessons.update_cell(cell.row, 3, datetime.now().strftime("%Y-%m-%d %H:%M"))
                else:
                    ws_lessons.append_row([lesson_choice, full_reference_text, datetime.now().strftime("%Y-%m-%d %H:%M")])
                
                st.success(f"🎉 ممتاز! تم تثبيت مراجع {lesson_choice} سحابياً بنجاح، ولن تختفي أبداً عند التحديث.")
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
                st.success("تم حذف المرجع بنجاح من قاعدة البيانات.")
                st.rerun()

    with tab3:
        st.markdown("### 👥 تتبع السجل الأكاديمي للتلاميذ")
        search_name = st.selectbox("اختر اسم التلميذ(ة) لعرض التقارير وسجل الالتزام الدفتري المحفوظ:", df_students['اسم التلميذ'].unique() if 'اسم التلميذ' in df_students.columns else df_students.iloc[:,1].unique())
        student_history = df_reports[df_reports['الاسم'] == search_name]
        if not student_history.empty:
            st.dataframe(student_history, use_container_width=True)
        else:
            st.info("لا توجد إرسالات مسجلة لهذا التلميذ حتى الآن.")

    with tab4:
        st.markdown("### ⚙️ إعدادات الصيانة والأمان")
        if st.button("تصفير سجل التقارير (حذف الكل)"):
            st.warning("يرجى حذف الصفوف يدوياً من ملف Google Sheets حالياً لضمان الأمان الفائق للملفات.")

# --- 4. واجهة التلميذ الاحترافية مع تصحيح المتغير بالكامل ---
def student_space(df_students, df_lessons):
    st.markdown("""
        <div style='background: linear-gradient(135deg, #10b981 0%, #1e3a8a 100%); padding: 35px; border-radius: 15px; margin-bottom: 25px; color: white; text-align: center; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);'>
            <h2 style='color: #ffffff !important; margin: 0; font-size: 2.2rem; font-weight: bold;'>🇲🇦 الفضاء الرقمي للتلميذات والتلاميذ</h2>
            <p style='color: #e2e8f0; margin-top: 8px; font-size: 1.1rem;'>منصة التدقيق الفوري للدفاتر المدرسية لضمان التميز الأكاديمي والتحصيل المستمر</p>
            <div style='margin-top: 15px; font-size: 0.9rem; background: rgba(255,255,255,0.15); padding: 8px 15px; border-radius: 20px; display: inline-block;'>
                ⚠️ <b>تنبيه أمني هام:</b> يرجى تصوير دفترك الشخصي والخاص فقط. المنصة مزودة برادار ذكي لكشف تكرار وتطابق الصور.
            </div>
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
        with st.container():
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
                    else:
                        st.error("❌ القن السري (رقم مسار) غير صحيح، يرجى إعادة التثبت.")
                else:
                    st.warning("المرجو تعبئة كافة الحقول المطلوبة لتوثيق الهوية.")
                    
    else:
        st.success(f"🏫 مرحباً بك: {st.session_state.user['name']} | القسم الفعلي: {st.session_state.user['class']}")
        
        lesson_tabs = st.tabs(["📘 المجزوءة / الدرس 1", "📗 المجزوءة / الدرس 2", "📙 المجزوءة / الدرس 3"])
        
        for i, tab in enumerate(lesson_tabs):
            with tab:
                l_name = f"الدرس {i+1}"
                st.markdown(f"#### 📸 مركز رفع صور دفتر مادة الرياضيات - {l_name}")
                st.write("الرجاء التقاط صور واضحة لجميع صفحات الدفتر المرتبطة بهذا الدرس ورفعها دفعة واحدة:")
                
                up_files = st.file_uploader(f"اختر صور صفحات الدفتر لـ {l_name}", accept_multiple_files=True, key=f"up_{l_name}", type=['jpg','jpeg','png'])
                
                if st.button(f"بدء المعالجة والتدقيق الفوري لـ {l_name}", key=f"btn_{l_name}"):
                    if up_files:
                        with st.spinner("🔄 جاري سحب المرجع التربوي السحابي وفحص بصمة الدفتر ومطابقة الحلول..."):
                            
                            saved_lesson_reference = get_lesson_ref(l_name, df_lessons)
                            
                            prompt_instructions = f"""
                            أنت مساعد أستاذ رياضيات عبقري ومراقب صارم جداً مكلف بكشف الغش والنسخ وتدقيق الدفاتر. 
                            التلميذ {st.session_state.user['name']} (القسم: {st.session_state.user['class']}) أرسل صور دفتره لدرس ({l_name}).

                            المرجع الأساسي المعتمد لهذا الدرس والمرفوع من طرف الأستاذ هو:
                            \"\"\"{saved_lesson_reference}\"\"\"

                            المهام والقيود الإلزامية المطلوبة منك أثناء التدقيق والتفتيش (ركز بدقة عالية):

                            1. **منع الغش وتطابق الدفاتر (حاسم جداً):**
                               - يمنع منعاً باتاً أن يقوم تلاميذ مختلفون بإرسال نفس الصور أو نفس الدفتر لسرقة مجهود غيرهم. 
                               - حلل بدقة "بصمة الدفتر البصرية" (نوع خط التلميذ، أسلوب التسطير وهندسة الدفتر، شكل وحواف الأوراق، لون الطاولة أو خلفية الصورة، وزاوية الإضاءة وظلال الهاتف الملقاة). 
                               - كل صورة أرسلها التلميذ يجب أن تكون فريدة تماماً ومختلفة عن الأخرى. إذا كان هناك تكرار لنفس الصورة في نفس الإرسال أو تشابه مريب مع دفاتر تلاميذ آخرين في نفس القسم، ضع تحذيراً باللون الأحمر الداكن في بداية التقرير مكتوب فيه بشكل بارز: "⚠️ تنبيه خطير: اشتباه قوي جداً في غش ونسخ دفتر تلميذ آخر!".

                            2. **التدقيق عنواناً بعنوان وفقرة بفقرة:**
                               - تتبع الصور المرسلة ورقة بورقة وعنواناً بعنوان بناءً على المرجع الأساسي المكتوب أعلاه. تأكد من أن التلميذ نقل جميع العناوين والتعاريف والخاصيات الرياضية (Propriétés) والرموز والمصطلحات المقررة في الدرس.

                            3. **تدقيق حلول التمارين التطبيقية وتصحيحها كاملة:**
                               - تحقق من وجود كل تمرين تطبيقي أو مثال (Exemples / Applications) ورد في المرجع أعلاه.
                               - بما أن مرجع الأستاذ يحتوي على نص التمارين التطبيقية فقط دون حلول جاهزة، يجب عليك (بصفتك خبيراً رياضياً) أن تقوم أولاً بحل التمرين ذهنياً خطوة بخطوة، ثم تتأكد بدقة أن التلميذ قد كتب "التصحيح والحل كاملاً ومقنعاً وبصيغة رياضية صحيحة" داخل الدفتر بخط يده. إذا قام بنقل نص التمرين فقط دون إدراج حله المتكامل, فاعتبر الفقرة ناقصة.
                            
                            أعط تقريراً منظماً وبليغاً باللغة العربية كالتالي:
                            - 🚨 **حالة الأمان ومكافحة الغش:** (تقرير صريح وحازم حول أصلية الدفتر وعدم تكراره)
                            - 📊 **نسبة اكتمال الدرس الإجمالية:** (من 100%)
                            - 📝 **جرد الفقرات والعناوين المكتوبة:** (العناوين المستوفاة والفقرات والتعاريف الناقصة بالترتيب)
                            - 🧮 **وضعية التمارين التطبيقية وتصحيحها المتكامل:** (تقييم كتابة حلول التمارين ومدى صحتها الرياضية والخطوات المتبعة)
                            - 🎨 **ملاحظة التنظيم والترتيب الهيكلي للدفتر:** (تقييم الخط واستعمال الألوان المناسبة للوضوح والترتيب)
                            """
                            
                            model = genai.GenerativeModel("gemini-2.5-flash")
                            imgs = [Image.open(f) for f in up_files]
                            
                            # تم إصلاح الخطأ البرمجي هنا لتمرير المتغيّر الصحيح imgs
                            res = model.generate_content([prompt_instructions, *imgs])
                            
                            client = get_gspread_client()
                            sh = client.open("les classes").worksheet("Reports")
                            sh.append_row([datetime.now().strftime("%Y-%m-%d"), st.session_state.user['name'], st.session_state.user['class'], l_name, res.text, "تم التدقيق بنجاح"])
                            
                            st.markdown("### 📋 تقرير الوزارة الرقمي لتدقيق الدفتر المستلم")
                            st.info(res.text)
                            st.success("تمت مزامنة وتسجيل البيانات وحفظ التقرير التربوي في سجلات الأستاذ السحابية بنجاح ✅")
                    else:
                        st.warning("⚠️ المرجو تزويد المنصة بصور الدفتر أولاً للبدء.")

# --- 5. منطق توزيع وتوجيه مسارات العرض والتحكم ---
if st.session_state.role == "student":
    student_space(df_students, df_lessons)
    
elif st.session_state.role == "admin":
    if not st.session_state.auth:
        st.markdown("<h3 style='color: #1e3a8a;'>🔑 فضاء الأستاذ والإدارة التربوية</h3>", unsafe_allow_html=True)
        admin_pwd = st.text_input("الرجاء إدخال كلمة سر الولوج الإدارية المخصصة:", type="password")
        
        if st.button("تأكيد الهوية وتفعيل الصلاحيات 👨‍🏫", use_container_width=True):
            if admin_pwd == "1234":
                st.session_state.auth = True
                st.session_state.user = {"name": "الأستاذ عبد الباسط المنصوري"}
                st.success("مرحباً بك مجدداً يا أستاذ! تم تحديث الصلاحيات الشاملة بنجاح.")
                st.rerun()
            else:
                st.error("❌ رمز المرور الإداري غير صحيح، يرجى المحاولة مرة أخرى.")
    else:
        admin_space(df_students, df_reports, df_lessons)
