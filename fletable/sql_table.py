from dataclasses import dataclass

import flet as ft

from .editable_table import FieldConfig


@dataclass
class DisplayValue:
    id: str
    label: str


class SqlTable:
    """
    Read-only таблица: только отображение и выбор строк.

    Пример:
        table = SqlTable(cursor, "users", {"user_id": "ID", "name": "Имя"})
        data_table = table.create_table()
        selected = table.get_selected_rows()
    """

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
        self.field_configs: dict[str, FieldConfig] = {
            name: cfg if isinstance(cfg, FieldConfig) else FieldConfig(label=str(cfg))
            for name, cfg in field_mapping.items()
        }
        self.width = width
        self.height = height
        self.dropdown_options = self._generate_dropdown_options()
        self.row_checkboxes: list[tuple[ft.Checkbox, dict]] = []
        self.header_checkbox: ft.Checkbox = None

    def _generate_dropdown_options(self) -> dict[str, list[DisplayValue]]:
        """
        Подтягиваем значения для внешних ключей, чтобы показывать подписанные лейблы.
        """
        options: dict[str, list[DisplayValue]] = {}
        for field, cfg in self.field_configs.items():
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
                    options[field] = [
                        DisplayValue(id=str(row[0]), label=str(row[1]))
                        for row in results
                    ]
                except Exception as e:
                    print(f"[WARN] Не удалось загрузить dropdown для {field}: {e}")
        return options

    def _label_for_fk(self, field: str, value) -> str:
        """
        Возвращает человеко-читаемое значение для внешнего ключа.
        """
        if field not in self.dropdown_options:
            return str(value)
        for option in self.dropdown_options[field]:
            if option.id == str(value):
                return option.label
        return str(value)

    def create_table(self) -> ft.DataTable:
        db_fields = list(self.field_configs.keys())
        query = f"SELECT {', '.join(db_fields)} FROM {self.table_name}"
        self.cursor.execute(query)
        data = self.cursor.fetchall()

        self.row_checkboxes = []

        def on_header_checkbox_change(e):
            for checkbox, _ in self.row_checkboxes:
                checkbox.value = self.header_checkbox.value
            e.page.update()

        self.header_checkbox = ft.Checkbox(
            value=False, on_change=on_header_checkbox_change
        )

        rows = []
        for row in data:
            row_data = {field: value for field, value in zip(db_fields, row)}
            row_checkbox = ft.Checkbox(value=False)
            self.row_checkboxes.append((row_checkbox, row_data))

            cells = [ft.DataCell(row_checkbox)]
            for field, value in zip(db_fields, row):
                display_value = self._label_for_fk(field, value)
                cells.append(ft.DataCell(ft.Text(display_value)))

            rows.append(ft.DataRow(cells=cells))

        columns = [ft.DataColumn(self.header_checkbox)] + [
            ft.DataColumn(ft.Text(self.field_configs[field].label))
            for field in db_fields
        ]

        return ft.DataTable(
            columns=columns,
            rows=rows,
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
