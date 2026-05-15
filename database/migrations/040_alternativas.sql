CREATE TABLE IF NOT EXISTS alternativas (
    id SERIAL PRIMARY KEY,
    texto TEXT NOT NULL,
    questao_id INTEGER NOT NULL REFERENCES questoes(id) ON DELETE CASCADE,
    is_correta BOOLEAN NOT NULL DEFAULT FALSE,
    ordem INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índice para buscas por questão
CREATE INDEX IF NOT EXISTS idx_alternativas_questao_id ON alternativas(questao_id);