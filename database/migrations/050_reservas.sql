-- Reservas de local para provas presenciais (modalidade PRESENCIAL).
-- Obs.: as FKs para locais (150) e tentativas (070) sao adicionadas via ALTER
-- nas respectivas migrations, pois essas tabelas sao criadas depois desta na
-- ordem de versionamento. Aqui criamos apenas as FKs cujos alvos ja existem
-- (usuarios e provas) e as colunas local_id / tentativa_id.
CREATE TABLE IF NOT EXISTS reservas (
    id SERIAL PRIMARY KEY,
    aluno_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    local_id INTEGER NOT NULL,
    prova_id INTEGER NOT NULL REFERENCES provas(id) ON DELETE CASCADE,
    data_reserva TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_expiracao TIMESTAMP,
    status VARCHAR(20) DEFAULT 'ATIVA' CHECK (status IN ('ATIVA', 'CANCELADA', 'EXPIRADA', 'CONFIRMADA')),
    necessidades_especiais TEXT,
    tentativa_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reservas_aluno_id ON reservas(aluno_id);
CREATE INDEX IF NOT EXISTS idx_reservas_local_id ON reservas(local_id);
CREATE INDEX IF NOT EXISTS idx_reservas_prova_id ON reservas(prova_id);
CREATE INDEX IF NOT EXISTS idx_reservas_status ON reservas(status);

-- Unicidade da reserva ATIVA por (aluno, prova): impede duas reservas ativas
-- simultaneas para a mesma prova (anti race-condition, auditoria A-03), mas
-- PERMITE re-reservar depois de CANCELADA/EXPIRADA. Um UNIQUE total
-- (aluno_id, prova_id) seria errado: travaria o aluno para sempre apos a 1a
-- reserva, mesmo cancelada.
CREATE UNIQUE INDEX IF NOT EXISTS uq_reservas_aluno_prova_ativa
    ON reservas (aluno_id, prova_id) WHERE status = 'ATIVA';
