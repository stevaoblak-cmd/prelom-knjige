"""Prelom: pretvara prelom zapis + podešavanja u PDF spreman za štampu."""
import html
import io
import os
import pathlib
import re
import subprocess
from dataclasses import dataclass, asdict, fields

from .paths import BUNDLED_FONTS_DIR, FONTS_DIR, setup_native_libs

PAGE_SIZES = {
    "A4 (210 × 297 mm)": (210, 297),
    "A5 (148 × 210 mm)": (148, 210),
    "B5 (176 × 250 mm)": (176, 250),
    "B6 (125 × 176 mm)": (125, 176),
    "13 × 20 cm": (130, 200),
    "14 × 20 cm": (140, 200),
    "14,5 × 20,5 cm": (145, 205),
    "16,5 × 23,5 cm": (165, 235),
    "17 × 24 cm": (170, 240),
    "20 × 20 cm": (200, 200),
}


@dataclass
class Settings:
    # strana
    page_size: str = "14,5 × 20,5 cm"
    page_width: float = 145.0  # mm, koristi se kad je page_size == "Prilagođeno"
    page_height: float = 205.0
    margin_top: float = 18.0
    margin_bottom: float = 20.0
    margin_inner: float = 20.0  # unutrašnja (kod rikne)
    margin_outer: float = 15.0
    # tekst
    font_family: str = "Liberation Serif"
    heading_font_family: str = ""  # prazno = isti kao tekst
    font_size: float = 11.0  # pt
    line_height: float = 1.35  # prored, umnožak veličine slova
    paragraph_indent: float = 5.0  # mm, uvlaka prvog reda
    paragraph_spacing: float = 0.0  # mm razmaka između pasusa
    justify: bool = True
    hyphenate: bool = True
    language: str = "auto"  # auto, sr (ćirilica), sr-Latn, en, ...
    widows_orphans: int = 2
    # poglavlja
    chapter_start: str = "odd"  # odd = neparna (desna), any = nova strana, none = nastavlja
    chapter_drop: float = 30.0  # mm spuštanja naslova poglavlja
    chapter_heading_size: float = 18.0  # pt
    chapter_number_pages: bool = False  # broj strane na početnoj strani poglavlja
    # zaglavlje i paginacija
    page_numbers: str = "outer"  # outer, center, none
    running_header: bool = True  # levo naslov knjige, desno naslov poglavlja
    first_page_number: int = 1
    # naslovna strana i sadržaj
    title: str = ""
    author: str = ""
    title_page: bool = True
    toc: str = "none"  # none, start, end
    # štampa
    pages_multiple: int = 1  # dopuni praznim stranama do umnoška (npr. 16 za tabake)
    crop_marks: bool = False
    bleed: float = 0.0  # mm

    @classmethod
    def from_dict(cls, data):
        s = cls()
        for f in fields(cls):
            if f.name not in data:
                continue
            val = data[f.name]
            try:
                if f.type in (bool, "bool"):
                    val = val in (True, "1", "on", "true", "yes")
                elif f.type in (int, "int"):
                    val = int(float(val))
                elif f.type in (float, "float"):
                    val = float(str(val).replace(",", "."))
            except ValueError:
                continue
            setattr(s, f.name, val)
        return s

    def to_dict(self):
        return asdict(self)

    def page_mm(self):
        if self.page_size in PAGE_SIZES:
            return PAGE_SIZES[self.page_size]
        return (self.page_width, self.page_height)


# --------------------------------------------------------------- fontovi

_family_cache = {}


def _fonts_in(folder):
    """{ime familije: [putanje]} za .ttf/.otf fontove u folderu."""
    result = {}
    if not os.path.isdir(folder):
        return result
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith((".ttf", ".otf")):
            continue
        path = os.path.join(folder, name)
        if path not in _family_cache:
            _family_cache[path] = _font_family_name(path) or os.path.splitext(name)[0]
        result.setdefault(_family_cache[path], []).append(path)
    return result


def user_fonts():
    """Ugrađeni fontovi programa + fontovi koje je korisnik dodao."""
    result = _fonts_in(BUNDLED_FONTS_DIR)
    for fam, paths in _fonts_in(FONTS_DIR).items():
        result.setdefault(fam, []).extend(paths)
    return result


