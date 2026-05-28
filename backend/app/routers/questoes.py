from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas
from app.dependencies import get_usuario_admin

router = APIRouter(prefix="/questoes", tags=["Questões"])

# CRIAR QUESTÃO
@router.post("/", response_model=schemas.QuestaoResponse, status_code=status.HTTP_201_CREATED)
def criar_questao(
    dados: schemas.QuestaoCreate,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    # Validar se a prova existe
    prova = db.query(models.Prova).filter(models.Prova.id == dados.prova_id).first()
    if not prova:
        raise HTTPException(status_code=404, detail="Prova não encontrada")

    # Criar a questão
    nova_questao = models.Questao(
        enunciado=dados.enunciado,
        prova_id=dados.prova_id,
        nivel_dificuldade=dados.nivel_dificuldade,
    )
    db.add(nova_questao)
    db.flush()  # para obter o id

    # Criar as alternativas
    for idx, alt in enumerate(dados.alternativas):
        nova_alt = models.Alternativa(
            texto=alt.texto,
            questao_id=nova_questao.id,
            is_correta=alt.is_correta,
            ordem=alt.ordem if alt.ordem is not None else idx,
        )
        db.add(nova_alt)

    db.commit()
    db.refresh(nova_questao)

    # Retornar questão com alternativas
    return nova_questao


# LISTAR QUESTÕES
@router.get("/", response_model=List[schemas.QuestaoResponse])
def listar_questoes(
    prova_id: int = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Questao)
    if prova_id:
        query = query.filter(models.Questao.prova_id == prova_id)
    questoes = query.order_by(models.Questao.ordem).all()
    return questoes


# EDITAR QUESTÃO
@router.put("/{questao_id}", response_model=schemas.QuestaoResponse)
def editar_questao(
    questao_id: int,
    dados: schemas.QuestaoCreate,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    questao = db.query(models.Questao).filter(models.Questao.id == questao_id).first()
    if not questao:
        raise HTTPException(status_code=404, detail="Questão não encontrada")

    # Atualiza dados da questão
    questao.enunciado = dados.enunciado
    questao.nivel_dificuldade = dados.nivel_dificuldade

    # Remove alternativas antigas e adiciona novas
    db.query(models.Alternativa).filter(models.Alternativa.questao_id == questao_id).delete()
    for idx, alt in enumerate(dados.alternativas):
        nova_alt = models.Alternativa(
            texto=alt.texto,
            questao_id=questao.id,
            is_correta=alt.is_correta,
            ordem=alt.ordem if alt.ordem is not None else idx,
        )
        db.add(nova_alt)

    db.commit()
    db.refresh(questao)
    return questao


@router.delete("/{questao_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_questao(
    questao_id: int,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    questao = db.query(models.Questao).filter(models.Questao.id == questao_id).first()
    if not questao:
        raise HTTPException(status_code=404, detail="Questão não encontrada")

    db.delete(questao)
    db.commit()

# LISTAR ALTERNATIVAS DE UMA QUESTÃO
@router.get("/{questao_id}/alternativas", response_model=List[schemas.AlternativaResponse])
def listar_alternativas(
    questao_id: int,
    db: Session = Depends(get_db),
):
    alternativas = db.query(models.Alternativa).filter(
        models.Alternativa.questao_id == questao_id
    ).order_by(models.Alternativa.ordem).all()
    if not alternativas:
        raise HTTPException(status_code=404, detail="Questão não encontrada ou não possui alternativas")
    return alternativas
