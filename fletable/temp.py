import sqlite3
from datetime import datetime

import flet as ft

from fletable import EditableTable, FieldConfig, LoginView, SqlTable


class SQLiteCompatCursor:
    """
    Адаптер курсора SQLite под стиль placeholder-ов `%s`,
    который используется внутри компонентов fletable.
    """

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self._cursor = connection.cursor()

    def execute(self, query: str, params=None):
        sqlite_query = query.replace("%s", "?")
        if params is None:
            return self._cursor.execute(sqlite_query)
        return self._cursor.execute(sqlite_query, params)

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchone(self):
        return self._cursor.fetchone()


def build_demo_db() -> SQLiteCompatCursor:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON;")

    connection.executescript(
        """
        CREATE TABLE user (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            login TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        );

        CREATE TABLE category (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL
        );

        CREATE TABLE task (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            image_path TEXT,
            user_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            deadline TEXT,
            start_at TEXT,
            start_time TEXT,
            status TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES user(user_id),
            FOREIGN KEY (category_id) REFERENCES category(category_id)
        );
        """
    )

    users = [
        ("Alice", "alice", "1234", "admin"),
        ("Bob", "bob", "1234", "operator"),
        ("Charlie", "charlie", "1234", "viewer"),
    ]
    categories = [("Backend",), ("Frontend",), ("QA",)]
    tasks = [
        (
            "Подготовить релиз",
            "https://flet.dev/img/logo.svg",
            1,
            1,
            "2026-04-30",
            "2026-04-20 10:30:00",
            "10:30:00",
            "active",
        ),
        (
            "Обновить документацию",
            "https://picsum.photos/120/80",
            2,
            2,
            "2026-05-10",
            "2026-04-21 14:00:00",
            "14:00:00",
            "active",
        ),
    ]

    connection.executemany(
        "INSERT INTO user(user, login, password, role) VALUES (?, ?, ?, ?)", users
    )
    connection.executemany("INSERT INTO category(category) VALUES (?)", categories)
    connection.executemany(
        """
        INSERT INTO task(title, image_path, user_id, category_id, deadline, start_at, start_time, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        tasks,
    )
    connection.commit()
    return SQLiteCompatCursor(connection)


def task_field_mapping():
    return {
        "task_id": "ID",
        "title": "Задача",
        "image_path": FieldConfig(label="Картинка", field_type="image", default_image="https://flet.dev/img/logo.svg"),
        "user_id": FieldConfig(label="Исполнитель"),
        "category_id": FieldConfig(label="Категория"),
        "deadline": FieldConfig(label="Дедлайн", field_type="date"),
        "start_at": FieldConfig(label="Начало", field_type="datetime"),
        "start_time": FieldConfig(label="Время", field_type="time"),
        "status": "Статус",
    }


def build_home_view(page: ft.Page, cursor: SQLiteCompatCursor) -> ft.View:
    editable_table = EditableTable(
        cursor=cursor,
        table_name="task",
        field_mapping=task_field_mapping(),
        pk_mapping={"task_id": "ID"},
        where_clause="status = %s",
        where_params=("active",),
    )
    sql_table = SqlTable(
        cursor=cursor,
        table_name="task",
        field_mapping=task_field_mapping(),
    )
    add_form, add_record = editable_table.create_add_form()
    output = ft.Text("Тестовая панель: выбирай строки, редактируй и сохраняй.")
    editable_table_container = ft.Container(padding=8)
    sql_table_container = ft.Container(padding=8)

    def refresh_tables():
        editable_table_container.content = editable_table.create_table()
        sql_table_container.content = sql_table.create_table()
        page.update()

    def show_snack(message: str):
        page.show_dialog(ft.SnackBar(ft.Text(message)))

    def on_add(e):
        add_record(e)
        refresh_tables()

    def open_edit_dialog(record_id: int):
        edit_form, handle_save, handle_delete = editable_table.create_edit_form(record_id)

        def on_save(e):
            ok, message = handle_save(e)
            show_snack(message)
            if ok:
                page.pop_dialog()
                refresh_tables()

        def on_delete(e):
            handle_delete(e)

        dialog = ft.AlertDialog(
            title=ft.Text(f"Редактирование задачи #{record_id}"),
            content=ft.Container(content=edit_form, width=700),
            actions=[
                ft.TextButton("Сохранить", on_click=on_save),
                ft.TextButton("Удалить", on_click=on_delete),
                ft.TextButton("Закрыть", on_click=lambda _: page.pop_dialog()),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dialog)

    def on_open_edit(_):
        selected = editable_table.get_selected_rows()
        if not selected:
            show_snack("Выберите хотя бы одну строку")
            return
        record_id = selected[0]["task_id"]
        open_edit_dialog(record_id)

    def on_selected_editable(_):
        selected = editable_table.get_selected_rows()
        output.value = f"Editable selected ({len(selected)}): {selected}"
        page.update()

    def on_selected_readonly(_):
        selected = sql_table.get_selected_rows()
        output.value = f"SqlTable selected ({len(selected)}): {selected}"
        page.update()

    def on_show_session(_):
        role = page.session.store.get("current_user_role")
        user_id = page.session.store.get("current_user_id")
        output.value = f"session.store -> role={role}, user_id={user_id}"
        page.update()

    def on_logout(_):
        page.session.store.clear()
        page.go("/login")

    refresh_tables()

    return ft.View(
        route="/home",
        controls=[
            ft.SafeArea(
                content=ft.Column(
                    controls=[
                        ft.Text("Demo: EditableTable + LoginView + sqlite3", size=20),
                        ft.Row(
                            controls=[
                                ft.TextButton("Показать session.store", on_click=on_show_session),
                                ft.TextButton("Логаут", on_click=on_logout),
                            ]
                        ),
                        ft.Divider(),
                        ft.Text("Форма добавления записи"),
                        add_form,
                        ft.Row(
                            controls=[
                                ft.FilledButton("Добавить", on_click=on_add),
                                ft.FilledButton("Открыть форму редактирования", on_click=on_open_edit),
                                ft.TextButton(
                                    "Показать selected (EditableTable)",
                                    on_click=on_selected_editable,
                                ),
                                ft.TextButton(
                                    "Показать selected (SqlTable)",
                                    on_click=on_selected_readonly,
                                ),
                            ]
                        ),
                        output,
                        ft.Divider(),
                        ft.Text("EditableTable (редактируемая)"),
                        editable_table_container,
                        ft.Divider(),
                        ft.Text("SqlTable (read-only)"),
                        sql_table_container,
                    ],
                    scroll=ft.ScrollMode.AUTO,
                )
            )
        ],
    )


def build_login_view(page: ft.Page, cursor: SQLiteCompatCursor) -> LoginView:
    return LoginView(
        page=page,
        user_table="user",
        user_login_col="login",
        user_password_col="password",
        dbapi_cursor=cursor,
        redirect_route="/home",
        user_role_col="role",
        user_role_key="current_user_role",
        user_id_col="user_id",
        user_id_key="current_user_id",
    )


def main(page: ft.Page):
    page.title = "Fletable temp demo"
    page.window_width = 1300
    page.window_height = 900
    cursor = build_demo_db()

    def route_change(_):
        route = page.route or "/login"
        page.views.clear()

        if route == "/home":
            page.views.append(build_home_view(page, cursor))
        else:
            page.views.append(build_login_view(page, cursor))
            page.route = "/login"

        page.update()

    def view_pop(e: ft.ViewPopEvent):
        if e.view and e.view in page.views:
            page.views.remove(e.view)
        if page.views:
            page.go(page.views[-1].route)
        else:
            page.go("/login")

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    page.go("/login")


if __name__ == "__main__":
    ft.run(main)
