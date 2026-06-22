-- Log de auditoria. Conforme o banco real: usuario_id NAO possui FK (registro
-- preservado mesmo apos remocao do usuario) e acao/entidade sao nullable.
CREATE TABLE IF NOT EXISTS auditoria (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER,
    acao VARCHAR(100),
    entidade VARCHAR(50),
    entidade_id INTEGER,
    ip VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
