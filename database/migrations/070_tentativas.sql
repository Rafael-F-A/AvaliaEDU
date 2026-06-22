CREATE TABLE IF NOT EXISTS tentativas (
    id SERIAL PRIMARY KEY,
    aluno_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    prova_id INTEGER NOT NULL REFERENCES provas(id) ON DELETE CASCADE,
    tipo VARCHAR(15) NOT NULL CHECK (tipo IN ('SIMULADO', 'CERTIFICACAO')),
    status VARCHAR(20) DEFAULT 'INSCRITO' CHECK (status IN ('INSCRITO', 'EM_ANDAMENTO', 'PAUSADO', 'CONCLUIDA', 'CANCELADA')),
    data_inicio TIMESTAMP,
    data_fim TIMESTAMP,
    nota DECIMAL(5,2),
    resultado VARCHAR(20) CHECK (resultado IN ('APROVADO', 'REPROVADO')),
    bloqueio_ate DATE,
    ordem_questoes JSON,
    ordem_alternativas JSON,
    modalidade VARCHAR(15) NOT NULL DEFAULT 'ONLINE' CHECK (modalidade IN ('ONLINE', 'PRESENCIAL')),
    reserva_id INTEGER REFERENCES reservas(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tentativas_aluno_id ON tentativas(aluno_id);
CREATE INDEX IF NOT EXISTS idx_tentativas_prova_id ON tentativas(prova_id);
CREATE INDEX IF NOT EXISTS idx_tentativas_status ON tentativas(status);

-- Para bancos ja existentes (tabela criada antes destas colunas): nao-destrutivo.
ALTER TABLE tentativas ADD COLUMN IF NOT EXISTS ordem_alternativas JSON;
ALTER TABLE tentativas ADD COLUMN IF NOT EXISTS modalidade VARCHAR(15) NOT NULL DEFAULT 'ONLINE';
ALTER TABLE tentativas ADD COLUMN IF NOT EXISTS reserva_id INTEGER;

-- Garante o CHECK de modalidade mesmo em bancos antigos.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'tentativas_modalidade_check'
    ) THEN
        ALTER TABLE tentativas
            ADD CONSTRAINT tentativas_modalidade_check
            CHECK (modalidade IN ('ONLINE', 'PRESENCIAL'));
    END IF;
END$$;

-- FK reserva_id -> reservas (idempotente).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'tentativas_reserva_id_fkey'
    ) THEN
        ALTER TABLE tentativas
            ADD CONSTRAINT tentativas_reserva_id_fkey
            FOREIGN KEY (reserva_id) REFERENCES reservas(id) ON DELETE SET NULL;
    END IF;
END$$;

-- FKs adiadas que apontam para tentativas (alvos criados somente agora).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'respostas_tentativa_id_fkey'
    ) THEN
        ALTER TABLE respostas
            ADD CONSTRAINT respostas_tentativa_id_fkey
            FOREIGN KEY (tentativa_id) REFERENCES tentativas(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'reservas_tentativa_id_fkey'
    ) THEN
        ALTER TABLE reservas
            ADD CONSTRAINT reservas_tentativa_id_fkey
            FOREIGN KEY (tentativa_id) REFERENCES tentativas(id) ON DELETE SET NULL;
    END IF;
END$$;
