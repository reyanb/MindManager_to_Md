"""Simple GUI application to convert MindManager files to Markdown."""

from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception:  # pragma: no cover - optional dependency
    TkinterDnD = None  # type: ignore[assignment]
    DND_FILES = None  # type: ignore[assignment]

from mindmap_to_md import MindmapConversionError, extract_markdown_lines


def convert_with_save_dialog(root: tk.Tk, file_path: str) -> bool:
    """Run the conversion flow for a single file, prompting for destination."""
    try:
        md_lines = extract_markdown_lines(file_path)
    except MindmapConversionError as exc:
        messagebox.showerror("Conversion failed", str(exc), parent=root)
        return False

    initial_name = f"{Path(file_path).stem}.md"
    output_path = filedialog.asksaveasfilename(
        parent=root,
        title="Save Markdown As",
        initialfile=initial_name,
        defaultextension=".md",
        filetypes=(("Markdown", "*.md"), ("All Files", "*.*")),
    )
    if not output_path:
        return False

    with open(output_path, "w", encoding="utf-8") as stream:
        stream.write("\n".join(md_lines))

    messagebox.showinfo(
        "Conversion complete",
        f"Markdown saved to:\n{output_path}",
        parent=root,
    )
    return True


class MindmapConverterApp:
    def __init__(self) -> None:
        BaseTk = TkinterDnD.Tk if TkinterDnD else tk.Tk
        try:
            self.root = BaseTk()
            self._dragdrop_enabled = TkinterDnD is not None
        except RuntimeError:
            # Fallback when tkdnd library cannot be loaded even though
            # tkinterdnd2 is importable (common on macOS without tkdnd).
            self.root = tk.Tk()
            self._dragdrop_enabled = False
        self.root.title("Mindmap → Markdown")
        self.root.geometry("420x260")
        self.root.minsize(360, 220)

        self.status_var = tk.StringVar(
            self.root,
            value="Drop a .mmap/.xmmap file here or click ‘Choose Mind Map’.",
        )

        container = ttk.Frame(self.root, padding=20)
        container.pack(fill=tk.BOTH, expand=True)

        drop_label_text = (
            "Drop mind map here"
            if self._dragdrop_enabled
            else "Drag & drop needs 'tkinterdnd2' + tkdnd library"
        )

        self.drop_zone = ttk.Frame(
            container,
            relief=tk.RIDGE,
            padding=30,
        )
        self.drop_zone.pack(fill=tk.BOTH, expand=True)
        self.drop_zone.pack_propagate(False)

        self.drop_message = ttk.Label(
            self.drop_zone,
            text=drop_label_text,
            anchor=tk.CENTER,
            font=("Helvetica", 13),
            wraplength=260,
        )
        self.drop_message.pack(expand=True)

        if self._dragdrop_enabled and DND_FILES:
            self.drop_zone.drop_target_register(DND_FILES)
            self.drop_zone.dnd_bind("<<Drop>>", self._on_drop)

        button_bar = ttk.Frame(container)
        button_bar.pack(fill=tk.X, pady=(15, 0))

        choose_btn = ttk.Button(
            button_bar,
            text="Choose Mind Map…",
            command=self.select_file,
        )
        choose_btn.pack(side=tk.LEFT)

        info_label = ttk.Label(
            container,
            textvariable=self.status_var,
            wraplength=360,
            foreground="#444444",
            padding=(0, 12, 0, 0),
            justify=tk.LEFT,
        )
        info_label.pack(fill=tk.X)

    def select_file(self) -> None:
        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="Select MindManager file",
            filetypes=(
                ("MindManager maps", "*.mmap *.xmmap"),
                ("All files", "*.*"),
            ),
        )
        if file_path:
            self.convert_and_report(file_path)

    def _on_drop(self, event: tk.Event) -> None:  # type: ignore[override]
        if not event.data:
            return
        file_paths = self.root.tk.splitlist(event.data)
        for path in file_paths:
            self.convert_and_report(path)

    def convert_and_report(self, file_path: str) -> None:
        normalized = os.path.normpath(file_path)
        if not os.path.isfile(normalized):
            messagebox.showerror(
                "Invalid file",
                f"The dropped item is not a file:\n{file_path}",
                parent=self.root,
            )
            return

        self.status_var.set(f"Converting {normalized} …")
        self.root.update_idletasks()

        success = convert_with_save_dialog(self.root, normalized)
        if success:
            self.status_var.set("Conversion complete. You can convert another file.")
        else:
            self.status_var.set("Conversion cancelled or failed. Try again.")

    def run(self) -> None:
        self.root.mainloop()


def process_cli_arguments(paths: list[str]) -> None:
    root = tk.Tk()
    root.withdraw()
    for path in paths:
        normalized = os.path.normpath(path)
        if not os.path.isfile(normalized):
            messagebox.showerror(
                "Invalid file",
                f"The dropped item is not a file:\n{path}",
                parent=root,
            )
            continue
        convert_with_save_dialog(root, normalized)
    root.destroy()


if __name__ == "__main__":
    input_paths = [arg for arg in sys.argv[1:] if arg.strip()]
    if input_paths:
        process_cli_arguments(input_paths)
    else:
        MindmapConverterApp().run()
