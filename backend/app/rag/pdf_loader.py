"""PDF -> list of (page_number, text), using PyMuPDF."""
import fitz  # PyMuPDF

MAX_PAGES = 500


def load_pdf(data: bytes) -> list[tuple[int, str]]:
    pages: list[tuple[int, str]] = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        if doc.needs_pass:
            raise ValueError("Password-protected PDFs are not supported")
        if doc.page_count > MAX_PAGES:
            raise ValueError(f"PDF has more than {MAX_PAGES} pages")
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if text:
                pages.append((i, text))
    if not pages:
        raise ValueError("No text found. Scanned PDFs (images only) are not supported yet.")
    return pages
