-- ============================================================
-- Supabase Schema for AI-Driven Personalized VR Teaching System
-- EXTENSIBLE DESIGN: Class-based with dynamic subjects
-- Run this in Supabase SQL Editor to create all required tables
-- ============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- CLASSES TABLE (Class 1-12, expandable)
-- ============================================================
CREATE TABLE IF NOT EXISTS classes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    class_name TEXT NOT NULL UNIQUE, -- "Class 1", "Class 10", "Class 12"
    class_number INTEGER NOT NULL UNIQUE, -- 1, 10, 12 (for sorting)
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed initial classes
INSERT INTO
    classes (
        class_name,
        class_number,
        description
    )
VALUES (
        'Class 1',
        1,
        'Primary - Grade 1'
    ),
    (
        'Class 2',
        2,
        'Primary - Grade 2'
    ),
    (
        'Class 3',
        3,
        'Primary - Grade 3'
    ),
    (
        'Class 4',
        4,
        'Primary - Grade 4'
    ),
    (
        'Class 5',
        5,
        'Primary - Grade 5'
    ),
    (
        'Class 6',
        6,
        'Middle School - Grade 6'
    ),
    (
        'Class 7',
        7,
        'Middle School - Grade 7'
    ),
    (
        'Class 8',
        8,
        'Middle School - Grade 8'
    ),
    (
        'Class 9',
        9,
        'High School - Grade 9'
    ),
    (
        'Class 10',
        10,
        'High School - Grade 10 (Board)'
    ),
    (
        'Class 11',
        11,
        'Senior Secondary - Grade 11'
    ),
    (
        'Class 12',
        12,
        'Senior Secondary - Grade 12 (Board)'
    ) ON CONFLICT (class_number) DO NOTHING;

-- ============================================================
-- SUBJECTS TABLE (Dynamic per class)
-- ============================================================
CREATE TABLE IF NOT EXISTS subjects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    class_id UUID NOT NULL REFERENCES classes (id) ON DELETE CASCADE,
    subject_code TEXT NOT NULL, -- "physics", "maths", "chemistry"
    subject_name TEXT NOT NULL, -- "Physics", "Mathematics", "Chemistry"
    description TEXT,
    icon_url TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (class_id, subject_code)
);

-- Seed Class 10 subjects (current focus)
INSERT INTO
    subjects (
        class_id,
        subject_code,
        subject_name,
        description
    )
SELECT c.id, s.code, s.name, s.desc
FROM classes c
    CROSS JOIN (
        VALUES (
                'physics', 'Physics', 'Study of matter, energy, and their interactions'
            ), (
                'chemistry', 'Chemistry', 'Study of substances and their properties'
            ), (
                'maths', 'Mathematics', 'Study of numbers, quantities, and shapes'
            )
    ) AS s (code, name, desc)
WHERE
    c.class_number = 10 ON CONFLICT (class_id, subject_code) DO NOTHING;

-- ============================================================
-- SYLLABUS TOPICS TABLE (Topics within subjects)
-- ============================================================
CREATE TABLE IF NOT EXISTS syllabus_topics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    subject_id UUID NOT NULL REFERENCES subjects (id) ON DELETE CASCADE,
    topic_code TEXT NOT NULL, -- "projectile_motion", "kinematics"
    topic_name TEXT NOT NULL, -- "Projectile Motion", "Kinematics"
    description TEXT,
    subtopics JSONB DEFAULT '[]',
    prerequisites JSONB DEFAULT '[]', -- topic_codes that should be learned first
    order_index INTEGER DEFAULT 0, -- for sequencing
    estimated_duration_minutes INTEGER DEFAULT 30,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (subject_id, topic_code)
);

-- ============================================================
-- USERS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    class_id UUID REFERENCES classes (id), -- Which class the user is in
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

CREATE INDEX IF NOT EXISTS idx_users_class ON users (class_id);

