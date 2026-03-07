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

    def rename_movie_plex(self, fp: str) -> str:
        p = Path(fp)
        title = self.clean_title(p.name)
        year  = self.extract_year(p.stem)
        base  = f"{title} ({year})" if year else title
        return self.safe_filename(base + p.suffix.lower())

    def rename_series_plex(self, fp: str) -> str:
        p = Path(fp)
        s, e  = self.extract_season_episode(p.stem)
        title = self.clean_title(p.name)
        if s is not None and e is not None:
            return self.safe_filename(f"{title} - S{s:02d}E{e:02d}{p.suffix.lower()}")
        elif e is not None:
            return self.safe_filename(f"{title} - E{e:03d}{p.suffix.lower()}")
        return self.safe_filename(title + p.suffix.lower())

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

    def rename_book(self, fp: str, author: str = '') -> str:
        """Auteur - Titre (Année).ext"""
        p     = Path(fp)
        title = self.clean_title(p.name)
        year  = self.extract_year(p.stem)
        yr_s  = f" ({year})" if year else ''
        if author.strip():
            au = self.safe_filename(author.strip().title())
            return self.safe_filename(f"{au} - {title}{yr_s}{p.suffix.lower()}")
        return self.safe_filename(f"{title}{yr_s}{p.suffix.lower()}")

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
#  PALETTE & HELPERS
# ═══════════════════════════════════════════════════════════════════

BG      = '#0f1117'
SURFACE = '#13151e'
CARD    = '#1a1d2b'
CARD2   = '#1e2235'
BORDER  = '#2a2d3e'
ACCENT  = '#f0c060'
BLUE    = '#6ab0f5'
GREEN   = '#4dbb6e'
RED     = '#e05555'
ORANGE  = '#e09040'
PINK    = '#f07090'
TEXT    = '#dce2f0'
MUTED   = '#7a82a0'
SEL     = '#252a40'

FN  = 'Segoe UI'
FNM = 'Consolas'


def lbl(parent, text, size=11, bold=False, fg=None, bg=None, wrap=0):
    kw = dict(text=text, font=(FN, size, 'bold' if bold else 'normal'),
              fg=fg or TEXT, bg=bg or parent.cget('bg'), anchor='w')
    if wrap: kw['wraplength'] = wrap
    return tk.Label(parent, **kw)

def sep(parent, color=BORDER, h=1):
    return tk.Frame(parent, bg=color, height=h)

def chk(parent, text, var, fg=None, size=11):
    bg = parent.cget('bg')
    return tk.Checkbutton(parent, text=text, variable=var,
        font=(FN, size), fg=TEXT, bg=bg,
        selectcolor=CARD2,
        activebackground=bg, activeforeground=fg or ACCENT,
        relief='flat', cursor='hand2')

def btn(parent, text, cmd, bg=CARD, fg=TEXT, size=11, bold=False):
    return tk.Button(parent, text=text, command=cmd,
        font=(FN, size, 'bold' if bold else 'normal'),
        bg=bg, fg=fg,
        activebackground=BORDER, activeforeground=ACCENT,
        relief='flat', cursor='hand2', padx=14, pady=8)

def entry(parent, var, width=28):
    return tk.Entry(parent, textvariable=var,
        font=(FN, 11), bg='#0a0c14', fg=TEXT,
        insertbackground=ACCENT, relief='flat', bd=6, width=width)


# ═══════════════════════════════════════════════════════════════════
#  APPLICATION
# ═══════════════════════════════════════════════════════════════════

