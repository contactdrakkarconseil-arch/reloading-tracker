#!/usr/bin/env python3
"""Reloading Tracker – Suivi de développement de charges."""

import sys
import os

# Ensure modules are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk

from utils.database import Database
from modules.dashboard import DashboardFrame
from modules.setups import SetupsFrame
from modules.nouvelle_session import NouvelleSessionFrame
from modules.historique import HistoriqueFrame
from modules.analyse import AnalyseFrame
from modules.export import ExportFrame


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ── Appearance (must be set before widgets) ──
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # ── Window setup ──
        self.title("Reloading Tracker")
        self.geometry("1280x820")
        self.minsize(1200, 800)

        # ── Database ──
        self.db = Database()
        self.db.seed_default_setup()

        # ── Layout: sidebar + content using pack ──
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # App title in sidebar
        ctk.CTkLabel(
            self.sidebar, text="Reloading\nTracker",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(pady=(25, 30), padx=15)

        # Navigation buttons
        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "Tableau de bord"),
            ("setups", "Mes Setups"),
            ("new_session", "Nouvelle Session"),
            ("historique", "Historique"),
            ("analyse", "Analyse & Graphiques"),
            ("export", "Export"),
        ]

        for key, label in nav_items:
            btn = ctk.CTkButton(
                self.sidebar,
                text=f"  {label}",
                height=40,
                anchor="w",
                font=ctk.CTkFont(size=14),
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray75", "gray25"),
                command=lambda k=key: self._navigate(k),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = btn

        # Version at bottom
        ctk.CTkLabel(
            self.sidebar, text="v1.0.0",
            font=ctk.CTkFont(size=11), text_color="gray50",
        ).pack(side="bottom", pady=10)

        # Main content area
        self.content = ctk.CTkFrame(self, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)

        # ── Create all pages ──
        self.pages = {}
        self._create_pages()

        # ── Keyboard shortcuts ──
        self.bind("<Command-n>", lambda e: self._navigate("new_session"))
        self.bind("<Command-e>", lambda e: self._navigate("export"))

        # ── Start on dashboard ──
        self._navigate("dashboard")

    def _create_pages(self):
        self.pages["dashboard"] = DashboardFrame(self.content, self.db)
        self.pages["setups"] = SetupsFrame(self.content, self.db)
        self.pages["new_session"] = NouvelleSessionFrame(
            self.content, self.db, on_session_saved=self._on_session_saved,
        )
        self.pages["historique"] = HistoriqueFrame(self.content, self.db)
        self.pages["analyse"] = AnalyseFrame(self.content, self.db)
        self.pages["export"] = ExportFrame(self.content, self.db)

    def _navigate(self, page_key: str):
        # Hide all pages
        for page in self.pages.values():
            page.pack_forget()

        # Update nav button styles
        for key, btn in self.nav_buttons.items():
            if key == page_key:
                btn.configure(fg_color=("#3B8ED0", "#1F6AA5"), text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color=("gray10", "gray90"))

        # Show selected page
        page = self.pages[page_key]
        page.pack(fill="both", expand=True)

        # Refresh page data
        if hasattr(page, "refresh"):
            page.refresh()

    def _on_session_saved(self):
        """Called after a session is saved – refresh relevant pages."""
        pass  # Pages refresh on navigate

    def on_closing(self):
        self.db.close()
        self.destroy()


def main():
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
