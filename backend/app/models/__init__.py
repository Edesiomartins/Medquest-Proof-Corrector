from .base import Base
from .user import User
from .student import Student, Organization, Class
from .exam import ExamTemplate, Exam, ExamQuestion, QuestionRubric
from .pipeline import UploadBatch, DetectedExamInstance, AnswerRegion
from .grading import OCRResult, GradingResult, ManualReview

# This ensures all models are imported and registered with Base.metadata
