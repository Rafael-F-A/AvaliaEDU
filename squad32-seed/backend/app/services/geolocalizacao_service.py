from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException
from app import schemas


def criar_local(dados: schemas.LocalCreate, db: Session):
    sql = text("""
        INSERT INTO locais (nome, endereco, cidade, estado, cep, contato, capacidade,
                            vagas_restantes, geolocalizacao)
        VALUES (
            :nome, :endereco, :cidade, :estado, :cep, :contato, :capacidade,
            :vagas_restantes,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
        )
        RETURNING
            id, nome, endereco, cidade, estado, cep, contato, capacidade, vagas_restantes,
            ST_Y(geolocalizacao::geometry) AS latitude,
            ST_X(geolocalizacao::geometry) AS longitude,
            created_at
    """)
    row = db.execute(sql, {
        "nome":            dados.nome,
        "endereco":        dados.endereco,
        "cidade":          dados.cidade,
        "estado":          dados.estado,
        "cep":             dados.cep,
        "contato":         dados.contato,
        "capacidade":      dados.capacidade,
        "vagas_restantes": dados.vagas_restantes,
        "lat":             dados.latitude,
        "lon":             dados.longitude,
    })
    db.commit()
    return dict(row.mappings().fetchone())


def listar_locais(db: Session, cidade: str = None):
    filtro = "AND cidade = :cidade" if cidade else ""
    sql = text(f"""
        SELECT
            id, nome, endereco, cidade, estado, cep, contato, capacidade, vagas_restantes,
            ST_Y(geolocalizacao::geometry) AS latitude,
            ST_X(geolocalizacao::geometry) AS longitude,
            created_at
        FROM locais
        WHERE ativo = TRUE {filtro}
        ORDER BY nome
    """)
    params = {"cidade": cidade} if cidade else {}
    rows = db.execute(sql, params)
    return [dict(r) for r in rows.mappings().all()]


def locais_proximos(latitude: float, longitude: float, raio_km: float, limite: int, db: Session):
    sql = text("""
        SELECT
            id, nome, cidade, estado,
            ST_Y(geolocalizacao::geometry) AS latitude,
            ST_X(geolocalizacao::geometry) AS longitude,
            ROUND(
                ST_DistanceSphere(geolocalizacao, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))::numeric, 0
            ) AS distancia_metros
        FROM locais
        WHERE
            ativo = TRUE
            AND geolocalizacao IS NOT NULL
            AND ST_DWithin(
                geolocalizacao::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                :raio
            )
        ORDER BY distancia_metros
        LIMIT :limite
    """)
    rows = db.execute(sql, {
        "lat":    latitude,
        "lon":    longitude,
        "raio":   raio_km * 1000,
        "limite": limite,
    })
    return [dict(r) for r in rows.mappings().all()]


def buscar_local(local_id: int, db: Session):
    sql = text("""
        SELECT
            id, nome, endereco, cidade, estado, cep, contato, capacidade, vagas_restantes,
            ST_Y(geolocalizacao::geometry) AS latitude,
            ST_X(geolocalizacao::geometry) AS longitude,
            created_at
        FROM locais
        WHERE id = :id AND ativo = TRUE
    """)
    row = db.execute(sql, {"id": local_id}).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Local não encontrado")
    return dict(row)


def editar_local(local_id: int, dados: schemas.LocalCreate, db: Session):
    buscar_local(local_id, db)
    sql = text("""
        UPDATE locais SET
            nome           = :nome,
            endereco       = :endereco,
            cidade         = :cidade,
            estado         = :estado,
            cep            = :cep,
            contato        = :contato,
            capacidade     = :capacidade,
            vagas_restantes = :vagas_restantes,
            geolocalizacao = ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
        WHERE id = :id
        RETURNING
            id, nome, endereco, cidade, estado, cep, contato, capacidade, vagas_restantes,
            ST_Y(geolocalizacao::geometry) AS latitude,
            ST_X(geolocalizacao::geometry) AS longitude,
            created_at
    """)
    row = db.execute(sql, {
        "id":              local_id,
        "nome":            dados.nome,
        "endereco":        dados.endereco,
        "cidade":          dados.cidade,
        "estado":          dados.estado,
        "cep":             dados.cep,
        "contato":         dados.contato,
        "capacidade":      dados.capacidade,
        "vagas_restantes": dados.vagas_restantes,
        "lat":             dados.latitude,
        "lon":             dados.longitude,
    })
    db.commit()
    return dict(row.mappings().fetchone())


def excluir_local(local_id: int, db: Session):
    buscar_local(local_id, db)
    sql = text("UPDATE locais SET ativo = FALSE WHERE id = :id")
    db.execute(sql, {"id": local_id})
    db.commit()