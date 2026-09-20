import os
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox

import app as base


class EnhancedApp(base.App):
    """v4.1 integration layer: global drag/drop, live preview, source-folder export."""

    def __init__(self):
        # Base App creates the Tk root and loads its own settings first.
        # Extra Tk variables must only be created AFTER the root exists.
        self._pending_enhanced_cfg = {}
        super().__init__()

        self.output_to_source = tk.BooleanVar(master=self, value=False)
        self.source_subfolder = tk.StringVar(master=self, value="加工後")

        pending = dict(getattr(self, "_pending_enhanced_cfg", {}) or {})
        if "output_to_source" in pending:
            self.output_to_source.set(bool(pending["output_to_source"]))
        if "source_subfolder" in pending:
            self.source_subfolder.set(str(pending["source_subfolder"]))

        self.title("Batch Watermark Tool Pro v4.1")
        self._install_source_export_bar()
        self._register_drop_targets_recursive(self)
        self._install_live_preview_traces()
        self._refresh_enhanced_summary()

    # ---------- Drag & drop ----------
    def _register_drop_targets_recursive(self, widget):
        """Make the whole application window accept file/folder drops."""
        if not base.DND_AVAILABLE:
            return
        try:
            widget.drop_target_register(base.DND_FILES)
            widget.dnd_bind("<<Drop>>", self.on_drop)
        except Exception:
            pass
        try:
            for child in widget.winfo_children():
                self._register_drop_targets_recursive(child)
        except Exception:
            pass

    def on_drop(self, event):
        """Accept one/many images and folders; folders are scanned recursively."""
        try:
            items = self.tk.splitlist(event.data)
        except Exception:
            items = [event.data]

        found = []
        for raw in items:
            p = Path(str(raw).strip())
            if p.is_file() and p.suffix.lower() in base.SUPPORTED:
                found.append(str(p))
            elif p.is_dir():
                try:
                    found.extend(
                        str(x) for x in p.rglob("*")
                        if x.is_file() and x.suffix.lower() in base.SUPPORTED
                    )
                except Exception:
                    pass

        if found:
            self._append(sorted(found))
            self.status.set(f"拖曳匯入完成：目前 {len(self.paths)} 張")
        else:
            self.status.set("拖曳內容中沒有支援的圖片格式")

    # ---------- Live preview ----------
    def _install_live_preview_traces(self):
        variables = [
            self.wm_enabled, self.wm_mode, self.wm_position,
            self.wm_scale, self.wm_opacity, self.wm_rotation,
            self.margin, self.free_x, self.free_y, self.tile_gap,
            self.text_enabled, self.text_value, self.text_size,
            self.text_opacity, self.text_position,
            self.output_ratio, self.crop_x, self.crop_y,
            self.size_mode, self.resize_percent, self.long_edge,
            self.allow_upscale, self.output_format, self.quality,
        ]
        for variable in variables:
            try:
                variable.trace_add("write", self._on_live_change)
            except Exception:
                pass

    def _on_live_change(self, *_):
        try:
            self.preview()
            self._refresh_enhanced_summary()
        except Exception:
            pass

    # ---------- Source-folder output UI ----------
    def _install_source_export_bar(self):
        bar = ttk.Frame(self, style="Bottom.TFrame", padding=(14, 7))
        bar.pack(fill="x", side="bottom")

        ttk.Label(bar, text="輸出位置", style="Status.TLabel").pack(side="left")
        ttk.Checkbutton(
            bar,
            text="輸出到每張原圖所在資料夾",
            variable=self.output_to_source,
            command=self._refresh_enhanced_summary,
        ).pack(side="left", padx=(12, 8))

        ttk.Label(bar, text="子資料夾：", style="Status.TLabel").pack(side="left")
        ttk.Entry(bar, textvariable=self.source_subfolder, width=16).pack(side="left", padx=(0, 10))
        self.source_subfolder.trace_add("write", lambda *_: self._refresh_enhanced_summary())

        ttk.Label(
            bar,
            text="例：原圖\\加工後\\photo.jpg",
            style="Status.TLabel",
        ).pack(side="left")

        if not base.DND_AVAILABLE:
            ttk.Label(
                bar,
                text="拖曳元件未載入，仍可使用『加入圖片』",
                style="Status.TLabel",
            ).pack(side="right")

    def _safe_subfolder(self):
        name = self.source_subfolder.get().strip() or "加工後"
        for char in '<>:"/\\|?*':
            name = name.replace(char, "_")
        name = name.strip(" .")
        if not name or name in {".", ".."}:
            name = "加工後"
        return name

    def _refresh_enhanced_summary(self):
        if not hasattr(self, "output_to_source"):
            return
        try:
            if self.size_mode.get() == "指定長邊":
                size_text = f"長邊 {self.long_edge.get()}px"
            else:
                size_text = f"{int(self.resize_percent.get())}%"
            destination = (
                f"原圖資料夾 / {self._safe_subfolder()}"
                if self.output_to_source.get()
                else "自訂輸出資料夾"
            )
            self.export_summary.set(
                f"輸出：{self.output_ratio.get()} · {size_text} · "
                f"{self.output_format.get()} · 品質 {self.quality.get()} · {destination}"
            )
        except Exception:
            pass

    # ---------- Destination behavior ----------
    def _target_folder(self, src, profile_name=None):
        if self.output_to_source.get():
            folder = Path(src).parent / self._safe_subfolder()
        else:
            folder = Path(self.output_dir.get()).expanduser()
        if profile_name:
            folder = folder / profile_name
        return folder

    def worker(self, out, active):
        done = 0
        skip = 0
        step = 0
        errors = []

        for i, src in enumerate(self.paths):
            if self.cancelled:
                break

            profiles = active or [("Single", {
                "ratio": self.output_ratio.get(),
                "mode": self.size_mode.get(),
                "pct": self.resize_percent.get(),
                "edge": self.long_edge.get(),
                "format": self.output_format.get(),
                "quality": self.quality.get(),
            })]

            for name, cfg in profiles:
                if self.cancelled:
                    break
                try:
                    img, exif = self.process(
                        src,
                        cfg.get("ratio"),
                        cfg.get("mode", "指定長邊"),
                        cfg.get("pct", 100),
                        cfg.get("edge", 2048),
                        processed=True,
                    )
                    fmt = cfg.get("format", "JPG")
                    folder = self._target_folder(src, name if active else None)
                    folder.mkdir(parents=True, exist_ok=True)
                    output_path = self.resolve(folder / self.filename(src, i, img, fmt))

                    if output_path is None:
                        skip += 1
                    else:
                        self.save_image(img, output_path, fmt, cfg.get("quality", 92), exif)
                        done += 1
                except Exception as exc:
                    errors.append(f"{Path(src).name}: {exc}")

                step += 1
                self.after(0, lambda value=step: (
                    self.progress.configure(value=value),
                    self.status.set(f"處理中 {value}/{int(self.progress['maximum'])}"),
                ))

        self.after(0, lambda: self.finish(done, skip, errors, out))

    def finish(self, done, skip, errors, out):
        self.status.set("已取消" if self.cancelled else f"完成：{done}")
        destination = (
            f"各原圖資料夾內的『{self._safe_subfolder()}』"
            if self.output_to_source.get()
            else str(out)
        )
        msg = f"成功 {done}\n略過 {skip}\n錯誤 {len(errors)}\n\n輸出位置：{destination}"

        if errors:
            messagebox.showwarning("批次處理完成", msg + "\n\n" + "\n".join(errors[:8]))
        else:
            messagebox.showinfo("批次處理完成", msg)

        try:
            if os.name == "nt" and not self.output_to_source.get():
                os.startfile(str(out))
        except Exception:
            pass

    # ---------- Persist enhanced settings ----------
    def config(self):
        cfg = super().config()
        if hasattr(self, "output_to_source"):
            cfg["output_to_source"] = self.output_to_source.get()
            cfg["source_subfolder"] = self.source_subfolder.get()
        else:
            cfg.update(getattr(self, "_pending_enhanced_cfg", {}) or {})
        return cfg

    def apply_cfg(self, cfg):
        # Called once during base initialization before our extra Tk variables exist.
        super().apply_cfg(cfg)
        if hasattr(self, "output_to_source"):
            if "output_to_source" in cfg:
                self.output_to_source.set(bool(cfg["output_to_source"]))
            if "source_subfolder" in cfg:
                self.source_subfolder.set(str(cfg["source_subfolder"]))
            self._refresh_enhanced_summary()
        else:
            self._pending_enhanced_cfg = {
                "output_to_source": cfg.get("output_to_source", False),
                "source_subfolder": cfg.get("source_subfolder", "加工後"),
            }
