from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from datetime import datetime, timezone

from app import models, schemas


def criar_prova(dados: schemas.ProvaCreate, criado_por: int, db: Session) -> models.Prova:
    nova_prova = models.Prova(
        titulo=dados.titulo,
        descricao=dados.descricao,
        nivel=dados.nivel,
        serie=dados.serie,
        tipo=dados.tipo,
        nota_minima=dados.nota_minima,
        tempo_limite=dados.tempo_limite,
        data_inicio=dados.data_inicio,
        data_fim=dados.data_fim,
        data_inicio_inscricao=dados.data_inicio_inscricao,
        data_fim_inscricao=dados.data_fim_inscricao,
        status="RASCUNHO",
        criado_por=criado_por,
    )
    db.add(nova_prova)
    db.commit()
    db.refresh(nova_prova)
    return nova_prova


def listar_provas(
    db: Session,
    usuario: models.Usuario,
    nivel: Optional[str] = None,
    serie: Optional[str] = None,
    tipo: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
) -> dict:
    
    query = db.query(models.Prova).filter(models.Prova.deleted == False)

    if usuario.perfil != "ADMIN":
        query = query.filter(models.Prova.status == "PUBLICADA")
        if usuario.nivel:
            query = query.filter(models.Prova.nivel == usuario.nivel)

    if nivel:
        query = query.filter(models.Prova.nivel == nivel)
    if serie:
        query = query.filter(models.Prova.serie == serie)
    if tipo:
        query = query.filter(models.Prova.tipo == tipo)
    # integration-contract-1: filtro opcional por status (o front envia
    # ?status=PUBLICADA). Para não-admin o status já é forçado a PUBLICADA acima.
    if status:
        query = query.filter(models.Prova.status == status)

    total = query.count()
    provas = (
        query.order_by(models.Prova.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {"total": total, "skip": skip, "limit": limit, "provas": provas}


def listar_provas_aluno(
    db: Session,
    aluno: models.Usuario,
    nivel: Optional[str] = None,
    tipo: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
) -> dict:
    """
    US14 — Provas disponíveis para o aluno.
    """
    agora = datetime.now(timezone.utc)

    tentativas_aluno = (
        db.query(models.Tentativa.prova_id)
        .filter(
            models.Tentativa.aluno_id == aluno.id,
            models.Tentativa.status.in_(["CONCLUIDA", "EM_ANDAMENTO", "PAUSADO"]),
        )
        .subquery()
    )

    query = db.query(models.Prova).filter(
        models.Prova.deleted == False,
        models.Prova.status == "PUBLICADA",
        models.Prova.id.notin_(tentativas_aluno),
    )

    query = query.filter(
        (models.Prova.data_inicio_inscricao == None)
        | (models.Prova.data_inicio_inscricao <= agora)
    )
    query = query.filter(
        (models.Prova.data_fim_inscricao == None)
        | (models.Prova.data_fim_inscricao >= agora)
    )

    nivel_filtro = nivel or aluno.nivel
    if nivel_filtro:
        query = query.filter(models.Prova.nivel == nivel_filtro)

    if tipo:
        query = query.filter(models.Prova.tipo == tipo)

    total = query.count()
    provas = (
        query.order_by(models.Prova.data_fim_inscricao.asc().nullslast())
        .offset(skip)
        .limit(limit)
        .all()
    )

    items = []
    for prova in provas:
        total_questoes = (
            db.query(func.count(models.Questao.id))
            .filter(models.Questao.prova_id == prova.id)
            .scalar()
        )

        dias_restantes = None
        if prova.data_fim_inscricao:
            delta = prova.data_fim_inscricao.replace(tzinfo=timezone.utc) - agora
            dias_restantes = max(0, delta.days)

        items.append(
            schemas.ProvaDisponivelResponse(
                id=prova.id,
                titulo=prova.titulo,
                descricao=prova.descricao,
                nivel=prova.nivel,
                serie=prova.serie,
                tipo=prova.tipo,
                nota_minima=prova.nota_minima,
                tempo_limite=prova.tempo_limite,
                data_inicio=prova.data_inicio,
                data_fim=prova.data_fim,
                data_inicio_inscricao=prova.data_inicio_inscricao,
                data_fim_inscricao=prova.data_fim_inscricao,
                status=prova.status,
                created_at=prova.created_at,
                criado_por=prova.criado_por,
                total_questoes=total_questoes,
                dias_restantes=dias_restantes,
            )
        )

    return {"total": total, "skip": skip, "limit": limit, "provas": items}


def buscar_prova_por_id(prova_id: int, usuario: models.Usuario, db: Session) -> models.Prova:
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.deleted == False,
    ).first()

    if not prova:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Prova não encontrada."
        )

    if usuario.perfil != "ADMIN" and prova.status != "PUBLICADA":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado."
        )

    return prova


def editar_prova(prova_id: int, dados: schemas.ProvaUpdate, db: Session) -> models.Prova:
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.deleted == False,
    ).first()

    if not prova:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Prova não encontrada."
        )

    if prova.status == "PUBLICADA":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Prova publicada não pode ser editada. Altere o status para RASCUNHO primeiro.",
        )

    tentativas_ativas = db.query(models.Tentativa).filter(
        models.Tentativa.prova_id == prova_id,
        models.Tentativa.status == "EM_ANDAMENTO",
    ).first()

    if tentativas_ativas:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não é possível editar uma prova enquanto alunos estão realizando-a.",
        )

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(prova, campo, valor)

    db.commit()
    db.refresh(prova)
    return prova


def deletar_prova(prova_id: int, db: Session) -> None:
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.deleted == False,
    ).first()

    if not prova:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Prova não encontrada."
        )

    tentativas = db.query(models.Tentativa).filter(
        models.Tentativa.prova_id == prova_id
    ).first()

    if tentativas:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não é possível excluir uma prova que já possui tentativas registradas.",
        )

    prova.deleted = True
    db.commit()


def publicar_prova(prova_id: int, db: Session) -> models.Prova:
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.deleted == False,
    ).first()

    if not prova:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Prova não encontrada."
        )

    if prova.status == "PUBLICADA":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Prova já está publicada."
        )

    total_questoes = db.query(models.Questao).filter(
        models.Questao.prova_id == prova_id
    ).count()

    if total_questoes == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Não é possível publicar uma prova sem questões.",
        )

    prova.status = "PUBLICADA"
    db.commit()
    db.refresh(prova)
    return prova


def voltar_para_rascunho(prova_id: int, db: Session) -> models.Prova:
    """Reverte uma prova PUBLICADA para RASCUNHO, liberando a edição de questões.

    Bloqueia se houver alunos com simulado EM_ANDAMENTO/PAUSADO (mesma proteção
    de editar_prova) para não corromper tentativas ativas. Tentativas apenas
    INSCRITO (ex.: PDFs já gerados) ou CONCLUIDA não impedem o retorno."""
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.deleted == False,
    ).first()

    if not prova:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Prova não encontrada."
        )

    if prova.status != "PUBLICADA":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Apenas provas publicadas podem voltar para rascunho.",
        )

    tentativa_ativa = db.query(models.Tentativa).filter(
        models.Tentativa.prova_id == prova_id,
        models.Tentativa.status.in_(["EM_ANDAMENTO", "PAUSADO"]),
    ).first()

    if tentativa_ativa:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Há alunos realizando esta prova; não é possível voltar para rascunho agora.",
        )

    prova.status = "RASCUNHO"
    db.commit()
    db.refresh(prova)
    return prova