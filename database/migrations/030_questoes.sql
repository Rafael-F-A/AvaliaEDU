CREATE TABLE IF NOT EXISTS questoes (
    id SERIAL PRIMARY KEY,
    enunciado TEXT NOT NULL,
    prova_id INTEGER NOT NULL REFERENCES provas(id) ON DELETE CASCADE,
    nivel_dificuldade VARCHAR(20) DEFAULT 'MEDIO' CHECK (nivel_dificuldade IN ('FACIL', 'MEDIO', 'DIFICIL')),
    pontuacao DECIMAL(5,2) DEFAULT 1.0,
    ordem INTEGER,
    imagem_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Para bancos ja existentes (nao-destrutivo).
ALTER TABLE questoes ADD COLUMN IF NOT EXISTS imagem_url VARCHAR(500);