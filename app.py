import random
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import os
import uuid
import requests
from io import BytesIO
from sqlalchemy import create_engine, text
from PIL import Image, ImageOps
from supabase import create_client

# Настройка параметров страницы
st.set_page_config(
    page_title="Подари Новый год", 
    layout="wide", 
    page_icon="🎁",
    initial_sidebar_state="collapsed"
)

# Функция для загрузки внешнего файла со стилями
def load_css(file_name):
    """Читает CSS-файл и внедряет его в страницу Streamlit."""
    with open(file_name, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("styles.css")

# Кэшируем создание подключения к базе данных
@st.cache_resource
def get_engine():
    return create_engine(st.secrets["DB_URL"])

engine = get_engine()

# Инициализация клиента Supabase для загрузки фотографий
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_SECRET_KEY"])

# Ссылки на платежные системы
PAYMENT_LINK_SBER = "https://messenger.sbrf.ru/sl/sJx7ApERw6maUQxmU"
PAYMENT_LINK_TBANK = "https://t.tb.ru/pm_short/5bXCzeGZek5"

# Пароль для входа в панель волонтера
VOLUNTEER_PASSWORD = st.secrets["VOLUNTEER_PASSWORD"]

# --- ФОНОВЫЕ ЭЛЕМЕНТЫ (снежинки и гирлянды) ---
def init_background_elements():
    if 'snowflakes_html' not in st.session_state:
        html = '<div class="snow-container">'
        for _ in range(40):
            left = random.uniform(0, 100)
            duration = random.uniform(5, 15)
            delay = random.uniform(0, 10)
            size = random.uniform(0.8, 2.0)
            html += f'<div class="snowflake" style="left: {left}vw; animation-duration: {duration}s; animation-delay: -{delay}s; font-size: {size}rem;">❄️</div>'
        html += '</div>'
        st.session_state.snowflakes_html = html

    if 'garlands_html' not in st.session_state:
        garland_left = """
        <div class="garland garland-left">
            <svg viewBox="0 0 200 150">
                <path d="M 0 0 Q 100 150 200 0" fill="none" stroke="#2C3E50" stroke-width="2" opacity="0.5"/>
                <circle cx="20" cy="50" r="7" class="bulb b-red delay-0"/>
                <circle cx="60" cy="90" r="7" class="bulb b-yellow delay-1"/>
                <circle cx="100" cy="110" r="7" class="bulb b-green delay-2"/>
                <circle cx="140" cy="90" r="7" class="bulb b-blue delay-3"/>
                <circle cx="180" cy="50" r="7" class="bulb b-pink delay-4"/>
            </svg>
        </div>
        """
        garland_right_1 = """
        <div class="garland garland-right-1">
            <svg viewBox="0 0 250 180">
                <path d="M 0 0 Q 125 180 250 0" fill="none" stroke="#2C3E50" stroke-width="2" opacity="0.5"/>
                <circle cx="25" cy="60" r="8" class="bulb b-pink delay-1"/>
                <circle cx="75" cy="110" r="8" class="bulb b-red delay-3"/>
                <circle cx="125" cy="130" r="8" class="bulb b-yellow delay-0"/>
                <circle cx="175" cy="110" r="8" class="bulb b-green delay-2"/>
                <circle cx="225" cy="60" r="8" class="bulb b-blue delay-4"/>
            </svg>
        </div>
        """
        garland_right_2 = """
        <div class="garland garland-right-2">
            <svg viewBox="0 0 150 120">
                <path d="M 0 0 Q 75 120 150 0" fill="none" stroke="#2C3E50" stroke-width="2" opacity="0.5"/>
                <circle cx="15" cy="40" r="6" class="bulb b-green delay-2"/>
                <circle cx="45" cy="70" r="6" class="bulb b-blue delay-0"/>
                <circle cx="75" cy="85" r="6" class="bulb b-pink delay-4"/>
                <circle cx="105" cy="70" r="6" class="bulb b-red delay-1"/>
                <circle cx="135" cy="40" r="6" class="bulb b-yellow delay-3"/>
            </svg>
        </div>
        """
        st.session_state.garlands_html = garland_left + garland_right_1 + garland_right_2

init_background_elements()
st.markdown(st.session_state.snowflakes_html, unsafe_allow_html=True)
st.markdown(st.session_state.garlands_html, unsafe_allow_html=True)

# --- ИНИЦИАЛИЗАЦИЯ ПЕРЕМЕННЫХ СОСТОЯНИЯ ---
defaults = {
    'show_payment_dialog': False,
    'payment_dialog_option': None,
    'show_purchase_dialog': False,
    'purchase_dialog_row_id': None,
    'purchase_dialog_row_name': None,
    'volunteer_auth': False,
    'view_image_path': None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# --- БОКОВАЯ ПАНЕЛЬ ВОЛОНТЕРА ---
with st.sidebar:
    st.subheader("🔐 Панель волонтёра")

    if st.session_state.volunteer_auth:
        st.success("✅ Вы вошли как волонтёр")
        st.caption("Вам доступны панели управления.")
        if st.button("🚪 Выйти", use_container_width=True):
            st.session_state.volunteer_auth = False
            st.rerun()
    else:
        st.caption("Доступ только для координаторов фонда.")
        with st.form("volunteer_login_form"):
            pwd = st.text_input("Пароль", type="password", label_visibility="collapsed", placeholder="Введите пароль")
            login = st.form_submit_button("Войти", use_container_width=True, type="primary")
            if login:
                if pwd == VOLUNTEER_PASSWORD:
                    st.session_state.volunteer_auth = True
                    st.rerun()
                else:
                    st.error("❌ Неверный пароль")

    st.divider()
    st.caption("🎄 Акция «Подари мечту»")

# --- ЗАГОЛОВОК И ТАЙМЕР ---
col_title, col_timer = st.columns([3, 1], vertical_alignment="center")
with col_title:
    st.markdown("""
    <h1 style='font-size: 2.2rem; margin-bottom: 0; padding-bottom: 0;'>
        🎁 Письмо Деду Морозу
    </h1>
    <p style='font-size: 1.2rem; color: #E63946; font-weight: 600; margin-top: 5px; margin-bottom: 15px;'>
        Для детей с онко-гематологией
    </p>
    """, unsafe_allow_html=True)
    st.caption("Выберите письмо ребёнка и помогите исполнить его мечту ✨")
with col_timer:
    with open("header.html", "r", encoding="utf-8") as f:
        components.html(f.read(), height=110)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
@st.cache_data(ttl=60)
def get_letters():
    return pd.read_sql("SELECT * FROM cildrens_letters ORDER BY id", con=engine)

def reserve_letter(letter_id, option, name, phone, service, pvz, d_date):
    with engine.begin() as conn:
        query = text("""
            UPDATE cildrens_letters
            SET status = 'reserved', payment_option = :opt, volunteer_name = :name, 
                volunteer_phone = :phone, delivery_service = :service, 
                delivery_pvz = :pvz, delivery_date = :d_date
            WHERE id = :id AND status = 'free'
        """)
        res = conn.execute(query, {
            "opt": option, "name": name, "phone": phone, 
            "service": service, "pvz": pvz, "d_date": d_date, "id": letter_id
        })
        get_letters.clear()
        return res.rowcount > 0

def mark_received(letter_id, received: bool):
    new_status = 'received' if received else 'free' 
    with engine.begin() as conn:
        conn.execute(text("UPDATE cildrens_letters SET status = :st WHERE id = :id"), {"st": new_status, "id": letter_id})
    get_letters.clear()

def delete_letter(letter_id, photo_url):
    if photo_url and "supabase.co" in photo_url:
        try:
            filename = photo_url.split("/")[-1]
            supabase.storage.from_("letters-photos").remove([filename])
        except Exception as e:
            st.warning(f"Не удалось удалить фото из хранилища: {e}")
            
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM cildrens_letters WHERE id = :id"), {"id": letter_id})
    get_letters.clear()

# Функция поиска (используется только для удаления)
def filter_letters_for_deletion(df, query):
    if not query:
        return df
    query = str(query).lower()
    mask = df['child_name'].str.lower().str.contains(query, na=False) | df['id'].astype(str).str.contains(query)
    return df[mask]

def format_age(age):
    if age is None or pd.isna(age): return None
    age = int(age)
    if age == 0: return None
    if 11 <= age % 100 <= 14: return f"{age} лет"
    last = age % 10
    if last == 1: return f"{age} год"
    elif last in (2, 3, 4): return f"{age} года"
    else: return f"{age} лет"

@st.cache_data
def load_image_portrait(path):
    if path.startswith("http"):
        response = requests.get(path)
        img = Image.open(BytesIO(response.content))
    else:
        img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    return img

# --- МОДАЛЬНЫЕ ОКНА ---
@st.dialog("📩 Письмо ребёнка")
def view_image_dialog():
    img_path = st.session_state.get('view_image_path')
    if img_path:
        try:
            img = load_image_portrait(img_path)
            st.image(img, use_column_width=True)
        except Exception as e:
            st.error(f"Не удалось загрузить фото: {e}")

@st.dialog("💳 Оплата")
def payment_dialog():
    option = st.session_state.payment_dialog_option
    st.write(f"**Назначение перевода:** {option}")

    if option == "Скинуть деньги на подарок":
        st.caption("Переведите сумму, которая пойдёт на подарки детям. Волонтёр фонда распределит средства.")
    else:
        st.caption("Переведите любую сумму в общий фонд. Волонтёр фонда распределит средства на подарки.")

    st.divider()
    st.write("**Выберите удобный способ перевода:**")
    
    col1, col2 = st.columns(2)
    with col1:
        st.link_button("🟢 Сбербанк", PAYMENT_LINK_SBER, use_container_width=True, type="primary")
    with col2:
        st.link_button("🟡 Т-Банк", PAYMENT_LINK_TBANK, use_container_width=True, type="primary")

    st.divider()
    st.caption("После перевода закройте это окно. Спасибо за помощь! ❤️")

    if st.button("Закрыть", use_container_width=True):
        st.session_state.show_payment_dialog = False
        st.rerun()

@st.dialog("🛒 Купить подарок самому")
def purchase_dialog():
    row_id = st.session_state.purchase_dialog_row_id
    child_name = st.session_state.purchase_dialog_row_name

    st.info(f"Вы помогаете ребёнку: **{child_name}**")
    st.write("Заполните данные — координатор свяжется с вами по телефону.")

    with st.form(key=f"purchase_form_{row_id}"):
        v_phone = st.text_input("Телефон для связи")
        v_service = st.selectbox("Служба доставки", ["Wildberries", "Ozon", "Яндекс Маркет", "СДЭК", "Авито"])
        v_pvz = st.text_input("Адрес или название ПВЗ")
        v_date = st.date_input("Дата прибытия заказа", value=None)

        submit = st.form_submit_button("Забронировать и купить", type="primary", use_container_width=True)

        if submit:
            if v_phone and v_pvz and v_date and v_service:
                if reserve_letter(row_id, "Купить подарок самому", "Аноним", v_phone, v_service, v_pvz, v_date):
                    st.session_state.show_purchase_dialog = False
                    st.success("✅ Вы забронировали подарок! Спасибо!")
                    st.rerun()
                else:
                    st.error("Не удалось забронировать. Возможно, подарок уже заняли.")
            else:
                st.error("Пожалуйста, заполните все поля")

# --- БЛОК ВЫБОРА ВАРИАНТА ПОМОЩИ ---
def render_option_selector(row):
    st.write("**Как вы хотите помочь?**")

    if st.button("💝 Скинуть деньги на подарок", key=f"optbtn_{row['id']}_0", use_container_width=True):
        st.session_state.payment_dialog_option = "Скинуть деньги на подарок"
        st.session_state.show_payment_dialog = True
        st.rerun()

    if st.button("🎁 Скинуть деньги на общий сбор", key=f"optbtn_{row['id']}_1", use_container_width=True):
        st.session_state.payment_dialog_option = "Скинуть деньги на общий сбор"
        st.session_state.show_payment_dialog = True
        st.rerun()

    if st.button("🛒 Купить подарок самому", key=f"optbtn_{row['id']}_2", use_container_width=True):
        st.session_state.purchase_dialog_row_id = row['id']
        st.session_state.purchase_dialog_row_name = row['child_name']
        st.session_state.show_purchase_dialog = True
        st.rerun()

# --- ОСНОВНОЙ ИНТЕРФЕЙС ---
df = get_letters()

if st.session_state.volunteer_auth:
    tab1, tab2, tab_manage, tab3 = st.tabs(["✉️ Выбрать письмо", "📦 Панель волонтера", "✏️ Управление письмами", "📖 Инструкция"])
else:
    tab1, tab3 = st.tabs(["✉️ Выбрать письмо", "📖 Инструкция"])
    tab2 = None
    tab_manage = None

# Вкладка 1: Карточки с письмами
with tab1:
    cols = st.columns(3)
    for index, row in df.iterrows():
        with cols[index % 3]:
            with st.container(border=True):
                if pd.notna(row.get('photo_url')) and row['photo_url']:
                    img_path = row['photo_url']
                else:
                    img_filename = row['photo_filename']
                    img_path = f"static/{img_filename}"
                    
                is_valid_image = img_path.startswith("http") or os.path.exists(img_path)

                if is_valid_image:
                    if st.button("📩 Читать письмо", key=f"read_{row['id']}", use_container_width=True, type="primary"):
                        st.session_state.view_image_path = img_path
                        st.rerun()
                else:
                    st.info("Фото скоро появится")

                age_str = format_age(row['child_age'])
                name_display = f"{row['child_name']}, {age_str}" if age_str else row['child_name']
                st.subheader(name_display)

                st.divider()

                if row['status'] == 'free':
                    render_option_selector(row)
                elif row['status'] == 'reserved':
                    st.warning("⏳ Уже забронировано")
                    if row['volunteer_name'] and row['volunteer_name'] != "Аноним":
                        st.caption(f"Забрал(а): {row['volunteer_name']}")
                    if row['payment_option'] == "Купить подарок самому":
                        st.write(f"🚚 Доставка: {row['delivery_service']}")
                        st.write(f"📦 ПВЗ: {row['delivery_pvz']}")
                        st.write(f"📅 Дата: {row['delivery_date']}")
                elif row['status'] == 'received':
                    st.success("✅ Подарок получен фондом!")
                    st.caption("Окно заблокировано.")

    # Вызов модальных окон
    if st.session_state.get('view_image_path'):
        view_image_dialog()
        st.session_state.view_image_path = None

    if st.session_state.show_payment_dialog:
        st.session_state.show_payment_dialog = False
        payment_dialog()

    if st.session_state.show_purchase_dialog and st.session_state.purchase_dialog_row_id is not None:
        st.session_state.show_purchase_dialog = False
        purchase_dialog()

# Вкладка 2: Панель координатора
if st.session_state.volunteer_auth and tab2 is not None:
    with tab2:
        st.header("Панель координатора")
        st.write("Здесь волонтёры отмечают, пришли ли заказы в ПВЗ.")

        df_reserved = df[df['status'] == 'reserved']

        if df_reserved.empty:
            st.info("Нет забронированных подарков, ожидающих получения.")
        else:
            for index, row in df_reserved.iterrows():
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        age_str = format_age(row['child_age'])
                        name_display = f"{row['child_name']}, {age_str}" if age_str else row['child_name']
                        st.write(f"**{name_display}**")
                        if row['volunteer_name'] and row['volunteer_name'] != "Аноним":
                            st.write(f"Заказал: {row['volunteer_name']}")
                        st.write(f"📞 Телефон: {row['volunteer_phone']}")
                        st.write(f"🚚 Доставка: {row['delivery_service']}")
                        st.write(f"📦 ПВЗ: {row['delivery_pvz']}")
                        st.write(f"📅 Ожидается: {row['delivery_date']}")
                    with col2:
                        st.write("Подарок пришёл?")
                        if st.button("Да", key=f"yes_{row['id']}", type="primary", use_container_width=True):
                            mark_received(row['id'], True)
                            st.rerun()
                        if st.button("Нет (вернуть)", key=f"no_{row['id']}", use_container_width=True):
                            mark_received(row['id'], False)
                            st.rerun()

# Вкладка УПРАВЛЕНИЯ (Добавление и Удаление с поиском)
if st.session_state.volunteer_auth and tab_manage is not None:
    with tab_manage:
        st.header("Управление письмами")
        
        # Секция добавления
        with st.expander("➕ Добавить новое письмо", expanded=False):
            with st.form("add_letter_form", clear_on_submit=True):
                child_name = st.text_input("Имя ребёнка*")
                child_age = st.number_input("Возраст (полных лет)", min_value=0, max_value=18, step=1)
                letter_text = st.text_area("Текст письма (по желанию)", help="Можно оставить пустым.")
                uploaded_file = st.file_uploader("Фотография письма*", type=["jpg", "jpeg", "png"])
                
                submitted = st.form_submit_button("Сохранить письмо", type="primary", use_container_width=True)
                
                if submitted:
                    if not child_name or not uploaded_file:
                        st.error("Пожалуйста, заполните имя и загрузите фото.")
                    else:
                        try:
                            file_extension = uploaded_file.name.split(".")[-1]
                            file_name = f"{uuid.uuid4()}.{file_extension}"
                            
                            file_bytes = uploaded_file.getvalue()
                            supabase.storage.from_("letters-photos").upload(
                                path=file_name,
                                file=file_bytes,
                                file_options={"content-type": uploaded_file.type}
                            )
                            
                            photo_url = supabase.storage.from_("letters-photos").get_public_url(file_name)
                            
                            with engine.begin() as conn:
                                conn.execute(text("""
                                    INSERT INTO cildrens_letters 
                                    (child_name, child_age, letter_text, photo_url, status)
                                    VALUES (:name, :age, :text, :url, 'free')
                                """), {
                                    "name": child_name, 
                                    "age": child_age, 
                                    "text": letter_text if letter_text else None, 
                                    "url": photo_url
                                })
                            
                            st.success(f"Письмо для {child_name} успешно добавлено!")
                            get_letters.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка при сохранении: {e}")

        st.divider()
        
        # Секция удаления с поиском
        st.subheader("🗑️ Удалить письмо")
        st.write("Найдите письмо по имени или ID, чтобы удалить его с сайта и из базы данных.")
        
        # Поиск для удаления
        search_del = st.text_input("🔍 Поиск для удаления", placeholder="Введите имя ребёнка или ID...", key="search_del")
        filtered_del_df = filter_letters_for_deletion(df, search_del)

        if filtered_del_df.empty:
            st.info("Письма по вашему запросу не найдены.")
        else:
            for index, row in filtered_del_df.iterrows():
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 2, 1])
                    with col1:
                        st.write(f"**{row['child_name']}** (ID: {row['id']})")
                    with col2:
                        st.write(f"Статус: {row['status']}")
                    with col3:
                        confirm_key = f"confirm_del_{row['id']}"
                        if st.session_state.get(confirm_key):
                            if st.button("Да, удалить", key=f"yes_del_{row['id']}", type="primary", use_container_width=True):
                                delete_letter(row['id'], row.get('photo_url'))
                                st.session_state[confirm_key] = False
                                st.success(f"Письмо {row['child_name']} удалено.")
                                st.rerun()
                            if st.button("Отмена", key=f"no_del_{row['id']}", use_container_width=True):
                                st.session_state[confirm_key] = False
                                st.rerun()
                        else:
                            if st.button("🗑️ Удалить", key=f"btn_del_{row['id']}", use_container_width=True):
                                st.session_state[confirm_key] = True
                                st.rerun()

