"""
╔══════════════════════════════════════════════════════════════════╗
║              FileRenamer — Outil de renommage multimédia         ║
║  Vidéos • Livres • Mangas (Kobo/PC) • Photos • Convention custom ║
║  Windows — Python 3.8+  — Tkinter GUI                           ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import re
import sys
import json
import ctypes
import shutil
import stat
import threading
import urllib.request
import urllib.parse
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image, ImageTk
    from PIL.ExifTags import TAGS
    PIL_OK = True
except ImportError:
    PIL_OK = False
    ImageTk = None


# ═══════════════════════════════════════════════════════════════════
#  CONSTANTES
# ═══════════════════════════════════════════════════════════════════

VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv',
              '.m4v', '.ts', '.webm', '.rmvb', '.divx', '.xvid'}
BOOK_EXTS  = {'.pdf', '.epub', '.mobi', '.azw', '.azw3', '.djvu', '.fb2'}
MANGA_EXTS = {'.cbz', '.cbr', '.pdf', '.epub'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff',
              '.tif', '.webp', '.heic', '.raw', '.cr2', '.nef', '.arw'}

NOISE_WORDS = {
    '1080p','720p','480p','4k','2160p','bluray','blu-ray','bdrip','brrip',
    'dvdrip','dvdscr','hdtv','web-dl','webrip','hdrip','remux','x264','x265',
    'h264','h265','avc','hevc','xvid','divx','ac3','dts','aac','mp3','dd5',
    'dd51','truehd','atmos','hdr','hdr10','dovi','repack','proper','extended',
    'theatrical','unrated','directors','cut','retail','limited','internal',
    'yify','yts','ettv','eztv','rarbg','fgt','ion10','qxr','tbs',
    'french','english','vf','vostfr','multi','dubbed','subbed','truefrench',
    'mhd','uhd','sdr','complete','vo','vff',
}

C = {
    'bg':      '#0d1117',
    'surface': '#161b22',
    'panel':   '#1c2128',
    'card':    '#21262d',
    'accent':  '#e8b84b',
    'blue':    '#58a6ff',
    'green':   '#3fb950',
    'red':     '#f85149',
    'orange':  '#d29922',
    'text':    '#e6edf3',
    'muted':   '#8b949e',
    'border':  '#30363d',
    'hover':   '#262c36',
    'manga':   '#ff6b9d',
}


# ═══════════════════════════════════════════════════════════════════
#  MOTEUR DE RENOMMAGE
# ═══════════════════════════════════════════════════════════════════

class RenameEngine:

    _LOWER_WORDS = {
        'a','an','the','and','but','or','nor','at','by','for','in',
        'of','on','to','up','as','de','du','des','le','la','les',
        'un','une','et','ou','en','au','aux','sur','par','dans',
        'avec','sans','sous','x','vs',
    }

    @staticmethod
    def smart_title(text: str) -> str:
        words = text.split()
        result = []
        for i, w in enumerate(words):
            if i == 0 or w.lower() not in RenameEngine._LOWER_WORDS:
                result.append(w.capitalize())
            else:
                result.append(w.lower())
        return ' '.join(result)

    @staticmethod
    def clean_title(raw_name: str) -> str:
        q, _ = RenameEngine.build_query(raw_name)
        return RenameEngine.smart_title(q) if q else ""

    @staticmethod
    def extract_year(raw_name: str) -> str:
        _, y = RenameEngine.build_query(raw_name)
        if y: return y
        m = re.search(r"(19|20)\d{2}", raw_name)
        return m.group(0) if m else ""

    @staticmethod
    def build_query(raw_name: str):
        name = Path(raw_name).stem if ("." in raw_name and "/" not in raw_name and chr(92) not in raw_name) else raw_name
        year = ""
        m = re.search(r"[\s._\-\(]((19|20)\d{2})[\s._\-\)]", name)
        if m:
            year = m.group(1)
        else:
            m = re.search(r"[-._\s]((19|20)\d{2})$", name)
            if m: year = m.group(1)

        # ── Normaliser TOUS les séparateurs -> espace ──────────────
        # points séparateurs (pas d'extension)
        if name.count(".") > 1 and " " not in name:
            name = name.replace(".", " ")
        else:
            name = re.sub(r"(?<=\w)\.(?=\w)", " ", name)
            name = re.sub(r"\.", " ", name)
        name = name.replace("_", " ")
        # tirets isolés : "one-piece" → "one piece"  (sauf tiret dans un mot composé court)
        name = re.sub(r"(?<=\w)-(?=\w)", " ", name)

        # ── Retirer blocs entre parentheses/crochets ──────────────
        name = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", " ", name)

        # ── Retirer numéros d'épisode/volume/tome ─────────────────
        name = re.sub(r"\b[Ss]\d{1,2}[Ee]\d{1,3}(?:[-\s]?[Ee]\d{1,3})?\b", "", name)
        name = re.sub(r"\b\d{1,2}[xX]\d{1,2}\b", "", name)
        name = re.sub(r"\b[Ee]p(?:isode)?\s*\d{1,3}\b", "", name, flags=re.IGNORECASE)
        name = re.sub(r"\b(?:tome|vol(?:ume)?)\s*\d{1,4}\b", "", name, flags=re.IGNORECASE)
        name = re.sub(r"\bv\d{1,3}\b", "", name)
        name = re.sub(r"\bt\d{1,3}\b", "", name, flags=re.IGNORECASE)
        name = re.sub(r"#\d{1,4}", "", name)
        name = re.sub(r"\s+\d{1,4}$", "", name)

        # ── Retirer URLs et groupes release ───────────────────────
        name = re.sub(r"\b\w+ Www\b", "", name, flags=re.IGNORECASE)
        name = re.sub(r"\b\w+\.(?:com|fr|net|org|tv)\b", "", name, flags=re.IGNORECASE)

        # ── Couper sur premier mot bruit ou année ─────────────────
        tokens = name.split()
        cleaned = []
        for i, tok in enumerate(tokens):
            low = re.sub(r"[^a-z0-9]", "", tok.lower())
            if low in NOISE_WORDS: break
            if i > 0 and re.match(r"^(19|20)\d{2}$", tok): break
            cleaned.append(tok)

        result = " ".join(cleaned)
        # Retirer tirets résiduels en début/fin
        result = re.sub(r"\s*[-–—]+\s*$", "", result)
        result = re.sub(r"^\s*[-–—]+\s*", "", result)
        result = re.sub(r"\s+", " ", result).strip()
        return result, year

    @staticmethod
    def extract_season_episode(raw_name: str):
        # Double episode : S01E01E02 ou S01E01-E02
        m = re.search(r'[Ss](\d{1,2})[Ee](\d{1,3})[-]?[Ee](\d{1,3})', raw_name)
        if m:
            return int(m.group(1)), int(m.group(2)), int(m.group(3))
        patterns = [
            r'[Ss](\d{1,2})[Ee](\d{1,3})',
            r'(\d{1,2})[xX](\d{1,2})',
            r'[Ss]eason\s*(\d{1,2})\s*[Ee]p(?:isode)?\s*(\d{1,2})',
        ]
        for p in patterns:
            m = re.search(p, raw_name)
            if m:
                return int(m.group(1)), int(m.group(2)), None
        m = re.search(r'(?:[Ee]p?|episode\s*)(\d{1,3})', raw_name, re.IGNORECASE)
        if m:
            return None, int(m.group(1)), None
        return None, None, None

    @staticmethod
    def extract_volume(raw_name: str):
        patterns = [
            r'(?:tome|vol(?:ume)?)[.\s_-]?(\d{1,4})',   # tome42, vol.7, volume 3
            r'(?<=[_\s\-\.#])([tT])(\d{1,3})(?![a-zA-Z])',  # _T15, -T03
            r'(?<=[_\s\-\.#])([vV])(\d{1,3})(?![a-zA-Z])',  # _v7, _V007
            r'#(\d{1,4})',                                # #018
            r'[\s_.-](\d{1,4})$',                        # bleach_018, One.Piece.042
        ]
        for i, p in enumerate(patterns):
            m = re.search(p, raw_name, re.IGNORECASE)
            if m:
                # patterns 1 et 2 ont le numéro en groupe 2
                grp = 2 if i in (1, 2) else 1
                return int(m.group(grp))
        return None

    @staticmethod
    def safe_filename(name: str) -> str:
        name = re.sub(r'[<>:"/\\|?*]', ' ', name)
        name = re.sub(r'  +', ' ', name)
        return name.strip('. ')
    @staticmethod
    def get_exif_date(filepath: str) -> str:
        if not PIL_OK:
            return ''
        try:
            img = Image.open(filepath)
            exif = img._getexif()
            if exif:
                for tag_id, val in exif.items():
                    if TAGS.get(tag_id) in ('DateTimeOriginal', 'DateTime'):
                        dt = datetime.strptime(val, '%Y:%m:%d %H:%M:%S')
                        return dt.strftime('%Y%m%d_%H%M%S')
        except Exception:
            pass
        return ''

    @staticmethod
    def get_file_date(filepath: str) -> str:
        ts = os.path.getmtime(filepath)
        return datetime.fromtimestamp(ts).strftime('%Y%m%d_%H%M%S')

    # ─ Vidéo ──────────────────────────────────────────────────────

    # Conventions film par logiciel
    # Plex / Emby / Jellyfin : Titre (Année).ext
    # Tous partagent le même format de base — vraie différence sur les séries
    VIDEO_CONVENTIONS = {
        'plex':        ('Plex',                    'Titre (Année).ext'),
        'kodi':        ('Kodi / LibreELEC',        'Titre (Année).ext'),
        'jellyfin':    ('Jellyfin',                'Titre (Année).ext'),
        'emby':        ('Emby',                    'Titre (Année).ext'),
        'tmdb':        ('TMDb / Sonarr / Radarr',  'Titre.Annee.ext'),
    }
    SERIES_CONVENTIONS = {
        'plex':        ('Plex',                   'Titre - s01e01.ext'),   # tiret + minuscules
        'kodi':        ('Kodi / LibreELEC',       'Titre S01E01.ext'),     # pas de tiret
        'jellyfin':    ('Jellyfin',               'Titre S01E01.ext'),     # idem Kodi
        'emby':        ('Emby',                   'Titre S01E01.ext'),     # idem Kodi
        'tmdb':        ('TMDb / Sonarr',          'Titre.S01E01.ext'),     # points
    }

    def rename_movie(self, fp: str, convention: str = 'plex') -> str:
        """
        Conventions films (sources officielles) :
          plex        → Titre (2010).mkv          support.plex.tv
          jellyfin    → Titre (2010).mkv          jellyfin.org/docs
          emby        → Titre (2010).mkv          emby.media/support
          kodi        → Titre (2010).mkv          kodi.wiki (même format)
          infuse      → Titre (2010).mkv          support.firecore.com
          mediaportal → Titre (2010).mkv          team-mediaportal.com (même format)
          tmdb        → Titre.2010.mkv            format points/dots (Radarr/Sonarr)
        Pour les FILMS toutes les apps acceptent "Titre (Année)" — la différence
        est uniquement sur les séries TV.
        """
        p     = Path(fp)
        title = self.clean_title(p.name)
        year  = self.extract_year(p.stem)
        ext   = p.suffix.lower()

        if convention == 'tmdb':
            # Format Radarr/Sonarr avec points — Titre.2010.mkv
            t_dots = title.replace(' ', '.')
            return f"{t_dots}.{year}{ext}" if year else f"{t_dots}{ext}"

        # Toutes les autres conventions : Titre (2010).mkv
        base = f"{title} ({year})" if year else title
        return self.safe_filename(base + ext)

    # Alias pour compat
    def rename_movie_plex(self, fp: str) -> str:
        return self.rename_movie(fp, 'plex')

    def rename_series(self, fp: str, convention: str = 'plex',
                      anime: bool = False) -> str:
        """
        Conventions séries TV (sources officielles) :
          plex        → Titre - s01e01.mkv         support.plex.tv  (tiret + minuscules)
          jellyfin    → Titre S01E01.mkv            jellyfin.org/docs (pas de tiret)
          emby        → Titre S01E01.mkv            emby.media/support (idem Jellyfin)
          kodi        → Titre S01E01.mkv            kodi.wiki/Episodes (scanner cherche SxxEyy)
          infuse      → Titre S01E01.mkv            support.firecore.com (très flexible, S01E01 suffit)
          mediaportal → Titre S01E01.mkv            team-mediaportal.com (SssEee standard)
          tmdb        → Titre.S01E01.mkv            format points (Sonarr/LibreELEC)
        """
        p = Path(fp)
        s, e, e2 = self.extract_season_episode(p.stem)
        title    = self.clean_title(p.name)
        ext      = p.suffix.lower()
        ep_w     = 3 if anime else 2   # 3 chiffres pour anime

        if s is not None and e is not None:
            if e2 is not None:
                ep_str_upper = f"S{s:02d}E{e:0{ep_w}d}-E{e2:0{ep_w}d}"
                ep_str_lower = f"s{s:02d}e{e:0{ep_w}d}-e{e2:0{ep_w}d}"
            else:
                ep_str_upper = f"S{s:02d}E{e:0{ep_w}d}"
                ep_str_lower = f"s{s:02d}e{e:0{ep_w}d}"

            if convention == 'tmdb':
                # Points entre mots — Titre.S01E01.mkv  (Sonarr/LibreELEC)
                t_dots = title.replace(' ', '.')
                return f"{t_dots}.{ep_str_upper}{ext}"
            elif convention == 'plex':
                # Plex officiel : "ShowName - s01e01 - Optional_Info.ext" (tiret + minuscules)
                return self.safe_filename(f"{title} - {ep_str_lower}{ext}")
            elif convention in ('kodi', 'jellyfin', 'emby', 'infuse', 'mediaportal'):
                # Kodi/Jellyfin/Emby/Infuse/MediaPortal : "ShowName S01E01.ext" (pas de tiret, majuscules)
                return self.safe_filename(f"{title} {ep_str_upper}{ext}")
            else:
                # Défaut Plex
                return self.safe_filename(f"{title} - {ep_str_lower}{ext}")

        elif e is not None:
            return self.safe_filename(f"{title} - E{e:03d}{ext}")
        return self.safe_filename(title + ext)


    def generate_nfo(self, folder: str, nfo_type: str = 'tvshow',
                     title: str = '', tmdb_id: str = '') -> str:
        """Genere un fichier .nfo Kodi/TMDb dans le dossier donne."""
        if nfo_type == 'tvshow':
            content = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
            content += '<tvshow>\n'
            if title:
                content += f'  <title>{title}</title>\n'
            if tmdb_id.strip():
                content += f'  <tmdbid>{tmdb_id.strip()}</tmdbid>\n'
                content += f'  <uniqueid type="tmdb" default="true">{tmdb_id.strip()}</uniqueid>\n'
            content += '</tvshow>\n'
            nfo_path = os.path.join(folder, 'tvshow.nfo')
        else:  # movie
            content = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
            content += '<movie>\n'
            if title:
                content += f'  <title>{title}</title>\n'
            if tmdb_id.strip():
                content += f'  <tmdbid>{tmdb_id.strip()}</tmdbid>\n'
                content += f'  <uniqueid type="tmdb" default="true">{tmdb_id.strip()}</uniqueid>\n'
            content += '</movie>\n'
            nfo_path = os.path.join(folder, 'movie.nfo')
        with open(nfo_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return nfo_path

    def rename_series_plex(self, fp: str) -> str:
        return self.rename_series(fp, 'plex')

    # ─ Manga ──────────────────────────────────────────────────────

    def rename_manga_kobo(self, fp: str, series: str = '') -> str:
        """Kobo : Série - T001.ext  (tri alphanumérique parfait sur liseuse)"""
        p   = Path(fp)
        vol = self.extract_volume(p.stem)
        base = self.safe_filename(
            series.strip().title() if series.strip() else self.clean_title(p.name))
        if vol is not None:
            return f"{base} - T{vol:03d}{p.suffix.lower()}"
        return self.safe_filename(base + p.suffix.lower())

    def rename_manga_pc(self, fp: str, series: str = '') -> str:
        """PC/Komga/Kavita : Série v001.ext"""
        p   = Path(fp)
        vol = self.extract_volume(p.stem)
        base = self.safe_filename(
            series.strip().title() if series.strip() else self.clean_title(p.name))
        if vol is not None:
            return f"{base} v{vol:03d}{p.suffix.lower()}"
        return self.safe_filename(base + p.suffix.lower())

    def rename_manga_mylar(self, fp: str, series: str = '', year: str = '') -> str:
        """Mylar3/ComicRack : Série (Année) #001.ext"""
        p   = Path(fp)
        vol = self.extract_volume(p.stem)
        base = self.safe_filename(
            series.strip().title() if series.strip() else self.clean_title(p.name))
        yr   = year.strip() if year.strip() else self.extract_year(p.stem)
        yr_s = f" ({yr})" if yr else ''
        if vol is not None:
            return f"{base}{yr_s} #{vol:03d}{p.suffix.lower()}"
        return self.safe_filename(base + yr_s + p.suffix.lower())

    # ─ Livre ──────────────────────────────────────────────────────

    # Conventions livre par logiciel :
    # Calibre           : Auteur - Titre (Année).ext   — standard bibliothèque
    # Kobo              : Titre - Auteur.ext            — affiché sur liseuse
    # Kindle            : Titre - Auteur.ext            — même format
    # Adobe DE          : Auteur - Titre.ext            — sans année
    # Moon+ Reader      : Titre (Année) - Auteur.ext   — mobile Android
    BOOK_CONVENTIONS = {
        'calibre':  ('Calibre',              'Auteur - Titre (Année).ext'),
        'kobo':     ('Kobo (liseuse)',        'Titre - Auteur.ext'),
        'kindle':   ('Kindle',               'Titre - Auteur.ext'),
        'adobe':    ('Adobe Digital Editions','Auteur - Titre.ext'),
    }

    def rename_book(self, fp: str, author: str = '', convention: str = 'calibre') -> str:
        p     = Path(fp)
        title = self.clean_title(p.name)
        year  = self.extract_year(p.stem)
        ext   = p.suffix.lower()
        au    = self.safe_filename(author.strip().title()) if author.strip() else ''
        yr_s  = f" ({year})" if year else ''

        if convention == 'calibre':
            if au:
                return self.safe_filename(f"{au} - {title}{yr_s}{ext}")
            return self.safe_filename(f"{title}{yr_s}{ext}")
        elif convention in ('kobo', 'kindle'):
            if au:
                return self.safe_filename(f"{title} - {au}{ext}")
            return self.safe_filename(f"{title}{ext}")
        elif convention == 'adobe':
            if au:
                return self.safe_filename(f"{au} - {title}{ext}")
            return self.safe_filename(f"{title}{ext}")
        # fallback
        return self.safe_filename(f"{title}{yr_s}{ext}")

    # ─ Photo ──────────────────────────────────────────────────────

    def rename_photo(self, fp: str, prefix: str = '', use_exif: bool = True) -> str:
        p = Path(fp)
        date_str = self.get_exif_date(fp) if use_exif else ''
        if not date_str:
            date_str = self.get_file_date(fp)
        pref = f"_{self.safe_filename(prefix.strip())}" if prefix.strip() else ''
        return f"{date_str}{pref}{p.suffix.lower()}"

    # ─ Custom ─────────────────────────────────────────────────────

    def rename_custom(self, fp: str, template: str, extra: dict = None) -> str:
        p     = Path(fp)
        extra = extra or {}
        title = self.clean_title(p.name)
        year  = self.extract_year(p.stem)
        s, e, _  = self.extract_season_episode(p.stem)
        vol   = self.extract_volume(p.stem)
        date  = self.get_file_date(fp)
        mapping = {
            'titre':   extra.get('titre', title),
            'année':   extra.get('année', year),
            'ext':     p.suffix.lower(),
            'saison':  f"{s:02d}" if s else '',
            'episode': f"{e:02d}" if e else '',
            'auteur':  extra.get('auteur', ''),
            'tome':    f"{vol:03d}" if vol else '',
            'date':    extra.get('date', date),
            'prefixe': extra.get('prefixe', ''),
        }
        try:
            result = template.format(**mapping)
        except KeyError:
            result = title + p.suffix.lower()
        return self.safe_filename(result)



