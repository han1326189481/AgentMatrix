CREATE TABLE IF NOT EXISTS user_profile (
    user_id VARCHAR(64) PRIMARY KEY,
    display_name VARCHAR(128),
    identity VARCHAR(32),
    long_term_goals JSON,
    preferences JSON,
    expression_style VARCHAR(32),
    learning_stage VARCHAR(32),
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW() ON UPDATE NOW()
);

CREATE TABLE IF NOT EXISTS user_capability (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(64),
    skill_node_id VARCHAR(128),
    proficiency VARCHAR(16),
    evidence JSON,
    practice_count INT DEFAULT 0,
    last_practiced DATETIME,
    updated_at DATETIME DEFAULT NOW() ON UPDATE NOW(),
    UNIQUE KEY uk_user_skill (user_id, skill_node_id)
);

CREATE TABLE IF NOT EXISTS user_project (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(64),
    project_name VARCHAR(256),
    role VARCHAR(64),
    status VARCHAR(32),
    created_at DATETIME DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_session_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(64),
    session_id VARCHAR(64),
    question TEXT,
    answer_summary TEXT,
    task_type VARCHAR(32),
    skill_nodes JSON,
    review_score DECIMAL(3,2),
    created_at DATETIME DEFAULT NOW(),
    INDEX idx_user_time (user_id, created_at)
);