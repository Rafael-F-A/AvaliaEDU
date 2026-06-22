-- Respostas do aluno por questao dentro de uma tentativa.
-- UNIQUE(tentativa_id, questao_id): uma unica resposta por questao na tentativa.
-- Obs.: a FK tentativa_id -> tentativas e adicionada via ALTER em 070_tentativas.sql,
-- pois a tabela tentativas e criada depois desta na ordem de versionamento.
CREATE TABLE IF NOT EXISTS respostas (
    id SERIAL PRIMARY KEY,
    tentativa_id INTEGER NOT NULL,
    questao_id INTEGER NOT NULL REFERENCES questoes(id) ON DELETE CASCADE,
    alternativa_id INTEGER REFERENCES alternativas(id) ON DELETE SET NULL,
    is_correta BOOLEAN,
    data_resposta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tentativa_id, questao_id)
);

CREATE INDEX IF NOT EXISTS idx_respostas_tentativa_id ON respostas(tentativa_id);
CREATE INDEX IF NOT EXISTS idx_respostas_questao_id ON respostas(questao_id);
