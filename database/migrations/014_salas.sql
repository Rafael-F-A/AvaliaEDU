CREATE TABLE IF NOT EXISTS salas (
    id SERIAL PRIMARY KEY,

    local_id INTEGER NOT NULL
     REFERENCES locais(id) ON DELETE CASCADE,

    nome VARCHAR(100) NOT NULL,
    capacidade INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ativo', -- disponível, em_uso, manutenção
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP

); 

CREATE INDEX IF NOT EXISTS idx_salas_local_id ON salas(local_id);