import json
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .categories import existing_categories_path, generate_api_categories, generate_keyword_categories, get_categories_path
from .crawler import get_paper_source, get_paper_sources, get_papers_path, initialize_papers
from .downloader import download_pdf
from .state import load_state, record_download, reset_state, save_state, set_current_index
from .utils import PROJECT_ROOT, clean_filename, log_error, recent_logs, resolve_project_path


CONFIG_PATH = PROJECT_ROOT / "config.json"


TEXT = {
    "zh": {
        "app_title": "Conference Paper PDF Downloader",
        "download_root": "下载根目录",
        "choose": "选择",
        "language": "语言",
        "paper_source": "论文源",
        "initializing": "初始化中...",
        "init_loading": "正在读取缓存或请求论文源页面...",
        "open_detail": "打开详情页",
        "open_pdf": "打开 PDF 链接",
        "category": "分类",
        "new_category": "新建分类",
        "refresh_categories": "刷新分类文件夹",
        "previous": "上一篇",
        "skip": "跳过",
        "download_to_category": "下载到该分类",
        "auto_classify": "自动分类",
        "stop_auto_classify": "中止自动分类",
        "pause_save": "暂停并保存",
        "reinitialize": "重新初始化论文列表",
        "reset_progress": "重新初始化下载进度",
        "recent_logs": "最近日志",
        "init_failed": "初始化失败",
        "loaded_cache": "已从缓存加载 {count} 篇论文。",
        "init_done": "论文列表初始化完成，已缓存 {count} 篇论文。",
        "init_done_title": "初始化完成",
        "no_paper": "没有可显示的论文",
        "progress": "当前进度：{index} / {total}",
        "untitled": "(无标题)",
        "new_category_prompt": "请输入分类文件夹名称：",
        "invalid_name": "无效名称",
        "empty_category": "分类名称不能为空。",
        "file_exists": "文件已存在",
        "pdf_exists": "该 PDF 已存在，是否覆盖？",
        "downloading": "正在下载，请稍候...",
        "download_failed": "下载失败",
        "auto_no_papers": "论文列表尚未初始化。",
        "auto_cannot_start": "无法自动分类",
        "auto_failed": "自动分类失败",
        "auto_running": "自动分类下载中...",
        "auto_running_progress": "自动分类下载中：{index} / {total} -> {category}",
        "auto_stop_requested": "已请求中止自动分类；当前 PDF 下载完成后停止。",
        "category_file_missing": "未找到分类文件：{path}",
        "category_file_list": "分类 JSON 必须是论文对象列表。",
        "category_missing": "分类 JSON 中没有可用的 category 字段。",
        "category_strategy_title": "选择分类方式",
        "category_strategy_prompt": "未找到当前论文源的分类文件：\n{path}\n\n请选择分类方式。",
        "category_strategy_keyword": "根据关键词规则匹配分类",
        "category_strategy_api": "调用API进行分类",
        "category_strategy_manual": "自行分类",
        "category_strategy_cancel": "取消",
        "keyword_classifying": "正在根据关键词规则生成分类文件...",
        "keyword_done": "已生成分类文件：{path}\n共 {count} 篇论文。",
        "api_classifying": "正在提交 Batch API 分类任务...",
        "api_done": "API 分类完成，已生成分类文件：{path}",
        "manual_category_hint": "请将当前论文源缓存文件提交给 AI 生成分类 JSON，并保存为：\n{path}",
        "overwrite_auto": "{filename} 已存在。\n\n是：覆盖\n否：跳过该论文\n取消：中止自动分类",
        "auto_stopped_title": "自动分类已中止",
        "auto_stopped": "自动分类已中止。已下载 {downloaded} 篇，跳过 {skipped} 篇，失败 {failed} 篇。",
        "auto_done_title": "自动分类完成",
        "auto_done": "自动分类完成。已下载 {downloaded} 篇，跳过 {skipped} 篇，失败 {failed} 篇。",
        "saved_title": "已保存",
        "saved": "当前进度已保存。",
        "reset_progress_title": "重新初始化下载进度",
        "reset_progress_confirm": "确定要清空下载进度、跳过记录和分类记录吗？\n\n当前下载目录和语言设置会保留。",
        "reset_progress_done": "下载进度已重新初始化。",
        "language_switched": "语言已切换。",
        "source_switched": "论文源已切换。",
    },
    "en": {
        "app_title": "Conference Paper PDF Downloader",
        "download_root": "Download Root",
        "choose": "Choose",
        "language": "Language",
        "paper_source": "Paper Source",
        "initializing": "Initializing...",
        "init_loading": "Reading cache or requesting paper source pages...",
        "open_detail": "Open Detail Page",
        "open_pdf": "Open PDF Link",
        "category": "Category",
        "new_category": "New Category",
        "refresh_categories": "Refresh Categories",
        "previous": "Previous",
        "skip": "Skip",
        "download_to_category": "Download to Category",
        "auto_classify": "Auto Classify",
        "stop_auto_classify": "Stop Auto",
        "pause_save": "Pause and Save",
        "reinitialize": "Reinitialize Paper List",
        "reset_progress": "Reset Progress",
        "recent_logs": "Recent Logs",
        "init_failed": "Initialization Failed",
        "loaded_cache": "Loaded {count} papers from cache.",
        "init_done": "Paper list initialized and cached with {count} papers.",
        "init_done_title": "Initialization Complete",
        "no_paper": "No paper to display",
        "progress": "Progress: {index} / {total}",
        "untitled": "(Untitled)",
        "new_category_prompt": "Enter a category folder name:",
        "invalid_name": "Invalid Name",
        "empty_category": "Category name cannot be empty.",
        "file_exists": "File Exists",
        "pdf_exists": "This PDF already exists. Overwrite it?",
        "downloading": "Downloading, please wait...",
        "download_failed": "Download Failed",
        "auto_no_papers": "The paper list has not been initialized.",
        "auto_cannot_start": "Cannot Start Auto Classification",
        "auto_failed": "Auto Classification Failed",
        "auto_running": "Auto classification is downloading...",
        "auto_running_progress": "Auto downloading: {index} / {total} -> {category}",
        "auto_stop_requested": "Stop requested; the app will stop after the current PDF finishes.",
        "category_file_missing": "Category file not found: {path}",
        "category_file_list": "The category JSON must be a list of paper objects.",
        "category_missing": "No usable category field found in the category JSON.",
        "category_strategy_title": "Choose Classification Method",
        "category_strategy_prompt": "No category file was found for the current paper source:\n{path}\n\nChoose a classification method.",
        "category_strategy_keyword": "Keyword Rules",
        "category_strategy_api": "API Classification",
        "category_strategy_manual": "Manual Classification",
        "category_strategy_cancel": "Cancel",
        "keyword_classifying": "Generating categories with keyword rules...",
        "keyword_done": "Generated category file: {path}\nTotal papers: {count}.",
        "api_classifying": "Submitting Batch API classification job...",
        "api_done": "API classification complete. Generated category file: {path}",
        "manual_category_hint": "Upload the current paper cache to AI, generate a categorized JSON file, and save it as:\n{path}",
        "overwrite_auto": "{filename} already exists.\n\nYes: overwrite\nNo: skip this paper\nCancel: stop auto classification",
        "auto_stopped_title": "Auto Classification Stopped",
        "auto_stopped": "Auto classification stopped. Downloaded {downloaded}, skipped {skipped}, failed {failed}.",
        "auto_done_title": "Auto Classification Complete",
        "auto_done": "Auto classification complete. Downloaded {downloaded}, skipped {skipped}, failed {failed}.",
        "saved_title": "Saved",
        "saved": "Current progress has been saved.",
        "reset_progress_title": "Reset Download Progress",
        "reset_progress_confirm": "Clear download progress, skipped items, and classification records?\n\nThe current download root and language setting will be kept.",
        "reset_progress_done": "Download progress has been reset.",
        "language_switched": "Language switched.",
        "source_switched": "Paper source switched.",
    },
}


class CVPRDownloaderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.config_data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.state_data = load_state()
        self.lang = self.state_data.get("language", "zh")
        if self.lang not in TEXT:
            self.lang = "zh"
        self.paper_sources = get_paper_sources(self.config_data)
        self.source_names = {source["name"]: source["id"] for source in self.paper_sources}
        self.source_id_to_name = {source["id"]: source["name"] for source in self.paper_sources}
        self.source_id = self._initial_source_id()

        self.papers = []
        self.categories = []
        self.is_busy = False
        self.auto_stop_event = threading.Event()
        self.i18n_widgets = []

        self.title(self.t("app_title"))
        self.geometry("960x560")
        self.minsize(820, 500)

        self._build_ui()
        self.apply_language()
        self._ensure_download_root()
        self.refresh_categories()
        self.load_cached_papers()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def t(self, key: str, **kwargs) -> str:
        value = TEXT[self.lang].get(key, TEXT["zh"].get(key, key))
        return value.format(**kwargs) if kwargs else value

    def _initial_source_id(self) -> str:
        selected = self.state_data.get("paper_source") or self.config_data.get("default_paper_source")
        source = get_paper_source(self.config_data, selected)
        return source["id"]

    def _default_download_root_for_source(self, source_id: str = "") -> str:
        source_id = source_id or self.source_id
        source_name = self.source_id_to_name.get(source_id, source_id)
        return f"downloads/{source_name}"

    def _is_source_default_download_root(self, path_text: str) -> bool:
        def normalize(value: str) -> str:
            return str(Path(value or ""))

        normalized = normalize(path_text)
        defaults = {
            "",
            normalize("downloads"),
            normalize("downloads/default"),
        }
        defaults.update(normalize(str(Path("downloads") / source["name"])) for source in self.paper_sources)
        return normalized in defaults

    def _initial_download_root(self) -> str:
        stored = self.state_data.get("download_root") or ""
        if self._is_source_default_download_root(stored):
            return self._default_download_root_for_source()
        return stored

    def _label(self, parent, key: str, **kwargs):
        widget = ttk.Label(parent, **kwargs)
        self.i18n_widgets.append((widget, key))
        return widget

    def _button(self, parent, key: str, command, **kwargs):
        widget = ttk.Button(parent, command=command, **kwargs)
        self.i18n_widgets.append((widget, key))
        return widget

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(5, weight=1)

        top = ttk.Frame(self, padding=12)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        self._label(top, "download_root").grid(row=0, column=0, sticky="w")
        self.root_var = tk.StringVar(value=self._initial_download_root())
        ttk.Entry(top, textvariable=self.root_var).grid(row=0, column=1, sticky="ew", padx=8)
        self._button(top, "choose", self.choose_root).grid(row=0, column=2)
        self._label(top, "language").grid(row=0, column=3, sticky="w", padx=(16, 4))
        self.language_var = tk.StringVar(value=self.lang)
        self.language_box = ttk.Combobox(top, textvariable=self.language_var, state="readonly", width=10)
        self.language_box["values"] = ("zh", "en")
        self.language_box.grid(row=0, column=4, sticky="e")
        self.language_box.bind("<<ComboboxSelected>>", self.change_language)
        self._label(top, "paper_source").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.source_var = tk.StringVar(value=self.source_id_to_name.get(self.source_id, self.source_id))
        self.source_box = ttk.Combobox(top, textvariable=self.source_var, state="readonly", width=24)
        self.source_box["values"] = [source["name"] for source in self.paper_sources]
        self.source_box.grid(row=1, column=1, sticky="w", padx=8, pady=(8, 0))
        self.source_box.bind("<<ComboboxSelected>>", self.change_paper_source)

        paper_frame = ttk.Frame(self, padding=(12, 4, 12, 4))
        paper_frame.grid(row=1, column=0, sticky="ew")
        paper_frame.columnconfigure(0, weight=1)
        self.progress_var = tk.StringVar(value=self.t("initializing"))
        ttk.Label(paper_frame, textvariable=self.progress_var).grid(row=0, column=0, sticky="w")
        self.init_status_var = tk.StringVar(value="")
        ttk.Label(paper_frame, textvariable=self.init_status_var).grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.title_var = tk.StringVar(value="")
        ttk.Label(paper_frame, textvariable=self.title_var, wraplength=900, font=("", 12, "bold")).grid(row=2, column=0, sticky="ew", pady=(8, 0))

        link_frame = ttk.Frame(self, padding=(12, 4, 12, 4))
        link_frame.grid(row=2, column=0, sticky="ew")
        self._button(link_frame, "open_detail", self.open_detail).pack(side="left")
        self._button(link_frame, "open_pdf", self.open_pdf).pack(side="left", padx=8)

        category_frame = ttk.Frame(self, padding=(12, 10, 12, 4))
        category_frame.grid(row=3, column=0, sticky="ew")
        category_frame.columnconfigure(1, weight=1)
        self._label(category_frame, "category").grid(row=0, column=0, sticky="w")
        self.category_var = tk.StringVar()
        self.category_box = ttk.Combobox(category_frame, textvariable=self.category_var, state="readonly")
        self.category_box.grid(row=0, column=1, sticky="ew", padx=8)
        self._button(category_frame, "new_category", self.create_category).grid(row=0, column=2)
        self._button(category_frame, "refresh_categories", self.refresh_categories).grid(row=0, column=3, padx=(8, 0))

        actions = ttk.Frame(self, padding=(12, 8, 12, 8))
        actions.grid(row=4, column=0, sticky="ew")
        self._button(actions, "previous", self.previous_paper).pack(side="left")
        self._button(actions, "skip", self.skip_paper).pack(side="left", padx=8)
        self._button(actions, "download_to_category", self.download_current).pack(side="left")
        self._button(actions, "auto_classify", self.start_auto_classify).pack(side="left", padx=(8, 0))
        self._button(actions, "stop_auto_classify", self.stop_auto_classify).pack(side="left", padx=8)
        self._button(actions, "pause_save", self.pause_save).pack(side="left")
        self._button(actions, "reset_progress", self.reset_progress).pack(side="left", padx=8)
        self._button(actions, "reinitialize", lambda: self.load_papers_async(force=True)).pack(side="right")

        self.log_frame = ttk.LabelFrame(self, padding=8)
        self.log_frame.grid(row=5, column=0, sticky="nsew", padx=12, pady=(4, 12))
        self.log_frame.columnconfigure(0, weight=1)
        self.log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(self.log_frame, height=8, wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.update_logs()

    def apply_language(self) -> None:
        self.title(self.t("app_title"))
        for widget, key in self.i18n_widgets:
            widget.configure(text=self.t(key))
        self.log_frame.configure(text=self.t("recent_logs"))
        self.update_paper_display()

    def change_language(self, _event=None) -> None:
        selected = self.language_var.get()
        if selected not in TEXT:
            return
        self.lang = selected
        self.state_data["language"] = self.lang
        self.state_data["paper_source"] = self.source_id
        save_state(self.state_data)
        self.apply_language()
        self.init_status_var.set(self.t("language_switched"))

    def change_paper_source(self, _event=None) -> None:
        selected_name = self.source_var.get()
        selected_id = self.source_names.get(selected_name)
        if not selected_id or selected_id == self.source_id:
            return
        self.source_id = selected_id
        self.state_data["paper_source"] = self.source_id
        self.state_data["current_index"] = 0
        if self._is_source_default_download_root(self.root_var.get()):
            self.root_var.set(self._default_download_root_for_source())
        save_state(self.state_data)
        self.init_status_var.set(self.t("source_switched"))
        self._ensure_download_root()
        self.refresh_categories()
        self.papers = []
        self.load_cached_papers()

    def _ensure_download_root(self) -> Path:
        root = resolve_project_path(self.root_var.get())
        root.mkdir(parents=True, exist_ok=True)
        self.state_data["download_root"] = self.root_var.get()
        self.state_data["language"] = self.lang
        self.state_data["paper_source"] = self.source_id
        save_state(self.state_data)
        return root

    def current_paper(self):
        if not self.papers:
            return None
        index = int(self.state_data.get("current_index", 0))
        if index >= len(self.papers):
            return None
        return self.papers[index]

    def load_cached_papers(self) -> None:
        papers_path = get_papers_path(self.source_id)
        self.papers = []
        if papers_path.exists():
            try:
                data = json.loads(papers_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self.papers = data
                    set_current_index(self.state_data, int(self.state_data.get("current_index", 0)), len(self.papers))
                    save_state(self.state_data)
                    self.update_paper_display()
                    self.init_status_var.set(self.t("loaded_cache", count=len(self.papers)))
                    return
            except Exception as exc:
                message = str(exc)
                log_error(f"Could not load cached papers {papers_path}: {message}")
                self.update_logs()
        self.update_paper_display()
        self.init_status_var.set(self.t("auto_no_papers"))

    def load_papers_async(self, force: bool = False) -> None:
        if self.is_busy:
            return
        self.is_busy = True
        self.progress_var.set(self.t("initializing"))
        self.init_status_var.set(self.t("init_loading"))
        thread = threading.Thread(target=self._load_papers_worker, args=(force,), daemon=True)
        thread.start()

    def _load_papers_worker(self, force: bool) -> None:
        try:
            from_cache = self._has_cached_papers() and not force
            papers = initialize_papers(self.config_data, force=force, source_id=self.source_id)
            self.after(0, lambda: self._finish_load_papers(papers, from_cache))
        except Exception as exc:
            message = str(exc)
            log_error(message)
            self.after(0, lambda msg=message: messagebox.showerror(self.t("init_failed"), msg))
            self.after(0, self.update_logs)
        finally:
            self.after(0, lambda: setattr(self, "is_busy", False))

    def _has_cached_papers(self) -> bool:
        papers_path = get_papers_path(self.source_id)
        if not papers_path.exists():
            return False
        try:
            data = json.loads(papers_path.read_text(encoding="utf-8"))
            return bool(data)
        except Exception:
            return False

    def _finish_load_papers(self, papers, from_cache: bool) -> None:
        self.papers = papers
        set_current_index(self.state_data, int(self.state_data.get("current_index", 0)), len(self.papers))
        save_state(self.state_data)
        self.update_paper_display()
        if from_cache:
            self.init_status_var.set(self.t("loaded_cache", count=len(self.papers)))
        else:
            message = self.t("init_done", count=len(self.papers))
            self.init_status_var.set(message)
            messagebox.showinfo(self.t("init_done_title"), message)
        self.update_logs()

    def update_paper_display(self) -> None:
        if not hasattr(self, "progress_var"):
            return
        paper = self.current_paper()
        if not paper:
            self.progress_var.set(self.t("no_paper"))
            if hasattr(self, "title_var"):
                self.title_var.set("")
            return
        index = int(self.state_data.get("current_index", 0))
        self.progress_var.set(self.t("progress", index=index + 1, total=len(self.papers)))
        self.title_var.set(paper.get("title", self.t("untitled")))

    def choose_root(self) -> None:
        selected = filedialog.askdirectory(initialdir=str(self._ensure_download_root()))
        if selected:
            self.root_var.set(selected)
            self._ensure_download_root()
            self.refresh_categories()

    def refresh_categories(self) -> None:
        root = self._ensure_download_root()
        self.categories = sorted([p.name for p in root.iterdir() if p.is_dir()])
        if not self.categories:
            (root / "default").mkdir(exist_ok=True)
            self.categories = ["default"]
        self.category_box["values"] = self.categories
        if self.category_var.get() not in self.categories:
            self.category_var.set(self.categories[0])

    def create_category(self) -> None:
        name = simpledialog.askstring(self.t("new_category"), self.t("new_category_prompt"), parent=self)
        if not name:
            return
        safe_name = self.safe_category_name(name)
        if not safe_name:
            messagebox.showwarning(self.t("invalid_name"), self.t("empty_category"))
            return
        (self._ensure_download_root() / safe_name).mkdir(parents=True, exist_ok=True)
        self.refresh_categories()
        self.category_var.set(safe_name)

    def safe_category_name(self, name: str) -> str:
        return "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in name).strip()

    def open_detail(self) -> None:
        paper = self.current_paper()
        if paper:
            webbrowser.open(paper["detail_url"])

    def open_pdf(self) -> None:
        paper = self.current_paper()
        if paper:
            webbrowser.open(paper["pdf_url"])

    def previous_paper(self) -> None:
        if not self.papers:
            return
        set_current_index(self.state_data, int(self.state_data.get("current_index", 0)) - 1, len(self.papers))
        save_state(self.state_data)
        self.update_paper_display()

    def skip_paper(self) -> None:
        paper = self.current_paper()
        if paper:
            self.state_data.setdefault("skipped", []).append(paper.get("detail_url", paper.get("title", "")))
        self.next_paper()

    def next_paper(self) -> None:
        if not self.papers:
            return
        set_current_index(self.state_data, int(self.state_data.get("current_index", 0)) + 1, len(self.papers))
        save_state(self.state_data)
        self.update_paper_display()

    def download_current(self) -> None:
        if self.is_busy:
            return
        paper = self.current_paper()
        category = self.category_var.get()
        if not paper or not category:
            return
        target_dir = self._ensure_download_root() / category
        filename = target_dir / (clean_filename(paper.get("title", "paper")) + ".pdf")
        overwrite = False
        if filename.exists():
            overwrite = messagebox.askyesno(self.t("file_exists"), self.t("pdf_exists"))
            if not overwrite:
                return
        self.is_busy = True
        self.progress_var.set(self.t("downloading"))
        thread = threading.Thread(target=self._download_worker, args=(paper, category, target_dir, overwrite), daemon=True)
        thread.start()

    def _download_worker(self, paper, category: str, target_dir: Path, overwrite: bool) -> None:
        try:
            file_path = download_pdf(paper, target_dir, self.config_data, overwrite=overwrite)
            record_download(self.state_data, paper, category, file_path)
            self.after(0, self.next_paper)
        except FileExistsError as exc:
            message = str(exc)
            self.after(0, lambda msg=message: messagebox.showwarning(self.t("file_exists"), msg))
        except Exception as exc:
            message = str(exc)
            log_error(message)
            self.after(0, lambda msg=message: messagebox.showerror(self.t("download_failed"), msg))
        finally:
            save_state(self.state_data)
            self.after(0, self.update_logs)
            self.after(0, lambda: setattr(self, "is_busy", False))

    def start_auto_classify(self) -> None:
        if self.is_busy:
            return
        if not self.papers:
            messagebox.showwarning(self.t("auto_cannot_start"), self.t("auto_no_papers"))
            return
        try:
            if not existing_categories_path(self.source_id).exists():
                if not self.prepare_categories_for_auto_classify():
                    return
            category_map = self.load_category_map()
        except Exception as exc:
            log_error(str(exc))
            self.update_logs()
            messagebox.showerror(self.t("auto_failed"), str(exc))
            return

        download_root = self._ensure_download_root()
        self.auto_stop_event.clear()
        self.is_busy = True
        self.init_status_var.set(self.t("auto_running"))
        thread = threading.Thread(target=self._auto_classify_worker, args=(category_map, download_root), daemon=True)
        thread.start()

    def stop_auto_classify(self) -> None:
        self.auto_stop_event.set()
        self.init_status_var.set(self.t("auto_stop_requested"))

    def ask_category_strategy(self, missing_path: Path) -> str:
        dialog = tk.Toplevel(self)
        dialog.title(self.t("category_strategy_title"))
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        result = {"value": ""}

        frame = ttk.Frame(dialog, padding=16)
        frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(
            frame,
            text=self.t("category_strategy_prompt", path=missing_path),
            wraplength=520,
            justify="left",
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 12))

        def choose(value: str) -> None:
            result["value"] = value
            dialog.destroy()

        ttk.Button(frame, text=self.t("category_strategy_keyword"), command=lambda: choose("keyword")).grid(row=1, column=0, padx=(0, 8))
        ttk.Button(frame, text=self.t("category_strategy_api"), command=lambda: choose("api")).grid(row=1, column=1, padx=8)
        ttk.Button(frame, text=self.t("category_strategy_manual"), command=lambda: choose("manual")).grid(row=1, column=2, padx=8)
        ttk.Button(frame, text=self.t("category_strategy_cancel"), command=lambda: choose("")).grid(row=1, column=3, padx=(8, 0))

        dialog.protocol("WM_DELETE_WINDOW", lambda: choose(""))
        dialog.update_idletasks()
        x = self.winfo_rootx() + max(0, (self.winfo_width() - dialog.winfo_width()) // 2)
        y = self.winfo_rooty() + max(0, (self.winfo_height() - dialog.winfo_height()) // 2)
        dialog.geometry(f"+{x}+{y}")
        self.wait_window(dialog)
        return result["value"]

    def prepare_categories_for_auto_classify(self) -> bool:
        target_path = get_categories_path(self.source_id)
        strategy = self.ask_category_strategy(target_path)
        if strategy == "keyword":
            self.init_status_var.set(self.t("keyword_classifying"))
            self.update_idletasks()
            path, _counts = generate_keyword_categories(self.source_id, self.papers)
            self.init_status_var.set(self.t("keyword_done", path=path, count=len(self.papers)))
            messagebox.showinfo(self.t("init_done_title"), self.t("keyword_done", path=path, count=len(self.papers)))
            return True
        if strategy == "api":
            self.start_api_classification()
            return False
        if strategy == "manual":
            messagebox.showinfo(self.t("category_strategy_title"), self.t("manual_category_hint", path=target_path))
            return False
        return False

    def start_api_classification(self) -> None:
        self.is_busy = True
        self.init_status_var.set(self.t("api_classifying"))
        papers = list(self.papers)
        thread = threading.Thread(target=self._api_classification_worker, args=(papers,), daemon=True)
        thread.start()

    def _api_classification_worker(self, papers: list) -> None:
        try:
            def report(message: str) -> None:
                self.after(0, lambda msg=message: self.init_status_var.set(msg))

            path = generate_api_categories(self.source_id, papers, self.config_data, status_callback=report)
            self.after(0, lambda p=path: self._finish_api_classification(p))
        except Exception as exc:
            message = str(exc)
            log_error(message)
            self.after(0, lambda msg=message: messagebox.showerror(self.t("auto_failed"), msg))
            self.after(0, self.update_logs)
            self.after(0, lambda: setattr(self, "is_busy", False))

    def _finish_api_classification(self, path: Path) -> None:
        self.is_busy = False
        self.init_status_var.set(self.t("api_done", path=path))
        messagebox.showinfo(self.t("category_strategy_title"), self.t("api_done", path=path))
        self.start_auto_classify()

    def load_category_map(self) -> dict:
        categories_path = existing_categories_path(self.source_id)
        if not categories_path.exists():
            raise FileNotFoundError(self.t("category_file_missing", path=categories_path))
        data = json.loads(categories_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(self.t("category_file_list"))

        category_map = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            category = item.get("category")
            if not category:
                continue
            if item.get("detail_url"):
                category_map[("detail_url", item["detail_url"])] = category
            if item.get("title"):
                category_map[("title", item["title"])] = category
        if not category_map:
            raise ValueError(self.t("category_missing"))
        return category_map

    def _category_for_paper(self, paper: dict, category_map: dict) -> str:
        return (
            category_map.get(("detail_url", paper.get("detail_url")))
            or category_map.get(("title", paper.get("title")))
            or ""
        )

    def _advance_after_auto_step(self) -> None:
        self.next_paper()
        self.update_logs()

    def _ask_overwrite_sync(self, file_path: Path):
        event = threading.Event()
        result = {"value": None}

        def ask():
            result["value"] = messagebox.askyesnocancel(
                self.t("file_exists"),
                self.t("overwrite_auto", filename=file_path.name),
            )
            event.set()

        self.after(0, ask)
        event.wait()
        return result["value"]

    def _auto_classify_worker(self, category_map: dict, download_root: Path) -> None:
        downloaded = 0
        skipped = 0
        failed = 0
        stopped = False

        try:
            while not self.auto_stop_event.is_set():
                index = int(self.state_data.get("current_index", 0))
                if index >= len(self.papers):
                    break

                paper = self.papers[index]
                category = self._category_for_paper(paper, category_map)
                if not category:
                    skipped += 1
                    log_error(f"Auto classify skipped, no category: {paper.get('title', '')}")
                    self.after(0, self._advance_after_auto_step)
                    wait_event = threading.Event()
                    self.after(0, wait_event.set)
                    wait_event.wait()
                    continue

                safe_category = self.safe_category_name(category)
                if not safe_category:
                    skipped += 1
                    log_error(f"Auto classify skipped, invalid category: {category}")
                    self.after(0, self._advance_after_auto_step)
                    wait_event = threading.Event()
                    self.after(0, wait_event.set)
                    wait_event.wait()
                    continue

                target_dir = download_root / safe_category
                target_dir.mkdir(parents=True, exist_ok=True)
                final_path = target_dir / (clean_filename(paper.get("title", "paper")) + ".pdf")
                overwrite = False
                if final_path.exists():
                    answer = self._ask_overwrite_sync(final_path)
                    if answer is None:
                        stopped = True
                        self.auto_stop_event.set()
                        break
                    if answer is False:
                        skipped += 1
                        self.after(0, self._advance_after_auto_step)
                        wait_event = threading.Event()
                        self.after(0, wait_event.set)
                        wait_event.wait()
                        continue
                    overwrite = True

                self.after(0, lambda i=index, total=len(self.papers), c=safe_category: self.init_status_var.set(
                    self.t("auto_running_progress", index=i + 1, total=total, category=c)
                ))

                try:
                    file_path = download_pdf(paper, target_dir, self.config_data, overwrite=overwrite)
                    record_download(self.state_data, paper, safe_category, file_path)
                    downloaded += 1
                    self.after(0, self._advance_after_auto_step)
                    wait_event = threading.Event()
                    self.after(0, wait_event.set)
                    wait_event.wait()
                except Exception as exc:
                    failed += 1
                    log_error(f"Auto classify download failed: {paper.get('title', '')}: {exc}")
                    self.after(0, self.update_logs)
                    self.auto_stop_event.set()
                    stopped = True
                    break

            if self.auto_stop_event.is_set():
                stopped = True
        finally:
            save_state(self.state_data)
            self.after(0, self.update_logs)
            self.after(0, lambda: setattr(self, "is_busy", False))
            self.after(0, lambda: self._finish_auto_classify(downloaded, skipped, failed, stopped))

    def _finish_auto_classify(self, downloaded: int, skipped: int, failed: int, stopped: bool) -> None:
        if stopped:
            message = self.t("auto_stopped", downloaded=downloaded, skipped=skipped, failed=failed)
            self.init_status_var.set(message)
            messagebox.showinfo(self.t("auto_stopped_title"), message)
        else:
            message = self.t("auto_done", downloaded=downloaded, skipped=skipped, failed=failed)
            self.init_status_var.set(message)
            messagebox.showinfo(self.t("auto_done_title"), message)

    def pause_save(self) -> None:
        self.state_data["download_root"] = self.root_var.get()
        self.state_data["language"] = self.lang
        self.state_data["paper_source"] = self.source_id
        save_state(self.state_data)
        self.update_logs()
        messagebox.showinfo(self.t("saved_title"), self.t("saved"))

    def reset_progress(self) -> None:
        if self.is_busy:
            return
        confirmed = messagebox.askyesno(self.t("reset_progress_title"), self.t("reset_progress_confirm"))
        if not confirmed:
            return
        self.state_data = reset_state(self.root_var.get(), self.lang)
        self.state_data["paper_source"] = self.source_id
        save_state(self.state_data)
        self.update_paper_display()
        self.update_logs()
        messagebox.showinfo(self.t("reset_progress_title"), self.t("reset_progress_done"))

    def update_logs(self) -> None:
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert("1.0", recent_logs())

    def on_close(self) -> None:
        self.state_data["download_root"] = self.root_var.get()
        self.state_data["language"] = self.lang
        self.state_data["paper_source"] = self.source_id
        save_state(self.state_data)
        self.destroy()


def main() -> None:
    app = CVPRDownloaderApp()
    app.mainloop()
