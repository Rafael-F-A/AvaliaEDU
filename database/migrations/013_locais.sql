CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS locais(

    id       SERIAL PRIMARY KEY,
    nome     VARCHAR(100) NOT NULL,
    endereco TEXT NOT NULL,
    diretoria_regional   VARCHAR(50), 
    municipio  VARCHAR(50) NOT NULL,
    criado_em     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    geom     GEOGRAPHY(Point, 4326) NOT NULL
);

CREATE INDEX idx_locais_geom ON locais USING GIST (geom);

CREATE INDEX idx_locais_municipio_diretoria ON locais (diretoria_regional, municipio);

