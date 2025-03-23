import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.ttk import Notebook
import re
import threading
from queue import Queue
from config_manager import ConfigManager
import chardet
import os


class Notepad:
    def __init__(self, root):
        self.root = root
        self.root.title("Note")

        # Очередь для асинхронной подсветки
        self.highlight_queue = Queue()

        # Панель инструментов
        self.toolbar = tk.Frame(self.root)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        tk.Button(self.toolbar, text="Новый", command=self.new_file, bg="gray", fg="lightgray").pack(
            side=tk.LEFT, padx=2, pady=2)
        tk.Button(self.toolbar, text="Открыть", command=self.open_file, bg="gray", fg="lightgray").pack(
            side=tk.LEFT, padx=2, pady=2)
        tk.Button(self.toolbar, text="Сохранить", command=self.save_file, bg="gray", fg="lightgray").pack(
            side=tk.LEFT, padx=2, pady=2)
        tk.Button(self.toolbar, text="Найти", command=self.find_text, bg="gray", fg="lightgray").pack(
            side=tk.LEFT, padx=2, pady=2)

        # Ползунок для прозрачности
        self.opacity_frame = tk.Frame(self.root)
        self.opacity_frame.pack(side=tk.TOP, fill=tk.X)
        tk.Label(self.opacity_frame, text="Прозрачность:").pack(
            side=tk.LEFT, padx=5)
        self.opacity_scale = tk.Scale(
            self.opacity_frame, from_=0.1, to=1.0, orient=tk.HORIZONTAL, command=self.set_opacity,
            resolution=0.01  # Устанавливаем шаг 0.01
        )
        self.opacity_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.opacity_scale.bind("<Button-1>", self.on_scale_click)
        self.set_opacity(0.5)

        # Начальный шрифт
        self.font_size = 12

        # Темы
        self.themes = {
            "dark": {
                "bg": "black",
                "fg": "white",
                "insertbg": "white",
                "keyword": "#00FFFF",
                "string": "#00FF00",
                "comment": "#AAAAAA",
                "select_bg": "#555555",  # Цвет фона выделения для темной темы
                "select_fg": "white"     # Цвет текста выделения для темной темы
            },
            "light": {
                "bg": "white",
                "fg": "black",
                "insertbg": "black",
                "keyword": "blue",
                "string": "green",
                "comment": "gray",
                "select_bg": "#ADD8E6",  # Цвет фона выделения для светлой темы
                "select_fg": "black"     # Цвет текста выделения для светлой темы
            }
        }
        self.current_theme = "dark"

        # Вкладки
        self.notebook = Notebook(self.root)
        self.notebook.pack(expand=True, fill="both")
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        self.notebook.bind("<Button-3>", self.on_tab_right_click)
        self.tabs = {}
        self.add_tab()

        # Список ключевых слов Python
        self.keywords = [
            "def", "class", "if", "else", "elif", "for", "while", "try",
            "except", "import", "from", "as", "with", "return", "break",
            "continue", "pass", "True", "False", "None"
        ]

        # Создаем меню
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)

        # Меню "Файл"
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Файл", menu=self.file_menu)
        self.file_menu.add_command(
            label="Новый (Ctrl+N)", command=self.new_file)
        self.file_menu.add_command(
            label="Открыть (Ctrl+O)", command=self.open_file)
        self.file_menu.add_command(
            label="Сохранить (Ctrl+S)", command=self.save_file)
        self.file_menu.add_command(
            label="Сохранить как", command=self.save_as_file)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Выход", command=self.exit_app)

        # Меню "Тема"
        self.theme_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Тема", menu=self.theme_menu)
        self.theme_menu.add_command(
            label="Темная", command=lambda: self.set_theme("dark"))
        self.theme_menu.add_command(
            label="Светлая", command=lambda: self.set_theme("light"))

        # Загрузка настроек через ConfigManager
        self.config_manager = ConfigManager()
        config = self.config_manager.load_config(default_config={
            "theme": "dark",
            "font_size": 14,
            "geometry": "700x500",
            "opacity": 0.87
        })
        self.current_theme = config["theme"]
        self.font_size = config["font_size"]
        self.root.geometry(config["geometry"])
        self.opacity_scale.set(config["opacity"])
        self.set_opacity(config["opacity"])
        self.apply_theme()
        for tab_info in self.tabs.values():
            tab_info["text"].config(font=("Courier", self.font_size))

        # Настройка подсветки синтаксиса и событий для текущей вкладки
        self.setup_syntax_highlighting()
        self.setup_font_resize()

        # Привязка горячих клавиш
        self.setup_hotkeys()

        # Запуск асинхронного обработчика подсветки
        self.root.after(100, self.process_highlight_queue)

    def on_scale_click(self, event):
        # Обработка клика на ползунок для установки прозрачности по позиции клика
        scale_width = self.opacity_scale.winfo_width()
        click_x = event.x
        fraction = click_x / scale_width
        new_value = 0.1 + fraction * (1.0 - 0.1)
        self.opacity_scale.set(new_value)
        self.set_opacity(new_value)

    def set_opacity(self, value):
        # Установка прозрачности окна
        opacity = float(value)
        self.root.attributes("-alpha", opacity)

    def setup_hotkeys(self):
        # Настройка стандартных горячих клавиш
        self.root.bind(
            "<Control-c>", lambda event: self.copy_text(event))
        self.root.bind(
            "<Control-x>", lambda event: self.text_area.event_generate("<<Cut>>"))
        self.root.bind(
            "<Control-s>", lambda event: self.save_file())
        self.root.bind(
            "<Control-o>", lambda event: self.open_file())
        self.root.bind(
            "<Control-n>", lambda event: self.new_file())
        self.root.bind(
            "<Control-z>", lambda event: self.text_area.edit_undo())
        self.root.bind(
            "<Control-y>", lambda event: self.text_area.edit_redo())
        self.root.bind(
            "<Control-f>", lambda event: self.find_text())
        self.root.bind(
            "<Control-a>", self.select_all_without_highlight)

    def copy_text(self, event):
        # Кастомная функция для копирования текста#
        tab_info = self.get_current_tab()
        if not tab_info:
            return "break"
        text_area = tab_info["text"]
        if text_area.tag_ranges("sel"):
            selected_text = text_area.get("sel.first", "sel.last")
            self.root.clipboard_clear()
            self.root.clipboard_append(selected_text)
        return "break"

    def paste_text(self, event):
        # Кастомная функция для вставки текста
        tab_info = self.get_current_tab()
        if not tab_info:
            return "break"
        text_area = tab_info["text"]

        try:
            # Получаем текст из буфера обмена
            clipboard_text = self.root.clipboard_get()
            # Удаляем лишние символы новой строки, если они есть
            clipboard_text = clipboard_text.rstrip('\n')
        except tk.TclError:
            # Если буфер обмена пуст или недоступен, ничего не делаем
            return "break"

        # Если есть выделенный текст, удаляем его
        if text_area.tag_ranges("sel"):
            sel_start = text_area.index("sel.first")
            sel_end = text_area.index("sel.last")
            text_area.delete(sel_start, sel_end)

        # Вставляем текст в текущую позицию курсора
        current_pos = text_area.index(tk.INSERT)
        text_area.insert(current_pos, clipboard_text)

        # Перемещаем курсор в конец вставленного текста
        new_pos = f"{current_pos}+{len(clipboard_text)}c"
        text_area.mark_set(tk.INSERT, new_pos)

        # Очищаем выделение после вставки
        text_area.tag_remove("sel", "1.0", "end")

        return "break"

    def select_all_without_highlight(self, event):
        # Выделение всего текста с использованием стандартного тега 'sel'
        tab_info = self.get_current_tab()
        if not tab_info:
            return "break"
        text_area = tab_info["text"]
        # Удаляем предыдущее выделение
        text_area.tag_remove("sel", "1.0", "end")
        # Добавляем стандартное выделение
        # Исключаем последний символ (обычно \n)
        text_area.tag_add("sel", "1.0", "end-1c")
        # Устанавливаем фокус на текстовое поле, чтобы выделение было активным
        text_area.focus_set()
        return "break"

    def add_tab(self):
        # Добавление новой вкладки
        frame = tk.Frame(self.notebook)
        text_area = tk.Text(frame, wrap="word", undo=True,
                            font=("Courier", self.font_size))
        text_area.pack(expand=True, fill="both")
        self.notebook.add(frame, text="Новый файл")
        self.tabs[text_area] = {"file": None, "text": text_area}
        self.text_area = text_area
        # Привязываем <Control-v> к paste_text для этого текстового поля
        text_area.bind("<Control-v>", self.paste_text)
        # Привязываем <Control-c> к copy_text для этого текстового поля
        text_area.bind("<Control-c>", self.copy_text)
        self.apply_theme()
        self.setup_syntax_highlighting()
        self.notebook.select(frame)

    def on_tab_changed(self, event):
        # Обновление текущей вкладки при переключении
        self.get_current_tab()
        self.queue_highlight()

    def on_tab_right_click(self, event):
        # Обработка правого клика по вкладке для закрытия
        tab = self.notebook.tk.call(
            self.notebook._w, "identify", "tab", event.x, event.y)
        if tab != "":
            self.close_tab(tab)

    def close_tab(self, tab_index):
        # Закрытие вкладки с проверкой несохраненных изменений
        if len(self.notebook.tabs()) <= 1:
            return
        frame = self.notebook.tabs()[tab_index]
        for text_area, info in list(self.tabs.items()):
            if str(text_area.master) == str(frame):
                if text_area.get("1.0", tk.END).strip():
                    self.text_area = text_area
                    if messagebox.askyesno("Сохранить?", "Хотите сохранить перед закрытием?"):
                        self.save_file()
                self.notebook.forget(tab_index)
                del self.tabs[text_area]
                break
        self.get_current_tab()

    def get_current_tab(self):
        # Получение текущей активной вкладки
        current_tab = self.notebook.select()
        if not current_tab:  # Проверяем, есть ли активная вкладка
            return None
        for text_area, info in self.tabs.items():
            if str(self.notebook.tabs()[self.notebook.index(current_tab)]) == str(text_area.master):
                self.text_area = text_area
                return info
        return None

    def apply_theme(self):
        # Применение текущей темы ко всем вкладкам
        theme = self.themes[self.current_theme]
        for tab_info in self.tabs.values():
            text_area = tab_info["text"]
            text_area.config(bg=theme["bg"], fg=theme["fg"],
                             insertbackground=theme["insertbg"])
            text_area.tag_configure("keyword", foreground=theme["keyword"])
            text_area.tag_configure("string", foreground=theme["string"])
            text_area.tag_configure("comment", foreground=theme["comment"])
            # Настраиваем тег 'sel' для визуального выделения текста
            text_area.tag_configure(
                "sel", background=theme["select_bg"], foreground=theme["select_fg"])
            # Устанавливаем приоритет тега 'sel' выше других тегов
            text_area.tag_raise("sel")
        self.queue_highlight()

    def set_theme(self, theme_name):
        # Переключение темы
        self.current_theme = theme_name
        self.apply_theme()

    def setup_syntax_highlighting(self):
        # Настройка подсветки синтаксиса для текущей вкладки
        self.text_area.bind("<KeyRelease>", self.queue_highlight)
        self.text_area.bind("<Expose>", self.queue_highlight)
        self.text_area.bind("<Configure>", self.queue_highlight)
        self.queue_highlight()

    def queue_highlight(self, event=None):
        # Добавление задачи подсветки в очередь с задержкой
        if hasattr(self, "highlight_after_id"):
            self.root.after_cancel(self.highlight_after_id)
        self.highlight_after_id = self.root.after(
            200, lambda: self.highlight_queue.put(True))

    def process_highlight_queue(self):
        # Обработка очереди подсветки в фоновом потоке
        if not self.highlight_queue.empty():
            self.highlight_queue.get()
            threading.Thread(
                target=self.highlight_visible_syntax, daemon=True).start()
        self.root.after(100, self.process_highlight_queue)

    def highlight_visible_syntax(self):
        # Подсветка синтаксиса только для видимой части текста
        tab_info = self.get_current_tab()
        if not tab_info:
            return
        text_area = tab_info["text"]
        top_line = int(text_area.index("@0,0").split('.')[0])
        bottom_line = int(text_area.index("@0,%d" %
                          text_area.winfo_height()).split('.')[0])
        visible_text = text_area.get(
            f"{top_line}.0", f"{bottom_line}.0 + 1 lines")

        for tag in ["keyword", "string", "comment"]:
            text_area.tag_remove(
                tag, f"{top_line}.0", f"{bottom_line}.0 + 1 lines")

        for word in self.keywords:
            pattern = r"\b" + word + r"\b"
            for match in re.finditer(pattern, visible_text):
                start = f"{top_line}.0 + {match.start()} chars"
                end = f"{top_line}.0 + {match.end()} chars"
                text_area.tag_add("keyword", start, end)

        for match in re.finditer(r'"[^"]*"|\'[^\']*\'', visible_text):
            start = f"{top_line}.0 + {match.start()} chars"
            end = f"{top_line}.0 + {match.end()} chars"
            text_area.tag_add("string", start, end)

        for match in re.finditer(r"#.*$", visible_text, re.MULTILINE):
            start = f"{top_line}.0 + {match.start()} chars"
            end = f"{top_line}.0 + {match.end()} chars"
            text_area.tag_add("comment", start, end)

    def setup_font_resize(self):
        # Настройка изменения размера шрифта
        self.root.bind("<Control-MouseWheel>", self.resize_font)

    def resize_font(self, event):
        # Изменение размера шрифта
        if event.delta > 0:
            self.font_size += 1
        elif event.delta < 0 and self.font_size > 1:
            self.font_size -= 1
        for tab_info in self.tabs.values():
            tab_info["text"].config(font=("Courier", self.font_size))
        self.queue_highlight()

    def find_text(self):
        # Поиск текста в текущей вкладке
        tab_info = self.get_current_tab()
        if not tab_info:
            return
        text_area = tab_info["text"]
        search = simpledialog.askstring("Найти", "Введите текст для поиска:")
        if search:
            text_area.tag_remove("search", "1.0", tk.END)
            start_pos = "1.0"
            while True:
                pos = text_area.search(search, start_pos, stopindex=tk.END)
                if not pos:
                    break
                end_pos = f"{pos}+{len(search)}c"
                text_area.tag_add("search", pos, end_pos)
                start_pos = end_pos
            text_area.tag_config(
                "search", background="yellow", foreground="black")

    def new_file(self):
        # Создать новый файл (новая вкладка)
        self.add_tab()

    def detect_encoding(self, file_path):
        # Определение кодировки файла
        with open(file_path, "rb") as file:
            raw_data = file.read()
            result = chardet.detect(raw_data)
            encoding = result["encoding"]
            confidence = result["confidence"]
            if confidence < 0.5 or encoding is None:
                encoding = "utf-8"
            return encoding

    def open_file(self):
        # Открыть существующий файл в новой вкладке с определением кодировки
        file_path = filedialog.askopenfilename(
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")])
        if file_path:
            try:
                encoding = self.detect_encoding(file_path)
                try:
                    with open(file_path, "r", encoding=encoding) as file:
                        self.add_tab()
                        tab_info = self.get_current_tab()
                        tab_info["text"].delete("1.0", tk.END)
                        tab_info["text"].insert("1.0", file.read())
                        tab_info["file"] = file_path
                        self.notebook.tab(
                            self.notebook.select(), text=os.path.basename(file_path))
                        self.queue_highlight()
                except UnicodeDecodeError:
                    with open(file_path, "r", encoding="windows-1251") as file:
                        self.add_tab()
                        tab_info = self.get_current_tab()
                        tab_info["text"].delete("1.0", tk.END)
                        tab_info["text"].insert("1.0", file.read())
                        tab_info["file"] = file_path
                        self.notebook.tab(
                            self.notebook.select(), text=os.path.basename(file_path))
                        self.queue_highlight()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось открыть файл: {e}")

    def save_file(self):
        # Сохранить текущий файл
        tab_info = self.get_current_tab()
        if not tab_info:
            return
        if tab_info["file"]:
            try:
                with open(tab_info["file"], "w", encoding="utf-8") as file:
                    file.write(tab_info["text"].get("1.0", tk.END))
                self.notebook.tab(self.notebook.select(),
                                  text=os.path.basename(tab_info["file"]))
            except Exception as e:
                messagebox.showerror(
                    "Ошибка", f"Не удалось сохранить файл: {e}")
        else:
            self.save_as_file()

    def save_as_file(self):
        # Сохранить как новый файл
        tab_info = self.get_current_tab()
        if not tab_info:
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".txt",
                                                 filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")])
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(tab_info["text"].get("1.0", tk.END))
                tab_info["file"] = file_path
                self.notebook.tab(self.notebook.select(),
                                  text=os.path.basename(file_path))
            except Exception as e:
                messagebox.showerror(
                    "Ошибка", f"Не удалось сохранить файл: {e}")

    def exit_app(self):
        # Выход из приложения
        for tab_info in self.tabs.values():
            if tab_info["text"].get("1.0", tk.END).strip():
                self.text_area = tab_info["text"]
                if messagebox.askyesno("Сохранить?", "Хотите сохранить перед выходом?"):
                    self.save_file()
        self.config_manager.save_config({
            "theme": self.current_theme,
            "font_size": self.font_size,
            "geometry": self.root.geometry(),
            "opacity": self.opacity_scale.get()
        })
        self.root.quit()


if __name__ == "__main__":
    root = tk.Tk()
    app = Notepad(root)
    root.mainloop()