# ═══════════════════════════════════════════════════════════════════
#  GESTION DROITS ADMINISTRATEUR (Windows)
# ═══════════════════════════════════════════════════════════════════

def is_admin() -> bool:
    """Vérifie si le processus a les droits administrateur."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False  # Non-Windows : on suppose que c'est OK

def relaunch_as_admin():
    """Relance le script en tant qu'administrateur via UAC."""
    try:
        script = os.path.abspath(sys.argv[0])
        params = ' '.join(f'"{a}"' for a in sys.argv[1:])
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}" {params}', None, 1)
        if ret > 32:
            return True   # Relance réussie
        return False
    except Exception:
        return False

def check_file_writable(filepath: str) -> str:
    """Retourne '' si OK, sinon un message d'erreur."""
    # Teste si le dossier parent est accessible en écriture
    folder = os.path.dirname(os.path.abspath(filepath))
    if not os.access(folder, os.W_OK):
        return "Dossier non accessible en écriture"
    if not os.access(filepath, os.W_OK):
        return "Fichier en lecture seule"
    return ""


engine = RenameEngine()

# ═══════════════════════════════════════════════════════════════════
#  SCRAPERS  TMDb (films/séries/anime)  +  AniList (manga)
# ═══════════════════════════════════════════════════════════════════

class TMDbScraper:
    """Interroge l'API TMDb v3 pour films, séries et anime."""

    BASE = 'https://api.themoviedb.org/3'

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._cache  = {}          # {url: data}

    def _get(self, endpoint: str, params: dict) -> dict:
        params['api_key']  = self.api_key
        params['language'] = 'fr-FR'
        qs  = urllib.parse.urlencode(params)
        url = f"{self.BASE}{endpoint}?{qs}"
        if url in self._cache:
            return self._cache[url]
        try:
            req  = urllib.request.Request(url,
                headers={'User-Agent': 'FileRenamer/1.0'})
            resp = urllib.request.urlopen(req, timeout=8)
            data = json.loads(resp.read().decode('utf-8'))
            self._cache[url] = data
            return data
        except Exception as exc:
            raise ConnectionError(f"TMDb inaccessible : {exc}")

    def search_movie(self, query: str, year: str = '') -> list:
        """Recherche film avec fallbacks: avec annee, sans annee, sans accents."""
        def _parse(data):
            out = []
            for r in data.get('results', [])[:8]:
                yr = r.get('release_date', '')[:4] or '?'
                out.append({
                    'id':             r['id'],
                    'title':          r.get('title', r.get('original_title', '?')),
                    'original_title': r.get('original_title', ''),
                    'year':           yr,
                    'type':           'movie',
                })
            return out
        # Tentative 1 : query + annee
        params = {'query': query}
        if year: params['year'] = year
        results = _parse(self._get('/search/movie', params))
        if results: return results
        # Tentative 2 : sans annee (annee peut etre decalee de 1 an)
        if year:
            results = _parse(self._get('/search/movie', {'query': query}))
            if results: return results
        # Tentative 3 : query simplifiee (premiers 3 mots)
        words = query.split()
        if len(words) > 3:
            short_q = ' '.join(words[:4])
            results = _parse(self._get('/search/movie', {'query': short_q}))
            if results: return results
        return []

    def search_tv(self, query: str, year: str = '') -> list:
        """Recherche serie avec fallbacks."""
        def _parse(data):
            out = []
            for r in data.get('results', [])[:8]:
                yr = r.get('first_air_date', '')[:4] or '?'
                out.append({
                    'id':             r['id'],
                    'title':          r.get('name', r.get('original_name', '?')),
                    'original_title': r.get('original_name', ''),
                    'year':           yr,
                    'type':           'tv',
                })
            return out
        params = {'query': query}
        if year: params['first_air_date_year'] = year
        results = _parse(self._get('/search/tv', params))
        if results: return results
        if year:
            results = _parse(self._get('/search/tv', {'query': query}))
            if results: return results
        words = query.split()
        if len(words) > 3:
            results = _parse(self._get('/search/tv', {'query': ' '.join(words[:4])}))
            if results: return results
        return []

    def get_movie(self, tmdb_id: int) -> dict:
        data = self._get(f'/movie/{tmdb_id}', {})
        return {
            'id':    data['id'],
            'title': data.get('title', data.get('original_title', '?')),
            'year':  data.get('release_date', '')[:4] or '?',
            'type':  'movie',
        }

    def get_tv(self, tmdb_id: int) -> dict:
        data = self._get(f'/tv/{tmdb_id}', {})
        return {
            'id':    data['id'],
            'title': data.get('name', data.get('original_name', '?')),
            'year':  data.get('first_air_date', '')[:4] or '?',
            'type':  'tv',
        }


class AniListScraper:
    """Interroge l'API AniList (GraphQL, sans cle API) pour manga et anime."""

    URL = 'https://graphql.anilist.co'

    def _query(self, gql: str, variables: dict) -> dict:
        body = json.dumps({'query': gql, 'variables': variables}).encode('utf-8')
        req  = urllib.request.Request(self.URL, data=body,
            headers={'Content-Type': 'application/json',
                     'User-Agent': 'FileRenamer/1.0'})
        try:
            resp = urllib.request.urlopen(req, timeout=8)
            return json.loads(resp.read().decode('utf-8'))
        except Exception as exc:
            raise ConnectionError(f"AniList inaccessible : {exc}")

    def search(self, query: str, media_type: str = 'MANGA') -> list:
        """media_type = MANGA | ANIME"""
        # Champs valides AniList : romaji, english, native, userPreferred
        # "french" n'existe PAS dans le schéma → HTTP 400
        gql = """
        query ($search: String, $type: MediaType) {
          Page(perPage: 8) {
            media(search: $search, type: $type) {
              id
              title { romaji english native userPreferred }
              startDate { year }
              volumes
              episodes
            }
          }
        }"""
        data = self._query(gql, {'search': query, 'type': media_type})
        results = []
        for r in data.get('data', {}).get('Page', {}).get('media', []):
            t = r.get('title', {})
            # Priorité : userPreferred (langue interface AniList) > english > romaji > native
            title = t.get('userPreferred') or t.get('english') or t.get('romaji') or t.get('native') or '?'
            yr    = (r.get('startDate') or {}).get('year') or '?'
            results.append({
                'id':     r['id'],
                'title':  title,
                'romaji': t.get('romaji', ''),
                'year':   str(yr),
                'type':   media_type.lower(),
                'volumes': r.get('volumes') or '?',
            })
        return results


# ═══════════════════════════════════════════════════════════════════
#  FileRenamer — UI 2026
#  Direction : "Terminal Luxe" — noir profond, accents néon amber/cyan,
#  typographie Segoe UI Variable + Consolas, surfaces vitrées (glassmorphism léger),
#  micro-animations via after(), barre latérale iconique avec tooltips,
#  cartes radio avec indicateur animé, layout 3 colonnes flottantes.
# ═══════════════════════════════════════════════════════════════════

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ── Palette "Terminal Luxe" ──────────────────────────────────────
_BG      = '#080b12'      # noir quasi-pur
_SURF    = '#0d1120'      # surface principale
_PANEL   = '#111827'      # panneaux
_CARD    = '#161e2e'      # cartes
_CARD2   = '#1a2235'      # cartes secondaires
_BORDER  = '#1e2d45'      # bordures subtiles
_GLOW    = '#0f2040'      # lueur de fond

_AMBER   = '#f5a623'      # accent primaire
_AMBER2  = '#ffc853'      # amber clair hover
_CYAN    = '#38bdf8'      # accent secondaire
_TEAL    = '#2dd4bf'      # accent tertiaire
_VIOLET  = '#a78bfa'      # accent quaternaire
_GREEN   = '#34d399'      # succès
_RED     = '#f87171'      # erreur
_ORANGE  = '#fb923c'      # avertissement
_PINK    = '#f472b6'      # manga