class App(tk.Tk):

    MODES = [
        ('video',   '🎬', 'Films & Séries'),
        ('manga',   '🎌', 'Mangas'),
        ('book',    '📚', 'Livres & BD'),
        ('photo',   '🖼️', 'Photos'),
        ('custom',  '⚙️', 'Personnalisé'),
    ]

    def __init__(self):
        super().__init__()
        self.title('FileRenamer')
        self.geometry('1400x860')
        self.minsize(1100, 680)
        self.configure(bg=BG)

        # ── Variables ────────────────────────────────────────────────
        self.folder_var         = tk.StringVar()
        self.recursive_var      = tk.BooleanVar(value=False)
        self.rename_folder_var  = tk.BooleanVar(value=False)
        self.video_mode         = tk.StringVar(value='film_plex')
        self.v_overwrite        = tk.BooleanVar(value=False)
        self.manga_mode         = tk.StringVar(value='kobo')
        self.manga_series       = tk.StringVar()
        self.manga_year         = tk.StringVar()
        self.manga_cbz          = tk.BooleanVar(value=True)
        self.manga_cbr          = tk.BooleanVar(value=True)
        self.manga_pdf          = tk.BooleanVar(value=True)
        self.manga_epub         = tk.BooleanVar(value=True)
        self.book_author        = tk.StringVar()
        self.book_pdf           = tk.BooleanVar(value=True)
        self.book_epub          = tk.BooleanVar(value=True)
        self.book_mobi          = tk.BooleanVar(value=True)
        self.book_djvu          = tk.BooleanVar(value=False)
        self.photo_prefix       = tk.StringVar()
        self.photo_exif         = tk.BooleanVar(value=True)
        self.custom_template    = tk.StringVar(value='{titre} ({année}){ext}')
        self.custom_author      = tk.StringVar()
        self.custom_prefix      = tk.StringVar()
        self.custom_video       = tk.BooleanVar(value=True)
        self.custom_book        = tk.BooleanVar(value=True)
        self.custom_manga       = tk.BooleanVar(value=True)
        self.custom_image       = tk.BooleanVar(value=True)
        self.preview_data       = []
        self.folder_preview_data = []
        self._current_mode      = tk.StringVar(value='video')
        self._pages             = {}
        self._nav_btns          = {}

        self._build_ui()
        self._apply_style()

    # ── TTK style ────────────────────────────────────────────────────

    def _apply_style(self):
        s = ttk.Style(self)
        s.theme_use('clam')
        s.configure('Treeview',
            background=SURFACE, fieldbackground=SURFACE,
            foreground=TEXT, font=(FNM, 10), rowheight=26, borderwidth=0)
        s.configure('Treeview.Heading',
            background=CARD, foreground=ACCENT,
            font=(FN, 10, 'bold'), relief='flat')
        s.map('Treeview',
            background=[('selected', SEL)],
            foreground=[('selected', BLUE)])
        s.configure('TScrollbar',
            background=SURFACE, troughcolor=BG,
            borderwidth=0, arrowsize=12)

    # ── Squelette ────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=SURFACE)
        hdr.pack(fill='x')
        inner = tk.Frame(hdr, bg=SURFACE)
        inner.pack(fill='x', padx=20, pady=14)
        lbl(inner, 'FileRenamer', 20, bold=True, fg=ACCENT, bg=SURFACE).pack(side='left')
        lbl(inner, '  Films · Mangas · Livres · Photos', 12, fg=MUTED, bg=SURFACE).pack(side='left')
        if sys.platform == 'win32':
            try:
                ok = is_admin()
            except Exception:
                ok = False
            if ok:
                lbl(inner, '✓ Administrateur', 10, fg=GREEN, bg=SURFACE).pack(side='right', padx=8)
            else:
                def _rel():
                    if relaunch_as_admin(): self.destroy()
                    else: messagebox.showerror('Erreur', 'Clic droit → Exécuter en tant qu\'administrateur')
                btn(inner, '⚠ Relancer en Admin', _rel, bg=ORANGE, fg='#0d1117', bold=True).pack(side='right', padx=8)
        sep(self).pack(fill='x')

        # Corps principal
        body = tk.Frame(self, bg=BG)
        body.pack(fill='both', expand=True)

        # Colonne gauche : nav + options
        left = tk.Frame(body, bg=SURFACE, width=320)
        left.pack(side='left', fill='y')
        left.pack_propagate(False)
        self._build_left(left)

        sep(body, BORDER, w=1 if False else 1).pack(side='left', fill='y') if False else             tk.Frame(body, bg=BORDER, width=1).pack(side='left', fill='y')

        # Zone centrale : page du mode sélectionné
        self._page_area = tk.Frame(body, bg=CARD, width=380)
        self._page_area.pack(side='left', fill='y')
        self._page_area.pack_propagate(False)

        tk.Frame(body, bg=BORDER, width=1).pack(side='left', fill='y')

        # Panneau droit : preview
        right = tk.Frame(body, bg=BG)
        right.pack(side='left', fill='both', expand=True)
        self._build_right(right)

        # Barre statut
        bar = tk.Frame(self, bg=CARD, height=28)
        bar.pack(fill='x', side='bottom')
        sep(bar).pack(fill='x', side='top')
        self.status_var = tk.StringVar(value='Prêt — Choisissez un dossier')
        tk.Label(bar, textvariable=self.status_var,
            bg=CARD, fg=MUTED, font=(FN, 9), anchor='w').pack(
            side='left', padx=14, fill='y')

        # Construire toutes les pages et afficher la première
        self._build_all_pages()
        self._show_page('video')

    # ── Panneau gauche : dossier + navigation ────────────────────────

    def _build_left(self, parent):
        # Dossier
        z = tk.Frame(parent, bg=SURFACE)
        z.pack(fill='x', padx=16, pady=(16, 8))

        lbl(z, '📁  Dossier à traiter', 11, bold=True, fg=ACCENT, bg=SURFACE).pack(anchor='w', pady=(0,6))

        row = tk.Frame(z, bg='#0a0c14')
        row.pack(fill='x')
        entry(row, self.folder_var).pack(side='left', fill='x', expand=True, padx=(6,2), pady=5)
        btn(row, '…', self._browse_folder, bg=BORDER).pack(side='left', padx=(0,4), pady=5)

        sep(parent).pack(fill='x', padx=16, pady=6)

        opts = tk.Frame(parent, bg=SURFACE)
        opts.pack(fill='x', padx=16, pady=(0,4))
        chk(opts, 'Inclure les sous-dossiers', self.recursive_var).pack(anchor='w', pady=3)
        chk(opts, 'Renommer aussi le dossier', self.rename_folder_var, fg=BLUE).pack(anchor='w', pady=3)

        sep(parent).pack(fill='x', padx=16, pady=(6,2))

        # Navigation modes
        lbl(parent, '  MODE', 9, fg=MUTED, bg=SURFACE).pack(anchor='w', padx=16, pady=(8,4))

        nav = tk.Frame(parent, bg=SURFACE)
        nav.pack(fill='x', padx=8)

        for mode_id, icon, label in self.MODES:
            f = tk.Frame(nav, bg=SURFACE, cursor='hand2')
            f.pack(fill='x', pady=2)

            indicator = tk.Frame(f, bg=SURFACE, width=4)
            indicator.pack(side='left', fill='y')

            b = tk.Button(f, text=f'  {icon}  {label}',
                font=(FN, 12), fg=MUTED, bg=SURFACE,
                activebackground=CARD2, activeforeground=TEXT,
                relief='flat', cursor='hand2', anchor='w',
                padx=8, pady=10,
                command=lambda m=mode_id: self._show_page(m))
            b.pack(side='left', fill='x', expand=True)

            self._nav_btns[mode_id] = (f, b, indicator)

    # ── Pages des modes ──────────────────────────────────────────────

    def _build_all_pages(self):
        for mode_id, _, _ in self.MODES:
            page = tk.Frame(self._page_area, bg=CARD)
            self._pages[mode_id] = page
            builder = getattr(self, f'_page_{mode_id}')
            builder(page)

    def _show_page(self, mode_id):
        # Cacher toutes les pages
        for pid, page in self._pages.items():
            page.place_forget()
            f, b, ind = self._nav_btns[pid]
            b.configure(fg=MUTED, bg=SURFACE, font=(FN, 12))
            ind.configure(bg=SURFACE)

        # Afficher la page sélectionnée
        self._pages[mode_id].place(x=0, y=0, relwidth=1, relheight=1)
        f, b, ind = self._nav_btns[mode_id]
        b.configure(fg=TEXT, bg=CARD2, font=(FN, 12, 'bold'))
        ind.configure(bg=ACCENT)
        self._current_mode.set(mode_id)

    # ── Helpers UI des pages ─────────────────────────────────────────

    def _section_title(self, parent, text, color=ACCENT):
        f = tk.Frame(parent, bg=CARD)
        f.pack(fill='x', padx=20, pady=(18, 4))
        lbl(f, text, 11, bold=True, fg=color, bg=CARD).pack(anchor='w')
        tk.Frame(f, bg=color, height=2).pack(fill='x', pady=(4,0))

    def _hint_lbl(self, parent, text, color=MUTED):
        lbl(parent, text, 10, fg=color, bg=CARD, wrap=340).pack(
            anchor='w', padx=22, pady=(2, 6))

    def _field_row(self, parent, label, var, hint=''):
        row = tk.Frame(parent, bg=CARD2)
        row.pack(fill='x', padx=20, pady=4)
        lbl(row, label, 11, fg=MUTED, bg=CARD2).pack(
            side='left', padx=(10,6), pady=8)
        entry(row, var, width=20).pack(
            side='left', fill='x', expand=True, padx=(0,8), pady=6)
        if hint:
            lbl(row, hint, 9, fg=MUTED, bg=CARD2).pack(side='left', padx=(0,8))

    def _radio_card(self, parent, title, example, var, val, color=ACCENT):
        """Carte radio cliquable — sélection fiable via trace variable."""
        CR = '#171a27'
        CH = '#202438'

        f = tk.Frame(parent, bg=CR, cursor='hand2')
        f.pack(fill='x', padx=20, pady=4)

        # Indicateur couleur gauche
        bar = tk.Frame(f, bg=BORDER, width=4)
        bar.pack(side='left', fill='y')

        content = tk.Frame(f, bg=CR)
        content.pack(side='left', fill='both', expand=True, padx=12, pady=10)

        l_title = lbl(content, title, 12, bold=True, fg=TEXT, bg=CR)
        l_title.pack(anchor='w')
        l_ex = lbl(content, example, 10, fg=color, bg=CR)
        l_ex.pack(anchor='w', pady=(2,0))

        # Mise à jour visuelle quand la variable change
        def _refresh(*_):
            selected = (var.get() == val)
            _bg = CH if selected else CR
            bar.configure(bg=color if selected else BORDER)
            for w in [f, content, l_title, l_ex]:
                try: w.configure(bg=_bg)
                except: pass
        var.trace_add('write', _refresh)

        # Clic → set variable
        def _click(e=None):
            var.set(val)
        for w in [f, bar, content, l_title, l_ex]:
            w.bind('<Button-1>', _click)

        # Hover
        def _enter(e):
            if var.get() != val:
                for w in [f, content, l_title, l_ex]:
                    try: w.configure(bg='#1c2035')
                    except: pass
        def _leave(e):
            _refresh()
        for w in [f, content, l_title, l_ex]:
            w.bind('<Enter>', _enter)
            w.bind('<Leave>', _leave)

        _refresh()  # état initial

    def _fmt_checks(self, parent, items):
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill='x', padx=20, pady=6)
        for text, var, color in items:
            f = tk.Frame(row, bg=CARD2)
            f.pack(side='left', padx=4)
            tk.Checkbutton(f, text=text, variable=var,
                font=(FN, 11, 'bold'), fg=color, bg=CARD2,
                selectcolor=CARD2, activebackground=CARD2,
                activeforeground=color,
                relief='flat', cursor='hand2',
                padx=10, pady=8).pack()

    def _run_btn(self, parent, mode_id, label):
        f = tk.Frame(parent, bg=CARD)
        f.pack(fill='x', padx=20, pady=(20, 20), side='bottom')
        sep(f).pack(fill='x', pady=(0,12))
        btn(f, f'🔍  Analyser — {label}',
            lambda: self._run_preview(mode_id),
            bg=ACCENT, fg='#0a0d12', size=12, bold=True
        ).pack(fill='x', ipady=6)

    # ── Page Films & Séries ──────────────────────────────────────────

    def _page_video(self, p):
        self._section_title(p, 'Type de contenu')
        self._radio_card(p, 'Film',
            'ex: The Dark Knight (2008).mkv',
            self.video_mode, 'film_plex', ACCENT)
        self._radio_card(p, 'Série TV',
            'ex: Breaking Bad - S03E07.mkv',
            self.video_mode, 'serie_plex', BLUE)

        self._section_title(p, 'Options')
        f = tk.Frame(p, bg=CARD)
        f.pack(fill='x', padx=20, pady=4)
        chk(f, 'Écraser si la destination existe déjà',
            self.v_overwrite).pack(anchor='w', pady=6)

        self._run_btn(p, 'video', 'Films & Séries')

    # ── Page Mangas ──────────────────────────────────────────────────

    def _page_manga(self, p):
        self._section_title(p, 'Lecteur / Convention', PINK)
        self._radio_card(p, 'Kobo  (liseuse)',
            'ex: One Piece - T042.cbz',
            self.manga_mode, 'kobo', PINK)
        self._radio_card(p, 'PC · Komga · Kavita',
            'ex: One Piece v042.cbz',
            self.manga_mode, 'pc', BLUE)
        self._radio_card(p, 'Mylar3 · ComicRack',
            'ex: One Piece (1997) #042.cbz',
            self.manga_mode, 'mylar', ORANGE)

        self._section_title(p, 'Nom de la série', PINK)
        self._hint_lbl(p, 'Laissez vide → titre extrait du nom de fichier')
        self._field_row(p, 'Série :', self.manga_series, hint='ex: One Piece')
        self._field_row(p, 'Année :', self.manga_year,   hint='ex: 1997')

        self._section_title(p, 'Formats à traiter', PINK)
        self._fmt_checks(p, [
            ('CBZ', self.manga_cbz, PINK),
            ('CBR', self.manga_cbr, PINK),
            ('PDF', self.manga_pdf, ORANGE),
            ('EPUB', self.manga_epub, BLUE),
        ])

        self._run_btn(p, 'manga', 'Mangas')

    # ── Page Livres & BD ─────────────────────────────────────────────

    def _page_book(self, p):
        self._section_title(p, 'Informations')
        self._hint_lbl(p, 'Résultat : Tolkien - Le Seigneur des Anneaux (2001).epub')
        self._field_row(p, 'Auteur :', self.book_author, hint='optionnel')

        self._section_title(p, 'Formats à traiter')
        self._fmt_checks(p, [
            ('PDF',  self.book_pdf,  ORANGE),
            ('EPUB', self.book_epub, BLUE),
            ('MOBI', self.book_mobi, GREEN),
            ('DJVU', self.book_djvu, MUTED),
        ])

        self._run_btn(p, 'book', 'Livres & BD')

    # ── Page Photos ──────────────────────────────────────────────────

    def _page_photo(self, p):
        self._section_title(p, 'Renommage par date')
        self._hint_lbl(p, 'Résultat : 20231225_143022_vacances.jpg')
        self._field_row(p, 'Suffixe :', self.photo_prefix, hint='ex: vacances')

        f = tk.Frame(p, bg=CARD)
        f.pack(fill='x', padx=20, pady=4)
        chk(f, 'Utiliser la date EXIF (prise de vue)',
            self.photo_exif).pack(anchor='w', pady=6)
        pil_ok_c = GREEN if PIL_OK else ORANGE
        pil_ok_t = '✓ Pillow installé — EXIF actif' if PIL_OK                    else '⚠ Pillow absent — pip install pillow'
        lbl(f, pil_ok_t, 10, fg=pil_ok_c, bg=CARD).pack(anchor='w', padx=4)

        self._run_btn(p, 'photo', 'Photos')

    # ── Page Personnalisé ────────────────────────────────────────────

    def _page_custom(self, p):
        self._section_title(p, 'Modèle de renommage')
        self._hint_lbl(p,
            '{titre}  {année}  {ext}  {saison}  {episode}\n'            '{tome}  {auteur}  {date}  {prefixe}', color=BLUE)
        self._field_row(p, 'Modèle :', self.custom_template)

        self._section_title(p, 'Valeurs par défaut')
        self._field_row(p, 'Auteur :',  self.custom_author)
        self._field_row(p, 'Préfixe :', self.custom_prefix)

        self._section_title(p, 'Types de fichiers')
        self._fmt_checks(p, [
            ('Vidéo', self.custom_video, ACCENT),
            ('Livre', self.custom_book,  BLUE),
            ('Manga', self.custom_manga, PINK),
            ('Image', self.custom_image, GREEN),
        ])

        self._run_btn(p, 'custom', 'Personnalisé')

    # ── Panneau droit (preview) ──────────────────────────────────────

    def _build_right(self, parent):
        hdr = tk.Frame(parent, bg=CARD)
        hdr.pack(fill='x')
        lbl(hdr, 'Prévisualisation', 13, bold=True, fg=ACCENT, bg=CARD).pack(
            side='left', padx=16, pady=12)
        lbl(hdr, 'double-clic → aperçu image/CBZ', 9, fg=MUTED, bg=CARD).pack(
            side='left')
        self.count_label = lbl(hdr, '', 10, fg=MUTED, bg=CARD)
        self.count_label.pack(side='right', padx=16)
        tk.Frame(parent, bg=BORDER, height=1).pack(fill='x')

        # Treeview
        tf = tk.Frame(parent, bg=SURFACE)
        tf.pack(fill='both', expand=True)

        s = ttk.Style()
        s.configure('Treeview', rowheight=26)

        cols = ('avant', 'apres', 'statut')
        self.tree = ttk.Treeview(tf, columns=cols,
            show='headings', selectmode='extended')
        self.tree.heading('avant',  text='  Nom original')
        self.tree.heading('apres',  text='  Nouveau nom')
        self.tree.heading('statut', text='Statut')
        self.tree.column('avant',  width=380, minwidth=180)
        self.tree.column('apres',  width=380, minwidth=180)
        self.tree.column('statut', width=120, minwidth=80, anchor='center')

        sb_y = ttk.Scrollbar(tf, orient='vertical',   command=self.tree.yview)
        sb_x = ttk.Scrollbar(tf, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        sb_y.grid(row=0, column=1, sticky='ns')
        sb_x.grid(row=1, column=0, sticky='ew')
        tf.rowconfigure(0, weight=1)
        tf.columnconfigure(0, weight=1)

        self.tree.tag_configure('ok',     foreground=GREEN)
        self.tree.tag_configure('same',   foreground=MUTED)
        self.tree.tag_configure('exists', foreground=ORANGE)
        self.tree.tag_configure('done',   foreground=BLUE)
        self.tree.tag_configure('error',  foreground=RED)
        self.tree.bind('<Double-1>', self._show_preview_popup)

        # Barre d'actions
        act = tk.Frame(parent, bg=BG)
        act.pack(fill='x', padx=10, pady=8)

        self.sel_all_var = tk.BooleanVar(value=True)
        cb = chk(act, '  Tout sélectionner', self.sel_all_var, fg=ACCENT)
        cb.configure(command=self._toggle_select)
        cb.pack(side='left', padx=4)

        btn(act, '🗑  Effacer', self._clear, bg=CARD).pack(side='left', padx=6)

        self.apply_btn = btn(act,
            '✅  Renommer les fichiers sélectionnés',
            self._apply, bg=GREEN, fg='#0a0d12', bold=True)
        self.apply_btn.pack(side='right', padx=4)
        self.apply_btn.configure(state='disabled')

        btn(act, '📋  Rapport', self._export_log, bg=CARD).pack(side='right', padx=6)

    # ── Logique ──────────────────────────────────────────────────────

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
                for f in fnames:
                    if Path(f).suffix.lower() in exts:
                        files.append(os.path.join(root, f))
        else:
            for f in os.listdir(folder):
                fp = os.path.join(folder, f)
                if os.path.isfile(fp) and Path(f).suffix.lower() in exts:
                    files.append(fp)
        return sorted(files)

    def _run_preview(self, mode):
        self._clear()
        self.status_var.set('Analyse en cours…')
        self.update_idletasks()
        pairs = []

        if mode == 'video':
            files = self._collect(VIDEO_EXTS)
            vm = self.video_mode.get()
            for fp in files:
                fn  = os.path.basename(fp)
                new = engine.rename_movie_plex(fn) if vm == 'film_plex'                       else engine.rename_series_plex(fn)
                pairs.append((fp, new))

        elif mode == 'manga':
            exts = set()
            if self.manga_cbz.get():  exts.add('.cbz')
            if self.manga_cbr.get():  exts.add('.cbr')
            if self.manga_pdf.get():  exts.add('.pdf')
            if self.manga_epub.get(): exts.add('.epub')
            files = self._collect(exts)
            mm, s, y = self.manga_mode.get(), self.manga_series.get(), self.manga_year.get()
            for fp in files:
                fn = os.path.basename(fp)
                if   mm == 'kobo':  new = engine.rename_manga_kobo(fn, s)
                elif mm == 'pc':    new = engine.rename_manga_pc(fn, s)
                else:               new = engine.rename_manga_mylar(fn, s, y)
                pairs.append((fp, new))

        elif mode == 'book':
            exts = set()
            if self.book_pdf.get():  exts.add('.pdf')
            if self.book_epub.get(): exts.add('.epub')
            if self.book_mobi.get(): exts.add('.mobi')
            if self.book_djvu.get(): exts.add('.djvu')
            files = self._collect(exts)
            au = self.book_author.get()
            for fp in files:
                pairs.append((fp, engine.rename_book(os.path.basename(fp), au)))

        elif mode == 'photo':
            files = self._collect(IMAGE_EXTS)
            pref, use_exif = self.photo_prefix.get(), self.photo_exif.get()
            for fp in files:
                pairs.append((fp, engine.rename_photo(fp, pref, use_exif)))

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
            same     = (old_name == new_name)
            dest     = os.path.join(os.path.dirname(fp), new_name)
            exists   = os.path.exists(dest) and not same
            if same:     tag, st = 'same', '═  inchangé'
            elif exists: tag, st = 'exists', '⚠  existe déjà'
            else:        tag, st = 'ok', '✓  prêt'; count_ok += 1
            self.tree.insert('', 'end',
                values=('  '+old_name, '  '+new_name, st), tags=(tag,))

        # Dossier optionnel
        self.folder_preview_data = []
        if self.rename_folder_var.get() and pairs:
            folder_path = self.folder_var.get().strip()
            folder_name = os.path.basename(folder_path)
            new_folder  = engine.safe_filename(engine.clean_title(os.path.basename(pairs[0][0])))
            if new_folder and new_folder != folder_name:
                dest_folder = os.path.join(os.path.dirname(folder_path), new_folder)
                if os.path.exists(dest_folder):
                    tag_f, st_f = 'exists', '⚠  dossier existe'
                else:
                    tag_f, st_f = 'ok', '📁  dossier'; count_ok += 1
                self.folder_preview_data = [(folder_path, dest_folder)]
                self.tree.insert('', 0,
                    values=(f'  📁 {folder_name}', f'  📁 {new_folder}', st_f),
                    tags=(tag_f,))

        n = len(pairs)
        self.count_label.config(text=f'{n} fichier(s)  •  {count_ok} à renommer')
        self.tree.selection_set(self.tree.get_children())
        self.apply_btn.configure(state='normal' if count_ok > 0 else 'disabled')
        self.status_var.set(f'{n} fichier(s) analysé(s) — {count_ok} à renommer')

    def _apply(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo('Rien à faire', 'Aucune ligne sélectionnée.'); return
        if not messagebox.askyesno('Confirmer',
                f'Renommer {len(selected)} élément(s) ?\nCette action est irréversible.',
                icon='warning'): return

        done, skipped, errors, errs = 0, 0, 0, []
        all_items  = self.tree.get_children()
        iid_to_idx = {iid: i for i, iid in enumerate(all_items)}
        has_folder = bool(self.folder_preview_data)

        for iid in selected:
            idx = iid_to_idx.get(iid)
            if idx is None: continue
            if has_folder and idx == 0: continue  # dossier → après
            file_idx = idx - (1 if has_folder else 0)
            if file_idx < 0 or file_idx >= len(self.preview_data): continue

            fp, new_name = self.preview_data[file_idx]
            fp       = os.path.abspath(fp)
            old_name = os.path.basename(fp)
            dest     = os.path.join(os.path.dirname(fp), new_name)

            if old_name == new_name: skipped += 1; continue
            if os.path.exists(dest):
                self.tree.item(iid, values=('  '+old_name, '  '+new_name, '⚠  ignoré'), tags=('exists',))
                skipped += 1; continue
            try:
                try: os.chmod(fp, os.stat(fp).st_mode | stat.S_IWRITE)
                except: pass
                shutil.move(fp, dest)
                self.preview_data[file_idx] = (dest, new_name)
                self.tree.item(iid, values=('  '+old_name, '  '+new_name, '✅  renommé'), tags=('done',))
                done += 1
            except OSError as exc:
                code  = getattr(exc, 'winerror', 0)
                label = '❌ accès refusé' if code == 5 else '❌ fichier ouvert' if code == 32 else '❌ erreur'
                self.tree.item(iid, values=('  '+old_name, '  '+new_name, label), tags=('error',))
                errs.append(f'{old_name} : {exc}'); errors += 1

        if self.folder_preview_data:
            old_dir, new_dir = self.folder_preview_data[0]
            if not os.path.exists(new_dir):
                try:
                    shutil.move(old_dir, new_dir)
                    self.folder_var.set(new_dir)
                    done += 1
                except OSError as exc:
                    errs.append(f'[DOSSIER] {exc}'); errors += 1

        self.status_var.set(f'Terminé — {done} renommé(s), {skipped} ignoré(s), {errors} erreur(s)')
        detail = ('\n\nDétails :\n' + '\n'.join(errs[:5]) +
                  (f'\n... +{len(errs)-5}' if len(errs)>5 else '')) if errs else ''
        messagebox.showinfo('Terminé', f'{done} renommé(s)\n{skipped} ignoré(s)\n{errors} erreur(s){detail}')

        if errors and sys.platform == 'win32':
            try:
                if not is_admin() and any('5' in d for d in errs):
                    if messagebox.askyesno('Droits insuffisants', 'Relancer en Administrateur ?'):
                        if relaunch_as_admin(): self.destroy()
            except: pass

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
            popup.configure(bg=BG)
            popup.resizable(False, False)
            lbl(popup, Path(fp).name, 10, bold=True, fg=ACCENT, bg=BG).pack(padx=14, pady=(12,4))
            il = tk.Label(popup, image=photo, bg=BG)
            il.image = photo
            il.pack(padx=14, pady=(0,4))
            btn(popup, 'Fermer', popup.destroy, bg=CARD).pack(pady=(0,12))
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
            data = [{'original': os.path.basename(fp), 'nouveau': n,
                     'dossier': os.path.dirname(fp)} for fp, n in self.preview_data]
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
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