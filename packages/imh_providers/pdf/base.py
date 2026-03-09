from abc import ABC, abstractmethod
from packages.imh_core.dto import PDFExtractionResultDTO

class IPDFProvider(ABC):
    """
    Abstract Base Class for PDF Text Extraction Providers.
    """
    
    @abstractmethod
    def extract_text(self, file_path: str) -> PDFExtractionResultDTO:
        """
        Extract text from a PDF file.

        Args:
            file_path (str): Absolute path to the PDF file.

        Returns:
            PDFExtractionResultDTO: Extracted text and metadata.

        Raises:
            Exception: If extraction fails.
        """
        pass