def _font_family_name(path):
    try:
        from fontTools.ttLib import TTFont

        font = TTFont(path, lazy=True)
        name = font["name"]
        return (name.getDebugName(16) or name.getDebugName(1) or "").strip() or None
    except Exception:
        return None


def _font_style(path):
    try:
        from fontTools.ttLib import TTFont

        font = TTFont(path, lazy=True)
        weight = font["OS/2"].usWeightClass
        italic = bool(font["OS/2"].fsSelection & 1)
        return weight, italic
    except Exception:
        low = path.lower()
        return (700 if "bold" in low else 400), ("italic" in low or "oblique" in low)


def system_fonts():
    if os.name == "nt":
        fams = set()
        for folder in (os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
                       os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")):
            fams.update(_fonts_in(folder))
        return sorted(f for f in fams if "emoji" not in f.lower())
    try:
        out = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True,
                             timeout=10).stdout
    except Exception:
        return []
    fams = set()
    for line in out.splitlines():
        name = line.split(",")[0].strip()
        if name and "emoji" not in name.lower():
            fams.add(name)
    return sorted(fams)


def available_fonts():
    return sorted(set(system_fonts()) | set(user_fonts()))


def _font_face_css():
    css = []
    for family, paths in user_fonts().items():
        for path in paths:
            weight, italic = _font_style(path)
            url = pathlib.Path(path).resolve().as_uri()
            css.append(
                f'@font-face {{ font-family: "{family}"; src: url("{url}"); '
                f'font-weight: {weight}; font-style: {"italic" if italic else "normal"}; }}'
            )
    return "\n".join(css)


# ----------------------------------------------------- prelom zapis -> HTML

def inline_to_html(text):
    """**podebljano**, *kurziv*, \\* doslovna zvezdica."""
    text = text.replace("\\\\", "\x00B").replace("\\*", "\x00S")
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    return text.replace("\x00S", "*").replace("\x00B", "\\")


def parse_markup(text):
    """Vraća listu blokova: (vrsta, sadržaj)."""
    blocks = []
    para = []

    def flush():
        if para:
            joined = " ".join(l.strip() for l in para)
            if joined.startswith(">"):
                blocks.append(("quote", joined.lstrip("> ").strip()))
            else:
                blocks.append(("p", joined))
            para.clear()

    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        low = stripped.lower()
        if m:
            flush()
            blocks.append((f"h{len(m.group(1))}", m.group(2).strip()))
        elif re.fullmatch(r"(\*\s*){3,}|(-\s*){3,}|~{3,}", stripped):
            flush()
            blocks.append(("scene", ""))
        elif low in ("[nova strana]", "[новa страна]", "[нова страна]"):
            flush()
            blocks.append(("pagebreak", ""))
        elif low in ("[prazna strana]", "[празна страна]"):
            flush()
            blocks.append(("blank", ""))
        elif low in ("[neparna strana]", "[непарна страна]"):
            flush()
            blocks.append(("oddbreak", ""))
        else:
            para.append(line)
    flush()
    return blocks


def detect_language(text):
    cyr = len(re.findall(r"[\u0400-\u04FF]", text))
    lat = len(re.findall(r"[A-Za-zčćžšđČĆŽŠĐ]", text))
    if cyr > lat:
        return "sr"
    if re.search(r"[čćžšđČĆŽŠĐ]", text) or lat == 0:
        return "sr-Latn"
    return "sr-Latn"


def plain(text):
    return re.sub(r"\\?\*+", "", text)


