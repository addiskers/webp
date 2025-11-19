from __future__ import annotations

import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Iterable, List, Tuple
from zipfile import ZipFile

from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from PIL import Image, UnidentifiedImageError
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


WEBP_EXPORT_ARGS = {"format": "WEBP", "quality": 95, "method": 6, "lossless": False}
ALLOWED_SUFFIXES = {".jpg", ".jpeg"}


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")
    app.config.setdefault("MAX_CONTENT_LENGTH", 64 * 1024 * 1024)  # 64 MB

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.post("/convert")
    def convert() -> Response:
        files = extract_files(request.files.getlist("images"))
        if not files:
            flash("Please choose at least one JPG/JPEG image.", "error")
            return redirect(url_for("index"))

        successes, failures, archive = convert_to_webp(files)

        if not successes:
            error_text = "\n".join(failures) if failures else "Unable to convert the uploads."
            flash(error_text, "error")
            return redirect(url_for("index"))

        if failures:
            flash(f"Converted {len(successes)} file(s). Skipped {len(failures)} issue(s).", "warning")

        archive.seek(0)
        stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
        filename = f"webp-conversion-{stamp}.zip"
        return send_file(
            archive,
            mimetype="application/zip",
            as_attachment=True,
            download_name=filename,
        )

    return app


def extract_files(file_list: Iterable[FileStorage]) -> List[FileStorage]:
    return [f for f in file_list if f.filename]


def convert_to_webp(
    uploads: Iterable[FileStorage],
) -> Tuple[List[str], List[str], BytesIO]:
    successes: List[str] = []
    failures: List[str] = []
    archive = BytesIO()

    with ZipFile(archive, "w") as zipped:
        for upload in uploads:
            filename = secure_filename(upload.filename or "")
            suffix = Path(filename).suffix.lower()
            if suffix not in ALLOWED_SUFFIXES:
                failures.append(f"{filename or 'Unknown'}: unsupported file type")
                continue

            try:
                webp_bytes = convert_single_stream(upload)
            except (UnidentifiedImageError, OSError) as exc:
                failures.append(f"{filename or 'Unknown'}: {exc}")
                continue

            webp_name = f"{Path(filename).stem}.webp"
            zipped.writestr(webp_name, webp_bytes.getvalue())
            successes.append(webp_name)

    return successes, failures, archive


def convert_single_stream(upload: FileStorage) -> BytesIO:
    upload.stream.seek(0)
    with Image.open(upload.stream) as img:
        converted = img.convert("RGB")
        buffer = BytesIO()
        converted.save(buffer, **WEBP_EXPORT_ARGS)
        buffer.seek(0)
        return buffer


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5008"))
    app.run(host="0.0.0.0", port=port, debug=False)

