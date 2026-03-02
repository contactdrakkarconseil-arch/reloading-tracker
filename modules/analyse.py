"""Analyse & Graphiques module."""

import customtkinter as ctk
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from typing import List, Dict, Optional

from utils.database import Database
from utils.conversions import mm_to_moa, mm_to_inch, calculate_jump_thou
from utils.ballistics import es_color


class AnalyseFrame(ctk.CTkFrame):
    def __init__(self, parent, db: Database):
        super().__init__(parent, fg_color="transparent")
        self.db = db
        self._figures = []  # Track figures for cleanup
        self._initialized = False
        self._build_ui()

    def _build_ui(self):
        title = ctk.CTkLabel(
            self, text="Analyse & Graphiques",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        title.pack(pady=(10, 5), anchor="w", padx=20)

        # Setup selector
        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(filter_frame, text="Setup :").pack(side="left", padx=(0, 5))
        setups = self.db.get_setups()
        setup_names = [s["nom"] for s in setups]
        self._setup_map = {s["nom"]: s["id"] for s in setups}
        self._setups = {s["id"]: s for s in setups}

        self.setup_combo = ctk.CTkComboBox(
            filter_frame, values=setup_names if setup_names else ["Aucun"],
            width=250, command=self._on_setup_changed,
        )
        self.setup_combo.pack(side="left", padx=5)

        # Graph tabs
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        self.tab_es_sd = self.tab_view.add("ES & SD vs Charge")
        self.tab_vel = self.tab_view.add("Vitesse vs Charge")
        self.tab_grp_charge = self.tab_view.add("Groupement vs Charge")
        self.tab_grp_cbto = self.tab_view.add("Groupement vs CBTO")
        self.tab_summary = self.tab_view.add("Synthèse")

        if setup_names:
            self.setup_combo.set(setup_names[0])
            # Don't plot immediately - wait for refresh() which is called on navigate
            self._initialized = True

    def _on_setup_changed(self, name: str):
        setup_id = self._setup_map.get(name)
        if not setup_id:
            return
        series = self.db.get_all_series(setup_id)
        setup = self._setups.get(setup_id, {})

        # Close previous figures to avoid memory leaks
        self._close_figures()

        self._plot_es_sd(series)
        self._plot_velocity(series)
        self._plot_group_charge(series)
        self._plot_group_cbto(series, setup)
        self._build_summary(series, setup)

    def _close_figures(self):
        """Close all tracked matplotlib figures."""
        import matplotlib.pyplot as plt
        for fig in self._figures:
            try:
                plt.close(fig)
            except Exception:
                pass
        self._figures = []

    def _clear_tab(self, tab):
        for w in tab.winfo_children():
            w.destroy()

    def _make_figure(self, tab, figsize=(8, 4.5)):
        fig = Figure(figsize=figsize, dpi=100)
        fig.patch.set_facecolor("#2B2B2B")

        canvas = FigureCanvasTkAgg(fig, master=tab)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(fill="both", expand=True)

        toolbar = NavigationToolbar2Tk(canvas, tab)
        toolbar.update()
        toolbar.pack(side="bottom", fill="x")

        self._figures.append(fig)
        return fig, canvas

    def _style_ax(self, ax):
        ax.set_facecolor("#2B2B2B")
        ax.tick_params(colors="#999999", labelsize=9)
        for spine in ax.spines.values():
            spine.set_color("#666666")
        ax.xaxis.label.set_color("#999999")
        ax.yaxis.label.set_color("#999999")
        ax.title.set_color("white")

    # ── Graph 1: ES & SD vs Charge ──

    def _plot_es_sd(self, series: List[Dict]):
        self._clear_tab(self.tab_es_sd)
        valid = [s for s in series if s.get("es") is not None and s["es"] > 0]
        if len(valid) < 2:
            ctk.CTkLabel(self.tab_es_sd,
                         text=f"Pas assez de données (min 2 séries avec ES). Trouvé: {len(valid)}",
                         text_color="gray50").pack(pady=30)
            return

        # Sort by charge for proper line plotting
        valid.sort(key=lambda x: x["charge_gr"])

        fig, canvas = self._make_figure(self.tab_es_sd)
        ax1 = fig.add_subplot(111)
        self._style_ax(ax1)

        charges = [s["charge_gr"] for s in valid]
        es_vals = [s["es"] for s in valid]
        sd_vals = [s.get("sd", 0) or 0 for s in valid]
        colors = [es_color(e) for e in es_vals]

        ax1.scatter(charges, es_vals, c=colors, s=80, zorder=5, label="ES")
        ax1.plot(charges, es_vals, color="gray", alpha=0.4, linewidth=1)
        ax1.axhline(y=15, color="lime", linewidth=1, linestyle="--", alpha=0.6, label="ES=15 fps")
        ax1.set_xlabel("Charge (gr)")
        ax1.set_ylabel("ES (fps)", color="#3B8ED0")
        ax1.tick_params(axis="y", labelcolor="#3B8ED0")

        # Set axis limits with some padding
        if es_vals:
            es_min_val = min(es_vals)
            es_max_val = max(es_vals)
            margin = max((es_max_val - es_min_val) * 0.2, 2)
            ax1.set_ylim(max(0, es_min_val - margin), es_max_val + margin)

        if charges:
            c_margin = max((max(charges) - min(charges)) * 0.1, 0.2)
            ax1.set_xlim(min(charges) - c_margin, max(charges) + c_margin)

        # Highlight nodes (local minima)
        if len(es_vals) >= 3:
            for i in range(1, len(es_vals) - 1):
                if es_vals[i] < es_vals[i-1] and es_vals[i] < es_vals[i+1]:
                    ax1.annotate(
                        f"Node\n{es_vals[i]:.0f}fps",
                        (charges[i], es_vals[i]),
                        textcoords="offset points", xytext=(0, 15),
                        ha="center", fontsize=8, color="lime",
                        arrowprops=dict(arrowstyle="->", color="lime", lw=0.8),
                    )

        # SD on right axis
        ax2 = ax1.twinx()
        ax2.plot(charges, sd_vals, "s--", color="#E8A317", alpha=0.7, markersize=5, label="SD")
        ax2.set_ylabel("SD (fps)", color="#E8A317")
        ax2.tick_params(axis="y", labelcolor="#E8A317")

        if sd_vals:
            sd_min_val = min(sd_vals)
            sd_max_val = max(sd_vals)
            sd_margin = max((sd_max_val - sd_min_val) * 0.2, 1)
            ax2.set_ylim(max(0, sd_min_val - sd_margin), sd_max_val + sd_margin)

        ax1.set_title("ES & SD vs Charge")
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right",
                   fontsize=8, facecolor="#3B3B3B", edgecolor="#808080", labelcolor="white")

        fig.tight_layout()
        canvas.draw_idle()

    # ── Graph 2: Velocity vs Charge ──

    def _plot_velocity(self, series: List[Dict]):
        self._clear_tab(self.tab_vel)
        valid = [s for s in series if s.get("v_moy") and s["v_moy"] > 0]
        if len(valid) < 2:
            ctk.CTkLabel(self.tab_vel,
                         text=f"Pas assez de données. Trouvé: {len(valid)} séries avec V moy.",
                         text_color="gray50").pack(pady=30)
            return

        # Sort by charge
        valid.sort(key=lambda x: x["charge_gr"])

        fig, canvas = self._make_figure(self.tab_vel)
        ax = fig.add_subplot(111)
        self._style_ax(ax)

        charges = [s["charge_gr"] for s in valid]
        v_moy = [s["v_moy"] for s in valid]
        es_vals = [s.get("es", 0) or 0 for s in valid]

        ax.errorbar(charges, v_moy, yerr=[e / 2 for e in es_vals],
                    fmt="o-", color="#3B8ED0", capsize=4, capthick=1,
                    markersize=6, linewidth=1.5, ecolor="gray")

        # Trend: fps per grain
        if len(charges) >= 2:
            coeffs = np.polyfit(charges, v_moy, 1)
            trend_label = f"Tendance: {coeffs[0]:.1f} fps/gr"
            x_fit = np.linspace(min(charges), max(charges), 50)
            y_fit = np.polyval(coeffs, x_fit)
            ax.plot(x_fit, y_fit, "--", color="#E8A317", alpha=0.6, label=trend_label)
            ax.legend(fontsize=9, facecolor="#3B3B3B", edgecolor="#808080", labelcolor="white")

        ax.set_xlabel("Charge (gr)")
        ax.set_ylabel("Vitesse moyenne (fps)")
        ax.set_title("Vitesse moyenne vs Charge")

        fig.tight_layout()
        canvas.draw_idle()

    # ── Graph 3: Group vs Charge ──

    def _plot_group_charge(self, series: List[Dict]):
        self._clear_tab(self.tab_grp_charge)
        valid = [s for s in series if s.get("groupement_mm") and s["groupement_mm"] > 0]
        if len(valid) < 2:
            ctk.CTkLabel(self.tab_grp_charge,
                         text=f"Pas assez de données. Trouvé: {len(valid)} séries avec groupement.",
                         text_color="gray50").pack(pady=30)
            return

        # Sort by charge
        valid.sort(key=lambda x: x["charge_gr"])

        fig, canvas = self._make_figure(self.tab_grp_charge)
        ax = fig.add_subplot(111)
        self._style_ax(ax)

        charges = [s["charge_gr"] for s in valid]
        distances = [s.get("distance_m", 100) for s in valid]
        grp_moa = [mm_to_moa(s["groupement_mm"], d) for s, d in zip(valid, distances)]
        nb = [s.get("nb_coups", 5) for s in valid]
        sizes = [n * 15 for n in nb]

        ax.scatter(charges, grp_moa, s=sizes, c="#3B8ED0", alpha=0.8, edgecolors="white", linewidth=0.5)

        for c, m, n in zip(charges, grp_moa, nb):
            ax.annotate(f"{n}c", (c, m), textcoords="offset points",
                        xytext=(8, 0), fontsize=8, color="#999999")

        ax.set_xlabel("Charge (gr)")
        ax.set_ylabel("Groupement (MOA)")
        ax.set_title("Groupement vs Charge (Phase 1)")

        fig.tight_layout()
        canvas.draw_idle()

    # ── Graph 4: Group vs CBTO/Jump ──

    def _plot_group_cbto(self, series: List[Dict], setup: Dict):
        self._clear_tab(self.tab_grp_cbto)
        valid = [s for s in series
                 if s.get("groupement_mm") and s["groupement_mm"] > 0
                 and s.get("cbto_mm")]
        if len(valid) < 2:
            ctk.CTkLabel(self.tab_grp_cbto,
                         text=f"Pas assez de données Phase 2. Trouvé: {len(valid)} séries avec CBTO + groupement.",
                         text_color="gray50").pack(pady=30)
            return

        cbto_lands = setup.get("cbto_lands_mm", 58.57)

        fig, canvas = self._make_figure(self.tab_grp_cbto)
        ax = fig.add_subplot(111)
        self._style_ax(ax)

        cbto_vals = [s["cbto_mm"] for s in valid]
        jump_thou = [calculate_jump_thou(cbto_lands, c) for c in cbto_vals]
        distances = [s.get("distance_m", 100) for s in valid]
        grp_moa = [mm_to_moa(s["groupement_mm"], d) for s, d in zip(valid, distances)]

        ax.plot(jump_thou, grp_moa, "o-", color="#9B59B6", markersize=8)

        # Highlight best
        if grp_moa:
            best_idx = grp_moa.index(min(grp_moa))
            ax.scatter([jump_thou[best_idx]], [grp_moa[best_idx]],
                       s=150, c="lime", zorder=10, marker="*")
            ax.annotate(
                f"Optimal\n{jump_thou[best_idx]:.0f} thou",
                (jump_thou[best_idx], grp_moa[best_idx]),
                textcoords="offset points", xytext=(15, -10),
                fontsize=9, color="lime",
                arrowprops=dict(arrowstyle="->", color="lime"),
            )

        ax.set_xlabel("Jump (thou)")
        ax.set_ylabel("Groupement (MOA)")
        ax.set_title("Groupement vs Jump / CBTO (Phase 2)")

        # Secondary x-axis for CBTO mm
        ax2 = ax.twiny()
        ax2.set_xlim([cbto_lands - t / 39.3701 for t in ax.get_xlim()])
        ax2.set_xlabel("CBTO (mm)", color="#999999")
        ax2.tick_params(colors="#999999", labelsize=8)

        fig.tight_layout()
        canvas.draw_idle()

    # ── Summary table ──

    def _build_summary(self, series: List[Dict], setup: Dict):
        self._clear_tab(self.tab_summary)

        scroll = ctk.CTkScrollableFrame(self.tab_summary, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(
            scroll, text="Tableau de synthèse",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w", pady=(10, 15))

        if not series:
            ctk.CTkLabel(scroll, text="Aucune donnée.", text_color="gray50").pack(pady=20)
            return

        valid_es = [s for s in series if s.get("es") is not None and s["es"] > 0]
        valid_grp = [s for s in series if s.get("groupement_mm") and s["groupement_mm"] > 0]

        results = []

        if valid_es:
            best = min(valid_es, key=lambda x: x["es"])
            results.append(("Meilleure charge (ES min)",
                            f'{best["charge_gr"]:.1f} gr → ES {best["es"]:.1f} fps'))

        if valid_grp:
            best = min(valid_grp, key=lambda x: x["groupement_mm"])
            d = best.get("distance_m", 100)
            moa = mm_to_moa(best["groupement_mm"], d)
            results.append(("Meilleur groupement",
                            f'{best["charge_gr"]:.1f} gr → {best["groupement_mm"]:.1f} mm '
                            f'({moa:.2f} MOA @ {d:.0f}m)'))

        # Best compromise
        if valid_es and valid_grp:
            scored = []
            for s in series:
                if s.get("es") and s["es"] > 0 and s.get("groupement_mm") and s["groupement_mm"] > 0:
                    es_norm = s["es"] / max(x["es"] for x in valid_es)
                    d = s.get("distance_m", 100)
                    moa = mm_to_moa(s["groupement_mm"], d)
                    max_moa = max(mm_to_moa(x["groupement_mm"], x.get("distance_m", 100)) for x in valid_grp)
                    grp_norm = moa / max_moa if max_moa > 0 else 0
                    score = 0.5 * es_norm + 0.5 * grp_norm
                    scored.append((s, score))
            if scored:
                best = min(scored, key=lambda x: x[1])[0]
                results.append(("Charge recommandée (compromis)",
                                f'{best["charge_gr"]:.1f} gr '
                                f'(ES {best.get("es", 0):.1f} fps, '
                                f'{best.get("groupement_mm", 0):.1f} mm)'))

        # CBTO analysis
        cbto_series = [s for s in series if s.get("cbto_mm") and s.get("groupement_mm") and s["groupement_mm"] > 0]
        if len(cbto_series) >= 2:
            best_cbto = min(cbto_series, key=lambda x: x["groupement_mm"])
            cbto_lands = setup.get("cbto_lands_mm", 58.57)
            jump = calculate_jump_thou(cbto_lands, best_cbto["cbto_mm"])
            results.append(("CBTO optimal",
                            f'{best_cbto["cbto_mm"]:.2f} mm (jump {jump:.0f} thou)'))

        retained = [s for s in series if s.get("charge_retenue")]
        if retained:
            r = retained[-1]
            results.append(("Charge retenue", f'{r["charge_gr"]:.1f} gr'))

        for label, value in results:
            card = ctk.CTkFrame(scroll, corner_radius=8)
            card.pack(fill="x", pady=4)
            ctk.CTkLabel(
                card, text=label, font=ctk.CTkFont(size=12),
                text_color="gray60",
            ).pack(anchor="w", padx=15, pady=(8, 2))
            ctk.CTkLabel(
                card, text=value,
                font=ctk.CTkFont(size=15, weight="bold"),
            ).pack(anchor="w", padx=15, pady=(0, 8))

        # Full data table
        ctk.CTkLabel(
            scroll, text="Toutes les séries",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", pady=(25, 10))

        # Table header
        hdr_frame = ctk.CTkFrame(scroll, fg_color=("gray75", "gray25"), corner_radius=4)
        hdr_frame.pack(fill="x")
        headers = ["Date", "Charge", "V moy", "ES", "SD", "Grp (MOA)", "Jump"]
        widths = [90, 70, 75, 65, 65, 85, 75]
        for h, w in zip(headers, widths):
            ctk.CTkLabel(hdr_frame, text=h, width=w,
                         font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=2, pady=4)

        for s in series:
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=1)

            d = s.get("distance_m", 100)
            grp_moa = mm_to_moa(s["groupement_mm"], d) if s.get("groupement_mm") else None

            vals = [
                s.get("date", "")[:10],
                f'{s["charge_gr"]:.1f}',
                f'{s["v_moy"]:.0f}' if s.get("v_moy") else "—",
                f'{s["es"]:.1f}' if s.get("es") else "—",
                f'{s["sd"]:.1f}' if s.get("sd") else "—",
                f'{grp_moa:.2f}' if grp_moa else "—",
                f'{s.get("jump_mm", 0):.2f}mm' if s.get("jump_mm") is not None else "—",
            ]
            for col_idx, (v, w) in enumerate(zip(vals, widths)):
                color = "white"
                if col_idx == 3 and v != "—":  # ES column
                    try:
                        color = es_color(float(v))
                    except ValueError:
                        pass
                ctk.CTkLabel(row, text=v, width=w,
                             font=ctk.CTkFont(size=10), text_color=color).pack(side="left", padx=2, pady=2)

    def refresh(self):
        setups = self.db.get_setups()
        setup_names = [s["nom"] for s in setups]
        self._setup_map = {s["nom"]: s["id"] for s in setups}
        self._setups = {s["id"]: s for s in setups}
        self.setup_combo.configure(values=setup_names if setup_names else ["Aucun"])
        if setup_names:
            current = self.setup_combo.get()
            if current in setup_names:
                # Use after_idle to ensure the tab widgets are fully rendered
                self.after_idle(lambda: self._on_setup_changed(current))
            else:
                self.setup_combo.set(setup_names[0])
                self.after_idle(lambda: self._on_setup_changed(setup_names[0]))
