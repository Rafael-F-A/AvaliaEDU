CREATE TABLE IF NOT EXISTS provas_componentes (
    prova_id INTEGER NOT NULL REFERENCES provas(id) ON DELETE CASCADE,
    componente_id INTEGER NOT NULL REFERENCES componentes_curriculares(id) ON DELETE CASCADE,
    PRIMARY KEY (prova_id, componente_id)
);

CREATE INDEX idx_provas_componentes_prova_id ON provas_componentes(prova_id);
CREATE INDEX idx_provas_componentes_componente_id ON provas_componentes(componente_id);