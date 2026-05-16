import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- 1. الإعدادات الأولية والربط السحابي ---
st.set_page_config(page_title="منصة الأستاذ المنصوري", layout="wide")

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
        
    # قراءة المراجع الثابتة من ورقة Lessons (الحل الجديد لمنع الاختفاء)
    try:
        ws_lessons = sh.worksheet("Lessons")
        df_lessons = pd.DataFrame(ws_lessons.get_all_records())
    except:
        # إذا لم تكن الورقة موجودة، يتم إنشاؤها تلقائياً بصفوف افتراضية
        ws_lessons = sh.add_worksheet(title="Lessons", rows="10", cols="3")
        ws_lessons.append_row(["الدرس", "الملاحظات_المرجعية", "تاريخ_التحديث"])
        ws_lessons.append_row(["الدرس 1", "لا توجد ملاحظات مرجعية حالياً", ""])
        ws_lessons.append_row(["الدرس 2", "لا توجد ملاحظات مرجعية حالياً", ""])
        ws_lessons.append_row(["الدرس 3", "لا توجد ملاحظات مرجعية حالياً", ""])
        df_lessons = pd.DataFrame(ws_lessons.get_all_records())
        
    return df_students, df_reports, df_lessons

# تحميل البيانات الشاملة من السحاب
df_students, df_reports, df_lessons = load_data()

# دالة مساعدة لجلب مرجع درس معين من البيانات المحملة
def get_lesson_ref(lesson_name, df_lessons):
    if not df_lessons.empty and "الدرس" in df_lessons.columns:
        row = df_lessons[df_lessons["الدرس"] == lesson_name]
        if not row.empty:
            return row.iloc[0]["الملاحظات_المرجعية"]
    return "لا توجد ملاحظات مرجعية ثابتة محددة لهذا الدرس من طرف الأستاذ."

