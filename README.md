# FileRenamer

# FileRenamer — Guide d'utilisation

## Prérequis

- Python 3.8 ou supérieur : https://www.python.org/downloads/
- Pillow (optionnel, pour la date EXIF des photos) :
  ```
  pip install pillow
  ```

## Lancement

Double-cliquez sur `lancer.bat` ou exécutez dans un terminal :
```
python file_renamer.py
```

---

## Conventions de nommage

### 🎬 Vidéos — Plex / Kodi / Emby / Jellyfin
| Type    | Résultat                        |
|---------|---------------------------------|
| Film    | `Titre (2023).mkv`              |
| Série   | `Titre - S01E05.mkv`            |

Le script détecte automatiquement l'année et le numéro S01E05 depuis
le nom d'origine (ex: `titre.2023.1080p.bluray.mkv` → `Titre (2023).mkv`).

---

### 🎌 Mangas

#### Kobo (liseuse)
```
One Piece - T001.cbz
One Piece - T002.cbz
```
→ Tri parfait sur la liseuse, reconnu par la bibliothèque Kobo.

#### PC / Komga / Kavita
```
One Piece v001.cbz
One Piece v002.cbz
```
→ Standard reconnu par la plupart des readers CBZ/CBR sur PC.

#### Mylar3 / ComicRack
```
One Piece (1997) #001.cbz
One Piece (1997) #002.cbz
```
→ Compatible ComicInfo.xml, Mylar3, ComicRack.

**Astuce :** Si tous tes fichiers sont du même manga, remplis le champ
"Nom de série" pour forcer le nom (sinon il est extrait automatiquement).

---

### 📚 Livres
```
Auteur - Titre (2020).epub
Auteur - Titre (2020).pdf
```
Laisse "Auteur" vide si tu ne veux pas le préfixe.

---

### 🖼️ Photos
```
20231225_143022.jpg
20231225_143022_vacances.jpg   ← avec préfixe "vacances"
```
Utilise la date EXIF si Pillow est installé, sinon la date du fichier.

---

### ⚙️ Convention personnalisée
Variables disponibles dans le template :
| Variable   | Contenu                          |
|------------|----------------------------------|
| `{titre}`  | Titre extrait du nom             |
| `{année}`  | Année détectée (ex: 2023)        |
| `{ext}`    | Extension (.mkv, .cbz…)          |
| `{saison}` | Numéro de saison (01)            |
| `{episode}`| Numéro d'épisode (05)            |
| `{tome}`   | Numéro de tome (001)             |
| `{auteur}` | Auteur saisi manuellement        |
| `{date}`   | Date du fichier (YYYYMMDD_HHMMSS)|
| `{prefixe}`| Préfixe saisi manuellement       |

Exemple de template : `{auteur} - {titre} ({année}){ext}`

---

## Utilisation

1. **Choisir un dossier** avec le bouton `…`
2. **Sélectionner l'onglet** correspondant au type de fichier
3. Cliquer sur **🔍 Prévisualiser**
4. **Vérifier** les renommages proposés dans le tableau
5. **Décocher** les lignes à ignorer si besoin
6. Cliquer sur **✅ Appliquer le renommage**

Le bouton "Exporter log" permet de sauvegarder la liste (.txt ou .json).