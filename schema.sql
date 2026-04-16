CREATE TABLE conversations (
    conversation_id VARCHAR(10),
    user_id BIGINT,
    conversation_resume VARCHAR(255),
    started_at DATETIME
);

CREATE TABLE messages (
    message_id INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id VARCHAR(10),
    user_id BIGINT,
    role VARCHAR(20),
    content TEXT,
    sent_at DATETIME
);