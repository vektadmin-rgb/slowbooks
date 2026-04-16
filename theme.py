"""
theme.py — Slowbooks
All visual constants and ttk style configuration.
Import this in receipt_tracker.py: from theme import *
"""

import tkinter as tk
from tkinter import ttk

# ─────────────────────────────────────────────
# PALETTE
# ─────────────────────────────────────────────
BG      = "#0f0f0f"   # root background
PANEL   = "#1a1a1a"   # sidebar / toolbar
CARD    = "#222222"   # input fields / buttons
BORDER  = "#2e2e2e"   # separators / field borders
ACCENT  = "#c8102e"   # primary red
ACCENT2 = "#ff3c5a"   # lighter red / totals highlight
TEXT    = "#f0f0f0"   # primary text
MUTED   = "#888888"   # labels / secondary text
SUCCESS = "#2ecc71"   # location on / saved states
WARNING = "#f39c12"   # caution states

# ─────────────────────────────────────────────
# TYPOGRAPHY
# ─────────────────────────────────────────────
FONT_H1 = ("Georgia", 20, "bold")
FONT_H2 = ("Georgia", 14, "bold")
FONT_H3 = ("Georgia", 11, "bold")
FONT_B  = ("Consolas", 10)
FONT_SM = ("Consolas", 9)

# ─────────────────────────────────────────────
# BRANDING
# ─────────────────────────────────────────────
APP_NAME    = "Slowbooks"
APP_SUBTITLE = "by Nick War Art"
WINDOW_TITLE = "Slowbooks — Nick War Art Expense Tracker"

# ─────────────────────────────────────────────
# TTK STYLE APPLICATOR
# Call apply_theme(root) once at app startup
# ─────────────────────────────────────────────
def apply_theme(root: tk.Tk):
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(
        "Treeview",
        background=CARD,
        foreground=TEXT,
        fieldbackground=CARD,
        rowheight=32,
        font=FONT_B,
        borderwidth=0,
    )
    style.configure(
        "Treeview.Heading",
        background=PANEL,
        foreground=MUTED,
        font=FONT_SM,
        relief=tk.FLAT,
    )
    style.map("Treeview", background=[("selected", ACCENT)])

    style.configure(
        "TCombobox",
        fieldbackground=CARD,
        background=CARD,
        foreground=TEXT,
        font=FONT_B,
        selectbackground=ACCENT,
        selectforeground=TEXT,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", CARD)],
        foreground=[("readonly", TEXT)],
    )

    style.configure(
        "Vertical.TScrollbar",
        background=BORDER,
        troughcolor=BG,
        arrowcolor=MUTED,
        borderwidth=0,
    )

    style.configure(
        "TSeparator",
        background=BORDER,
    )
