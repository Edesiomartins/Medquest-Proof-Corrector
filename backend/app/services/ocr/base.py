from abc import ABC, abstractmethod
from pydantic import BaseModel

class OCRResultData(BaseModel):
    text: str
    confidence_avg: float
    needs_fallback: bool

class OCRProvider(ABC):
    @abstractmethod
    async def extract_handwriting(self, image_bytes: bytes) -> OCRResultData:
        """
        Recebe a imagem recortada da resposta e devolve o texto extraído e sua confiança.
        """
        pass
