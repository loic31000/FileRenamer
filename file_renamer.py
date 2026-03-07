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
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_OK = True
except ImportError:
    PIL_OK = False


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

    @staticmethod
    def clean_title(raw_name: str) -> str:
        name = Path(raw_name).stem
        name = re.sub(r'[._]', ' ', name)
        name = re.sub(r'[\(\[\{][^\)\]\}]*[\)\]\}]', ' ', name)
        # Retire les patterns épisode/saison et numéros de tome du titre
        name = re.sub(r'\b[Ss]\d{1,2}[Ee]\d{1,2}\b', '', name)
        name = re.sub(r'\b\d{1,2}[xX]\d{1,2}\b', '', name)
        name = re.sub(r'\b[Ee]p?\d{1,3}\b', '', name, flags=re.IGNORECASE)
        name = re.sub(r'(?:tome|vol(?:ume)?)[.\s_-]?\d{1,4}', '', name, flags=re.IGNORECASE)
        name = re.sub(r'(?<=[_\s\-\.#])([tTvV])\d{1,3}(?![a-zA-Z])', '', name)
        name = re.sub(r'#\d{1,4}', '', name)
        name = re.sub(r'[\s_-]\d{1,4}$', '', name)
        tokens = name.split()
        cleaned = []
        for tok in tokens:
            low = tok.lower().strip('.-_')
            if low in NOISE_WORDS:
                break
            if re.match(r'^(19|20)\d{2}$', tok):
                break
            cleaned.append(tok)
        result = ' '.join(cleaned).strip()
        return re.sub(r'\s+', ' ', result).title()

    @staticmethod
    def extract_year(raw_name: str) -> str:
        m = re.search(r'(19|20)\d{2}', raw_name)
        return m.group(0) if m else ''

    @staticmethod
    def extract_season_episode(raw_name: str):
        patterns = [
            r'[Ss](\d{1,2})[Ee](\d{1,2})',
            r'(\d{1,2})[xX](\d{1,2})',
            r'[Ss]eason\s*(\d{1,2})\s*[Ee]p(?:isode)?\s*(\d{1,2})',
        ]
        for p in patterns:
            m = re.search(p, raw_name)
            if m:
                return int(m.group(1)), int(m.group(2))
        m = re.search(r'(?:[Ee]p?|episode\s*)(\d{1,3})', raw_name, re.IGNORECASE)
        if m:
            return None, int(m.group(1))
        return None, None

    @staticmethod
    def extract_volume(raw_name: str):
        patterns = [
            r'(?:tome|vol(?:ume)?)[.\s_-]?(\d{1,4})',   # tome42, vol.7, volume 3
            r'(?<=[_\s\-\.#])([tT])(\d{1,3})(?![a-zA-Z])',  # _T15, -T03
            r'(?<=[_\s\-\.#])([vV])(\d{1,3})(?![a-zA-Z])',  # _v7, _V007
            r'#(\d{1,4})',                                # #018
            r'[\s_-](\d{1,4})$',                         # bleach_018 (fin de nom)
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
        name = re.sub(r'[<>:"/\\|?*]', '-', name)
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
    # Kodi                   : Titre (Année).ext  (idem, standard NFO)
    # Infuse                 : Titre (Année).ext
    # MediaPortal            : Titre (Année).ext
    # Tous partagent le même format de base — différences sur le nom de dossier
    VIDEO_CONVENTIONS = {
        'plex':        ('Plex / Emby / Jellyfin', 'Titre (Année).ext'),
        'kodi':        ('Kodi / XBMC',             'Titre (Année).ext'),
        'infuse':      ('Infuse / Apple TV',        'Titre (Année).ext'),
        'mediaportal': ('MediaPortal',              'Titre.ext'),
    }
    SERIES_CONVENTIONS = {
        'plex':        ('Plex / Emby / Jellyfin', 'Titre - S01E01.ext'),
        'kodi':        ('Kodi / XBMC',             'Titre S01E01.ext'),
        'infuse':      ('Infuse / Apple TV',        'Titre - S01E01.ext'),
        'mediaportal': ('MediaPortal',              'Titre_S01E01.ext'),
    }

    def rename_movie(self, fp: str, convention: str = 'plex') -> str:
        p = Path(fp)
        title = self.clean_title(p.name)
        year  = self.extract_year(p.stem)
        ext   = p.suffix.lower()
        if convention == 'mediaportal':
            base = title
        else:
            base = f"{title} ({year})" if year else title
        return self.safe_filename(base + ext)

    # Alias pour compat
    def rename_movie_plex(self, fp: str) -> str:
        return self.rename_movie(fp, 'plex')

    def rename_series(self, fp: str, convention: str = 'plex') -> str:
        p = Path(fp)
        s, e  = self.extract_season_episode(p.stem)
        title = self.clean_title(p.name)
        ext   = p.suffix.lower()
        if s is not None and e is not None:
            ep_str = f"S{s:02d}E{e:02d}"
            if convention == 'kodi':
                return self.safe_filename(f"{title} {ep_str}{ext}")
            elif convention == 'mediaportal':
                return self.safe_filename(f"{title}_S{s:02d}E{e:02d}{ext}")
            else:  # plex, infuse
                return self.safe_filename(f"{title} - {ep_str}{ext}")
        elif e is not None:
            return self.safe_filename(f"{title} - E{e:03d}{ext}")
        return self.safe_filename(title + ext)

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
        s, e  = self.extract_season_episode(p.stem)
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
        ('video',  '▶', 'Films & Séries'),
        ('manga',  '◈', 'Mangas'),
        ('book',   '◉', 'Livres & BD'),
        ('photo',  '◎', 'Photos'),
        ('custom', '◆', 'Personnalisé'),
    ]

    def __init__(self):
        super().__init__()
        self.title('FileRenamer')
        self.geometry('1480x900')
        self.minsize(1200, 720)
        self.configure(bg=_BG)

        # ── Variables ─────────────────────────────────────────────
        self.folder_var          = tk.StringVar()
        self.recursive_var       = tk.BooleanVar(value=False)
        self.rename_folder_var   = tk.BooleanVar(value=False)
        self.video_mode          = tk.StringVar(value='film_plex')
        self.video_conv          = tk.StringVar(value='plex')
        self.v_overwrite         = tk.BooleanVar(value=False)
        self.v_multi_titles      = tk.BooleanVar(value=False)
        self.manga_mode          = tk.StringVar(value='kobo')
        self.manga_series        = tk.StringVar()
        self.manga_year          = tk.StringVar()
        self.manga_cbz           = tk.BooleanVar(value=True)
        self.manga_cbr           = tk.BooleanVar(value=True)
        self.manga_pdf           = tk.BooleanVar(value=True)
        self.manga_epub          = tk.BooleanVar(value=True)
        self.book_author         = tk.StringVar()
        self.book_conv           = tk.StringVar(value='calibre')
        self.book_pdf            = tk.BooleanVar(value=True)
        self.book_epub           = tk.BooleanVar(value=True)
        self.book_mobi           = tk.BooleanVar(value=True)
        self.book_djvu           = tk.BooleanVar(value=False)
        self.photo_prefix        = tk.StringVar()
        self.photo_exif          = tk.BooleanVar(value=True)
        self.custom_template     = tk.StringVar(value='{titre} ({année}){ext}')
        self.custom_author       = tk.StringVar()
        self.custom_prefix       = tk.StringVar()
        self.custom_video        = tk.BooleanVar(value=True)
        self.custom_book         = tk.BooleanVar(value=True)
        self.custom_manga        = tk.BooleanVar(value=True)
        self.custom_image        = tk.BooleanVar(value=True)
        self.preview_data        = []
        self.folder_preview_data = []
        self._pages              = {}
        self._nav_btns           = {}

        self._build_ui()
        self._apply_style()
        self._animate_border()

    # ── TTK ───────────────────────────────────────────────────────

    def _apply_style(self):
        s = ttk.Style(self)
        s.theme_use('clam')
        s.configure('Treeview',
            background=_SURF, fieldbackground=_SURF,
            foreground=_TEXT, font=FM(10), rowheight=28, borderwidth=0)
        s.configure('Treeview.Heading',
            background=_PANEL, foreground=_AMBER,
            font=F(10, True), relief='flat')
        s.map('Treeview',
            background=[('selected', _SEL)],
            foreground=[('selected', _CYAN)])
        s.configure('TScrollbar',
            background=_PANEL, troughcolor=_BG,
            borderwidth=0, arrowsize=10)

    # ── Animation bordure header ──────────────────────────────────

    def _animate_border(self):
        """Fait pulser subtilement la bordure amber du header."""
        colors = [_AMBER, '#e8961a', '#d4850f', '#e8961a', _AMBER]
        self._anim_idx = 0
        def _step():
            if hasattr(self, '_header_border'):
                c = colors[self._anim_idx % len(colors)]
                self._header_border.configure(bg=c)
                self._anim_idx += 1
                self.after(600, _step)
        self.after(800, _step)

    # ── Squelette ─────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._header_border = tk.Frame(self, bg=_AMBER, height=1)
        self._header_border.pack(fill='x')

        body = tk.Frame(self, bg=_BG)
        body.pack(fill='both', expand=True)

        # Col 1 : nav latérale (72px) — icônes
        nav_col = tk.Frame(body, bg=_SURF, width=72)
        nav_col.pack(side='left', fill='y')
        nav_col.pack_propagate(False)
        self._build_nav(nav_col)

        tk.Frame(body, bg=_BORDER, width=1).pack(side='left', fill='y')

        # Col 2 : options du mode (380px)
        self._page_area = tk.Frame(body, bg=_PANEL, width=390)
        self._page_area.pack(side='left', fill='y')
        self._page_area.pack_propagate(False)

        tk.Frame(body, bg=_BORDER, width=1).pack(side='left', fill='y')

        # Col 3 : prévisualisation
        right = tk.Frame(body, bg=_BG)
        right.pack(side='left', fill='both', expand=True)
        self._build_right(right)

        # Barre statut
        bar = tk.Frame(self, bg=_SURF, height=26)
        bar.pack(fill='x', side='bottom')
        tk.Frame(bar, bg=_BORDER, height=1).pack(fill='x', side='top')
        self.status_var = tk.StringVar(value='Prêt')
        tk.Label(bar, textvariable=self.status_var,
            bg=_SURF, fg=_MUTED, font=FM(9), anchor='w').pack(
            side='left', padx=14, fill='y')
        tk.Label(bar, text='FileRenamer v4  ·  2026',
            bg=_SURF, fg=_MUTED, font=FM(9)).pack(side='right', padx=14)

        self._build_all_pages()
        self._show_page('video')

    # ── Header ────────────────────────────────────────────────────

    def _build_header(self):
        hdr = tk.Frame(self, bg=_SURF)
        hdr.pack(fill='x')
        inner = tk.Frame(hdr, bg=_SURF)
        inner.pack(fill='x', padx=20, pady=12)

        # Logo
        logo_frame = tk.Frame(inner, bg=_SURF)
        logo_frame.pack(side='left')
        tk.Label(logo_frame, text='FR', font=F(18, True),
            fg=_BG, bg=_AMBER, padx=10, pady=2).pack(side='left')
        tk.Frame(logo_frame, bg=_SURF, width=10).pack(side='left')
        tk.Label(logo_frame, text='FileRenamer',
            font=F(16, True), fg=_TEXT, bg=_SURF).pack(side='left')
        tk.Label(logo_frame, text='  /  Films · Mangas · Livres · Photos',
            font=F(11), fg=_MUTED, bg=_SURF).pack(side='left', padx=(4,0))

        # Dossier (centré dans le header)
        folder_frame = tk.Frame(inner, bg=_SURF)
        folder_frame.pack(side='left', fill='x', expand=True, padx=30)

        row = tk.Frame(folder_frame, bg=_BORDER, highlightthickness=0)
        row.pack(fill='x')
        tk.Label(row, text='📁', bg=_BORDER, fg=_AMBER, font=F(12)).pack(
            side='left', padx=(8,4), pady=4)
        tk.Entry(row, textvariable=self.folder_var,
            font=FM(10), bg=_BORDER, fg=_TEXT,
            insertbackground=_AMBER, relief='flat', bd=0).pack(
            side='left', fill='x', expand=True, pady=6)
        BTN(row, '…', self._browse_folder, bg=_AMBER, fg=_BG, bold=True,
            pad=(10,6)).pack(side='left', padx=(4,4), pady=4)

        # Options
        opts = tk.Frame(folder_frame, bg=_SURF)
        opts.pack(anchor='w', pady=(4,0))
        CHK(opts, 'Sous-dossiers', self.recursive_var, fg=_CYAN).pack(
            side='left', padx=(0,16))
        CHK(opts, 'Renommer le dossier', self.rename_folder_var, fg=_TEAL).pack(
            side='left')

        # Droits admin
        if sys.platform == 'win32':
            try:
                ok = is_admin()
            except Exception:
                ok = False
            adm = tk.Frame(inner, bg=_SURF)
            adm.pack(side='right')
            if ok:
                tk.Label(adm, text='✓ Admin', font=F(10),
                    fg=_GREEN, bg=_SURF).pack()
            else:
                def _rel():
                    if relaunch_as_admin(): self.destroy()
                    else: messagebox.showerror('Erreur', 'Clic droit → Exécuter en tant qu\'administrateur')
                BTN(adm, '⚠ Admin', _rel, bg=_ORANGE, fg=_BG, bold=True).pack()

    # ── Navigation latérale (icônes) ──────────────────────────────

    def _build_nav(self, parent):
        tk.Frame(parent, bg=_SURF, height=16).pack()

        for mode_id, icon, label in self.MODES:
            cell = tk.Frame(parent, bg=_SURF, cursor='hand2')
            cell.pack(fill='x', pady=2)

            indicator = tk.Frame(cell, bg=_SURF, width=3)
            indicator.pack(side='left', fill='y')

            inner = tk.Frame(cell, bg=_SURF)
            inner.pack(side='left', fill='both', expand=True)

            icon_lbl = tk.Label(inner, text=icon, font=F(18),
                fg=_MUTED, bg=_SURF, cursor='hand2')
            icon_lbl.pack(pady=(10,2))

            name_lbl = tk.Label(inner, text=label.split()[0],
                font=F(8), fg=_MUTED, bg=_SURF, cursor='hand2')
            name_lbl.pack(pady=(0,10))

            all_w = [cell, inner, icon_lbl, name_lbl]

            # Clic
            for w in all_w:
                w.bind('<Button-1>', lambda e, m=mode_id: self._show_page(m))

            # Hover
            def _enter(e, ws=all_w):
                for w in ws:
                    try: w.configure(bg=_CARD)
                    except: pass
            def _leave(e, ws=all_w, m=mode_id):
                bg = _CARD2 if self._pages.get('_current') == m else _SURF
                for w in ws:
                    try: w.configure(bg=bg)
                    except: pass
            for w in all_w:
                w.bind('<Enter>', _enter)
                w.bind('<Leave>', _leave)

            self._nav_btns[mode_id] = (cell, inner, icon_lbl, name_lbl, indicator)

    def _show_page(self, mode_id):
        self._pages['_current'] = mode_id
        for pid, page in self._pages.items():
            if pid == '_current': continue
            page.place_forget()
            cell, inner, icon_lbl, name_lbl, ind = self._nav_btns[pid]
            for w in [cell, inner, icon_lbl, name_lbl]:
                try: w.configure(bg=_SURF, fg=_MUTED)
                except: w.configure(bg=_SURF)
            ind.configure(bg=_SURF)

        self._pages[mode_id].place(x=0, y=0, relwidth=1, relheight=1)
        cell, inner, icon_lbl, name_lbl, ind = self._nav_btns[mode_id]
        for w in [cell, inner]:
            w.configure(bg=_CARD2)
        icon_lbl.configure(bg=_CARD2, fg=_AMBER)
        name_lbl.configure(bg=_CARD2, fg=_AMBER2)
        ind.configure(bg=_AMBER)

    # ── Helpers pages ─────────────────────────────────────────────

    def _sec(self, p, text, color=_AMBER):
        f = tk.Frame(p, bg=_PANEL)
        f.pack(fill='x', padx=0, pady=(0,0))
        row = tk.Frame(f, bg=_CARD)
        row.pack(fill='x', padx=16, pady=(14,6))
        tk.Frame(row, bg=color, width=3).pack(side='left', fill='y', padx=(0,8))
        L(row, text, 10, bold=True, fg=color, bg=_CARD).pack(
            side='left', anchor='w', pady=4)

    def _hint(self, p, text, color=_MUTED):
        L(p, text, 9, fg=color, bg=_PANEL, wrap=350).pack(
            anchor='w', padx=20, pady=(0,6))

    def _field(self, p, label, var, hint=''):
        row = tk.Frame(p, bg=_CARD2)
        row.pack(fill='x', padx=16, pady=3)
        L(row, label, 10, fg=_TEXT2, bg=_CARD2).pack(
            side='left', padx=(10,8), pady=8)
        ENT(row, var, width=18).pack(
            side='left', fill='x', expand=True, padx=(0,8), pady=6)
        if hint:
            L(row, hint, 9, fg=_MUTED, bg=_CARD2).pack(side='left', padx=(0,8))

    def _radio(self, p, title, example, var, val, color=_AMBER):
        CR = _CARD
        CH = _CARD2

        f = tk.Frame(p, bg=CR, cursor='hand2')
        f.pack(fill='x', padx=16, pady=3)

        bar = tk.Frame(f, bg=_BORDER, width=3)
        bar.pack(side='left', fill='y')

        content = tk.Frame(f, bg=CR)
        content.pack(side='left', fill='both', expand=True, padx=(12,10), pady=10)

        l_t = L(content, title, 11, bold=True, fg=_TEXT, bg=CR)
        l_t.pack(anchor='w')
        l_e = LM(content, example, 9, fg=color, bg=CR)
        l_e.pack(anchor='w', pady=(2,0))

        # Sélection via trace
        def _refresh(*_):
            sel = (var.get() == val)
            _bg = CH if sel else CR
            bar.configure(bg=color if sel else _BORDER)
            for w in [f, content, l_t, l_e]:
                try: w.configure(bg=_bg)
                except: pass
            l_t.configure(fg=color if sel else _TEXT)

        var.trace_add('write', _refresh)

        def _click(e=None): var.set(val)
        for w in [f, bar, content, l_t, l_e]:
            w.bind('<Button-1>', _click)

        def _enter(e):
            if var.get() != val:
                for w in [f, content, l_t, l_e]:
                    try: w.configure(bg='#131929')
                    except: pass
        def _leave(e): _refresh()
        for w in [f, content, l_t, l_e]:
            w.bind('<Enter>', _enter)
            w.bind('<Leave>', _leave)

        _refresh()

    def _fmt(self, p, items):
        row = tk.Frame(p, bg=_PANEL)
        row.pack(fill='x', padx=16, pady=6)
        for text, var, color in items:
            f = tk.Frame(row, bg=_CARD)
            f.pack(side='left', padx=3)
            tk.Checkbutton(f, text=text, variable=var,
                font=F(10, True), fg=color, bg=_CARD,
                selectcolor=_CARD, activebackground=_CARD,
                activeforeground=color, relief='flat', cursor='hand2',
                padx=10, pady=7).pack()

    def _run_btn(self, p, mode_id, label):
        f = tk.Frame(p, bg=_PANEL)
        f.pack(fill='x', padx=16, side='bottom', pady=(0,16))
        SEP(f, _BORDER).pack(fill='x', pady=(0,10))
        BTN(f, f'  Analyser — {label}  →',
            lambda: self._run_preview(mode_id),
            bg=_AMBER, fg=_BG, size=11, bold=True, pad=(0, 10)
        ).pack(fill='x')

    # ── Pages ─────────────────────────────────────────────────────

    def _build_all_pages(self):
        for mode_id, _, _ in self.MODES:
            page = tk.Frame(self._page_area, bg=_PANEL)
            self._pages[mode_id] = page
            getattr(self, f'_page_{mode_id}')(page)

    def _page_video(self, p):
        self._sec(p, 'TYPE DE CONTENU')
        self._radio(p, 'Film', 'ex: The Dark Knight (2008).mkv',
            self.video_mode, 'film_plex', _AMBER)
        self._radio(p, 'Série TV', 'ex: Breaking Bad - S03E07.mkv',
            self.video_mode, 'serie_plex', _CYAN)

        self._sec(p, 'CONVENTION MÉDIA', _CYAN)
        self._radio(p, 'Plex · Emby · Jellyfin',
            'Titre (2008).mkv  /  Titre - S01E02.mkv',
            self.video_conv, 'plex', _CYAN)
        self._radio(p, 'Kodi · XBMC',
            'Titre (2008).mkv  /  Titre S01E02.mkv',
            self.video_conv, 'kodi', _TEAL)
        self._radio(p, 'Infuse · Apple TV',
            'Titre (2008).mkv  /  Titre - S01E02.mkv',
            self.video_conv, 'infuse', _GREEN)
        self._radio(p, 'MediaPortal',
            'Titre.mkv  /  Titre_S01E02.mkv',
            self.video_conv, 'mediaportal', _VIOLET)

        self._sec(p, 'OPTIONS')
        f = tk.Frame(p, bg=_PANEL)
        f.pack(fill='x', padx=16, pady=4)
        CHK(f, 'Mode multi-titres (saisir chaque titre manuellement)',
            self.v_multi_titles, fg=_AMBER).pack(anchor='w', pady=4)
        CHK(f, 'Écraser si la destination existe déjà',
            self.v_overwrite, fg=_ORANGE).pack(anchor='w', pady=2)
        self._run_btn(p, 'video', 'Films & Séries')

    def _page_manga(self, p):
        self._sec(p, 'LECTEUR / CONVENTION', _PINK)
        self._radio(p, 'Kobo  (liseuse)',
            'ex: One Piece - T042.cbz', self.manga_mode, 'kobo', _PINK)
        self._radio(p, 'PC · Komga · Kavita',
            'ex: One Piece v042.cbz', self.manga_mode, 'pc', _CYAN)
        self._radio(p, 'Mylar3 · ComicRack',
            'ex: One Piece (1997) #042.cbz', self.manga_mode, 'mylar', _VIOLET)

        self._sec(p, 'NOM DE LA SÉRIE', _PINK)
        self._hint(p, 'Vide → extrait automatiquement du fichier')
        self._field(p, 'Série :', self.manga_series, hint='ex: One Piece')
        self._field(p, 'Année :', self.manga_year,   hint='ex: 1997')

        # Avertissement Mylar : l'année est obligatoire
        warn_frame = tk.Frame(p, bg=_PANEL)
        warn_frame.pack(fill='x', padx=16, pady=(0,4))
        self._mylar_warn = tk.Label(warn_frame,
            text='⚠  Mylar3 : saisissez l\'annee - obligatoire pour le format (Serie (Annee) #001)',
            font=F(9), fg=_ORANGE, bg=_PANEL,
            wraplength=340, justify='left', anchor='w')

        def _check_mylar_warn(*_):
            if self.manga_mode.get() == 'mylar':
                self._mylar_warn.pack(anchor='w', pady=2)
            else:
                self._mylar_warn.pack_forget()
        self.manga_mode.trace_add('write', _check_mylar_warn)
        self.manga_year.trace_add('write', lambda *_: (
            self._mylar_warn.configure(
                fg=_GREEN if self.manga_year.get().strip() else _ORANGE,
                text='\u2713  Annee definie - format complet : Serie (Annee) #001'
                     if self.manga_year.get().strip()
                     else '\u26a0  Mylar3 : saisissez l annee - obligatoire pour le format (Serie (Annee) #001)'
            ) if self.manga_mode.get() == 'mylar' else None
        ))
        _check_mylar_warn()

        self._sec(p, 'FORMATS', _PINK)
        self._fmt(p, [
            ('CBZ', self.manga_cbz, _PINK),
            ('CBR', self.manga_cbr, _PINK),
            ('PDF', self.manga_pdf, _ORANGE),
            ('EPUB', self.manga_epub, _CYAN),
        ])
        self._run_btn(p, 'manga', 'Mangas')

    def _page_book(self, p):
        self._sec(p, 'LOGICIEL / LISEUSE', _TEAL)
        self._radio(p, 'Calibre',
            'Tolkien - Le Seigneur des Anneaux (2001).epub',
            self.book_conv, 'calibre', _AMBER)
        self._radio(p, 'Kobo  (liseuse)',
            'Le Seigneur des Anneaux - Tolkien.epub',
            self.book_conv, 'kobo', _CYAN)
        self._radio(p, 'Kindle',
            'Le Seigneur des Anneaux - Tolkien.epub',
            self.book_conv, 'kindle', _ORANGE)
        self._radio(p, 'Adobe Digital Editions',
            'Tolkien - Le Seigneur des Anneaux.epub',
            self.book_conv, 'adobe', _TEAL)

        self._sec(p, 'INFORMATIONS', _TEAL)
        self._hint(p, 'Laissez vide → auteur extrait du nom de fichier')
        self._field(p, 'Auteur :', self.book_author, hint='optionnel')

        self._sec(p, 'FORMATS', _TEAL)
        self._fmt(p, [
            ('PDF',  self.book_pdf,  _ORANGE),
            ('EPUB', self.book_epub, _CYAN),
            ('MOBI', self.book_mobi, _GREEN),
            ('DJVU', self.book_djvu, _MUTED),
        ])
        self._run_btn(p, 'book', 'Livres & BD')

    def _page_photo(self, p):
        self._sec(p, 'RENOMMAGE PAR DATE')
        self._hint(p, 'Résultat : 20231225_143022_vacances.jpg')
        self._field(p, 'Suffixe :', self.photo_prefix, hint='ex: vacances')
        f = tk.Frame(p, bg=_PANEL)
        f.pack(fill='x', padx=16, pady=6)
        CHK(f, 'Utiliser la date EXIF (prise de vue)', self.photo_exif).pack(
            anchor='w', pady=6)
        pil_c = _GREEN if PIL_OK else _ORANGE
        pil_t = '✓ Pillow installé — EXIF actif' if PIL_OK \
                else '⚠ Pillow absent — pip install pillow'
        L(f, pil_t, 9, fg=pil_c, bg=_PANEL).pack(anchor='w', padx=4)
        self._run_btn(p, 'photo', 'Photos')

    def _page_custom(self, p):
        self._sec(p, 'MODÈLE DE RENOMMAGE', _VIOLET)
        self._hint(p,
            '{titre}  {année}  {ext}  {saison}  {episode}\n'
            '{tome}  {auteur}  {date}  {prefixe}', color=_CYAN)
        self._field(p, 'Modèle :', self.custom_template)

        self._sec(p, 'VALEURS', _VIOLET)
        self._field(p, 'Auteur :',  self.custom_author)
        self._field(p, 'Préfixe :', self.custom_prefix)

        self._sec(p, 'TYPES DE FICHIERS', _VIOLET)
        self._fmt(p, [
            ('Vidéo', self.custom_video, _AMBER),
            ('Livre', self.custom_book,  _CYAN),
            ('Manga', self.custom_manga, _PINK),
            ('Image', self.custom_image, _GREEN),
        ])
        self._run_btn(p, 'custom', 'Personnalisé')

    # ── Panneau droit ─────────────────────────────────────────────

    def _build_right(self, parent):
        # Header preview
        hdr = tk.Frame(parent, bg=_PANEL)
        hdr.pack(fill='x')
        L(hdr, 'PRÉVISUALISATION', 11, bold=True, fg=_AMBER, bg=_PANEL).pack(
            side='left', padx=16, pady=12)
        L(hdr, 'double-clic → aperçu', 9, fg=_MUTED, bg=_PANEL).pack(
            side='left', padx=(0,8))
        self.count_label = L(hdr, '', 10, fg=_CYAN, bg=_PANEL)
        self.count_label.pack(side='right', padx=16)
        tk.Frame(parent, bg=_AMBER, height=1).pack(fill='x')

        # Treeview
        tf = tk.Frame(parent, bg=_SURF)
        tf.pack(fill='both', expand=True)

        cols = ('avant', 'apres', 'statut')
        self.tree = ttk.Treeview(tf, columns=cols,
            show='headings', selectmode='extended')
        self.tree.heading('avant',  text='  Nom original')
        self.tree.heading('apres',  text='  Nouveau nom')
        self.tree.heading('statut', text='Statut')
        self.tree.column('avant',  width=400, minwidth=180)
        self.tree.column('apres',  width=400, minwidth=180)
        self.tree.column('statut', width=130, minwidth=80, anchor='center')

        sb_y = ttk.Scrollbar(tf, orient='vertical',   command=self.tree.yview)
        sb_x = ttk.Scrollbar(tf, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        sb_y.grid(row=0, column=1, sticky='ns')
        sb_x.grid(row=1, column=0, sticky='ew')
        tf.rowconfigure(0, weight=1)
        tf.columnconfigure(0, weight=1)

        self.tree.tag_configure('ok',     foreground=_GREEN)
        self.tree.tag_configure('same',   foreground=_MUTED)
        self.tree.tag_configure('exists', foreground=_ORANGE)
        self.tree.tag_configure('done',   foreground=_CYAN)
        self.tree.tag_configure('error',  foreground=_RED)
        self.tree.bind('<Double-1>', self._show_preview_popup)

        # Barre actions — 2 lignes
        tk.Frame(parent, bg=_BORDER, height=1).pack(fill='x')
        act = tk.Frame(parent, bg=_BG)
        act.pack(fill='x', padx=12, pady=(6,4))

        row1 = tk.Frame(act, bg=_BG)
        row1.pack(fill='x', pady=(0,4))
        self.sel_all_var = tk.BooleanVar(value=True)
        cb = CHK(row1, '  Tout sélectionner', self.sel_all_var, fg=_AMBER)
        cb.configure(command=self._toggle_select)
        cb.pack(side='left', padx=4)
        BTN(row1, '✕  Effacer', self._clear, bg=_PANEL, fg=_TEXT2).pack(
            side='left', padx=8)
        BTN(row1, '↓  Rapport', self._export_log, bg=_PANEL, fg=_TEXT2).pack(
            side='right', padx=4)

        row2 = tk.Frame(act, bg=_BG)
        row2.pack(fill='x')
        self.apply_btn = BTN(row2,
            '✓  Renommer les fichiers sélectionnés',
            self._apply, bg=_GREEN, fg=_BG, size=12, bold=True, pad=(0,10))
        self.apply_btn.pack(fill='x')
        self.apply_btn.configure(state='disabled')

    # ── Logique ───────────────────────────────────────────────────

    def _browse_folder(self):
        d = filedialog.askdirectory(title='Choisir un dossier')
        if d: self.folder_var.set(d)

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

    def _collect(self, exts):
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning('Dossier invalide', 'Sélectionnez un dossier valide.')
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

    def _run_preview(self, mode):
        self._clear()
        self.status_var.set('Analyse en cours…')
        self.update_idletasks()
        pairs = []

        if mode == 'video':
            files = self._collect(VIDEO_EXTS)
            vm, conv = self.video_mode.get(), self.video_conv.get()
            is_film = (vm == 'film_plex')
            if self.v_multi_titles.get() and is_film and files:
                pairs = self._multi_title_dialog(files, conv)
            else:
                for fp in files:
                    fn  = os.path.basename(fp)
                    new = engine.rename_movie(fn, conv) if is_film \
                          else engine.rename_series(fn, conv)
                    pairs.append((fp, new))

        elif mode == 'manga':
            exts = set()
            if self.manga_cbz.get():  exts.add('.cbz')
            if self.manga_cbr.get():  exts.add('.cbr')
            if self.manga_pdf.get():  exts.add('.pdf')
            if self.manga_epub.get(): exts.add('.epub')
            files = self._collect(exts)
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
            files = self._collect(exts)
            au, conv = self.book_author.get(), self.book_conv.get()
            for fp in files:
                pairs.append((fp, engine.rename_book(os.path.basename(fp), au, conv)))

        elif mode == 'photo':
            files = self._collect(IMAGE_EXTS)
            for fp in files:
                pairs.append((fp, engine.rename_photo(fp,
                    self.photo_prefix.get(), self.photo_exif.get())))

        elif mode == 'custom':
            exts = set()
            if self.custom_video.get(): exts |= VIDEO_EXTS
            if self.custom_book.get():  exts |= BOOK_EXTS
            if self.custom_manga.get(): exts |= MANGA_EXTS
            if self.custom_image.get(): exts |= IMAGE_EXTS
            files = self._collect(exts)
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
                is_film = (self.video_mode.get() == 'film_plex')
                if is_film and conv != 'mediaportal':
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
                try: os.chmod(fp, os.stat(fp).st_mode | stat.S_IWRITE)
                except: pass
                shutil.move(fp, dest)
                self.preview_data[file_idx] = (dest, new_name)
                self.tree.item(iid, values=('  '+old_name, '  '+new_name, '✓ renommé'),
                    tags=('done',))
                done += 1
            except OSError as exc:
                code  = getattr(exc, 'winerror', 0)
                label = '✕ accès refusé' if code == 5 else '✕ fichier ouvert' if code == 32 else '✕ erreur'
                self.tree.item(iid, values=('  '+old_name, '  '+new_name, label),
                    tags=('error',))
                errs.append(f'{old_name} : {exc}'); errors += 1

        if self.folder_preview_data:
            old_dir, new_dir = self.folder_preview_data[0]
            if not os.path.exists(new_dir):
                try:
                    shutil.move(old_dir, new_dir)
                    self.folder_var.set(new_dir); done += 1
                except OSError as exc:
                    errs.append(f'[DOSSIER] {exc}'); errors += 1

        self.status_var.set(f'Terminé — {done} renommé(s), {skipped} ignoré(s), {errors} erreur(s)')
        detail = ('\n\nDétails :\n' + '\n'.join(errs[:5])) if errs else ''
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