"""
Serviço de inscrições — US44.

Regras de negócio:
- Aluno pode se inscrever apenas em provas PUBLICADAS dentro do período de inscrição.
- Pré-requisito: nível do aluno deve ser compatível com o nível da prova.
- Duplicata: se já existe inscrição ATIVA (INSCRITO), retorna 409.
- Se já existe tentativa EM_ANDAMENTO ou PAUSADO, retorna 409.
- Se já CONCLUÍDA, retorna 409 (simulado já realizado).
- Cancelar: só cancela inscrição com status INSCRITO (não pode cancelar se já iniciou).
- GET /inscricoes/minhas: lista tentativas com status INSCRITO do aluno.
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

from app import models
from app.enums import StatusTentativa


def _prova_valida_para_inscricao(prova_id: int, db: Session) -> models.Prova:
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.status == "PUBLICADA",
        models.Prova.deleted == False,
    ).first()

    if not prova:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prova não encontrada ou não disponível para inscrição.",
        )
    return prova


def inscrever(prova_id: int, aluno: models.Usuario, db: Session) -> dict:
    """POST /inscricoes/provas/{prova_id} — US44."""
    prova = _prova_valida_para_inscricao(prova_id, db)
    agora = datetime.now(timezone.utc)

    # Verifica período de inscrição (se definido)
    if prova.data_inicio_inscricao:
        inicio = prova.data_inicio_inscricao
        if inicio.tzinfo is None:
            inicio = inicio.replace(tzinfo=timezone.utc)
        if agora < inicio:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"As inscrições para esta prova abrem em {inicio.strftime('%d/%m/%Y %H:%M')} UTC.",
            )

    if prova.data_fim_inscricao:
        fim = prova.data_fim_inscricao
        if fim.tzinfo is None:
            fim = fim.replace(tzinfo=timezone.utc)
        if agora > fim:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="O período de inscrições para esta prova já encerrou.",
            )

    # Verifica compatibilidade de nível (US44 — validar pré-requisitos)
    if not aluno.nivel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configure seu nível de ensino no perfil antes de se inscrever em uma prova.",
        )

    if prova.nivel != aluno.nivel:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Esta prova é para o nível {prova.nivel}. "
                f"Seu perfil está cadastrado como {aluno.nivel}."
            ),
        )

    # Verifica tentativa existente
    tentativa_existente = db.query(models.Tentativa).filter(
        models.Tentativa.aluno_id == aluno.id,
        models.Tentativa.prova_id == prova_id,
        models.Tentativa.status.in_([
            StatusTentativa.INSCRITO.value,
            StatusTentativa.EM_ANDAMENTO.value,
            StatusTentativa.PAUSADO.value,
        ]),
    ).first()

    if tentativa_existente:
        if tentativa_existente.status == StatusTentativa.INSCRITO.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Você já está inscrito nesta prova.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Você já iniciou ou está realizando esta prova.",
        )

    # Verifica se já concluiu esta prova
    concluida = db.query(models.Tentativa).filter(
        models.Tentativa.aluno_id == aluno.id,
        models.Tentativa.prova_id == prova_id,
        models.Tentativa.status == StatusTentativa.CONCLUIDA.value,
    ).first()

    if concluida:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Você já realizou esta prova.",
        )

    # Cria inscrição (Tentativa com status INSCRITO)
    tentativa = models.Tentativa(
        aluno_id=aluno.id,
        prova_id=prova.id,
        tipo=prova.tipo,
        status=StatusTentativa.INSCRITO.value,
    )
    db.add(tentativa)
    db.commit()
    db.refresh(tentativa)

    return {
        "tentativa_id": tentativa.id,
        "prova_id": prova.id,
        "tipo": prova.tipo,
        "status": tentativa.status,
        "prova_titulo": prova.titulo,
        "data_inscricao": tentativa.created_at,
    }


def cancelar(prova_id: int, aluno: models.Usuario, db: Session) -> None:
    """DELETE /inscricoes/provas/{prova_id} — cancela inscrição INSCRITO."""
    tentativa = db.query(models.Tentativa).filter(
        models.Tentativa.aluno_id == aluno.id,
        models.Tentativa.prova_id == prova_id,
        models.Tentativa.status == StatusTentativa.INSCRITO.value,
    ).first()

    if not tentativa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inscrição ativa não encontrada. Só é possível cancelar inscrições com status INSCRITO.",
        )

    tentativa.status = StatusTentativa.CANCELADA.value
    db.commit()


def minhas_inscricoes(aluno: models.Usuario, db: Session) -> list:
    """GET /inscricoes/minhas — lista inscrições ativas do aluno."""
    tentativas = (
        db.query(models.Tentativa)
        .options(joinedload(models.Tentativa.prova))
        .filter(
            models.Tentativa.aluno_id == aluno.id,
            models.Tentativa.status == StatusTentativa.INSCRITO.value,
        )
        .order_by(models.Tentativa.created_at.desc())
        .all()
    )

    return [
        {
            "tentativa_id": t.id,
            "prova_id": t.prova_id,
            "tipo": t.tipo,
            "status": t.status,
            "prova_titulo": t.prova.titulo if t.prova else None,
            "data_inscricao": t.created_at,
        }
        for t in tentativas
    ]
