-- Tabela usuarios
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    senha_hash VARCHAR(255) NOT NULL,
    perfil VARCHAR(50) NOT NULL,
    nivel VARCHAR(50),
    serie VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela provas
CREATE TABLE IF NOT EXISTS provas (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(255) NOT NULL,
    descricao TEXT,
    nivel VARCHAR(50) NOT NULL,
    serie VARCHAR(50) NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'RASCUNHO',
    nota_minima FLOAT DEFAULT 6.0,
    tempo_limite INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela questoes
CREATE TABLE IF NOT EXISTS questoes (
    id SERIAL PRIMARY KEY,
    enunciado TEXT NOT NULL,
    prova_id INTEGER NOT NULL REFERENCES provas(id) ON DELETE CASCADE,
    nivel_dificuldade VARCHAR(50) DEFAULT 'MEDIO',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);