_TEXT    = '#e2e8f0'      # texte principal
_TEXT2   = '#94a3b8'      # texte secondaire
_MUTED   = '#475569'      # texte désactivé
_SEL     = '#1e3a5f'      # sélection treeview

_FN  = 'Segoe UI Variable Display'   # police principale
_FNM = 'Cascadia Code'               # police mono (avec fallback)

# Fallback si police absente
def _font(name, size, style='normal'):
    return (name, size, style)

def F(size, bold=False):   return (_FN,  size, 'bold' if bold else 'normal')
def FM(size, bold=False):  return (_FNM, size, 'bold' if bold else 'normal')


# ── Helpers ──────────────────────────────────────────────────────

def L(parent, text, size=11, bold=False, fg=None, bg=None, wrap=0, anchor='w'):
    kw = dict(text=text, font=F(size, bold),
              fg=fg or _TEXT, bg=bg or parent.cget('bg'), anchor=anchor)
    if wrap: kw['wraplength'] = wrap
    return tk.Label(parent, **kw)

def LM(parent, text, size=10, fg=None, bg=None):
    return tk.Label(parent, text=text, font=FM(size),
        fg=fg or _TEXT2, bg=bg or parent.cget('bg'), anchor='w')

def SEP(parent, color=_BORDER, h=1):
    return tk.Frame(parent, bg=color, height=h)

def CHK(parent, text, var, fg=None, size=11):
    bg = parent.cget('bg')
    return tk.Checkbutton(parent, text=text, variable=var,
        font=F(size), fg=_TEXT, bg=bg,
        selectcolor=_CARD2, activebackground=bg,
        activeforeground=fg or _AMBER,
        relief='flat', cursor='hand2')

def BTN(parent, text, cmd, bg=_CARD, fg=_TEXT, size=11, bold=False, pad=(16,9)):
    return tk.Button(parent, text=text, command=cmd,
        font=F(size, bold), bg=bg, fg=fg,
        activebackground=_BORDER, activeforeground=_AMBER2,
        relief='flat', cursor='hand2',
        padx=pad[0], pady=pad[1])

def ENT(parent, var, width=24, font_size=11):
    return tk.Entry(parent, textvariable=var,
        font=FM(font_size), bg='#060912', fg=_TEXT,
        insertbackground=_AMBER, relief='flat',
        highlightthickness=1, highlightcolor=_AMBER,
        highlightbackground=_BORDER, bd=4, width=width)


# ═══════════════════════════════════════════════════════════════════
#  APPLICATION
# ═══════════════════════════════════════════════════════════════════

