"""
styles.py — Slowbooks
All visual constants, typography, branding, and ttk theme configuration.
"""

import tkinter as tk
from tkinter import ttk

# ─────────────────────────────────────────────
# PALETTE
# ─────────────────────────────────────────────
BG      = "#0f0f0f"   # root background
PANEL   = "#1a1a1a"   # sidebar / toolbar
CARD    = "#222222"   # input fields / secondary buttons
BORDER  = "#2e2e2e"   # separators / field outlines
ACCENT  = "#c8102e"   # primary red
ACCENT2 = "#ff3c5a"   # lighter red / totals highlight
TEXT    = "#f0f0f0"   # primary text
MUTED   = "#888888"   # labels / secondary text
SUCCESS = "#2ecc71"   # location on / saved states
WARNING = "#f39c12"   # caution states
HOVER   = "#2a2a2a"   # button hover

# ─────────────────────────────────────────────
# TYPOGRAPHY
# ─────────────────────────────────────────────
FONT_H1 = ("Georgia",  20, "bold")
FONT_H2 = ("Georgia",  14, "bold")
FONT_H3 = ("Georgia",  11, "bold")
FONT_B  = ("Consolas", 10)
FONT_SM = ("Consolas",  9)

# ─────────────────────────────────────────────
# DIMENSIONS
# ─────────────────────────────────────────────
SIDEBAR_W   = 220
TOOLBAR_H   = 56
WIN_W       = 1100
WIN_H       = 720
WIN_MIN_W   = 900
WIN_MIN_H   = 600
THUMB_W     = 220
THUMB_H     = 160
CAM_W       = 640
CAM_H       = 480

# ─────────────────────────────────────────────
# BRANDING
# ─────────────────────────────────────────────
APP_NAME     = "Slowbooks"
APP_SUBTITLE = "by Nick War Art"
WINDOW_TITLE = "Slowbooks — Nick War Art Expense Tracker"

# ─────────────────────────────────────────────
# CATEGORIES
# ─────────────────────────────────────────────
CATEGORIES = [
    "Tattoo Supplies",
    "Ink & Needles",
    "Studio Rent",
    "Equipment",
    "Convention / Show",
    "Travel & Mileage",
    "Marketing / Content",
    "Software & Subscriptions",
    "Meals & Entertainment",
    "Other",
]

# ─────────────────────────────────────────────
# TTK THEME
# Call apply_theme(root) once at app startup.
# ─────────────────────────────────────────────
def apply_theme(root: tk.Tk) -> None:
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
        arrowcolor=MUTED,
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

    style.configure("TSeparator", background=BORDER)
