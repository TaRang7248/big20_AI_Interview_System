import time
import logging
from fastapi import HTTPException, status
from pypdf import PdfReader
from packages.imh_core.dto import PDFExtractionResultDTO, PDFPageDTO
from packages.imh_providers.pdf.base import IPDFProvider
from packages.imh_core.logging import get_logger

MAX_PAGES = 50

class LocalPDFProvider(IPDFProvider):
    """
    Local PDF Text Extractor using pypdf.
    Enforces page limits and checks for valid text content.
    """
    
    def __init__(self):
        self.logger = get_logger("IMH.provider.pdf.local")

    def extract_text(self, file_path: str) -> PDFExtractionResultDTO:
        start_time = time.time()
        
        try:
            reader = PdfReader(file_path)
            
            # 1. Validation: Encryption
            if reader.is_encrypted:
                self.logger.warning(f"PDF Validation Failed: Encrypted PDF. Path: {file_path}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "ENCRYPTED_PDF", "message": "Encrypted PDF files are not supported."}
                )

            # 2. Validation: Page Count
            num_pages = len(reader.pages)
            if num_pages > MAX_PAGES:
                self.logger.warning(f"PDF Validation Failed: Too many pages ({num_pages} > {MAX_PAGES}). Path: {file_path}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error_code": "FILE_TOO_LARGE", 
                        "message": f"PDF exceeds maximum page limit ({MAX_PAGES}). Current: {num_pages}"
                    }
                )
            
            # 3. Text Extraction
            pages_dto = []
            full_text_builder = []
            total_chars = 0
            
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                page_text = page_text.strip()
                
                if page_text:
                    pages_dto.append(PDFPageDTO(page_number=i+1, text=page_text))
                    full_text_builder.append(page_text)
                    total_chars += len(page_text)
            
            full_text = "\n\n".join(full_text_builder)
            
            # 4. Validation: No Text (Image PDF)
            if not full_text:
                self.logger.warning(f"PDF Validation Failed: No text layer found (Image/Scan). Path: {file_path}")
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error_code": "NO_TEXT_FOUND", 
                        "message": "No text could be extracted. The file might be a scanned image."
                    }
                )

            # 5. Logging Metrics
            latency_ms = int((time.time() - start_time) * 1000)
            self.logger.info(
                f"PDF Extraction Success. Pages: {num_pages}, Chars: {total_chars}, Time: {latency_ms}ms. Path: {file_path}"
            )
            
            return PDFExtractionResultDTO(
                full_text=full_text,
                pages=pages_dto,
                metadata={
                    "num_pages": num_pages,
                    "file_size_bytes": 0, # Note: File size is handled by controller generally, or we can check file_path size here if needed.
                    "extraction_method": "pypdf",
                    "latency_ms": latency_ms
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error during PDF extraction. Path: {file_path}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error_code": "PDF_PROCESSING_ERROR", "message": "An unexpected error occurred during PDF processing."}
            )
