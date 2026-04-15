"""Floating AERIS desktop widget.

Features:
- Adjustable transparency (alpha)
- Sticky always-on-top mode
- Clickable/drag-movable surface
- Live preview of current AERIS mode + last message
- Quick actions: speak last message, open chat terminal
"""

from __future__ import annotations

import asyncio
import subprocess
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk

MODE_FILE = Path("/tmp/aeris_mode")
LAST_MSG_FILE = Path("/tmp/aeris_last_msg")


class AerisWidget:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.drag_x = 0
        self.drag_y = 0
        self.alpha = tk.DoubleVar(value=0.68)
        self.sticky = tk.BooleanVar(value=True)

        self.mode_text = tk.StringVar(value="mode: booting")
        self.last_text = tk.StringVar(value="AERIS is waking up...")

        self._build_window()
        self._build_ui()
        self._bind_drag()

        self.refresh_files()
        self.keep_on_top()

    def _build_window(self) -> None:
        self.root.title("AERIS")
        self.root.geometry("360x170+70+90")
        self.root.overrideredirect(True)
        self.root.configure(bg="#0b1220")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", self.alpha.get())

    def _build_ui(self) -> None:
        frame = tk.Frame(self.root, bg="#0b1220", highlightthickness=1, highlightbackground="#5fb0ff")
        frame.pack(fill="both", expand=True)

        header = tk.Frame(frame, bg="#102038")
        header.pack(fill="x")

        tk.Label(
            header,
            text="AERIS",
            fg="#d9ecff",
            bg="#102038",
            font=("DejaVu Sans", 11, "bold"),
            padx=10,
            pady=6,
        ).pack(side="left")

        ttk.Button(header, text="x", width=3, command=self.root.destroy).pack(side="right", padx=6, pady=4)

        body = tk.Frame(frame, bg="#0b1220")
        body.pack(fill="both", expand=True, padx=10, pady=8)

        tk.Label(body, textvariable=self.mode_text, fg="#99cfff", bg="#0b1220", anchor="w").pack(fill="x")
        tk.Label(
            body,
            textvariable=self.last_text,
            fg="#e7f3ff",
            bg="#0b1220",
            anchor="w",
            justify="left",
            wraplength=330,
        ).pack(fill="x", pady=(4, 8))

        controls = tk.Frame(body, bg="#0b1220")
        controls.pack(fill="x")

        tk.Label(controls, text="Transparency", fg="#bddfff", bg="#0b1220").pack(side="left")
        ttk.Scale(controls, from_=0.30, to=1.0, variable=self.alpha, command=self.on_alpha_changed).pack(side="left", fill="x", expand=True, padx=8)

        actions = tk.Frame(body, bg="#0b1220")
        actions.pack(fill="x", pady=(8, 0))

        ttk.Checkbutton(actions, text="Sticky", variable=self.sticky, command=self.on_sticky_toggle).pack(side="left")
        ttk.Button(actions, text="Speak", command=self.speak_last).pack(side="left", padx=6)
        ttk.Button(actions, text="Chat", command=self.open_chat).pack(side="left")

    def _bind_drag(self) -> None:
        self.root.bind("<ButtonPress-1>", self.on_drag_start)
        self.root.bind("<B1-Motion>", self.on_drag_move)

    def on_drag_start(self, event: tk.Event) -> None:
        self.drag_x = event.x
        self.drag_y = event.y

    def on_drag_move(self, event: tk.Event) -> None:
        x = self.root.winfo_x() + event.x - self.drag_x
        y = self.root.winfo_y() + event.y - self.drag_y
        self.root.geometry(f"+{x}+{y}")

    def on_alpha_changed(self, _value: str) -> None:
        self.root.attributes("-alpha", max(0.30, min(1.0, self.alpha.get())))

    def on_sticky_toggle(self) -> None:
        self.root.attributes("-topmost", self.sticky.get())

    def keep_on_top(self) -> None:
        if self.sticky.get():
            self.root.attributes("-topmost", True)
        self.root.after(2000, self.keep_on_top)

    def refresh_files(self) -> None:
        mode = MODE_FILE.read_text(encoding="utf-8").strip() if MODE_FILE.exists() else "offline"
        msg = LAST_MSG_FILE.read_text(encoding="utf-8").strip() if LAST_MSG_FILE.exists() else "No recent message yet."

        self.mode_text.set(f"mode: {mode}")
        self.last_text.set(msg[:120])
        self.root.after(1200, self.refresh_files)

    def speak_last(self) -> None:
        text = self.last_text.get().strip()
        if not text:
            return

        def _worker() -> None:
            try:
                from personality.voice import voice
                asyncio.run(voice.speak(text))
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def open_chat(self) -> None:
        cmd = [
            "bash",
            "-lc",
            "cd /mnt/win_d/projects/AERIS && python assistant.py",
        ]
        subprocess.Popen(["x-terminal-emulator", "-e", *cmd])


def main() -> None:
    root = tk.Tk()
    AerisWidget(root)
    root.mainloop()


if __name__ == "__main__":
    main()