class App(tk.Tk):

    MODES = [
        ('video',    '▶',  'Vidéo'),
        ('manga',    '◈',  'Manga'),
        ('book',     '◉',  'Livres'),
        ('photo',    '◎',  'Photos'),
        ('custom',   '◆',  'Custom'),
        ('settings', '◍',  'Réglages'),
    ]

    MODE_COLOR = {
        'video': '#f5a623', 'manga': '#f472b6', 'book': '#2dd4bf',
        'photo': '#38bdf8', 'custom': '#a78bfa', 'settings': '#475569',
    }

    # ──────────────────────────────────────────────────────────────
    def __init__(self):
        super().__init__()
        self.title('FileRenamer')
        self.geometry('1480x860')
        self.minsize(1100, 680)
        self.configure(bg=_BG)

        # Variables
        self.tmdb_api_key       = tk.StringVar(value='')
        self._tmdb              = None
        self._anilist           = AniListScraper()
        self.scraper_enabled    = tk.BooleanVar(value=True)
        self.folder_var         = tk.StringVar()
        self.recursive_var      = tk.BooleanVar(value=False)
        self.rename_folder_var  = tk.BooleanVar(value=False)
        self.video_mode         = tk.StringVar(value='film')
        self.video_conv         = tk.StringVar(value='plex')
        self.v_overwrite        = tk.BooleanVar(value=False)
        self.v_multi_titles     = tk.BooleanVar(value=False)
        self.v_nfo              = tk.BooleanVar(value=False)
        self.v_anime            = tk.BooleanVar(value=False)
        self.v_tmdb_id          = tk.StringVar()
        self.manga_mode         = tk.StringVar(value='kobo')
        self.manga_series       = tk.StringVar()
        self.manga_year         = tk.StringVar()
        self.manga_cbz          = tk.BooleanVar(value=True)
        self.manga_cbr          = tk.BooleanVar(value=True)
        self.manga_pdf          = tk.BooleanVar(value=True)
        self.manga_epub         = tk.BooleanVar(value=True)
        self.book_author        = tk.StringVar()
        self.book_conv          = tk.StringVar(value='calibre')
        self.book_pdf           = tk.BooleanVar(value=True)
        self.book_epub          = tk.BooleanVar(value=True)
        self.book_mobi          = tk.BooleanVar(value=True)
        self.book_djvu          = tk.BooleanVar(value=False)
        self.photo_prefix       = tk.StringVar()
        self.photo_exif         = tk.BooleanVar(value=True)
        self.custom_template    = tk.StringVar(value='{titre} ({annee}){ext}')
        self.custom_author      = tk.StringVar()
        self.custom_prefix      = tk.StringVar()
        self.custom_video       = tk.BooleanVar(value=True)
        self.custom_book        = tk.BooleanVar(value=True)
        self.custom_manga       = tk.BooleanVar(value=True)
        self.custom_image       = tk.BooleanVar(value=True)
        self.preview_data       = []
        self._selected_files    = []
        self.folder_preview_data= []
        self._pages             = {}
        self._current_mode      = 'video'
        self._nav_btns          = {}
        self._scrape_pending_id = None
        self._refresh_pending_id= None
        self._scrape_cache      = None   # dernier résultat scraper: {title,year,id,files,mode,anime}

        self._build_ui()
        self._apply_style()
        self._load_icon()

    # ── Style TTK ─────────────────────────────────────────────────
    def _apply_style(self):
        s = ttk.Style(self)
        s.theme_use('clam')
        s.configure('Treeview',
            background=_SURF, fieldbackground=_SURF,
            foreground=_TEXT, font=FM(10), rowheight=26, borderwidth=0)
        s.configure('Treeview.Heading',
            background=_PANEL, foreground=_AMBER,
            font=F(10, True), relief='flat')
        s.map('Treeview',
            background=[('selected', _SEL)],
            foreground=[('selected', _CYAN)])
        s.configure('TScrollbar',
            background=_PANEL, troughcolor=_BG,
            borderwidth=0, arrowsize=10)

    def _load_icon(self):
        """Charge icon.ico depuis le même dossier que le .py/.exe et l'applique."""
        # Trouver le chemin de l'icône (compatible PyInstaller _MEIPASS)
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        ico_path = os.path.join(base, 'icon.ico')
        png_path = os.path.join(base, 'icon_48.png')
        # Icône de la fenêtre (titlebar + taskbar)
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass
        # Icône dans le header (logo visuel) — si Pillow dispo
        if PIL_OK and ImageTk and os.path.exists(png_path):
            try:
                img = Image.open(png_path).resize((28, 28), Image.LANCZOS)
                self._logo_img = ImageTk.PhotoImage(img)
                # Remplacer le label texte "FR" par l'image
                if hasattr(self, '_logo_lbl'):
                    self._logo_lbl.configure(image=self._logo_img, text='', padx=0, pady=0)
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════
    #  BUILD UI — structure principale
    # ══════════════════════════════════════════════════════════════
    def _build_ui(self):
        # Statut (bottom — packed first)
        bar = tk.Frame(self, bg=_SURF, height=24)
        bar.pack(fill='x', side='bottom')
        tk.Frame(bar, bg=_BORDER, height=1).pack(fill='x', side='top')
        self.status_var = tk.StringVar(value='Prêt — choisissez un dossier ou des fichiers')
        tk.Label(bar, textvariable=self.status_var,
            bg=_SURF, fg=_MUTED, font=FM(9), anchor='w').pack(
            side='left', padx=12, fill='y')
        tk.Label(bar, text='FileRenamer v3  ·  2026',
            bg=_SURF, fg=_MUTED, font=FM(9)).pack(side='right', padx=12)

        # Header
        self._build_header()
        tk.Frame(self, bg=_AMBER, height=2).pack(fill='x')

        # Onglets modes (barre horizontale sous le header)
        self._build_modebar()
        tk.Frame(self, bg=_BORDER, height=1).pack(fill='x')

        # Body
        body = tk.Frame(self, bg=_BG)
        body.pack(fill='both', expand=True)

        # Panneau gauche options (304px)
        self._opts_frame = tk.Frame(body, bg=_PANEL, width=304)
        self._opts_frame.pack(side='left', fill='y')
        self._opts_frame.pack_propagate(False)
        tk.Frame(body, bg=_BORDER, width=1).pack(side='left', fill='y')

        # Panneau droit preview
        right = tk.Frame(body, bg=_BG)
        right.pack(side='left', fill='both', expand=True)
        self._build_right(right)

        # Pages (dans _opts_frame)
        self._build_all_pages()
        self._show_page('video')

    # ── Header ───────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=_SURF)
        hdr.pack(fill='x')
        row = tk.Frame(hdr, bg=_SURF)
        row.pack(fill='x', padx=14, pady=8)

        # Logo (remplacé par icône PNG si disponible via _load_icon)
        self._logo_lbl = tk.Label(row, text='FR', font=F(14, True),
            fg=_BG, bg=_AMBER, padx=8, pady=1)
        self._logo_lbl.pack(side='left')
        tk.Label(row, text=' FileRenamer',
            font=F(13, True), fg=_TEXT, bg=_SURF).pack(side='left')

        # Barre dossier (expandable)
        fb = tk.Frame(row, bg=_BORDER)
        fb.pack(side='left', fill='x', expand=True, padx=14)
        tk.Label(fb, text='📁', bg=_BORDER, fg=_AMBER,
            font=F(11)).pack(side='left', padx=(7,3), pady=3)
        tk.Entry(fb, textvariable=self.folder_var,
            font=FM(10), bg=_BORDER, fg=_TEXT,
            insertbackground=_AMBER, relief='flat', bd=0).pack(
            side='left', fill='x', expand=True, pady=4)
        # Séparateur vertical
        tk.Frame(fb, bg=_MUTED, width=1).pack(side='left', fill='y', pady=3)
        BTN(fb, '📁 Dossier', self._browse_folder,
            bg=_AMBER, fg=_BG, bold=True, pad=(9,4)).pack(side='left', padx=(1,1))
        BTN(fb, '🎬 Fichiers', self._browse_files,
            bg=_CARD2, fg=_AMBER, bold=True, pad=(9,4)).pack(side='left', padx=(0,1))

        # Options inline (right of folder bar)
        chk_f = tk.Frame(row, bg=_SURF)
        chk_f.pack(side='left', padx=(8,0))
        CHK(chk_f, 'Récursif',   self.recursive_var,   fg=_CYAN,  size=9).pack(anchor='w')
        CHK(chk_f, 'Dossier',    self.rename_folder_var, fg=_TEAL, size=9).pack(anchor='w')

        # Admin (Windows only)
        if sys.platform == 'win32':
            try:    _ok = is_admin()
            except: _ok = False
            af = tk.Frame(row, bg=_SURF)
            af.pack(side='right', padx=8)
            if _ok:
                tk.Label(af, text='✓ Admin', font=F(9, True),
                    fg=_GREEN, bg=_SURF).pack()
            else:
                def _rel():
                    if relaunch_as_admin(): self.destroy()
                BTN(af, '⚠ Admin', _rel,
                    bg=_ORANGE, fg=_BG, bold=True, pad=(8,3)).pack()

        # Trace dossier → scraper
        def _on_folder_change(*_):
            d = self.folder_var.get().strip()
            if d and os.path.isdir(d):
                self._trigger_scrape(d, delay=700)
        self.folder_var.trace_add('write', _on_folder_change)

    # ── Barre de modes (onglets horizontaux) ─────────────────────
    def _build_modebar(self):
        bar = tk.Frame(self, bg=_SURF)
        bar.pack(fill='x')

        for mode_id, icon, label in self.MODES:
            color = self.MODE_COLOR[mode_id]

            cell = tk.Frame(bar, bg=_SURF, cursor='hand2')
            cell.pack(side='left')

            # Indicateur bas (coloré quand actif)
            ind = tk.Frame(cell, bg=_SURF, height=3)
            ind.pack(side='bottom', fill='x')

            lbl = tk.Label(cell,
                text=f'{icon}  {label}',
                font=F(10, True), fg=_MUTED, bg=_SURF,
                padx=18, pady=6, cursor='hand2')
            lbl.pack()

            all_w = [cell, lbl]
            for w in all_w:
                w.bind('<Button-1>', lambda e, m=mode_id: self._show_page(m))

            def _enter(e, ws=all_w):
                for w in ws:
                    try: w.configure(bg=_CARD)
                    except: pass
            def _leave(e, ws=all_w, m=mode_id):
                active = self._current_mode == m
                for w in ws:
                    try: w.configure(bg=_CARD2 if active else _SURF)
                    except: pass
            for w in all_w:
                w.bind('<Enter>', _enter)
                w.bind('<Leave>', _leave)

            self._nav_btns[mode_id] = (cell, lbl, ind, color)

    def _show_page(self, mode_id):
        self._pages['_current'] = mode_id
        self._current_mode = mode_id

        if mode_id in ('video', 'manga', 'book'):
            d = self.folder_var.get().strip()
            if self._selected_files:
                self._trigger_scrape_files(list(self._selected_files), delay=300)
            elif d and os.path.isdir(d):
                self._trigger_scrape(d, delay=300)

        # Reset tous
        for pid, page in self._pages.items():
            if pid == '_current': continue
            page.place_forget()
            cell, lbl, ind, col = self._nav_btns[pid]
            cell.configure(bg=_SURF)
            lbl.configure(bg=_SURF, fg=_MUTED)
            ind.configure(bg=_SURF)

        # Activer
        self._pages[mode_id].place(x=0, y=0, relwidth=1, relheight=1)
        cell, lbl, ind, color = self._nav_btns[mode_id]
        cell.configure(bg=_CARD2)
        lbl.configure(bg=_CARD2, fg=color)
        ind.configure(bg=color)

    # ══════════════════════════════════════════════════════════════
    #  PAGES OPTIONS
    # ══════════════════════════════════════════════════════════════
    def _build_all_pages(self):
        for mode_id, _, _ in self.MODES:
            page = tk.Frame(self._opts_frame, bg=_PANEL)
            self._pages[mode_id] = page
            getattr(self, f'_page_{mode_id}')(page)

    # ── Widget helpers ────────────────────────────────────────────
    def _sec(self, p, text, color=_AMBER):
        """En-tête de section compact."""
        f = tk.Frame(p, bg=_PANEL)
        f.pack(fill='x', padx=8, pady=(8, 2))
        tk.Frame(f, bg=color, width=2, height=13).pack(side='left')
        tk.Label(f, text=text, font=F(9, True), fg=color,
            bg=_PANEL, padx=5).pack(side='left', anchor='w')

    def _seg_btns(self, p, opts, var, color):
        """Boutons segmentés (remplace radio cards scrollables)."""
        row = tk.Frame(p, bg=_PANEL)
        row.pack(fill='x', padx=8, pady=(2, 0))
        btns = {}

        def _refresh(*_):
            for val, (btn, sep) in btns.items():
                sel = var.get() == val
                btn.configure(
                    bg=color if sel else _CARD,
                    fg=_BG   if sel else _TEXT2)

        for i, (val, label) in enumerate(opts):
            # Séparateur 1px entre boutons
            if i > 0:
                tk.Frame(row, bg=_BORDER, width=1).pack(side='left', fill='y', pady=1)
            b = tk.Button(row, text=label,
                font=F(9, True), bg=_CARD, fg=_TEXT2,
                relief='flat', bd=0, cursor='hand2',
                padx=10, pady=6,
                activebackground=_CARD2, activeforeground=color,
                command=lambda v=val: var.set(v))
            b.pack(side='left', fill='x', expand=True)
            btns[val] = (b, None)

        var.trace_add('write', _refresh)
        _refresh()

    def _example_lbl(self, p, var, exmap, color):
        """Label d'exemple dynamique sous les boutons segmentés."""
        lbl = tk.Label(p, text='', font=FM(9), fg=color,
            bg=_PANEL, anchor='w', padx=10)
        lbl.pack(fill='x', pady=(1, 5))
        def _upd(*_):
            lbl.configure(text='→ ' + exmap.get(var.get(), ''))
        var.trace_add('write', _upd)
        _upd()

    def _field_row(self, p, label, var, hint='', color=_TEXT2):
        """Champ texte compact sur une ligne."""
        row = tk.Frame(p, bg=_PANEL)
        row.pack(fill='x', padx=8, pady=2)
        tk.Label(row, text=label, font=F(9), fg=color,
            bg=_PANEL, width=7, anchor='e').pack(side='left')
        ent = tk.Entry(row, textvariable=var,
            font=FM(10), bg=_CARD, fg=_TEXT,
            insertbackground=_AMBER, relief='flat',
            highlightthickness=1, highlightcolor=_AMBER,
            highlightbackground=_BORDER, bd=3)
        ent.pack(side='left', fill='x', expand=True, padx=(4, 0))
        if hint:
            tk.Label(row, text=hint, font=F(8), fg=_MUTED,
                bg=_PANEL).pack(side='left', padx=4)

    def _fmt_row(self, p, items):
        """Checkboxes formats sur une ligne."""
        row = tk.Frame(p, bg=_PANEL)
        row.pack(fill='x', padx=8, pady=(2, 4))
        for text, var, color in items:
            tk.Checkbutton(row, text=text, variable=var,
                font=F(9, True), fg=color, bg=_PANEL,
                selectcolor=_CARD, activebackground=_PANEL,
                activeforeground=color,
                relief='flat', cursor='hand2').pack(side='left', padx=(0, 8))

    def _run_btn(self, p, mode_id, label='Analyser'):
        """Bouton analyser compact."""
        f = tk.Frame(p, bg=_PANEL)
        f.pack(fill='x', padx=8, pady=(6, 10), side='bottom')
        tk.Frame(f, bg=_BORDER, height=1).pack(fill='x', pady=(0, 5))
        BTN(f, f'  {label}  →',
            lambda: self._run_preview(mode_id),
            bg=_AMBER, fg=_BG, size=10, bold=True, pad=(0, 7)
        ).pack(fill='x')

    # ── Page Vidéo ────────────────────────────────────────────────
    def _page_video(self, p):
        self._sec(p, 'TYPE DE CONTENU')
        self._seg_btns(p, [
            ('film',  '🎬 Film'),
            ('serie', '📺 Série'),
            ('anime', '🎌 Anime'),
        ], self.video_mode, _AMBER)

        # Exemple dynamique type + convention
        ex_type = {
            'film': {
                'plex':        'Inception (2010).mkv',
                'kodi':        'Inception (2010).mkv',
                'jellyfin':    'Inception (2010).mkv',
                'emby':        'Inception (2010).mkv',
                'infuse':      'Inception (2010).mkv',
                'mediaportal': 'Inception (2010).mkv',
                'tmdb':        'Inception.2010.mkv'},
            'serie': {
                'plex':        'Breaking Bad - s01e01.mkv',   # tiret + minuscules (officiel Plex)
                'kodi':        'Breaking Bad S01E01.mkv',     # pas de tiret (officiel Kodi)
                'jellyfin':    'Breaking Bad S01E01.mkv',     # idem Kodi (officiel Jellyfin)
                'emby':        'Breaking Bad S01E01.mkv',     # idem Kodi (officiel Emby)
                'infuse':      'Breaking Bad S01E01.mkv',     # idem (officiel Infuse)
                'mediaportal': 'Breaking Bad S01E01.mkv',     # idem (officiel MP)
                'tmdb':        'Breaking.Bad.S01E01.mkv'},
            'anime': {
                'plex':        'Demon Slayer - s01e007.mkv',
                'kodi':        'Demon Slayer S01E007.mkv',
                'jellyfin':    'Demon Slayer S01E007.mkv',
                'emby':        'Demon Slayer S01E007.mkv',
                'infuse':      'Demon Slayer S01E007.mkv',
                'mediaportal': 'Demon Slayer S01E007.mkv',
                'tmdb':        'Demon.Slayer.S01E007.mkv'},
        }
        ex_lbl = tk.Label(p, text='', font=FM(9), fg=_AMBER,
            bg=_PANEL, anchor='w', padx=10)
        ex_lbl.pack(fill='x', pady=(1, 5))
        def _upd_ex(*_):
            m = self.video_mode.get(); c = self.video_conv.get()
            ex_lbl.configure(text='→ ' + ex_type.get(m, {}).get(c, ''))
        self.video_mode.trace_add('write', _upd_ex)
        self.video_conv.trace_add('write', _upd_ex)
        _upd_ex()

        self._sec(p, 'CONVENTION', _CYAN)
        # Ligne 1 : lecteurs grand public
        self._seg_btns(p, [
            ('plex',     'Plex'),
            ('kodi',     'Kodi'),
            ('jellyfin', 'Jellyfin'),
            ('emby',     'Emby'),
        ], self.video_conv, _CYAN)
        # Ligne 2 : outils automatisation
        self._seg_btns(p, [
            ('tmdb',     'TMDb / Sonarr / Radarr'),
        ], self.video_conv, _CYAN)

        self._sec(p, 'OPTIONS', _MUTED)
        opt_f = tk.Frame(p, bg=_PANEL)
        opt_f.pack(fill='x', padx=8, pady=2)
        CHK(opt_f, 'Multi-titres', self.v_multi_titles, fg=_AMBER, size=9).pack(
            side='left', padx=(0, 10))
        CHK(opt_f, 'Écraser', self.v_overwrite, fg=_ORANGE, size=9).pack(side='left')
        nfo_f = tk.Frame(p, bg=_PANEL)
        nfo_f.pack(fill='x', padx=8, pady=(2, 0))
        CHK(nfo_f, 'Générer .nfo (Kodi)', self.v_nfo, fg=_TEAL, size=9).pack(
            side='left', padx=(0, 6))
        self._field_row(p, 'ID TMDb', self.v_tmdb_id, hint='ex: 1396')

        # Traces
        def _on_type(*_):
            self._tmdb_banner.pack_forget()
            d = self.folder_var.get().strip()
            if self._selected_files:
                self._trigger_scrape_files(list(self._selected_files), delay=200)
            elif d and os.path.isdir(d):
                self._trigger_scrape(d, delay=200)
        self.video_mode.trace_add('write', _on_type)
        self.video_conv.trace_add('write', self._refresh_preview)

        self._run_btn(p, 'video', 'Analyser Films & Séries')

    # ── Page Manga ────────────────────────────────────────────────
    def _page_manga(self, p):
        self._sec(p, 'LECTEUR', _PINK)
        self._seg_btns(p, [
            ('kobo',  'Kobo'),
            ('pc',    'PC / Komga'),
            ('mylar', 'Mylar3'),
        ], self.manga_mode, _PINK)
        self._example_lbl(p, self.manga_mode, {
            'kobo':  'One Piece - T042.cbz',
            'pc':    'One Piece v042.cbz',
            'mylar': 'One Piece (1997) #042.cbz',
        }, _PINK)

        self._mylar_warn = tk.Label(p,
            text='⚠  Mylar3 : année obligatoire pour le format complet',
            font=F(9), fg=_ORANGE, bg=_PANEL, anchor='w', padx=10)

        self._sec(p, 'SÉRIE', _PINK)
        self._field_row(p, 'Série :', self.manga_series, hint='auto si vide')
        self._field_row(p, 'Année :', self.manga_year)

        self._sec(p, 'FORMATS', _PINK)
        self._fmt_row(p, [
            ('CBZ', self.manga_cbz, _PINK), ('CBR', self.manga_cbr, _PINK),
            ('PDF', self.manga_pdf, _ORANGE), ('EPUB', self.manga_epub, _CYAN),
        ])

        # Traces
        def _chk_mylar(*_):
            if self.manga_mode.get() == 'mylar':
                self._mylar_warn.pack(fill='x', after=p.winfo_children()[3])
            else:
                self._mylar_warn.pack_forget()
        def _on_manga_mode(*_):
            _chk_mylar()
            self._refresh_preview()
            d = self.folder_var.get().strip()
            if d and os.path.isdir(d):
                self._tmdb_banner.pack_forget()
                self.after(300, lambda: self._auto_scrape(d))
        self.manga_mode.trace_add('write', _on_manga_mode)
        self.manga_series.trace_add('write', self._refresh_preview_delayed)
        self.manga_year.trace_add('write', self._refresh_preview_delayed)
        _chk_mylar()

        self._run_btn(p, 'manga', 'Analyser Mangas')

    # ── Page Livres ───────────────────────────────────────────────
    def _page_book(self, p):
        self._sec(p, 'LOGICIEL', _TEAL)
        self._seg_btns(p, [
            ('calibre', 'Calibre'),
            ('kobo',    'Kobo'),
            ('kindle',  'Kindle'),
            ('adobe',   'Adobe'),
        ], self.book_conv, _TEAL)
        self._example_lbl(p, self.book_conv, {
            'calibre': 'Tolkien - Le Seigneur des Anneaux (2001).epub',
            'kobo':    'Le Seigneur des Anneaux - Tolkien.epub',
            'kindle':  'Le Seigneur des Anneaux - Tolkien.epub',
            'adobe':   'Tolkien - Le Seigneur des Anneaux.epub',
        }, _TEAL)

        self._sec(p, 'AUTEUR', _TEAL)
        self._field_row(p, 'Auteur :', self.book_author, hint='auto si vide')

        self._sec(p, 'FORMATS', _TEAL)
        self._fmt_row(p, [
            ('PDF', self.book_pdf, _ORANGE), ('EPUB', self.book_epub, _CYAN),
            ('MOBI', self.book_mobi, _GREEN), ('DJVU', self.book_djvu, _MUTED),
        ])

        def _on_book(*_):
            self._refresh_preview()
            d = self.folder_var.get().strip()
            if d and os.path.isdir(d):
                self._tmdb_banner.pack_forget()
                self.after(300, lambda: self._auto_scrape(d))
        self.book_conv.trace_add('write', _on_book)
        self.book_author.trace_add('write', self._refresh_preview_delayed)

        self._run_btn(p, 'book', 'Analyser Livres & BD')

    # ── Page Photos ───────────────────────────────────────────────
    def _page_photo(self, p):
        self._sec(p, 'RENOMMAGE PAR DATE', _CYAN)
        tk.Label(p, text='→ 20231225_143022_vacances.jpg',
            font=FM(9), fg=_CYAN, bg=_PANEL, anchor='w', padx=10).pack(
            fill='x', pady=(0, 4))
        self._field_row(p, 'Suffixe :', self.photo_prefix, hint='ex: vacances')
        opt = tk.Frame(p, bg=_PANEL)
        opt.pack(fill='x', padx=8, pady=4)
        CHK(opt, 'Date EXIF (prise de vue)', self.photo_exif, fg=_CYAN, size=9).pack(anchor='w')
        pil_c = _GREEN if PIL_OK else _ORANGE
        tk.Label(p, text=('✓ Pillow OK — EXIF actif' if PIL_OK else '⚠ pip install pillow'),
            font=F(9), fg=pil_c, bg=_PANEL, anchor='w', padx=10).pack(fill='x')
        self._run_btn(p, 'photo', 'Analyser Photos')

    # ── Page Custom ───────────────────────────────────────────────
    def _page_custom(self, p):
        self._sec(p, 'MODÈLE', _VIOLET)
        tk.Label(p,
            text='{titre}  {annee}  {ext}  {saison}  {episode}  {tome}  {auteur}  {date}  {prefixe}',
            font=FM(9), fg=_MUTED, bg=_PANEL, anchor='w', padx=10,
            justify='left').pack(fill='x', pady=(0, 2))
        self._field_row(p, 'Modèle :', self.custom_template)
        self._sec(p, 'VALEURS', _VIOLET)
        self._field_row(p, 'Auteur :', self.custom_author)
        self._field_row(p, 'Préfixe :', self.custom_prefix)
        self._sec(p, 'TYPES', _VIOLET)
        self._fmt_row(p, [
            ('Vidéo', self.custom_video, _AMBER),
            ('Livre', self.custom_book,  _CYAN),
            ('Manga', self.custom_manga, _PINK),
            ('Image', self.custom_image, _GREEN),
        ])
        self._run_btn(p, 'custom', 'Analyser Custom')

    # ── Page Réglages ─────────────────────────────────────────────
    def _page_settings(self, p):
        self._sec(p, 'API TMDB', _CYAN)
        tk.Label(p, text='Clé gratuite : themoviedb.org/settings/api',
            font=F(9), fg=_MUTED, bg=_PANEL, anchor='w', padx=10).pack(
            fill='x', pady=(0, 2))
        self._field_row(p, 'Clé API :', self.tmdb_api_key)
        test_f = tk.Frame(p, bg=_PANEL)
        test_f.pack(fill='x', padx=8, pady=4)
        self._api_status = tk.Label(test_f, text='', font=F(9),
            fg=_MUTED, bg=_PANEL, anchor='w')
        self._api_status.pack(anchor='w', pady=(0, 4))
        def _test():
            self._api_status.configure(text='Test en cours...', fg=_MUTED)
            self.update_idletasks()
            def _run():
                try:
                    r = self._get_tmdb().search_movie('Inception', '2010')
                    msg = f'✓ OK — {r[0]["title"]} ({r[0]["year"]})' if r else '✓ Connecté'
                    self.after(0, lambda: self._api_status.configure(text=msg, fg=_GREEN))
                except Exception as exc:
                    self.after(0, lambda: self._api_status.configure(
                        text=f'✗ {exc}', fg=_RED))
            threading.Thread(target=_run, daemon=True).start()
        BTN(test_f, 'Tester connexion TMDb', _test,
            bg=_CYAN, fg=_BG, bold=True, pad=(8, 5)).pack(anchor='w')

        self._sec(p, 'SCRAPER', _CYAN)
        CHK(p, 'Activer TMDb / AniList / OpenLibrary',
            self.scraper_enabled, fg=_CYAN, size=9).pack(anchor='w', padx=10, pady=4)

        self._sec(p, 'APIs GRATUITES', _MUTED)
        for k, v in [('AniList', 'graphql.anilist.co — sans clé'),
                     ('OpenLib', 'openlibrary.org — sans clé')]:
            row = tk.Frame(p, bg=_CARD)
            row.pack(fill='x', padx=8, pady=1)
            tk.Label(row, text=k, font=F(9, True), fg=_TEXT2,
                bg=_CARD, width=8, anchor='e').pack(side='left', padx=(6,4), pady=4)
            tk.Label(row, text=v, font=F(9), fg=_MUTED, bg=_CARD).pack(side='left')

    # ══════════════════════════════════════════════════════════════
    #  PANNEAU DROIT — Bannière + Treeview + Actions
    # ══════════════════════════════════════════════════════════════
    def _build_right(self, parent):
        # ── Zone bannière scraper ─────────────────────────────────
        self._banner_area = tk.Frame(parent, bg=_BG)
        self._banner_area.pack(fill='x')
        self._tmdb_banner = tk.Frame(self._banner_area, bg='#071828')
        # (sera pack/unpack par _show_tmdb_banner)

        # ── Header preview ────────────────────────────────────────
        phdr = tk.Frame(parent, bg=_PANEL)
        phdr.pack(fill='x')

        # Colonne gauche : label + hint
        ph_left = tk.Frame(phdr, bg=_PANEL)
        ph_left.pack(side='left', fill='y', padx=(12, 4), pady=6)
        tk.Label(ph_left, text='PRÉVISUALISATION',
            font=F(10, True), fg=_AMBER, bg=_PANEL).pack(side='left')
        tk.Label(ph_left, text=' · double-clic = aperçu',
            font=F(9), fg=_MUTED, bg=_PANEL).pack(side='left')

        # Colonne droite : compteur
        self.count_label = tk.Label(phdr, text='',
            font=FM(9), fg=_CYAN, bg=_PANEL)
        self.count_label.pack(side='right', padx=12)
        tk.Frame(parent, bg=_AMBER, height=1).pack(fill='x')

        # ── Treeview ──────────────────────────────────────────────
        tf = tk.Frame(parent, bg=_SURF)
        self._tree_frame = tf
        tf.pack(fill='both', expand=True)

        self.tree = ttk.Treeview(tf,
            columns=('avant', 'apres', 'statut'),
            show='headings', selectmode='extended')
        self.tree.heading('avant',  text='  Nom original')
        self.tree.heading('apres',  text='  Nouveau nom')
        self.tree.heading('statut', text='Statut')
        self.tree.column('avant',  width=430, minwidth=160)
        self.tree.column('apres',  width=430, minwidth=160)
        self.tree.column('statut', width=120, minwidth=70, anchor='center')

        sb_y = ttk.Scrollbar(tf, orient='vertical',   command=self.tree.yview)
        sb_x = ttk.Scrollbar(tf, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        sb_y.grid(row=0, column=1, sticky='ns')
        sb_x.grid(row=1, column=0, sticky='ew')
        tf.rowconfigure(0, weight=1)
        tf.columnconfigure(0, weight=1)

        # Tags couleur par ligne entière (via tag sur la row)
        self.tree.tag_configure('ok',     foreground=_GREEN,  background='#0d1f15')
        self.tree.tag_configure('same',   foreground=_MUTED,  background=_SURF)
        self.tree.tag_configure('exists', foreground=_ORANGE, background='#1f1408')
        self.tree.tag_configure('done',   foreground=_CYAN,   background='#071828')
        self.tree.tag_configure('error',  foreground=_RED,    background='#1f0808')
        self.tree.bind('<Double-1>', self._show_preview_popup)

        # ── Barre actions ─────────────────────────────────────────
        tk.Frame(parent, bg=_BORDER, height=1).pack(fill='x')
        act = tk.Frame(parent, bg=_BG)
        act.pack(fill='x', padx=8, pady=(5, 6))

        # Ligne 1 : sélection + export
        row1 = tk.Frame(act, bg=_BG)
        row1.pack(fill='x', pady=(0, 4))
        self.sel_all_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row1, text='Tout sélectionner',
            variable=self.sel_all_var, font=F(9), fg=_TEXT2, bg=_BG,
            selectcolor=_CARD, activebackground=_BG, relief='flat',
            cursor='hand2', command=self._toggle_select).pack(side='left', padx=(0, 8))
        BTN(row1, '✕ Effacer', self._clear,
            bg=_PANEL, fg=_TEXT2, size=9, pad=(8, 4)).pack(side='left')
        BTN(row1, '↓ Rapport', self._export_log,
            bg=_PANEL, fg=_TEXT2, size=9, pad=(8, 4)).pack(side='right')

        # Ligne 2 : bouton principal
        self.apply_btn = BTN(act,
            '  ✓  Renommer les fichiers sélectionnés  ',
            self._apply, bg=_GREEN, fg=_BG, size=11, bold=True, pad=(0, 8))
        self.apply_btn.pack(fill='x')
        self.apply_btn.configure(state='disabled')

    # ── Bannière scraper (redesign compact + lisible) ─────────────
    def _show_tmdb_banner(self, results, mode, files, conv, anime=False):
        ban = self._tmdb_banner
        for w in ban.winfo_children():
            w.destroy()
        if not results:
            ban.pack_forget()
            return

        choices    = [f"{r['title']}  ({r['year']})" for r in results]
        choice_var = tk.StringVar(value=choices[0])

        # Label source
        _src = {
            'video_film':  ('🎬', 'TMDb Films',   _AMBER),
            'video_serie': ('📺', 'TMDb Séries',  _CYAN),
            'video_anime': ('🎌', 'AniList Anime', _PINK),
            'manga':       ('📚', 'AniList',       _PINK),
            'book':        ('📖', 'Open Library',  _TEAL),
        }
        ico, src_name, src_color = _src.get(mode, ('🔍', 'Scraper', _MUTED))

        # Container principal
        main = tk.Frame(ban, bg='#071828')
        main.pack(fill='x', padx=8, pady=(5, 0))

        # Badge source
        badge = tk.Frame(main, bg=src_color)
        badge.pack(side='left', padx=(0, 8))
        tk.Label(badge, text=f'{ico}  {src_name}',
            font=F(9, True), fg=_BG, bg=src_color,
            padx=8, pady=4).pack()

        # Menu sélection résultat
        opt = tk.OptionMenu(main, choice_var, *choices)
        opt.configure(
            font=F(10, True), bg='#0d2540', fg=_TEXT,
            activebackground='#1a4060', activeforeground=_AMBER,
            highlightthickness=0, relief='flat', bd=0,
            padx=10, pady=4, anchor='w')
        opt['menu'].configure(
            font=F(10), bg='#0d2540', fg=_TEXT,
            activebackground=_SEL, activeforeground=_AMBER,
            relief='flat', bd=1)
        opt.pack(side='left', fill='x', expand=True, padx=(0, 8))

        # Boutons action
        def _accept():
            idx = choices.index(choice_var.get())
            self._apply_scrape_result(results[idx], mode, files, conv, anime)
            ban.pack_forget()

        def _edit():
            idx = choices.index(choice_var.get())
            self._scrape_edit_popup(results[idx], mode, files, conv, anime)

        BTN(main, '✓ Accepter', _accept,
            bg=_GREEN, fg=_BG, bold=True, pad=(10, 4)).pack(side='left', padx=(0, 3))
        BTN(main, '✎ Corriger', _edit,
            bg='#1a4060', fg=_TEXT2, pad=(8, 4)).pack(side='left', padx=(0, 3))
        BTN(main, '✕', ban.pack_forget,
            bg='#071828', fg=_MUTED, pad=(6, 4)).pack(side='right')

        # Sous-ligne info (ID + titre original)
        info_f = tk.Frame(ban, bg='#071828')
        info_f.pack(fill='x', padx=8, pady=(2, 5))
        info_lbl = tk.Label(info_f, text='',
            font=FM(9), fg='#3a6080', bg='#071828', anchor='w')
        info_lbl.pack(side='left')

        def _upd_info(*_):
            idx  = choices.index(choice_var.get())
            r    = results[idx]
            orig = r.get('original_title') or r.get('romaji') or r.get('author') or ''
            txt  = f"ID {r['id']}"
            if orig and orig != r['title']:
                txt += f'  ·  {orig}'
            if r.get('year') and r['year'] != '?':
                txt += f'  ·  {r["year"]}'
            info_lbl.configure(text=txt)
        choice_var.trace_add('write', _upd_info)
        _upd_info()

        # Pack la bannière dans sa zone
        ban.pack(in_=self._banner_area, fill='x')
        tk.Frame(self._banner_area, bg=_BORDER, height=1).pack(
            in_=self._banner_area, fill='x')


    def _refresh_preview(self, *_):
        """Rafraîchit la preview quand la convention change.
        Appelé par trace sur video_conv, manga_mode, book_conv.
        Utilise le cache scraper si disponible (conserve le titre TMDb/AniList).
        Sinon recalcule depuis les fichiers du dossier."""
        mode_id = self._current_mode
        if mode_id not in ('video', 'manga', 'book', 'photo', 'custom'):
            return

        # Pas de preview à rafraîchir si aucun fichier n'a été analysé
        if not self.preview_data:
            return

        if self._scrape_cache and mode_id in ('video', 'manga'):
            # Reconstruire depuis le cache scraper (titre TMDb/AniList conservé)
            # after(1) pour laisser tkinter finir de traiter l'événement avant de modifier le treeview
            self.after(1, self._rebuild_from_cache)
        else:
            # Recalculer depuis les noms de fichiers (sans scraper)
            self.after(1, lambda: self._run_preview(mode_id, silent=True))

    def _rebuild_from_cache(self):
        """Rebuilder la preview depuis le cache scraper (quand convention change)."""
        c = self._scrape_cache
        if not c:
            return
        conv = self.video_conv.get() if 'video' in c['mode'] else \
               self.manga_mode.get() if c['mode'] == 'manga' else self.book_conv.get()
        self._apply_scrape_result(
            {'title': c['title'], 'year': c['year'], 'id': c['id']},
            c['mode'], c['files'], conv, c.get('anime', False)
        )


    def _refresh_preview_delayed(self, *_, delay=300):
        """Rafraîchit la preview avec un délai (pour les champs texte)."""
        if hasattr(self, '_refresh_pending_id') and self._refresh_pending_id:
            try: self.after_cancel(self._refresh_pending_id)
            except: pass
        self._refresh_pending_id = self.after(delay, self._refresh_preview)


    def _get_tmdb(self):
        key = self.tmdb_api_key.get().strip()
        if not key:
            raise ValueError("Clé API TMDb manquante — configurez-la dans Paramètres.")
        if self._tmdb is None or self._tmdb.api_key != key:
            self._tmdb = TMDbScraper(key)
        return self._tmdb


    def _scrape_async(self, search_fn, query, year, callback):
        """Lance la recherche dans un thread pour ne pas bloquer l'UI."""
        def _run():
            try:
                results = search_fn(query, year)
                self.after(0, lambda: callback(results, None))
            except Exception as exc:
                self.after(0, lambda: callback(None, str(exc)))
        threading.Thread(target=_run, daemon=True).start()


    def _scrape_dialog(self, results, mode, files, conv, anime=False):
        """Popup de selection — menus deroulants ergonomiques."""
        if not results:
            messagebox.showwarning('Scraper', 'Aucun resultat trouve.')
            return

        dlg = tk.Toplevel(self)
        dlg.title('Confirmer le titre')
        dlg.configure(bg=_BG)
        dlg.geometry('520x320')
        dlg.resizable(False, False)
        dlg.grab_set()

        # Header
        hdr = tk.Frame(dlg, bg=_PANEL)
        hdr.pack(fill='x')
        L(hdr, 'Confirmer le titre', 13, bold=True,
          fg=_AMBER, bg=_PANEL).pack(anchor='w', padx=20, pady=(14,2))
        L(hdr, 'Verifiez et ajustez si necessaire', 9,
          fg=_MUTED, bg=_PANEL).pack(anchor='w', padx=20, pady=(0,12))
        tk.Frame(dlg, bg=_AMBER, height=1).pack(fill='x')

        body = tk.Frame(dlg, bg=_BG)
        body.pack(fill='both', expand=True, padx=24, pady=16)

        # ── Menu deroulant : choix du résultat ──────────────────
        L(body, 'Résultat TMDb', 10, bold=True, fg=_TEXT2, bg=_BG).pack(anchor='w')
        # Labels courts : "Titre (Année)"
        choices = [f"{r['title']}  ({r['year']})" for r in results]
        choice_var = tk.StringVar(value=choices[0])
        opt = tk.OptionMenu(body, choice_var, *choices)
        opt.configure(
            font=F(11), bg=_CARD, fg=_TEXT,
            activebackground=_CARD2, activeforeground=_AMBER,
            highlightthickness=0, relief='flat',
            indicatoron=True, bd=0, padx=12, pady=8,
            anchor='w', width=38)
        opt['menu'].configure(
            font=F(10), bg=_CARD, fg=_TEXT,
            activebackground=_SEL, activeforeground=_AMBER,
            relief='flat', bd=0)
        opt.pack(fill='x', pady=(4,14))

        # ── Champ titre modifiable ───────────────────────────────
        L(body, 'Titre (modifiable)', 10, bold=True, fg=_TEXT2, bg=_BG).pack(anchor='w')
        title_var = tk.StringVar(value=results[0]['title'])
        title_ent = ENT(body, title_var, width=42)
        title_ent.pack(fill='x', pady=(4,0))

        # ── Champ année modifiable ───────────────────────────────
        yr_row = tk.Frame(body, bg=_BG)
        yr_row.pack(fill='x', pady=(10,0))
        L(yr_row, 'Année', 10, bold=True, fg=_TEXT2, bg=_BG).pack(side='left', padx=(0,12))
        year_var = tk.StringVar(value=results[0]['year'])
        ENT(yr_row, year_var, width=8).pack(side='left')

        # ID TMDb (lecture seule, pour info)
        L(yr_row, '   ID TMDb', 10, bold=True, fg=_MUTED, bg=_BG).pack(side='left', padx=(20,8))
        id_var = tk.StringVar(value=str(results[0]['id']))
        LM(yr_row, '', 10, fg=_CYAN, bg=_BG).pack(side='left')
        id_lbl = tk.Label(yr_row, textvariable=id_var,
            font=FM(10), fg=_CYAN, bg=_BG)
        id_lbl.pack(side='left')

        # Sync menu -> champs
        def _on_choice(*_):
            val = choice_var.get()
            idx = choices.index(val)
            r   = results[idx]
            title_var.set(r['title'])
            year_var.set(r['year'])
            id_var.set(str(r['id']))
        choice_var.trace_add('write', _on_choice)

        # ── Boutons ──────────────────────────────────────────────
        tk.Frame(dlg, bg=_BORDER, height=1).pack(fill='x')
        bar = tk.Frame(dlg, bg=_BG)
        bar.pack(fill='x', padx=20, pady=12)

        chosen = {'result': None}

        def _confirm():
            # Construire le résultat avec les valeurs modifiées
            val = choice_var.get()
            idx = choices.index(val)
            r   = dict(results[idx])
            r['title'] = title_var.get().strip() or r['title']
            r['year']  = year_var.get().strip()  or r['year']
            chosen['result'] = r
            dlg.destroy()

        BTN(bar, '✓  Confirmer', _confirm,
            bg=_GREEN, fg=_BG, bold=True, pad=(20,9)).pack(side='right', padx=4)
        BTN(bar, 'Annuler', dlg.destroy,
            bg=_PANEL, pad=(16,9)).pack(side='right', padx=8)

        dlg.wait_window()
        if not chosen['result']:
            return
        self._apply_scrape_result(chosen['result'], mode, files, conv, anime)


    def _apply_scrape_result(self, result, mode, files, conv, anime):
        """Applique le résultat scraper pour générer les noms finaux."""
        title  = result['title']
        year   = result['year']
        tmdb_id = str(result['id'])
        pairs  = []

        # Mettre en cache pour que _refresh_preview puisse rebuilder sans perdre le titre
        self._scrape_cache = {
            'title': title, 'year': year, 'id': result['id'],
            'mode': mode, 'files': files, 'anime': anime
        }

        if mode == 'video_film':
            for fp in files:
                p   = Path(fp)
                if conv == 'tmdb':
                    t_dots = engine.safe_filename(title).replace(' ', '.')
                    new = f"{t_dots}.{year}{p.suffix.lower()}" if year != '?' \
                          else f"{t_dots}{p.suffix.lower()}"
                else:  # plex, kodi, jellyfin, emby — tous: Titre (Année)
                    new = engine.safe_filename(
                        f"{title} ({year}){p.suffix.lower()}") \
                          if year != '?' else engine.safe_filename(
                        f"{title}{p.suffix.lower()}")
                pairs.append((fp, new))

        elif mode == 'video_serie':
            for fp in files:
                p = Path(fp)
                s, e, e2 = engine.extract_season_episode(p.stem)
                ep_w = 3 if anime else 2
                if s is not None and e is not None:
                    ep_str_upper = f"S{s:02d}E{e:0{ep_w}d}-E{e2:0{ep_w}d}" if e2 else f"S{s:02d}E{e:0{ep_w}d}"
                    ep_str_lower = ep_str_upper.lower()
                    if conv == 'tmdb':
                        t_dots = engine.safe_filename(title).replace(' ', '.')
                        new = f"{t_dots}.{ep_str_upper}{p.suffix.lower()}"
                    elif conv == 'plex':
                        new = engine.safe_filename(f"{title} - {ep_str_lower}{p.suffix.lower()}")
                    else:  # kodi, jellyfin, emby
                        new = engine.safe_filename(f"{title} {ep_str_upper}{p.suffix.lower()}")
                else:
                    new = engine.safe_filename(title + p.suffix.lower())
                pairs.append((fp, new))

        elif mode == 'manga':
            for fp in files:
                p   = Path(fp)
                vol = engine.extract_volume(p.stem)
                ser = engine.safe_filename(title)
                yr  = year if year != '?' else ''
                if conv == 'kobo':
                    new = f"{ser} - T{vol:03d}{p.suffix.lower()}"                           if vol is not None else ser + p.suffix.lower()
                elif conv == 'pc':
                    new = f"{ser} v{vol:03d}{p.suffix.lower()}"                           if vol is not None else ser + p.suffix.lower()
                else:  # mylar
                    new = f"{ser} ({yr}) #{vol:03d}{p.suffix.lower()}"                           if vol is not None else ser + p.suffix.lower()
                pairs.append((fp, new))

        elif mode == 'book':
            au = result.get('author', '')
            for fp in files:
                new = engine.rename_book(os.path.basename(fp),
                    au or self.book_author.get(), conv)
                pairs.append((fp, new))

        # Mettre à jour preview
        self.preview_data = pairs
        self.tree.delete(*self.tree.get_children())
        count_ok = 0
        for fp, new_name in pairs:
            old_name = os.path.basename(fp)
            same   = (old_name == new_name)
            dest   = os.path.join(os.path.dirname(fp), new_name)
            exists = os.path.exists(dest) and not same
            if same:     tag, st = 'same', '—'
            elif exists: tag, st = 'exists', '⚠ existe'
            else:        tag, st = 'ok', '✓ prêt'; count_ok += 1
            self.tree.insert('', 'end',
                values=('  '+old_name, '  '+new_name, st), tags=(tag,))

        # NFO avec ID TMDb confirme
        if self.v_nfo.get() and result.get('type') in ('movie', 'tv', 'tv_anime'):
            folder   = self.folder_var.get().strip()
            nfo_type = 'movie' if result['type'] == 'movie' else 'tvshow'
            try:
                engine.generate_nfo(folder, nfo_type, title, tmdb_id)
                self.status_var.set(
                    f'TMDb confirme : {title} ({year}) — ID {tmdb_id} — '
                    f'{count_ok} fichier(s) pret(s)')
            except Exception:
                pass
        else:
            self.status_var.set(
                f'TMDb : {title} ({year}) — {count_ok} fichier(s) pret(s)')

        self.count_label.config(
            text=f'{len(pairs)} fichier(s)  ·  {count_ok} a renommer')
        self.tree.selection_set(self.tree.get_children())
        self.apply_btn.configure(state='normal' if count_ok > 0 else 'disabled')


    def _run_scraper(self, mode):
        """Point d'entrée bouton 'Scraper TMDb/AniList'."""
        if not self.scraper_enabled.get():
            self._run_preview(mode)
            return

        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning('Dossier', 'Choisissez un dossier valide.')
            return

        # Déterminer la query depuis le nom du dossier ou du premier fichier
        folder_name = os.path.basename(folder)
        query = engine.clean_title(folder_name) or folder_name
        year  = engine.extract_year(folder_name)
        conv  = self.video_conv.get()
        anime = self.v_anime.get()

        self.status_var.set(f'Recherche TMDb : "{query}"...')
        self.update_idletasks()

        if mode in ('video_film', 'video_serie'):
            # Collecter les fichiers
            vm      = self.video_mode.get()
            is_film = (vm == 'film_plex')
            files   = self._collect(VIDEO_EXTS)
            if not files:
                return
            # Si un seul fichier, utiliser son nom pour la query
            if len(files) == 1:
                query = engine.clean_title(os.path.basename(files[0]))
                year  = engine.extract_year(os.path.basename(files[0]))

            tmdb = self._get_tmdb()
            search_fn = tmdb.search_movie if is_film else tmdb.search_tv
            v_mode    = 'video_film' if is_film else 'video_serie'

            def _cb(results, err):
                if err:
                    messagebox.showerror('TMDb', err)
                    self.status_var.set('Erreur TMDb')
                    return
                self._scrape_dialog(results, v_mode, files, conv, anime)

            self._scrape_async(search_fn, query, year, _cb)

        elif mode == 'manga':
            exts = set()
            if self.manga_cbz.get():  exts.add('.cbz')
            if self.manga_cbr.get():  exts.add('.cbr')
            if self.manga_pdf.get():  exts.add('.pdf')
            if self.manga_epub.get(): exts.add('.epub')
            files = self._collect(exts)
            if not files:
                return
            s_query = self.manga_series.get().strip() or query

            def _cb_manga(results, err):
                if err:
                    messagebox.showerror('AniList', err)
                    self.status_var.set('Erreur AniList')
                    return
                self._scrape_dialog(results, 'manga', files,
                    self.manga_mode.get())

            self._scrape_async(
                self._anilist.search, s_query, '', _cb_manga)
            # AniList.search prend (query, media_type) — adapter le callback
            # On réappelle correctement :
            def _run_al():
                try:
                    results = self._anilist.search(s_query, 'MANGA')
                    self.after(0, lambda: _cb_manga(results, None))
                except Exception as exc:
                    self.after(0, lambda: _cb_manga(None, str(exc)))
            # Annuler le premier thread et relancer correctement
            threading.Thread(target=_run_al, daemon=True).start()


    # ── Bannière suggestion ───────────────────────────────────────


    def _scrape_edit_popup(self, result, mode, files, conv, anime):
        """Mini popup pour corriger titre / annee avant d'appliquer."""
        dlg = tk.Toplevel(self)
        dlg.title('Modifier')
        dlg.configure(bg=_BG)
        dlg.geometry('460x200')
        dlg.resizable(False, False)
        dlg.grab_set()

        hdr = tk.Frame(dlg, bg=_PANEL)
        hdr.pack(fill='x')
        L(hdr, 'Corriger le titre', 12, bold=True, fg=_AMBER, bg=_PANEL).pack(
            anchor='w', padx=16, pady=10)
        tk.Frame(dlg, bg=_AMBER, height=1).pack(fill='x')

        body = tk.Frame(dlg, bg=_BG)
        body.pack(fill='x', padx=20, pady=16)

        title_var = tk.StringVar(value=result['title'])
        year_var  = tk.StringVar(value=result['year'])

        r1 = tk.Frame(body, bg=_BG)
        r1.pack(fill='x', pady=(0,8))
        L(r1, 'Titre :', 10, bold=True, fg=_TEXT2, bg=_BG).pack(side='left', padx=(0,8))
        ENT(r1, title_var, width=34).pack(side='left', fill='x', expand=True)

        r2 = tk.Frame(body, bg=_BG)
        r2.pack(fill='x')
        L(r2, 'Annee :', 10, bold=True, fg=_TEXT2, bg=_BG).pack(side='left', padx=(0,8))
        ENT(r2, year_var, width=8).pack(side='left')
        L(r2, f"ID : {result['id']}", 9, fg=_MUTED, bg=_BG).pack(side='left', padx=16)

        tk.Frame(dlg, bg=_BORDER, height=1).pack(fill='x')
        bar = tk.Frame(dlg, bg=_BG)
        bar.pack(fill='x', padx=16, pady=10)

        def _ok():
            r = dict(result)
            r['title'] = title_var.get().strip() or r['title']
            r['year']  = year_var.get().strip()  or r['year']
            dlg.destroy()
            self._apply_scrape_result(r, mode, files, conv, anime)
            self._tmdb_banner.pack_forget()

        BTN(bar, '✓ Valider', _ok, bg=_GREEN, fg=_BG, bold=True, pad=(16,8)).pack(
            side='right', padx=4)
        BTN(bar, 'Annuler', dlg.destroy, bg=_PANEL, pad=(12,8)).pack(
            side='right', padx=8)
        dlg.wait_window()

    # ── Scraping automatique unifié ───────────────────────────────


    def _get_files_for_mode(self, mode_id, folder_path=None):
        """Retourne les fichiers filtrés selon le mode actif."""
        if mode_id == 'video':
            exts = VIDEO_EXTS
        elif mode_id == 'manga':
            exts = set()
            if self.manga_cbz.get():  exts.add('.cbz')
            if self.manga_cbr.get():  exts.add('.cbr')
            if self.manga_pdf.get():  exts.add('.pdf')
            if self.manga_epub.get(): exts.add('.epub')
            if not exts: exts = {'.cbz', '.cbr', '.pdf', '.epub'}
        elif mode_id == 'book':
            exts = set()
            if self.book_pdf.get():  exts.add('.pdf')
            if self.book_epub.get(): exts.add('.epub')
            if self.book_mobi.get(): exts.add('.mobi')
            if self.book_djvu.get(): exts.add('.djvu')
            if not exts: exts = {'.epub', '.pdf', '.mobi'}
        elif mode_id == 'photo':
            exts = IMAGE_EXTS
        else:
            return []
        # Priorité : fichiers sélectionnés individuellement
        if self._selected_files:
            valid = [f for f in self._selected_files
                     if os.path.isfile(f) and Path(f).suffix.lower() in exts]
            if valid:
                return valid
        # Sinon scanner le dossier
        if folder_path:
            return self._collect_silent(exts, folder_path)
        return []



    def _do_scrape(self, mode_id, files):
        """Scraping unifie pour toutes les categories."""
        if not files:
            self.status_var.set('Scraper : aucun fichier trouvé')
            return
        # Query depuis le 1er fichier, fallback nom dossier
        first       = os.path.basename(files[0])
        query, year = engine.build_query(first)
        folder = self.folder_var.get().strip()
        if (not query or len(query) < 3) and folder:
            q2, y2 = engine.build_query(os.path.basename(folder))
            if q2: query = q2
            if y2 and not year: year = y2
        # Dernier recours : stem du fichier brut
        if not query or len(query) < 3:
            query = re.sub(r'[._\-]+', ' ', Path(first).stem).strip()
        if not query or len(query) < 3:
            self.status_var.set(f'Scraper : query trop courte depuis "{first}"')
            return

        if mode_id == 'video':
            conv     = self.video_conv.get()
            vmode    = self.video_mode.get()   # 'film' | 'serie' | 'anime'
            is_film  = (vmode == 'film')
            is_anime = (vmode == 'anime')
            v_mode   = 'video_film' if is_film else 'video_serie'
            try:
                tmdb = self._get_tmdb()
            except ValueError:
                return
            # Anime : cherche d'abord sur TMDb TV, fallback AniList
            if is_anime:
                search_fn = tmdb.search_tv
            elif is_film:
                search_fn = tmdb.search_movie
            else:
                search_fn = tmdb.search_tv
            self.status_var.set(f'TMDb : "{query}"...')
            self.update_idletasks()
            def _run_v(q=query, y=year, f=files, vm=v_mode, c=conv,
                       ia=is_anime, sf=search_fn):
                try:
                    res = sf(q, y)
                    # Anime : si TMDb vide, essayer AniList
                    if not res and ia:
                        try:
                            res = self._anilist.search(q, 'ANIME')
                            if res:
                                self.after(0, lambda r=res, fi=f, mo=vm, co=c:
                                    self._show_tmdb_banner(r, mo, fi, co, True))
                                return
                        except Exception:
                            pass
                    if res:
                        self.after(0, lambda r=res, fi=f, mo=vm, co=c, a=ia:
                            self._show_tmdb_banner(r, mo, fi, co, a))
                    else:
                        self.after(0, lambda: self.status_var.set(
                            f'Aucun résultat pour "{q}"'))
                except Exception as exc:
                    err = str(exc)
                    self.after(0, lambda e=err: (
                        self.status_var.set(f'TMDb erreur : {e}'),
                        messagebox.showerror('Erreur TMDb', e)
                    ))
            threading.Thread(target=_run_v, daemon=True).start()

        elif mode_id == 'manga':
            s_query = self.manga_series.get().strip() or query
            conv    = self.manga_mode.get()
            self.status_var.set(f'AniList : "{s_query}"...')
            self.update_idletasks()
            def _run_m(q=s_query, f=files, c=conv):
                try:
                    res = self._anilist.search(q, 'MANGA')
                    if res:
                        self.after(0, lambda r=res, fi=f, co=c:
                            self._show_tmdb_banner(r, 'manga', fi, co))
                    else:
                        self.after(0, lambda: self.status_var.set(
                            f'Aucun résultat AniList pour "{q}"'))
                except Exception as exc:
                    err = str(exc)
                    self.after(0, lambda e=err: self.status_var.set(f'AniList erreur : {e}'))
            threading.Thread(target=_run_m, daemon=True).start()

        elif mode_id == 'book':
            # files est déjà filtré par _get_files_for_mode
            conv = self.book_conv.get()
            au   = self.book_author.get().strip()
            # Détecter format "Auteur - Titre" dans la query ou le stem
            stem = Path(first).stem
            stem_parts = re.split(r' - ', stem, maxsplit=1)
            if len(stem_parts) == 2 and len(stem_parts[0].strip()) < 40:
                # "Tolkien - Le Seigneur" → titre = partie droite, auteur = partie gauche
                if not au:
                    au = stem_parts[0].strip()
                # Recalculer query depuis le titre seul (partie droite)
                q2, _ = engine.build_query(stem_parts[1].strip())
                if q2 and len(q2) >= 3:
                    query = q2
            oq = f"{query} {au}".strip() if au else query
            self.status_var.set(f'Open Library : "{query}"...')
            self.update_idletasks()
            def _run_b(q=oq, tq=query, f=files, c=conv):
                try:
                    res = self._search_openlibrary(q)
                    if not res and q != tq:
                        res = self._search_openlibrary(tq)
                    if res:
                        self.after(0, lambda r=res, fi=f, co=c:
                            self._show_tmdb_banner(r, 'book', fi, co))
                    else:
                        self.after(0, lambda: self.status_var.set(
                            f'Aucun résultat Open Library pour "{tq}"'))
                except Exception as exc:
                    err = str(exc)
                    self.after(0, lambda e=err: self.status_var.set(f'OpenLib erreur : {e}'))
            threading.Thread(target=_run_b, daemon=True).start()


    def _search_openlibrary(self, query: str) -> list:
        """Recherche Open Library (gratuit, sans cle)."""
        qs  = urllib.parse.urlencode({
            'q': query, 'limit': 8,
            'fields': 'key,title,author_name,first_publish_year'})
        url = f"https://openlibrary.org/search.json?{qs}"
        req = urllib.request.Request(url, headers={'User-Agent': 'FileRenamer/1.0'})
        resp = urllib.request.urlopen(req, timeout=8)
        data = json.loads(resp.read().decode('utf-8'))
        results = []
        for r in data.get('docs', [])[:8]:
            au = (r.get('author_name') or ['?'])[0]
            yr = str(r.get('first_publish_year') or '?')
            results.append({
                'id':    r.get('key', '').replace('/works/', ''),
                'title': r.get('title', '?'),
                'year':  yr,
                'author': au,
                'original_title': au,
                'type':  'book',
            })
        return results


    def _trigger_scrape(self, folder_path, delay=200):
        """Déclenche un scrape dossier avec annulation du précédent pending."""
        if hasattr(self, '_scrape_pending_id') and self._scrape_pending_id:
            try: self.after_cancel(self._scrape_pending_id)
            except: pass
        fp = folder_path  # capture locale
        self._scrape_pending_id = self.after(
            delay, lambda: self._auto_scrape(fp))


    def _trigger_scrape_files(self, files, delay=200):
        """Déclenche un scrape fichiers avec annulation du précédent pending."""
        if hasattr(self, '_scrape_pending_id') and self._scrape_pending_id:
            try: self.after_cancel(self._scrape_pending_id)
            except: pass
        fl = list(files)  # capture locale
        self._scrape_pending_id = self.after(
            delay, lambda: self._auto_scrape_from_files(fl))


    def _auto_scrape(self, folder_path):
        """Declenche quand un dossier est selectionne."""
        if not self.scraper_enabled.get():
            return
        mode_id = self._current_mode
        if mode_id not in ('video', 'manga', 'book'):
            return
        files = self._get_files_for_mode(mode_id, folder_path)
        self._do_scrape(mode_id, files)


    def _auto_scrape_from_files(self, files):
        """Declenche quand des fichiers sont selectionnes individuellement."""
        if not self.scraper_enabled.get():
            return
        mode_id = self._current_mode
        if mode_id not in ('video', 'manga', 'book'):
            return
        self._do_scrape(mode_id, files)


    def _collect_silent(self, exts, folder_path):
        """Collecte fichiers sans popup."""
        if not folder_path or not os.path.isdir(folder_path):
            return []
        files = []
        try:
            for fn in os.listdir(folder_path):
                fp = os.path.join(folder_path, fn)
                if os.path.isfile(fp) and Path(fn).suffix.lower() in exts:
                    files.append(fp)
        except Exception:
            pass
        return sorted(files)

    # ── Header ────────────────────────────────────────────────────


    def _browse_folder(self):
        d = filedialog.askdirectory(title='Choisir un dossier')
        if d:
            self._selected_files = []
            self._scrape_cache   = None
            self.folder_var.set(d)   # déclenche trace -> _on_folder_change
            self._trigger_scrape(d)


    def _browse_files(self):
        files = filedialog.askopenfilenames(
            title='Choisir des fichiers',
            filetypes=[
                ('Tous les medias',
                 '*.mkv *.mp4 *.avi *.mov *.wmv *.m4v *.ts '
                 '*.cbz *.cbr *.epub *.pdf *.mobi '
                 '*.jpg *.jpeg *.png *.gif *.webp'),
                ('Videos',  '*.mkv *.mp4 *.avi *.mov *.wmv *.m4v *.ts *.webm'),
                ('Mangas',  '*.cbz *.cbr *.pdf *.epub'),
                ('Livres',  '*.epub *.pdf *.mobi *.djvu'),
                ('Images',  '*.jpg *.jpeg *.png *.gif *.webp *.tiff'),
                ('Tous',    '*.*'),
            ])
        if not files:
            return
        folder = os.path.dirname(files[0])
        self.folder_var.set(folder)
        self._selected_files = list(files)
        self._scrape_cache   = None
        self.status_var.set(f'{len(files)} fichier(s) selectionne(s)')
        self._trigger_scrape_files(list(files))


    def _toggle_select(self):
        if self.sel_all_var.get(): self.tree.selection_set(self.tree.get_children())
        else:                       self.tree.selection_remove(self.tree.get_children())


    def _clear(self):
        self.tree.delete(*self.tree.get_children())
        self.preview_data.clear()
        self.folder_preview_data.clear()
        self.count_label.config(text='')
        self.apply_btn.configure(state='disabled')
        self.status_var.set('Prêt.')

    def _clear_with_cache(self):
        """Efface la preview ET le cache scraper (changement de dossier/mode)."""
        self._scrape_cache = None
        self._clear()


    def _collect(self, exts, silent=False):
        # Priorité aux fichiers sélectionnés individuellement
        if self._selected_files:
            return [f for f in self._selected_files
                    if Path(f).suffix.lower() in exts]
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            if not silent:
                messagebox.showwarning('Dossier invalide', 'Selectionnez un dossier ou des fichiers.')
            return []
        files = []
        if self.recursive_var.get():
            for root, _, fnames in os.walk(folder):
                for fn in fnames:
                    if Path(fn).suffix.lower() in exts:
                        files.append(os.path.join(root, fn))
        else:
            for fn in os.listdir(folder):
                fp = os.path.join(folder, fn)
                if os.path.isfile(fp) and Path(fn).suffix.lower() in exts:
                    files.append(fp)
        return sorted(files)


    def _run_preview(self, mode, silent=False):
        self._clear()
        self.status_var.set('Analyse en cours…')
        self.update_idletasks()
        pairs = []

        if mode == 'video':
            files    = self._collect(VIDEO_EXTS, silent=silent)
            vm       = self.video_mode.get()
            conv     = self.video_conv.get()
            is_film  = (vm == 'film')
            is_anime = (vm == 'anime')
            if self.v_multi_titles.get() and is_film and files:
                pairs = self._multi_title_dialog(files, conv)
            else:
                for fp in files:
                    fn  = os.path.basename(fp)
                    new = engine.rename_movie(fn, conv) if is_film \
                          else engine.rename_series(fn, conv, anime=is_anime)
                    pairs.append((fp, new))
            # Generer .nfo si demande
            if self.v_nfo.get() and files:
                folder    = self.folder_var.get().strip()
                nfo_type  = 'movie' if is_film else 'tvshow'
                first_fn  = os.path.basename(files[0])
                nfo_title = engine.clean_title(first_fn)
                tmdb_id   = self.v_tmdb_id.get().strip()
                try:
                    nfo_path = engine.generate_nfo(folder, nfo_type, nfo_title, tmdb_id)
                    self.status_var.set(f'NFO genere : {os.path.basename(nfo_path)}')
                except Exception as exc:
                    self.status_var.set(f'Erreur NFO : {exc}')

        elif mode == 'manga':
            exts = set()
            if self.manga_cbz.get():  exts.add('.cbz')
            if self.manga_cbr.get():  exts.add('.cbr')
            if self.manga_pdf.get():  exts.add('.pdf')
            if self.manga_epub.get(): exts.add('.epub')
            files = self._collect(exts, silent=silent)
            mm, s, y = self.manga_mode.get(), self.manga_series.get(), self.manga_year.get()
            mylar_no_year = False
            for fp in files:
                fn = os.path.basename(fp)
                if   mm == 'kobo':  new = engine.rename_manga_kobo(fn, s)
                elif mm == 'pc':    new = engine.rename_manga_pc(fn, s)
                else:
                    new = engine.rename_manga_mylar(fn, s, y)
                    # Vérifier si l'année est absente du résultat
                    if not y.strip() and not engine.extract_year(fn):
                        mylar_no_year = True
                pairs.append((fp, new))
            if mylar_no_year:
                self.status_var.set(
                    '\u26a0  Mylar3 : aucune annee trouvee - '
                    'saisissez l annee dans le champ pour obtenir Serie (Annee) #001')

        elif mode == 'book':
            exts = set()
            if self.book_pdf.get():  exts.add('.pdf')
            if self.book_epub.get(): exts.add('.epub')
            if self.book_mobi.get(): exts.add('.mobi')
            if self.book_djvu.get(): exts.add('.djvu')
            files = self._collect(exts, silent=silent)
            au, conv = self.book_author.get(), self.book_conv.get()
            for fp in files:
                pairs.append((fp, engine.rename_book(os.path.basename(fp), au, conv)))

        elif mode == 'photo':
            files = self._collect(IMAGE_EXTS, silent=silent)
            for fp in files:
                pairs.append((fp, engine.rename_photo(fp,
                    self.photo_prefix.get(), self.photo_exif.get())))

        elif mode == 'custom':
            exts = set()
            if self.custom_video.get(): exts |= VIDEO_EXTS
            if self.custom_book.get():  exts |= BOOK_EXTS
            if self.custom_manga.get(): exts |= MANGA_EXTS
            if self.custom_image.get(): exts |= IMAGE_EXTS
            files = self._collect(exts, silent=silent)
            tmpl  = self.custom_template.get()
            extra = {'auteur': self.custom_author.get(), 'prefixe': self.custom_prefix.get()}
            for fp in files:
                pairs.append((fp, engine.rename_custom(fp, tmpl, extra)))

        self.preview_data = pairs
        count_ok = 0
        for fp, new_name in pairs:
            old_name = os.path.basename(fp)
            same   = (old_name == new_name)
            dest   = os.path.join(os.path.dirname(fp), new_name)
            exists = os.path.exists(dest) and not same
            if same:     tag, st = 'same', '—'
            elif exists: tag, st = 'exists', '⚠ existe'
            else:        tag, st = 'ok', '✓ prêt'; count_ok += 1
            self.tree.insert('', 'end',
                values=('  '+old_name, '  '+new_name, st), tags=(tag,))

        # Dossier optionnel
        self.folder_preview_data = []
        if self.rename_folder_var.get() and pairs:
            folder_path = self.folder_var.get().strip()
            folder_name = os.path.basename(folder_path)
            first_file  = os.path.basename(pairs[0][0])
            base_title  = engine.clean_title(first_file)
            base_year   = engine.extract_year(first_file)

            if mode == 'video':
                conv    = self.video_conv.get()
                is_film = (self.video_mode.get() == 'film')
                if is_film:
                    new_folder = engine.safe_filename(
                        f"{base_title} ({base_year})" if base_year else base_title)
                else:
                    new_folder = engine.safe_filename(base_title)
            elif mode == 'manga':
                mm  = self.manga_mode.get()
                yr  = self.manga_year.get().strip() or base_year
                ser = self.manga_series.get().strip() or base_title
                new_folder = engine.safe_filename(
                    f"{ser} ({yr})" if mm == 'mylar' and yr else ser)
            elif mode == 'book':
                au, conv = self.book_author.get().strip(), self.book_conv.get()
                if conv in ('calibre', 'adobe') and au:
                    new_folder = engine.safe_filename(au.title())
                else:
                    new_folder = engine.safe_filename(base_title)
            else:
                new_folder = engine.safe_filename(base_title)

            if new_folder and new_folder != folder_name:
                dest_folder = os.path.join(os.path.dirname(folder_path), new_folder)
                if os.path.exists(dest_folder):
                    tag_f, st_f = 'exists', '⚠ dossier'
                else:
                    tag_f, st_f = 'ok', '📁 dossier'; count_ok += 1
                self.folder_preview_data = [(folder_path, dest_folder)]
                self.tree.insert('', 0,
                    values=(f'  📁 {folder_name}', f'  📁 {new_folder}', st_f),
                    tags=(tag_f,))

        n = len(pairs)
        self.count_label.config(text=f'{n} fichier(s)  ·  {count_ok} à renommer')
        self.tree.selection_set(self.tree.get_children())
        self.apply_btn.configure(state='normal' if count_ok > 0 else 'disabled')
        self.status_var.set(f'{n} fichier(s) analysé(s) — {count_ok} à renommer')


    def _apply(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo('Rien à faire', 'Aucune ligne sélectionnée.'); return
        if not messagebox.askyesno('Confirmer',
                f'Renommer {len(selected)} élément(s) ?\nIrréversible.', icon='warning'): return

        done, skipped, errors, errs = 0, 0, 0, []
        all_items  = self.tree.get_children()
        iid_to_idx = {iid: i for i, iid in enumerate(all_items)}
        has_folder = bool(self.folder_preview_data)

        for iid in selected:
            idx = iid_to_idx.get(iid)
            if idx is None: continue
            if has_folder and idx == 0: continue
            file_idx = idx - (1 if has_folder else 0)
            if file_idx < 0 or file_idx >= len(self.preview_data): continue

            fp, new_name = self.preview_data[file_idx]
            fp       = os.path.abspath(fp)
            old_name = os.path.basename(fp)
            dest     = os.path.join(os.path.dirname(fp), new_name)

            if old_name == new_name: skipped += 1; continue
            if os.path.exists(dest):
                self.tree.item(iid, values=('  '+old_name, '  '+new_name, '⚠ ignoré'),
                    tags=('exists',)); skipped += 1; continue
            try:
                # Essai 1 : os.rename (le plus fiable sur réseau SMB)
                try:
                    os.rename(fp, dest)
                except OSError:
                    # Essai 2 : shutil.move
                    try:
                        shutil.move(fp, dest)
                    except OSError:
                        # Essai 3 : copie + suppression (contourne WinError 5 réseau)
                        shutil.copy2(fp, dest)
                        try: os.remove(fp)
                        except: pass
                self.preview_data[file_idx] = (dest, new_name)
                self.tree.item(iid, values=('  '+old_name, '  '+new_name, '✓ renommé'),
                    tags=('done',))
                done += 1
            except OSError as exc:
                code  = getattr(exc, 'winerror', 0)
                label = '✕ accès refusé' if code == 5 else '✕ fichier ouvert' if code == 32 else '✕ erreur'
                self.tree.item(iid, values=('  '+old_name, '  '+new_name, label),
                    tags=('error',))
                errs.append(f'{old_name} : [WinError {code}] {exc.strerror} — "{old_name}" -> "{new_name}"')
                errors += 1

        if self.folder_preview_data:
            old_dir, new_dir = self.folder_preview_data[0]
            if not os.path.exists(new_dir):
                try:
                    shutil.move(old_dir, new_dir)
                    self.folder_var.set(new_dir); done += 1
                except OSError as exc:
                    errs.append(f'[DOSSIER] {exc}'); errors += 1

        self.status_var.set(f'Terminé — {done} renommé(s), {skipped} ignoré(s), {errors} erreur(s)')
        detail = ('\n\nDétails erreurs :\n' + '\n'.join(errs[:8])) if errs else ''
        messagebox.showinfo('Terminé',
            f'{done} renommé(s)\n{skipped} ignoré(s)\n{errors} erreur(s){detail}')

        if errors and sys.platform == 'win32':
            try:
                if not is_admin() and any('5' in d for d in errs):
                    if messagebox.askyesno('Droits', 'Relancer en Admin ?'):
                        if relaunch_as_admin(): self.destroy()
            except: pass


    def _multi_title_dialog(self, files, conv):
        dlg = tk.Toplevel(self)
        dlg.title('Multi-titres')
        dlg.configure(bg=_BG)
        dlg.geometry('800x540')
        dlg.grab_set()

        L(dlg, 'Saisissez le titre pour chaque fichier', 13, bold=True,
            fg=_AMBER, bg=_BG).pack(anchor='w', padx=20, pady=(16,4))
        L(dlg, 'Vide = titre extrait automatiquement', 9, fg=_MUTED, bg=_BG).pack(
            anchor='w', padx=20, pady=(0,8))
        tk.Frame(dlg, bg=_BORDER, height=1).pack(fill='x')

        canvas = tk.Canvas(dlg, bg=_PANEL, highlightthickness=0)
        sb = ttk.Scrollbar(dlg, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        canvas.pack(side='top', fill='both', expand=True)
        inner = tk.Frame(canvas, bg=_PANEL)
        wid = canvas.create_window((0,0), window=inner, anchor='nw')
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(wid, width=e.width))
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Enter>', lambda e: canvas.bind_all('<MouseWheel>',
            lambda ev: canvas.yview_scroll(int(-1*(ev.delta/120)),'units')))
        canvas.bind('<Leave>', lambda e: canvas.unbind_all('<MouseWheel>'))

        title_vars, year_vars = [], []
        for fp in files:
            fn = os.path.basename(fp)
            row = tk.Frame(inner, bg=_CARD2)
            row.pack(fill='x', padx=12, pady=3)
            LM(row, fn, 9, fg=_MUTED, bg=_CARD2).pack(anchor='w', padx=10, pady=(6,2))
            fields = tk.Frame(row, bg=_CARD2)
            fields.pack(fill='x', padx=10, pady=(0,8))
            tv = tk.StringVar(value=engine.clean_title(fn))
            yv = tk.StringVar(value=engine.extract_year(fn))
            title_vars.append(tv); year_vars.append(yv)
            L(fields, 'Titre :', 10, fg=_TEXT2, bg=_CARD2).pack(side='left', padx=(0,6))
            ENT(fields, tv, width=30).pack(side='left', padx=(0,12))
            L(fields, 'Année :', 10, fg=_TEXT2, bg=_CARD2).pack(side='left', padx=(0,6))
            ENT(fields, yv, width=6).pack(side='left')

        tk.Frame(dlg, bg=_BORDER, height=1).pack(fill='x')
        bar = tk.Frame(dlg, bg=_BG)
        bar.pack(fill='x', padx=16, pady=10)

        result = []
        def _ok():
            for i, fp in enumerate(files):
                p = Path(fp)
                t = title_vars[i].get().strip() or engine.clean_title(p.name)
                y = year_vars[i].get().strip()  or engine.extract_year(p.stem)
                base = f"{engine.safe_filename(t)} ({y})" if y else engine.safe_filename(t)
                result.append((fp, base + p.suffix.lower()))
            dlg.destroy()

        BTN(bar, '✓  Valider', _ok, bg=_GREEN, fg=_BG, bold=True).pack(side='right', padx=4)
        BTN(bar, 'Annuler', dlg.destroy, bg=_PANEL).pack(side='right', padx=8)
        dlg.wait_window()
        return result


    def _show_preview_popup(self, event):
        sel = self.tree.selection()
        if not sel: return
        all_items  = self.tree.get_children()
        iid_to_idx = {iid: i for i, iid in enumerate(all_items)}
        idx = iid_to_idx.get(sel[0])
        if idx is None: return
        file_idx = idx - (1 if self.folder_preview_data else 0)
        if file_idx < 0 or file_idx >= len(self.preview_data): return
        fp, _ = self.preview_data[file_idx]
        fp = os.path.abspath(fp)
        ext = Path(fp).suffix.lower()
        if ext not in IMAGE_EXTS and ext not in {'.cbz', '.cbr'}: return
        if not PIL_OK:
            messagebox.showinfo('Aperçu', 'pip install pillow'); return
        try:
            if ext in IMAGE_EXTS:
                img = Image.open(fp)
            elif ext == '.cbz':
                import zipfile
                with zipfile.ZipFile(fp) as z:
                    names = sorted([n for n in z.namelist()
                        if n.lower().endswith(('.jpg','.jpeg','.png','.webp'))])
                    if not names: return
                    with z.open(names[0]) as imgf:
                        img = Image.open(imgf); img.load()
            img.thumbnail((380, 540))
            from PIL import ImageTk
            photo = ImageTk.PhotoImage(img)
            popup = tk.Toplevel(self)
            popup.title(Path(fp).name)
            popup.configure(bg=_BG)
            popup.resizable(False, False)
            L(popup, Path(fp).name, 10, bold=True, fg=_AMBER, bg=_BG).pack(
                padx=14, pady=(12,4))
            il = tk.Label(popup, image=photo, bg=_BG)
            il.image = photo
            il.pack(padx=14, pady=(0,4))
            BTN(popup, 'Fermer', popup.destroy, bg=_PANEL).pack(pady=(0,12))
        except Exception as exc:
            messagebox.showwarning('Aperçu', str(exc))


    def _export_log(self):
        if not self.preview_data:
            messagebox.showinfo('Vide', 'Lancez d\'abord une analyse.'); return
        path = filedialog.asksaveasfilename(
            defaultextension='.txt',
            filetypes=[('Texte', '*.txt'), ('JSON', '*.json')],
            title='Sauvegarder le rapport')
        if not path: return
        if path.endswith('.json'):
            with open(path, 'w', encoding='utf-8') as f:
                json.dump([{'original': os.path.basename(fp), 'nouveau': n,
                    'dossier': os.path.dirname(fp)} for fp, n in self.preview_data],
                    f, ensure_ascii=False, indent=2)
        else:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(f'FileRenamer — {datetime.now():%Y-%m-%d %H:%M:%S}\n{"="*60}\n\n')
                for fp, new in self.preview_data:
                    old = os.path.basename(fp)
                    f.write(f'{old}\n  →  {new}\n\n' if old != new else f'{old}  (inchangé)\n\n')
        self.status_var.set('Rapport : ' + path)
        messagebox.showinfo('Sauvegardé', path)


# ═══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    app = App()
    app.mainloop()