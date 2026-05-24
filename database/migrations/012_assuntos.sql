CREATE TABLE IF NOT EXISTS assuntos(
    
    id SERIAL PRIMARY KEY,
    componente_curricular_id INTEGER NOT NULL
     REFERENCES componente_curricular(id) ON DELETE CASCADE, 
    
    nome VARCHAR(100) NOT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_assuntos_componente_curricular ON assuntos (componente_curricular_id);