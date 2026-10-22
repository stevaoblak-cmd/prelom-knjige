"""Uvoz teksta iz Word (.docx) i PDF datoteka u jednostavan "prelom" zapis.

Prelom zapis (lako se ručno ispravlja u programu):
    # Naslov poglavlja        -> novo poglavlje (počinje na novoj / neparnoj strani)
    ## Podnaslov              -> naslov odeljka
    ### Manji naslov
    > Citat                   -> uvučen citat
    * * *                     -> razmak između scena
    [nova strana]             -> prelom strane
    [prazna strana]           -> ubacuje praznu stranu
    **podebljano**, *kurziv*
Pasusi se razdvajaju praznim redom.
"""
import re
import statistics
from collections import Counter

SCENE_RE = re.compile(r"^\s*([*#~•·]\s*){3,}\s*$|^\s*\*\s*\*\s*\*\s*$")
CHAPTER_WORD_RE = re.compile(
    r"^\s*(poglavlje|glava|deo|део|поглавље|глава|chapter|prolog|epilog|пролог|епилог)\b",
    re.IGNORECASE,
)


def escape(text):
    return text.replace("\\", "\\\\").replace("*", "\\*")


def runs_to_markup(runs):
    """runs: lista (tekst, bold, italic) -> tekst sa ** i * oznakama."""
    # spoji susedne delove istog stila
    merged = []
    for text, b, i in runs:
        if not text:
            continue
        if merged and merged[-1][1] == b and merged[-1][2] == i:
            merged[-1][0] += text
        else:
            merged.append([text, b, i])
    out = []
    for text, b, i in merged:
        t = escape(text)
        stripped = t.strip()
        if not stripped or not (b or i):
            out.append(t)
            continue
        lead = t[: len(t) - len(t.lstrip())]
        trail = t[len(t.rstrip()):]
        mark = ("**" if b else "") + ("*" if i else "")
        out.append(f"{lead}{mark}{stripped}{mark[::-1]}{trail}")
    return "".join(out).strip()


# --------------------------------------------------------------------- DOCX

def _docx_heading_level(par):
    name = (par.style.name or "").lower() if par.style is not None else ""
    if name in ("title", "naslov"):
        return 1
    m = re.match(r"(heading|naslov|заглавље|наслов)\s*(\d)", name)
    if m:
        return min(int(m.group(2)), 3)
    # nivo strukture zadat direktno na pasusu
    ppr = par._p.pPr
    if ppr is not None:
        ol = ppr.find(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}outlineLvl"
        )
        if ol is not None:
            val = ol.get(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val"
            )
            if val is not None and val.isdigit() and int(val) < 9:
                return min(int(val) + 1, 3)
    return 0


def import_docx(path):
    import docx

    document = docx.Document(path)
    lines = []
    for par in document.paragraphs:
        text = par.text.strip()
        if not text:
            continue
        if SCENE_RE.match(text):
            lines.append("* * *")
            continue
        level = _docx_heading_level(par)
        if level:
            lines.append("#" * level + " " + escape(text))
            continue
        runs = [(r.text, bool(r.bold), bool(r.italic)) for r in par.runs]
        all_bold = all(b for t, b, _ in runs if t.strip())
        if all_bold and len(text) < 80 and CHAPTER_WORD_RE.match(text):
            lines.append("# " + escape(text))
            continue
        lines.append(runs_to_markup(runs))
    return "\n\n".join(lines) + "\n"


# ---------------------------------------------------------------------- PDF

def _join_lines(lines):
    """Spaja redove u pasus, uklanjajući prelom reči na kraju reda."""
    out = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if out.endswith(("-", "­", "‐")) and line[:1].islower():
            out = out[:-1] + line
        elif out:
            out += " " + line
        else:
            out = line
    return out


