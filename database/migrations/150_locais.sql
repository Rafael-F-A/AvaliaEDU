CREATE TABLE IF NOT EXISTS locais (

    id SERIAL PRIMARY KEY,

    nome VARCHAR(100) NOT NULL,
    endereco TEXT NOT NULL,
    cidade VARCHAR(100) NOT NULL,
    estado VARCHAR(2) NOT NULL,
    cep VARCHAR(9) NOT NULL,
    contato VARCHAR(255),
    capacidade INTEGER NOT NULL CHECK (capacidade > 0),

    vagas_restantes INTEGER NOT NULL CHECK (vagas_restantes >= 0), -- CALCULAR NO BACKEND

    geolocalizacao GEOMETRY(Point, 4326),

    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP

);

CREATE INDEX idx_locais_geolocalizacao
ON locais
USING GIST (geolocalizacao);

CREATE INDEX idx_locais_cidade_estado ON locais (cidade, estado);

-- FK adiada: reservas.local_id -> locais (reservas criada em 050, antes desta
-- tabela na ordem de versionamento). Idempotente.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'reservas_local_id_fkey'
    ) THEN
        ALTER TABLE reservas
            ADD CONSTRAINT reservas_local_id_fkey
            FOREIGN KEY (local_id) REFERENCES locais(id) ON DELETE CASCADE;
    END IF;
END$$;
