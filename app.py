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
from werkzeug.exceptions import HTTPException


WEBP_EXPORT_ARGS = {"format": "WEBP", "quality": 95, "method": 6, "lossless": False}
ALLOWED_SUFFIXES = {".jpg", ".jpeg"}
MAX_FILE_COUNT = 200


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
        if len(files) > MAX_FILE_COUNT:
            flash(
                f"Please upload at most {MAX_FILE_COUNT} images at once. "
                f"We received {len(files)} files.",
                "error",
            )
            return redirect(url_for("index"))

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

    @app.errorhandler(413)
    def handle_request_entity_too_large(exc: HTTPException) -> Tuple[str, int]:
        return render_error_page(
            413,
            "Upload too large",
            "Your upload exceeded the 64 MB limit. Try converting fewer files at a time.",
        )

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException) -> Tuple[str, int]:
        status_code = getattr(exc, "code", 500) or 500
        title = getattr(exc, "name", "Application error")
        description = getattr(exc, "description", "We couldn't process your request.")
        return render_error_page(status_code, title, description)

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception) -> Tuple[str, int]:
        app.logger.exception("Unhandled error during request", exc_info=exc)
        return render_error_page(
            500,
            "Unexpected error",
            "We hit a snag while processing your images. Please try again.",
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


def render_error_page(status_code: int, title: str, message: str) -> Tuple[str, int]:
    return (
        render_template(
            "error.html",
            status_code=status_code,
            title=title,
            message=message,
            home_url=url_for("index"),
        ),
        status_code,
    )


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

