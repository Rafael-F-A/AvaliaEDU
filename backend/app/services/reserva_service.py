from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from app import models, schemas

HORAS_EXPIRACAO_RESERVA = 48


def _data_aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _serializar_reserva(r: models.Reserva) -> dict:
    return {
        "id": r.id,
        "local_id": r.local_id,
        "prova_id": r.prova_id,
        "status": r.status,
        "data_reserva": r.data_reserva,
        "data_expiracao": r.data_expiracao,
        "necessidades_especiais": r.necessidades_especiais,
        "local": r.local,
        "prova_titulo": r.prova.titulo if r.prova else None,
    }


def _serializar_reserva_admin(r: models.Reserva) -> dict:
    return {
        "id": r.id,
        "status": r.status,
        "data_reserva": r.data_reserva,
        "data_expiracao": r.data_expiracao,
        "necessidades_especiais": r.necessidades_especiais,
        "aluno": r.aluno,
        "local": r.local,
        "prova_titulo": r.prova.titulo if r.prova else None,
    }

# Criar reserva

def criar_reserva(
    dados: schemas.ReservaCreate,
    aluno: models.Usuario,
    db: Session,
) -> dict:
    # 1. Prova existe, publicada e não excluída?
    prova = db.query(models.Prova).filter(
        models.Prova.id == dados.prova_id,
        models.Prova.deleted == False,
        models.Prova.status == "PUBLICADA",
    ).first()

    if not prova:
        raise HTTPException(
            status_code=404,
            detail="Prova não encontrada ou não publicada.",
        )

    # 2. Local existe?
    #    Trava a linha do local (SELECT ... FOR UPDATE) dentro da mesma
    #    transação ANTES de checar duplicata/vagas e criar a reserva, para
    #    evitar race condition (read-check-then-write) em reservas concorrentes.
    local = db.query(models.Local).filter(
        models.Local.id == dados.local_id,
    ).with_for_update().first()

    if not local:
        raise HTTPException(status_code=404, detail="Local não encontrado.")

    # 3. Reserva duplicada — mesmo aluno + mesma prova com status ATIVA?
    #    Checada sob o lock do local para serializar com reservas concorrentes.
    reserva_existente = db.query(models.Reserva).filter(
        models.Reserva.aluno_id == aluno.id,
        models.Reserva.prova_id == dados.prova_id,
        models.Reserva.status == "ATIVA",
    ).first()

    if reserva_existente:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Você já possui uma reserva ativa para esta prova "
                f"(reserva_id={reserva_existente.id}, local='{reserva_existente.local.nome}'). "
                "Cancele-a antes de criar outra."
            ),
        )

    # 4. Local tem vaga?
    if local.vagas_restantes <= 0:
        raise HTTPException(
            status_code=409,
            detail=f"O local '{local.nome}' não possui mais vagas disponíveis.",
        )

    # Cria a reserva
    agora = datetime.now(timezone.utc)
    expiracao = agora + timedelta(hours=HORAS_EXPIRACAO_RESERVA)

    reserva = models.Reserva(
        aluno_id=aluno.id,
        local_id=local.id,
        prova_id=prova.id,
        data_reserva=agora,
        data_expiracao=expiracao,
        status="ATIVA",
        necessidades_especiais=dados.necessidades_especiais,
    )
    db.add(reserva)

    # Decrementa vaga
    local.vagas_restantes -= 1

    # Em caso de violação concorrente (ex.: índice único de reserva ativa),
    # desfaz a transação e responde 409 em vez de 500.
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Conflito ao criar a reserva. Tente novamente.",
        )
    db.refresh(reserva)

    return _serializar_reserva(reserva)

# Listar minhas reservas

def listar_minhas_reservas(aluno: models.Usuario, db: Session) -> list:
    reservas = (
        db.query(models.Reserva)
        .options(joinedload(models.Reserva.local), joinedload(models.Reserva.prova))
        .filter(models.Reserva.aluno_id == aluno.id)
        .order_by(models.Reserva.created_at.desc())
        .all()
    )

    # Atualiza status de reservas expiradas (lazy-check)
    agora = datetime.now(timezone.utc)
    mudou = False
    for r in reservas:
        if r.status == "ATIVA" and r.data_expiracao and _data_aware(r.data_expiracao) < agora:
            r.status = "EXPIRADA"
            # devolve a vaga sem ultrapassar a capacidade do local
            r.local.vagas_restantes = min(
                r.local.capacidade, r.local.vagas_restantes + 1
            )
            mudou = True
    if mudou:
        db.commit()

    return [_serializar_reserva(r) for r in reservas]

# Buscar reserva por ID

def buscar_reserva(reserva_id: int, aluno: models.Usuario, db: Session) -> dict:
    reserva = (
        db.query(models.Reserva)
        .options(joinedload(models.Reserva.local), joinedload(models.Reserva.prova))
        .filter(models.Reserva.id == reserva_id)
        .first()
    )

    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva não encontrada.")

    if reserva.aluno_id != aluno.id:
        raise HTTPException(status_code=403, detail="Esta reserva não pertence a você.")

    return _serializar_reserva(reserva)

# Cancelar reserva

def cancelar_reserva(reserva_id: int, aluno: models.Usuario, db: Session) -> dict:
    reserva = db.query(models.Reserva).filter(
        models.Reserva.id == reserva_id,
    ).first()

    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva não encontrada.")

    if reserva.aluno_id != aluno.id:
        raise HTTPException(status_code=403, detail="Esta reserva não pertence a você.")

    if reserva.status != "ATIVA":
        raise HTTPException(
            status_code=409,
            detail=f"Apenas reservas ATIVAS podem ser canceladas. Status atual: {reserva.status}.",
        )

    reserva.status = "CANCELADA"

    # Devolve a vaga ao local, sem ultrapassar a capacidade
    local = db.query(models.Local).filter(models.Local.id == reserva.local_id).first()
    if local:
        local.vagas_restantes = min(local.capacidade, local.vagas_restantes + 1)

    db.commit()

    return {"message": "Reserva cancelada com sucesso. A vaga foi liberada."}

# Admin — listar todas as reservas (com filtros opcionais)

def listar_todas_admin(
    db: Session,
    prova_id: int | None = None,
    local_id: int | None = None,
    status_filtro: str | None = None,
) -> list:
    query = db.query(models.Reserva).options(
        joinedload(models.Reserva.local),
        joinedload(models.Reserva.prova),
        joinedload(models.Reserva.aluno),
    )

    if prova_id:
        query = query.filter(models.Reserva.prova_id == prova_id)
    if local_id:
        query = query.filter(models.Reserva.local_id == local_id)
    if status_filtro:
        query = query.filter(models.Reserva.status == status_filtro.upper())

    reservas = query.order_by(models.Reserva.created_at.desc()).all()
    return [_serializar_reserva_admin(r) for r in reservas]