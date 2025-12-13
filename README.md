# Fletable

**Fletable** — Python-библиотека для создания интерактивных таблиц с данными из SQL-баз в приложениях на Flet. Поддерживает редактирование данных, автоматическую обработку внешних ключей и удобную работу с формами.

## ✨ Возможности

- 📝 **Редактируемые таблицы** — изменение, добавление и удаление записей прямо в интерфейсе
- 👀 **Таблицы только для чтения** — отображение данных с возможностью выбора строк
- 🔗 **Автоматическая обработка внешних ключей** — dropdown-списки для связанных таблиц
- ✅ **Множественный выбор** — чекбоксы для выделения строк
- 🔐 **Встроенная форма авторизации** — готовый компонент для входа пользователей
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
from fletable import EditableTable, FieldConfig

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
            )
        },
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
from fletable import SqlTable

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
            "category_id": "Категория"
        }
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
    def after_login(page):
        # Переход на главную страницу после успешного входа
        page.views.append(
            ft.View("/home", [
                ft.Text("Добро пожаловать!")
            ])
        )
        page.update()
    
    login_view = LoginView(
        user_table="users",
        user_login_col="login",
        user_password_col="password",
        dbapi_cursor=cursor,
        next=after_login,
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
    height: int = 400                # Высота таблицы (пикселей)
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
    height: int = 400
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
    label: str                       # Отображаемое название поля
    foreign_key: ForeignKeyConfig | None = None  # Конфигурация внешнего ключа
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
    user_table: str,                 # Таблица с пользователями
    user_login_col: str,             # Колонка с логином
    user_password_col: str,          # Колонка с паролем
    dbapi_cursor,                    # Курсор БД
    next: callable,                  # Функция после успешного входа
    user_role_col: str = None,       # Колонка с ролью (опционально)
    user_role_key: str = None,       # Ключ для хранения роли
    user_id_col: str = None,         # Колонка с ID пользователя
    user_id_key: str = None          # Ключ для хранения ID
)
```

## 🔧 Автоматическая обработка внешних ключей

Fletable автоматически создает dropdown-списки для полей с именами, заканчивающимися на `_id` (кроме первичного ключа таблицы):

```python
field_mapping = {
    "order_id": "ID заказа",
    "customer_id": "Клиент",        # Автоматически создаст dropdown из таблицы "customer"
    "product_id": "Товар"           # Автоматически создаст dropdown из таблицы "product"
}
```

Для более точной настройки используйте `ForeignKeyConfig`:

```python
field_mapping = {
    "order_id": "ID заказа",
    "customer_id": FieldConfig(
        label="Клиент",
        foreign_key=ForeignKeyConfig(
            table="customers",
            id_column="customer_id",
            label_column="full_name"
        )
    )
}
```

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
Email: abs2016123@gmail.com

---

⭐ Если вам понравился проект, поставьте звезду на GitHub!

