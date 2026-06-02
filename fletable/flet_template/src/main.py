import flet as ft
from fletable.utils import LoginView

from core.db import Session, engine
from models.models import User

ROLE_KEY = "role"
ID_KEY = "id"


def main(page: ft.Page):
    page.title = "AAAaaaAAAa"

    def route(e):
        if e.page.route == "/login":
            e.page.views.append(
                LoginView(
                    page,
                    "users",
                    "login",
                    "password",
                    engine.raw_connection().cursor(),
                    "/",  # заменить
                    "role_id",
                    ROLE_KEY,
                    "id",
                    ID_KEY,
                )
            )

    page.on_route_change = route
    page.go("/login")


ft.run(main)
