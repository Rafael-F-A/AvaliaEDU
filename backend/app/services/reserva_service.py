from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from app import models, schemas

HORAS_EXPIRACAO_RESERVA = 48

# Status aceitos pelo CHECK do banco (reservas.status).
STATUS_VALIDOS = ("ATIVA", "CANCELADA", "EXPIRADA", "CONFIRMADA")
# Status que efetivamente ocupam (seguram) uma vaga no local.
STATUS_OCUPA_VAGA = ("ATIVA", "CONFIRMADA")


def _ocupa_vaga(status: str) -> bool:
    return status in STATUS_OCUPA_VAGA


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
        "aluno_id": r.aluno_id,
        "prova_id": r.prova_id,
        "local_id": r.local_id,
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
    # Trava a reserva para serializar com cancelamentos concorrentes (evita
    # duplo-refund de vaga em double-submit).
    reserva = db.query(models.Reserva).filter(
        models.Reserva.id == reserva_id,
    ).with_for_update().first()

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

# Admin — cancelar qualquer reserva

def cancelar_reserva_admin(reserva_id: int, db: Session) -> dict:
    """Cancela qualquer reserva (sem checagem de dono) e devolve a vaga se ocupada."""
    # Trava a reserva para serializar com cancelamentos/edições concorrentes
    # (evita duplo-refund de vaga).
    reserva = db.query(models.Reserva).filter(
        models.Reserva.id == reserva_id,
    ).with_for_update().first()

    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva não encontrada.")

    if reserva.status == "CANCELADA":
        raise HTTPException(status_code=409, detail="Esta reserva já está cancelada.")

    devolver = _ocupa_vaga(reserva.status)
    reserva.status = "CANCELADA"

    if devolver:
        local = db.query(models.Local).filter(
            models.Local.id == reserva.local_id
        ).with_for_update().first()
        if local:
            local.vagas_restantes = min(local.capacidade, local.vagas_restantes + 1)

    db.commit()
    return {"message": "Reserva cancelada pelo administrador. A vaga foi liberada."}

# Admin — criar reserva em nome de um aluno

def criar_reserva_admin(dados: schemas.ReservaAdminCreate, db: Session) -> dict:
    status = (dados.status or "ATIVA").upper()
    if status not in STATUS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Status inválido. Use um de: {', '.join(STATUS_VALIDOS)}.",
        )

    aluno = db.query(models.Usuario).filter(
        models.Usuario.id == dados.aluno_id,
        models.Usuario.perfil == "ALUNO",
    ).first()
    if not aluno:
        raise HTTPException(status_code=404, detail="Aluno não encontrado.")

    prova = db.query(models.Prova).filter(
        models.Prova.id == dados.prova_id,
        models.Prova.deleted == False,
    ).first()
    if not prova:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")
    if prova.status != "PUBLICADA" and not dados.forcar:
        raise HTTPException(
            status_code=409,
            detail="A prova não está publicada. Marque 'Forçar' para reservar mesmo assim.",
        )

    # Trava a linha do local antes de checar vagas/duplicidade (anti-race).
    local = db.query(models.Local).filter(
        models.Local.id == dados.local_id,
    ).with_for_update().first()
    if not local:
        raise HTTPException(status_code=404, detail="Local não encontrado.")

    # Reserva duplicada (mesmo aluno + prova com status ATIVA). Regra sempre
    # aplicada (índice parcial do banco a garante); 'forcar' não a burla.
    if status == "ATIVA":
        dup = db.query(models.Reserva).filter(
            models.Reserva.aluno_id == aluno.id,
            models.Reserva.prova_id == prova.id,
            models.Reserva.status == "ATIVA",
        ).first()
        if dup:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"O aluno já possui uma reserva ATIVA para esta prova "
                    f"(reserva_id={dup.id}). Cancele-a antes de criar outra."
                ),
            )

    ocupa = _ocupa_vaga(status)
    if ocupa and local.vagas_restantes <= 0 and not dados.forcar:
        raise HTTPException(
            status_code=409,
            detail=(
                f"O local '{local.nome}' não possui mais vagas. "
                "Marque 'Forçar' para reservar assim mesmo."
            ),
        )

    agora = datetime.now(timezone.utc)
    reserva = models.Reserva(
        aluno_id=aluno.id,
        local_id=local.id,
        prova_id=prova.id,
        data_reserva=dados.data_reserva or agora,
        data_expiracao=dados.data_expiracao or (agora + timedelta(hours=HORAS_EXPIRACAO_RESERVA)),
        status=status,
        necessidades_especiais=dados.necessidades_especiais,
    )
    db.add(reserva)
    if ocupa:
        local.vagas_restantes = max(0, local.vagas_restantes - 1)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Conflito: o aluno já possui uma reserva ATIVA para esta prova "
                "(é permitida apenas uma reserva ativa por prova)."
            ),
        )
    db.refresh(reserva)
    return _serializar_reserva_admin(reserva)

