-- Setup UUID Extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enums
CREATE TYPE role_enum AS ENUM ('PROFESSOR', 'ADMIN');
CREATE TYPE batch_status AS ENUM ('PENDING', 'PARSING', 'CROPPING', 'OCR', 'GRADING', 'REVIEW_PENDING', 'DONE', 'FAILED');
CREATE TYPE review_status AS ENUM ('PENDING', 'APPROVED');
CREATE TYPE ocr_status AS ENUM ('PENDING', 'SUCCESS', 'FAILED', 'NEEDS_FALLBACK');

-- 1. Organizations & Classes
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE classes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de Alunos (Lista da Turma)
CREATE TABLE students (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    class_id UUID NOT NULL REFERENCES classes(id),
    name VARCHAR NOT NULL,
    registration_number VARCHAR NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR NOT NULL UNIQUE,
    password_hash VARCHAR NOT NULL,
    role role_enum NOT NULL DEFAULT 'PROFESSOR',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_users_email ON users(email);

-- 3. Exam Templates & Exams
CREATE TABLE exam_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR NOT NULL,
    pdf_blueprint_url VARCHAR,
    page_width FLOAT NOT NULL,
    page_height FLOAT NOT NULL
);

CREATE TABLE exams (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_id UUID NOT NULL REFERENCES exam_templates(id),
    class_id UUID REFERENCES classes(id),
    name VARCHAR NOT NULL,
    max_score FLOAT NOT NULL
);

CREATE TABLE exam_questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exam_id UUID NOT NULL REFERENCES exams(id),
    question_text TEXT NOT NULL,
    max_score FLOAT NOT NULL,
    expected_answer TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    box_x FLOAT NOT NULL,
    box_y FLOAT NOT NULL,
    box_w FLOAT NOT NULL,
    box_h FLOAT NOT NULL
);

CREATE TABLE question_rubrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    question_id UUID NOT NULL REFERENCES exam_questions(id),
    criteria TEXT NOT NULL,
    score_impact FLOAT NOT NULL,
    is_mandatory BOOLEAN DEFAULT FALSE
);

-- 4. Upload Pipeline
CREATE TABLE upload_batches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exam_id UUID NOT NULL REFERENCES exams(id),
    file_url VARCHAR NOT NULL,
    status batch_status NOT NULL DEFAULT 'PENDING',
    total_pages_detected INTEGER DEFAULT 0
);

CREATE TABLE detected_exam_instances (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_id UUID NOT NULL REFERENCES upload_batches(id),
    student_id UUID REFERENCES students(id),
    review_status review_status DEFAULT 'PENDING'
);

CREATE TABLE answer_regions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    instance_id UUID NOT NULL REFERENCES detected_exam_instances(id),
    question_id UUID NOT NULL REFERENCES exam_questions(id),
    cropped_image_url VARCHAR,
    ocr_status ocr_status DEFAULT 'PENDING'
);

-- 5. Grading & Review
CREATE TABLE ocr_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    answer_region_id UUID NOT NULL REFERENCES answer_regions(id) ON DELETE CASCADE,
    provider_used VARCHAR NOT NULL,
    extracted_text TEXT,
    confidence_avg FLOAT,
    needs_fallback_flag BOOLEAN DEFAULT FALSE
);

CREATE TABLE grading_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ocr_result_id UUID NOT NULL REFERENCES ocr_results(id) ON DELETE CASCADE,
    model_used VARCHAR NOT NULL,
    suggested_score FLOAT NOT NULL,
    criteria_met_json JSONB,
    justification TEXT,
    requires_manual_review BOOLEAN DEFAULT FALSE
);

CREATE TABLE manual_reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    grading_result_id UUID NOT NULL REFERENCES grading_results(id) ON DELETE CASCADE,
    reviewer_id UUID NOT NULL REFERENCES users(id),
    final_score FLOAT NOT NULL,
    reviewer_comments TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
