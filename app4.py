import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- 1. الإعدادات الأولية والربط السحابي ---
# جعل دالة set_page_config أول سطر تشغيلي لـ Streamlit لضمان عدم ظهور أخطاء
st.set_page_config(page_title="منصة الأستاذ المنصوري", layout="wide")

# إعداد حماية الخصوصية ومفتاح Gemini الذكي
genai.configure(api_key="AIzaSyAwhWzEseoWORwT8eBLWBNB57wkuFxaBeA")

# تهيئة متغيرات الجلسة (Session State) لربط عمليات الدخول والخروج بنجاح
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
    df_students = pd.DataFrame(sh.sheet1.get_all_records())
    try:
        df_reports = pd.DataFrame(sh.worksheet("Reports").get_all_records())
    except:
        df_reports = pd.DataFrame(columns=["التاريخ", "الاسم", "القسم", "الدرس", "التقرير", "النسبة"])
    return df_students, df_reports

# تحميل البيانات من محرك جوجل
df_students, df_reports = load_data()

# --- 2. بناء القائمة الجانبية الموحدة (Sidebar) مع نظام الخروج الفوري ---
with st.sidebar:
    st.markdown("<h2 style='color: #1e3a8a; text-align: center;'>🛡️ بوابة الأستاذ المنصوري</h2>", unsafe_allow_html=True)
    st.divider()
    
    # حالة (أ) : إذا كان هناك مستخدم متصل بالفعل (تلميذ أو أستاذ)
    if st.session_state.auth:
        user_display = st.session_state.user.get('name', 'المستخدم')
        st.success(f"✅ متصل الآن: \n\n**{user_display}**")
        if st.session_state.role == "student":
            st.info(f"📊 القسم الحالي: {st.session_state.user.get('class')}")
            
        st.divider()
        # زر تسجيل الخروج الحاسم لمسح الجلسة ومنع التلاميذ الآخرين من العبث بالحساب
        if st.button("🚪 تسجيل الخروج من الحساب", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
            
    # حالة (ب) : لم يتم تسجيل الدخول بعد، تظهر خيارات اختيار الفضاء
    else:
        st.info("الرجاء اختيار الفضاء المطلوب وتسجيل الدخول:")
        menu = st.radio("انتقل إلى:", ["🏠 فضاء التلميذ", "🔑 فضاء الأستاذ"])
        st.session_state.role = "student" if menu == "🏠 فضاء التلميذ" else "admin"

# --- 3. واجهة الأستاذ الكاملة ---
def admin_space(df_students, df_reports):
    st.markdown("<h1 style='color: #1e3a8a;'>👨‍🏫 لوحة تحكم الأستاذ المنصوري</h1>", unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 الإحصائيات", "📚 إدارة المراجع", "👥 تتبع التلاميذ", "⚙️ الإعدادات"])
    
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
        st.subheader("رفع الدروس المرجعية (Model)")
        lesson_choice = st.selectbox("اختر الدرس لتحديث مرجعه:", ["الدرس 1", "الدرس 2", "الدرس 3"])
        ref_files = st.file_uploader(f"ارفع صور درس الأستاذ المرجعي لـ {lesson_choice}:", accept_multiple_files=True, type=['jpg','png','pdf'])
        ref_note = st.text_area("ملاحظات إضافية للذكاء الاصطناعي حول هذا الدرس:")
        if st.button("حفظ وتحديث المرجع"):
            st.session_state[f"ref_img_{lesson_choice}"] = ref_files
            st.session_state[f"ref_note_{lesson_choice}"] = ref_note
            st.success(f"تم تحديث مرجع {lesson_choice} بنجاح ✅")

    with tab3:
        st.subheader("البحث عن تلميذ")
        search_name = st.selectbox("اختر التلميذ لرؤية تاريخه:", df_students['اسم التلميذ'].unique() if 'اسم التلميذ' in df_students.columns else df_students.iloc[:,1].unique())
        student_history = df_reports[df_reports['الاسم'] == search_name]
        st.table(student_history)

    with tab4:
        st.subheader("إدارة المنصة")
        if st.button("تصفير سجل التقارير (حذف الكل)"):
            st.warning("يرجى حذف الصفوف يدوياً من ملف Google Sheets حالياً لضمان الأمان.")

# --- 4. واجهة التلميذ الكاملة (تشمل رادار كشف الغش المتطور وتدقيق التمارين) ---
def student_space(df_students):
    st.markdown("<h2 style='text-align: center;'>📝 فضاء التلميذ</h2>", unsafe_allow_html=True)
    
    # تنظيف أسماء الأعمدة لضمان دقة العمل والمطابقة المستقرة
    df_students.columns = df_students.columns.str.strip()
    
    col_class = 'القسم' if 'القسم' in df_students.columns else None
    col_name = 'إسم التلميذ' if 'إسم التلميذ' in df_students.columns else ('اسم التلميذ' if 'اسم التلميذ' in df_students.columns else None)
    col_id = 'رقم التلميذ' if 'رقم التلميذ' in df_students.columns else None

    if not col_class or not col_name or not col_id:
        st.error(f"⚠️ خطأ في أسماء أعمدة ملف الإكسيل. الأعمدة الحالية هي: {df_students.columns.tolist()}")
        st.info("يرجى التأكد من تسمية الأعمدة بـ: رقم التلميذ، إسم التلميذ، القسم")
        return

    # إذا لم يسجل التلميذ دخوله بعد
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
                    
    # فضاء المعاينة والرفع الفعلي بعد نجاح التحقق والاتصال بخلفية الحساب
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
                        with st.spinner("🔄 جاري فحص بصمة الدفتر وتحليل التمارين الرياضية عنواناً بعنوان..."):
                            
                            # بناء برومبت الأستاذ المنصوري الصارم والذكي لتوجيه النموذج
                            prompt_instructions = f"""
                            أنت مساعد أستاذ رياضيات عبقري ومراقب صارم جداً مكلف بكشف الغش والنسخ وتدقيق الدفاتر. 
                            التلميذ {st.session_state.user['name']} (القسم: {st.session_state.user['class']}) أرسل صور دفتره لدرس ({l_name}).

                            المهام والقيود الإلزامية المطلوبة منك أثناء التدقيق والتفتيش (ركز بدقة):

                            1. **منع الغش وتطابق الدفاتر (حاسم جداً):**
                               - يمنع منعاً باتاً أن يقوم تلاميذ مختلفون بإرسال نفس الصور أو نفس الدفتر. 
                               - حلل بدقة "بصمة الدفتر البصرية" (نوع خط التلميذ، طريقة التسطير، شكل وحواف الأوراق، لون الطاولة أو خلفية الصورة، زاوية الإضاءة وظلال اليد الملقاة). 
                               - كل صورة أرسلها التلميذ يجب أن تكون فريدة تماماً ومختلفة عن الأخرى. إذا كان هناك تكرار لنفس الصورة في نفس الإرسال أو تشابه مريب مع دفاتر تلاميذ آخرين، ضع تحذيراً باللون الأحمر الداكن في بداية التقرير مكتوب فيه بشكل بارز: "⚠️ تنبيه: اشتباه قوي جداً في نسخ وتكرار دفتر تلميذ آخر!".

                            2. **التدقيق عنواناً بعنوان وفقرة بفقرة:**
                               - تتبع الصور المرسلة ورقة بورقة وعنواناً بعنوان. تأكد من أن التلميذ نقل جميع العناوين والتعاريف والخاصيات الرياضية (Propriétés) المقررة في درس الأستاذ.

                            3. **تدقيق حلول التمارين التطبيقية والتصحيح (هام للغاية):**
                               - تحقق من وجود كل تمرين تطبيقي أو مثال (Exemples / Applications) ورد في محتوى الدرس.
                               - بما أن ملف الأستاذ المرجعي يحتوي على نص التمارين التطبيقية فقط دون حلول، يجب عليك (بصفتك خبيراً رياضياً) أن تقوم أولاً بحل التمرين ذهنياً، ثم تتأكد بدقة أن التلميذ قد كتب "التصحيح والحل كاملاً ومقنعاً وبخط يده" داخل الدفتر. إذا قام بنقل نص التمرين فقط دون حل كامل، فاعتبر الفقرة غير مكتملة.

                            أعط تقريراً منظماً باللغة العربية كالتالي:
                            - 🚨 **حالة الأمان ومكافحة الغش:** (تقرير صريح حول أصلية الدفتر وعدم تكراره)
                            - 📊 **نسبة اكتمال الدرس الإجمالية:** (من 100%)
                            - 📝 **جرد الفقرات والعناوين المكتوبة:** (العناوين المستوفاة والفقرات الناقصة)
                            - 🧮 **وضعية التمارين التطبيقية والتصحيح:** (تقييم كتابة حلول التمارين بدقة وصحتها الرياضية والخطوات المتبعة)
                            - 🎨 **ملاحظة التنظيم والترتيب:** (تقييم الخط واستعمال الألوان للوضوح)
                            """
                            
                            model = genai.GenerativeModel("gemini-2.5-flash")
                            imgs = [Image.open(f) for f in up_files]
                            res = model.generate_content([prompt_instructions, *imgs])
                            
                            # استخراج السجل التلقائي وحفظ النتائج في صفحة السجلات بملف جوجل شيت
                            client = get_gspread_client()
                            sh = client.open("les classes").worksheet("Reports")
                            sh.append_row([datetime.now().strftime("%Y-%m-%d"), st.session_state.user['name'], st.session_state.user['class'], l_name, res.text, "جاري التقييم"])
                            
                            st.markdown("### 📋 نتيجة تدقيق الدفتر الفورية")
                            st.info(res.text)
                            st.success("تم تسجيل ومزامنة البيانات في سجلات الأستاذ بنجاح ✅")
                    else:
                        st.warning("⚠️ المرجو تزويد المنصة بصور الدفتر أولاً.")

# --- 5. منطق توزيع وتوجيه مسارات العرض والتنقل الإداري ---
if st.session_state.role == "student":
    student_space(df_students)
    
elif st.session_state.role == "admin":
    # إذا لم يكن الأستاذ قد سجل دخوله بالرقم السري بعد
    if not st.session_state.auth:
        st.markdown("<h3 style='color: #1e3a8a;'>🔑 فضاء الأستاذ - تسجيل الدخول</h3>", unsafe_allow_html=True)
        admin_pwd = st.text_input("الرجاء إدخال كلمة سر الإدارة الخاصة بك:", type="password")
        
        if st.button("تأكيد الدخول 👨‍🏫", use_container_width=True):
            if admin_pwd == "1234": # يمكنك تغييرها بأي رقم تريده لاحقاً
                st.session_state.auth = True
                st.session_state.user = {"name": "الأستاذ عبد الباسط المنصوري"}
                st.success("مرحباً بك مجدداً يا أستاذ! تم فتح الصلاحيات المتقدمة.")
                st.rerun()
            else:
                st.error("❌ كلمة المرور غير صحيحة، يرجى المحاولة مرة أخرى.")
    else:
        # عرض لوحة التحكم الكاملة بعد التحقق الإداري الناجح
        admin_space(df_students, df_reports)
