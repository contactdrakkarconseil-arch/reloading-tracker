"""Dashboard module – summary view."""

import customtkinter as ctk
from typing import Optional
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from utils.database import Database
from utils.conversions import mm_to_moa, mm_to_inch
from utils.ballistics import es_color


class DashboardFrame(ctk.CTkFrame):
    def __init__(self, parent, db: Database):
        super().__init__(parent, fg_color="transparent")
        self.db = db
        self._build_ui()

    def _build_ui(self):
        title = ctk.CTkLabel(
            self, text="Tableau de bord",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        title.pack(pady=(10, 15), anchor="w", padx=20)

        self.content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=20)

        self.refresh()

    def refresh(self):
        for w in self.content.winfo_children():
            w.destroy()

        setups = self.db.get_setups()
        if not setups:
            ctk.CTkLabel(
                self.content,
                text="Aucun setup configuré.\n\nAllez dans 'Mes Setups' pour commencer.",
                font=ctk.CTkFont(size=16),
                text_color="gray50",
            ).pack(pady=50)
            return

        for setup in setups:
            self._build_setup_card(setup)

    def _build_setup_card(self, setup: dict):
        card = ctk.CTkFrame(self.content, corner_radius=12)
        card.pack(fill="x", pady=8)

        # Header
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(12, 5))

        ctk.CTkLabel(
            header, text=setup["nom"],
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left")
        ctk.CTkLabel(
            header, text=setup.get("calibre", ""),
            font=ctk.CTkFont(size=14),
            text_color="gray60",
        ).pack(side="left", padx=15)

        # Stats
        best = self.db.get_best_series(setup["id"])
        sessions = self.db.get_sessions(setup["id"])
        all_series = self.db.get_all_series(setup["id"])

        stats_frame = ctk.CTkFrame(card, fg_color="transparent")
        stats_frame.pack(fill="x", padx=15, pady=5)

        stats = [
            ("Sessions", str(len(sessions))),
            ("Séries", str(len(all_series))),
        ]

        if best.get("best_es") is not None:
            color = es_color(best["best_es"])
            stats.append(("Meilleur ES", f"{best['best_es']:.1f} fps @ {best.get('best_es_charge', '?')} gr"))
        if best.get("best_group_mm") is not None:
            distance = 100
            moa = mm_to_moa(best["best_group_mm"], distance)
            stats.append(("Meilleur grp", f"{best['best_group_mm']:.1f} mm ({moa:.2f} MOA)"))
        if best.get("charge_retenue") is not None:
            stats.append(("Charge retenue", f"{best['charge_retenue']:.1f} gr"))

        cbto_lands = setup.get("cbto_lands_mm")
        if cbto_lands:
            stats.append(("CBTO Lands", f'{cbto_lands:.2f} mm ({mm_to_inch(cbto_lands):.3f}")'))

        for i, (label, value) in enumerate(stats):
            row = ctk.CTkFrame(stats_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=f"{label} :", width=140, anchor="w",
                         text_color="gray60", font=ctk.CTkFont(size=12)).pack(side="left")
            ctk.CTkLabel(row, text=value, anchor="w",
                         font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")

        # Mini chart: ES vs Charge (last session)
        if all_series:
            phase1 = [s for s in all_series if s.get("es") is not None and s["es"] > 0]
            if len(phase1) >= 2:
                chart_frame = ctk.CTkFrame(card, fg_color="transparent")
                chart_frame.pack(fill="x", padx=15, pady=(5, 10))

                fig = Figure(figsize=(5, 2), dpi=100)
                fig.patch.set_facecolor("#2B2B2B")
                ax = fig.add_subplot(111)
                ax.set_facecolor("#2B2B2B")

                charges = [s["charge_gr"] for s in phase1]
                es_vals = [s["es"] for s in phase1]
                colors = [es_color(e) for e in es_vals]

                ax.scatter(charges, es_vals, c=colors, s=50, zorder=5)
                ax.plot(charges, es_vals, color="gray", alpha=0.5, linewidth=1)
                ax.axhline(y=15, color="lime", linewidth=0.8, linestyle="--", alpha=0.5)
                ax.set_xlabel("Charge (gr)", fontsize=9, color="gray")
                ax.set_ylabel("ES (fps)", fontsize=9, color="gray")
                ax.tick_params(colors="gray", labelsize=8)
                for spine in ax.spines.values():
                    spine.set_color("#666666")
                fig.tight_layout()

                canvas = FigureCanvasTkAgg(fig, master=chart_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill="x")

        # Alerts
        if not sessions:
            alert = ctk.CTkLabel(
                card, text="Aucune session enregistrée pour ce setup.",
                text_color="#E8A317", font=ctk.CTkFont(size=12),
            )
            alert.pack(anchor="w", padx=15, pady=(0, 10))

        # Padding
        ctk.CTkFrame(card, height=5, fg_color="transparent").pack()
