"""Nouvelle Session module – 3-step session entry."""

import customtkinter as ctk
from datetime import date
import json
from typing import Optional, Dict, List, Callable

from utils.database import Database
from utils.conversions import (
    mm_to_inch, inch_to_mm, calculate_jump_mm, calculate_jump_thou, mm_to_moa,
)
from utils.ballistics import (
    calculate_es, calculate_sd, calculate_mean, es_color, charge_warning_level,
)


class NouvelleSessionFrame(ctk.CTkFrame):
    def __init__(self, parent, db: Database, on_session_saved: Optional[Callable] = None):
        super().__init__(parent, fg_color="transparent")
        self.db = db
        self.on_session_saved = on_session_saved

        self.current_step = 1
        self.session_data: Dict = {}
        self.serie_data: Dict = {}
        self.velocity_entries: List[ctk.CTkEntry] = []

        # Cache setup info
        self._setup_cache: Optional[Dict] = None
        self._powder_cache: Optional[Dict] = None

        self._build_ui()

    def _build_ui(self):
        # Title
        title = ctk.CTkLabel(
            self, text="Nouvelle Session", font=ctk.CTkFont(size=24, weight="bold")
        )
        title.pack(pady=(10, 5), anchor="w", padx=20)

        # Step indicator
        self.step_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.step_frame.pack(fill="x", padx=20, pady=(0, 10))

        self.step_labels = []
        steps = ["A – Infos Session", "B – Paramètres Série", "C – Vitesses & Résultats"]
        for i, text in enumerate(steps):
            lbl = ctk.CTkLabel(
                self.step_frame,
                text=f"  {text}  ",
                font=ctk.CTkFont(size=13, weight="bold"),
                corner_radius=6,
            )
            lbl.pack(side="left", padx=5)
            self.step_labels.append(lbl)

        # Content area (scrollable)
        self.content_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # Navigation buttons
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.pack(fill="x", padx=20, pady=(0, 15))

        self.btn_prev = ctk.CTkButton(
            nav_frame, text="< Précédent", width=140, command=self._prev_step
        )
        self.btn_prev.pack(side="left")

        self.btn_next = ctk.CTkButton(
            nav_frame, text="Suivant >", width=140, command=self._next_step
        )
        self.btn_next.pack(side="right")

        self._show_step(1)

    def _update_step_indicator(self):
        for i, lbl in enumerate(self.step_labels):
            step_num = i + 1
            if step_num == self.current_step:
                lbl.configure(fg_color=("#3B8ED0", "#1F6AA5"), text_color="white")
            elif step_num < self.current_step:
                lbl.configure(fg_color=("#2FA572", "#2FA572"), text_color="white")
            else:
                lbl.configure(fg_color=("gray75", "gray30"), text_color=("gray40", "gray60"))

    def _clear_content(self):
        for widget in self.content_scroll.winfo_children():
            widget.destroy()

    def _show_step(self, step: int):
        self.current_step = step
        self._update_step_indicator()
        self._clear_content()

        self.btn_prev.configure(state="normal" if step > 1 else "disabled")

        if step == 1:
            self._build_step_a()
            self.btn_next.configure(text="Suivant >", command=self._next_step)
        elif step == 2:
            self._build_step_b()
            self.btn_next.configure(text="Suivant >", command=self._next_step)
        elif step == 3:
            self._build_step_c()
            self.btn_next.configure(text="Enregistrer", command=self._save_session)

    def _prev_step(self):
        if self.current_step > 1:
            self._collect_current_step()
            self._show_step(self.current_step - 1)

    def _next_step(self):
        if self.current_step < 3:
            self._collect_current_step()
            self._show_step(self.current_step + 1)

    def _collect_current_step(self):
        """Collect data from current step widgets."""
        if self.current_step == 1:
            self._collect_step_a()
        elif self.current_step == 2:
            self._collect_step_b()
        elif self.current_step == 3:
            self._collect_step_c()

    # ── STEP A: Session Info ────────────────────────────────

    def _build_step_a(self):
        parent = self.content_scroll

        header = ctk.CTkLabel(
            parent, text="Informations de la session",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        header.pack(anchor="w", pady=(10, 15))

        # Setup selection
        setups = self.db.get_setups()
        setup_names = [s["nom"] for s in setups]
        self._setup_list = setups

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text="Setup arme :", width=160, anchor="w").pack(side="left")
        self.setup_combo = ctk.CTkComboBox(
            row, values=setup_names if setup_names else ["Aucun setup"],
            width=300, command=self._on_setup_changed,
        )
        self.setup_combo.pack(side="left", padx=10)
        if setup_names:
            prev = self.session_data.get("setup_nom", setup_names[0])
            if prev in setup_names:
                self.setup_combo.set(prev)
            else:
                self.setup_combo.set(setup_names[0])

        # Date
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text="Date :", width=160, anchor="w").pack(side="left")
        self.date_entry = ctk.CTkEntry(row, width=200)
        self.date_entry.pack(side="left", padx=10)
        self.date_entry.insert(0, self.session_data.get("date", date.today().isoformat()))

        # Lieu
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text="Lieu / Stand :", width=160, anchor="w").pack(side="left")
        self.lieu_entry = ctk.CTkEntry(row, width=300)
        self.lieu_entry.pack(side="left", padx=10)
        self.lieu_entry.insert(0, self.session_data.get("lieu", ""))

        # Phase
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text="Phase :", width=160, anchor="w").pack(side="left")
        self.phase_combo = ctk.CTkComboBox(
            row, values=["Phase 1 (Charge)", "Phase 2 (CBTO/Jump)"], width=250,
        )
        self.phase_combo.pack(side="left", padx=10)
        self.phase_combo.set(self.session_data.get("phase", "Phase 1 (Charge)"))

        # ── Météo ──
        meteo_header = ctk.CTkLabel(
            parent, text="Conditions météo",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        meteo_header.pack(anchor="w", pady=(20, 10))

        meteo = self.session_data.get("meteo", {})

        grid = ctk.CTkFrame(parent, fg_color="transparent")
        grid.pack(fill="x", pady=5)

        fields = [
            ("Température (°C)", "temperature", "20"),
            ("Vent (m/s)", "vent_force", "0"),
            ("Dir. vent", "vent_dir", ""),
            ("Humidité (%)", "hygro", "50"),
            ("Altitude (m)", "altitude", "0"),
            ("Pression (hPa)", "pression", "1013"),
        ]

        self.meteo_entries = {}
        for i, (label, key, default) in enumerate(fields):
            r, c = divmod(i, 3)
            ctk.CTkLabel(grid, text=label, anchor="w").grid(
                row=r * 2, column=c, padx=10, pady=(5, 0), sticky="w"
            )
            entry = ctk.CTkEntry(grid, width=140)
            entry.grid(row=r * 2 + 1, column=c, padx=10, pady=(0, 5), sticky="w")
            entry.insert(0, str(meteo.get(key, default)))
            self.meteo_entries[key] = entry

    def _on_setup_changed(self, value):
        pass

    def _collect_step_a(self):
        setups = self._setup_list if hasattr(self, "_setup_list") else []
        selected_name = self.setup_combo.get() if hasattr(self, "setup_combo") else ""
        setup_id = None
        for s in setups:
            if s["nom"] == selected_name:
                setup_id = s["id"]
                self._setup_cache = s
                break

        self.session_data["setup_id"] = setup_id
        self.session_data["setup_nom"] = selected_name
        self.session_data["date"] = self.date_entry.get() if hasattr(self, "date_entry") else ""
        self.session_data["lieu"] = self.lieu_entry.get() if hasattr(self, "lieu_entry") else ""
        self.session_data["phase"] = self.phase_combo.get() if hasattr(self, "phase_combo") else ""

        meteo = {}
        if hasattr(self, "meteo_entries"):
            for key, entry in self.meteo_entries.items():
                meteo[key] = entry.get()
        self.session_data["meteo"] = meteo

        # Cache powder info
        if setup_id:
            composants = self.db.get_composants(setup_id)
            for c in composants:
                if c["type"] == "Poudre":
                    self._powder_cache = c.get("details", {})
                    break

    # ── STEP B: Serie Parameters ────────────────────────────

    def _build_step_b(self):
        parent = self.content_scroll

        header = ctk.CTkLabel(
            parent, text="Paramètres de la série",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        header.pack(anchor="w", pady=(10, 15))

        # Get powder limits
        charge_min = 35.0
        charge_max = 41.5
        if self._powder_cache:
            charge_min = self._powder_cache.get("charge_min_gr", 35.0)
            charge_max = self._powder_cache.get("charge_max_gr", 41.5)

        # Charge
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text="Charge (gr) :", width=160, anchor="w").pack(side="left")
        self.charge_entry = ctk.CTkEntry(row, width=100)
        self.charge_entry.pack(side="left", padx=10)
        self.charge_entry.insert(0, str(self.serie_data.get("charge_gr", "")))

        self.charge_warning = ctk.CTkLabel(row, text="", font=ctk.CTkFont(size=12))
        self.charge_warning.pack(side="left", padx=10)

        self.charge_entry.bind("<KeyRelease>", self._on_charge_changed)

        # Charge slider
        slider_frame = ctk.CTkFrame(parent, fg_color="transparent")
        slider_frame.pack(fill="x", pady=(0, 5), padx=(160, 0))
        ctk.CTkLabel(slider_frame, text=f"{charge_min}", font=ctk.CTkFont(size=11)).pack(side="left")
        self.charge_slider = ctk.CTkSlider(
            slider_frame, from_=charge_min, to=charge_max,
            width=300, command=self._on_slider_changed,
        )
        self.charge_slider.pack(side="left", padx=10)
        ctk.CTkLabel(slider_frame, text=f"{charge_max}", font=ctk.CTkFont(size=11)).pack(side="left")

        initial_charge = self.serie_data.get("charge_gr", (charge_min + charge_max) / 2)
        if isinstance(initial_charge, str) and initial_charge:
            try:
                initial_charge = float(initial_charge)
            except ValueError:
                initial_charge = (charge_min + charge_max) / 2
        elif not initial_charge:
            initial_charge = (charge_min + charge_max) / 2
        self.charge_slider.set(float(initial_charge))

        # OAL
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text="OAL (mm) :", width=160, anchor="w").pack(side="left")
        self.oal_entry = ctk.CTkEntry(row, width=100)
        self.oal_entry.pack(side="left", padx=10)
        self.oal_entry.insert(0, str(self.serie_data.get("oal_mm", "")))
        self.oal_inch_label = ctk.CTkLabel(row, text="", font=ctk.CTkFont(size=12))
        self.oal_inch_label.pack(side="left")
        self.oal_entry.bind("<KeyRelease>", self._on_oal_changed)

        # CBTO
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text="CBTO (mm) :", width=160, anchor="w").pack(side="left")
        self.cbto_entry = ctk.CTkEntry(row, width=100)
        self.cbto_entry.pack(side="left", padx=10)
        default_cbto = self.serie_data.get("cbto_mm", "")
        if not default_cbto and self._setup_cache:
            default_cbto = 58.07  # 20 thou de jump par défaut
        self.cbto_entry.insert(0, str(default_cbto))
        self.cbto_inch_label = ctk.CTkLabel(row, text="", font=ctk.CTkFont(size=12))
        self.cbto_inch_label.pack(side="left")
        self.cbto_entry.bind("<KeyRelease>", self._on_cbto_changed)

        # Jump display
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text="Jump :", width=160, anchor="w").pack(side="left")
        self.jump_label = ctk.CTkLabel(
            row, text="", font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.jump_label.pack(side="left", padx=10)

        # Nb coups
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text="Nombre de coups :", width=160, anchor="w").pack(side="left")
        self.nb_coups_combo = ctk.CTkComboBox(
            row, values=["3", "5", "10"], width=100,
        )
        self.nb_coups_combo.pack(side="left", padx=10)
        self.nb_coups_combo.set(str(self.serie_data.get("nb_coups", "5")))

        # Distance
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text="Distance (m) :", width=160, anchor="w").pack(side="left")
        self.distance_entry = ctk.CTkEntry(row, width=100)
        self.distance_entry.pack(side="left", padx=10)
        self.distance_entry.insert(0, str(self.serie_data.get("distance_m", "100")))

        # Notes
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text="Notes série :", width=160, anchor="w").pack(side="left", anchor="n")
        self.serie_notes = ctk.CTkTextbox(row, width=350, height=60)
        self.serie_notes.pack(side="left", padx=10)
        self.serie_notes.insert("1.0", self.serie_data.get("notes", ""))

        # Trigger conversion displays
        self._on_cbto_changed(None)
        self._on_oal_changed(None)
        self._on_charge_changed(None)

    def _on_slider_changed(self, value):
        self.charge_entry.delete(0, "end")
        self.charge_entry.insert(0, f"{value:.1f}")
        self._on_charge_changed(None)

    def _on_charge_changed(self, event):
        try:
            charge = float(self.charge_entry.get())
            charge_max = 41.5
            if self._powder_cache:
                charge_max = self._powder_cache.get("charge_max_gr", 41.5)
            level = charge_warning_level(charge, charge_max)
            if level == "danger":
                self.charge_warning.configure(
                    text="DANGER : Charge > MAX SAAMI !",
                    text_color="red",
                )
                self.charge_entry.configure(border_color="red")
            elif level == "caution":
                self.charge_warning.configure(
                    text="ATTENTION : > 95% du max",
                    text_color="orange",
                )
                self.charge_entry.configure(border_color="orange")
            else:
                self.charge_warning.configure(text="", text_color="white")
                self.charge_entry.configure(border_color=("gray50", "gray30"))
        except ValueError:
            self.charge_warning.configure(text="", text_color="white")

    def _on_oal_changed(self, event):
        try:
            oal_mm = float(self.oal_entry.get())
            self.oal_inch_label.configure(text=f'= {mm_to_inch(oal_mm):.3f}"')
        except ValueError:
            self.oal_inch_label.configure(text="")

    def _on_cbto_changed(self, event):
        try:
            cbto_mm = float(self.cbto_entry.get())
            self.cbto_inch_label.configure(text=f'= {mm_to_inch(cbto_mm):.3f}"')

            cbto_lands = 58.57
            if self._setup_cache and self._setup_cache.get("cbto_lands_mm"):
                cbto_lands = self._setup_cache["cbto_lands_mm"]

            jump_mm = calculate_jump_mm(cbto_lands, cbto_mm)
            jump_thou = calculate_jump_thou(cbto_lands, cbto_mm)
            self.jump_label.configure(
                text=f"{jump_mm:.2f} mm = {jump_thou:.1f} thou "
                     f"(depuis lands {cbto_lands:.2f} mm)"
            )
        except ValueError:
            self.cbto_inch_label.configure(text="")
            self.jump_label.configure(text="")

    def _collect_step_b(self):
        self.serie_data["charge_gr"] = self.charge_entry.get() if hasattr(self, "charge_entry") else ""
        self.serie_data["oal_mm"] = self.oal_entry.get() if hasattr(self, "oal_entry") else ""
        self.serie_data["cbto_mm"] = self.cbto_entry.get() if hasattr(self, "cbto_entry") else ""
        self.serie_data["nb_coups"] = self.nb_coups_combo.get() if hasattr(self, "nb_coups_combo") else "5"
        self.serie_data["distance_m"] = self.distance_entry.get() if hasattr(self, "distance_entry") else "100"
        self.serie_data["notes"] = self.serie_notes.get("1.0", "end-1c") if hasattr(self, "serie_notes") else ""

    # ── STEP C: Velocities & Results ────────────────────────

    def _build_step_c(self):
        parent = self.content_scroll

        header = ctk.CTkLabel(
            parent, text="Saisie des vitesses & résultats",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        header.pack(anchor="w", pady=(10, 15))

        nb_coups = int(self.serie_data.get("nb_coups", 5))

        # Velocity entries
        vel_frame = ctk.CTkFrame(parent, fg_color="transparent")
        vel_frame.pack(fill="x", pady=5)

        self.velocity_entries = []
        prev_velocities = self.serie_data.get("vitesses", [])

        for i in range(nb_coups):
            row = ctk.CTkFrame(vel_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"V{i+1} (fps) :", width=100, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, width=120)
            entry.pack(side="left", padx=10)
            if i < len(prev_velocities):
                entry.insert(0, str(prev_velocities[i]))
            entry.bind("<KeyRelease>", self._update_stats)
            self.velocity_entries.append(entry)

        # Real-time stats display
        stats_frame = ctk.CTkFrame(parent, corner_radius=10)
        stats_frame.pack(fill="x", pady=15, padx=5)

        ctk.CTkLabel(
            stats_frame, text="Statistiques temps réel",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=15, pady=(10, 5))

        stats_grid = ctk.CTkFrame(stats_frame, fg_color="transparent")
        stats_grid.pack(fill="x", padx=15, pady=(0, 10))

        self.stat_labels = {}
        stat_items = [
            ("v_moy_fps", "V moyenne (fps)"),
            ("v_moy_ms", "V moyenne (m/s)"),
            ("es", "ES (fps)"),
            ("sd", "SD (fps)"),
        ]
        for i, (key, label) in enumerate(stat_items):
            ctk.CTkLabel(stats_grid, text=label, anchor="w").grid(
                row=i, column=0, padx=10, pady=3, sticky="w"
            )
            val_lbl = ctk.CTkLabel(
                stats_grid, text="—",
                font=ctk.CTkFont(size=14, weight="bold"),
            )
            val_lbl.grid(row=i, column=1, padx=20, pady=3, sticky="w")
            self.stat_labels[key] = val_lbl

        # ES color indicator
        self.es_indicator = ctk.CTkLabel(
            stats_frame, text="", font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=6, width=200,
        )
        self.es_indicator.pack(anchor="w", padx=15, pady=(0, 10))

        # ── Pressure signs ──
        pression_header = ctk.CTkLabel(
            parent, text="Signes de surpression",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        pression_header.pack(anchor="w", pady=(15, 5))

        self.pression_vars = {}
        signs = [
            ("cratering", "Crayon de feu (primer cratering)"),
            ("sticky_bolt", "Extraction difficile (sticky bolt)"),
            ("flat_primer", "Amorce plate ou dépassante"),
            ("case_blackening", "Noircissement corps étui"),
        ]
        prev_signs = self.serie_data.get("signes_pression", [])
        for key, label in signs:
            var = ctk.BooleanVar(value=key in prev_signs)
            cb = ctk.CTkCheckBox(
                parent, text=label, variable=var,
                command=self._check_pression,
            )
            cb.pack(anchor="w", padx=20, pady=2)
            self.pression_vars[key] = var

        self.pression_alert = ctk.CTkLabel(
            parent, text="", font=ctk.CTkFont(size=13, weight="bold"),
            text_color="red",
        )
        self.pression_alert.pack(anchor="w", padx=20, pady=(5, 10))

        # ── Groupement ──
        grp_header = ctk.CTkLabel(
            parent, text="Groupement",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        grp_header.pack(anchor="w", pady=(10, 5))

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text="Groupement (mm) :", width=160, anchor="w").pack(side="left")
        self.group_entry = ctk.CTkEntry(row, width=100)
        self.group_entry.pack(side="left", padx=10)
        self.group_entry.insert(0, str(self.serie_data.get("groupement_mm", "")))
        self.group_moa_label = ctk.CTkLabel(
            row, text="", font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.group_moa_label.pack(side="left", padx=10)
        self.group_entry.bind("<KeyRelease>", self._on_group_changed)

        # Observations
        ctk.CTkLabel(
            parent, text="Observations :",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", pady=(15, 5))
        self.obs_text = ctk.CTkTextbox(parent, width=500, height=80)
        self.obs_text.pack(anchor="w", padx=20, pady=(0, 10))
        self.obs_text.insert("1.0", self.serie_data.get("observations", ""))

        # Trigger initial calculations
        self._update_stats(None)
        self._check_pression()
        self._on_group_changed(None)

    def _get_velocities(self) -> List[float]:
        vels = []
        for entry in self.velocity_entries:
            try:
                v = float(entry.get())
                vels.append(v)
            except ValueError:
                pass
        return vels

    def _update_stats(self, event):
        vels = self._get_velocities()
        if len(vels) >= 2:
            v_moy = calculate_mean(vels)
            es = calculate_es(vels)
            sd = calculate_sd(vels)

            from utils.conversions import fps_to_ms
            self.stat_labels["v_moy_fps"].configure(text=f"{v_moy:.1f}")
            self.stat_labels["v_moy_ms"].configure(text=f"{fps_to_ms(v_moy):.1f}")
            self.stat_labels["es"].configure(text=f"{es:.1f}")
            self.stat_labels["sd"].configure(text=f"{sd:.1f}")

            color = es_color(es)
            color_map = {
                "green": ("#2FA572", "ES < 15 fps"),
                "orange": ("#E8A317", "ES 15-30 fps"),
                "red": ("#E04040", "ES > 30 fps"),
            }
            c, txt = color_map[color]
            self.es_indicator.configure(
                text=f"  {txt}  ", fg_color=c, text_color="white",
            )
            self.stat_labels["es"].configure(text_color=c)
        elif len(vels) == 1:
            from utils.conversions import fps_to_ms
            self.stat_labels["v_moy_fps"].configure(text=f"{vels[0]:.1f}")
            self.stat_labels["v_moy_ms"].configure(text=f"{fps_to_ms(vels[0]):.1f}")
            self.stat_labels["es"].configure(text="—")
            self.stat_labels["sd"].configure(text="—")
            self.es_indicator.configure(text="", fg_color="transparent")
        else:
            for key in self.stat_labels:
                self.stat_labels[key].configure(text="—")
            self.es_indicator.configure(text="", fg_color="transparent")

    def _check_pression(self):
        any_checked = any(v.get() for v in self.pression_vars.values())
        if any_checked:
            self.pression_alert.configure(
                text="ALERTE : Surpression possible – ne pas augmenter la charge !"
            )
        else:
            self.pression_alert.configure(text="")

    def _on_group_changed(self, event):
        try:
            grp_mm = float(self.group_entry.get())
            distance = float(self.serie_data.get("distance_m", 100))
            moa = mm_to_moa(grp_mm, distance)
            self.group_moa_label.configure(text=f"= {moa:.2f} MOA @ {distance:.0f}m")
        except ValueError:
            self.group_moa_label.configure(text="")

    def _collect_step_c(self):
        self.serie_data["vitesses"] = self._get_velocities()
        signs = [k for k, v in self.pression_vars.items() if v.get()]
        self.serie_data["signes_pression"] = signs
        try:
            self.serie_data["groupement_mm"] = float(self.group_entry.get())
        except (ValueError, AttributeError):
            self.serie_data["groupement_mm"] = None
        self.serie_data["observations"] = self.obs_text.get("1.0", "end-1c") if hasattr(self, "obs_text") else ""

    # ── Save ────────────────────────────────────────────────

    def _save_session(self):
        self._collect_current_step()

        # Validate required fields
        if not self.session_data.get("setup_id"):
            self._show_error("Veuillez sélectionner un setup arme.")
            return

        charge_str = self.serie_data.get("charge_gr", "")
        try:
            charge_gr = float(charge_str)
        except (ValueError, TypeError):
            self._show_error("Veuillez saisir une charge valide.")
            return

        vels = self.serie_data.get("vitesses", [])

        # Calculate stats
        es = calculate_es(vels) if len(vels) >= 2 else None
        sd = calculate_sd(vels) if len(vels) >= 2 else None
        v_moy = calculate_mean(vels) if vels else None

        # Calculate jump
        cbto_mm = None
        jump_mm = None
        try:
            cbto_mm = float(self.serie_data.get("cbto_mm", ""))
            cbto_lands = 58.57
            if self._setup_cache and self._setup_cache.get("cbto_lands_mm"):
                cbto_lands = self._setup_cache["cbto_lands_mm"]
            jump_mm = calculate_jump_mm(cbto_lands, cbto_mm)
        except (ValueError, TypeError):
            pass

        oal_mm = None
        try:
            oal_mm = float(self.serie_data.get("oal_mm", ""))
        except (ValueError, TypeError):
            pass

        distance_m = 100
        try:
            distance_m = float(self.serie_data.get("distance_m", 100))
        except (ValueError, TypeError):
            pass

        # Create session
        session_id = self.db.create_session({
            "setup_id": self.session_data["setup_id"],
            "date": self.session_data.get("date", date.today().isoformat()),
            "lieu": self.session_data.get("lieu", ""),
            "meteo": self.session_data.get("meteo", {}),
            "phase": self.session_data.get("phase", "Phase 1"),
            "notes": self.session_data.get("notes", ""),
        })

        # Create serie
        self.db.create_serie({
            "session_id": session_id,
            "charge_gr": charge_gr,
            "oal_mm": oal_mm,
            "cbto_mm": cbto_mm,
            "jump_mm": jump_mm,
            "nb_coups": int(self.serie_data.get("nb_coups", 5)),
            "vitesses": vels,
            "es": es,
            "sd": sd,
            "v_moy": v_moy,
            "groupement_mm": self.serie_data.get("groupement_mm"),
            "distance_m": distance_m,
            "signes_pression": self.serie_data.get("signes_pression", []),
            "observations": self.serie_data.get("observations", ""),
        })

        # Reset form
        self.session_data = {}
        self.serie_data = {}
        self._show_step(1)

        # Show success
        self._show_success("Session enregistrée avec succès !")

        if self.on_session_saved:
            self.on_session_saved()

    def _show_error(self, message: str):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Erreur")
        dialog.geometry("400x150")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        ctk.CTkLabel(dialog, text=message, wraplength=350, text_color="red").pack(
            expand=True, padx=20, pady=20,
        )
        ctk.CTkButton(dialog, text="OK", command=dialog.destroy, width=100).pack(
            pady=(0, 20),
        )

    def _show_success(self, message: str):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Succès")
        dialog.geometry("400x150")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        ctk.CTkLabel(dialog, text=message, wraplength=350, text_color="#2FA572").pack(
            expand=True, padx=20, pady=20,
        )
        ctk.CTkButton(dialog, text="OK", command=dialog.destroy, width=100).pack(
            pady=(0, 20),
        )
