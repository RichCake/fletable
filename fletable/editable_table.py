from dataclasses import dataclass
from datetime import date, datetime

import flet as ft


@dataclass
class ForeignKeyConfig:
    table: str
    id_column: str = "id"
    label_column: str = "name"


@dataclass
class FieldConfig:
    label: str
    foreign_key: ForeignKeyConfig | None = None
    field_type: str | None = None  # "text", "date", "datetime", "time", "number", etc.


class EditableTable:
    """
    Редактируемая таблица с автоматической генерацией форм добавления и редактирования.
    
    Возможности:
    - Добавление, редактирование, удаление записей
    - Выбор строк через чекбоксы
    - Автоматические dropdown для foreign key (*_id поля)
    - DatePicker/TimePicker для полей типа date/datetime/time
    - Фильтрация через WHERE-условия
    
    Советы:
    - Для дат/времени явно указывайте field_type="date", "datetime" или "time" в FieldConfig
    - Используйте get_selected_rows() для получения отмеченных строк
    
    Автогенерация FK (dropdown):
    - Поле должно заканчиваться на "_id" (например: user_id, category_id)
    - Не должно быть primary key самой таблицы (task_id в таблице tasks не станет FK)
    - Ожидается таблица с именем без "_id": user_id → таблица user
    - По умолчанию ищет колонки: user_id (id) и user (название) в таблице user
    - Для кастомных настроек используйте ForeignKeyConfig
    
    Пример:
        table = EditableTable(
            cursor=db_cursor,
            table_name="tasks",
            field_mapping={
                "task_id": "ID",
                "name": "Название",
                "user_id": FieldConfig(label="Исполнитель"),  # автоматический FK
                "deadline": FieldConfig(label="Срок", field_type="date"),
                "start_time": FieldConfig(label="Время начала", field_type="time"),
            },
            where_clause="status = %s",
            where_params=("active",)
        )
        page.add(table.create_add_form()[0])  # форма добавления
        page.add(table.create_table())  # таблица
        selected = table.get_selected_rows()  # получить выбранные строки
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
        # Приводим значения словаря к FieldConfig для типобезопасных подсказок
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
        self.row_checkboxes: list[tuple[ft.Checkbox, dict]] = []  # (checkbox, row_data)
        self.header_checkbox: ft.Checkbox = None
        self.date_pickers: dict[str, ft.DatePicker] = {}  # Хранилище DatePicker'ов

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

    def _create_date_field(self, field: str, label: str, value=None, is_datetime: bool = False):
        """
        Создаёт поле для выбора даты с DatePicker.
        Возвращает Container с TextField и кнопкой для открытия календаря.
        """
        # Форматируем начальное значение для отображения (российский формат)
        display_value = ""
        db_value = None
        
        if value:
            if isinstance(value, (date, datetime)):
                display_value = value.strftime("%d.%m.%Y" if not is_datetime else "%d.%m.%Y %H:%M")
                db_value = value.strftime("%Y-%m-%d" if not is_datetime else "%Y-%m-%d %H:%M:%S")
            else:
                # Пытаемся распарсить строку
                value_str = str(value)
                if value_str:
                    try:
                        if ' ' in value_str:  # datetime
                            # Пробуем разные форматы (с милисекундами и без)
                            for fmt in ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
                                try:
                                    dt = datetime.strptime(value_str, fmt)
                                    display_value = dt.strftime("%d.%m.%Y %H:%M")
                                    db_value = dt.strftime("%Y-%m-%d %H:%M:%S")
                                    break
                                except ValueError:
                                    continue
                            else:
                                display_value = value_str
                                db_value = value_str
                        else:  # date
                            dt = datetime.strptime(value_str, "%Y-%m-%d")
                            display_value = dt.strftime("%d.%m.%Y")
                            db_value = value_str
                    except:
                        display_value = value_str
                        db_value = value_str
        
        # Текстовое поле для отображения выбранной даты
        text_field = ft.TextField(
            label=label,
            value=display_value,
            read_only=True,
            expand=True,
        )
        
        # Храним отдельно дату и время
        if db_value and ' ' in str(db_value):
            date_part, time_part = str(db_value).split(' ', 1)
            container_data = {'date_part': date_part, 'time_part': time_part}
        else:
            container_data = {'date_part': db_value or '', 'time_part': '00:00:00'}
        
        # DatePicker
        picker_key = f"{field}_{id(text_field)}"
        
        def update_display():
            """Обновляет отображаемое значение на основе date_part и time_part"""
            if is_datetime and container.data['date_part'] and container.data['time_part']:
                # Комбинируем дату и время
                try:
                    dt = datetime.strptime(f"{container.data['date_part']} {container.data['time_part']}", 
                                          "%Y-%m-%d %H:%M:%S")
                    text_field.value = dt.strftime("%d.%m.%Y %H:%M")
                    container.data['date_value'] = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass
            elif container.data['date_part']:
                # Только дата
                try:
                    dt = datetime.strptime(container.data['date_part'], "%Y-%m-%d")
                    text_field.value = dt.strftime("%d.%m.%Y")
                    container.data['date_value'] = container.data['date_part']
                except:
                    pass
        
        def on_date_change(e):
            if e.control.value:
                selected_date = e.control.value
                container.data['date_part'] = selected_date.strftime("%Y-%m-%d")
                update_display()
                e.page.update()
        
        date_picker = ft.DatePicker(
            on_change=on_date_change,
        )
        
        self.date_pickers[picker_key] = date_picker
        
        # Кнопка для открытия DatePicker
        def open_date_picker(e):
            e.page.open(date_picker)
        
        calendar_button = ft.IconButton(
            icon=ft.Icons.CALENDAR_TODAY,
            tooltip="Выбрать дату",
            on_click=open_date_picker,
        )
        
        buttons = [calendar_button]
        
        # Для datetime добавляем TimePicker
        if is_datetime:
            def on_time_change(e):
                if e.control.value:
                    selected_time = e.control.value
                    container.data['time_part'] = selected_time.strftime("%H:%M:%S")
                    update_display()
                    e.page.update()
            
            time_picker = ft.TimePicker(
                on_change=on_time_change,
            )
            
            time_picker_key = f"{field}_time_{id(text_field)}"
            self.date_pickers[time_picker_key] = time_picker
            
            def open_time_picker(e):
                e.page.open(time_picker)
            
            time_button = ft.IconButton(
                icon=ft.Icons.ACCESS_TIME,
                tooltip="Выбрать время",
                on_click=open_time_picker,
            )
            buttons.append(time_button)
        
        # Container с полем и кнопками
        container = ft.Container(
            content=ft.Row([text_field] + buttons, spacing=5),
            expand=True,
            data=container_data
        )
        container.data['date_value'] = db_value
        
        return container

    def _create_date_field_inline(self, field: str, value=None, is_datetime: bool = False):
        """
        Создаёт inline поле для выбора даты (для использования в таблице).
        Возвращает Container с минимальным TextField и иконкой.
        """
        # Форматируем начальное значение для отображения (российский формат)
        display_value = ""
        db_value = None
        
        if value:
            if isinstance(value, (date, datetime)):
                display_value = value.strftime("%d.%m.%Y" if not is_datetime else "%d.%m.%Y %H:%M")
                db_value = value.strftime("%Y-%m-%d" if not is_datetime else "%Y-%m-%d %H:%M:%S")
            else:
                # Пытаемся распарсить строку
                value_str = str(value)
                if value_str:
                    try:
                        if ' ' in value_str:  # datetime
                            # Пробуем разные форматы (с милисекундами и без)
                            for fmt in ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
                                try:
                                    dt = datetime.strptime(value_str, fmt)
                                    display_value = dt.strftime("%d.%m.%Y %H:%M")
                                    db_value = dt.strftime("%Y-%m-%d %H:%M:%S")
                                    break
                                except ValueError:
                                    continue
                            else:
                                display_value = value_str
                                db_value = value_str
                        else:  # date
                            dt = datetime.strptime(value_str, "%Y-%m-%d")
                            display_value = dt.strftime("%d.%m.%Y")
                            db_value = value_str
                    except:
                        display_value = value_str
                        db_value = value_str
        
        # Текстовое поле для отображения выбранной даты
        text_field = ft.TextField(
            value=display_value,
            read_only=True,
            border=ft.InputBorder.NONE,
            text_size=14,
            expand=True,
        )
        
        # Храним отдельно дату и время
        if db_value and ' ' in str(db_value):
            date_part, time_part = str(db_value).split(' ', 1)
            container_data = {'date_part': date_part, 'time_part': time_part}
        else:
            container_data = {'date_part': db_value or '', 'time_part': '00:00:00'}
        
        # DatePicker
        picker_key = f"{field}_{id(text_field)}"
        
        def update_display():
            """Обновляет отображаемое значение на основе date_part и time_part"""
            if is_datetime and container.data['date_part'] and container.data['time_part']:
                # Комбинируем дату и время
                try:
                    dt = datetime.strptime(f"{container.data['date_part']} {container.data['time_part']}", 
                                          "%Y-%m-%d %H:%M:%S")
                    text_field.value = dt.strftime("%d.%m.%Y %H:%M")
                    container.data['date_value'] = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass
            elif container.data['date_part']:
                # Только дата
                try:
                    dt = datetime.strptime(container.data['date_part'], "%Y-%m-%d")
                    text_field.value = dt.strftime("%d.%m.%Y")
                    container.data['date_value'] = container.data['date_part']
                except:
                    pass
        
        def on_date_change(e):
            if e.control.value:
                selected_date = e.control.value
                container.data['date_part'] = selected_date.strftime("%Y-%m-%d")
                update_display()
                e.page.update()
        
        date_picker = ft.DatePicker(
            on_change=on_date_change,
        )
        
        self.date_pickers[picker_key] = date_picker
        
        # Кнопка для открытия DatePicker
        def open_date_picker(e):
            e.page.open(date_picker)
        
        calendar_icon = ft.IconButton(
            icon=ft.Icons.CALENDAR_TODAY,
            icon_size=16,
            tooltip="Выбрать дату",
            on_click=open_date_picker,
        )
        
        buttons = [calendar_icon]
        
        # Для datetime добавляем TimePicker
        if is_datetime:
            def on_time_change(e):
                if e.control.value:
                    selected_time = e.control.value
                    container.data['time_part'] = selected_time.strftime("%H:%M:%S")
                    update_display()
                    e.page.update()
            
            time_picker = ft.TimePicker(
                on_change=on_time_change,
            )
            
            time_picker_key = f"{field}_time_{id(text_field)}"
            self.date_pickers[time_picker_key] = time_picker
            
            def open_time_picker(e):
                e.page.open(time_picker)
            
            time_icon = ft.IconButton(
                icon=ft.Icons.ACCESS_TIME,
                icon_size=16,
                tooltip="Выбрать время",
                on_click=open_time_picker,
            )
            buttons.append(time_icon)
        
        # Container с полем и иконками
        container = ft.Row(
            [text_field] + buttons,
            spacing=2,
            expand=True,
        )
        container.data = container_data
        container.data['date_value'] = db_value
        
        return container

    def _create_time_field(self, field: str, label: str, value=None):
        """
        Создаёт поле для выбора времени с TimePicker.
        Возвращает Container с TextField и кнопкой для открытия выбора времени.
        """
        # Форматируем начальное значение для отображения (российский формат HH:MM)
        display_value = ""
        db_value = None
        
        if value:
            if isinstance(value, datetime):
                display_value = value.strftime("%H:%M")
                db_value = value.strftime("%H:%M:%S")
            else:
                # Пытаемся распарсить строку
                value_str = str(value)
                if value_str:
                    try:
                        # Пробуем разные форматы времени
                        for fmt in ["%H:%M:%S.%f", "%H:%M:%S", "%H:%M"]:
                            try:
                                dt = datetime.strptime(value_str, fmt)
                                display_value = dt.strftime("%H:%M")
                                db_value = dt.strftime("%H:%M:%S")
                                break
                            except ValueError:
                                continue
                        else:
                            display_value = value_str
                            db_value = value_str
                    except:
                        display_value = value_str
                        db_value = value_str
        
        # Текстовое поле для отображения выбранного времени
        text_field = ft.TextField(
            label=label,
            value=display_value,
            read_only=True,
            expand=True,
        )
        
        # TimePicker
        picker_key = f"{field}_{id(text_field)}"
        
        def on_time_change(e):
            if e.control.value:
                selected_time = e.control.value
                text_field.value = selected_time.strftime("%H:%M")
                container.data['time_value'] = selected_time.strftime("%H:%M:%S")
                e.page.update()
        
        time_picker = ft.TimePicker(
            on_change=on_time_change,
        )
        
        self.date_pickers[picker_key] = time_picker
        
        # Кнопка для открытия TimePicker
        def open_time_picker(e):
            e.page.open(time_picker)
        
        time_button = ft.IconButton(
            icon=ft.Icons.ACCESS_TIME,
            tooltip="Выбрать время",
            on_click=open_time_picker,
        )
        
        # Container с полем и кнопкой
        container = ft.Container(
            content=ft.Row([text_field, time_button], spacing=5),
            expand=True,
            data={'time_value': db_value}
        )
        
        return container

    def _create_time_field_inline(self, field: str, value=None):
        """
        Создаёт inline поле для выбора времени (для использования в таблице).
        Возвращает Row с минимальным TextField и иконкой.
        """
        # Форматируем начальное значение для отображения (российский формат HH:MM)
        display_value = ""
        db_value = None
        
        if value:
            if isinstance(value, datetime):
                display_value = value.strftime("%H:%M")
                db_value = value.strftime("%H:%M:%S")
            else:
                # Пытаемся распарсить строку
                value_str = str(value)
                if value_str:
                    try:
                        # Пробуем разные форматы времени
                        for fmt in ["%H:%M:%S.%f", "%H:%M:%S", "%H:%M"]:
                            try:
                                dt = datetime.strptime(value_str, fmt)
                                display_value = dt.strftime("%H:%M")
                                db_value = dt.strftime("%H:%M:%S")
                                break
                            except ValueError:
                                continue
                        else:
                            display_value = value_str
                            db_value = value_str
                    except:
                        display_value = value_str
                        db_value = value_str
        
        # Текстовое поле для отображения выбранного времени
        text_field = ft.TextField(
            value=display_value,
            read_only=True,
            border=ft.InputBorder.NONE,
            text_size=14,
            expand=True,
        )
        
        # TimePicker
        picker_key = f"{field}_{id(text_field)}"
        
        def on_time_change(e):
            if e.control.value:
                selected_time = e.control.value
                text_field.value = selected_time.strftime("%H:%M")
                container.data['time_value'] = selected_time.strftime("%H:%M:%S")
                e.page.update()
        
        time_picker = ft.TimePicker(
            on_change=on_time_change,
        )
        
        self.date_pickers[picker_key] = time_picker
        
        # Кнопка для открытия TimePicker
        def open_time_picker(e):
            e.page.open(time_picker)
        
        time_icon = ft.IconButton(
            icon=ft.Icons.ACCESS_TIME,
            icon_size=16,
            tooltip="Выбрать время",
            on_click=open_time_picker,
        )
        
        # Container с полем и иконкой
        container = ft.Row(
            [text_field, time_icon],
            spacing=2,
            expand=True,
        )
        container.data = {'time_value': db_value}
        
        return container

    def create_add_form(self):
        new_fields = {}
        input_controls = []

        for field in list(self.field_configs.keys())[1:]:  # Пропускаем ID
            field_type = self.field_types.get(field, "text")
            
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
            elif field_type in ("date", "datetime"):
                # Создаём поле с кнопкой для выбора даты
                ctrl = self._create_date_field(
                    field=field,
                    label=self.field_configs[field].label,
                    value=None,
                    is_datetime=field_type == "datetime"
                )
            elif field_type == "time":
                # Создаём поле с кнопкой для выбора времени
                ctrl = self._create_time_field(
                    field=field,
                    label=self.field_configs[field].label,
                    value=None
                )
            else:
                ctrl = ft.TextField(label=self.field_configs[field].label, expand=True)

            new_fields[field] = ctrl
            input_controls.append(ctrl)

        def handle_add():
            try:
                fields = ", ".join(new_fields.keys())
                placeholders = ", ".join(["%s"] * len(new_fields))
                values = []
                for field_name, ctrl in new_fields.items():
                    # Для DateField и TimeField получаем значение из data атрибута
                    if hasattr(ctrl, 'data') and isinstance(ctrl.data, dict):
                        if 'date_value' in ctrl.data:
                            values.append(ctrl.data['date_value'])
                        elif 'time_value' in ctrl.data:
                            values.append(ctrl.data['time_value'])
                        else:
                            values.append(ctrl.value)
                    else:
                        values.append(ctrl.value)
                
                insert_query = (
                    f"INSERT INTO {self.table_name} ({fields}) VALUES ({placeholders})"
                )
                self.cursor.execute(insert_query, values)
                self.cursor.connection.commit()
                
                # Очищаем поля
                for field_name, ctrl in new_fields.items():
                    if hasattr(ctrl, 'data') and isinstance(ctrl.data, dict):
                        # Для date/time полей: Container -> content (Row) -> controls[0] (TextField)
                        if 'date_value' in ctrl.data:
                            ctrl.data['date_value'] = None
                        if 'time_value' in ctrl.data:
                            ctrl.data['time_value'] = None
                        if hasattr(ctrl, 'content') and hasattr(ctrl.content, 'controls'):
                            text_field = ctrl.content.controls[0]
                            text_field.value = ""
                    else:
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
        
        if self.where_clause:
            query += f" WHERE {self.where_clause}"
            self.cursor.execute(query, self.where_params)
        else:
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

                field_type = self.field_types.get(field, "text")

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
                elif field_type in ("date", "datetime"):
                    # Для дат создаём специальное поле
                    ctrl = ft.Container(
                        content=self._create_date_field_inline(
                            field=field,
                            value=value,
                            is_datetime=field_type == "datetime"
                        ),
                        padding=5,
                        expand=True,
                    )
                elif field_type == "time":
                    # Для времени создаём специальное поле
                    ctrl = ft.Container(
                        content=self._create_time_field_inline(
                            field=field,
                            value=value
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

                # Для date/time полей сохраняем Container, а не его content
                if field_type in ("date", "datetime", "time"):
                    field_controls[field] = ctrl.content
                else:
                    field_controls[field] = ctrl.content
                    
                cells.append(ft.DataCell(ctrl))

            def make_save_callback(record_id, controls):
                def save(e):
                    try:
                        update_fields = ", ".join(
                            f"{field} = %s" for field in controls.keys()
                        )
                        values = []
                        for field_name, ctrl in controls.items():
                            # Для date/time полей получаем значение из data атрибута
                            if hasattr(ctrl, 'data') and isinstance(ctrl.data, dict):
                                if 'date_value' in ctrl.data:
                                    values.append(ctrl.data['date_value'])
                                elif 'time_value' in ctrl.data:
                                    values.append(ctrl.data['time_value'])
                                else:
                                    values.append(ctrl.value)
                            else:
                                values.append(ctrl.value)
                        
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