# Admin — editar reserva (datas, status, local, prova, necessidades)

def editar_reserva_admin(
    reserva_id: int,
    dados: schemas.ReservaAdminUpdate,
    db: Session,
) -> dict:
    # Trava a reserva primeiro (antes dos locais) para serializar edições
    # concorrentes na mesma reserva e evitar ajuste de vaga em dobro.
    reserva = db.query(models.Reserva).filter(
        models.Reserva.id == reserva_id,
    ).with_for_update().first()
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva não encontrada.")

    old_status = reserva.status
    old_local_id = reserva.local_id
    old_prova_id = reserva.prova_id

    new_status = (dados.status or old_status).upper()
    if new_status not in STATUS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Status inválido. Use um de: {', '.join(STATUS_VALIDOS)}.",
        )

    new_local_id = dados.local_id if dados.local_id is not None else old_local_id
    new_prova_id = dados.prova_id if dados.prova_id is not None else old_prova_id

    # Valida a prova nova (se mudou).
    if new_prova_id != old_prova_id:
        prova = db.query(models.Prova).filter(
            models.Prova.id == new_prova_id,
            models.Prova.deleted == False,
        ).first()
        if not prova:
            raise HTTPException(status_code=404, detail="Prova não encontrada.")
        if prova.status != "PUBLICADA" and not dados.forcar:
            raise HTTPException(
                status_code=409,
                detail="A prova selecionada não está publicada. Marque 'Forçar' para usá-la.",
            )

    # Trava os locais afetados (ordenados por id p/ evitar deadlock).
    ids_locais = sorted({old_local_id, new_local_id})
    locais = {
        l.id: l
        for l in db.query(models.Local)
        .filter(models.Local.id.in_(ids_locais))
        .with_for_update()
        .all()
    }
    new_local = locais.get(new_local_id)
    if new_local is None:
        raise HTTPException(status_code=404, detail="Local não encontrado.")
    old_local = locais.get(old_local_id)

    # Duplicidade ao (re)ativar. A regra "1 reserva ATIVA por prova" é sempre
    # aplicada (o índice parcial do banco a garante), então 'forcar' não a burla.
    if new_status == "ATIVA":
        dup = db.query(models.Reserva).filter(
            models.Reserva.aluno_id == reserva.aluno_id,
            models.Reserva.prova_id == new_prova_id,
            models.Reserva.status == "ATIVA",
            models.Reserva.id != reserva.id,
        ).first()
        if dup:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"O aluno já possui outra reserva ATIVA para esta prova "
                    f"(reserva_id={dup.id}). Cancele-a antes de ativar esta."
                ),
            )

    # Contabilidade de vaga por delta líquido por local:
    #  +1 onde a reserva deixa de ocupar; -1 onde passa a ocupar.
    held_before = _ocupa_vaga(old_status)
    held_after = _ocupa_vaga(new_status)
    delta: dict[int, int] = {}
    if held_before:
        delta[old_local_id] = delta.get(old_local_id, 0) + 1
    if held_after:
        delta[new_local_id] = delta.get(new_local_id, 0) - 1

    # Checa vaga apenas onde há consumo líquido (antes de qualquer mutação).
    for lid, d in delta.items():
        loc = locais.get(lid)
        if loc is None:
            continue  # local antigo pode ter sido removido; nada a checar/ajustar
        if d < 0 and loc.vagas_restantes < -d and not dados.forcar:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"O local '{loc.nome}' não possui vaga disponível. "
                    "Marque 'Forçar' para mover assim mesmo."
                ),
            )

    # Aplica os deltas (clamp entre 0 e a capacidade).
    for lid, d in delta.items():
        if d == 0:
            continue
        loc = locais.get(lid)
        if loc is None:
            continue  # local antigo inexistente: não há vaga para devolver
        loc.vagas_restantes = max(0, min(loc.capacidade, loc.vagas_restantes + d))

    # Aplica as alterações de campo.
    reserva.status = new_status
    reserva.local_id = new_local_id
    reserva.prova_id = new_prova_id
    if dados.data_reserva is not None:
        reserva.data_reserva = dados.data_reserva
    if dados.data_expiracao is not None:
        reserva.data_expiracao = dados.data_expiracao
    if dados.necessidades_especiais is not None:
        reserva.necessidades_especiais = dados.necessidades_especiais

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Conflito: já existe uma reserva ATIVA deste aluno para esta prova "
                "(é permitida apenas uma reserva ativa por prova)."
            ),
        )
    db.refresh(reserva)
    return _serializar_reserva_admin(reserva)