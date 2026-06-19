"""
US11 — Endpoints de geração automática e gerenciamento de modelos de questão
"""
from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app import models, schemas
from app.dependencies import get_usuario_admin
from app.services import geracao_service

router = APIRouter(prefix="/geracao", tags=["Geração Automática"])


# Geração para uma prova específica

@router.post(
    "/provas/{prova_id}/questoes",
    response_model=schemas.GerarQuestoesResponse,
    status_code=201,
    summary="Gera questões automaticamente para uma prova (US11)",
)
def gerar_questoes(
    prova_id : int,
    dados    : schemas.GerarQuestoesRequest,
    db       : Session = Depends(get_db),
    admin    : models.Usuario = Depends(get_usuario_admin),
):
    """
    Gera `quantidade` questões a partir do banco de modelos, aplicando templates
    com variáveis para criar enunciados únicos. A prova deve estar em RASCUNHO.

    Filtros opcionais:
    - **nivel**: herda da prova se não informado
    - **dificuldade**: FACIL | MEDIO | DIFICIL
    - **componente_id**: filtra por componente curricular
    """
    return geracao_service.gerar_questoes_para_prova(
        prova_id     = prova_id,
        quantidade   = dados.quantidade,
        db           = db,
        nivel        = dados.nivel,
        dificuldade  = dados.dificuldade,
        componente_id= dados.componente_id,
    )


# CRUD de modelos de questão

@router.post(
    "/modelos",
    response_model=schemas.ModeloQuestaoResponse,
    status_code=201,
    summary="Cadastra um modelo de questão",
)
def criar_modelo(
    dados : schemas.ModeloQuestaoCreate,
    db    : Session = Depends(get_db),
    admin : models.Usuario = Depends(get_usuario_admin),
):
    return geracao_service.criar_modelo(dados, db)


@router.get(
    "/modelos",
    response_model=List[schemas.ModeloQuestaoResponse],
    summary="Lista modelos de questão com filtros opcionais",
)
def listar_modelos(
    nivel         : Optional[str] = Query(None),
    dificuldade   : Optional[str] = Query(None),
    componente_id : Optional[int] = Query(None),
    db            : Session = Depends(get_db),
    admin         : models.Usuario = Depends(get_usuario_admin),
):
    return geracao_service.listar_modelos(db, nivel, dificuldade, componente_id)


@router.delete(
    "/modelos/{modelo_id}",
    status_code=204,
    summary="Remove um modelo de questão",
)
def deletar_modelo(
    modelo_id : int,
    db        : Session = Depends(get_db),
    admin     : models.Usuario = Depends(get_usuario_admin),
):
    geracao_service.deletar_modelo(modelo_id, db)

@router.post(
    "/modelos/{modelo_id}/imagem",
    summary="Faz upload de imagem para um modelo de questão",
)
def upload_imagem_modelo(
    modelo_id: int,
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    url = geracao_service.fazer_upload_imagem_modelo(modelo_id, arquivo, db)
    return {"modelo_id": modelo_id, "imagem_url": url}