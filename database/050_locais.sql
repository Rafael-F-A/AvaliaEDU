CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS locais(

    id       SERIAL PRIMARY KEY,
    nome     VARCHAR(100) NOT NULL,
    endereco TEXT NOT NULL,
    municipio   VARCHAR(100), 
    estado   CHAR(2),
    -- capacidade_total INTEGER REFERENCES salas(capacidade) ON DELETE SET NULL,
    criado_em     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    geom     GEOMETRY(Point, 4326) NOT NULL,
)

CREATE INDEX idx_locais_geom ON locais USING GIST (geom);

CREATE INDEX idx_locais_municipio_estado ON locais (municipio, estado);

CREATE TABLE IF NOT EXISTS salas (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    capacidade INTEGER NOT NULL,
    local_id INTEGER NOT NULL REFERENCES locais(id) ON DELETE CASCADE,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
); 