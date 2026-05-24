CREATE TABLE IF NOT EXISTS resposta_tentativa (
    id SERIAL PRIMARY KEY,

    tentativa_id INTEGER NOT NULL
     REFERENCES tentativa(id) ON DELETE CASCADE,

    questao_id INTEGER NOT NULL
     REFERENCES questoes(id) ON DELETE CASCADE,

    alternativa_escolhida_id INTEGER
     REFERENCES alternativas(id) ON DELETE SET NULL,
     
    is_correta BOOLEAN,

    UNIQUE (tentativa_id, questao_id)
);

CREATE INDEX IF NOT EXISTS idx_resposta_tentativa_id ON resposta_tentativa(tentativa_id);
CREATE INDEX IF NOT EXISTS idx_resposta_questao_id ON resposta_tentativa(questao_id);