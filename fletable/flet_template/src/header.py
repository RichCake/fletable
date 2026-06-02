import flet as ft


class Header(ft.Container):
    def __init__(self, name, role):
        super().__init__()
        self.padding = ft.Padding.all(2)
        self.bgcolor = "#BCBCBCFF"
        self.content = ft.Row(
            controls=[
                ft.Text(f"{role}: {name}"),
                ft.Button("Страница1", on_click=lambda e: e.page.go("/")),
            ]
        )
