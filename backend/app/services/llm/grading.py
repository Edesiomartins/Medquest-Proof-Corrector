from pydantic import BaseModel
import httpx
import json
from app.core.config import settings

class GradingContext(BaseModel):
    question_text: str
    max_score: float
    expected_answer: str
    rubrics: str
    student_answer_ocr: str

class GradingResultData(BaseModel):
    score_suggested: float
    max_score: float
    criteria_met: list[str]
    criteria_missing: list[str]
    justification: str
    grading_confidence: float
    manual_review_required: bool

class OpenRouterGradingService:
    @staticmethod
    async def grade(context: GradingContext) -> GradingResultData:
        """
        Conecta na API do OpenRouter e processa o modelo Claude 3.5 Sonnet
        utilizando Structured Outputs (JSON Schema).
        """
        print(f"[OpenRouter] Enviando requisição para Correção via LLM...")
        
        # TODO: Implementar chamada real `httpx.AsyncClient().post(...)`
        # usando settings.OPENROUTER_API_KEY
        
        # Retorno Mock para que o worker possa seguir
        return GradingResultData(
            score_suggested=context.max_score * 0.8,
            max_score=context.max_score,
            criteria_met=["Mencionou os principais conceitos", "Boa estruturação"],
            criteria_missing=["Esqueceu o detalhe secundário da complicação clínica"],
            justification="O aluno atendeu à maioria dos requisitos, mas perdeu 20% da nota ao não citar a complicação.",
            grading_confidence=0.88,
            manual_review_required=False
        )
