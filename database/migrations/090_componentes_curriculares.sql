CREATE TABLE IF NOT EXISTS componentes_curriculares (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL UNIQUE,
    descricao TEXT,
    codigo VARCHAR(20) UNIQUE,
    nivel VARCHAR(20),
    serie VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_componentes_nome ON componentes_curriculares(nome);

-- Para bancos ja existentes (nao-destrutivo).
ALTER TABLE componentes_curriculares ADD COLUMN IF NOT EXISTS nivel VARCHAR(20);
ALTER TABLE componentes_curriculares ADD COLUMN IF NOT EXISTS serie VARCHAR(20);