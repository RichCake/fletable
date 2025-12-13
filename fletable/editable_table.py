from dataclasses import dataclass

import flet as ft


@dataclass
class ForeignKeyConfig:
    table: str
    id_column: str
    label_column: str


@dataclass
class FieldConfig:
    label: str
    foreign_key: ForeignKeyConfig | None = None


class EditableTable:
    def __init__(
        self,
        cursor,
        table_name: str,
        field_mapping: dict[str, FieldConfig | str],
        width: int = 800,
        height: int = 400,
    ):
        self.cursor = cursor
        self.table_name = table_name
        # Приводим значения словаря к FieldConfig для типобезопасных подсказок
        self.field_configs: dict[str, FieldConfig] = {
            name: cfg if isinstance(cfg, FieldConfig) else FieldConfig(label=str(cfg))
            for name, cfg in field_mapping.items()
        }
        self.width = width
        self.height = height
        self.dropdown_options = self._generate_dropdown_options()
        self.row_checkboxes: list[tuple[ft.Checkbox, dict]] = []  # (checkbox, row_data)
        self.header_checkbox: ft.Checkbox = None

    def _generate_dropdown_options(self):
        options = {}
        for field, cfg in self.field_configs.items():
            # Настройки FK: явно через FieldConfig.foreign_key или по шаблону *_id
            ref_cfg = cfg.foreign_key
            if ref_cfg or (field.endswith("_id") and field != f"{self.table_name}_id"):
                ref_table = ref_cfg.table if ref_cfg else field.replace("_id", "")
                id_column = ref_cfg.id_column if ref_cfg else field
                label_column = ref_cfg.label_column if ref_cfg else ref_table
                try:
                    self.cursor.execute(
                        f"SELECT {id_column}, {label_column} FROM {ref_table}"
                    )
                    results = self.cursor.fetchall()
                    options[field] = [(str(row[0]), str(row[1])) for row in results]
                except Exception as e:
                    print(f"[WARN] Не удалось загрузить dropdown для {field}: {e}")
        return options

    def create_add_form(self):
        new_fields = {}
        input_controls = []

        for field in list(self.field_configs.keys())[1:]:  # Пропускаем ID
            if field in self.dropdown_options:
                ctrl = ft.Dropdown(
                    options=[
                        ft.dropdown.Option(key=str(k), text=str(v))
                        for k, v in self.dropdown_options[field]
                    ],
                    value=None,
                    expand=True,
                    label=self.field_configs[field].label,
                )
            else:
                ctrl = ft.TextField(label=self.field_configs[field].label, expand=True)

            new_fields[field] = ctrl
            input_controls.append(ctrl)

        def handle_add():
            try:
                fields = ", ".join(new_fields.keys())
                placeholders = ", ".join(["%s"] * len(new_fields))
                values = [ctrl.value for ctrl in new_fields.values()]
                insert_query = (
                    f"INSERT INTO {self.table_name} ({fields}) VALUES ({placeholders})"
                )
                self.cursor.execute(insert_query, values)
                self.cursor.connection.commit()
                for ctrl in input_controls:
                    ctrl.value = ""
                print("[INFO] Запись добавлена:", values)
                return True, "Успешно добавлено"
            except Exception as ex:
                print("[ERROR] Ошибка добавления:", str(ex))
                return False, f"Ошибка: {str(ex)}"

        form_row = ft.Row(input_controls)
        return form_row, handle_add

    def create_table(self):
        db_fields = list(self.field_configs.keys())
        query = f"SELECT {', '.join(db_fields)} FROM {self.table_name}"
        self.cursor.execute(query)
        data = self.cursor.fetchall()

        # Очищаем список чекбоксов перед созданием новой таблицы
        self.row_checkboxes = []

        # Создаём чекбокс для заголовка (выбрать все)
        def on_header_checkbox_change(e):
            for checkbox, _ in self.row_checkboxes:
                checkbox.value = self.header_checkbox.value
            e.page.update()

        self.header_checkbox = ft.Checkbox(
            value=False, on_change=on_header_checkbox_change
        )

        rows = []
        for row in data:
            record_id = row[0]
            cells = []
            field_controls = {}

            # Собираем данные строки в словарь
            row_data = {field: value for field, value in zip(db_fields, row)}

            # Создаём чекбокс для строки
            row_checkbox = ft.Checkbox(value=False)
            self.row_checkboxes.append((row_checkbox, row_data))
            cells.append(ft.DataCell(row_checkbox))

            for field, value in zip(db_fields, row):
                if field == db_fields[0]:
                    cells.append(ft.DataCell(ft.Text(str(value))))
                    continue

                if field in self.dropdown_options:
                    ctrl = ft.Container(
                        content=ft.Dropdown(
                            options=[
                                ft.dropdown.Option(key=str(k), text=v)
                                for k, v in self.dropdown_options[field]
                            ],
                            value=str(value),
                            expand=True,
                        ),
                        padding=5,
                        expand=True,
                    )
                else:
                    ctrl = ft.Container(
                        content=ft.TextField(
                            value=str(value), border=ft.InputBorder.NONE, expand=True
                        ),
                        padding=5,
                        expand=True,
                    )

                field_controls[field] = ctrl.content
                cells.append(ft.DataCell(ctrl))

            def make_save_callback(record_id, controls):
                def save(e):
                    try:
                        update_fields = ", ".join(
                            f"{field} = %s" for field in controls.keys()
                        )
                        values = [c.value for c in controls.values()]
                        update_query = f"UPDATE {self.table_name} SET {update_fields} WHERE {db_fields[0]} = %s"
                        self.cursor.execute(update_query, (*values, record_id))
                        self.cursor.connection.commit()
                        e.page.open(ft.SnackBar(ft.Text("Изменения сохранены")))
                        print(f"[LOG] Updated record {record_id} with values {values}")
                    except Exception as ex:
                        e.page.open(ft.SnackBar(ft.Text(f"Ошибка: {str(ex)}")))
                    e.page.update()

                return save

            save_button = ft.IconButton(
                icon=ft.Icons.SAVE,
                tooltip="Сохранить",
                on_click=make_save_callback(record_id, field_controls),
            )
            delete_button = ft.IconButton(
                icon=ft.Icons.DELETE,
                tooltip="Удалить",
                on_click=self._handle_delete(record_id),
            )
            cells.append(ft.DataCell(ft.Row([save_button, delete_button], spacing=0)))

            rows.append(ft.DataRow(cells=cells))

        # Колонки: чекбокс + поля из mapping + действия
        columns = (
            [ft.DataColumn(self.header_checkbox)]
            + [
                ft.DataColumn(ft.Text(self.field_configs[field].label))
                for field in db_fields
            ]
            + [ft.DataColumn(ft.Text("Действия"))]
        )

        return ft.DataTable(
            columns=columns,
            rows=rows,
            # width=self.width - 20
        )

    def get_selected_rows(self) -> list[dict]:
        """
        Возвращает список словарей с данными выделенных строк.
        Ключи словаря соответствуют полям из field_mapping.
        """
        selected = []
        for checkbox, row_data in self.row_checkboxes:
            if checkbox.value:
                selected.append(row_data.copy())
        return selected

    def _handle_delete(self, record_id: int):
        def callback(e):
            try:
                delete_query = f"DELETE FROM {self.table_name} WHERE {list(self.field_configs.keys())[0]} = %s"
                self.cursor.execute(delete_query, (record_id,))
                self.cursor.connection.commit()
                e.page.open(ft.SnackBar(ft.Text("Запись удалена!")))
                e.page.update()
            except Exception as ex:
                print(ex)
                e.page.open(ft.SnackBar(ft.Text(f"Ошибка: {str(ex)}")))
                e.page.update()

        return callback
