"""Prelom knjige - pokretanje: python app.py, pa otvoriti http://127.0.0.1:5000"""
import os
import tempfile
import webbrowser

from flask import Flask, jsonify, render_template, request, Response
from werkzeug.utils import secure_filename

from prelom.importers import import_file
from prelom.layout import FONTS_DIR, PAGE_SIZES, Settings, available_fonts, render_pdf

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024


@app.get("/")
def index():
    return render_template(
        "index.html",
        defaults=Settings().to_dict(),
        page_sizes=list(PAGE_SIZES) + ["Prilagođeno"],
    )


@app.get("/api/fonts")
def fonts():
    return jsonify(available_fonts())


@app.post("/api/fonts")
def upload_font():
    f = request.files.get("file")
    if not f or not f.filename.lower().endswith((".ttf", ".otf")):
        return jsonify(error="Izaberite .ttf ili .otf datoteku fonta."), 400
    os.makedirs(FONTS_DIR, exist_ok=True)
    f.save(os.path.join(FONTS_DIR, secure_filename(f.filename) or "font.ttf"))
    return jsonify(available_fonts())


@app.post("/api/import")
def do_import():
    f = request.files.get("file")
    if not f:
        return jsonify(error="Nije izabrana datoteka."), 400
    suffix = os.path.splitext(f.filename)[1].lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        f.save(tmp.name)
        path = tmp.name
    try:
        text = import_file(path, f.filename)
    except Exception as e:  # prikaži grešku korisniku
        return jsonify(error=str(e)), 400
    finally:
        os.unlink(path)
    return jsonify(text=text)


@app.post("/api/render")
def do_render():
    data = request.get_json(force=True)
    settings = Settings.from_dict(data.get("settings", {}))
    try:
        pdf, pages, added = render_pdf(data.get("text", ""), settings)
    except Exception as e:
        return jsonify(error=f"Greška pri prelomu: {e}"), 500
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"X-Pages": str(pages), "X-Added-Blank": str(added)},
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    if not os.environ.get("NO_BROWSER"):
        webbrowser.open(f"http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
