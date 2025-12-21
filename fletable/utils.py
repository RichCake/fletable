import flet as ft


class LoginView(ft.View):
    """
    Форма входа с проверкой логина/пароля по БД.
    
    Параметры:
    - user_table: имя таблицы с пользователями
    - user_login_col: название колонки с логином в БД
    - user_password_col: название колонки с паролем в БД
    - dbapi_cursor: курсор БД для выполнения запросов
    - next: функция, вызываемая после успешного входа (обычно для перехода на главную)
    - user_role_col: колонка с ролью в БД (опционально)
    - user_role_key: ключ для сохранения роли в page.client_storage (опционально)
    - user_id_col: колонка с ID пользователя в БД (опционально)
    - user_id_key: ключ для сохранения ID в page.client_storage (опционально)
    
    Пример:
        def after_login(page):
            page.go("/main")
        
        login_view = LoginView(
            user_table="users",
            user_login_col="login",
            user_password_col="password",
            dbapi_cursor=connection.cursor(),
            next=after_login,
            user_role_col="role",
            user_role_key="current_user_role",  # ключ в client_storage
            user_id_col="user_id",
            user_id_key="current_user_id"  # ключ в client_storage
        )
        page.views.append(login_view)
    """

    def __init__(
        self,
        page,
        user_table,
        user_login_col,
        user_password_col,
        dbapi_cursor,
        next,
        user_role_col=None,
        user_role_key=None,
        user_id_col=None,
        user_id_key=None,
    ):
        super().__init__()
        self.page = page
        self.user_table = user_table
        self.user_login_col = user_login_col
        self.user_password_col = user_password_col
        self.user_role_col = user_role_col
        self.user_role_key = user_role_key
        self.cursor = dbapi_cursor
        self.next_func = next
        self.user_id_col = user_id_col
        self.user_id_key = user_id_key

        title = ft.Text("Вход", size=20, weight="bold")
        self.login = ft.TextField(label="Логин")
        self.password = ft.TextField(
            label="Пароль", password=True, can_reveal_password=True
        )
        self.submit = ft.FilledButton("Войти", on_click=self.check_credentials)

        self.route = "/login"
        self.form = ft.Column(
            [
                ft.Row(controls=[title], alignment=ft.MainAxisAlignment.CENTER),
                self.login,
                self.password,
                ft.Row(controls=[self.submit], alignment=ft.MainAxisAlignment.END),
            ],
            width=300,
        )
        self.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.controls = [self.form]

    def check_credentials(self, e):
        login = self.login.value
        password = self.password.value
        self.password.error_text = None
        self.login.error_text = None
        if not (login and password):
            if not login:
                self.login.error_text = "введите логин"
            else:
                self.login.error_text = None
            if not password:
                self.password.error_text = "Введите пароль"
            else:
                self.password.error_text = None
            self.page.update()
            return
        self.page.update()

        self.cursor.execute(
            f"""
            SELECT {self.user_role_col if self.user_role_col else -1}, {self.user_id_col if self.user_id_col else -1}
            FROM {self.user_table} 
            WHERE {self.user_login_col}='{login}' AND {self.user_password_col}='{password}'
            """
        )
        result = self.cursor.fetchone()
        if not result:
            dlg = ft.AlertDialog(
                title=ft.Text("Предупреждение"),
                content=ft.Text("Неверный логин и пароль"),
                alignment=ft.alignment.center,
                title_padding=ft.padding.all(25),
                actions=[ft.TextButton("Ok", on_click=lambda e: self.page.close(dlg))],
            )
            self.page.open(dlg)
            return
        if self.user_role_col and self.user_role_key and result[0] != -1:
            self.page.client_storage.set(self.user_role_key, result[0])
            self.page.client_storage.set(self.user_id_key, result[1])

        self.page.views.pop()
        self.next_func(self.page)
