"""Mes Setups module – manage rifle setups and components."""

import customtkinter as ctk
import json
from typing import Optional, Dict, Callable

from utils.database import Database
from utils.conversions import mm_to_inch


class SetupsFrame(ctk.CTkFrame):
    def __init__(self, parent, db: Database):
        super().__init__(parent, fg_color="transparent")
        self.db = db
        self.selected_setup_id: Optional[int] = None
        self._build_ui()

    def _build_ui(self):
        title = ctk.CTkLabel(
            self, text="Mes Setups", font=ctk.CTkFont(size=24, weight="bold")
        )
        title.pack(pady=(10, 15), anchor="w", padx=20)

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=20)

        # Left panel: list
        left = ctk.CTkFrame(main, width=280)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        ctk.CTkLabel(left, text="Armes", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=10, pady=(10, 5)
        )

        self.setup_list_frame = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.setup_list_frame.pack(fill="both", expand=True, padx=5, pady=5)

        btn_frame = ctk.CTkFrame(left, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkButton(
            btn_frame, text="+ Nouveau Setup", command=self._new_setup, height=32,
        ).pack(fill="x")

        # Right panel: detail
        self.detail_frame = ctk.CTkScrollableFrame(main, fg_color="transparent")
        self.detail_frame.pack(side="left", fill="both", expand=True)

        self._refresh_list()

    def _refresh_list(self):
        for w in self.setup_list_frame.winfo_children():
            w.destroy()

        setups = self.db.get_setups()
        if not setups:
            ctk.CTkLabel(
                self.setup_list_frame, text="Aucun setup.\nCliquez + pour en créer.",
                text_color="gray50",
            ).pack(pady=20)
            return

        for setup in setups:
            btn = ctk.CTkButton(
                self.setup_list_frame,
                text=f"{setup['nom']}\n{setup['calibre']}",
                anchor="w",
                height=50,
                fg_color=("gray75", "gray25") if setup["id"] != self.selected_setup_id else ("#3B8ED0", "#1F6AA5"),
                hover_color=("#3B8ED0", "#1F6AA5"),
                command=lambda sid=setup["id"]: self._select_setup(sid),
            )
            btn.pack(fill="x", pady=2)

    def _select_setup(self, setup_id: int):
        self.selected_setup_id = setup_id
        self._refresh_list()
        self._show_detail(setup_id)

    def _show_detail(self, setup_id: int):
        for w in self.detail_frame.winfo_children():
            w.destroy()

        setup = self.db.get_setup(setup_id)
        if not setup:
            return

        # Header with action buttons
        header = ctk.CTkFrame(self.detail_frame, fg_color="transparent")
        header.pack(fill="x", pady=(10, 15))

        ctk.CTkLabel(
            header, text=setup["nom"],
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(side="left")

        ctk.CTkButton(
            header, text="Supprimer", width=90, height=28,
            fg_color="#E04040", hover_color="#C03030",
            command=lambda: self._delete_setup(setup_id),
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            header, text="Modifier", width=90, height=28,
            command=lambda: self._edit_setup(setup_id),
        ).pack(side="right", padx=5)

        # Setup info
        info_frame = ctk.CTkFrame(self.detail_frame, corner_radius=10)
        info_frame.pack(fill="x", pady=5)

        fields = [
            ("Calibre", setup.get("calibre", "")),
            ("Canon", f"{setup.get('longueur_canon_mm', '')} mm"
                      f" ({mm_to_inch(setup.get('longueur_canon_mm', 0)):.1f}\")" if setup.get("longueur_canon_mm") else ""),
            ("Pas de rayure", setup.get("twist", "")),
            ("Suppresseur", setup.get("suppresseur", "")),
            ("Lunette", setup.get("lunette", "")),
            ("Chrono", setup.get("chrono", "")),
            ("CBTO Lands", f"{setup.get('cbto_lands_mm', '')} mm"
                           f" ({mm_to_inch(setup.get('cbto_lands_mm', 0)):.3f}\")" if setup.get("cbto_lands_mm") else ""),
            ("OAL Ref", f"{setup.get('oal_ref_mm', '')} mm"
                        f" ({mm_to_inch(setup.get('oal_ref_mm', 0)):.3f}\")" if setup.get("oal_ref_mm") else ""),
        ]
        for i, (label, value) in enumerate(fields):
            if not value:
                continue
            row = ctk.CTkFrame(info_frame, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=3)
            ctk.CTkLabel(row, text=f"{label} :", width=140, anchor="w",
                         text_color="gray60").pack(side="left")
            ctk.CTkLabel(row, text=str(value), anchor="w").pack(side="left")

        if setup.get("notes"):
            row = ctk.CTkFrame(info_frame, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=3)
            ctk.CTkLabel(row, text="Notes :", width=140, anchor="w",
                         text_color="gray60").pack(side="left")
            ctk.CTkLabel(row, text=setup["notes"], anchor="w", wraplength=400).pack(side="left")

        # Components
        ctk.CTkLabel(
            self.detail_frame, text="Composants",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", pady=(20, 10))

        composants = self.db.get_composants(setup_id)
        if not composants:
            ctk.CTkLabel(
                self.detail_frame, text="Aucun composant enregistré.",
                text_color="gray50",
            ).pack(anchor="w", padx=10)
        else:
            for comp in composants:
                comp_frame = ctk.CTkFrame(self.detail_frame, corner_radius=8)
                comp_frame.pack(fill="x", pady=3)

                comp_header = ctk.CTkFrame(comp_frame, fg_color="transparent")
                comp_header.pack(fill="x", padx=10, pady=(8, 2))

                type_colors = {
                    "Ogive": "#3B8ED0",
                    "Poudre": "#E8A317",
                    "Amorce": "#2FA572",
                    "Étuis": "#9B59B6",
                }
                type_color = type_colors.get(comp["type"], "gray50")

                ctk.CTkLabel(
                    comp_header, text=comp["type"],
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=type_color,
                ).pack(side="left")

                ctk.CTkLabel(
                    comp_header,
                    text=f"{comp.get('marque', '')} {comp.get('modele', '')}",
                    font=ctk.CTkFont(size=13),
                ).pack(side="left", padx=15)

                ctk.CTkButton(
                    comp_header, text="X", width=28, height=28,
                    fg_color="#E04040", hover_color="#C03030",
                    command=lambda cid=comp["id"]: self._delete_composant(cid, setup_id),
                ).pack(side="right")

                # Details
                details = comp.get("details", {})
                if details:
                    det_frame = ctk.CTkFrame(comp_frame, fg_color="transparent")
                    det_frame.pack(fill="x", padx=25, pady=(0, 8))
                    for k, v in details.items():
                        if isinstance(v, dict):
                            txt = ", ".join(f"{mk}: {mv}" for mk, mv in v.items())
                        else:
                            txt = str(v)
                        ctk.CTkLabel(
                            det_frame,
                            text=f"{k}: {txt}",
                            font=ctk.CTkFont(size=11),
                            text_color="gray60",
                        ).pack(anchor="w")

        ctk.CTkButton(
            self.detail_frame, text="+ Ajouter composant", height=32,
            command=lambda: self._add_composant(setup_id),
        ).pack(anchor="w", pady=10)

    def _new_setup(self):
        self._open_setup_dialog()

    def _edit_setup(self, setup_id: int):
        setup = self.db.get_setup(setup_id)
        self._open_setup_dialog(setup)

    def _open_setup_dialog(self, existing: Optional[Dict] = None):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Modifier Setup" if existing else "Nouveau Setup")
        dialog.geometry("500x650")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        scroll = ctk.CTkScrollableFrame(dialog)
        scroll.pack(fill="both", expand=True, padx=15, pady=15)

        entries = {}
        fields = [
            ("nom", "Nom de l'arme", ""),
            ("calibre", "Calibre", ""),
            ("longueur_canon_mm", "Longueur canon (mm)", ""),
            ("twist", "Pas de rayure", ""),
            ("suppresseur", "Suppresseur", ""),
            ("lunette", "Lunette", ""),
            ("chrono", "Chrono", ""),
            ("cbto_lands_mm", "CBTO Lands (mm)", ""),
            ("oal_ref_mm", "OAL Référence (mm)", ""),
            ("notes", "Notes", ""),
        ]
        for key, label, default in fields:
            ctk.CTkLabel(scroll, text=label, anchor="w").pack(anchor="w", pady=(8, 2))
            entry = ctk.CTkEntry(scroll, width=400)
            entry.pack(anchor="w")
            val = str(existing.get(key, default)) if existing else default
            if val and val != "None":
                entry.insert(0, val)
            entries[key] = entry

        def save():
            data = {}
            for key, entry in entries.items():
                val = entry.get().strip()
                if key in ("longueur_canon_mm", "cbto_lands_mm", "oal_ref_mm"):
                    try:
                        data[key] = float(val) if val else None
                    except ValueError:
                        data[key] = None
                else:
                    data[key] = val
            if existing:
                self.db.update_setup(existing["id"], data)
                self.selected_setup_id = existing["id"]
            else:
                new_id = self.db.create_setup(data)
                self.selected_setup_id = new_id
            dialog.destroy()
            self._refresh_list()
            if self.selected_setup_id:
                self._show_detail(self.selected_setup_id)

        ctk.CTkButton(scroll, text="Enregistrer", command=save).pack(pady=20)

    def _delete_setup(self, setup_id: int):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirmer la suppression")
        dialog.geometry("400x150")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="Supprimer ce setup et toutes ses données associées ?",
            wraplength=350,
        ).pack(expand=True, padx=20, pady=20)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=(0, 20))

        def confirm():
            self.db.delete_setup(setup_id)
            self.selected_setup_id = None
            dialog.destroy()
            self._refresh_list()
            for w in self.detail_frame.winfo_children():
                w.destroy()

        ctk.CTkButton(btn_frame, text="Annuler", command=dialog.destroy, width=100).pack(
            side="left", padx=10
        )
        ctk.CTkButton(
            btn_frame, text="Supprimer", command=confirm, width=100,
            fg_color="#E04040", hover_color="#C03030",
        ).pack(side="left", padx=10)

    def _add_composant(self, setup_id: int):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Ajouter un composant")
        dialog.geometry("450x400")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Type :").pack(anchor="w", padx=20, pady=(15, 2))
        type_combo = ctk.CTkComboBox(
            dialog, values=["Ogive", "Poudre", "Amorce", "Étuis"], width=300,
        )
        type_combo.pack(anchor="w", padx=20)

        ctk.CTkLabel(dialog, text="Marque :").pack(anchor="w", padx=20, pady=(10, 2))
        marque_entry = ctk.CTkEntry(dialog, width=300)
        marque_entry.pack(anchor="w", padx=20)

        ctk.CTkLabel(dialog, text="Modèle :").pack(anchor="w", padx=20, pady=(10, 2))
        modele_entry = ctk.CTkEntry(dialog, width=300)
        modele_entry.pack(anchor="w", padx=20)

        ctk.CTkLabel(dialog, text="Détails JSON (optionnel) :").pack(anchor="w", padx=20, pady=(10, 2))
        details_text = ctk.CTkTextbox(dialog, width=300, height=80)
        details_text.pack(anchor="w", padx=20)
        details_text.insert("1.0", "{}")

        def save():
            details_str = details_text.get("1.0", "end-1c").strip()
            try:
                details = json.loads(details_str) if details_str else {}
            except json.JSONDecodeError:
                details = {}
            self.db.add_composant(setup_id, {
                "type": type_combo.get(),
                "marque": marque_entry.get(),
                "modele": modele_entry.get(),
                "details": details,
            })
            dialog.destroy()
            self._show_detail(setup_id)

        ctk.CTkButton(dialog, text="Ajouter", command=save).pack(pady=20)

    def _delete_composant(self, composant_id: int, setup_id: int):
        self.db.delete_composant(composant_id)
        self._show_detail(setup_id)

    def refresh(self):
        self._refresh_list()
        if self.selected_setup_id:
            self._show_detail(self.selected_setup_id)
