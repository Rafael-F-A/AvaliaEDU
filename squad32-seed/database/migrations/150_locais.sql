CREATE TABLE IF NOT EXISTS locais (

    id SERIAL PRIMARY KEY,

    nome VARCHAR(100) NOT NULL,
    endereco TEXT NOT NULL,
    cidade VARCHAR(100) NOT NULL,
    estado VARCHAR(2) NOT NULL,
    cep VARCHAR(9),
    contato VARCHAR(255),
    capacidade INTEGER NOT NULL CHECK (capacidade >= 0),

    vagas_restantes INTEGER NOT NULL CHECK (vagas_restantes >= 0), -- CALCULAR NO BACKEND

    geolocalizacao GEOMETRY(Point, 4326) NOT NULL,

    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (nome, endereco)
    
);

CREATE INDEX idx_locais_geolocalizacao
ON locais
USING GIST (geolocalizacao);

CREATE INDEX idx_locais_cidade_estado ON locais (cidade, estado);