from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app import models, schemas
from app.dependencies import get_usuario_admin
from app.services import questao_service

router = APIRouter(prefix="/questoes", tags=["Questões"])


@router.post("/", response_model=schemas.QuestaoResponse, status_code=201)
def criar_questao(
    dados: schemas.QuestaoCreate,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    return questao_service.criar_questao(dados, db)


@router.get("/", response_model=List[schemas.QuestaoResponse])
def listar_questoes(
    prova_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    return questao_service.listar_questoes(db, prova_id)


@router.put("/{questao_id}", response_model=schemas.QuestaoResponse)
def editar_questao(
    questao_id: int,
    dados: schemas.QuestaoCreate,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    return questao_service.editar_questao(questao_id, dados, db)


@router.delete("/{questao_id}", status_code=204)
def excluir_questao(
    questao_id: int,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    questao_service.excluir_questao(questao_id, db)


@router.get(
    "/{questao_id}/alternativas",
    response_model=List[schemas.AlternativaResponse],
)
def listar_alternativas(
    questao_id: int,
    db: Session = Depends(get_db),
):
    return questao_service.listar_alternativas(questao_id, db)


@router.post(
    "/{questao_id}/imagem",
    response_model=schemas.ImagemUploadResponse,
    summary="Faz upload de imagem para o enunciado da questão",
)
def upload_imagem_questao(
    questao_id: int,
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    url = questao_service.fazer_upload_imagem(questao_id, arquivo, db)
    return {"questao_id": questao_id, "imagem_url": url}


@router.post(
    "/{questao_id}/alternativas/{alternativa_id}/imagem",
    response_model=schemas.ImagemAltUploadResponse,
    summary="Faz upload de imagem para uma alternativa específica",
)
def upload_imagem_alternativa(
    questao_id: int,
    alternativa_id: int,
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    url = questao_service.fazer_upload_imagem_alternativa(
        questao_id, alternativa_id, arquivo, db
    )
    return {"alternativa_id": alternativa_id, "imagem_url": url}


@router.delete(
    "/{questao_id}/alternativas/{alternativa_id}/imagem",
    status_code=204,
    summary="Remove a imagem de uma alternativa",
)
def remover_imagem_alternativa(
    questao_id: int,
    alternativa_id: int,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    questao_service.remover_imagem_alternativa(questao_id, alternativa_id, db)

