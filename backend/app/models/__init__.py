from .base import Base
from .user import User, Organization, Class
from .student import Student
from .exam import ExamTemplate, Exam, ExamQuestion, QuestionRubric
from .pipeline import UploadBatch, DetectedExamInstance, AnswerRegion
from .grading import OCRResult, GradingResult, ManualReview

# This ensures all models are imported and registered with Base.metadata