-- ============================================================
-- LEARNER PROFILES TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS learner_profiles (
    student_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    name TEXT,

-- Learning preferences
learning_style TEXT DEFAULT 'visual+analogy',
preferred_analogies JSONB DEFAULT '["sports", "daily_life"]',

-- Topic tracking (keyed by subject_id:topic_code)
weak_topics JSONB DEFAULT '[]',
strong_topics JSONB DEFAULT '[]',
topic_knowledge JSONB DEFAULT '{}',

-- Historical data
historical_mistakes JSONB DEFAULT '[]',
    total_study_time_minutes INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- ASSESSMENTS TABLE (No hardcoded subject constraints)
-- ============================================================
CREATE TABLE IF NOT EXISTS assessments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id UUID REFERENCES subjects(id),  -- Link to subjects table

-- For flexibility, also store codes
subject_code TEXT NOT NULL,
topic_code TEXT NOT NULL,
topic_name TEXT,
assessment_type TEXT DEFAULT 'diagnostic',

-- Scores
score INTEGER NOT NULL CHECK (
    score >= 0
    AND score <= 100
),
max_score INTEGER DEFAULT 100,
level TEXT NOT NULL,
confidence FLOAT DEFAULT 0.5,

-- Analysis
misconceptions JSONB DEFAULT '[]',
    weak_concepts JSONB DEFAULT '[]',
    strong_concepts JSONB DEFAULT '[]',
    
    questions_attempted INTEGER DEFAULT 0,
    questions_correct INTEGER DEFAULT 0,
    time_taken_seconds INTEGER,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assessments_student ON assessments (student_id);

CREATE INDEX IF NOT EXISTS idx_assessments_subject ON assessments (subject_id);

CREATE INDEX IF NOT EXISTS idx_assessments_created ON assessments (created_at DESC);

-- ============================================================
-- TOPIC PROGRESS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS topic_progress (
    student_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    subject_id UUID NOT NULL REFERENCES subjects (id) ON DELETE CASCADE,
    topic_code TEXT NOT NULL,
    mastery_score FLOAT DEFAULT 0 CHECK (
        mastery_score >= 0
        AND mastery_score <= 100
    ),
    attempts INTEGER DEFAULT 0,
    last_attempt TIMESTAMPTZ,
    PRIMARY KEY (
        student_id,
        subject_id,
        topic_code
    )
);

CREATE INDEX IF NOT EXISTS idx_topic_progress_student ON topic_progress (student_id);

-- ============================================================
-- MISCONCEPTIONS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS misconceptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    student_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    subject_id UUID REFERENCES subjects (id),
    topic_code TEXT NOT NULL,
    misconception TEXT NOT NULL,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    detected_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_misconceptions_student ON misconceptions (student_id);

-- ============================================================
-- VR SESSIONS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS vr_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    student_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    subject_id UUID REFERENCES subjects (id),
    topic_code TEXT NOT NULL,
    total_steps INTEGER DEFAULT 0,
    completed_steps INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    duration_seconds INTEGER,
    interactions_count INTEGER DEFAULT 0,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

-- ============================================================
-- EXAMS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS exams (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    student_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    subject_id UUID REFERENCES subjects (id),
    topic_code TEXT NOT NULL,
    exam_type TEXT DEFAULT 'practice',
    questions JSONB NOT NULL DEFAULT '[]',
    responses JSONB DEFAULT '[]',
    total_score INTEGER,
    max_score INTEGER,
    percentage FLOAT,
    question_results JSONB DEFAULT '[]',
    overall_feedback TEXT,
    misconceptions JSONB DEFAULT '[]',
    recommendations JSONB DEFAULT '[]',
    time_limit_minutes INTEGER,
    time_taken_seconds INTEGER,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    graded_at TIMESTAMPTZ
);

-- ============================================================
-- HELPER VIEWS
-- ============================================================

-- View: Get subjects with class info
CREATE OR REPLACE VIEW v_subjects_with_class AS
SELECT
    s.id as subject_id,
    s.subject_code,
    s.subject_name,
    c.id as class_id,
    c.class_name,
    c.class_number
FROM subjects s
    JOIN classes c ON s.class_id = c.id
WHERE
    s.is_active = TRUE
    AND c.is_active = TRUE
ORDER BY c.class_number, s.subject_name;

-- View: Get topics with subject and class info
CREATE OR REPLACE VIEW v_topics_full AS
SELECT t.id as topic_id, t.topic_code, t.topic_name, t.subtopics, t.prerequisites, t.order_index, s.subject_code, s.subject_name, c.class_name, c.class_number
FROM
    syllabus_topics t
    JOIN subjects s ON t.subject_id = s.id
    JOIN classes c ON s.class_id = c.id
WHERE
    t.is_active = TRUE
ORDER BY c.class_number, s.subject_name, t.order_index;

-- ============================================================
-- FUNCTIONS
-- ============================================================

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_learner_profiles_updated_at
    BEFORE UPDATE ON learner_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- ENABLE RLS (uncomment when ready)
-- ============================================================
-- ALTER TABLE users ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE learner_profiles ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE assessments ENABLE ROW LEVEL SECURITY;