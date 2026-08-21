"""Pares rotulados de leitura manuscrita, colhidos da tela de revisão.

Item 13 do docs/HTR_PLANO_EXECUCAO.md.

Toda vez que o professor corrige uma transcrição na revisão, ele produz — sem
esforço adicional — exatamente o dado mais caro deste domínio: um par
`(recorte, o que o modelo leu, o que está escrito de fato)`. Hoje essa
informação é sobrescrita e some.

Persistir esses pares faz duas coisas. Primeiro, o conjunto de avaliação do
item 3 cresce sozinho, com dados da prova real em vez de fixtures. Segundo, em
alguns milhares de exemplos viabiliza um ajuste fino de modelo de leitura
(LoRA sobre Qwen2.5-VL, ou TrOCR adaptado a PT-BR), que é o único caminho para
melhorar cursiva além do que prompt e pré-processamento alcançam.

O registro guarda o **caminho** do recorte, não a imagem: os recortes já vivem
em disco desde o item 9, e duplicá-los no banco custaria caro sem ganho.
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from .base import Base


class HtrLabel(Base):
    __tablename__ = "htr_labels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    question_score_id = Column(
        UUID(as_uuid=True), ForeignKey("question_scores.id", ondelete="CASCADE"), nullable=True
    )
    exam_id = Column(UUID(as_uuid=True), nullable=True)
    student_id = Column(UUID(as_uuid=True), nullable=True)
    question_number = Column(Integer, nullable=True)
    page_number = Column(Integer, nullable=True)

    answer_crop_path = Column(Text, nullable=False)
    model_transcription = Column(Text, nullable=True)
    """O que o sistema leu."""
    human_transcription = Column(Text, nullable=False)
    """O que o professor diz que está escrito. Esta é a verdade de referência."""

    character_error_rate = Column(Float, nullable=True)
    """CER da leitura do modelo contra a correção humana, calculado na gravação."""
    was_correct = Column(Boolean, nullable=False, default=False)
    """True quando o professor confirmou a leitura sem alterá-la — caso que vale
    tanto quanto a correção: sem ele, o conjunto fica enviesado só com erros."""

    reading_confidence = Column(String(16), nullable=True)
    ocr_provider = Column(String(64), nullable=True)
    vision_model = Column(String(128), nullable=True)

    reviewer_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
