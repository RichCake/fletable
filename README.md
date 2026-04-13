# Fletable

**Fletable** — Python-библиотека для создания интерактивных таблиц с данными из SQL-баз в приложениях на Flet. Поддерживает редактирование данных, автоматическую обработку внешних ключей и удобную работу с формами.

## ✨ Возможности

- 📝 **Редактируемые таблицы** — изменение, добавление и удаление записей прямо в интерфейсе
- 👀 **Таблицы только для чтения** — отображение данных с возможностью выбора строк
- 🔗 **Автоматическая обработка внешних ключей** — dropdown-списки для связанных таблиц
- 📅 **Поддержка дат и времени** — DatePicker и TimePicker для удобного ввода дат/времени
- 🖼️ **Поддержка изображений** — поле типа `image` с выбором файла через FilePicker
- 🇷🇺 **Российский формат дат** — автоматическое форматирование дат (dd.mm.yyyy HH:MM)
- ✅ **Множественный выбор** — чекбоксы для выделения строк
- 🔍 **Фильтрация данных** — поддержка WHERE-условий для выборки
- 🔐 **Встроенная форма авторизации** — готовый компонент для входа пользователей с `redirect_route`
- 🎨 **Настраиваемые подписи полей** — удобное отображение имен колонок

## 📦 Установка

```bash
pip install fletable
```

Или установите из исходного кода:

```bash
git clone <repository-url>
cd fletable
pip install -e .
```

## 🚀 Быстрый старт

### 1. Редактируемая таблица

```python
import flet as ft
import psycopg2
from fletable import EditableTable, FieldConfig, ForeignKeyConfig

def main(page: ft.Page):
    # Подключение к базе данных
    conn = psycopg2.connect(
        host="localhost",
        database="mydb",
        user="user",
        password="password"
    )
    cursor = conn.cursor()
    
    # Создание таблицы
    table = EditableTable(
        cursor=cursor,
        table_name="employees",
        field_mapping={
            "employee_id": "ID",
            "name": "Имя",
            "email": "Email",
            "department_id": FieldConfig(
                label="Отдел",
                foreign_key=ForeignKeyConfig(
                    table="departments",
                    id_column="department_id",
                    label_column="department_name"
                )
            ),
            "hire_date": FieldConfig(label="Дата приёма", field_type="date"),
            "birth_date": FieldConfig(label="Дата рождения", field_type="date")
        },
        where_clause="active = %s",
        where_params=(True,)
    )
    
    # Форма добавления
    add_form, handle_add = table.create_add_form()
    
    def add_record(e):
        success, message = handle_add()
        if success:
            # Обновление таблицы после добавления
            container.content = table.create_table()
            page.update()
    
    add_button = ft.ElevatedButton("Добавить", on_click=add_record)
    
    # Контейнер с таблицей
    container = ft.Container(
        content=table.create_table(),
        padding=10
    )
    
    page.add(
        ft.Column([
            ft.Text("Управление сотрудниками", size=24, weight="bold"),
            add_form,
            add_button,
            container
        ])
    )

ft.app(target=main)
```

### 2. Таблица только для чтения

```python
import flet as ft
from fletable import SqlTable, FieldConfig

def main(page: ft.Page):
    # Подключение к БД
    cursor = conn.cursor()
    
    # Создание read-only таблицы
    table = SqlTable(
        cursor=cursor,
        table_name="products",
        field_mapping={
            "product_id": "ID",
            "product_name": "Название",
            "price": "Цена",
            "category_id": "Категория",
            "created_at": FieldConfig(label="Создано", field_type="datetime")
        },
        where_clause="price > %s",
        where_params=(100,)
    )
    
    # Кнопка для получения выделенных строк
    def show_selected(e):
        selected = table.get_selected_rows()
        print("Выбрано записей:", len(selected))
        for row in selected:
            print(row)
    
    page.add(
        ft.Column([
            ft.Container(content=table.create_table(), padding=10),
            ft.ElevatedButton("Показать выбранные", on_click=show_selected)
        ])
    )

ft.app(target=main)
```

### 3. Форма авторизации

```python
import flet as ft
from fletable import LoginView

def main(page: ft.Page):
    login_view = LoginView(
        page=page,
        user_table="users",
        user_login_col="login",
        user_password_col="password",
        dbapi_cursor=cursor,
        redirect_route="/home",
        user_role_col="role",
        user_role_key="user_role",
        user_id_col="user_id",
        user_id_key="current_user_id"
    )
    
    page.views.append(login_view)
    page.update()

ft.app(target=main)
```

## 📚 Документация API

