# Plan : Webapp Mobile Reloading Tracker

## Objectif
Créer une webapp Flask accessible depuis le téléphone au stand de tir, qui partage la même base SQLite que l'app desktop.

## Stack technique
- **Backend** : Flask (léger, Python, réutilise directement `utils/database.py`, `conversions.py`, `ballistics.py`)
- **Frontend** : HTML + CSS (Tailwind CDN) + JS vanilla — mobile-first, thème sombre
- **DB** : Même SQLite (`~/.reloading_tracker/reloading.db`)
- **Lancement** : `python3.14 webapp/app.py` → accessible sur le réseau local (ex: `http://192.168.x.x:5000`)

## Structure des fichiers

```
webapp/
├── app.py                  # Flask app + routes API
├── templates/
│   ├── base.html           # Layout (navbar bottom, dark theme)
│   ├── index.html          # Dashboard rapide (dernières sessions)
│   ├── new_session.html    # Saisie session (3 étapes en accordéon)
│   ├── historique.html     # Liste sessions + détail
│   └── setups.html         # Vue setups (lecture seule)
└── static/
    ├── style.css           # Styles custom + dark theme
    └── app.js              # Calculs temps réel ES/SD/conversions
```

## Pages & Fonctionnalités

### 1. Navbar bottom (mobile-first)
- 4 icônes : Accueil | Nouvelle | Historique | Setups
- Fixed en bas de l'écran, style iOS/Android

### 2. Page Nouvelle Session (`/new`)
- **Étape A** : Setup (dropdown), Date (pré-rempli aujourd'hui), Lieu, Phase, Météo (accordéon)
- **Étape B** : Charge (input + warning couleur), OAL, CBTO, Jump (calcul auto JS), Nb coups, Distance
- **Étape C** : Champs vitesses (inputs numériques), Stats temps réel (ES/SD/Vmoy en JS), Signes pression (checkboxes), Groupement (+ MOA auto), Observations
- Bouton "Enregistrer" → POST API → confirmation toast
- Les 3 étapes en accordéon/stepper (pas de page séparée)

### 3. Page Historique (`/history`)
- Liste des sessions groupées par date
- Cards : charge, V moy, ES (coloré), SD, groupement MOA
- Clic → détail avec toutes les vitesses

### 4. Page Setups (`/setups`)
- Vue lecture seule des setups + composants
- Info utile au stand (lands, charge min/max, etc.)

### 5. Page Accueil (`/`)
- Résumé rapide : nombre de sessions, meilleure charge ES, dernier test
- Lien rapide vers "Nouvelle Session"

## Routes API Flask

```
GET  /                    → Dashboard
GET  /new                 → Formulaire nouvelle session
POST /api/session         → Enregistre session + série
GET  /history             → Liste historique
GET  /api/sessions/<id>   → Détail session
GET  /setups              → Vue setups
GET  /api/setups          → JSON setups
GET  /api/setup/<id>/powder → JSON infos poudre (charge min/max)
```

## Calculs côté client (JS)
- ES = max(vitesses) - min(vitesses)
- SD = écart-type échantillon
- V moy = moyenne
- Conversion mm→inch, mm→thou, mm→MOA
- Warning charge vs max SAAMI (95% caution, 100% danger)
- Jump = cbto_lands - cbto_mm (en thou)

## Dépendance ajoutée
- `flask` dans requirements.txt

## Points importants
- Le serveur Flask écoute sur `0.0.0.0:5000` pour être accessible depuis le téléphone sur le même WiFi
- Thème sombre cohérent avec l'app desktop
- Inputs type="number" avec step="0.1" pour faciliter la saisie mobile
- Gros boutons et champs adaptés au tactile
