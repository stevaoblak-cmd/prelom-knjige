# PyInstaller: pyinstaller build/prelom.spec  (na Windows-u)
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = os.path.dirname(SPECPATH)  # koren projekta (spec je u build/)
P = lambda *parts: os.path.join(root, *parts)
datas = [
    (P("templates"), "templates"),
    (P("fonts_ugradjeni"), "fonts_ugradjeni"),
    (P("primeri", "primer_cirilica.docx"), "primeri"),
    (P("build", "gtk"), "gtk"),  # Pango/Cairo DLL-ovi iz MSYS2 + fonts.conf
]
datas += collect_data_files("weasyprint")
datas += collect_data_files("pyphen")

a = Analysis(
    [P("desktop.py")],
    pathex=[root],
    datas=datas,
    hiddenimports=collect_submodules("weasyprint") + ["pymupdf", "docx", "pypdf"],
    excludes=["tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="PrelomKnjige",
    icon=P("build", "ikona.ico"),
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="PrelomKnjige")