### EditableTable

Класс для создания редактируемых таблиц с поддержкой CRUD-операций.

#### Конструктор

```python
EditableTable(
    cursor,                          # Курсор базы данных (DB-API 2.0)
    table_name: str,                 # Имя таблицы в БД
    field_mapping: dict,             # Маппинг полей {column: label или FieldConfig}
    width: int = 800,                # Ширина таблицы (пикселей)
    height: int = 400,               # Высота таблицы (пикселей)
    where_clause: str | None = None, # WHERE-условие для фильтрации (опционально)
    where_params: tuple | None = None # Параметры для WHERE-условия (опционально)
)
```

#### Методы

- **`create_table()`** — создает и возвращает `ft.DataTable` с данными
- **`create_add_form()`** — создает форму для добавления новых записей, возвращает `(form_row, handle_add)`
- **`get_selected_rows()`** — возвращает список словарей с данными выделенных строк

### SqlTable

Класс для создания таблиц только для чтения с возможностью выбора строк.

#### Конструктор

```python
SqlTable(
    cursor,                          # Курсор базы данных
    table_name: str,                 # Имя таблицы
    field_mapping: dict,             # Маппинг полей
    width: int = 800,
    height: int = 400,
    where_clause: str | None = None, # WHERE-условие для фильтрации (опционально)
    where_params: tuple | None = None # Параметры для WHERE-условия (опционально)
)
```

#### Методы

- **`create_table()`** — создает и возвращает `ft.DataTable`
- **`get_selected_rows()`** — возвращает выделенные строки

### FieldConfig

Конфигурация для настройки отображения полей.

```python
@dataclass
class FieldConfig:
    label: str                                   # Отображаемое название поля
    foreign_key: ForeignKeyConfig | None = None  # Конфигурация внешнего ключа
    field_type: str | None = None                # Тип поля: "text", "date", "datetime", "time", "image"
    default_image: str | None = None             # Путь к картинке по умолчанию для field_type="image"
    image_width: int = 72                        # Фиксированная ширина картинки для field_type="image"
    image_height: int = 72                       # Фиксированная высота картинки для field_type="image"
```

### ForeignKeyConfig

Настройка внешнего ключа для автоматического создания dropdown-списков.

```python
@dataclass
class ForeignKeyConfig:
    table: str                       # Имя связанной таблицы
    id_column: str                   # Колонка с ID
    label_column: str                # Колонка с отображаемым значением
```

### LoginView

Готовая форма авторизации пользователей.

```python
LoginView(
    page: ft.Page,                   # Объект страницы Flet
    user_table: str,                 # Таблица с пользователями
    user_login_col: str,             # Колонка с логином
    user_password_col: str,          # Колонка с паролем
    dbapi_cursor,                    # Курсор БД
    redirect_route: str,             # Route для редиректа после успешного входа
    user_role_col: str = None,       # Колонка с ролью (опционально)
    user_role_key: str = None,       # Ключ для хранения роли в page.session.store
    user_id_col: str = None,         # Колонка с ID пользователя (опционально)
    user_id_key: str = None          # Ключ для хранения ID в page.session.store
)
```

## 🔧 Автоматическая обработка внешних ключей

Fletable автоматически создает dropdown-списки для полей с именами, заканчивающимися на `_id` (кроме первичного ключа таблицы).

### Требования для автогенерации

- Поле должно заканчиваться на `_id` (например: `user_id`, `category_id`)
- Не должно быть primary key самой таблицы (`task_id` в таблице `tasks` не станет FK)
- Ожидается таблица с именем без `_id`: `user_id` → таблица `user`
- По умолчанию ищет колонки: `user_id` (id) и `user` (название) в таблице `user`

### Пример автоматической обработки

```python
field_mapping = {
    "order_id": "ID заказа",        # Primary key - не будет dropdown
    "customer_id": "Клиент",        # Автоматически создаст dropdown из таблицы "customer"
    "product_id": "Товар"           # Автоматически создаст dropdown из таблицы "product"
}
```

### Кастомная настройка с ForeignKeyConfig

Для более точной настройки используйте `ForeignKeyConfig`:

```python
field_mapping = {
    "order_id": "ID заказа",
    "customer_id": FieldConfig(
        label="Клиент",
        foreign_key=ForeignKeyConfig(
            table="customers",           # Название таблицы отличается от шаблона
            id_column="customer_id",     # Колонка с ID
            label_column="full_name"     # Колонка для отображения (не "customer")
        )
    )
}
```

## 📅 Работа с датами и временем