def import_pdf(path):
    import pymupdf

    doc = pymupdf.open(path)
    pages = []
    sizes = Counter()
    for page in doc:
        data = page.get_text("dict")
        height = page.rect.height
        blocks = []
        for b in data["blocks"]:
            if b.get("type") != 0:
                continue
            blines = []
            for ln in b["lines"]:
                spans = [s for s in ln["spans"] if s["text"].strip()]
                if not spans:
                    continue
                runs = []
                for s in ln["spans"]:
                    font = s["font"].lower()
                    bold = bool(s["flags"] & 16) or "bold" in font
                    italic = bool(s["flags"] & 2) or "italic" in font or "oblique" in font
                    runs.append((s["text"], bold, italic))
                size = max(s["size"] for s in spans)
                for s in spans:
                    sizes[round(s["size"], 1)] += len(s["text"])
                blines.append({"runs": runs, "size": size, "y0": ln["bbox"][1],
                               "y1": ln["bbox"][3], "x0": ln["bbox"][0]})
            if blines:
                blocks.append({"lines": blines, "bbox": b["bbox"], "page_h": height})
        pages.append(blocks)

    if not sizes:
        return ""
    body = sizes.most_common(1)[0][0]

    # ponavljajuća zaglavlja/podnožja i brojevi strana
    edge_texts = Counter()
    for blocks in pages:
        for b in blocks:
            if b["bbox"][1] < b["page_h"] * 0.08 or b["bbox"][3] > b["page_h"] * 0.92:
                edge_texts[_block_plain(b)] += 1
    repeated = {t for t, n in edge_texts.items()
                if n >= max(3, len(pages) * 0.3) or (n >= 2 and len(t) < 80)}

    paragraphs = []  # (vrsta, runs) vrsta: 'p' ili nivo naslova
    for blocks in pages:
        for b in blocks:
            plain = _block_plain(b)
            near_edge = b["bbox"][1] < b["page_h"] * 0.08 or b["bbox"][3] > b["page_h"] * 0.92
            if near_edge and (re.fullmatch(r"[\d\s\-–—ivxlcdmIVXLCDM.]*", plain) or plain in repeated):
                continue
            size = max(l["size"] for l in b["lines"])
            level = 0
            if size >= body * 1.6:
                level = 1
            elif size >= body * 1.25:
                level = 2
            elif size >= body * 1.1:
                level = 3
            if level:
                paragraphs.append((level, [(_join_lines([_line_plain(l) for l in b["lines"]]), False, False)]))
                continue
            # razbij blok na pasuse po uvlaci prvog reda
            xs = [l["x0"] for l in b["lines"]]
            left = min(xs)
            current = []
            for l in b["lines"]:
                if current and l["x0"] > left + body * 0.8:
                    paragraphs.append(("p", current))
                    current = []
                current.append(l)
            if current:
                paragraphs.append(("p", current))

    # pasus koji se nastavlja na sledećoj strani (ne završava se interpunkcijom)
    merged = []
    for kind, content in paragraphs:
        if kind == "p":
            if (merged and merged[-1][0] == "p" and merged[-1][2]
                    and not re.search(r"[.!?:…\"”»)]\s*$", _line_plain(merged[-1][1][-1]))):
                first = _line_plain(content[0])
                if first[:1].islower():
                    merged[-1][1].extend(content)
                    merged[-1][2] = False
                    continue
            merged.append(["p", list(content), True])
        else:
            merged.append([kind, content, False])

    out = []
    for kind, content, _ in merged:
        if kind == "p":
            text = _lines_to_markup(content)
            if SCENE_RE.match(text.replace("\\", "")):
                out.append("* * *")
            elif text:
                out.append(text)
        else:
            out.append("#" * kind + " " + escape(content[0][0]))
    return "\n\n".join(out) + "\n"


def _line_plain(line):
    return "".join(r[0] for r in line["runs"]).strip()


def _block_plain(block):
    return " ".join(_line_plain(l) for l in block["lines"]).strip()


def _lines_to_markup(lines):
    runs = []
    for i, line in enumerate(lines):
        lr = [list(r) for r in line["runs"] if r[0]]
        if not lr:
            continue
        lr[0][0] = lr[0][0].lstrip()
        lr[-1][0] = lr[-1][0].rstrip()
        if runs:
            prev = runs[-1][0]
            first = lr[0][0]
            if prev.endswith(("-", "­", "‐")) and first[:1].islower():
                runs[-1][0] = prev[:-1]
            else:
                runs[-1][0] = prev + " "
        runs.extend(lr)
    return runs_to_markup([tuple(r) for r in runs])


def import_txt(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def import_file(path, filename=None):
    name = (filename or path).lower()
    if name.endswith(".docx"):
        return import_docx(path)
    if name.endswith(".pdf"):
        return import_pdf(path)
    if name.endswith((".txt", ".md")):
        return import_txt(path)
    if name.endswith(".doc"):
        raise ValueError("Stari .doc format nije podržan. Sačuvajte dokument kao .docx u Word-u.")
    raise ValueError("Podržani formati su .docx, .pdf i .txt")
