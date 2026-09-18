from fastapi import APIRouter, UploadFile, File, HTTPException, status
from services.pdf_service import extract_text_from_pdf_bytes, PDFProcessingError
from models.schemas import PDFExtractionResponse

router = APIRouter(prefix="/api/documents", tags=["documents"])

@router.post("/extract", response_model=PDFExtractionResponse)
async def extract_pdf_document(file: UploadFile = File(...)):
    """
    Accepts an uploaded FIR PDF file, validates it, and extracts text
    page-by-page to support evidence provenance in later pipeline stages.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided in upload."
        )

    # Basic extension validation
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type for '{file.filename}'. Only PDF (.pdf) files are supported."
        )

    try:
        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{file.filename}' is empty."
            )
        
        result = extract_text_from_pdf_bytes(content, file.filename)
        return result
    except PDFProcessingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error while processing PDF: {str(e)}"
        )
