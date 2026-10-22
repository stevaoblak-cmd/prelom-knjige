"""Prelom knjige kao program u sopstvenom prozoru (Windows instaler pokreće ovu datoteku)."""
import base64
import os
import socket
import sys
import threading

from app import app


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Api:
    """Funkcije koje stranica poziva preko window.pywebview.api (čuvanje datoteka)."""

    def __init__(self):
        self.window = None

    def save_file(self, filename, data_b64):
        import webview

        ext = os.path.splitext(filename)[1].lstrip(".") or "*"
        result = self.window.create_file_dialog(
            webview.SAVE_DIALOG, save_filename=filename,
            file_types=(f"{ext.upper()} (*.{ext})", "Sve datoteke (*.*)"),
        )
        if not result:
            return False
        path = result if isinstance(result, str) else result[0]
        with open(path, "wb") as f:
            f.write(base64.b64decode(data_b64))
        return path


def test_render(out_path):
    """Provera zapakovanog programa: uvoz primera i prelom u PDF, bez prozora."""
    from prelom.importers import import_file
    from prelom.layout import Settings, render_pdf
    from prelom.paths import APP_DIR

    text = import_file(os.path.join(APP_DIR, "primeri", "primer_cirilica.docx"))
    pdf, pages, _ = render_pdf(text, Settings(title="Проба", toc="start"))
    with open(out_path, "wb") as f:
        f.write(pdf)
    print(f"OK: {pages} strana -> {out_path}")


def _redirect_output():
    """Zapakovan program nema konzolu: ispis ide u log datoteku."""
    if sys.stdout is None or sys.stderr is None:
        from prelom.paths import DATA_DIR

        os.makedirs(DATA_DIR, exist_ok=True)
        log = open(os.path.join(DATA_DIR, "prelom.log"), "a", encoding="utf-8")
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log


def main():
    _redirect_output()
    if len(sys.argv) > 2 and sys.argv[1] == "--test-render":
        test_render(sys.argv[2])
        return
    port = free_port()
    server = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    server.start()
    url = f"http://127.0.0.1:{port}"
    try:
        import webview
    except ImportError:  # bez pywebview: otvori u pregledaču
        import webbrowser

        webbrowser.open(url)
        server.join()
        return
    api = Api()
    api.window = webview.create_window("Prelom knjige", url, js_api=api,
                                       width=1400, height=900, min_size=(900, 600))
    webview.start()


if __name__ == "__main__":
    main()
