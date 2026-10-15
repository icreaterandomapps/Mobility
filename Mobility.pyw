"""Mobility - a launcher for Windows admin, repair, network and power tools.

Double-click "Launch Mobility.bat" (or this file) to start.
"""
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mobility_tools as mt  # noqa: E402

# Windows 7 (Aero) palette
BG, PANEL, FG, MUTED = "#f0f0f0", "#ffffff", "#000000", "#6d6d6d"
TITLE, SEL, SEL_BORDER = "#1e395b", "#cfe3f9", "#7da2ce"
GLASS_TOP, GLASS_BOT, GLASS_LINE = "#e9f1fb", "#c9daf0", "#99b4d1"
FONT, FONT_B = ("Segoe UI", 9), ("Segoe UI", 9, "bold")
CAT_ORDER = ["System", "Administrative", "Storage", "Network", "Power & Mobility",
             "Repair", "Utilities", "Your Shortcuts", "Custom"]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mobility")
        self.geometry("960x640")
        self.minsize(780, 480)
        self.configure(bg=BG)
        self.settings = mt.load_settings()
        self.favs = set(self.settings.get("favorites", []))
        self.tools = mt.load_all_tools()
        self.view = []
        self.current_cat = "All"
        self._set_icons()
        self._load_ui_icons()
        self._style()
        self._build()
        self._refresh()
        self.after(300, self._auto_repair_icons)
        self.after(1000, self._tick)

    # ------------------------------------------------------------------ setup
    def _set_icons(self):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Mobility.Launcher")
        except Exception:
            pass
        ico = mt.asset("Res", "mobility.ico")
        png = mt.asset("Res", "mobility_64.png")
        self.logo = None
        try:
            self.logo = tk.PhotoImage(file=png)
            self.iconphoto(True, self.logo)
        except tk.TclError:
            pass
        try:
            self.iconbitmap(ico)
        except tk.TclError:
            pass

    def _load_ui_icons(self):
        """Small icons made from the Res folder icons (Res/ui/*.png)."""
        self.ui = {}
        for name in ("app", "storage", "admin", "folder", "god", "blank", "all", "fav", "system",
                     "network", "power", "repair", "utilities", "danger"):
            for px in (16, 20):
                try:
                    self.ui[(name, px)] = tk.PhotoImage(file=mt.asset("Res", "ui", f"{name}_{px}.png"))
                except tk.TclError:
                    self.ui[(name, px)] = None

    CAT_ICONS = {"All": "all", "Favorites": "fav", "System": "system", "Administrative": "admin",
                 "Storage": "storage", "Network": "network", "Power & Mobility": "power",
                 "Repair": "repair", "Utilities": "utilities", "Your Shortcuts": "folder",
                 "Custom": "folder"}

    def _cat_icon(self, cat):
        return self.ui.get((self.CAT_ICONS.get(cat, "blank"), 20))

    def _tool_icon(self, t):
        if t.confirm:
            name = "danger"          # risky action: reboot, network reset, deleting files
        elif t.name == "God Mode":
            name = "god"
        elif t.source != "builtin":
            name = "folder"
        else:
            name = self.CAT_ICONS.get(t.cat, "blank")
        return self.ui.get((name, 16))

    def _style(self):
        st = ttk.Style(self)
        for theme in ("vista", "xpnative", "clam"):  # native Windows look first
            try:
                st.theme_use(theme)
                break
            except tk.TclError:
                continue
        self.option_add("*Font", FONT)
        st.configure(".", font=FONT)
        st.configure("Treeview", rowheight=24, background=PANEL, fieldbackground=PANEL)
        st.configure("Treeview.Heading", font=FONT)
        st.configure("Default.TButton", font=FONT_B)

    def _build(self):
        # header: Aero "glass" band with the icon, like an Explorer title area
        self.head = tk.Canvas(self, height=76, bg=GLASS_TOP, highlightthickness=0, bd=0)
        self.head.pack(fill="x")
        self.head.bind("<Configure>", self._paint_glass)
        self.head.bind("<Button-3>", self._app_menu)
        x = 14
        if self.logo:
            self.head.create_image(14, 6, image=self.logo, anchor="nw")
            x = 14 + 64 + 12
        self.head.create_text(x, 24, text="Mobility", anchor="w", fill=TITLE, font=("Segoe UI", 18))
        self.info_id = self.head.create_text(x, 52, text=mt.system_summary(), anchor="w",
                                             fill=MUTED, font=FONT)

        # command bar: search + admin switch
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=10, pady=(8, 6))
        tk.Label(bar, text="Search:", bg=BG, font=FONT).pack(side="left", padx=(0, 6))
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *_: self._refresh())
        self.search = ttk.Entry(bar, textvariable=self.q)
        self.search.pack(side="left", fill="x", expand=True)
        self.admin_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Run as administrator", variable=self.admin_var).pack(side="left", padx=(14, 0))

        # status bar + buttons (packed before the body so it keeps its space)
        foot = tk.Frame(self, bg=BG, highlightthickness=1, highlightbackground="#d5d5d5")
        foot.pack(side="bottom", fill="x")
        self.status = tk.Label(foot, text="Double-click a tool, or press Enter.", bg=BG, fg=MUTED,
                               anchor="w", font=FONT)
        self.status.pack(side="left", fill="x", expand=True, padx=10, pady=8)
        ttk.Button(foot, text="Run as admin", command=lambda: self.run_selected(True)).pack(
            side="right", padx=(6, 10), pady=6)
        ttk.Button(foot, text="Launch", style="Default.TButton", command=self.run_selected).pack(
            side="right", pady=6)

        # body: navigation pane (left) + details list (right)
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.cats = ttk.Treeview(body, show="tree", selectmode="browse", height=10)
        self.cats.column("#0", width=190, stretch=False)
        self.cats.pack(side="left", fill="y", padx=(0, 8))
        self.cats.bind("<<TreeviewSelect>>", self._pick_cat)

        right = tk.Frame(body, bg="#828790", bd=0, highlightthickness=0)
        right.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(right, bg=PANEL)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.tree = ttk.Treeview(inner, columns=("desc", "kind"), selectmode="browse")
        self.tree.heading("#0", text="Name", anchor="w")
        self.tree.heading("desc", text="Description", anchor="w")
        self.tree.heading("kind", text="Type", anchor="w")
        self.tree.column("#0", width=260, stretch=False)
        self.tree.column("desc", width=420)
        self.tree.column("kind", width=80, stretch=False)
        sb = ttk.Scrollbar(inner, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self.run_selected())
        self.tree.bind("<Return>", lambda e: self.run_selected())
        self.tree.bind("<Button-3>", self._context)

        # context menu
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Run", command=self.run_selected)
        self.menu.add_command(label="Run as administrator", command=lambda: self.run_selected(True))
        self.menu.add_separator()
        self.menu.add_command(label="Add / remove favorite", command=self.toggle_fav)
        self.menu.add_command(label="Copy command", command=self.copy_cmd)
        self.menu.add_command(label="Remove custom tool", command=self.remove_custom,
                              image=self.ui.get(("danger", 16)) or "", compound="left")

        # shortcuts
        self.bind("<Control-f>", lambda e: (self.search.focus_set(), "break")[1])
        self.bind("<Escape>", lambda e: self.q.set(""))
        self.search.bind("<Down>", self._to_tree)
        self.search.bind("<Return>", self._search_enter)
        self.search.focus_set()
        self._fill_cats()

    # ------------------------------------------------------------------ data
    def _categories(self):
        # shortcuts you added have no tab of their own; they only appear under "All"
        present = {t.cat for t in self.tools} - {"Your Shortcuts"}
        ordered = [c for c in CAT_ORDER if c in present] + sorted(present - set(CAT_ORDER))
        return ["All", "Favorites"] + ordered

    def _fill_cats(self):
        names = self._categories()
        self.cats.delete(*self.cats.get_children())
        for i, c in enumerate(names):
            n = (len(self.tools) if c == "All" else len(self.favs & {t.name for t in self.tools})
                 if c == "Favorites" else sum(1 for t in self.tools if t.cat == c))
            self.cats.insert("", "end", iid=str(i), text=f" {c} ({n})",
                             image=self._cat_icon(c) or "")
        self.cats.selection_set(str(names.index(self.current_cat) if self.current_cat in names else 0))

    def _pick_cat(self, _e=None):
        sel = self.cats.selection()
        if sel:
            cat = self._categories()[int(sel[0])]
            if cat != self.current_cat:
                self.current_cat = cat
                self._refresh()

    def _refresh(self):
        needle = self.q.get().strip().lower()
        words = needle.split()
        rows = []
        for t in self.tools:
            if self.current_cat == "Favorites" and t.name not in self.favs:
                continue
            if self.current_cat not in ("All", "Favorites") and t.cat != self.current_cat:
                continue
            hay = f"{t.name} {t.desc} {t.cat} {t.exe} {t.args}".lower()
            if all(w in hay for w in words):
                rows.append(t)
        # when searching/All: favorites first
        rows.sort(key=lambda t: (t.name not in self.favs, ))
        self.view = rows
        self.tree.delete(*self.tree.get_children())
        for i, t in enumerate(rows):
            star = "★ " if t.name in self.favs else ""
            kind = "Admin" if t.admin else ("Custom" if t.source == "custom" else "")
            self.tree.insert("", "end", iid=str(i), text=f" {star}{t.name}", values=(t.desc, kind),
                             image=self._tool_icon(t) or "")
        if rows:
            self.tree.selection_set("0")
        self.status.config(text=f"{len(rows)} tool{'s' if len(rows) != 1 else ''}")

    def _selected(self):
        sel = self.tree.selection()
        return self.view[int(sel[0])] if sel else None

    def _to_tree(self, _e=None):
        if self.view:
            self.tree.focus_set()
            sel = self.tree.selection()
            self.tree.focus(sel[0] if sel else "0")
        return "break"

    def _search_enter(self, _e=None):
        if self.view:
            self.run_selected()
        return "break"

    def _context(self, e):
        row = self.tree.identify_row(e.y)
        if row:
            self.tree.selection_set(row)
            self.menu.tk_popup(e.x_root, e.y_root)

    def _app_menu(self, e):
        """Right-click the header: the options that used to live in the File / Help menus."""
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Add custom tool...", command=self.add_tool_dialog)
        m.add_command(label="Create desktop shortcut", command=self.make_shortcut)
        m.add_command(label="Repair folder icons", command=self.repair_icons)
        m.add_command(label="Open this folder",
                      command=lambda: os.startfile(mt.ROOT) if mt.IS_WIN else None)
        m.add_separator()
        m.add_command(label="About Mobility", command=self.about)
        m.add_command(label="Exit", command=self.destroy)
        m.tk_popup(e.x_root, e.y_root)

    def _paint_glass(self, e):
        c = self.head
        c.delete("glass")
        h = e.height
        r1, g1, b1 = (int(GLASS_TOP[i:i + 2], 16) for i in (1, 3, 5))
        r2, g2, b2 = (int(GLASS_BOT[i:i + 2], 16) for i in (1, 3, 5))
        for y in range(h):
            t = y / max(1, h - 1)
            col = "#%02x%02x%02x" % (int(r1 + (r2 - r1) * t), int(g1 + (g2 - g1) * t), int(b1 + (b2 - b1) * t))
            c.create_line(0, y, e.width, y, fill=col, tags="glass")
        c.create_line(0, h - 1, e.width, h - 1, fill=GLASS_LINE, tags="glass")
        c.tag_lower("glass")

    def _tick(self):
        self.head.itemconfig(self.info_id, text=mt.system_summary())
        self.after(30000, self._tick)

    # ------------------------------------------------------------------ actions
    def run_selected(self, force_admin=False):
        t = self._selected()
        if not t:
            return
        if t.confirm and not messagebox.askyesno("Mobility", t.confirm, parent=self):
            return
        try:
            self.status.config(text=mt.launch(t, force_admin or self.admin_var.get()))
        except OSError as e:
            self.status.config(text=str(e))
            messagebox.showerror("Mobility", str(e), parent=self)

    def toggle_fav(self):
        t = self._selected()
        if not t:
            return
        self.favs.symmetric_difference_update({t.name})
        self.settings["favorites"] = sorted(self.favs)
        mt.save_settings(self.settings)
        self._fill_cats()
        self._refresh()

    def copy_cmd(self):
        t = self._selected()
        if t:
            self.clipboard_clear()
            self.clipboard_append(t.command)
            self.status.config(text="Copied: " + t.command)

    def remove_custom(self):
        t = self._selected()
        if not t or t.source != "custom":
            self.status.config(text="Only custom tools can be removed.")
            return
        self.tools.remove(t)
        mt.save_custom(self.tools)
        self._fill_cats()
        self._refresh()

    def add_tool_dialog(self):
        win = tk.Toplevel(self)
        win.title("Add custom tool")
        win.configure(bg=BG)
        win.transient(self)
        win.resizable(False, False)
        fields = {}
        rows = [("Name", "name"), ("Program / file / folder / URL", "exe"),
                ("Arguments (optional)", "args"), ("Description", "desc")]
        for i, (label, key) in enumerate(rows):
            tk.Label(win, text=label, bg=BG, fg=MUTED).grid(row=i, column=0, sticky="w", padx=14, pady=(10, 0))
            v = tk.StringVar()
            ttk.Entry(win, textvariable=v, width=48).grid(row=i, column=1, padx=14, pady=(10, 0))
            fields[key] = v
        ttk.Button(win, text="Browse...", command=lambda: fields["exe"].set(
            filedialog.askopenfilename(parent=win) or fields["exe"].get())).grid(row=1, column=2, padx=(0, 14), pady=(10, 0))
        tk.Label(win, text="Category", bg=BG, fg=MUTED).grid(row=4, column=0, sticky="w", padx=14, pady=(10, 0))
        cat = tk.StringVar(value="Custom")
        ttk.Combobox(win, textvariable=cat, values=self._categories()[2:], width=45).grid(
            row=4, column=1, padx=14, pady=(10, 0))
        adm = tk.BooleanVar()
        ttk.Checkbutton(win, text="Always run as administrator", variable=adm).grid(
            row=5, column=1, sticky="w", padx=14, pady=10)

        def save():
            name, exe = fields["name"].get().strip(), fields["exe"].get().strip()
            if not name or not exe:
                messagebox.showwarning("Mobility", "Name and program are required.", parent=win)
                return
            self.tools.append(mt.Tool(name, cat.get().strip() or "Custom", fields["desc"].get().strip(),
                                      exe, fields["args"].get().strip(), adm.get(), source="custom"))
            try:
                mt.save_custom(self.tools)
            except OSError as e:
                messagebox.showerror("Mobility", f"Could not save: {e}", parent=win)
            win.destroy()
            self._fill_cats()
            self._refresh()

        ttk.Button(win, text="Add tool", style="Default.TButton", command=save).grid(
            row=6, column=1, sticky="e", padx=14, pady=(0, 14))
        win.grab_set()

    def make_shortcut(self):
        try:
            p = mt.create_desktop_shortcut()
            self.status.config(text=f"Shortcut created: {p}")
        except OSError as e:
            messagebox.showerror("Mobility", str(e), parent=self)

    def repair_icons(self):
        notes = mt.repair_folder_icons()
        messagebox.showinfo("Folder icons", "\n".join(notes) +
                            "\n\nIf an icon still looks old, press F5 in Explorer or restart it "
                            "(Repair > Restart Explorer).", parent=self)

    def _auto_repair_icons(self):
        try:
            if mt.icons_need_repair():
                mt.repair_folder_icons()
                self.status.config(text="Folder icons re-pointed to this location.")
        except Exception:
            pass

    def about(self):
        messagebox.showinfo("Mobility", "Mobility - Windows tools launcher\n\n"
                            f"{len(self.tools)} tools loaded.\n"
                            "Drop your own shortcuts or programs in the 'Custom Tools' folder "
                            "and they appear under 'All'.\n\n"
                            "Ctrl+F search - Enter run - right-click a tool for favorites,\nright-click the blue header for more options.", parent=self)


if __name__ == "__main__":
    App().mainloop()