# Вкладка 3: Инструкция и реквизиты
if tab3 is not None:
    with tab3:
        st.header("Как это работает?")
        st.markdown("""
        1. Нажмите **«📩 Читать письмо»** — фотография откроется в новом окне.
        2. Выберите удобный вариант помощи:
           - 💝 **Скинуть деньги на подарок** — откроется окно с ссылками на Сбербанк и Т-Банк.
           - 🎁 **Скинуть деньги на общий сбор** — откроется окно с ссылками на Сбербанк и Т-Банк для перевода в общий фонд.
           - 🛒 **Купить подарок самому** — откроется форма с телефоном, выбором службы доставки, адресом ПВЗ и датой прибытия. **ФИО указывать не нужно**.
        3. **Важно про варианты 1 и 2:** деньги идут в общий фонд, волонтёр распределяет их на подарки детям.
        4. **Про вариант 3:** после заполнения формы подарок закрепляется за вами. Координатор свяжется по указанному телефону.

        *Пожалуйста, если ваши планы изменились, сообщите координатору — подарок ждёт ребёнок.*
        """)

        st.divider()
        st.subheader("💳 Реквизиты для помощи")
        st.write("Вы можете перевести средства на покупку подарков по удобной для вас ссылке:")
        
        col1, col2 = st.columns(2)
        with col1:
            st.link_button("🟢 Перевести через Сбербанк", PAYMENT_LINK_SBER, use_container_width=True, type="primary")
        with col2:
            st.link_button("🟡 Перевести через Т-Банк", PAYMENT_LINK_TBANK, use_container_width=True, type="primary")
