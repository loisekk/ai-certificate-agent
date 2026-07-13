-- AI Certificate Agent System - Database Schema
-- PostgreSQL with pgvector extension

-- Enable pgvector extension for vector embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- =====================================================
-- TABLE 1: Workshop Transcripts (Agent 1 writes)
-- =====================================================
CREATE TABLE IF NOT EXISTS workshop_transcripts (
    id SERIAL PRIMARY KEY,
    course_name VARCHAR(255) NOT NULL,
    provider VARCHAR(100),
    chapter_title VARCHAR(255),
    chapter_number INT,
    transcript TEXT NOT NULL,
    duration_minutes INT,
    video_url VARCHAR(500),
    subtitle_language VARCHAR(10) DEFAULT 'en',
    word_count INT,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster queries
CREATE INDEX idx_transcripts_course ON workshop_transcripts(course_name);
CREATE INDEX idx_transcripts_processed ON workshop_transcripts(processed);

-- =====================================================
-- TABLE 2: Chunk Embeddings (Agent 2 writes)
-- =====================================================
CREATE TABLE IF NOT EXISTS chunk_embeddings (
    id SERIAL PRIMARY KEY,
    course_name VARCHAR(255) NOT NULL,
    chapter VARCHAR(255),
    chapter_number INT,
    chunk_index INT,
    content TEXT NOT NULL,
    embedding VECTOR(768),
    token_count INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for vector similarity search
CREATE INDEX idx_embeddings_course ON chunk_embeddings(course_name);
CREATE INDEX idx_embeddings_embedding ON chunk_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- =====================================================
-- TABLE 3: AI Summaries (Agent 2 writes)
-- =====================================================
CREATE TABLE IF NOT EXISTS ai_summaries (
    id SERIAL PRIMARY KEY,
    course_name VARCHAR(255) NOT NULL,
    summary_type VARCHAR(50) NOT NULL, -- 'chapter', 'course', 'concept', 'quiz_answer'
    chapter VARCHAR(255),
    summary_content TEXT NOT NULL,
    key_points JSONB,
    word_count INT,
    model_used VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for summary queries
CREATE INDEX idx_summaries_course ON ai_summaries(course_name);
CREATE INDEX idx_summaries_type ON ai_summaries(summary_type);

-- =====================================================
-- TABLE 4: Generated Materials (Agent 2 writes)
-- =====================================================
CREATE TABLE IF NOT EXISTS generated_materials (
    id SERIAL PRIMARY KEY,
    course_name VARCHAR(255) NOT NULL,
    material_type VARCHAR(50) NOT NULL, -- 'study_guide', 'cheat_sheet', 'key_concepts', 'quiz_answers'
    file_path VARCHAR(500),
    content TEXT NOT NULL,
    word_count INT,
    version INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for material queries
CREATE INDEX idx_materials_course ON generated_materials(course_name);
CREATE INDEX idx_materials_type ON generated_materials(material_type);

-- =====================================================
-- TABLE 5: Course Progress
-- =====================================================
CREATE TABLE IF NOT EXISTS course_progress (
    id SERIAL PRIMARY KEY,
    course_name VARCHAR(255) NOT NULL UNIQUE,
    provider VARCHAR(100),
    course_url VARCHAR(500),
    status VARCHAR(20) DEFAULT 'not_started', -- 'not_started', 'downloading', 'transcribing', 'summarizing', 'completed'
    videos_total INT DEFAULT 0,
    videos_completed INT DEFAULT 0,
    hours_total DECIMAL(5,2) DEFAULT 0,
    hours_completed DECIMAL(5,2) DEFAULT 0,
    chapters_total INT DEFAULT 0,
    chapters_completed INT DEFAULT 0,
    study_guide_ready BOOLEAN DEFAULT FALSE,
    cheat_sheet_ready BOOLEAN DEFAULT FALSE,
    key_concepts_ready BOOLEAN DEFAULT FALSE,
    certificate_earned BOOLEAN DEFAULT FALSE,
    certificate_url VARCHAR(500),
    start_date DATE,
    end_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for progress queries
CREATE INDEX idx_progress_status ON course_progress(status);
CREATE INDEX idx_progress_provider ON course_progress(provider);

-- =====================================================
-- TABLE 6: Quiz Answers (for tracking predicted answers)
-- =====================================================
CREATE TABLE IF NOT EXISTS quiz_answers (
    id SERIAL PRIMARY KEY,
    course_name VARCHAR(255) NOT NULL,
    chapter VARCHAR(255),
    question_number INT,
    question_text TEXT,
    predicted_answer TEXT,
    confidence_score DECIMAL(3,2), -- 0.00 to 1.00
    explanation TEXT,
    source_chunk_id INT REFERENCES chunk_embeddings(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for quiz queries
CREATE INDEX idx_quiz_course ON quiz_answers(course_name);

-- =====================================================
-- TABLE 7: Processing Logs
-- =====================================================
CREATE TABLE IF NOT EXISTS processing_logs (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(50) NOT NULL, -- 'agent1_watcher', 'agent2_summarizer'
    course_name VARCHAR(255),
    action VARCHAR(100),
    status VARCHAR(20), -- 'started', 'completed', 'failed'
    message TEXT,
    duration_seconds INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for log queries
CREATE INDEX idx_logs_agent ON processing_logs(agent_name);
CREATE INDEX idx_logs_course ON processing_logs(course_name);

-- =====================================================
-- FUNCTIONS
-- =====================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
CREATE TRIGGER update_transcripts_updated_at
    BEFORE UPDATE ON workshop_transcripts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_materials_updated_at
    BEFORE UPDATE ON generated_materials
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_progress_updated_at
    BEFORE UPDATE ON course_progress
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- VIEWS
-- =====================================================

-- View: Course completion status
CREATE OR REPLACE VIEW course_completion_status AS
SELECT 
    cp.course_name,
    cp.provider,
    cp.status,
    cp.videos_completed,
    cp.videos_total,
    cp.hours_completed,
    cp.hours_total,
    ROUND((cp.videos_completed::DECIMAL / NULLIF(cp.videos_total, 0)) * 100, 1) as progress_percent,
    cp.study_guide_ready,
    cp.certificate_earned
FROM course_progress cp
ORDER BY cp.updated_at DESC;

-- View: Transcript statistics
CREATE OR REPLACE VIEW transcript_stats AS
SELECT 
    course_name,
    COUNT(*) as total_chapters,
    SUM(duration_minutes) as total_minutes,
    SUM(word_count) as total_words,
    ROUND(SUM(duration_minutes) / 60.0, 1) as total_hours
FROM workshop_transcripts
GROUP BY course_name;

-- =====================================================
-- SAMPLE DATA (Optional - for testing)
-- =====================================================

-- Insert sample course progress
INSERT INTO course_progress (course_name, provider, status, videos_total, hours_total)
VALUES 
    ('Google AI Essentials', 'Google', 'not_started', 10, 10),
    ('Microsoft AI-900', 'Microsoft', 'not_started', 8, 8),
    ('AWS Cloud Practitioner', 'AWS', 'not_started', 6, 6),
    ('Anthropic Claude 101', 'Anthropic', 'not_started', 5, 5)
ON CONFLICT (course_name) DO NOTHING;
