import io

class PDFBuilderService:
    @staticmethod
    def generate_class_exam_batch(exam_id: str, students: list) -> bytes:
        """
        [MOCK MVP] Serviço que desenha o PDF personalizado de provas.
        Para cada aluno na lista da turma, o algoritmo:
        1. Resgata o layout do gabarito (Exam Template).
        2. Insere Cabeçalho (Nome do Aluno, Matrícula).
        3. Insere QR Code legível por máquina vinculado a {exam_id}:{student_id}.
        
        TODO em Prod: Usar reportlab.pdfgen.canvas e a biblioteca qrcode.
        """
        print(f"[PDF_BUILDER] Gerando caderno PDF com {len(students)} provas base...")
        
        # Simulação dos bytes do PDF compilado final
        mock_pdf_bytes = b"%PDF-1.4 Mock PDF Header com QR Codes embutidos"
        return mock_pdf_bytes
