import streamlit as st
import pandas as pd
import os
from sqlalchemy import create_engine, text

# --- НАСТРОЙКИ ---
# Читаем данные для подключения из секретов
DB_URL = st.secrets["DB_URL"]
engine = create_engine(DB_URL)

PAYMENT_LINK = "https://example.com/pay"

st.set_page_config(page_title="Подари Новый год", layout="wide", page_icon="🎁")

try:
    VOLUNTEER_PASSWORD = st.secrets["VOLUNTEER_PASSWORD"]
except (KeyError, FileNotFoundError):
    VOLUNTEER_PASSWORD = "volunteer2024"

# --- СТИЛИ ---
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(180deg, #FFFBF5 0%, #FFE8E0 100%);
    }
    h1, h2, h3 {
        color: #2C3E50 !important;
        font-weight: 700 !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        min-height: 560px;
        background-color: #FFFFFF !important;
        border-radius: 14px !important;
        box-shadow: 0 4px 14px rgba(230, 57, 70, 0.08) !important;
        border: 1px solid #FFD4CC !important;
        padding: 1.2rem !important;
    }
    .letter-link {
        display: block;
        padding: 0.6rem 1rem;
        background-color: #E63946;
        color: white !important;
        text-decoration: none !important;
        border-radius: 0.6rem;
        text-align: center;
        font-family: sans-serif;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.15s;
        margin-bottom: 0.5rem;
        box-shadow: 0 2px 6px rgba(230, 57, 70, 0.25);
    }
    .letter-link:hover {
        background-color: #C1272D;
        transform: translateY(-1px);
        box-shadow: 0 4px 10px rgba(230, 57, 70, 0.35);
    }
    .stButton > button, .stLinkButton > a {
        border-radius: 0.6rem !important;
        font-weight: 500 !important;
        transition: all 0.15s !important;
    }
    .stButton > button[kind="secondary"] {
        background-color: #FFE8E0 !important;
        color: #2C3E50 !important;
        border: 1px solid #FFD4CC !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background-color: #FFD4CC !important;
        border-color: #E63946 !important;
    }
    .stButton > button[kind="primary"] {
        background-color: #E63946 !important;
        color: white !important;
        border: 1px solid #E63946 !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #C1272D !important;
        border-color: #C1272D !important;
    }
    .stAlert { border-radius: 0.6rem !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        border-radius: 0.6rem 0.6rem 0 0 !important;
        padding: 0.6rem 1.2rem !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- ИНИЦИАЛИЗАЦИЯ СОСТОЯНИЯ (до sidebar!) ---
defaults = {
    'show_payment_dialog': False,
    'payment_dialog_option': None,
    'show_purchase_dialog': False,
    'purchase_dialog_row_id': None,
    'purchase_dialog_row_name': None,
    'volunteer_auth': False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# --- БОКОВАЯ ПАНЕЛЬ: ВХОД ДЛЯ ВОЛОНТЁРОВ ---
with st.sidebar:
    st.subheader("🔐 Панель волонтёра")

    if st.session_state.volunteer_auth:
        st.success("✅ Вы вошли как волонтёр")
        st.caption("Вам доступна вкладка «📦 Панель волонтера».")
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

st.title("🎁 Новогодняя акция: Подари мечту")
st.caption("Выберите письмо ребёнка и помогите исполнить его мечту ✨")

# --- ФУНКЦИИ ---
def get_letters():
    return pd.read_sql("SELECT * FROM cildrens_letters ORDER BY id", con=engine)

def reserve_letter(letter_id, option, name, phone, pvz, d_date):
    """Резервирует письмо. Используется ТОЛЬКО для варианта 3."""
    with engine.begin() as conn:
        query = text("""
            UPDATE cildrens_letters
            SET status = 'reserved', payment_option = :opt, volunteer_name = :name, 
                volunteer_phone = :phone, delivery_pvz = :pvz, delivery_date = :d_date
            WHERE id = :id AND status = 'free'
        """)
        res = conn.execute(query, {
            "opt": option, "name": name, "phone": phone, 
            "pvz": pvz, "d_date": d_date, "id": letter_id
        })
        return res.rowcount > 0

def mark_received(letter_id, received: bool):
    new_status = 'received' if received else 'free' 
    with engine.begin() as conn:
        conn.execute(text("UPDATE cildrens_letters SET status = :st WHERE id = :id"), {"st": new_status, "id": letter_id})

def format_age(age):
    if age is None or pd.isna(age):
        return None
    age = int(age)
    if age == 0:
        return None
    if 11 <= age % 100 <= 14:
        return f"{age} лет"
    last = age % 10
    if last == 1:
        return f"{age} год"
    elif last in (2, 3, 4):
        return f"{age} года"
    else:
        return f"{age} лет"

# --- МОДАЛЬНОЕ ОКНО ОПЛАТЫ (без брони, чисто информационное) ---
@st.dialog("💳 Оплата")
def payment_dialog():
    option = st.session_state.payment_dialog_option

    st.write(f"**Назначение перевода:** {option}")

    if option == "Скинуть деньги на подарок":
        st.caption("Переведите сумму, которая пойдёт на подарки детям. Волонтёр фонда распределит средства.")
    else:
        st.caption("Переведите любую сумму в общий фонд. Волонтёр фонда распределит средства на подарки.")

    st.divider()

    qr_path = "static/qr.png"
    if os.path.exists(qr_path):
        col1, col2, col3 = st.columns([1, 3, 1])
        with col2:
            st.image(qr_path, use_column_width=True)
    else:
        st.warning("💳 QR-код для оплаты будет добавлен позже. Свяжитесь с координатором фонда.")

    st.write("**Или перейдите по ссылке:**")
    st.link_button("💳 Перейти к оплате", PAYMENT_LINK, use_container_width=True)

    st.divider()
    st.caption("После перевода закройте это окно. Спасибо за помощь! ❤️")

    if st.button("Закрыть", use_container_width=True):
        st.session_state.show_payment_dialog = False
        st.rerun()

# --- МОДАЛЬНОЕ ОКНО ПОКУПКИ (вариант 3 — с бронью, БЕЗ ФИО) ---
@st.dialog("🛒 Купить подарок самому")
def purchase_dialog():
    row_id = st.session_state.purchase_dialog_row_id
    child_name = st.session_state.purchase_dialog_row_name

    st.info(f"Вы помогаете ребёнку: **{child_name}**")
    st.write("Заполните данные — координатор свяжется с вами по телефону.")

    with st.form(key=f"purchase_form_{row_id}"):
        v_phone = st.text_input("Телефон для связи")
        v_pvz = st.text_input("Адрес ПВЗ Wildberries")
        v_date = st.date_input("Дата прибытия заказа", value=None)

        submit = st.form_submit_button(
            "Забронировать и купить",
            type="primary",
            use_container_width=True
        )

        if submit:
            if v_phone and v_pvz and v_date:
                if reserve_letter(row_id, "Купить подарок самому", "Аноним", v_phone, v_pvz, v_date):
                    st.session_state.show_purchase_dialog = False
                    st.success("✅ Вы забронировали подарок! Спасибо!")
                    st.rerun()
                else:
                    st.error("Не удалось забронировать. Возможно, подарок уже заняли.")
            else:
                st.error("Пожалуйста, заполните все поля")

# --- ВЫБОР ВАРИАНТА ПОМОЩИ ---
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

# --- ВКЛАДКИ ---
df = get_letters()

if st.session_state.volunteer_auth:
    tab1, tab2, tab3 = st.tabs(["✉️ Выбрать письмо", "📦 Панель волонтера", "📖 Инструкция"])
else:
    tab1, tab3 = st.tabs(["✉️ Выбрать письмо", "📖 Инструкция"])
    tab2 = None

# --- ВКЛАДКА 1 ---
with tab1:
    cols = st.columns(3)

    for index, row in df.iterrows():
        with cols[index % 3]:
            with st.container(border=True):
                img_filename = row['photo_filename']
                img_path = f"static/{img_filename}"

                if os.path.exists(img_path):
                    st.markdown(
                        f'<a href="/app/static/{img_filename}" target="_blank" class="letter-link">📩 Читать письмо</a>',
                        unsafe_allow_html=True
                    )
                else:
                    st.info("Фото скоро появится")

                age_str = format_age(row['child_age'])
                name_display = f"{row['child_name']}, {age_str}" if age_str else row['child_name']
                st.subheader(name_display)

                st.divider()

                # === ИСПРАВЛЕННЫЙ БЛОК СТАТУСОВ (правильные отступы!) ===
                if row['status'] == 'free':
                    render_option_selector(row)
                elif row['status'] == 'reserved':
                    st.warning("⏳ Уже забронировано")
                    if row['volunteer_name'] and row['volunteer_name'] != "Аноним":
                        st.caption(f"Забрал(а): {row['volunteer_name']}")
                    if row['payment_option'] == "Купить подарок самому":
                        st.write(f"📦 ПВЗ: {row['delivery_pvz']}")
                        st.write(f"📅 Дата: {row['delivery_date']}")
                elif row['status'] == 'received':
                    st.success("✅ Подарок получен фондом!")
                    st.caption("Окно заблокировано.")

    # Модальные окна
    if st.session_state.show_payment_dialog:
        st.session_state.show_payment_dialog = False
        payment_dialog()

    if st.session_state.show_purchase_dialog and st.session_state.purchase_dialog_row_id is not None:
        st.session_state.show_purchase_dialog = False
        purchase_dialog()

# --- ВКЛАДКА 2: ПАНЕЛЬ ВОЛОНТЁРА ---
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
                        # Показываем ФИО только если это не Аноним
                        if row['volunteer_name'] and row['volunteer_name'] != "Аноним":
                            st.write(f"Заказал: {row['volunteer_name']}")
                        st.write(f"📞 Телефон: {row['volunteer_phone']}")
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

# --- ВКЛАДКА 3 ---
with tab3:
    st.header("Как это работает?")
    st.markdown("""
    1. Нажмите **«📩 Читать письмо»** — фотография откроется в новой вкладке.
    2. Выберите удобный вариант помощи:
       - 💝 **Скинуть деньги на подарок** — откроется окно с QR-кодом и ссылкой для перевода.
       - 🎁 **Скинуть деньги на общий сбор** — откроется окно с QR-кодом и ссылкой для перевода в общий фонд.
       - 🛒 **Купить подарок самому** — откроется форма с телефоном, адресом ПВЗ Wildberries и датой прибытия. **ФИО указывать не нужно** — вы можете помочь анонимно.
    3. **Важно про варианты 1 и 2:** деньги идут в общий фонд, волонтёр распределяет их на подарки детям. Переводы не привязываются к конкретному ребёнку — можно переводить любую сумму любое количество раз.
    4. **Про вариант 3:** после заполнения формы подарок закрепляется за вами. Координатор свяжется по указанному телефону для уточнения деталей.

    *Пожалуйста, если ваши планы изменились, сообщите координатору — подарок ждёт ребёнок.*
    """)

    st.divider()
    st.subheader("💳 Реквизиты для помощи")
    qr_path = "static/qr.png"
    if os.path.exists(qr_path):
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image(qr_path, use_column_width=True)
    else:
        st.info("QR-код будет добавлен позже")

    st.write("**Или перейдите по ссылке:**")
    st.link_button("💳 Перейти к оплате", PAYMENT_LINK, use_container_width=True)