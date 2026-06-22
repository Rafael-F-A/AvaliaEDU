CREATE TABLE IF NOT EXISTS modelos_questao (
    id SERIAL PRIMARY KEY,
    modelo_texto TEXT NOT NULL,
    nivel VARCHAR(20) NOT NULL,
    serie VARCHAR(20),
    componente_id INTEGER REFERENCES componentes_curriculares(id) ON DELETE SET NULL,
    dificuldade VARCHAR(20) DEFAULT 'MEDIO' CHECK (dificuldade IN ('FACIL', 'MEDIO', 'DIFICIL')),
    gabarito TEXT,
    distradores JSON,
    variaveis JSON,
    imagem_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_modelos_nivel ON modelos_questao(nivel);
CREATE INDEX idx_modelos_componente ON modelos_questao(componente_id);

-- Para bancos ja existentes (nao-destrutivo).
ALTER TABLE modelos_questao ADD COLUMN IF NOT EXISTS gabarito TEXT;
ALTER TABLE modelos_questao ADD COLUMN IF NOT EXISTS distradores JSON;
ALTER TABLE modelos_questao ADD COLUMN IF NOT EXISTS variaveis JSON;
ALTER TABLE modelos_questao ADD COLUMN IF NOT EXISTS imagem_url VARCHAR(500);