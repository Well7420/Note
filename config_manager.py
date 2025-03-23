import json
import os


class ConfigManager:
    def __init__(self, config_file="notepad_config.json"):
        self.config_file = config_file

    def load_config(self, default_config=None):
        """Загрузка настроек из файла или возврат значений по умолчанию"""
        if default_config is None:
            default_config = {
                "theme": "dark",
                "font_size": 12,
                "geometry": "700x500",
                "opacity": 0.87  # Добавляем прозрачность по умолчанию
            }
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    config = json.load(f)
                    default_config.update(config)
            except (json.JSONDecodeError, IOError):
                pass
        return default_config

    def save_config(self, config):
        """Сохранение настроек в файл"""
        try:
            with open(self.config_file, "w") as f:
                json.dump(config, f)
        except IOError as e:
            print(f"Не удалось сохранить настройки: {e}")
