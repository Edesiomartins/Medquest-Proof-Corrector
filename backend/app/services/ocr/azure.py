from .base import OCRProvider, OCRResultData
from app.core.config import settings

class AzureOCRProvider(OCRProvider):
    async def extract_handwriting(self, image_bytes: bytes) -> OCRResultData:
        """
        Implementação da Read API v3+ do Azure Document Intelligence.
        Ideal para caligrafia em Português.
        
        TODO: Implementar o SDK `azure-ai-documentintelligence` em produção.
        """
        print("[AzureOCR] Enviando imagem recortada para a Azure Read API...")
        
        # Mock de retorno temporário para mantermos o fluxo do pipeline isolado
        return OCRResultData(
            text="Exemplo de resposta manuscrita do aluno convertida perfeitamente em texto.",
            confidence_avg=0.92,
            needs_fallback=False
        )