Fletable поддерживает удобный ввод дат и времени через встроенные пикеры с автоматическим форматированием.

### Поддерживаемые типы

```python
field_mapping = {
    "event_date": FieldConfig(label="Дата события", field_type="date"),       # Только дата: 13.12.2025
    "created_at": FieldConfig(label="Создано", field_type="datetime"),        # Дата и время: 13.12.2025 14:30
    "start_time": FieldConfig(label="Время начала", field_type="time")        # Только время: 14:30
}
```

### Особенности

- **DatePicker** для полей типа `date` и `datetime`
- **TimePicker** для полей типа `time` и `datetime`
- Автоматическое форматирование:
  - Отображение в российском формате (dd.mm.yyyy HH:MM)
  - Сохранение в БД в формате ISO (YYYY-MM-DD HH:MM:SS)
- Поддержка различных форматов при чтении из БД

### Пример с расписанием

```python
table = EditableTable(
    cursor=cursor,
    table_name="schedule",
    field_mapping={
        "id": "ID",
        "event_name": "Событие",
        "event_date": FieldConfig(label="Дата", field_type="date"),
        "start_time": FieldConfig(label="Начало", field_type="time"),
        "end_time": FieldConfig(label="Конец", field_type="time"),
        "created_at": FieldConfig(label="Создано", field_type="datetime")
    }
)
```

## 🖼️ Работа с изображениями

Для поля типа `image` в БД хранится путь к файлу (или URL), а в таблице показывается превью.

### Что происходит в UI

- В `EditableTable` у image-поля отображается только превью и кнопка выбора файла (`FilePicker`) — текстовое поле с путем скрыто.
- В `SqlTable` image-поля рендерятся как read-only превью.
- При пустом значении используется `default_image` (если задан).
- Высота строк `DataTable` адаптируется под размер картинки (`data_row_max_height=float("inf")`).

### Конфигурация image-поля

```python
field_mapping = {
    "id": "ID",
    "title": "Название",
    "photo": FieldConfig(
        label="Фото",
        field_type="image",
        default_image="assets/no-image.png",
        image_width=140,
        image_height=100,
    ),
}
```

### Поддерживаемые форматы при выборе файла

`jpg`, `jpeg`, `png`, `gif`, `webp`, `bmp`, `svg`

## 💡 Примеры использования

### Обновление таблицы после изменений

```python
def refresh_table(e):
    container.content = table.create_table()
    page.update()

refresh_button = ft.IconButton(
    icon=ft.Icons.REFRESH,
    on_click=refresh_table
)
```

### Работа с выделенными строками

```python
def process_selected(e):
    selected = table.get_selected_rows()
    for row in selected:
        print(f"ID: {row['employee_id']}, Name: {row['name']}")
```

### Массовое удаление

```python
def delete_selected(e):
    selected = table.get_selected_rows()
    for row in selected:
        cursor.execute(
            "DELETE FROM employees WHERE employee_id = %s",
            (row['employee_id'],)
        )
    conn.commit()
    refresh_table(e)
```

### Фильтрация данных с WHERE

```python
# Показать только активных сотрудников из конкретного отдела
table = EditableTable(
    cursor=cursor,
    table_name="employees",
    field_mapping={
        "employee_id": "ID",
        "name": "Имя",
        "department_id": "Отдел",
        "active": "Активен"
    },
    where_clause="active = %s AND department_id = %s",
    where_params=(True, 5)
)
```

### Динамическая смена фильтра

```python
def filter_by_department(e):
    department_id = department_dropdown.value
    
    # Создаём новую таблицу с фильтром
    new_table = EditableTable(
        cursor=cursor,
        table_name="employees",
        field_mapping=field_mapping,
        where_clause="department_id = %s",
        where_params=(department_id,)
    )
    
    # Обновляем контейнер
    table_container.content = new_table.create_table()
    page.update()
```

## 🗄️ Поддерживаемые базы данных

Fletable работает с любыми базами данных, поддерживающими DB-API 2.0:

- PostgreSQL (psycopg2)
- MySQL (mysql-connector-python)
- SQLite (sqlite3)
- Oracle
- Microsoft SQL Server

## 📋 Требования

- Python >= 3.6
- flet >= 0.28.3
- Драйвер базы данных (psycopg2, mysql-connector, и т.д.)

## 🤝 Участие в разработке

Мы приветствуем ваши предложения и pull request'ы!

## 📄 Лицензия

MIT License

## 👨‍💻 Автор

**RichCake**
Email: arseniikarpov.evro@gmail.com

---

⭐ Если вам понравился проект, поставьте звезду на GitHub!