# --- 2. بناء القائمة الجانبية الموحدة (Sidebar) مع نظام الخروج الفوري ---
with st.sidebar:
    st.markdown("<h2 style='color: #1e3a8a; text-align: center;'>🛡️ بوابة الأستاذ المنصوري</h2>", unsafe_allow_html=True)
    st.divider()
    
    if st.session_state.auth:
        user_display = st.session_state.user.get('name', 'المستخدم')
        st.success(f"✅ متصل الآن: \n\n**{user_display}**")
        if st.session_state.role == "student":
            st.info(f"📊 القسم الحالي: {st.session_state.user.get('class')}")
            
        st.divider()
        if st.button("🚪 تسجيل الخروج من الحساب", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    else:
        st.info("الرجاء اختيار الفضاء المطلوب وتسجيل الدخول:")
        menu = st.radio("انتقل إلى:", ["🏠 فضاء التلميذ", "🔑 فضاء الأستاذ"])
        st.session_state.role = "student" if menu == "🏠 فضاء التلميذ" else "admin"

# --- 3. واجهة الأستاذ الكاملة مع ميزة الحفظ السحابي الدائم للمراجع ---
def admin_space(df_students, df_reports, df_lessons):
    st.markdown("<h1 style='color: #1e3a8a;'>👨‍🏫 لوحة تحكم الأستاذ المنصوري</h1>", unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 الإحصائيات", "📚 إدارة المراجع السحابية", "👥 تتبع التلاميذ", "⚙️ الإعدادات"])
    
    with tab1:
        st.subheader("تحليل النشاط العام")
        col1, col2, col3 = st.columns(3)
        col1.metric("إجمالي التلاميذ", len(df_students))
        col2.metric("إجمالي الإرسالات", len(df_reports))
        col3.metric("الأقسام النشطة", df_students['القسم'].nunique())
        
        if not df_reports.empty:
            fig = px.bar(df_reports.groupby('القسم').size().reset_index(name='العدد'), x='القسم', y='العدد', title="تفاعل الأقسام")
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("إدارة الدروس المرجعية الثابتة (حفظ سحابي دائم)")
        lesson_choice = st.selectbox("اختر الدرس لتحديث مرجعه الثابت:", ["الدرس 1", "الدرس 2", "الدرس 3"])
        
        # جلب المرجع الحالي المخزن في جوجل شيت لعرضه للأستاذ
        current_ref = get_lesson_ref(lesson_choice, df_lessons)
        st.info(f"📝 المرجع الحالي المخزن في السحاب لهذا الدرس:\n\n{current_ref}")
        
        ref_note = st.text_area("اكتب أو عدل التوجيهات والملاحظات التفصيلية للذكاء الاصطناعي (أو الصق نص عناصر الدرس هنا):", height=200, value=current_ref if "لا توجد ملاحظات" not in current_ref else "")
        
        col_btn1, col_btn2 = st.columns(2)
        
        if col_btn1.button("💾 حفظ وتحديث المرجع في السحاب", use_container_width=True):
            with st.spinner("جاري المزامنة مع Google Sheets..."):
                client = get_gspread_client()
                sh = client.open("les classes")
                ws_lessons = sh.worksheet("Lessons")
                
                # البحث عن السطر المقابل للدرس لتحديثه أو إضافته
                cell = ws_lessons.find(lesson_choice)
                if cell:
                    ws_lessons.update_cell(cell.row, 2, ref_note)
                    ws_lessons.update_cell(cell.row, 3, datetime.now().strftime("%Y-%m-%d %H:%M"))
                else:
                    ws_lessons.append_row([lesson_choice, ref_note, datetime.now().strftime("%Y-%m-%d %H:%M")])
                
                st.success(f"تم حفظ مرجع {lesson_choice} بشكل دائم في السحاب بنجاح ولن يختفي أبداً! 🎉")
                st.rerun()
                
        if col_btn2.button("🗑️ حذف الملف (تصفير المرجع الجاري)", use_container_width=True):
            with st.spinner("جاري حذف المرجع من السحاب..."):
                client = get_gspread_client()
                sh = client.open("les classes")
                ws_lessons = sh.worksheet("Lessons")
                cell = ws_lessons.find(lesson_choice)
                if cell:
                    ws_lessons.update_cell(cell.row, 2, "لا توجد ملاحظات مرجعية حالياً")
                    ws_lessons.update_cell(cell.row, 3, "")
                st.success("تم تصفير المرجع بنجاح من قاعدة البيانات.")
                st.rerun()

    with tab3:
        st.subheader("البحث عن تلميذ")
        search_name = st.selectbox("اختر التلميذ لرؤية تاريخه:", df_students['اسم التلميذ'].unique() if 'اسم التلميذ' in df_students.columns else df_students.iloc[:,1].unique())
        student_history = df_reports[df_reports['الاسم'] == search_name]
        st.table(student_history)

    with tab4:
        st.subheader("إدارة المنصة")
        if st.button("تصفير سجل التقارير (حذف الكل)"):
            st.warning("يرجى حذف الصفوف يدوياً من ملف Google Sheets حالياً لضمان الأمان.")

# --- 4. واجهة التلميذ الكاملة ---
def student_space(df_students, df_lessons):
    st.markdown("<h2 style='text-align: center;'>📝 فضاء التلميذ</h2>", unsafe_allow_html=True)
    
    df_students.columns = df_students.columns.str.strip()
    col_class = 'القسم' if 'القسم' in df_students.columns else None
    col_name = 'إسم التلميذ' if 'إسم التلميذ' in df_students.columns else ('اسم التلميذ' if 'اسم التلميذ' in df_students.columns else None)
    col_id = 'رقم التلميذ' if 'رقم التلميذ' in df_students.columns else None

    if not col_class or not col_name or not col_id:
        st.error(f"⚠️ خطأ في أسماء أعمدة ملف الإكسيل. الأعمدة الحالية هي: {df_students.columns.tolist()}")
        return

    if not st.session_state.auth:
        with st.container():
            c1, c2 = st.columns(2)
            sel_class = c1.selectbox("القسم:", ["---"] + df_students[col_class].unique().tolist())
            
            names = df_students[df_students[col_class] == sel_class][col_name].tolist() if sel_class != "---" else []
            sel_name = c2.selectbox("الاسم الكامل:", ["---"] + names)
            pwd = st.text_input("رقم مسار الخاص بك (القن السري):", type="password")
            
            if st.button("تسجيل الدخول والتفعيل 🚀", use_container_width=True):
                if sel_name != "---" and pwd.strip() != "":
                    real_pwd = df_students[df_students[col_name] == sel_name][col_id].values[0]
                    if str(pwd).strip().upper() == str(real_pwd).strip().upper():
                        st.session_state.auth = True
                        st.session_state.user = {"name": sel_name, "class": sel_class}
                        st.rerun()
                    else:
                        st.error("❌ القن السري (رقم مسار) غير صحيح")
                else:
                    st.warning("المرجو ملء جميع معلومات الدخول أولاً.")
                    
    else:
        st.success(f"مرحباً {st.session_state.user['name']} | قسم: {st.session_state.user['class']}")
        
        lesson_tabs = st.tabs(["📘 الدرس 1", "📗 الدرس 2", "📙 الدرس 3"])
        
        for i, tab in enumerate(lesson_tabs):
            with tab:
                l_name = f"الدرس {i+1}"
                st.write(f"ارفع صور {l_name} (الحد الأقصى 20 صورة للدفتر الشخصي)")
                up_files = st.file_uploader(f"اختر الصور لـ {l_name}", accept_multiple_files=True, key=f"up_{l_name}", type=['jpg','jpeg','png'])
                
                if st.button(f"تحليل وإرسال {l_name}", key=f"btn_{l_name}"):
                    if up_files:
                        with st.spinner("🔄 جاري سحب المرجع السحابي وفحص بصمة الدفتر وتحليل التمارين..."):
                            
                            # جلب المرجع الدائم المخزن في السحاب للدرس الحالي ليعتمد عليه Gemini بالكامل
                            saved_lesson_reference = get_lesson_ref(l_name, df_lessons)
                            
                            prompt_instructions = f"""
                            أنت مساعد أستاذ رياضيات عبقري ومراقب صارم جداً مكلف بكشف الغش والنسخ وتدقيق الدفاتر. 
                            التلميذ {st.session_state.user['name']} (القسم: {st.session_state.user['class']}) أرسل صور دفتره لدرس ({l_name}).

                            المرجع الأساسي المعتمد لهذا الدرس والمرفوع من طرف الأستاذ هو:
                            \"\"\"{saved_lesson_reference}\"\"\"

                            المهام والقيود الإلزامية المطلوبة منك أثناء التدقيق والتفتيش (ركز بدقة عالية):

                            1. **منع الغش وتطابق الدفاتر (حاسم جداً):**
                               - يمنع منعاً باتاً أن يقوم تلاميذ مختلفون بإرسال نفس الصور أو نفس الدفتر. 
                               - حلل بدقة "بصمة الدفتر البصرية" (نوع خط التلميذ، طريقة التسطير، شكل وحواف الأوراق، لون الطاولة أو خلفية الصورة، زاوية الإضاءة وظلال اليد الملقاة). 
                               - كل صورة أرسلها التلميذ يجب أن تكون فريدة تماماً ومختلفة عن الأخرى. إذا كان هناك تكرار لنفس الصورة في نفس الإرسال أو تشابه مريب مع دفاتر تلاميذ آخرين، ضع تحذيراً باللون الأحمر الداكن في بداية التقرير مكتوب فيه بشكل بارز: "⚠️ تنبيه: اشتباه قوي جداً في نسخ وتكرار دفتر تلميذ آخر!".

                            2. **التدقيق عنواناً بعنوان وفقرة بفقرة:**
                               - تتبع الصور المرسلة ورقة بورقة وعنواناً بعنوان بناءً على المرجع الأساسي للأستاذ المكتوب أعلاه. تأكد من أن التلميذ نقل جميع العناوين والتعاريف والخاصيات الرياضية (Propriétés) المقررة في الدرس.

                            3. **تدقيق حلول التمارين التطبيقية والتصحيح (هام للغاية):**
                               - تحقق من وجود كل تمرين تطبيقي أو مثال (Exemples / Applications) ورد في المرجع أعلاه.
                               - بما أن مرجع الأستاذ قد يحتوي على نص التمارين التطبيقية فقط دون حلول، يجب عليك (بصفتك خبيراً رياضياً) أن تقوم أولاً بحل التمرين ذهنياً، ثم تتأكد بدقة أن التلميذ قد كتب "التصحيح والحل كاملاً ومقنعاً وبخط يده" داخل الدفتر. إذا قام بنقل نص التمرين فقط دون حل كامل، فاعتبر الفقرة غير مكتملة.

                            أعط تقريراً منظماً باللغة العربية كالتالي:
                            - 🚨 **حالة الأمان ومكافحة الغش:** (تقرير صريح حول أصلية الدفتر وعدم تكراره)
                            - 📊 **نسبة اكتمال الدرس الإجمالية:** (من 100%)
                            - 📝 **جرد الفقرات والعناوين المكتوبة:** (العناوين المستوفاة والفقرات الناقصة بالترتيب)
                            - 🧮 **وضعية التمارين التطبيقية والتصحيح:** (تقييم كتابة حلول التمارين بدقة وصحتها الرياضية والخطوات المتبعة)
                            - 🎨 **ملاحظة التنظيم والترتيب:** (تقييم الخط واستعمال الألوان للوضوح)
                            """
                            
                            model = genai.GenerativeModel("gemini-1.5-flash")
                            imgs = [Image.open(f) for f in up_files]
                            res = model.generate_content([prompt_instructions, *imgs])
                            
                            client = get_gspread_client()
                            sh = client.open("les classes").worksheet("Reports")
                            sh.append_row([datetime.now().strftime("%Y-%m-%d"), st.session_state.user['name'], st.session_state.user['class'], l_name, res.text, "جاري التقييم"])
                            
                            st.markdown("### 📋 نتيجة تدقيق الدفتر الفورية")
                            st.info(res.text)
                            st.success("تم تسجيل ومزامنة البيانات في سجلات الأستاذ بنجاح ✅")
                    else:
                        st.warning("⚠️ المرجو تزويد المنصة بصور الدفتر أولاً.")

# --- 5. منطق توزيع مسارات العرض ---
if st.session_state.role == "student":
    student_space(df_students, df_lessons)
    
elif st.session_state.role == "admin":
    if not st.session_state.auth:
        st.markdown("<h3 style='color: #1e3a8a;'>🔑 فضاء الأستاذ - تسجيل الدخول</h3>", unsafe_allow_html=True)
        admin_pwd = st.text_input("الرجاء إدخال كلمة سر الإدارة الخاصة بك:", type="password")
        
        if st.button("تأكيد الدخول 👨‍🏫", use_container_width=True):
            if admin_pwd == "1234":
                st.session_state.auth = True
                st.session_state.user = {"name": "الأستاذ عبد الباسط المنصوري"}
                st.success("مرحباً بك مجدداً يا أستاذ!")
                st.rerun()
            else:
                st.error("❌ كلمة المرور غير صحيحة، يرجى المحاولة مرة أخرى.")
    else:
        admin_space(df_students, df_reports, df_lessons)
