CREATE TABLE IF NOT EXISTS certificados (
    id SERIAL PRIMARY KEY,
    tentativa_id INTEGER NOT NULL UNIQUE REFERENCES tentativas(id) ON DELETE CASCADE,
    aluno_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    prova_id INTEGER NOT NULL REFERENCES provas(id) ON DELETE CASCADE,
    codigo_validacao VARCHAR(50) UNIQUE NOT NULL,
    url_pdf VARCHAR(500),
    data_emissao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_certificados_codigo ON certificados(codigo_validacao);
CREATE INDEX idx_certificados_aluno_id ON certificados(aluno_id);

-- Para bancos ja existentes (nao-destrutivo). Coluna nullable com default TRUE,
-- conforme o banco real.
ALTER TABLE certificados ADD COLUMN IF NOT EXISTS ativo BOOLEAN DEFAULT TRUE;