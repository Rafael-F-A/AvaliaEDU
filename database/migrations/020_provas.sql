CREATE TABLE IF NOT EXISTS provas (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(255) NOT NULL,
    descricao TEXT,
    nivel VARCHAR(20) NOT NULL,
    serie VARCHAR(20) NOT NULL,
    tipo VARCHAR(15) NOT NULL CHECK (tipo IN ('SIMULADO', 'CERTIFICACAO')),
    status VARCHAR(20) DEFAULT 'RASCUNHO' CHECK (status IN ('RASCUNHO', 'PUBLICADA')),
    nota_minima DECIMAL(5,2) DEFAULT 6.0,
    tempo_limite INTEGER,
    data_inicio DATE,
    data_fim DATE,
    criado_por INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);