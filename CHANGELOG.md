# Changelog

Toutes les modifications notables sont documentées ici.
Format : [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/)

---

## [2.0.0] — 2026-03-08

### ✨ Nouveautés

#### Scraper automatique intégré
- **Films & Séries** : recherche automatique sur TMDb à l'ouverture du dossier
- **Séries Animées** : recherche TMDb + fallback automatique AniList si aucun résultat
- **Mangas** : recherche AniList GraphQL (sans clé API, gratuit)
- **Livres** : recherche Open Library (sans clé API, gratuit)
- Bannière de suggestion avec menu déroulant des N premiers résultats
- Bouton **✎ Corriger** : popup pour modifier titre/année avant application
- Bouton **✓ Accepter** : applique le résultat en un clic
- Déclenchement automatique à l'ouverture du dossier, à la sélection de fichiers, et au changement de mode
- Système `_trigger_scrape` avec annulation des requêtes pendantes (anti-doublon)

#### Mode Série Animée
- Nouveau type de contenu dédié dans l'onglet Vidéo
- Numérotation épisodes sur 3 chiffres : `S01E007`
- Recherche prioritaire TMDb TV, fallback AniList si vide
- Bannière étiquetée `🎌 AniList Anime` quand AniList répond

#### Sélection de fichiers individuels
- Bouton **🎬 Fichiers** dans le header pour sélectionner des fichiers un par un
- Priorité sur le scan dossier quand des fichiers sont sélectionnés
- Support multi-sélection natif (`askopenfilenames`)

### 🔧 Corrections de bugs

#### WinError 5 — Accès refusé (NAS / partages réseau SMB)
- Triple méthode de renommage en cascade : `os.rename → shutil.move → shutil.copy2 + os.remove`
- Contourne les restrictions SMB sur NAS Synology, QNAP, partages Windows
- Message d'erreur précis avec code WinError dans le rapport

#### Title case intelligent (`smart_title`)
- `Game Of Thrones` → `Game of Thrones`
- `Attack On Titan` → `Attack on Titan`
- Liste de petits mots préservés : `of`, `on`, `the`, `and`, `de`, `du`, `les`, `et`, `en`...

#### Moteur `build_query` — extraction du titre
- Tirets intra-mots normalisés : `one-piece-tome-84.cbz` → query `"one piece"` ✓
- Groupes release supprimés : `-gismo65`, `-YIFY`, `-YTS`, URLs (`.com`...)
- Découpe sur premier NOISE_WORD : `MULTI`, `FRENCH`, `1080p`, `BluRay`, `WEBRip`, `HEVC`...
- Année extraite AVANT normalisation — évite les collisions de chiffres
- `2001 A Space Odyssey.mkv` → titre `"2001 A Space Odyssey"` (année en position 0 = partie du titre)

#### Livres — extraction auteur automatique
- Format `"Tolkien - Le Seigneur des Anneaux.epub"` → auteur `"Tolkien"` extrait automatiquement
- Query recalculée depuis la partie titre seule
- Fallback sans auteur si Open Library renvoie 0 résultats avec l'auteur

#### `safe_filename` — remplacement par espace
- Caractères interdits Windows (`< > : " / \ | ? *`) remplacés par espace au lieu de tiret
- `"Breaking: Bad"` → `"Breaking Bad"` ✓ (au lieu de `"Breaking- Bad"`)

#### `extract_volume` — détection chiffres fin de nom
- Pattern `.NNN$` ajouté : `One.Piece.042.cbz` → volume 42 ✓

#### Variable `_current_mode`
- Mise à jour immédiate dans `_show_page` (évite le bug de lecture tardive via `_pages['_current']`)

#### `_get_files_for_mode` — méthode reconstruite
- Code parasite retiré (thread AniList mal placé)
- Filtrage correct par extension selon le mode actif

### 🔑 Sécurité
- Clé API TMDb retirée du code source — champ vide par défaut
- L'utilisateur saisit sa propre clé dans Paramètres

### 📦 Build
- `build_release.bat` mis à jour → version 2.0.0 par défaut

---

## [1.0.0] — 2026-02-15

### ✨ Première version publique
- Interface "Terminal Luxe" : palette sombre amber/cyan, navigation latérale iconique
- 5 modes : Films & Séries, Mangas, Livres & BD, Photos, Personnalisé
- Moteur `RenameEngine` pur Python (sans dépendances GUI)
- Conventions : Plex, Kodi, Infuse, MediaPortal, Kobo, Mylar3, Calibre, Adobe, Kindle
- Prévisualisation obligatoire avant application
- Mode multi-titres Films
- Génération `.nfo` Kodi/TMDb
- Export rapport `.txt` / `.json`
- Aperçu miniature images et CBZ (Pillow requis)
- Gestion droits admin Windows (UAC)
- Compilation `.exe` autonome via PyInstaller
