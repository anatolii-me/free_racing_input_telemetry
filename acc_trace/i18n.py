from __future__ import annotations


STRINGS = {
    "ru": {
        "settings": "Настройки", "settings_title": "Настройки · ACC Trace",
        "subtitle": "Настройте вид панели и источник телеметрии.",
        "appearance": "ВНЕШНИЙ ВИД", "wheel_style": "Вид руля",
        "formula": "Штурвал", "sport": "Руль", "classic": "Классический руль",
        "info_position": "Подсказки и кнопки", "top": "Сверху", "bottom": "Снизу",
        "language": "Язык", "display": "ГРАФИК И ОТКЛИК",
        "graph_speed": "Скорость графика", "smoothing": "Сглаживание",
        "avoid_trace_overlap": "Раздвигать линии при совпадении",
        "opacity": "Непрозрачность", "steering_lock": "Поворот руля от упора до упора",
        "update_rate": "Обновление / FPS", "source_section": "ИСТОЧНИК И ОСИ",
        "source": "Источник педалей и руля", "acc": "Телеметрия ACC",
        "controller": "Руль / геймпад", "demo": "Демо",
        "source_hint": "ACC считывает игровые значения; оси ниже нужны для прямого чтения контроллера.",
        "device": "Устройство", "refresh": "Обновить", "gas": "Газ",
        "brake": "Тормоз", "steer": "Руль", "invert": "Инверсия",
        "visibility": "ПОКАЗЫВАТЬ", "speed": "Скорость", "gear": "Передача",
        "defaults": "По умолчанию", "cancel": "Отмена", "save": "Сохранить",
        "select_device": "Выберите режим руля для поиска устройства",
        "no_device": "Устройство не найдено", "old_device": "Ранее выбранное устройство (отключено)",
        "axis_unavailable": "Ось {index} недоступна в WinMM",
        "rate_item": "{rate} Гц · до {rate} FPS", "milliseconds": "мс",
        "status_wait_acc": "ОЖИДАНИЕ ACC", "status_wait_wheel": "ОЖИДАНИЕ РУЛЯ",
        "status_windows": "ТОЛЬКО WINDOWS", "status_wheel_windows": "РУЛЬ: ТОЛЬКО WINDOWS",
        "status_axes": "НАСТРОЙТЕ ОСИ", "status_demo": "ДЕМО · ПРЕВЬЮ",
        "status_wheel_live": "РУЛЬ · LIVE",
        "history": "ИСТОРИЯ НАЖАТИЙ", "kmh": "КМ/Ч", "hz": "ГЦ / FPS",
        "show_overlay": "Показать оверлей", "quit": "Выход",
    },
    "en": {
        "settings": "Settings", "settings_title": "Settings · ACC Trace",
        "subtitle": "Customize the overlay and telemetry source.",
        "appearance": "APPEARANCE", "wheel_style": "Wheel style",
        "formula": "Formula", "sport": "Sport wheel", "classic": "Classic wheel",
        "info_position": "Hints and controls", "top": "Top", "bottom": "Bottom",
        "language": "Language", "display": "GRAPH AND RESPONSE",
        "graph_speed": "Graph speed", "smoothing": "Smoothing",
        "avoid_trace_overlap": "Separate overlapping traces",
        "opacity": "Opacity", "steering_lock": "Wheel rotation, lock to lock",
        "update_rate": "Refresh / FPS", "source_section": "SOURCE AND AXES",
        "source": "Pedal and wheel source", "acc": "ACC telemetry",
        "controller": "Wheel / gamepad", "demo": "Demo",
        "source_hint": "ACC reads in-game values; the axes below are used for direct controller input.",
        "device": "Device", "refresh": "Refresh", "gas": "Gas",
        "brake": "Brake", "steer": "Wheel", "invert": "Invert",
        "visibility": "SHOW", "speed": "Speed", "gear": "Gear",
        "defaults": "Defaults", "cancel": "Cancel", "save": "Save",
        "select_device": "Select wheel mode to find a device",
        "no_device": "No device found", "old_device": "Previously selected device (disconnected)",
        "axis_unavailable": "Axis {index} unavailable in WinMM",
        "rate_item": "{rate} Hz · up to {rate} FPS", "milliseconds": "ms",
        "status_wait_acc": "WAITING FOR ACC", "status_wait_wheel": "WAITING FOR WHEEL",
        "status_windows": "WINDOWS ONLY", "status_wheel_windows": "WHEEL: WINDOWS ONLY",
        "status_axes": "SET UP AXES", "status_demo": "DEMO · PREVIEW",
        "status_wheel_live": "WHEEL · LIVE",
        "history": "INPUT HISTORY", "kmh": "KM/H", "hz": "HZ / FPS",
        "show_overlay": "Show overlay", "quit": "Quit",
    },
}


def tr(language: str, key: str, **values: object) -> str:
    return STRINGS.get(language, STRINGS["ru"]).get(key, key).format(**values)


def status_label(language: str, label: str) -> str:
    status_keys = {
        "ОЖИДАНИЕ ACC": "status_wait_acc", "ОЖИДАНИЕ РУЛЯ": "status_wait_wheel",
        "ТОЛЬКО WINDOWS": "status_windows", "РУЛЬ: ТОЛЬКО WINDOWS": "status_wheel_windows",
        "НАСТРОЙТЕ ОСИ": "status_axes", "ДЕМО · PREVIEW": "status_demo",
        "РУЛЬ · LIVE": "status_wheel_live",
    }
    return tr(language, status_keys[label]) if label in status_keys else label
