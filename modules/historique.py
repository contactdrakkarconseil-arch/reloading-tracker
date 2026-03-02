"""Historique des sessions module."""

import customtkinter as ctk
import json
from typing import Optional

from utils.database import Database
from utils.conversions import mm_to_inch, mm_to_moa, fps_to_ms
from utils.ballistics import es_color


class HistoriqueFrame(ctk.CTkFrame):
    def __init__(self, parent, db: Database):
        super().__init__(parent, fg_color="transparent")
        self.db = db
        self._build_ui()

    def _build_ui(self):
        title = ctk.CTkLabel(
            self, text="Historique des sessions",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        title.pack(pady=(10, 5), anchor="w", padx=20)

        # Filters
        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(filter_frame, text="Setup :").pack(side="left", padx=(0, 5))
        setups = self.db.get_setups()
        setup_names = ["Tous"] + [s["nom"] for s in setups]
        self._setup_map = {s["nom"]: s["id"] for s in setups}
        self.filter_setup = ctk.CTkComboBox(
            filter_frame, values=setup_names, width=200, command=self._on_filter,
        )
        self.filter_setup.pack(side="left", padx=5)
        self.filter_setup.set("Tous")

        ctk.CTkLabel(filter_frame, text="Phase :").pack(side="left", padx=(20, 5))
        self.filter_phase = ctk.CTkComboBox(
            filter_frame,
            values=["Toutes", "Phase 1 (Charge)", "Phase 2 (CBTO/Jump)"],
            width=180, command=self._on_filter,
        )
        self.filter_phase.pack(side="left", padx=5)
        self.filter_phase.set("Toutes")

        # Split: table left, detail right
        self.split = ctk.CTkFrame(self, fg_color="transparent")
        self.split.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        self.table_frame = ctk.CTkScrollableFrame(self.split, width=550)
        self.table_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.detail_frame = ctk.CTkScrollableFrame(self.split, width=380)
        self.detail_frame.pack(side="right", fill="both")

        self.refresh()

    def _on_filter(self, _=None):
        self.refresh()

    def refresh(self):
        for w in self.table_frame.winfo_children():
            w.destroy()
        for w in self.detail_frame.winfo_children():
            w.destroy()

        setup_name = self.filter_setup.get()
        setup_id = self._setup_map.get(setup_name)

        sessions = self.db.get_sessions(setup_id if setup_name != "Tous" else None)

        phase_filter = self.filter_phase.get()

        if phase_filter != "Toutes":
            sessions = [s for s in sessions if s.get("phase", "") == phase_filter]

        if not sessions:
            ctk.CTkLabel(
                self.table_frame,
                text="Aucune session trouvée.",
                text_color="gray50",
                font=ctk.CTkFont(size=14),
            ).pack(pady=30)
            return

        # Header row
        hdr = ctk.CTkFrame(self.table_frame, fg_color=("gray75", "gray25"), corner_radius=6)
        hdr.pack(fill="x", pady=(0, 5))
        cols = ["Date", "Setup", "Phase", "Séries"]
        widths = [100, 150, 130, 60]
        for col, w in zip(cols, widths):
            ctk.CTkLabel(
                hdr, text=col, width=w,
                font=ctk.CTkFont(size=11, weight="bold"),
            ).pack(side="left", padx=5, pady=5)

        for session in sessions:
            series = self.db.get_series(session["id"])
            row_frame = ctk.CTkFrame(self.table_frame, fg_color="transparent", cursor="hand2")
            row_frame.pack(fill="x", pady=1)

            vals = [
                session.get("date", ""),
                session.get("setup_nom", ""),
                session.get("phase", ""),
                str(len(series)),
            ]
            for val, w in zip(vals, widths):
                lbl = ctk.CTkLabel(row_frame, text=val, width=w, font=ctk.CTkFont(size=12))
                lbl.pack(side="left", padx=5, pady=3)

            # Bind click
            sid = session["id"]
            for child in [row_frame] + list(row_frame.winfo_children()):
                child.bind("<Button-1>", lambda e, s=sid: self._show_session_detail(s))

        # Show first session by default
        if sessions:
            self._show_session_detail(sessions[0]["id"])

    def _show_session_detail(self, session_id: int):
        for w in self.detail_frame.winfo_children():
            w.destroy()

        session = self.db.get_session(session_id)
        if not session:
            return

        # Session info
        ctk.CTkLabel(
            self.detail_frame,
            text=f"Session du {session.get('date', '')}",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", pady=(10, 5))

        info_items = [
            ("Setup", session.get("setup_nom", "")),
            ("Lieu", session.get("lieu", "")),
            ("Phase", session.get("phase", "")),
        ]
        meteo = session.get("meteo", {})
        if meteo:
            temp = meteo.get("temperature", "")
            wind = f"{meteo.get('vent_force', '')} m/s {meteo.get('vent_dir', '')}"
            info_items.append(("Temp", f"{temp} °C"))
            info_items.append(("Vent", wind))
            if meteo.get("pression"):
                info_items.append(("Pression", f"{meteo['pression']} hPa"))

        for label, val in info_items:
            if val and val.strip():
                row = ctk.CTkFrame(self.detail_frame, fg_color="transparent")
                row.pack(fill="x", pady=1)
                ctk.CTkLabel(row, text=f"{label}:", width=80, anchor="w",
                             text_color="gray60", font=ctk.CTkFont(size=11)).pack(side="left")
                ctk.CTkLabel(row, text=val, font=ctk.CTkFont(size=12)).pack(side="left")

        # Series
        series = self.db.get_series(session_id)
        for i, serie in enumerate(series):
            self._build_serie_card(serie, i + 1, session_id)

        # Delete session button
        ctk.CTkButton(
            self.detail_frame, text="Supprimer cette session",
            fg_color="#E04040", hover_color="#C03030",
            height=30, command=lambda: self._delete_session(session_id),
        ).pack(pady=15)

    def _build_serie_card(self, serie: dict, num: int, session_id: int):
        card = ctk.CTkFrame(self.detail_frame, corner_radius=8)
        card.pack(fill="x", pady=5)

        # Serie header
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=10, pady=(8, 2))

        ctk.CTkLabel(
            hdr, text=f"Série #{num}",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left")

        charge_txt = f"{serie['charge_gr']:.1f} gr"
        ctk.CTkLabel(hdr, text=charge_txt, font=ctk.CTkFont(size=13)).pack(side="left", padx=15)

        # Star for charge_retenue
        is_retained = bool(serie.get("charge_retenue"))
        star_btn = ctk.CTkButton(
            hdr, text="★" if is_retained else "☆",
            width=30, height=28,
            fg_color="#E8A317" if is_retained else "gray40",
            hover_color="#E8A317",
            command=lambda: self._toggle_retenue(serie["id"], not is_retained, session_id),
        )
        star_btn.pack(side="right")

        # Stats
        stats_frame = ctk.CTkFrame(card, fg_color="transparent")
        stats_frame.pack(fill="x", padx=10, pady=(2, 8))

        stats = []
        if serie.get("v_moy"):
            stats.append(f"V moy: {serie['v_moy']:.0f} fps")
        if serie.get("es") is not None:
            color = es_color(serie["es"])
            stats.append(f"ES: {serie['es']:.1f} fps")
        if serie.get("sd") is not None:
            stats.append(f"SD: {serie['sd']:.1f} fps")
        if serie.get("groupement_mm") is not None:
            distance = serie.get("distance_m", 100)
            moa = mm_to_moa(serie["groupement_mm"], distance)
            stats.append(f"Grp: {serie['groupement_mm']:.1f}mm ({moa:.2f} MOA)")
        if serie.get("jump_mm") is not None:
            stats.append(f"Jump: {serie['jump_mm']:.2f}mm")

        if stats:
            ctk.CTkLabel(
                stats_frame,
                text="  |  ".join(stats),
                font=ctk.CTkFont(size=11),
                text_color="gray60",
            ).pack(anchor="w")

        # Velocities
        vels = serie.get("vitesses", [])
        if vels:
            vel_txt = ", ".join(f"{v:.0f}" for v in vels)
            ctk.CTkLabel(
                stats_frame, text=f"Vitesses: {vel_txt}",
                font=ctk.CTkFont(size=10), text_color="gray50",
            ).pack(anchor="w")

        # Pressure signs
        signs = serie.get("signes_pression", [])
        if signs:
            ctk.CTkLabel(
                stats_frame,
                text=f"Surpression: {', '.join(signs)}",
                font=ctk.CTkFont(size=11), text_color="red",
            ).pack(anchor="w")

    def _toggle_retenue(self, serie_id: int, retenue: bool, session_id: int):
        self.db.update_serie_charge_retenue(serie_id, retenue)
        self._show_session_detail(session_id)

    def _delete_session(self, session_id: int):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirmer la suppression")
        dialog.geometry("400x150")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="Supprimer cette session et toutes ses séries ?",
            wraplength=350,
        ).pack(expand=True, padx=20, pady=20)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=(0, 20))

        def confirm():
            self.db.delete_session(session_id)
            dialog.destroy()
            self.refresh()

        ctk.CTkButton(btn_frame, text="Annuler", command=dialog.destroy, width=100).pack(
            side="left", padx=10,
        )
        ctk.CTkButton(
            btn_frame, text="Supprimer", command=confirm, width=100,
            fg_color="#E04040", hover_color="#C03030",
        ).pack(side="left", padx=10)
