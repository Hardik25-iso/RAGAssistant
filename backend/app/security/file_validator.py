"""Upload validation: allow-list by real file signature, size limit, zip-bomb check."""
import io
import re
import zipfile
from dataclasses import dataclass

from fastapi import HTTPException, status

from app.config import get_settings

settings = get_settings()

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # legacy .ppt / .doc

MAX_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
MAX_ZIP_ENTRIES = 5000


@dataclass
class ValidatedFile:
    file_type: str  # pdf | pptx
    safe_name: str


def _bad(msg: str, code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(status_code=code, detail=msg)


def sanitize_filename(name: str) -> str:
    name = name.replace("\\", "/").split("/")[-1]  # strip any path
    name = re.sub(r"[^A-Za-z0-9._ \-()]", "_", name).strip(" .")
    return (name or "document")[:200]


def _check_pptx(data: bytes) -> None:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise _bad("File is not a valid PowerPoint (.pptx) file") from None
    infos = zf.infolist()
    names = {i.filename for i in infos}
    if "[Content_Types].xml" not in names or "ppt/presentation.xml" not in names:
        raise _bad("File is a ZIP archive but not a PowerPoint (.pptx) file")
    if len(infos) > MAX_ZIP_ENTRIES:
        raise _bad("PPTX has too many internal files")
    total = sum(i.file_size for i in infos)
    compressed = sum(i.compress_size for i in infos) or 1
    if total > MAX_UNCOMPRESSED_BYTES or total / compressed > MAX_COMPRESSION_RATIO:
        raise _bad("PPTX rejected: suspicious compression (possible zip bomb)")
    for i in infos:
        if i.filename.startswith("/") or ".." in i.filename.split("/"):
            raise _bad("PPTX contains unsafe paths")


def validate_upload(filename: str, data: bytes) -> ValidatedFile:
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) == 0:
        raise _bad("File is empty")
    if len(data) > max_bytes:
        raise _bad(f"File is larger than {settings.MAX_UPLOAD_MB} MB", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

    safe = sanitize_filename(filename or "document")
    ext = safe.rsplit(".", 1)[-1].lower() if "." in safe else ""
    head = data[:8]

    if head.startswith(OLE_MAGIC) or ext == "ppt":
        raise _bad("Old .ppt files are not supported. Save it as .pptx or export to PDF first.")
    if head.startswith(PDF_MAGIC):
        if ext != "pdf":
            raise _bad("File extension does not match its content (expected .pdf)")
        return ValidatedFile("pdf", safe)
    if head.startswith(ZIP_MAGIC):
        if ext != "pptx":
            raise _bad("File extension does not match its content (expected .pptx)")
        _check_pptx(data)
        return ValidatedFile("pptx", safe)
    raise _bad("Only PDF and PPTX files are allowed", status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
