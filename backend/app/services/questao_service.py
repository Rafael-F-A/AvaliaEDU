from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app import models, schemas


def _validar_alternativas(alternativas: list) -> None:
    """
    Regras de negócio da US10 (centralizadas aqui para reuso):
    - Mínimo 2 alternativas
    - Exatamente 1 correta
    - Nenhuma com texto vazio
    """
    if len(alternativas) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A questão deve ter no mínimo 2 alternativas.",
        )

    textos_vazios = [a for a in alternativas if not a.texto or not a.texto.strip()]
    if textos_vazios:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nenhuma alternativa pode ter texto vazio.",
        )

    total_corretas = sum(1 for a in alternativas if a.is_correta)
    if total_corretas == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A questão deve ter exatamente 1 alternativa correta. Nenhuma foi marcada.",
        )
    if total_corretas > 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"A questão deve ter exatamente 1 alternativa correta. {total_corretas} foram marcadas.",
        )


def criar_questao(dados: schemas.QuestaoCreate, db: Session) -> models.Questao:
    """
    Cria uma questão com suas alternativas.
    Valida regras de negócio antes de persistir.
    """
    _validar_alternativas(dados.alternativas)

    prova = db.query(models.Prova).filter(models.Prova.id == dados.prova_id).first()
    if not prova:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prova não encontrada.")

    nova_questao = models.Questao(
        enunciado=dados.enunciado,
        prova_id=dados.prova_id,
        nivel_dificuldade=dados.nivel_dificuldade,
    )
    db.add(nova_questao)
    db.flush()

    for idx, alt in enumerate(dados.alternativas):
        db.add(models.Alternativa(
            texto=alt.texto.strip(),
            questao_id=nova_questao.id,
            is_correta=alt.is_correta,
            ordem=alt.ordem if alt.ordem is not None else idx,
        ))

    db.commit()
    db.refresh(nova_questao)
    return nova_questao


def listar_questoes(db: Session, prova_id: Optional[int] = None) -> list:
    """
    Lista questões, com filtro opcional por prova.
    """
    query = db.query(models.Questao)
    if prova_id:
        query = query.filter(models.Questao.prova_id == prova_id)
    return query.order_by(models.Questao.ordem).all()


def editar_questao(questao_id: int, dados: schemas.QuestaoCreate, db: Session) -> models.Questao:
    """
    Atualiza enunciado, nível de dificuldade e alternativas.
    As mesmas validações da criação se aplicam aqui.
    """
    _validar_alternativas(dados.alternativas)

    questao = db.query(models.Questao).filter(models.Questao.id == questao_id).first()
    if not questao:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Questão não encontrada.")

    questao.enunciado = dados.enunciado
    questao.nivel_dificuldade = dados.nivel_dificuldade

    # Remove as alternativas antigas e recria
    db.query(models.Alternativa).filter(
        models.Alternativa.questao_id == questao_id
    ).delete()

    for idx, alt in enumerate(dados.alternativas):
        db.add(models.Alternativa(
            texto=alt.texto.strip(),
            questao_id=questao.id,
            is_correta=alt.is_correta,
            ordem=alt.ordem if alt.ordem is not None else idx,
        ))

    db.commit()
    db.refresh(questao)
    return questao


def excluir_questao(questao_id: int, db: Session) -> None:
    """
    Remove uma questão e suas alternativas (cascade no model).
    """
    questao = db.query(models.Questao).filter(models.Questao.id == questao_id).first()
    if not questao:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Questão não encontrada.")

    db.delete(questao)
    db.commit()


def listar_alternativas(questao_id: int, db: Session) -> list:
    """
    Retorna as alternativas de uma questão ordenadas por 'ordem'.
    """
    questao = db.query(models.Questao).filter(models.Questao.id == questao_id).first()
    if not questao:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Questão não encontrada.")

    return (
        db.query(models.Alternativa)
        .filter(models.Alternativa.questao_id == questao_id)
        .order_by(models.Alternativa.ordem)
        .all()
    )