def build_html(markup, s: Settings):
    blocks = parse_markup(markup)
    lang = s.language if s.language != "auto" else detect_language(markup)
    body = []
    chapter_idx = 0
    in_chapter = False
    after_heading = True
    toc_entries = []

    def close_chapter():
        nonlocal in_chapter
        if in_chapter:
            body.append("</section>")
            in_chapter = False

    for kind, content in blocks:
        if kind == "h1":
            close_chapter()
            chapter_idx += 1
            cid = f"pog-{chapter_idx}"
            toc_entries.append((cid, content))
            body.append(f'<section class="chapter" id="{cid}">')
            body.append(f'<h1 data-title="{html.escape(plain(content))}">{inline_to_html(content)}</h1>')
            in_chapter = True
            after_heading = True
        elif kind in ("h2", "h3"):
            body.append(f"<{kind}>{inline_to_html(content)}</{kind}>")
            after_heading = True
        elif kind == "scene":
            body.append('<p class="scene">*&#8194;*&#8194;*</p>')
            after_heading = True
        elif kind == "pagebreak":
            body.append('<div class="pagebreak"></div>')
            after_heading = True
        elif kind == "oddbreak":
            body.append('<div class="oddbreak"></div>')
            after_heading = True
        elif kind == "blank":
            body.append('<div class="blankpage"></div>')
            after_heading = True
        elif kind == "quote":
            body.append(f'<blockquote>{inline_to_html(content)}</blockquote>')
            after_heading = True
        else:
            cls = ' class="first"' if after_heading else ""
            body.append(f"<p{cls}>{inline_to_html(content)}</p>")
            after_heading = False
    close_chapter()

    front = []
    if s.title_page and (s.title or s.author):
        front.append('<section class="titlepage">')
        if s.author:
            front.append(f'<div class="tp-author">{html.escape(s.author)}</div>')
        if s.title:
            front.append(f'<div class="tp-title">{html.escape(s.title)}</div>')
        front.append("</section>")

    toc = ""
    if s.toc != "none" and toc_entries:
        items = "".join(
            f'<li><a href="#{cid}">{inline_to_html(t)}</a></li>' for cid, t in toc_entries
        )
        toc_title = "Садржај" if lang == "sr" else "Sadržaj"
        toc = f'<section class="toc"><h1 class="toc-title">{toc_title}</h1><ul>{items}</ul></section>'

    parts = front[:]
    if s.toc == "start":
        parts.append(toc)
    parts.extend(body)
    if s.toc == "end":
        parts.append(toc)

    return (
        f'<!DOCTYPE html><html lang="{lang}"><head><meta charset="utf-8">'
        f"<title>{html.escape(s.title or 'Knjiga')}</title></head><body>"
        + "\n".join(parts)
        + "</body></html>"
    )


