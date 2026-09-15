import os
import json
import threading
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser

from PIL import Image, ImageTk, ImageEnhance, ImageOps, ImageDraw, ImageFont

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    BaseTk = TkinterDnD.Tk
    DND_AVAILABLE = True
except Exception:
    BaseTk = tk.Tk
    DND_AVAILABLE = False


APP_TITLE = "Batch Watermark Tool Pro v4"
APP_DIR = Path.home() / ".batch_watermark_tool_v4"
SETTINGS_FILE = APP_DIR / "settings.json"
PRESETS_FILE = APP_DIR / "presets.json"
BRANDS_FILE = APP_DIR / "brands.json"
PROFILES_FILE = APP_DIR / "profiles.json"

SUPPORTED = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
RATIOS = {
    "原始比例": None,
    "1:1": (1, 1),
    "4:5": (4, 5),
    "3:4": (3, 4),
    "16:9": (16, 9),
    "9:16": (9, 16),
    "2:3": (2, 3),
    "3:2": (3, 2),
}
POSITIONS = ["左上", "上中", "右上", "左中", "置中", "右中", "左下", "下中", "右下"]


class App(BaseTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1540x920")
        self.minsize(1220, 760)

        self.paths = []
        self.watermark_path = None
        self.preview_photo = None
        self.preview_box = None
        self.preview_processed = tk.BooleanVar(value=True)
        self.preview_zoom = tk.DoubleVar(value=1.0)
        self.cancelled = False

        self.output_dir = tk.StringVar(value=str(Path.home() / "Desktop"))

        self.wm_enabled = tk.BooleanVar(value=True)
        self.wm_mode = tk.StringVar(value="九宮格")
        self.wm_position = tk.StringVar(value="右下")
        self.wm_scale = tk.DoubleVar(value=18)
        self.wm_opacity = tk.DoubleVar(value=70)
        self.wm_rotation = tk.DoubleVar(value=0)
        self.margin = tk.IntVar(value=24)
        self.free_x = tk.DoubleVar(value=.85)
        self.free_y = tk.DoubleVar(value=.85)
        self.tile_gap = tk.IntVar(value=80)

        self.text_enabled = tk.BooleanVar(value=False)
        self.text_value = tk.StringVar(value="© Brand")
        self.text_size = tk.IntVar(value=48)
        self.text_opacity = tk.DoubleVar(value=70)
        self.text_color = "#ffffff"
        self.text_position = tk.StringVar(value="左下")

        self.output_ratio = tk.StringVar(value="原始比例")
        self.crop_x = tk.DoubleVar(value=.5)
        self.crop_y = tk.DoubleVar(value=.5)

        self.size_mode = tk.StringVar(value="百分比")
        self.resize_percent = tk.DoubleVar(value=100)
        self.long_edge = tk.IntVar(value=2048)
        self.allow_upscale = tk.BooleanVar(value=False)
        self.output_format = tk.StringVar(value="JPG")
        self.quality = tk.IntVar(value=92)
        self.preserve_exif = tk.BooleanVar(value=True)

        self.rename_enabled = tk.BooleanVar(value=False)
        self.rename_template = tk.StringVar(value="{name}_{index}")
        self.rename_start = tk.IntVar(value=1)
        self.rename_digits = tk.IntVar(value=3)
        self.conflict_mode = tk.StringVar(value="自動加序號")

        self.status = tk.StringVar(value="就緒")
        self.file_info = tk.StringVar(value="尚未選擇圖片")
        self.selection_info = tk.StringVar(value="0 張圖片")
        self.export_summary = tk.StringVar(value="輸出：原始比例 · 100% · JPG")

        self.presets = {}
        self.brands = {}
        self.profiles = {}
        self.profile_vars = {}

        self._style()
        self._ui()
        self._bind_shortcuts()
        self._load_all()
        self._refresh_summary()

    def _style(self):
        self.configure(bg="#111315")
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except Exception:
            pass

        bg = "#171a1d"
        panel = "#1d2125"
        panel2 = "#24292e"
        fg = "#f3f5f7"
        muted = "#aab2bb"
        accent = "#5aa7ff"

        s.configure(".", font=("Segoe UI", 10))
        s.configure("TFrame", background=bg)
        s.configure("Card.TFrame", background=panel)
        s.configure("Top.TFrame", background="#14171a")
        s.configure("Bottom.TFrame", background="#14171a")

        s.configure("TLabel", background=bg, foreground=fg)
        s.configure("Muted.TLabel", background=bg, foreground=muted)
        s.configure("Title.TLabel", background="#14171a", foreground=fg, font=("Segoe UI Semibold", 15))
        s.configure("Section.TLabel", background=panel, foreground=fg, font=("Segoe UI Semibold", 10))
        s.configure("Status.TLabel", background="#14171a", foreground=muted)

        s.configure("TLabelframe", background=panel, foreground=fg, bordercolor="#30363d")
        s.configure("TLabelframe.Label", background=panel, foreground=fg, font=("Segoe UI Semibold", 10))

        s.configure("TCheckbutton", background=bg, foreground=fg)
        s.configure("TRadiobutton", background=bg, foreground=fg)

        s.configure("TButton", padding=(10, 6))
        s.configure("Primary.TButton", padding=(14, 8), font=("Segoe UI Semibold", 10))
        s.map("Primary.TButton", background=[("active", "#3186e6"), ("!disabled", accent)], foreground=[("!disabled", "#07121f")])

        s.configure("TNotebook", background=bg, borderwidth=0)
        s.configure("TNotebook.Tab", padding=(12, 8))
        s.map("TNotebook.Tab", background=[("selected", panel2), ("!selected", bg)], foreground=[("selected", fg), ("!selected", muted)])

        s.configure("Treeview", background="#121518", fieldbackground="#121518", foreground=fg, rowheight=30, borderwidth=0)
        s.configure("Treeview.Heading", background=panel2, foreground=fg, font=("Segoe UI Semibold", 9))
        s.map("Treeview", background=[("selected", "#274d70")])

        s.configure("Horizontal.TProgressbar", troughcolor="#24292e", background=accent)
        s.configure("TEntry", fieldbackground="#111417", foreground=fg)
        s.configure("TCombobox", fieldbackground="#111417", foreground=fg)
        s.map("TCombobox", fieldbackground=[("readonly", "#111417")], foreground=[("readonly", fg)], selectbackground=[("readonly", "#274d70")], selectforeground=[("readonly", fg)])

    def _ui(self):
        top = ttk.Frame(self, style="Top.TFrame", padding=(14, 10))
        top.pack(fill="x")

        ttk.Label(top, text="Batch Watermark Tool Pro", style="Title.TLabel").pack(side="left")
        ttk.Label(top, text="v4", style="Status.TLabel").pack(side="left", padx=(8, 18))
        ttk.Button(top, text="＋ 加入圖片", command=self.add_images).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="＋ 加入資料夾", command=self.add_folder).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="選擇浮水印", command=self.choose_wm).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="IG 4:5", command=lambda: self.quick_ratio("4:5", 1350)).pack(side="right", padx=3)
        ttk.Button(top, text="限動 9:16", command=lambda: self.quick_ratio("9:16", 1920)).pack(side="right", padx=3)
        ttk.Button(top, text="正方形 1:1", command=lambda: self.quick_ratio("1:1", 1080)).pack(side="right", padx=3)

        body = ttk.Frame(self, padding=(10, 8))
        body.pack(fill="both", expand=True)
        paned = ttk.Panedwindow(body, orient="horizontal")
        paned.pack(fill="both", expand=True)
        left = ttk.Frame(paned, padding=8)
        center = ttk.Frame(paned, padding=8)
        right = ttk.Frame(paned, padding=8)
        paned.add(left, weight=0)
        paned.add(center, weight=1)
        paned.add(right, weight=0)

        head = ttk.Frame(left)
        head.pack(fill="x", pady=(0, 8))
        ttk.Label(head, text="圖片清單", font=("Segoe UI Semibold", 11)).pack(side="left")
        ttk.Label(head, textvariable=self.selection_info, style="Muted.TLabel").pack(side="right")

        drop = tk.Label(left, text="拖曳圖片或資料夾到這裡" if DND_AVAILABLE else "可使用上方按鈕匯入", bg="#20252a", fg="#b8c0c8", height=3, bd=1, relief="solid", font=("Segoe UI", 9))
        drop.pack(fill="x", pady=(0, 8))
        if DND_AVAILABLE:
            drop.drop_target_register(DND_FILES)
            drop.dnd_bind("<<Drop>>", self.on_drop)

        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_frame, columns=("size",), show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="檔案")
        self.tree.heading("size", text="尺寸")
        self.tree.column("#0", width=220, minwidth=160)
        self.tree.column("size", width=90, anchor="center")
        ysb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_tree_select())

        lr = ttk.Frame(left)
        lr.pack(fill="x", pady=(8, 0))
        ttk.Button(lr, text="移除選取", command=self.remove_selected).pack(side="left", fill="x", expand=True, padx=(0, 3))
        ttk.Button(lr, text="清空", command=self.clear).pack(side="left", fill="x", expand=True, padx=(3, 0))
        ttk.Separator(left).pack(fill="x", pady=10)
        ttk.Label(left, textvariable=self.file_info, style="Muted.TLabel", wraplength=310, justify="left").pack(fill="x")

        preview_toolbar = ttk.Frame(center)
        preview_toolbar.pack(fill="x", pady=(0, 8))
        ttk.Label(preview_toolbar, text="預覽", font=("Segoe UI Semibold", 11)).pack(side="left")
        ttk.Checkbutton(preview_toolbar, text="顯示處理效果", variable=self.preview_processed, command=self.preview).pack(side="right", padx=(12, 0))
        ttk.Button(preview_toolbar, text="符合視窗", command=self.fit_preview).pack(side="right", padx=3)
        ttk.Button(preview_toolbar, text="100%", command=lambda: self.set_zoom(1.0)).pack(side="right", padx=3)
        ttk.Button(preview_toolbar, text="＋", width=3, command=lambda: self.change_zoom(.15)).pack(side="right", padx=3)
        ttk.Button(preview_toolbar, text="－", width=3, command=lambda: self.change_zoom(-.15)).pack(side="right", padx=3)

        preview_wrap = ttk.Frame(center)
        preview_wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(preview_wrap, bg="#0b0d0f", highlightthickness=1, highlightbackground="#2a3036")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.preview())
        self.canvas.bind("<Button-1>", self.drag)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<MouseWheel>", self._mouse_zoom)

        hint = ttk.Frame(center)
        hint.pack(fill="x", pady=(8, 0))
        ttk.Label(hint, text="自由位置：拖曳浮水印位置　｜　比例裁切：拖曳裁切重心", style="Muted.TLabel").pack(side="left")
        self.zoom_label = ttk.Label(hint, text="100%", style="Muted.TLabel")
        self.zoom_label.pack(side="right")

        quick = ttk.LabelFrame(right, text="品牌與設定", padding=10)
        quick.pack(fill="x", pady=(0, 8))
        self.brand_name = tk.StringVar()
        self.brand_combo = ttk.Combobox(quick, textvariable=self.brand_name, state="readonly")
        self.brand_combo.pack(fill="x")
        q1 = ttk.Frame(quick)
        q1.pack(fill="x", pady=(5, 8))
        ttk.Button(q1, text="套用品牌", command=self.apply_brand).pack(side="left", fill="x", expand=True, padx=(0, 3))
        ttk.Button(q1, text="儲存品牌", command=self.save_brand).pack(side="left", fill="x", expand=True, padx=(3, 0))
        self.preset_name = tk.StringVar()
        self.preset_combo = ttk.Combobox(quick, textvariable=self.preset_name, state="readonly")
        self.preset_combo.pack(fill="x")
        q2 = ttk.Frame(quick)
        q2.pack(fill="x", pady=(5, 0))
        ttk.Button(q2, text="套用", command=self.apply_preset).pack(side="left", fill="x", expand=True, padx=(0, 3))
        ttk.Button(q2, text="儲存", command=self.save_preset).pack(side="left", fill="x", expand=True, padx=3)
        ttk.Button(q2, text="刪除", command=self.delete_preset).pack(side="left", fill="x", expand=True, padx=(3, 0))

        nb = ttk.Notebook(right)
        nb.pack(fill="both", expand=True)
        def scroll_tab(title):
            shell = ttk.Frame(nb)
            nb.add(shell, text=title)
            canvas = tk.Canvas(shell, highlightthickness=0, bg="#171a1d", width=340)
            scrollbar = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side="right", fill="y")
            canvas.pack(fill="both", expand=True)
            content = ttk.Frame(canvas, padding=12)
            item = canvas.create_window(0, 0, anchor="nw", window=content)
            content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=e.width))
            return content

        logo = scroll_tab("浮水印")
        crop = scroll_tab("裁切")
        text = scroll_tab("文字")
        out = scroll_tab("輸出")
        multi = scroll_tab("多尺寸")

        ttk.Checkbutton(logo, text="啟用 Logo 浮水印", variable=self.wm_enabled, command=self.preview).pack(anchor="w")
        self.wm_path_label = ttk.Label(logo, text="尚未選擇浮水印", style="Muted.TLabel", wraplength=330)
        self.wm_path_label.pack(fill="x", pady=(4, 10))
        ttk.Label(logo, text="模式").pack(anchor="w")
        c = ttk.Combobox(logo, values=["九宮格", "自由位置", "平鋪"], state="readonly", textvariable=self.wm_mode)
        c.pack(fill="x", pady=(2, 8))
        c.bind("<<ComboboxSelected>>", lambda e: self.preview())
        self.slider(logo, "大小", self.wm_scale, 1, 100, suffix="%")
        self.slider(logo, "透明度", self.wm_opacity, 0, 100, suffix="%")
        self.slider(logo, "旋轉", self.wm_rotation, -180, 180, suffix="°")
        ttk.Label(logo, text="位置").pack(anchor="w", pady=(8, 2))
        pc = ttk.Combobox(logo, values=POSITIONS, state="readonly", textvariable=self.wm_position)
        pc.pack(fill="x")
        pc.bind("<<ComboboxSelected>>", lambda e: self.preview())
        self.spin_row(logo, "邊距", self.margin, 0, 1000, "px")
        self.spin_row(logo, "平鋪間距", self.tile_gap, 0, 1000, "px")

        ttk.Label(crop, text="常用比例").pack(anchor="w")
        ratio_grid = ttk.Frame(crop)
        ratio_grid.pack(fill="x", pady=(6, 10))
        for i, name in enumerate(["原始比例", "1:1", "4:5", "3:4", "16:9", "9:16"]):
            ttk.Button(ratio_grid, text=name, command=lambda n=name: self.set_ratio(n)).grid(row=i // 3, column=i % 3, sticky="ew", padx=2, pady=2)
        for col in range(3):
            ratio_grid.columnconfigure(col, weight=1)
        ttk.Label(crop, text="精確比例").pack(anchor="w")
        rc = ttk.Combobox(crop, values=list(RATIOS.keys()), state="readonly", textvariable=self.output_ratio)
        rc.pack(fill="x", pady=(2, 10))
        rc.bind("<<ComboboxSelected>>", lambda e: (self.preview(), self._refresh_summary()))
        ttk.Label(crop, text="選擇比例後，可在預覽圖片內拖曳以改變裁切重心。", style="Muted.TLabel", wraplength=330).pack(fill="x")
        ttk.Button(crop, text="裁切重心置中", command=self.reset_crop).pack(fill="x", pady=(10, 0))

        ttk.Checkbutton(text, text="啟用文字浮水印", variable=self.text_enabled, command=self.preview).pack(anchor="w")
        ttk.Label(text, text="文字內容").pack(anchor="w", pady=(10, 2))
        e = ttk.Entry(text, textvariable=self.text_value)
        e.pack(fill="x")
        self.text_value.trace_add("write", lambda *a: self.preview())
        self.spin_row(text, "字體大小", self.text_size, 10, 500, "px")
        self.slider(text, "透明度", self.text_opacity, 0, 100, suffix="%")
        ttk.Button(text, text="選擇文字顏色", command=self.choose_text_color).pack(fill="x", pady=(8, 0))
        ttk.Label(text, text="位置").pack(anchor="w", pady=(10, 2))
        tp = ttk.Combobox(text, values=POSITIONS, state="readonly", textvariable=self.text_position)
        tp.pack(fill="x")
        tp.bind("<<ComboboxSelected>>", lambda e: self.preview())

        ttk.Label(out, text="尺寸模式").pack(anchor="w")
        sm = ttk.Combobox(out, values=["百分比", "指定長邊"], state="readonly", textvariable=self.size_mode)
        sm.pack(fill="x", pady=(2, 8))
        sm.bind("<<ComboboxSelected>>", lambda e: (self.preview(), self._refresh_summary()))
        self.slider(out, "圖片尺寸", self.resize_percent, 10, 200, suffix="%")
        self.spin_row(out, "指定長邊", self.long_edge, 320, 20000, "px", step=100)
        ttk.Checkbutton(out, text="允許放大原圖", variable=self.allow_upscale, command=self.preview).pack(anchor="w", pady=(8, 10))
        ttk.Label(out, text="圖片格式").pack(anchor="w")
        fmt = ttk.Combobox(out, values=["JPG", "JPEG", "PNG"], state="readonly", textvariable=self.output_format)
        fmt.pack(fill="x", pady=(2, 8))
        fmt.bind("<<ComboboxSelected>>", lambda e: self._refresh_summary())
        self.spin_row(out, "JPG 品質", self.quality, 40, 100, "%")
        ttk.Checkbutton(out, text="保留 EXIF", variable=self.preserve_exif).pack(anchor="w", pady=(8, 8))
        ttk.Label(out, text="檔案重複").pack(anchor="w")
        ttk.Combobox(out, values=["自動加序號", "覆蓋", "略過"], state="readonly", textvariable=self.conflict_mode).pack(fill="x", pady=(2, 8))
        ttk.Checkbutton(out, text="啟用重新命名", variable=self.rename_enabled).pack(anchor="w")
        ttk.Entry(out, textvariable=self.rename_template).pack(fill="x", pady=(4, 2))
        ttk.Label(out, text="變數：{name} {index} {date} {width} {height}", style="Muted.TLabel", wraplength=330).pack(fill="x")

        ttk.Label(multi, text="一次輸出多種規格", font=("Segoe UI Semibold", 10)).pack(anchor="w")
        ttk.Label(multi, text="啟用後，每個規格會自動建立子資料夾。", style="Muted.TLabel").pack(anchor="w", pady=(2, 8))
        self.multi_frame = ttk.Frame(multi)
        self.multi_frame.pack(fill="both", expand=True)
        mb = ttk.Frame(multi)
        mb.pack(fill="x", pady=(8, 0))
        ttk.Button(mb, text="新增規格", command=self.add_profile).pack(side="left", fill="x", expand=True, padx=(0, 3))
        ttk.Button(mb, text="刪除勾選", command=self.delete_profiles).pack(side="left", fill="x", expand=True, padx=(3, 0))

        bottom = ttk.Frame(self, style="Bottom.TFrame", padding=(14, 10))
        bottom.pack(fill="x")
        ttk.Label(bottom, textvariable=self.export_summary, style="Status.TLabel").pack(side="left")
        ttk.Label(bottom, textvariable=self.status, style="Status.TLabel").pack(side="left", padx=(18, 12))
        self.progress = ttk.Progressbar(bottom, mode="determinate", length=230)
        self.progress.pack(side="left", padx=(0, 12))
        ttk.Button(bottom, text="選擇輸出資料夾", command=self.choose_output).pack(side="right", padx=(6, 0))
        ttk.Button(bottom, text="取消", command=self.cancel).pack(side="right", padx=(6, 0))
        ttk.Button(bottom, text="開始批次導出", style="Primary.TButton", command=self.export).pack(side="right", padx=(6, 0))

    def _bind_shortcuts(self):
        self.bind("<Control-o>", lambda e: self.add_images())
        self.bind("<Control-Shift-O>", lambda e: self.add_folder())
        self.bind("<Control-e>", lambda e: self.export())
        self.bind("<Delete>", lambda e: self.remove_selected())
        self.bind("<Control-0>", lambda e: self.fit_preview())

    def slider(self, parent, label, var, a, b, suffix=""):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(6, 0))
        ttk.Label(row, text=label).pack(side="left")
        value = ttk.Label(row, text=f"{int(var.get())}{suffix}", style="Muted.TLabel")
        value.pack(side="right")
        def changed(_=None):
            try:
                value.config(text=f"{int(var.get())}{suffix}")
            except Exception:
                pass
            self.preview()
            self._refresh_summary()
        ttk.Scale(parent, from_=a, to=b, variable=var, command=changed).pack(fill="x")

    def spin_row(self, parent, label, var, a, b, suffix="", step=1):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(8, 0))
        ttk.Label(row, text=label).pack(side="left")
        ttk.Label(row, text=suffix, style="Muted.TLabel").pack(side="right")
        sp = ttk.Spinbox(row, from_=a, to=b, increment=step, textvariable=var, width=9, command=self._spin_changed)
        sp.pack(side="right", padx=(0, 6))
        sp.bind("<KeyRelease>", lambda e: self._spin_changed())

    def _spin_changed(self):
        self.preview()
        self._refresh_summary()

    def add_images(self):
        self._append(filedialog.askopenfilenames(title="選擇圖片", filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff")]))

    def add_folder(self):
        d = filedialog.askdirectory(title="選擇圖片資料夾")
        if d:
            self._append([str(p) for p in Path(d).iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED])

    def on_drop(self, e):
        try:
            items = self.tk.splitlist(e.data)
        except Exception:
            items = [e.data]
        arr = []
        for x in items:
            p = Path(x)
            if p.is_dir():
                arr += [str(y) for y in p.iterdir() if y.is_file() and y.suffix.lower() in SUPPORTED]
            elif p.is_file() and p.suffix.lower() in SUPPORTED:
                arr.append(str(p))
        self._append(arr)

    def _append(self, items):
        existing = set(self.paths)
        for p in items:
            p = str(p)
            if p in existing:
                continue
            self.paths.append(p)
            existing.add(p)
            try:
                with Image.open(p) as im:
                    size_text = f"{im.width}×{im.height}"
            except Exception:
                size_text = "—"
            self.tree.insert("", "end", iid=str(len(self.paths)-1), text=Path(p).name, values=(size_text,))
        if self.paths and not self.tree.selection():
            self.tree.selection_set("0")
        self.selection_info.set(f"{len(self.paths)} 張圖片")
        self.status.set(f"已載入 {len(self.paths)} 張")
        self._on_tree_select()

    def _rebuild_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, p in enumerate(self.paths):
            try:
                with Image.open(p) as im:
                    size_text = f"{im.width}×{im.height}"
            except Exception:
                size_text = "—"
            self.tree.insert("", "end", iid=str(i), text=Path(p).name, values=(size_text,))
        self.selection_info.set(f"{len(self.paths)} 張圖片")
        if self.paths:
            self.tree.selection_set("0")

    def _on_tree_select(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self.paths):
            return
        p = self.paths[idx]
        try:
            with Image.open(p) as im:
                kb = Path(p).stat().st_size / 1024
                self.file_info.set(f"{Path(p).name}\n{im.width} × {im.height}px · {kb:,.0f} KB · {im.format or ''}")
        except Exception:
            self.file_info.set(Path(p).name)
        self.preview()

    def remove_selected(self):
        selected = sorted([int(x) for x in self.tree.selection()], reverse=True)
        if not selected:
            return
        for i in selected:
            if 0 <= i < len(self.paths):
                del self.paths[i]
        self._rebuild_tree()
        self.preview()

    def clear(self):
        self.paths.clear()
        self._rebuild_tree()
        self.canvas.delete("all")
        self.file_info.set("尚未選擇圖片")
        self.status.set("圖片清單已清空")

    def choose_wm(self):
        p = filedialog.askopenfilename(title="選擇 Logo / 浮水印", filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")])
        if p:
            self.watermark_path = p
            self.wm_path_label.config(text=Path(p).name)
            self.preview()

    def choose_output(self):
        d = filedialog.askdirectory(title="選擇輸出資料夾")
        if d:
            self.output_dir.set(d)
            self.status.set(f"輸出：{d}")

    def choose_text_color(self):
        c = colorchooser.askcolor(color=self.text_color)
        if c and c[1]:
            self.text_color = c[1]
            self.preview()

    def quick_ratio(self, ratio, edge):
        self.output_ratio.set(ratio)
        self.size_mode.set("指定長邊")
        self.long_edge.set(edge)
        self.preview()
        self._refresh_summary()

    def set_ratio(self, ratio):
        self.output_ratio.set(ratio)
        self.preview()
        self._refresh_summary()

    def change_zoom(self, delta):
        self.preview_zoom.set(max(.25, min(3.0, self.preview_zoom.get() + delta)))
        self.zoom_label.config(text=f"{int(self.preview_zoom.get()*100)}%")
        self.preview()

    def set_zoom(self, value):
        self.preview_zoom.set(value)
        self.zoom_label.config(text=f"{int(value*100)}%")
        self.preview()

    def fit_preview(self):
        self.preview_zoom.set(1.0)
        self.zoom_label.config(text="符合視窗")
        self.preview()

    def _mouse_zoom(self, e):
        self.change_zoom(.1 if e.delta > 0 else -.1)

    def _refresh_summary(self):
        if self.size_mode.get() == "指定長邊":
            size_text = f"長邊 {self.long_edge.get()}px"
        else:
            size_text = f"{int(self.resize_percent.get())}%"
        self.export_summary.set(f"輸出：{self.output_ratio.get()} · {size_text} · {self.output_format.get()} · 品質 {self.quality.get()}")

    def crop(self, img, ratio_name=None):
        ratio = RATIOS.get(ratio_name or self.output_ratio.get())
        if not ratio:
            return img
        rw, rh = ratio
        target = rw / rh
        w, h = img.size
        cur = w / h
        cx = max(0, min(1, self.crop_x.get()))
        cy = max(0, min(1, self.crop_y.get()))
        if cur > target:
            nw = int(h * target)
            left = int((w - nw) * cx)
            return img.crop((left, 0, left + nw, h))
        nh = int(w / target)
        top = int((h - nh) * cy)
        return img.crop((0, top, w, top + nh))

    def resize(self, img, mode=None, pct=None, edge=None):
        mode = mode or self.size_mode.get()
        pct = self.resize_percent.get() if pct is None else pct
        edge = self.long_edge.get() if edge is None else edge
        w, h = img.size
        if mode == "指定長邊":
            cur = max(w, h)
            scale = edge / cur
            if scale > 1 and not self.allow_upscale.get():
                scale = 1
        else:
            scale = pct / 100
            if scale > 1 and not self.allow_upscale.get():
                scale = 1
        if abs(scale - 1) < .001:
            return img
        return img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)

    def anchor(self, bs, osz, pos, margin=24):
        bw, bh = bs
        ow, oh = osz
        xs = {"左": margin, "中": (bw - ow) // 2, "右": bw - ow - margin}
        ys = {"上": margin, "中": (bh - oh) // 2, "下": bh - oh - margin}
        if pos == "置中":
            return xs["中"], ys["中"]
        if len(pos) == 2:
            a, b = pos[0], pos[1]
            return (xs[a], ys[b]) if a in "左右" else (xs[b], ys[a])
        return bw - ow - margin, bh - oh - margin

    def apply_wm(self, img):
        base = img.convert("RGBA")
        if self.wm_enabled.get() and self.watermark_path:
            wm = Image.open(self.watermark_path).convert("RGBA")
            tw = max(1, int(base.width * self.wm_scale.get() / 100))
            sc = tw / wm.width
            wm = wm.resize((tw, max(1, int(wm.height * sc))), Image.Resampling.LANCZOS)
            if abs(self.wm_rotation.get()) > .01:
                wm = wm.rotate(self.wm_rotation.get(), expand=True, resample=Image.Resampling.BICUBIC)
            alpha = wm.getchannel("A")
            wm.putalpha(ImageEnhance.Brightness(alpha).enhance(self.wm_opacity.get() / 100))
            if self.wm_mode.get() == "平鋪":
                sx = max(1, wm.width + self.tile_gap.get())
                sy = max(1, wm.height + self.tile_gap.get())
                row = 0
                y = -wm.height // 2
                while y < base.height:
                    x = -wm.width // 2 + (sx // 2 if row % 2 else 0)
                    while x < base.width:
                        base.alpha_composite(wm, dest=(x, y))
                        x += sx
                    y += sy
                    row += 1
            else:
                if self.wm_mode.get() == "自由位置":
                    x = int(self.free_x.get() * base.width - wm.width / 2)
                    y = int(self.free_y.get() * base.height - wm.height / 2)
                else:
                    x, y = self.anchor(base.size, wm.size, self.wm_position.get(), self.margin.get())
                base.alpha_composite(wm, dest=(x, y))
        if self.text_enabled.get() and self.text_value.get().strip():
            layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            try:
                f = ImageFont.truetype("arial.ttf", self.text_size.get())
            except Exception:
                f = ImageFont.load_default()
            h = self.text_color.lstrip("#")
            rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
            fill = (*rgb, int(self.text_opacity.get() * 2.55))
            bb = d.textbbox((0, 0), self.text_value.get(), font=f)
            size = (bb[2] - bb[0], bb[3] - bb[1])
            x, y = self.anchor(base.size, size, self.text_position.get(), self.margin.get())
            d.text((x, y), self.text_value.get(), font=f, fill=fill)
            base = Image.alpha_composite(base, layer)
        return base

    def process(self, path, ratio=None, mode=None, pct=None, edge=None, processed=True):
        with Image.open(path) as s:
            exif = s.info.get("exif")
            img = ImageOps.exif_transpose(s).convert("RGBA")
            img = self.crop(img, ratio)
            img = self.resize(img, mode, pct, edge)
            if processed:
                img = self.apply_wm(img)
            return img, exif

    def preview(self):
        if not self.paths:
            return
        try:
            sel = self.tree.selection()
            idx = int(sel[0]) if sel else 0
            if idx >= len(self.paths):
                idx = 0
            img, _ = self.process(self.paths[idx], processed=self.preview_processed.get())
            cw = max(250, self.canvas.winfo_width() - 24)
            ch = max(250, self.canvas.winfo_height() - 24)
            p = img.copy()
            p.thumbnail((cw, ch), Image.Resampling.LANCZOS)
            zoom = max(.25, min(3.0, self.preview_zoom.get()))
            if abs(zoom - 1) > .01:
                nw = max(1, int(p.width * zoom))
                nh = max(1, int(p.height * zoom))
                p = p.resize((nw, nh), Image.Resampling.LANCZOS)
            self.preview_photo = ImageTk.PhotoImage(p)
            self.canvas.delete("all")
            cx = self.canvas.winfo_width() // 2
            cy = self.canvas.winfo_height() // 2
            self.canvas.create_image(cx, cy, image=self.preview_photo)
            self.preview_box = (cx - p.width // 2, cy - p.height // 2, cx + p.width // 2, cy + p.height // 2)
            self.canvas.create_text(14, 14, anchor="nw", text=f"{img.width} × {img.height}px", fill="#aab2bb", font=("Segoe UI", 9))
        except Exception as e:
            self.status.set(f"預覽失敗：{e}")

    def drag(self, e):
        if not self.preview_box:
            return
        l, t, r, b = self.preview_box
        if not (l <= e.x <= r and t <= e.y <= b):
            return
        nx = (e.x - l) / max(1, r - l)
        ny = (e.y - t) / max(1, b - t)
        if self.wm_mode.get() == "自由位置" and self.watermark_path:
            self.free_x.set(nx)
            self.free_y.set(ny)
        elif RATIOS.get(self.output_ratio.get()):
            self.crop_x.set(nx)
            self.crop_y.set(ny)
        self.preview()

    def reset_crop(self):
        self.crop_x.set(.5)
        self.crop_y.set(.5)
        self.preview()

    def filename(self, src, i, img, fmt):
        ext = ".png" if fmt == "PNG" else ".jpeg" if fmt == "JPEG" else ".jpg"
        if not self.rename_enabled.get():
            return Path(src).stem + ext
        idx = f"{self.rename_start.get() + i:0{self.rename_digits.get()}d}"
        d = {"name": Path(src).stem, "index": idx, "date": datetime.now().strftime("%Y%m%d"), "width": img.width, "height": img.height}
        try:
            stem = self.rename_template.get().format(**d)
        except Exception:
            stem = f"{Path(src).stem}_{idx}"
        for c in '<>:"/\\|?*':
            stem = stem.replace(c, "_")
        return stem + ext

    def resolve(self, p):
        if not p.exists() or self.conflict_mode.get() == "覆蓋":
            return p
        if self.conflict_mode.get() == "略過":
            return None
        n = 1
        while True:
            c = p.with_name(f"{p.stem}_{n}{p.suffix}")
            if not c.exists():
                return c
            n += 1

    def save_image(self, img, p, fmt, q, exif):
        if fmt in ("JPG", "JPEG"):
            bg = Image.new("RGB", img.size, "white")
            if img.mode == "RGBA":
                bg.paste(img, mask=img.getchannel("A"))
            else:
                bg.paste(img.convert("RGB"))
            kw = {"format": "JPEG", "quality": q, "optimize": True}
            if self.preserve_exif.get() and exif:
                kw["exif"] = exif
            bg.save(p, **kw)
        else:
            img.save(p, "PNG", optimize=True)

    def export(self):
        if not self.paths:
            messagebox.showwarning("提醒", "請先加入圖片")
            return
        out = Path(self.output_dir.get())
        out.mkdir(parents=True, exist_ok=True)
        self.cancelled = False
        self._sync_profiles()
        active = [(n, c) for n, c in self.profiles.items() if c.get("enabled")]
        total = len(self.paths) * (len(active) if active else 1)
        self.progress["maximum"] = max(1, total)
        self.progress["value"] = 0
        self.save_settings()
        self.status.set("開始處理…")
        threading.Thread(target=self.worker, args=(out, active), daemon=True).start()

    def worker(self, out, active):
        done = skip = step = 0
        errors = []
        for i, src in enumerate(self.paths):
            if self.cancelled:
                break
            profiles = active or [("Single", {"ratio": self.output_ratio.get(), "mode": self.size_mode.get(), "pct": self.resize_percent.get(), "edge": self.long_edge.get(), "format": self.output_format.get(), "quality": self.quality.get()})]
            for name, c in profiles:
                if self.cancelled:
                    break
                try:
                    img, exif = self.process(src, c.get("ratio"), c.get("mode", "指定長邊"), c.get("pct", 100), c.get("edge", 2048), processed=True)
                    fmt = c.get("format", "JPG")
                    folder = out if not active else out / name
                    folder.mkdir(parents=True, exist_ok=True)
                    p = self.resolve(folder / self.filename(src, i, img, fmt))
                    if p is None:
                        skip += 1
                    else:
                        self.save_image(img, p, fmt, c.get("quality", 92), exif)
                        done += 1
                except Exception as e:
                    errors.append(f"{Path(src).name}: {e}")
                step += 1
                self.after(0, lambda v=step: (self.progress.configure(value=v), self.status.set(f"處理中 {v}/{int(self.progress['maximum'])}")))
        self.after(0, lambda: self.finish(done, skip, errors, out))

    def finish(self, done, skip, errors, out):
        self.status.set("已取消" if self.cancelled else f"完成：{done}")
        msg = f"成功 {done}\n略過 {skip}\n錯誤 {len(errors)}\n\n{out}"
        if errors:
            messagebox.showwarning("完成", msg + "\n\n" + "\n".join(errors[:5]))
        else:
            messagebox.showinfo("完成", msg)
        try:
            if os.name == "nt":
                os.startfile(str(out))
        except Exception:
            pass

    def cancel(self):
        self.cancelled = True
        self.status.set("正在停止…")

    def default_profiles(self):
        return {
            "Instagram_4x5": {"enabled": True, "ratio": "4:5", "mode": "指定長邊", "edge": 1350, "format": "JPG", "quality": 92},
            "Story_9x16": {"enabled": False, "ratio": "9:16", "mode": "指定長邊", "edge": 1920, "format": "JPG", "quality": 92},
            "Square_1x1": {"enabled": False, "ratio": "1:1", "mode": "指定長邊", "edge": 1080, "format": "JPG", "quality": 92},
        }

    def refresh_profiles(self):
        for w in self.multi_frame.winfo_children():
            w.destroy()
        self.profile_vars = {}
        for n, c in self.profiles.items():
            v = tk.BooleanVar(value=c.get("enabled", False))
            self.profile_vars[n] = v
            r = ttk.Frame(self.multi_frame)
            r.pack(fill="x", pady=4)
            ttk.Checkbutton(r, text=n, variable=v, command=self._sync_profiles).pack(side="left")
            ttk.Label(r, text=f"{c.get('ratio')} · {c.get('edge')}px", style="Muted.TLabel").pack(side="right")

    def _sync_profiles(self):
        for n, v in self.profile_vars.items():
            self.profiles[n]["enabled"] = v.get()
        self._save_json(PROFILES_FILE, self.profiles)

    def add_profile(self):
        n = simpledialog.askstring("新增規格", "名稱：", parent=self)
        if not n:
            return
        ratio = simpledialog.askstring("比例", "4:5 / 9:16 / 1:1 / 原始比例", initialvalue="4:5", parent=self)
        ratio = ratio if ratio in RATIOS else "原始比例"
        edge = simpledialog.askinteger("長邊", "像素", initialvalue=1350, minvalue=320, maxvalue=20000, parent=self) or 1350
        self.profiles[n] = {"enabled": True, "ratio": ratio, "mode": "指定長邊", "edge": edge, "format": "JPG", "quality": 92}
        self._save_json(PROFILES_FILE, self.profiles)
        self.refresh_profiles()

    def delete_profiles(self):
        selected = [x for x, v in self.profile_vars.items() if v.get()]
        if not selected:
            return
        if not messagebox.askyesno("刪除規格", "確定刪除勾選的輸出規格？"):
            return
        for n in selected:
            self.profiles.pop(n, None)
        self._save_json(PROFILES_FILE, self.profiles)
        self.refresh_profiles()

    def config(self):
        return {
            "wm_enabled": self.wm_enabled.get(), "wm_mode": self.wm_mode.get(), "wm_position": self.wm_position.get(),
            "wm_scale": self.wm_scale.get(), "wm_opacity": self.wm_opacity.get(), "wm_rotation": self.wm_rotation.get(),
            "margin": self.margin.get(), "free_x": self.free_x.get(), "free_y": self.free_y.get(), "tile_gap": self.tile_gap.get(),
            "text_enabled": self.text_enabled.get(), "text_value": self.text_value.get(), "text_size": self.text_size.get(),
            "text_opacity": self.text_opacity.get(), "text_color": self.text_color, "text_position": self.text_position.get(),
            "output_ratio": self.output_ratio.get(), "crop_x": self.crop_x.get(), "crop_y": self.crop_y.get(),
            "size_mode": self.size_mode.get(), "resize_percent": self.resize_percent.get(), "long_edge": self.long_edge.get(),
            "allow_upscale": self.allow_upscale.get(), "output_format": self.output_format.get(), "quality": self.quality.get(),
            "preserve_exif": self.preserve_exif.get(), "rename_enabled": self.rename_enabled.get(), "rename_template": self.rename_template.get(),
            "rename_start": self.rename_start.get(), "rename_digits": self.rename_digits.get(), "conflict_mode": self.conflict_mode.get(),
            "output_dir": self.output_dir.get(), "watermark_path": self.watermark_path
        }

    def apply_cfg(self, c):
        m = {
            "wm_enabled": self.wm_enabled, "wm_mode": self.wm_mode, "wm_position": self.wm_position,
            "wm_scale": self.wm_scale, "wm_opacity": self.wm_opacity, "wm_rotation": self.wm_rotation,
            "margin": self.margin, "free_x": self.free_x, "free_y": self.free_y, "tile_gap": self.tile_gap,
            "text_enabled": self.text_enabled, "text_value": self.text_value, "text_size": self.text_size,
            "text_opacity": self.text_opacity, "text_position": self.text_position, "output_ratio": self.output_ratio,
            "crop_x": self.crop_x, "crop_y": self.crop_y, "size_mode": self.size_mode, "resize_percent": self.resize_percent,
            "long_edge": self.long_edge, "allow_upscale": self.allow_upscale, "output_format": self.output_format,
            "quality": self.quality, "preserve_exif": self.preserve_exif, "rename_enabled": self.rename_enabled,
            "rename_template": self.rename_template, "rename_start": self.rename_start, "rename_digits": self.rename_digits,
            "conflict_mode": self.conflict_mode, "output_dir": self.output_dir
        }
        for k, v in m.items():
            if k in c:
                v.set(c[k])
        if "text_color" in c:
            self.text_color = c["text_color"]
        p = c.get("watermark_path")
        if p and Path(p).exists():
            self.watermark_path = p
            self.wm_path_label.config(text=Path(p).name)
        self.preview()
        self._refresh_summary()

    def _save_json(self, p, obj):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_json(self, p, default):
        try:
            return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
        except Exception:
            return default

    def save_settings(self):
        self._save_json(SETTINGS_FILE, self.config())

    def _load_all(self):
        c = self._load_json(SETTINGS_FILE, {})
        self.presets = self._load_json(PRESETS_FILE, {})
        self.brands = self._load_json(BRANDS_FILE, {})
        self.profiles = self._load_json(PROFILES_FILE, self.default_profiles())
        self.apply_cfg(c)
        self.refresh_presets()
        self.refresh_brands()
        self.refresh_profiles()

    def refresh_presets(self):
        self.preset_combo["values"] = list(self.presets)
        self.preset_name.set(next(iter(self.presets), ""))

    def refresh_brands(self):
        self.brand_combo["values"] = list(self.brands)
        self.brand_name.set(next(iter(self.brands), ""))

    def save_preset(self):
        n = simpledialog.askstring("Preset", "名稱：", parent=self)
        if n:
            self.presets[n] = self.config()
            self._save_json(PRESETS_FILE, self.presets)
            self.refresh_presets()
            self.preset_name.set(n)

    def apply_preset(self):
        if self.preset_name.get() in self.presets:
            self.apply_cfg(self.presets[self.preset_name.get()])

    def delete_preset(self):
        n = self.preset_name.get()
        if n and n in self.presets:
            self.presets.pop(n, None)
            self._save_json(PRESETS_FILE, self.presets)
            self.refresh_presets()

    def save_brand(self):
        n = simpledialog.askstring("品牌", "品牌名稱：", parent=self)
        if n:
            self.brands[n] = self.config()
            self._save_json(BRANDS_FILE, self.brands)
            self.refresh_brands()
            self.brand_name.set(n)

    def apply_brand(self):
        if self.brand_name.get() in self.brands:
            self.apply_cfg(self.brands[self.brand_name.get()])


if __name__ == "__main__":
    App().mainloop()

