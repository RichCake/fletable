from dataclasses import dataclass
from datetime import date, datetime

import flet as ft

from .editable_table import FieldConfig


@dataclass
class DisplayValue:
    id: str
    label: str


class SqlTable:
    """
    Read-only таблица для отображения данных без редактирования.
    
    Возможности:
    - Отображение данных с выбором строк через чекбоксы
    - Автоматическая подстановка названий для foreign key (*_id поля)
    - Форматирование дат в российском формате (dd.mm.yyyy)
    - Фильтрация через WHERE-условия
    
    Советы:
    - Для дат явно указывайте field_type="date" или "datetime" в FieldConfig
    - Используйте get_selected_rows() для получения отмеченных строк
    
    Автогенерация FK (подстановка названий):
    - Поле должно заканчиваться на "_id" (например: user_id, category_id)
    - Не должно быть primary key самой таблицы (task_id в таблице tasks не станет FK)
    - Ожидается таблица с именем без "_id": user_id → таблица user
    - По умолчанию ищет колонки: user_id (id) и user (название) в таблице user
    - Для кастомных настроек используйте ForeignKeyConfig
    
    Пример:
        table = SqlTable(
            cursor=db_cursor,
            table_name="tasks",
            field_mapping={
                "task_id": "ID",
                "name": "Название",
                "user_id": FieldConfig(label="Исполнитель"),  # автоматический FK
                "deadline": FieldConfig(label="Срок", field_type="date"),
            },
            where_clause="status = %s",
            where_params=("completed",)
        )
        page.add(table.create_table())
        selected = table.get_selected_rows()
    """

    def __init__(
        self,
        cursor,
        table_name: str,
        field_mapping: dict[str, FieldConfig | str],
        width: int = 800,
        height: int = 400,
        where_clause: str | None = None,
        where_params: tuple | None = None,
    ):
        self.cursor = cursor
        self.table_name = table_name
        self.field_configs: dict[str, FieldConfig] = {
            name: cfg if isinstance(cfg, FieldConfig) else FieldConfig(label=str(cfg))
            for name, cfg in field_mapping.items()
        }
        self.width = width
        self.height = height
        self.where_clause = where_clause
        self.where_params = where_params or ()
        self.field_types = self._detect_field_types()
        self.dropdown_options = self._generate_dropdown_options()
        self.row_checkboxes: list[tuple[ft.Checkbox, dict]] = []
        self.header_checkbox: ft.Checkbox = None

    def _detect_field_types(self) -> dict[str, str]:
        """
        Определяет типы полей из явного field_type в FieldConfig.
        Если не указано явно - возвращает "text" по умолчанию.
        Возвращает словарь {field_name: field_type}.
        """
        field_types = {}
        for field, cfg in self.field_configs.items():
            field_types[field] = cfg.field_type or "text"
        return field_types

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

    def _format_display_value(self, field: str, value) -> str:
        """
        Форматирует значение для отображения в зависимости от типа поля.
        """
        if value is None:
            return ""
        
        field_type = self.field_types.get(field, "text")
        
        # Для внешних ключей используем лейбл
        if field in self.dropdown_options:
            return self._label_for_fk(field, value)
        
        # Для дат форматируем в российском формате
        if field_type == "date":
            if isinstance(value, (date, datetime)):
                return value.strftime("%d.%m.%Y")
            else:
                # Пытаемся распарсить строку
                try:
                    dt = datetime.strptime(str(value), "%Y-%m-%d")
                    return dt.strftime("%d.%m.%Y")
                except:
                    return str(value)
        
        elif field_type == "datetime":
            if isinstance(value, (date, datetime)):
                return value.strftime("%d.%m.%Y %H:%M")
            else:
                # Пытаемся распарсить строку с разными форматами
                value_str = str(value)
                for fmt in ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
                    try:
                        dt = datetime.strptime(value_str, fmt)
                        return dt.strftime("%d.%m.%Y %H:%M")
                    except ValueError:
                        continue
                return value_str
        
        return str(value)

    def create_table(self) -> ft.DataTable:
        db_fields = list(self.field_configs.keys())
        query = f"SELECT {', '.join(db_fields)} FROM {self.table_name}"
        
        if self.where_clause:
            query += f" WHERE {self.where_clause}"
            self.cursor.execute(query, self.where_params)
        else:
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
                display_value = self._format_display_value(field, value)
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
