#!/usr/bin/env python3
"""
aThemeArt Security Firewall Defense
Modern Windows GUI for the Security-Firewall-Defense PowerShell toolkit.

Developed by: aThemeArt
Website: https://athemeart.com
Author: Saiful Islam
"""
from __future__ import annotations

import sys
import threading
import traceback
from pathlib import Path

# Ensure src is on path when running as script
if getattr(sys, "frozen", False):
    # PyInstaller
    BASE = Path(sys.executable).parent
else:
    BASE = Path(__file__).resolve().parent
    sys.path.insert(0, str(BASE))

import customtkinter as ctk
from tkinter import messagebox, filedialog
from tkinter import ttk
import tkinter as tk

from core.admin import require_admin, is_admin
from core.firewall import FirewallManager, AllowedApp
from core.paths import APP_DIR, DATA_DIR, LOG_FILE

# Branding
APP_NAME = "Security Firewall Defense"
APP_VERSION = "1.0.0"
DEVELOPER = "aThemeArt"
WEBSITE = "https://athemeart.com"
AUTHOR = "Saiful Islam"

# Appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class StatusCard(ctk.CTkFrame):
    def __init__(self, master, title: str, **kwargs):
        super().__init__(master, **kwargs)
        self.title_label = ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=13, weight="bold"))
        self.title_label.pack(anchor="w", padx=12, pady=(10, 2))
        self.value_label = ctk.CTkLabel(self, text="—", font=ctk.CTkFont(size=20, weight="bold"))
        self.value_label.pack(anchor="w", padx=12, pady=(0, 10))

    def set_value(self, text: str, color: str | None = None):
        self.value_label.configure(text=text)
        if color:
            self.value_label.configure(text_color=color)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME}  •  {DEVELOPER}")
        self.geometry("1180x720")
        self.minsize(980, 640)

        self.fw = FirewallManager()
        self._monitor_running = False
        self._monitor_thread: threading.Thread | None = None

        self._build_ui()
        self.after(200, self.refresh_status)
        self.after(500, self._start_monitor)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, height=64, corner_radius=0)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        title_lbl = ctk.CTkLabel(
            header,
            text=f"🛡  {APP_NAME}",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        title_lbl.pack(side="left", padx=20, pady=12)

        brand = ctk.CTkLabel(
            header,
            text=f"Developed by {DEVELOPER}  •  {WEBSITE}  •  Author: {AUTHOR}",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray70"),
        )
        brand.pack(side="right", padx=20)

        # Main body: sidebar + content
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10, pady=10)

        # Sidebar navigation
        self.sidebar = ctk.CTkFrame(body, width=200, corner_radius=10)
        self.sidebar.pack(side="left", fill="y", padx=(0, 10))
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(
            self.sidebar, text="NAVIGATION", font=ctk.CTkFont(size=11, weight="bold"),
            text_color="gray60"
        ).pack(anchor="w", padx=16, pady=(16, 8))

        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "Dashboard"),
            ("apps", "Allowed Apps"),
            ("ips", "Blocked IPs"),
            ("logs", "Security Log"),
            ("connections", "Live Connections"),
            ("actions", "Actions"),
            ("persistence", "Persistence Scan"),
            ("about", "About"),
        ]
        for key, label in nav_items:
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                anchor="w",
                height=36,
                fg_color="transparent",
                text_color=("gray20", "gray90"),
                hover_color=("gray80", "gray30"),
                command=lambda k=key: self.show_page(k),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = btn

        # Status indicator at bottom of sidebar
        self.sidebar_status = ctk.CTkLabel(
            self.sidebar, text="Status: Checking…", font=ctk.CTkFont(size=12)
        )
        self.sidebar_status.pack(side="bottom", pady=16, padx=12)

        # Content area
        self.content = ctk.CTkFrame(body, corner_radius=10)
        self.content.pack(side="left", fill="both", expand=True)

        # Pages
        self.pages: dict[str, ctk.CTkFrame] = {}
        self._build_dashboard()
        self._build_apps_page()
        self._build_ips_page()
        self._build_logs_page()
        self._build_connections_page()
        self._build_actions_page()
        self._build_persistence_page()
        self._build_about_page()

        self.show_page("dashboard")

    def show_page(self, key: str):
        for p in self.pages.values():
            p.pack_forget()
        page = self.pages.get(key)
        if page:
            page.pack(fill="both", expand=True, padx=8, pady=8)
        # Highlight active nav
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.configure(fg_color=("gray75", "gray25"))
            else:
                btn.configure(fg_color="transparent")

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    def _build_dashboard(self):
        page = ctk.CTkFrame(self.content, fg_color="transparent")
        self.pages["dashboard"] = page

        ctk.CTkLabel(page, text="Security Dashboard", font=ctk.CTkFont(size=18, weight="bold")).pack(
            anchor="w", padx=8, pady=(4, 12)
        )

        # Status cards row
        cards = ctk.CTkFrame(page, fg_color="transparent")
        cards.pack(fill="x", padx=4, pady=4)

        self.card_status = StatusCard(cards, "Firewall Status", width=200)
        self.card_status.pack(side="left", padx=6, fill="x", expand=True)
        self.card_inbound = StatusCard(cards, "Default Inbound", width=180)
        self.card_inbound.pack(side="left", padx=6, fill="x", expand=True)
        self.card_outbound = StatusCard(cards, "Default Outbound", width=180)
        self.card_outbound.pack(side="left", padx=6, fill="x", expand=True)
        self.card_rules = StatusCard(cards, "Firewall Rules", width=160)
        self.card_rules.pack(side="left", padx=6, fill="x", expand=True)

        # Quick actions
        qa = ctk.CTkFrame(page)
        qa.pack(fill="x", padx=4, pady=16)
        ctk.CTkLabel(qa, text="Quick Actions", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=12, pady=(10, 6)
        )
        btn_row = ctk.CTkFrame(qa, fg_color="transparent")
        btn_row.pack(fill="x", padx=8, pady=(0, 12))

        ctk.CTkButton(btn_row, text="Apply Full Hardening", command=self._action_apply_all,
                      height=36, fg_color="#1f6aa5").pack(side="left", padx=6)
        ctk.CTkButton(btn_row, text="Apply Lockdown Only", command=self._action_lockdown,
                      height=36).pack(side="left", padx=6)
        ctk.CTkButton(btn_row, text="Update Threat Feed", command=self._action_blocklist,
                      height=36).pack(side="left", padx=6)
        ctk.CTkButton(btn_row, text="Restore Defaults", command=self._action_restore,
                      height=36, fg_color="#8B0000", hover_color="#A52A2A").pack(side="left", padx=6)
        ctk.CTkButton(btn_row, text="Refresh Status", command=self.refresh_status,
                      height=36, fg_color="gray40").pack(side="left", padx=6)

        # Recent log preview
        ctk.CTkLabel(page, text="Recent Security Events", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=8, pady=(8, 4)
        )
        self.dash_log = ctk.CTkTextbox(page, height=220, font=ctk.CTkFont(family="Consolas", size=12))
        self.dash_log.pack(fill="both", expand=True, padx=8, pady=4)
        self.dash_log.configure(state="disabled")

    # ------------------------------------------------------------------
    # Allowed Apps page
    # ------------------------------------------------------------------
    def _build_apps_page(self):
        page = ctk.CTkFrame(self.content, fg_color="transparent")
        self.pages["apps"] = page

        header = ctk.CTkFrame(page, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(header, text="Allowed Applications", font=ctk.CTkFont(size=18, weight="bold")).pack(
            side="left"
        )
        ctk.CTkButton(header, text="Add Application", width=140, command=self._add_app_dialog).pack(
            side="right", padx=4
        )
        ctk.CTkButton(header, text="Refresh", width=90, command=self._reload_apps).pack(side="right", padx=4)

        # Treeview for apps
        tree_frame = ctk.CTkFrame(page)
        tree_frame.pack(fill="both", expand=True)

        columns = ("name", "path", "ports")
        self.apps_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=18)
        self.apps_tree.heading("name", text="Name")
        self.apps_tree.heading("path", text="Executable Path")
        self.apps_tree.heading("ports", text="Ports / ANY")
        self.apps_tree.column("name", width=160, anchor="w")
        self.apps_tree.column("path", width=520, anchor="w")
        self.apps_tree.column("ports", width=120, anchor="center")
        self.apps_tree.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.apps_tree.yview)
        sb.pack(side="right", fill="y")
        self.apps_tree.configure(yscrollcommand=sb.set)

        btn_bar = ctk.CTkFrame(page, fg_color="transparent")
        btn_bar.pack(fill="x", pady=8)
        ctk.CTkButton(btn_bar, text="Edit Selected", command=self._edit_app).pack(side="left", padx=4)
        ctk.CTkButton(btn_bar, text="Remove Selected", fg_color="#8B0000",
                      command=self._remove_app).pack(side="left", padx=4)
        ctk.CTkButton(btn_bar, text="Open allowed-apps.txt",
                      command=lambda: self._open_file(DATA_DIR / "allowed-apps.txt")).pack(side="right", padx=4)

        self._reload_apps()

    def _reload_apps(self):
        for i in self.apps_tree.get_children():
            self.apps_tree.delete(i)
        for app in self.fw.list_allowed_apps():
            self.apps_tree.insert("", "end", values=(app.name, app.path, app.ports))

    def _add_app_dialog(self):
        self._app_dialog()

    def _edit_app(self):
        sel = self.apps_tree.selection()
        if not sel:
            messagebox.showinfo("Edit", "Select an application first.")
            return
        vals = self.apps_tree.item(sel[0], "values")
        self._app_dialog(name=vals[0], path=vals[1], ports=vals[2], edit=True)

    def _app_dialog(self, name="", path="", ports="80,443", edit=False):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Edit Application" if edit else "Add Application")
        dlg.geometry("520x280")
        dlg.transient(self)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="Display Name").pack(anchor="w", padx=20, pady=(16, 2))
        name_e = ctk.CTkEntry(dlg, width=460)
        name_e.pack(padx=20)
        name_e.insert(0, name)

        ctk.CTkLabel(dlg, text="Full path to .exe").pack(anchor="w", padx=20, pady=(12, 2))
        path_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        path_frame.pack(fill="x", padx=20)
        path_e = ctk.CTkEntry(path_frame, width=380)
        path_e.pack(side="left")
        path_e.insert(0, path)

        def browse():
            f = filedialog.askopenfilename(filetypes=[("Executable", "*.exe"), ("All files", "*.*")])
            if f:
                path_e.delete(0, "end")
                path_e.insert(0, f)

        ctk.CTkButton(path_frame, text="Browse…", width=70, command=browse).pack(side="left", padx=6)

        ctk.CTkLabel(dlg, text="Ports (comma-separated) or ANY").pack(anchor="w", padx=20, pady=(12, 2))
        ports_e = ctk.CTkEntry(dlg, width=460)
        ports_e.pack(padx=20)
        ports_e.insert(0, ports)

        def save():
            n = name_e.get().strip()
            p = path_e.get().strip()
            po = ports_e.get().strip() or "80,443"
            if not n or not p:
                messagebox.showwarning("Validation", "Name and path are required.")
                return
            apps = self.fw.list_allowed_apps()
            if edit:
                apps = [a for a in apps if a.name != name]
            apps.append(AllowedApp(name=n, path=p, ports=po))
            self.fw.save_allowed_apps(apps)
            self._reload_apps()
            dlg.destroy()

        ctk.CTkButton(dlg, text="Save", command=save, height=36).pack(pady=20)

    def _remove_app(self):
        sel = self.apps_tree.selection()
        if not sel:
            return
        name = self.apps_tree.item(sel[0], "values")[0]
        if messagebox.askyesno("Confirm", f"Remove '{name}' from allowed list?"):
            self.fw.remove_allowed_app(name)
            self._reload_apps()

    # ------------------------------------------------------------------
    # Blocked IPs page
    # ------------------------------------------------------------------
    def _build_ips_page(self):
        page = ctk.CTkFrame(self.content, fg_color="transparent")
        self.pages["ips"] = page

        header = ctk.CTkFrame(page, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(header, text="Malicious IP Blocklist", font=ctk.CTkFont(size=18, weight="bold")).pack(
            side="left"
        )
        ctk.CTkButton(header, text="Add IP / CIDR", width=120, command=self._add_ip_dialog).pack(
            side="right", padx=4
        )
        ctk.CTkButton(header, text="Refresh", width=90, command=self._reload_ips).pack(side="right", padx=4)
        ctk.CTkButton(header, text="Update from Feeds", width=140,
                      command=self._action_blocklist).pack(side="right", padx=4)

        # Search
        search_f = ctk.CTkFrame(page, fg_color="transparent")
        search_f.pack(fill="x", pady=4)
        ctk.CTkLabel(search_f, text="Filter:").pack(side="left", padx=(4, 6))
        self.ip_filter = ctk.CTkEntry(search_f, width=280, placeholder_text="Type to filter…")
        self.ip_filter.pack(side="left")
        self.ip_filter.bind("<KeyRelease>", lambda e: self._filter_ips())

        tree_frame = ctk.CTkFrame(page)
        tree_frame.pack(fill="both", expand=True)

        self.ips_tree = ttk.Treeview(tree_frame, columns=("ip",), show="headings", height=18)
        self.ips_tree.heading("ip", text="IP Address / CIDR")
        self.ips_tree.column("ip", width=400, anchor="w")
        self.ips_tree.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.ips_tree.yview)
        sb.pack(side="right", fill="y")
        self.ips_tree.configure(yscrollcommand=sb.set)

        btn_bar = ctk.CTkFrame(page, fg_color="transparent")
        btn_bar.pack(fill="x", pady=8)
        ctk.CTkButton(btn_bar, text="Remove Selected", fg_color="#8B0000",
                      command=self._remove_ip).pack(side="left", padx=4)
        ctk.CTkLabel(btn_bar, text="Note: Large lists are applied in batches of 100 IPs.",
                     text_color="gray60").pack(side="left", padx=16)
        ctk.CTkButton(btn_bar, text="Open malicious-ips.txt",
                      command=lambda: self._open_file(DATA_DIR / "malicious-ips.txt")).pack(side="right", padx=4)

        self._all_ips: list[str] = []
        self._reload_ips()

    def _reload_ips(self):
        self._all_ips = self.fw.list_blocked_ips()
        self._filter_ips()

    def _filter_ips(self):
        q = self.ip_filter.get().strip().lower() if hasattr(self, "ip_filter") else ""
        for i in self.ips_tree.get_children():
            self.ips_tree.delete(i)
        for ip in self._all_ips:
            if not q or q in ip.lower():
                self.ips_tree.insert("", "end", values=(ip,))

    def _add_ip_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Add IP / CIDR")
        dlg.geometry("400x160")
        dlg.transient(self)
        dlg.grab_set()
        ctk.CTkLabel(dlg, text="IP address or CIDR (e.g. 1.2.3.4 or 10.0.0.0/8)").pack(
            anchor="w", padx=20, pady=(20, 4)
        )
        e = ctk.CTkEntry(dlg, width=340)
        e.pack(padx=20)

        def save():
            ip = e.get().strip()
            if not ip:
                return
            self.fw.add_blocked_ip(ip)
            self._reload_ips()
            dlg.destroy()

        ctk.CTkButton(dlg, text="Add", command=save).pack(pady=16)

    def _remove_ip(self):
        sel = self.ips_tree.selection()
        if not sel:
            return
        ip = self.ips_tree.item(sel[0], "values")[0]
        if messagebox.askyesno("Confirm", f"Remove {ip} from blocklist?"):
            self.fw.remove_blocked_ip(ip)
            self._reload_ips()

    # ------------------------------------------------------------------
    # Logs page
    # ------------------------------------------------------------------
    def _build_logs_page(self):
        page = ctk.CTkFrame(self.content, fg_color="transparent")
        self.pages["logs"] = page

        header = ctk.CTkFrame(page, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(header, text="Security & Firewall Log", font=ctk.CTkFont(size=18, weight="bold")).pack(
            side="left"
        )
        ctk.CTkButton(header, text="Refresh", width=90, command=self._reload_logs).pack(side="right", padx=4)
        ctk.CTkButton(header, text="Clear Log", width=90, fg_color="#8B0000",
                      command=self._clear_log).pack(side="right", padx=4)
        ctk.CTkButton(header, text="Open Log File", width=110,
                      command=lambda: self._open_file(LOG_FILE)).pack(side="right", padx=4)

        filter_f = ctk.CTkFrame(page, fg_color="transparent")
        filter_f.pack(fill="x", pady=4)
        ctk.CTkLabel(filter_f, text="Search:").pack(side="left", padx=(4, 6))
        self.log_filter = ctk.CTkEntry(filter_f, width=320, placeholder_text="Filter log lines…")
        self.log_filter.pack(side="left")
        self.log_filter.bind("<KeyRelease>", lambda e: self._filter_logs())

        self.log_text = ctk.CTkTextbox(page, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)
        self._all_log_lines: list[str] = []
        self._reload_logs()

    def _reload_logs(self):
        self._all_log_lines = self.fw.get_log_lines(8000)
        self._filter_logs()
        # Also update dashboard preview
        if hasattr(self, "dash_log"):
            self.dash_log.configure(state="normal")
            self.dash_log.delete("1.0", "end")
            preview = self._all_log_lines[-40:]
            self.dash_log.insert("end", "\n".join(preview))
            self.dash_log.configure(state="disabled")
            self.dash_log.see("end")

    def _filter_logs(self):
        q = self.log_filter.get().strip().lower() if hasattr(self, "log_filter") else ""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        for line in self._all_log_lines:
            if not q or q in line.lower():
                self.log_text.insert("end", line + "\n")
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def _clear_log(self):
        if messagebox.askyesno("Confirm", "Clear the security log?"):
            self.fw.clear_log()
            self._reload_logs()

    # ------------------------------------------------------------------
    # Live Connections
    # ------------------------------------------------------------------
    def _build_connections_page(self):
        page = ctk.CTkFrame(self.content, fg_color="transparent")
        self.pages["connections"] = page

        header = ctk.CTkFrame(page, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(header, text="Live Established TCP Connections",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="Refresh Now", width=110, command=self._reload_connections).pack(
            side="right", padx=4
        )
        self.conn_auto = ctk.CTkCheckBox(header, text="Auto-refresh (5s)")
        self.conn_auto.pack(side="right", padx=12)
        self.conn_auto.select()

        tree_frame = ctk.CTkFrame(page)
        tree_frame.pack(fill="both", expand=True)

        cols = ("local", "remote", "pid", "process")
        self.conn_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=20)
        self.conn_tree.heading("local", text="Local Address:Port")
        self.conn_tree.heading("remote", text="Remote Address:Port")
        self.conn_tree.heading("pid", text="PID")
        self.conn_tree.heading("process", text="Process")
        self.conn_tree.column("local", width=220)
        self.conn_tree.column("remote", width=220)
        self.conn_tree.column("pid", width=80, anchor="center")
        self.conn_tree.column("process", width=200)
        self.conn_tree.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.conn_tree.yview)
        sb.pack(side="right", fill="y")
        self.conn_tree.configure(yscrollcommand=sb.set)

        self._reload_connections()

    def _reload_connections(self):
        for i in self.conn_tree.get_children():
            self.conn_tree.delete(i)
        try:
            conns = self.fw.get_live_connections()
            for c in conns:
                self.conn_tree.insert(
                    "", "end",
                    values=(
                        f"{c.local_address}:{c.local_port}",
                        f"{c.remote_address}:{c.remote_port}",
                        c.process_id,
                        c.process_name,
                    ),
                )
        except Exception as e:
            self.conn_tree.insert("", "end", values=(f"Error: {e}", "", "", ""))

    # ------------------------------------------------------------------
    # Actions page
    # ------------------------------------------------------------------
    def _build_actions_page(self):
        page = ctk.CTkFrame(self.content, fg_color="transparent")
        self.pages["actions"] = page

        ctk.CTkLabel(page, text="Security Actions", font=ctk.CTkFont(size=18, weight="bold")).pack(
            anchor="w", padx=8, pady=(4, 12)
        )

        actions = [
            ("Apply Full Hardening (Lockdown + Threat Feed + Defender)", self._action_apply_all,
             "Recommended first-time setup. Applies outbound lockdown, downloads IP blocklists, and enables Defender ASR rules."),
            ("Apply Firewall Lockdown Only", self._action_lockdown,
             "Resets firewall, blocks outbound by default, allows listed apps, blocks high-risk ports and LOLBins."),
            ("Update Threat Feed & Apply IP Blocks", self._action_blocklist,
             "Downloads public malicious-IP feeds and creates inbound block rules in batches."),
            ("Apply Windows Defender Hardening Only", self._action_defender,
             "Enables real-time protection, Controlled Folder Access, and Attack Surface Reduction rules."),
            ("Restore Windows Firewall Defaults", self._action_restore,
             "Resets the firewall to Microsoft defaults and turns the protection status OFF."),
        ]

        for title, cmd, desc in actions:
            frame = ctk.CTkFrame(page)
            frame.pack(fill="x", padx=8, pady=6)
            ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=14, weight="bold")).pack(
                anchor="w", padx=12, pady=(10, 2)
            )
            ctk.CTkLabel(frame, text=desc, text_color="gray60", wraplength=700, justify="left").pack(
                anchor="w", padx=12
            )
            ctk.CTkButton(frame, text="Run", width=100, command=cmd).pack(anchor="e", padx=12, pady=10)

        self.action_progress = ctk.CTkLabel(page, text="", text_color="gray70")
        self.action_progress.pack(anchor="w", padx=12, pady=8)

    # ------------------------------------------------------------------
    # Persistence scan
    # ------------------------------------------------------------------
    def _build_persistence_page(self):
        page = ctk.CTkFrame(self.content, fg_color="transparent")
        self.pages["persistence"] = page

        header = ctk.CTkFrame(page, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(header, text="Persistence Scan (Read-Only)",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="Run Scan", width=110, command=self._run_persistence).pack(
            side="right", padx=4
        )

        ctk.CTkLabel(
            page,
            text="This scan reports common locations used by malware/RATs for persistence. "
                 "Nothing is deleted automatically. Review each entry carefully.",
            text_color="gray60", wraplength=900, justify="left"
        ).pack(anchor="w", padx=8, pady=4)

        self.persist_text = ctk.CTkTextbox(page, font=ctk.CTkFont(family="Consolas", size=12))
        self.persist_text.pack(fill="both", expand=True, padx=4, pady=8)

    def _run_persistence(self):
        self.persist_text.delete("1.0", "end")
        self.persist_text.insert("end", "Scanning… please wait.\n")
        self.update_idletasks()

        def worker():
            try:
                report = self.fw.scan_persistence()
                self.after(0, lambda: self._show_persist(report))
            except Exception as e:
                self.after(0, lambda: self._show_persist(f"Error: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _show_persist(self, text: str):
        self.persist_text.delete("1.0", "end")
        self.persist_text.insert("end", text)

    # ------------------------------------------------------------------
    # About
    # ------------------------------------------------------------------
    def _build_about_page(self):
        page = ctk.CTkFrame(self.content, fg_color="transparent")
        self.pages["about"] = page

        ctk.CTkLabel(page, text=APP_NAME, font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(30, 6))
        ctk.CTkLabel(page, text=f"Version {APP_VERSION}", font=ctk.CTkFont(size=14)).pack()
        ctk.CTkLabel(page, text=f"Developed by: {DEVELOPER}", font=ctk.CTkFont(size=14)).pack(pady=(16, 2))
        ctk.CTkLabel(page, text=f"Website: {WEBSITE}", font=ctk.CTkFont(size=14)).pack()
        ctk.CTkLabel(page, text=f"Author: {AUTHOR}", font=ctk.CTkFont(size=14)).pack(pady=(2, 16))

        info = (
            "This application provides a modern graphical interface for the\n"
            "Security-Firewall-Defense PowerShell toolkit.\n\n"
            "It helps you harden Windows Firewall against RATs and malware,\n"
            "manage allowed applications, maintain malicious IP blocklists,\n"
            "monitor live connections, and apply Microsoft Defender ASR rules.\n\n"
            "All destructive actions require confirmation. The persistence scan\n"
            "is strictly read-only."
        )
        ctk.CTkLabel(page, text=info, justify="center", text_color="gray60").pack(pady=10)

        ctk.CTkLabel(
            page,
            text="© 2024–2026 aThemeArt. All rights reserved.",
            text_color="gray50",
            font=ctk.CTkFont(size=11),
        ).pack(side="bottom", pady=20)

    # ------------------------------------------------------------------
    # Actions helpers (run in background)
    # ------------------------------------------------------------------
    def _run_action(self, title: str, func):
        if not is_admin():
            messagebox.showerror("Administrator Required",
                                 "This action requires Administrator privileges.")
            return
        if not messagebox.askyesno("Confirm", f"Proceed with:\n\n{title}?"):
            return

        self.action_progress.configure(text=f"Running: {title}…")
        self.update_idletasks()

        def worker():
            try:
                def prog(msg):
                    self.after(0, lambda: self.action_progress.configure(text=msg))

                ok, msg = func(progress_cb=prog)
                def done():
                    self.action_progress.configure(
                        text=("Completed successfully." if ok else "Finished with errors – see log.")
                    )
                    self.refresh_status()
                    self._reload_logs()
                    if not ok:
                        messagebox.showwarning("Action Result", msg[-1500:] if len(msg) > 1500 else msg)
                    else:
                        messagebox.showinfo("Action Result", "Operation completed.")
                self.after(0, done)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
                self.after(0, lambda: self.action_progress.configure(text="Error occurred."))

        threading.Thread(target=worker, daemon=True).start()

    def _action_apply_all(self):
        self._run_action("Full Hardening", self.fw.apply_all)

    def _action_lockdown(self):
        self._run_action("Firewall Lockdown", self.fw.apply_lockdown)

    def _action_blocklist(self):
        self._run_action("Threat Feed Update", self.fw.update_blocklist)

    def _action_defender(self):
        self._run_action("Defender Hardening", self.fw.apply_defender_hardening)

    def _action_restore(self):
        self._run_action("Restore Defaults", self.fw.restore_defaults)

    # ------------------------------------------------------------------
    # Status & monitoring
    # ------------------------------------------------------------------
    def refresh_status(self):
        def worker():
            try:
                st = self.fw.get_status()
                self.after(0, lambda: self._apply_status(st))
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _apply_status(self, st):
        if st.enabled or st.default_outbound.upper() == "BLOCK":
            self.card_status.set_value("ON / Hardened", "#3ddc84")
            self.sidebar_status.configure(text="Status: PROTECTED", text_color="#3ddc84")
        else:
            self.card_status.set_value("OFF / Default", "#ff6b6b")
            self.sidebar_status.configure(text="Status: NOT HARDENED", text_color="#ff6b6b")

        self.card_inbound.set_value(st.default_inbound)
        self.card_outbound.set_value(st.default_outbound)
        self.card_rules.set_value(str(st.rule_count))

        color_in = "#3ddc84" if st.default_inbound.upper() == "BLOCK" else None
        color_out = "#3ddc84" if st.default_outbound.upper() == "BLOCK" else None
        if color_in:
            self.card_inbound.value_label.configure(text_color=color_in)
        if color_out:
            self.card_outbound.value_label.configure(text_color=color_out)

    def _start_monitor(self):
        self._monitor_running = True

        def loop():
            while self._monitor_running:
                try:
                    self.refresh_status()
                    # Auto-refresh connections if page visible and checkbox on
                    if self.conn_auto.get() and self.pages["connections"].winfo_ismapped():
                        self.after(0, self._reload_connections)
                    # Refresh log preview occasionally
                    self.after(0, self._reload_logs)
                except Exception:
                    pass
                for _ in range(50):  # ~5 seconds
                    if not self._monitor_running:
                        break
                    threading.Event().wait(0.1)

        self._monitor_thread = threading.Thread(target=loop, daemon=True)
        self._monitor_thread.start()

    def _open_file(self, path: Path):
        import os
        try:
            os.startfile(str(path))
        except Exception as e:
            messagebox.showerror("Open File", str(e))

    def on_closing(self):
        self._monitor_running = False
        self.destroy()


def main():
    # On Windows we require admin for firewall operations
    if sys.platform == "win32":
        require_admin(exit_on_fail=True)

    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
