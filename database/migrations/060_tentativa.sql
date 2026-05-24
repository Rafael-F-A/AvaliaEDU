CREATE TABLE IF NOT EXISTS tentativa (
    id SERIAL PRIMARY KEY,
    
    aluno_id INTEGER NOT NULL
     REFERENCES usuarios(id) ON DELETE CASCADE,

    prova_id INTEGER NOT NULL
     REFERENCES provas(id) ON DELETE CASCADE,

    status VARCHAR(20) DEFAULT 'EM_ANDAMENTO'
     CHECK (status IN ('EM_ANDAMENTO', 'FINALIZADA', 'ABANDONADA')),

    nota_final DECIMAL(5,2),
    iniciada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finalizada_em TIMESTAMP,
    tempo_gasto_segundos INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tentativa_aluno_id ON tentativa(aluno_id);
CREATE INDEX IF NOT EXISTS idx_tentativa_prova_id ON tentativa(prova_id);
