"""
receipt_tracker.py — Slowbooks
Main application entry point.

Run:  python receipt_tracker.py
Deps: pip install pillow opencv-python requests

All app data (receipts.db, images/) is stored alongside this file.
"""

import csv
import datetime
import os
import shutil
import sqlite3
import threading
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from styles import (
    ACCENT, ACCENT2, APP_NAME, APP_SUBTITLE,
    BG, BORDER, CAM_H, CAM_W, CARD,
    CATEGORIES, FONT_B, FONT_H1, FONT_H2, FONT_H3,
    FONT_SM, MUTED, PANEL, SUCCESS, TEXT, THUMB_H, THUMB_W,
    SIDEBAR_W, TOOLBAR_H, WARNING, WIN_H, WIN_MIN_H, WIN_MIN_W,
    WIN_W, WINDOW_TITLE, apply_theme,
)

# ─────────────────────────────────────────────
# OPTIONAL DEPENDENCIES
# ─────────────────────────────────────────────
try:
    import cv2
    CAMERA_OK = True
except ImportError:
    CAMERA_OK = False

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

# ─────────────────────────────────────────────
# PATHS  (everything lives next to this file)
# ─────────────────────────────────────────────
APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "receipts.db"
IMG_DIR = APP_DIR / "images"
IMG_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────
def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                date          TEXT    NOT NULL,
                merchant      TEXT,
                amount        REAL,
                category      TEXT,
                notes         TEXT,
                image_path    TEXT,
                latitude      REAL,
                longitude     REAL,
                location_name TEXT,
                created_at    TEXT
            )
        """)
        conn.commit()


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def insert_receipt(data: dict) -> int:
    with _conn() as conn:
        cur = conn.execute("""
            INSERT INTO receipts
                (date, merchant, amount, category, notes,
                 image_path, latitude, longitude, location_name, created_at)
            VALUES
                (:date, :merchant, :amount, :category, :notes,
                 :image_path, :latitude, :longitude, :location_name, :created_at)
        """, data)
        conn.commit()
        return cur.lastrowid


def update_receipt(rid: int, data: dict) -> None:
    with _conn() as conn:
        conn.execute("""
            UPDATE receipts
            SET date=:date, merchant=:merchant, amount=:amount,
                category=:category, notes=:notes, image_path=:image_path,
                latitude=:latitude, longitude=:longitude,
                location_name=:location_name
            WHERE id=:id
        """, {**data, "id": rid})
        conn.commit()


def delete_receipt(rid: int) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM receipts WHERE id=?", (rid,))
        conn.commit()


_COLS = ["id", "date", "merchant", "amount", "category", "notes",
         "image_path", "latitude", "longitude", "location_name", "created_at"]


def fetch_receipts(month=None, year=None, category=None, search="") -> list[dict]:
    query = "SELECT * FROM receipts WHERE 1=1"
    params: list = []

    if month and year:
        query += " AND strftime('%m', date)=? AND strftime('%Y', date)=?"
        params += [f"{month:02d}", str(year)]

    if category and category != "All":
        query += " AND category=?"
        params.append(category)

    if search:
        query += " AND (merchant LIKE ? OR notes LIKE ? OR category LIKE ?)"
        like = f"%{search}%"
        params += [like, like, like]

    query += " ORDER BY date DESC"

    with _conn() as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(zip(_COLS, r)) for r in rows]


def monthly_summary(year: int) -> list[tuple]:
    with _conn() as conn:
        return conn.execute("""
            SELECT strftime('%m', date) AS month, category, SUM(amount)
            FROM receipts
            WHERE strftime('%Y', date)=?
            GROUP BY month, category
            ORDER BY month
        """, (str(year),)).fetchall()


# ─────────────────────────────────────────────
# LOCATION TRACKER
# ─────────────────────────────────────────────
class LocationTracker:
    def __init__(self):
        self.enabled = False
        self.current: dict = {"lat": None, "lon": None, "name": ""}
        self._thread: threading.Thread | None = None
        self._stop = False

    def toggle(self):
        self.enabled = not self.enabled
        if self.enabled:
            self._stop = False
            self._thread = threading.Thread(target=self._poll, daemon=True)
            self._thread.start()
        else:
            self._stop = True
            self.current = {"lat": None, "lon": None, "name": ""}

    def _poll(self):
        while not self._stop:
            self._fetch()
            threading.Event().wait(30)

    def _fetch(self):
        if not REQUESTS_OK:
            return
        try:
            r = requests.get("http://ip-api.com/json/", timeout=5)
            if r.status_code == 200:
                d = r.json()
                self.current = {
                    "lat":  d.get("lat"),
                    "lon":  d.get("lon"),
                    "name": f"{d.get('city', '')}, {d.get('regionName', '')}",
                }
        except Exception:
            pass

    def get(self) -> dict:
        return self.current.copy()


location_tracker = LocationTracker()


# ─────────────────────────────────────────────
# CAMERA WINDOW
# ─────────────────────────────────────────────
class CameraWindow(tk.Toplevel):
    def __init__(self, parent, on_capture):
        super().__init__(parent)
        self.title("Capture Receipt")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.on_capture = on_capture
        self.cap = None
        self.running = False
        self._after_id = None

        if not CAMERA_OK or not PIL_OK:
            tk.Label(
                self,
                text="Camera unavailable.\npip install opencv-python pillow",
                fg=WARNING, bg=BG, font=FONT_B, padx=40, pady=40,
            ).pack()
            tk.Button(self, text="Close", command=self.destroy,
                      bg=CARD, fg=TEXT, font=FONT_B,
                      relief=tk.FLAT, pady=8).pack(pady=10)
            return

        self._build_ui()
        self._start_camera()

    def _build_ui(self):
        self.canvas = tk.Canvas(self, width=CAM_W, height=CAM_H,
                                bg="#000", highlightthickness=0)
        self.canvas.pack(padx=10, pady=10)
        row = tk.Frame(self, bg=BG)
        row.pack(pady=8)
        _btn(row, "📷  CAPTURE", self._capture, ACCENT, FONT_H3).pack(side=tk.LEFT, padx=6)
        _btn(row, "Cancel",     self.destroy,   CARD,   FONT_H3).pack(side=tk.LEFT, padx=6)

    def _start_camera(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror("Camera Error", "No camera found.", parent=self)
            self.destroy()
            return
        self.running = True
        self._next_frame()

    def _next_frame(self):
        if not self.running:
            return
        ret, frame = self.cap.read()
        if ret:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            photo = ImageTk.PhotoImage(Image.fromarray(rgb).resize((CAM_W, CAM_H)))
            self.canvas.create_image(0, 0, anchor=tk.NW, image=photo)
            self.canvas._photo = photo  # keep reference
        self._after_id = self.after(33, self._next_frame)

    def _capture(self):
        if not self.cap:
            return
        ret, frame = self.cap.read()
        if ret:
            fname = f"receipt_{datetime.datetime.now():%Y%m%d_%H%M%S}.jpg"
            path  = IMG_DIR / fname
            cv2.imwrite(str(path), frame)
            self._cleanup()
            self.on_capture(str(path))
            self.destroy()

    def _cleanup(self):
        self.running = False
        if self._after_id:
            self.after_cancel(self._after_id)
        if self.cap:
            self.cap.release()

    def destroy(self):
        self._cleanup()
        super().destroy()


# ─────────────────────────────────────────────
# RECEIPT FORM
# ─────────────────────────────────────────────
class ReceiptForm(tk.Toplevel):
    def __init__(self, parent, on_save, receipt: dict | None = None):
        super().__init__(parent)
        self.title("New Receipt" if not receipt else "Edit Receipt")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.on_save    = on_save
        self.receipt    = receipt
        self.image_path = tk.StringVar(value=(receipt or {}).get("image_path", ""))
        self._build()
        if receipt:
            self._populate(receipt)
        self.grab_set()

    # ── layout ────────────────────────────────
    def _build(self):
        tk.Frame(self, bg=ACCENT, height=4).pack(fill=tk.X)
        tk.Label(self, text="RECEIPT ENTRY", font=FONT_H2,
                 fg=TEXT, bg=BG, pady=14).pack()

        body = tk.Frame(self, bg=BG, padx=30, pady=10)
        body.pack(fill=tk.BOTH)
        body.columnconfigure(0, weight=1)

        def lbl(text, row):
            tk.Label(body, text=text, font=FONT_SM, fg=MUTED,
                     bg=BG, anchor="w").grid(
                row=row * 2, column=0, columnspan=2,
                sticky="w", pady=(8, 0))

        def ent(var, row):
            e = tk.Entry(body, textvariable=var, bg=CARD, fg=TEXT,
                         font=FONT_B, relief=tk.FLAT, insertbackground=TEXT,
                         highlightthickness=1, highlightbackground=BORDER, bd=4)
            e.grid(row=row * 2 + 1, column=0, columnspan=2,
                   sticky="ew", pady=(2, 0))
            return e

        self.date_var     = tk.StringVar(value=datetime.date.today().isoformat())
        self.merchant_var = tk.StringVar()
        self.amount_var   = tk.StringVar()
        self.cat_var      = tk.StringVar(value=CATEGORIES[0])

        lbl("Date", 0);            ent(self.date_var,     0)
        lbl("Merchant / Vendor", 1); ent(self.merchant_var, 1)
        lbl("Amount ($)", 2);       ent(self.amount_var,   2)

        lbl("Category", 3)
        ttk.Combobox(body, textvariable=self.cat_var, values=CATEGORIES,
                     state="readonly", font=FONT_B
                     ).grid(row=7, column=0, columnspan=2,
                            sticky="ew", pady=(2, 0))

        tk.Label(body, text="Notes / Memo", font=FONT_SM,
                 fg=MUTED, bg=BG, anchor="w").grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.notes_t = tk.Text(
            body, height=3, bg=CARD, fg=TEXT, font=FONT_B,
            relief=tk.FLAT, insertbackground=TEXT, bd=0,
            highlightthickness=1, highlightbackground=BORDER)
        self.notes_t.grid(row=9, column=0, columnspan=2,
                          sticky="ew", pady=(2, 0))

        # Image row
        img_f = tk.Frame(body, bg=BG)
        img_f.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        tk.Label(img_f, text="Receipt Image", font=FONT_SM,
                 fg=MUTED, bg=BG).pack(anchor="w")
        btn_row = tk.Frame(img_f, bg=BG)
        btn_row.pack(fill=tk.X, pady=4)
        _small_btn(btn_row, "📷 Camera",      self._open_camera).pack(side=tk.LEFT, padx=(0, 6))
        _small_btn(btn_row, "📁 Upload File", self._upload_file).pack(side=tk.LEFT)
        tk.Label(img_f, textvariable=self.image_path,
                 font=FONT_SM, fg=SUCCESS, bg=BG,
                 wraplength=380, anchor="w").pack(anchor="w")
        self.thumb_lbl = tk.Label(img_f, bg=BG)
        self.thumb_lbl.pack(pady=4)
        if self.image_path.get():
            self._show_thumb(self.image_path.get())

        # Location status
        loc = location_tracker.get()
        loc_text = (loc["name"] if loc["name"] else
                    ("Tracking ON — fetching…" if location_tracker.enabled
                     else "Location OFF"))
        tk.Label(body, text=f"📍 {loc_text}", font=FONT_SM,
                 fg=SUCCESS if location_tracker.enabled else MUTED,
                 bg=BG).grid(row=11, column=0, columnspan=2,
                              sticky="w", pady=(10, 0))

        # Buttons
        foot = tk.Frame(self, bg=BG, pady=16)
        foot.pack()
        tk.Button(foot, text="  SAVE RECEIPT  ", command=self._save,
                  bg=ACCENT, fg=TEXT, font=FONT_H3,
                  relief=tk.FLAT, padx=20, pady=10,
                  cursor="hand2").pack(side=tk.LEFT, padx=8)
        tk.Button(foot, text="Cancel", command=self.destroy,
                  bg=CARD, fg=MUTED, font=FONT_B,
                  relief=tk.FLAT, padx=16, pady=10,
                  cursor="hand2").pack(side=tk.LEFT, padx=8)

    def _open_camera(self):
        CameraWindow(self, self._on_captured)

    def _upload_file(self):
        path = filedialog.askopenfilename(
            parent=self,
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp"), ("All", "*.*")],
        )
        if path:
            dest = IMG_DIR / Path(path).name
            shutil.copy2(path, dest)
            self.image_path.set(str(dest))
            self._show_thumb(str(dest))

    def _on_captured(self, path: str):
        self.image_path.set(path)
        self._show_thumb(path)

    def _show_thumb(self, path: str):
        if not PIL_OK or not os.path.exists(path):
            return
        try:
            img = Image.open(path)
            img.thumbnail((THUMB_W, THUMB_H))
            self._thumb = ImageTk.PhotoImage(img)
            self.thumb_lbl.configure(image=self._thumb)
        except Exception:
            pass

    def _populate(self, r: dict):
        self.date_var.set(r.get("date", ""))
        self.merchant_var.set(r.get("merchant", "") or "")
        self.amount_var.set(str(r.get("amount", "") or ""))
        self.cat_var.set(r.get("category", CATEGORIES[0]) or CATEGORIES[0])
        if r.get("notes"):
            self.notes_t.insert("1.0", r["notes"])

    def _save(self):
        raw = self.amount_var.get().replace("$", "").strip()
        try:
            amount = float(raw) if raw else 0.0
        except ValueError:
            messagebox.showerror("Error", "Amount must be a number.", parent=self)
            return

        loc = (location_tracker.get() if location_tracker.enabled
               else {"lat": None, "lon": None, "name": ""})

        data = {
            "date":          self.date_var.get(),
            "merchant":      self.merchant_var.get(),
            "amount":        amount,
            "category":      self.cat_var.get(),
            "notes":         self.notes_t.get("1.0", tk.END).strip(),
            "image_path":    self.image_path.get(),
            "latitude":      loc["lat"],
            "longitude":     loc["lon"],
            "location_name": loc["name"],
            "created_at":    datetime.datetime.now().isoformat(),
        }

        if self.receipt:
            update_receipt(self.receipt["id"], data)
        else:
            insert_receipt(data)

        self.on_save()
        self.destroy()


# ─────────────────────────────────────────────
# WIDGET HELPERS
# ─────────────────────────────────────────────
def _btn(parent, text, cmd, bg, font=FONT_B, **kw):
    return tk.Button(parent, text=text, command=cmd,
                     bg=bg, fg=TEXT, font=font,
                     relief=tk.FLAT, cursor="hand2",
                     activebackground=BORDER, activeforeground=TEXT,
                     **kw)


def _small_btn(parent, text, cmd):
    return _btn(parent, text, cmd, CARD, FONT_SM, padx=10, pady=5)


# ─────────────────────────────────────────────
# MAIN APPLICATION
# ─────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(WINDOW_TITLE)
        self.configure(bg=BG)
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.minsize(WIN_MIN_W, WIN_MIN_H)
        init_db()
        apply_theme(self)
        self._build()
        self.load_receipts()

    # ── layout ────────────────────────────────
    def _build(self):
        self._build_sidebar()
        self._build_main()

    def _build_sidebar(self):
        sb = tk.Frame(self, bg=PANEL, width=SIDEBAR_W)
        sb.pack(side=tk.LEFT, fill=tk.Y)
        sb.pack_propagate(False)

        brand = tk.Frame(sb, bg=PANEL, pady=20)
        brand.pack(fill=tk.X)
        tk.Label(brand, text=APP_NAME, font=("Georgia", 18, "bold"),
                 fg=ACCENT, bg=PANEL).pack()
        tk.Label(brand, text=APP_SUBTITLE, font=FONT_SM,
                 fg=MUTED, bg=PANEL).pack()

        ttk.Separator(sb, orient="horizontal").pack(fill=tk.X, padx=14, pady=4)

        nav = [
            ("📋  Receipts",        self._show_receipts),
            ("📊  Monthly Summary", self._show_summary),
            ("📤  Export CSV",      self._export_csv),
        ]
        for label, cmd in nav:
            tk.Button(sb, text=label, command=cmd,
                      bg=PANEL, fg=TEXT, font=FONT_B,
                      relief=tk.FLAT, anchor="w",
                      padx=20, pady=10, cursor="hand2",
                      activebackground=CARD,
                      activeforeground=ACCENT).pack(fill=tk.X)

        ttk.Separator(sb, orient="horizontal").pack(fill=tk.X, padx=14, pady=12)

        self._loc_text = tk.StringVar(value="📍 Location: OFF")
        self._loc_btn = tk.Button(sb, textvariable=self._loc_text,
                                   command=self._toggle_location,
                                   bg=CARD, fg=MUTED, font=FONT_SM,
                                   relief=tk.FLAT, padx=16, pady=8,
                                   cursor="hand2", wraplength=180)
        self._loc_btn.pack(fill=tk.X, padx=14, pady=4)

        self._loc_display = tk.Label(sb, text="", font=FONT_SM,
                                      fg=SUCCESS, bg=PANEL,
                                      wraplength=190, justify=tk.LEFT, padx=14)
        self._loc_display.pack(anchor="w")

    def _build_main(self):
        main = tk.Frame(self, bg=BG)
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_toolbar(main)
        self._receipt_frame = tk.Frame(main, bg=BG)
        self._summary_frame = tk.Frame(main, bg=BG)
        self._build_receipt_view()
        self._build_summary_view()
        self._show_receipts()

    def _build_toolbar(self, parent):
        tb = tk.Frame(parent, bg=PANEL, height=TOOLBAR_H)
        tb.pack(fill=tk.X)
        tb.pack_propagate(False)

        _btn(tb, "＋  NEW RECEIPT", self._new_receipt, ACCENT, FONT_H3,
             padx=20, pady=10).pack(side=tk.LEFT, padx=14, pady=8)

        tk.Label(tb, text="Month:", fg=MUTED, bg=PANEL,
                 font=FONT_SM).pack(side=tk.LEFT, padx=(20, 4))
        self._month_var = tk.StringVar(value="All")
        months = ["All"] + [datetime.date(2000, m, 1).strftime("%B") for m in range(1, 13)]
        ttk.Combobox(tb, textvariable=self._month_var, values=months,
                     width=10, state="readonly",
                     font=FONT_SM).pack(side=tk.LEFT)

        tk.Label(tb, text="Category:", fg=MUTED, bg=PANEL,
                 font=FONT_SM).pack(side=tk.LEFT, padx=(12, 4))
        self._cat_filter = tk.StringVar(value="All")
        ttk.Combobox(tb, textvariable=self._cat_filter,
                     values=["All"] + CATEGORIES,
                     width=18, state="readonly",
                     font=FONT_SM).pack(side=tk.LEFT)

        tk.Label(tb, text="Search:", fg=MUTED, bg=PANEL,
                 font=FONT_SM).pack(side=tk.LEFT, padx=(12, 4))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self.load_receipts())
        tk.Entry(tb, textvariable=self._search_var, bg=CARD, fg=TEXT,
                 font=FONT_SM, relief=tk.FLAT, width=14,
                 insertbackground=TEXT,
                 highlightthickness=1,
                 highlightbackground=BORDER).pack(side=tk.LEFT)

        _btn(tb, "Filter", self.load_receipts, CARD, FONT_SM,
             padx=12, pady=6).pack(side=tk.LEFT, padx=8)

        self._total_var = tk.StringVar(value="Total: $0.00")
        tk.Label(tb, textvariable=self._total_var,
                 font=FONT_H3, fg=ACCENT2, bg=PANEL).pack(side=tk.RIGHT, padx=20)

    # ── receipt table ──────────────────────────
    def _build_receipt_view(self):
        cols   = ("date", "merchant", "amount", "category", "location", "notes")
        widths = {"date": 100, "merchant": 200, "amount": 90,
                  "category": 160, "location": 160, "notes": 200}
        heads  = {"date": "Date", "merchant": "Merchant", "amount": "Amount",
                  "category": "Category", "location": "Location", "notes": "Notes"}

        self._tree = ttk.Treeview(self._receipt_frame, columns=cols,
                                   show="headings", selectmode="browse")
        for col in cols:
            self._tree.heading(col, text=heads[col])
            self._tree.column(col, width=widths[col], anchor="w")

        vsb = ttk.Scrollbar(self._receipt_frame, orient="vertical",
                             command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                        padx=(10, 0), pady=10)
        vsb.pack(side=tk.LEFT, fill=tk.Y, pady=10)

        self._ctx = tk.Menu(self, tearoff=0, bg=CARD, fg=TEXT,
                             activebackground=ACCENT, font=FONT_SM)
        self._ctx.add_command(label="✏️  Edit",       command=self._edit_selected)
        self._ctx.add_command(label="🖼  View Image", command=self._view_image)
        self._ctx.add_separator()
        self._ctx.add_command(label="🗑  Delete",     command=self._delete_selected)

        self._tree.bind("<Button-3>",  self._show_ctx)
        self._tree.bind("<Double-1>",  lambda e: self._edit_selected())
        self._row_data: dict = {}

    # ── summary chart ──────────────────────────
    def _build_summary_view(self):
        tk.Label(self._summary_frame, text="MONTHLY SUMMARY",
                 font=FONT_H1, fg=TEXT, bg=BG, pady=20).pack()

        self._yr_var = tk.StringVar(value=str(datetime.date.today().year))
        yr_row = tk.Frame(self._summary_frame, bg=BG)
        yr_row.pack()
        tk.Label(yr_row, text="Year:", fg=MUTED, bg=BG,
                 font=FONT_SM).pack(side=tk.LEFT)
        years = [str(y) for y in range(datetime.date.today().year,
                                        datetime.date.today().year - 6, -1)]
        ttk.Combobox(yr_row, textvariable=self._yr_var, values=years,
                     width=6, state="readonly").pack(side=tk.LEFT, padx=6)
        _btn(yr_row, "Refresh", self._draw_summary, CARD, FONT_SM,
             padx=10, pady=4).pack(side=tk.LEFT)

        self._sum_canvas = tk.Canvas(self._summary_frame, bg=BG,
                                      highlightthickness=0)
        self._sum_canvas.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def _draw_summary(self):
        c = self._sum_canvas
        c.delete("all")
        year = int(self._yr_var.get())
        rows = monthly_summary(year)

        if not rows:
            c.create_text(400, 200, text="No data for this year",
                          fill=MUTED, font=FONT_H2)
            return

        month_totals: dict[int, float] = {}
        for m, _cat, total in rows:
            mn = int(m)
            month_totals[mn] = month_totals.get(mn, 0) + total

        W = c.winfo_width() or 800
        H = c.winfo_height() or 400
        pl, pr, pt, pb = 70, 30, 40, 60
        max_val = max(month_totals.values()) or 1
        gap    = (W - pl - pr) / 12
        bar_w  = gap * 0.6

        month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                       "Jul","Aug","Sep","Oct","Nov","Dec"]
        bar_colors  = [ACCENT, "#e84060", "#ff6080", ACCENT2,
                       "#c0102a", "#ff3040", "#e02040", ACCENT,
                       ACCENT2, "#ff5060", "#d01030", "#e83050"]

        c.create_line(pl, pt, pl, H - pb, fill=BORDER)
        c.create_line(pl, H - pb, W - pr, H - pb, fill=BORDER)

        for i in range(5):
            y   = pt + (H - pt - pb) * i / 4
            val = max_val * (1 - i / 4)
            c.create_line(pl, y, W - pr, y, fill=BORDER, dash=(4, 6))
            c.create_text(pl - 8, y, text=f"${val:,.0f}",
                          anchor="e", fill=MUTED, font=FONT_SM)

        for i, mn in enumerate(range(1, 13)):
            xc  = pl + gap * i + gap / 2
            val = month_totals.get(mn, 0)
            bh  = (val / max_val) * (H - pt - pb)
            x0, x1 = xc - bar_w / 2, xc + bar_w / 2
            y0, y1 = H - pb - bh, H - pb

            if val > 0:
                c.create_rectangle(x0, y0, x1, y1,
                                   fill=bar_colors[i], outline="")
                c.create_text(xc, y0 - 6, text=f"${val:,.0f}",
                              fill=TEXT, font=("Consolas", 8), anchor="s")

            c.create_text(xc, H - pb + 14, text=month_names[i],
                          fill=MUTED, font=FONT_SM, anchor="n")

        total = sum(month_totals.values())
        c.create_text(W - pr, pt - 10, text=f"Year Total: ${total:,.2f}",
                      fill=ACCENT2, font=FONT_H3, anchor="e")

    # ── view switching ─────────────────────────
    def _show_receipts(self):
        self._summary_frame.pack_forget()
        self._receipt_frame.pack(fill=tk.BOTH, expand=True)

    def _show_summary(self):
        self._receipt_frame.pack_forget()
        self._summary_frame.pack(fill=tk.BOTH, expand=True)
        self.after(50, self._draw_summary)

    # ── data loading ───────────────────────────
    def load_receipts(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._row_data.clear()

        month_str = self._month_var.get()
        month_num = None
        if month_str != "All":
            for m in range(1, 13):
                if datetime.date(2000, m, 1).strftime("%B") == month_str:
                    month_num = m
                    break

        receipts = fetch_receipts(
            month=month_num,
            year=datetime.date.today().year if month_num else None,
            category=self._cat_filter.get(),
            search=self._search_var.get().strip(),
        )

        total = 0.0
        for r in receipts:
            total += r["amount"] or 0
            iid = self._tree.insert("", tk.END, values=(
                r["date"],
                r["merchant"] or "—",
                f"${r['amount']:,.2f}" if r["amount"] else "$0.00",
                r["category"] or "—",
                r["location_name"] or "—",
                (r["notes"] or "")[:50],
            ))
            self._row_data[iid] = r

        self._total_var.set(f"Total: ${total:,.2f}")

    # ── receipt actions ────────────────────────
    def _new_receipt(self):
        ReceiptForm(self, self.load_receipts)

    def _edit_selected(self):
        sel = self._tree.selection()
        if sel:
            ReceiptForm(self, self.load_receipts,
                        receipt=self._row_data[sel[0]])

    def _delete_selected(self):
        sel = self._tree.selection()
        if not sel:
            return
        r = self._row_data[sel[0]]
        if messagebox.askyesno("Delete",
                               f"Delete receipt from {r['merchant']}?",
                               parent=self):
            delete_receipt(r["id"])
            self.load_receipts()

    def _view_image(self):
        sel = self._tree.selection()
        if not sel:
            return
        path = self._row_data[sel[0]].get("image_path", "")
        if not path or not os.path.exists(path):
            messagebox.showinfo("No Image",
                                "No image attached to this receipt.",
                                parent=self)
            return
        if PIL_OK:
            win = tk.Toplevel(self)
            win.title("Receipt Image")
            win.configure(bg=BG)
            img = Image.open(path)
            img.thumbnail((700, 900))
            photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(win, image=photo, bg=BG)
            lbl.image = photo
            lbl.pack(padx=10, pady=10)
        else:
            os.startfile(path) if os.name == "nt" else os.system(f"open '{path}'")

    def _show_ctx(self, event):
        iid = self._tree.identify_row(event.y)
        if iid:
            self._tree.selection_set(iid)
            self._ctx.post(event.x_root, event.y_root)

    # ── location ───────────────────────────────
    def _toggle_location(self):
        location_tracker.toggle()
        if location_tracker.enabled:
            self._loc_btn.configure(bg=ACCENT, fg=TEXT)
            self._loc_text.set("📍 Location: ON")
            self._loc_display.configure(text="Fetching…")
            self.after(2000, self._update_loc_display)
        else:
            self._loc_btn.configure(bg=CARD, fg=MUTED)
            self._loc_text.set("📍 Location: OFF")
            self._loc_display.configure(text="")

    def _update_loc_display(self):
        loc = location_tracker.get()
        self._loc_display.configure(text=loc["name"] or "Location unknown")
        if location_tracker.enabled:
            self.after(30_000, self._update_loc_display)

    # ── export ─────────────────────────────────
    def _export_csv(self):
        default = f"slowbooks_{datetime.date.today().isoformat()}.csv"
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=default,
        )
        if not path:
            return
        receipts = fetch_receipts()
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_COLS)
            writer.writeheader()
            writer.writerows(receipts)
        messagebox.showinfo("Exported",
                            f"Saved {len(receipts)} receipts to:\n{path}",
                            parent=self)


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    App().mainloop()
