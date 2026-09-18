try:
    import pymupdf as fitz
except ImportError:
    import fitz

from typing import Dict, Any
from models.schemas import PageText, PDFExtractionResponse

class PDFProcessingError(Exception):
    """Custom exception for PDF extraction failures."""
    pass

def extract_text_from_pdf_bytes(file_bytes: bytes, filename: str) -> PDFExtractionResponse:
    """
    Extracts text page-by-page from an in-memory PDF byte stream using PyMuPDF.
    Preserves page boundaries to ensure evidence provenance.
    """
    if not file_bytes:
        raise PDFProcessingError(f"Uploaded file '{filename}' is empty.")

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise PDFProcessingError(f"Failed to open '{filename}' as a valid PDF: {str(e)}")

    try:
        if doc.is_encrypted:
            raise PDFProcessingError(f"PDF '{filename}' is password protected / encrypted.")

        page_count = len(doc)
        if page_count == 0:
            raise PDFProcessingError(f"PDF '{filename}' contains 0 pages.")

        pages = []
        all_text_segments = []

        for page_index in range(page_count):
            page = doc[page_index]
            page_text = page.get_text("text").strip()
            
            pages.append(
                PageText(
                    page_number=page_index + 1,
                    text=page_text,
                    character_count=len(page_text)
                )
            )
            if page_text:
                all_text_segments.append(f"--- Page {page_index + 1} ---\n{page_text}")

        combined_text = "\n\n".join(all_text_segments)

        return PDFExtractionResponse(
            filename=filename,
            page_count=page_count,
            pages=pages,
            combined_text=combined_text,
            status="success"
        )
    finally:
        doc.close()
