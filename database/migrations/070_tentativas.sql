CREATE TABLE IF NOT EXISTS tentativas (
    id SERIAL PRIMARY KEY,
    aluno_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    prova_id INTEGER NOT NULL REFERENCES provas(id) ON DELETE CASCADE,
    tipo VARCHAR(15) NOT NULL CHECK (tipo IN ('SIMULADO', 'CERTIFICACAO')),
    status VARCHAR(20) DEFAULT 'INSCRITO' CHECK (status IN ('INSCRITO', 'EM_ANDAMENTO', 'CONCLUIDA', 'CANCELADA')),
    data_inicio TIMESTAMP,
    data_fim TIMESTAMP,
    nota DECIMAL(5,2),
    resultado VARCHAR(20) CHECK (resultado IN ('APROVADO', 'REPROVADO')),
    bloqueio_ate DATE,
    ordem_questoes JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tentativas_aluno_id ON tentativas(aluno_id);
CREATE INDEX idx_tentativas_prova_id ON tentativas(prova_id);
CREATE INDEX idx_tentativas_status ON tentativas(status);