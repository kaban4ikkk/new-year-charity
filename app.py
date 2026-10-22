import random
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import os
from sqlalchemy import create_engine, text
from PIL import Image, ImageOps

# Настройка параметров страницы (должна быть первой командой Streamlit)
st.set_page_config(page_title="Подари Новый год", layout="wide", page_icon="🎁")

# Функция для загрузки внешнего файла со стилями
def load_css(file_name):
    """Читает CSS-файл и внедряет его в страницу Streamlit."""
    with open(file_name, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Подключаем стили
load_css("styles.css")

# Функция для генерации падающих снежинок
def add_snowflakes(count=40):
    """Создает HTML-разметку для анимации падающих снежинок."""
    snowflakes_html = '<div class="snow-container">'
    for _ in range(count):
        left = random.uniform(0, 100)
        duration = random.uniform(5, 15)
        delay = random.uniform(0, 10)
        size = random.uniform(0.8, 2.0)
        # Используем символ снежинки
        snowflakes_html += f'<div class="snowflake" style="left: {left}vw; animation-duration: {duration}s; animation-delay: -{delay}s; font-size: {size}rem;">❄️</div>'
    snowflakes_html += '</div>'
    st.markdown(snowflakes_html, unsafe_allow_html=True)

# Добавляем снежинки на фон
add_snowflakes()

# Настройки приложения и подключение к базе данных
# Читаем данные для подключения из секретов Streamlit
DB_URL = st.secrets["DB_URL"]
engine = create_engine(DB_URL)

# Ссылка на платежную систему
PAYMENT_LINK = "https://example.com/pay"

# Пароль для входа в панель волонтера
VOLUNTEER_PASSWORD = st.secrets["VOLUNTEER_PASSWORD"]

# Инициализация переменных состояния
# Делаем это до отрисовки интерфейса, чтобы избежать ошибок при первом запуске
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

# Боковая панель для авторизации волонтеров
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

# Блок с заголовком и таймером (делим на две колонки)
col_title, col_timer = st.columns([3, 1], vertical_alignment="center")

with col_title:
    st.title("🎁 Новогодняя акция: Подари мечту")
    st.caption("Выберите письмо ребёнка и помогите исполнить его мечту ✨")

with col_timer:
    # Загружаем HTML-файл с таймером через компонент, чтобы работал JavaScript
    with open("header.html", "r", encoding="utf-8") as f:
        components.html(f.read(), height=110)

# Вспомогательные функции для работы с данными и базой
def get_letters():
    """Загружает все письма из базы данных."""
    return pd.read_sql("SELECT * FROM cildrens_letters ORDER BY id", con=engine)

def reserve_letter(letter_id, option, name, phone, pvz, d_date):
    """Резервирует письмо за пользователем. Используется только для третьего варианта помощи."""
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
    """Меняет статус подарка на 'получен' или возвращает в общий список."""
    new_status = 'received' if received else 'free' 
    with engine.begin() as conn:
        conn.execute(text("UPDATE cildrens_letters SET status = :st WHERE id = :id"), {"st": new_status, "id": letter_id})

def format_age(age):
    """Склоняет слово 'год' в зависимости от возраста и скрывает нулевой возраст."""
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

def load_image_portrait(path):
    """Читает фото и применяет EXIF-поворот, чтобы вертикальные снимки не отображались боком."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    return img


# Модальные окна (всплывающие диалоги)
@st.dialog("📩 Письмо ребёнка")
def view_image_dialog():
    """Окно для просмотра фотографии письма."""
    img_path = st.session_state.get('view_image_path')
    if img_path and os.path.exists(img_path):
        try:
            # Применяем правильный поворот перед показом
            img = load_image_portrait(img_path)
            st.image(img, use_column_width=True)
        except Exception as e:
            st.error(f"Не удалось загрузить фото: {e}")

@st.dialog("💳 Оплата")
def payment_dialog():
    """Окно с информацией для перевода денег (QR-код и ссылка)."""
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

@st.dialog("🛒 Купить подарок самому")
def purchase_dialog():
    """Окно для ввода данных доставки при самостоятельной покупке подарка."""
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


# Блок с кнопками выбора варианта помощи для карточки
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


# Основной интерфейс и вкладки
df = get_letters()

# Панель волонтера видна только авторизованным пользователям
if st.session_state.volunteer_auth:
    tab1, tab2, tab3 = st.tabs(["✉️ Выбрать письмо", "📦 Панель волонтера", "📖 Инструкция"])
else:
    tab1, tab3 = st.tabs(["✉️ Выбрать письмо", "📖 Инструкция"])
    tab2 = None

# Первая вкладка: карточки с письмами
with tab1:
    cols = st.columns(3)

    for index, row in df.iterrows():
        with cols[index % 3]:
            with st.container(border=True):
                img_filename = row['photo_filename']
                img_path = f"static/{img_filename}"

                # Кнопка для открытия модального окна с фото
                if os.path.exists(img_path):
                    if st.button("📩 Читать письмо", key=f"read_{row['id']}", use_container_width=True, type="primary"):
                        st.session_state.view_image_path = img_path
                        st.rerun()
                else:
                    st.info("Фото скоро появится")

                age_str = format_age(row['child_age'])
                name_display = f"{row['child_name']}, {age_str}" if age_str else row['child_name']
                st.subheader(name_display)

                st.divider()

                # Логика отображения карточки в зависимости от статуса
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

    # Вызов модальных окон, если пользователь нажал на соответствующую кнопку
    if st.session_state.get('view_image_path'):
        view_image_dialog()
        st.session_state.view_image_path = None  # Сбрасываем флаг, чтобы окно закрывалось

    if st.session_state.show_payment_dialog:
        st.session_state.show_payment_dialog = False
        payment_dialog()

    if st.session_state.show_purchase_dialog and st.session_state.purchase_dialog_row_id is not None:
        st.session_state.show_purchase_dialog = False
        purchase_dialog()

# Вторая вкладка: панель координатора
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

# Третья вкладка: инструкция и реквизиты
with tab3:
    st.header("Как это работает?")
    st.markdown("""
    1. Нажмите **«📩 Читать письмо»** — фотография откроется в новом окне.
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
