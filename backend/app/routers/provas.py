from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app import models, schemas
from app.dependencies import get_usuario_atual, get_usuario_admin
from app.services import prova_service

router = APIRouter(prefix="/provas", tags=["Provas"])


# US14 — Endpoint dedicado para o aluno

@router.get(
    "/disponiveis",
    response_model=schemas.ProvasDisponivelListResponse,
    summary="Lista provas disponíveis para o aluno (US14)",
)
def listar_provas_disponiveis(
    nivel: Optional[str] = Query(None, description="Sobrescreve o nível do perfil"),
    tipo: Optional[str] = Query(None, description="SIMULADO | CERTIFICACAO"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual),
):
    return prova_service.listar_provas_aluno(
        db=db, aluno=aluno, nivel=nivel, tipo=tipo, skip=skip, limit=limit,
    )

@router.post("/", response_model=schemas.ProvaResponse, status_code=201)
def criar_prova(
    dados: schemas.ProvaCreate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_admin),
):
    return prova_service.criar_prova(dados, criado_por=usuario.id, db=db)

@router.get(
    "/",
    response_model=schemas.ProvasListResponse,
    summary="Lista todas as provas com paginação (US06)",
)
def listar_provas(
    nivel: Optional[str] = Query(None),
    serie: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="Filtra por status (ex.: PUBLICADA)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_atual),
):
    """
    Retorna lista paginada de provas com total, skip e limit.
    Admin vê todas (incluindo rascunhos). Aluno vê apenas publicadas.
    """
    return prova_service.listar_provas(db, usuario, nivel, serie, tipo, skip, limit, status)


@router.get("/{prova_id}", response_model=schemas.ProvaResponse)
def buscar_prova(
    prova_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_atual),
):
    return prova_service.buscar_prova_por_id(prova_id, usuario, db)


@router.put("/{prova_id}", response_model=schemas.ProvaResponse)
def editar_prova(
    prova_id: int,
    dados: schemas.ProvaUpdate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_admin),
):
    return prova_service.editar_prova(prova_id, dados, db)


@router.patch("/{prova_id}/publicar", response_model=schemas.ProvaResponse)
def publicar_prova(
    prova_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_admin),
):
    """Publica uma prova (RASCUNHO → PUBLICADA). Exige ao menos 1 questão."""
    return prova_service.publicar_prova(prova_id, db)


@router.delete("/{prova_id}", response_model=schemas.MensagemResponse)
def deletar_prova(
    prova_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_admin),
):
    prova_service.deletar_prova(prova_id, db)
    return {"message": "Prova deletada com sucesso."}