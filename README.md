# FileRenamer 🚀

**Outil multimédia** de renommage de fichiers avec interface graphique moderne.  
*Optimisé Plex/Jellyfin/Kobo/Komga/Mylar3 — Vidéos, Mangas, Livres, Photos*

***

## ✨ **Ce qu'il fait**

| 🎬 **Vidéos** | 📚 **Livres** | 🎌 **Mangas** | 🖼️ **Photos** |
|---------------|---------------|---------------|---------------|
| `Film (2023).mkv` | `Auteur - Titre (2020).epub` | `Série - T001.cbz` | `20231225_143022.jpg` |
| `Série - S01E05.mkv` | | `Série v001.cbz` | `20231225_vacances.jpg` |

**+ Mode template personnalisé** `{titre} ({année}){ext}`

***

## 🛠️ **Stack technique**

```
🎨 Python 3.8+  •  Tkinter GUI  •  Windows-first
📦 Pillow (optionnel EXIF)
🔨 PyInstaller → FileRenamer.exe (UAC Admin auto)
```

***

## 🚀 **Installation rapide**

### **1️⃣ Cloner**
```bash
git clone https://github.com/<ton-user>/FileRenamer.git
cd FileRenamer
```

### **2️⃣ Dépendances**
```bash
pip install pillow  # ← Photos EXIF (optionnel)
```

### **3️⃣ Lancer**
```
👆 Double-clic `lancer.bat`  (Windows)
OR
python file_renamer.py
```

***

## ⚡ **Créer l'exécutable (.exe)**

**`creer_exe.bat`** → `dist/FileRenamer.exe` en **1 clic**  
*(Auto Python + PyInstaller + UAC Admin)*

```bash
# Ou manuellement
pip install pyinstaller
python -m PyInstaller --onefile --windowed --uac-admin --name FileRenamer file_renamer.py
```

***

## 🎯 **Conventions de nommage**

### **Vidéos Plex/Jellyfin** 🎥
```
titre.2023.1080p.mkv  →  Titre (2023).mkv
serie.s01e05.mkv      →  Serie - S01E05.mkv
```

### **Mangas** 💎
```
🔴 Kobo : One Piece - T001.cbz
🔵 PC/Komga : One Piece v001.cbz  
🟠 Mylar3 : One Piece (1997) #001.cbz
```

### **Photos** 📸
```
IMG_20231225.jpg  →  20231225_143022.jpg
+ suffixe : *_vacances.jpg*
```

### **Template custom** ⚙️
```
Variables : {titre} {année} {saison} {episode} {tome} {auteur} {date}
Exemple : {auteur} - {titre} ({année}) # {tome}{ext}
```

***

## 🎮 **Utilisation (5s)**

```
1️⃣ Choisir dossier (…👆)
2️⃣ Mode (Films/Mangas/Photos...)
3️⃣ 🔍 Prévisualiser
4️⃣ ✅ cocher/décocher → Appliquer
5️⃣ 📋 Rapport (txt/json)
```

**Bonus :** Double-clic ligne → aperçu image/CBZ

***

## 🛡️ **Gestion erreurs**

| Statut | Signification |
|--------|---------------|
| ✓ prêt | OK à renommer |
| ⚠ existe | Fichier déjà présent |
| ═ inchangé | Nom identique |
| ❌ accès refusé | Relance Admin |

**Auto-relance UAC** si besoin !

***

## 📦 **Fichiers du projet**

```
FileRenamer/
├── file_renamer.py     # 🎨 Application principale
├── lancer.bat          # 🚀 Launcher auto Python
├── creer_exe.bat       # 🔨 Build exe 1-clic
└── README.md           # 📖 Ce fichier
```

***