def build_css(s: Settings):
    w, h = s.page_mm()
    font = f'"{s.font_family}", "DejaVu Serif", serif'
    hfont = f'"{s.heading_font_family}", {font}' if s.heading_font_family else font
    lh = s.line_height
    num = s.page_numbers
    meta_size = max(s.font_size * 0.8, 7)

    def margin_box(side):
        """CSS za zaglavlje/podnožje leve ili desne strane."""
        outer = "left" if side == "left" else "right"
        rules = []
        if s.running_header:
            src = "string(booktitle)" if side == "left" else "string(chaptertitle)"
            rules.append(
                f"@top-center {{ content: {src}; font-family: {font}; font-size: {meta_size}pt;"
                f" font-style: italic; vertical-align: bottom; padding-bottom: 4mm; }}"
            )
        if num == "outer":
            rules.append(
                f"@bottom-{outer} {{ content: counter(page); font-family: {font};"
                f" font-size: {meta_size}pt; vertical-align: top; padding-top: 4mm; }}"
            )
        elif num == "center":
            rules.append(
                f"@bottom-center {{ content: counter(page); font-family: {font};"
                f" font-size: {meta_size}pt; vertical-align: top; padding-top: 4mm; }}"
            )
        return "\n".join(rules)

    empty_boxes = " ".join(
        f"@{b} {{ content: none; }}"
        for b in ("top-center", "top-left", "top-right", "bottom-center",
                  "bottom-left", "bottom-right")
    )
    no_header = "@top-center { content: none; }"

    if s.chapter_start == "odd":
        chapter_break = "right"
    elif s.chapter_start == "any":
        chapter_break = "page"
    else:
        chapter_break = "auto"

    print_marks = ""
    if s.crop_marks:
        print_marks += "marks: crop;"
    if s.bleed:
        print_marks += f"bleed: {s.bleed}mm;"

    book_title = s.title.replace('"', '\\"')
    first_counter = s.first_page_number

    return f"""
{_font_face_css()}
@page {{
  size: {w}mm {h}mm;
  margin-top: {s.margin_top}mm; margin-bottom: {s.margin_bottom}mm;
  {print_marks}
}}
@page :left {{ margin-left: {s.margin_outer}mm; margin-right: {s.margin_inner}mm; {margin_box('left')} }}
@page :right {{ margin-left: {s.margin_inner}mm; margin-right: {s.margin_outer}mm; {margin_box('right')} }}
@page :blank {{ {empty_boxes} }}
@page front {{ {empty_boxes} }}
@page :nth(1 of chapter) {{ {no_header} {'' if s.chapter_number_pages else empty_boxes} }}
@page blankp {{ {empty_boxes} }}

body {{ string-set: booktitle "{book_title}"; }}
@page :first {{ counter-reset: page {first_counter}; }}
body {{
  font-family: {font}; font-size: {s.font_size}pt; line-height: {lh};
  margin: 0;
  hyphens: {'auto' if s.hyphenate else 'manual'}; hyphenate-character: "-";
  hyphenate-limit-chars: 6 3 3;
  orphans: {s.widows_orphans}; widows: {s.widows_orphans};
}}
p {{
  margin: 0 0 {s.paragraph_spacing}mm 0;
  text-indent: {s.paragraph_indent}mm;
  text-align: {'justify' if s.justify else 'left'};
}}
p.first {{ text-indent: 0; }}
p.scene {{ text-align: center; text-indent: 0; margin: {lh}em 0; }}
blockquote {{ margin: {lh/2}em 8mm; font-size: 0.92em; text-align: {'justify' if s.justify else 'left'}; }}
strong {{ font-weight: bold; }}
em {{ font-style: italic; }}

section.chapter {{ page: chapter; break-before: {chapter_break}; }}
h1 {{
  string-set: chaptertitle attr(data-title);
  font-family: {hfont}; font-size: {s.chapter_heading_size}pt; font-weight: normal;
  text-align: center; line-height: 1.2; hyphens: manual;
  margin: {s.chapter_drop if chapter_break != 'auto' else 8}mm 0 12mm 0;
  break-after: avoid;
}}
h2 {{ font-family: {hfont}; font-size: {s.font_size * 1.25}pt; font-weight: bold;
     margin: {lh}em 0 {lh/2}em 0; break-after: avoid; hyphens: manual; text-align: left; }}
h3 {{ font-family: {hfont}; font-size: {s.font_size * 1.05}pt; font-weight: bold; font-style: italic;
     margin: {lh}em 0 {lh/3}em 0; break-after: avoid; hyphens: manual; text-align: left; }}

.pagebreak {{ break-after: page; }}
.oddbreak {{ break-after: right; }}
.blankpage {{ page: blankp; break-before: page; break-after: page; height: 1px; }}

section.titlepage {{ page: front; text-align: center; break-after: right; padding-top: 25%; }}
.tp-author {{ font-family: {hfont}; font-size: {s.font_size * 1.3}pt; margin-bottom: 15mm; }}
.tp-title {{ font-family: {hfont}; font-size: {s.chapter_heading_size * 1.4}pt; line-height: 1.2; hyphens: manual; }}

section.toc {{ page: front; break-before: right; break-after: right; }}
section.toc h1 {{ string-set: none; }}
section.toc ul {{ list-style: none; padding: 0; margin: 0; }}
section.toc li {{ margin: 0 0 {lh/2}em 0; text-indent: 0; }}
section.toc a {{ color: inherit; text-decoration: none; display: block; }}
section.toc a::after {{ content: leader('.') target-counter(attr(href), page); }}
"""


def render_pdf(markup, settings: Settings):
    """Vraća (pdf_bajtovi, broj_strana, dodatih_praznih)."""
    setup_native_libs()
    import weasyprint
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject

    html_doc = build_html(markup, settings)
    css = build_css(settings)
    document = weasyprint.HTML(string=html_doc, base_url=FONTS_DIR).render(
        stylesheets=[weasyprint.CSS(string=css)]
    )
    pdf = document.write_pdf()
    count = len(document.pages)
    added = 0
    mult = max(1, int(settings.pages_multiple or 1))
    if count % mult:
        added = mult - count % mult
        reader = PdfReader(io.BytesIO(pdf))
        writer = PdfWriter(clone_from=reader)
        box = reader.pages[-1].mediabox
        for _ in range(added):
            page = writer.add_blank_page(width=float(box.width), height=float(box.height))
            for name in ("/TrimBox", "/BleedBox"):
                if name in reader.pages[-1]:
                    page[NameObject(name)] = reader.pages[-1][name]
        out = io.BytesIO()
        writer.write(out)
        pdf = out.getvalue()
    return pdf, count + added, added
