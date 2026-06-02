from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

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
    field_type: str | None = None  # "text", "date", "datetime", "time", "image", "number", etc.
    default_image: str | None = None
    image_width: int = 72
    image_height: int = 72


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
    - Для изображений используйте field_type="image" (в значении поля хранится путь к файлу)
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
            pk_mapping={"task_id": "ID"},
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
        pk_mapping: dict[str, str],
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
        if len(pk_mapping) != 1:
            raise ValueError("pk_mapping должен содержать ровно одно поле первичного ключа")
        self.pk_field, self.pk_label = next(iter(pk_mapping.items()))
        if self.pk_field not in self.field_configs:
            raise ValueError("Поле из pk_mapping должно присутствовать в field_mapping")
        self.width = width
        self.height = height
        self.where_clause = where_clause
        self.where_params = where_params or ()
        self.field_types = self._detect_field_types()
        self.dropdown_options = self._generate_dropdown_options()
        self.row_checkboxes: list[tuple[ft.Checkbox, dict]] = []  # (checkbox, row_data)
        self.header_checkbox: ft.Checkbox = None
        self.date_pickers: dict[str, ft.DatePicker] = {}  # Хранилище DatePicker'ов
        self.file_pickers: list[ft.FilePicker] = []  # Хранилище FilePicker'ов

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

    def _get_data_row_min_height(self) -> int:
        """
        Возвращает минимальную высоту строки таблицы с учетом image-полей.
        """
        image_heights = [
            cfg.image_height
            for cfg in self.field_configs.values()
            if cfg.field_type == "image"
        ]
        if not image_heights:
            return 48
        # +16 для внутренних отступов контейнера ячейки (padding=5 + запас)
        return max(48, max(image_heights) + 16)

    def _show_alert(self, page: ft.Page, title: str, message: str):
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("OK", on_click=lambda _: page.pop_dialog())],
        )
        page.show_dialog(dialog)

    def _generate_dropdown_options(self):
        options = {}
        for field, cfg in self.field_configs.items():
            # Настройки FK: явно через FieldConfig.foreign_key или по шаблону *_id
            ref_cfg = cfg.foreign_key
            if ref_cfg or (field.endswith("_id") and field != self.pk_field):
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
                e.page.pop_dialog()
                e.page.update()
        
        date_picker = ft.DatePicker(
            on_change=on_date_change,
        )
        
        self.date_pickers[picker_key] = date_picker
        
        # Кнопка для открытия DatePicker
        def open_date_picker(e):
            e.page.show_dialog(date_picker)
        
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
                    e.page.pop_dialog()
                    e.page.update()
            
            time_picker = ft.TimePicker(
                on_change=on_time_change,
            )
            
            time_picker_key = f"{field}_time_{id(text_field)}"
            self.date_pickers[time_picker_key] = time_picker
            
            def open_time_picker(e):
                e.page.show_dialog(time_picker)
            
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
                e.page.pop_dialog()
                e.page.update()
        
        date_picker = ft.DatePicker(
            on_change=on_date_change,
        )
        
        self.date_pickers[picker_key] = date_picker
        
        # Кнопка для открытия DatePicker
        def open_date_picker(e):
            e.page.show_dialog(date_picker)
        
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
                    e.page.pop_dialog()
                    e.page.update()
            
            time_picker = ft.TimePicker(
                on_change=on_time_change,
            )
            
            time_picker_key = f"{field}_time_{id(text_field)}"
            self.date_pickers[time_picker_key] = time_picker
            
            def open_time_picker(e):
                e.page.show_dialog(time_picker)
            
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
                e.page.pop_dialog()
                e.page.update()
        
        time_picker = ft.TimePicker(
            on_change=on_time_change,
        )
        
        self.date_pickers[picker_key] = time_picker
        
        # Кнопка для открытия TimePicker
        def open_time_picker(e):
            e.page.show_dialog(time_picker)
        
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
                e.page.pop_dialog()
                e.page.update()
        
        time_picker = ft.TimePicker(
            on_change=on_time_change,
        )
        
        self.date_pickers[picker_key] = time_picker
        
        # Кнопка для открытия TimePicker
        def open_time_picker(e):
            e.page.show_dialog(time_picker)
        
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

    def _create_image_field_inline(self, field: str, value=None):
        """
        Создаёт inline отображение изображения с выбором файла через FilePicker.
        """
        cfg = self.field_configs[field]
        image_path = "" if value is None else str(value)
        default_image = cfg.default_image or ""
        preview_src = image_path or default_image
        file_picker = ft.FilePicker()
        self.file_pickers.append(file_picker)
        preview = ft.Image(
            src=preview_src,
            width=cfg.image_width,
            height=cfg.image_height,
            # fit=ft.BoxFit.CONTAIN,
        )
        row = ft.Row(
            [preview],
            spacing=8,
            expand=True,
            data={
                "image_value": image_path,
                "default_image": default_image,
                "image_preview": preview,
            },
        )

        async def open_file_picker(e):
            files = await file_picker.pick_files(
                dialog_title="Выберите изображение",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["jpg", "jpeg", "png", "gif", "webp", "bmp", "svg"],
                allow_multiple=False,
            )
            if files:
                selected = files[0]
                selected_path = selected.path or selected.name or ""
                preview.src = selected_path or default_image
                row.data["image_value"] = selected_path
                e.page.update()

        pick_button = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            icon_size=16,
            tooltip="Выбрать файл",
            on_click=open_file_picker,
        )
        row.controls.append(pick_button)
        return row

    def _create_image_field(self, field: str, label: str, value=None, default_image: str | None = None):
        """
        Создаёт поле с превью изображения и выбором файла через FilePicker.
        Возвращает Container, значение пути хранится в data['image_value'].
        """
        cfg = self.field_configs[field]
        image_path = "" if value is None else str(value)
        initial_value = image_path or (default_image or "")
        file_picker = ft.FilePicker()
        self.file_pickers.append(file_picker)
        preview = ft.Image(
            src=initial_value,
            width=cfg.image_width,
            height=cfg.image_height,
            # fit=ft.BoxFit.CONTAIN,
        )

        container = ft.Container(
            content=ft.Row([], spacing=8),
            expand=True,
            data={
                "image_value": initial_value,
                "default_image": default_image or "",
                "image_preview": preview,
            },
        )

        def sync_value(new_value: str):
            preview.src = new_value
            container.data["image_value"] = new_value

        async def open_file_picker(e):
            files = await file_picker.pick_files(
                dialog_title="Выберите изображение",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["jpg", "jpeg", "png", "gif", "webp", "bmp", "svg"],
                allow_multiple=False,
            )
            if files:
                selected = files[0]
                selected_path = selected.path or selected.name or ""
                sync_value(selected_path or (default_image or ""))
                e.page.update()

        pick_button = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="Выбрать файл",
            on_click=open_file_picker,
        )
        container.content = ft.Column(
            controls=[
                ft.Text(label),
                ft.Row([preview, pick_button], spacing=8, expand=True),
            ],
            spacing=4,
        )
        return container

    def _get_non_pk_fields(self) -> list[str]:
        return [field for field in self.field_configs.keys() if field != self.pk_field]

    def _create_form_control(self, field: str, value=None):
        field_type = self.field_types.get(field, "text")

        if field in self.dropdown_options:
            return ft.Dropdown(
                options=[
                    ft.DropdownOption(key=str(k), text=str(v))
                    for k, v in self.dropdown_options[field]
                ],
                value=str(value) if value is not None else None,
                expand=True,
                label=self.field_configs[field].label,
            )
        if field_type in ("date", "datetime"):
            return self._create_date_field(
                field=field,
                label=self.field_configs[field].label,
                value=value,
                is_datetime=field_type == "datetime",
            )
        if field_type == "time":
            return self._create_time_field(
                field=field,
                label=self.field_configs[field].label,
                value=value,
            )
        if field_type == "image":
            return self._create_image_field(
                field=field,
                label=self.field_configs[field].label,
                value=value,
                default_image=self.field_configs[field].default_image,
            )
        return ft.TextField(
            label=self.field_configs[field].label,
            value="" if value is None else str(value),
            expand=True,
        )

    def _extract_control_value(self, ctrl):
        if hasattr(ctrl, "data") and isinstance(ctrl.data, dict):
            if "date_value" in ctrl.data:
                return ctrl.data["date_value"]
            if "time_value" in ctrl.data:
                return ctrl.data["time_value"]
            if "image_value" in ctrl.data:
                return ctrl.data["image_value"]
        return ctrl.value if hasattr(ctrl, "value") else None

    def _is_int_field(self, field_name: str) -> bool:
        field_type = (self.field_types.get(field_name, "text") or "").lower()
        return field_name.endswith("_id") or field_type in ("int", "integer")
    
    def _is_float_field(self, field_name: str) -> bool:
        field_type = (self.field_types.get(field_name, "text") or "").lower()
        return field_type == "float"

    def _validate_input_fields(self, values_by_field: dict[str, object], page: ft.Page | None = None) -> bool:
        for field_name, raw_value in values_by_field.items():
            value = "" if raw_value is None else str(raw_value).strip()
            label = self.field_configs[field_name].label
            if value == "":
                if page:
                    self._show_alert(page, "Ошибка", f"Поле '{label}' обязательно для заполнения")
                return False
            if self._is_int_field(field_name):
                try:
                    int(value)
                except ValueError:
                    if page:
                        self._show_alert(page, "Ошибка", f"Поле '{label}' должно быть числом")
                    return False
            elif self._is_float_field(field_name):
                try:
                    float(value)
                except ValueError:
                    if page:
                        self._show_alert(page, "Ошибка", f"Поле '{label}' должно быть числом")
                    return False
            elif (field_type := (self.field_types.get(field_name, "text") or "").lower()).startswith("decimal"):
                try:
                    # decimal-8-2 -> precision=8, scale=2
                    parts = field_type.split("-")

                    if len(parts) == 3:
                        precision = int(parts[1])
                        scale = int(parts[2])
                    else:
                        precision = None
                        scale = None

                    dec_value = Decimal(value)

                    # Проверка количества знаков после точки
                    if scale is not None:
                        exponent = abs(dec_value.as_tuple().exponent)
                        if exponent > scale:
                            raise ValueError(
                                f"Допустимо не более {scale} знаков после запятой"
                            )

                    # Проверка общего количества цифр
                    if precision is not None:
                        digits_count = len(dec_value.as_tuple().digits)
                        if digits_count > precision:
                            raise ValueError(
                                f"Допустимо не более {precision} цифр"
                            )

                except (InvalidOperation, ValueError):
                    if page:
                        self._show_alert(
                            page,
                            "Ошибка",
                            f"Поле '{label}' должно быть с {scale} знаками после запятой и {precision} знаками всего"
                        )
                    return False
        return True

    def _clear_form_controls(self, controls_by_field: dict[str, object]):
        for field_name, ctrl in controls_by_field.items():
            if hasattr(ctrl, "data") and isinstance(ctrl.data, dict):
                if "date_value" in ctrl.data:
                    ctrl.data["date_value"] = None
                    if hasattr(ctrl, "content") and hasattr(ctrl.content, "controls"):
                        for item in ctrl.content.controls:
                            if isinstance(item, ft.TextField):
                                item.value = ""
                if "time_value" in ctrl.data:
                    ctrl.data["time_value"] = None
                    if hasattr(ctrl, "content") and hasattr(ctrl.content, "controls"):
                        for item in ctrl.content.controls:
                            if isinstance(item, ft.TextField):
                                item.value = ""
                if "image_value" in ctrl.data:
                    default_value = self.field_configs[field_name].default_image or ""
                    ctrl.data["image_value"] = default_value
                    preview = ctrl.data.get("image_preview")
                    if preview is not None:
                        preview.src = default_value
            elif hasattr(ctrl, "value"):
                ctrl.value = ""

    def _show_delete_confirmation(self, page: ft.Page, on_confirm):
        def confirm_and_close(_):
            page.pop_dialog()
            on_confirm()

        dialog = ft.AlertDialog(
            title=ft.Text("Подтверждение удаления"),
            content=ft.Text("Вы уверены, что хотите удалить объект?"),
            actions=[
                ft.TextButton("Отмена", on_click=lambda _: page.pop_dialog()),
                ft.TextButton(
                    "Удалить",
                    on_click=confirm_and_close,
                ),
            ],
        )
        page.show_dialog(dialog)

    def create_add_form(self):
        self.file_pickers = []
        new_fields = {}
        input_controls = []

        for field in self._get_non_pk_fields():
            ctrl = self._create_form_control(field=field, value=None)
            new_fields[field] = ctrl
            input_controls.append(ctrl)

        def handle_add(e=None):
            page = e.page if e and hasattr(e, "page") else None
            try:
                values_by_field = {
                    field_name: self._extract_control_value(ctrl)
                    for field_name, ctrl in new_fields.items()
                }
                if not self._validate_input_fields(values_by_field, page):
                    return False, "Ошибка валидации"

                fields = ", ".join(new_fields.keys())
                placeholders = ", ".join(["%s"] * len(new_fields))
                values = [values_by_field[field_name] for field_name in new_fields.keys()]
                
                insert_query = (
                    f"INSERT INTO {self.table_name} ({fields}) VALUES ({placeholders})"
                )
                self.cursor.execute(insert_query, values)
                self.cursor.connection.commit()
                
                self._clear_form_controls(new_fields)
                
                print("[INFO] Запись добавлена:", values)
                if page:
                    self._show_alert(page, "Успех", "Запись успешно добавлена")
                return True, "Успешно добавлено"
            except Exception as ex:
                print("[ERROR] Ошибка добавления:", str(ex))
                if page:
                    self._show_alert(page, "Ошибка", f"Не удалось добавить запись: {str(ex)}")
                return False, f"Ошибка: {str(ex)}"

        form_row = ft.Column(input_controls, spacing=10)
        return form_row, handle_add

    def create_edit_form(self, record_id: int):
        self.file_pickers = []
        editable_fields = self._get_non_pk_fields()
        query = f"SELECT {', '.join(self.field_configs.keys())} FROM {self.table_name} WHERE {self.pk_field} = %s"
        self.cursor.execute(query, (record_id,))
        row = self.cursor.fetchone()
        if row is None:
            raise ValueError(f"Запись с ID {record_id} не найдена")

        row_data = {field: value for field, value in zip(self.field_configs.keys(), row)}
        edit_fields = {}
        input_controls = []
        for field in editable_fields:
            ctrl = self._create_form_control(field=field, value=row_data.get(field))
            edit_fields[field] = ctrl
            input_controls.append(ctrl)

        def handle_save(e=None):
            page = e.page if e and hasattr(e, "page") else None
            try:
                values_by_field = {
                    field_name: self._extract_control_value(ctrl)
                    for field_name, ctrl in edit_fields.items()
                }
                if not self._validate_input_fields(values_by_field, page):
                    return False, "Ошибка валидации"

                update_fields = ", ".join(f"{field} = %s" for field in edit_fields.keys())
                values = [values_by_field[field_name] for field_name in edit_fields.keys()]
                update_query = (
                    f"UPDATE {self.table_name} SET {update_fields} WHERE {self.pk_field} = %s"
                )
                self.cursor.execute(update_query, (*values, record_id))
                self.cursor.connection.commit()
                if page:
                    self._show_alert(page, "Успех", "Запись успешно обновлена")
                return True, "Успешно обновлено"
            except Exception as ex:
                if page:
                    self._show_alert(page, "Ошибка", f"Не удалось обновить запись: {str(ex)}")
                return False, f"Ошибка: {str(ex)}"

        def handle_delete(e=None):
            page = e.page if e and hasattr(e, "page") else None
            if page:
                self._handle_delete(record_id)(e)
                return True, "Удаление запрошено"
            return False, "Не удалось удалить запись: отсутствует page"

        save_button = ft.Button("Сохранить", icon=ft.Icons.SAVE, on_click=handle_save)
        delete_button = ft.Button(
            "Удалить",
            icon=ft.Icons.DELETE,
            bgcolor=ft.Colors.RED_100,
            on_click=handle_delete,
        )
        form_column = ft.Column(
            controls=[
                ft.Text(f"{self.pk_label}: {record_id}", size=16, weight=ft.FontWeight.BOLD),
                *input_controls,
                # ft.Row([save_button, delete_button], spacing=10),
            ],
            spacing=10,
        )
        return form_column, handle_save, handle_delete

    def create_table(self):
        self.file_pickers = []
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

        pk_index = list(db_fields).index(self.pk_field)
        rows = []
        for row in data:
            record_id = row[pk_index]
            cells = []
            field_controls = {}

            # Собираем данные строки в словарь
            row_data = {field: value for field, value in zip(db_fields, row)}

            # Создаём чекбокс для строки
            row_checkbox = ft.Checkbox(value=False)
            self.row_checkboxes.append((row_checkbox, row_data))
            cells.append(ft.DataCell(row_checkbox))

            for field, value in zip(db_fields, row):
                if field == self.pk_field:
                    cells.append(ft.DataCell(ft.Text(str(value))))
                    continue

                field_type = self.field_types.get(field, "text")
                value_control = None

                if field in self.dropdown_options:
                    ctrl = ft.Container(
                        content=ft.Dropdown(
                            options=[
                                ft.DropdownOption(key=str(k), text=v)
                                for k, v in self.dropdown_options[field]
                            ],
                            value=str(value),
                            expand=True,
                        ),
                        padding=5,
                        expand=True,
                    )
                    value_control = ctrl.content
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
                    value_control = ctrl.content
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
                    value_control = ctrl.content
                elif field_type == "image":
                    image_row = self._create_image_field_inline(
                        field=field,
                        value=value,
                    )
                    ctrl = ft.Container(
                        content=image_row,
                        padding=5,
                        expand=True,
                    )
                    value_control = image_row
                else:
                    ctrl = ft.Container(
                        content=ft.TextField(
                            value=str(value), border=ft.InputBorder.NONE, expand=True
                        ),
                        padding=5,
                        expand=True,
                    )
                    value_control = ctrl.content
                
                field_controls[field] = value_control
                    
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
                        
                        update_query = f"UPDATE {self.table_name} SET {update_fields} WHERE {self.pk_field} = %s"
                        self.cursor.execute(update_query, (*values, record_id))
                        self.cursor.connection.commit()
                        e.page.show_dialog(ft.SnackBar(ft.Text("Изменения сохранены")))
                        print(f"[LOG] Updated record {record_id} with values {values}")
                    except Exception as ex:
                        e.page.show_dialog(ft.SnackBar(ft.Text(f"Ошибка: {str(ex)}")))
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
            data_row_min_height=self._get_data_row_min_height(),
            data_row_max_height=float("inf"),
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
            page = e.page if e and hasattr(e, "page") else None
            if not page:
                return

            def confirm_delete():
                try:
                    delete_query = f"DELETE FROM {self.table_name} WHERE {self.pk_field} = %s"
                    self.cursor.execute(delete_query, (record_id,))
                    self.cursor.connection.commit()
                    page.show_dialog(ft.SnackBar(ft.Text("Запись удалена!")))
                    page.update()
                except Exception as ex:
                    print(ex)
                    page.show_dialog(ft.SnackBar(ft.Text(f"Ошибка: {str(ex)}")))
                    page.update()

            self._show_delete_confirmation(page, confirm_delete)

        return callback
