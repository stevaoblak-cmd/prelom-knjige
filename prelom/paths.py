"""Putanje programa: radi i iz izvornog koda i iz zapakovanog Windows programa."""
import os
import sys

FROZEN = getattr(sys, "frozen", False)
# folder sa datotekama programa (templates, ugrađeni fontovi, biblioteke)
APP_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if FROZEN and os.name == "nt":
    DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PrelomKnjige")
else:
    DATA_DIR = APP_DIR

BUNDLED_FONTS_DIR = os.path.join(APP_DIR, "fonts_ugradjeni")
FONTS_DIR = os.path.join(DATA_DIR, "fonts")  # fontovi koje korisnik doda
TEMPLATES_DIR = os.path.join(APP_DIR, "templates")


def setup_native_libs():
    """U zapakovanom programu WeasyPrint-u pokazuje gde su Pango biblioteke i fontconfig."""
    gtk = os.path.join(APP_DIR, "gtk")
    if not os.path.isdir(gtk):
        return
    os.environ.setdefault("WEASYPRINT_DLL_DIRECTORIES", gtk)
    conf = os.path.join(gtk, "fonts.conf")
    if os.path.exists(conf):
        os.environ.setdefault("FONTCONFIG_FILE", conf)
        os.environ.setdefault("FONTCONFIG_PATH", gtk)
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(gtk)
