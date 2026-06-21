"""
Router de inscrições — US44.

Endpoints:
  POST   /inscricoes/provas/{prova_id}  — Inscrever-se em uma prova
  DELETE /inscricoes/provas/{prova_id}  — Cancelar inscrição
  GET    /inscricoes/minhas             — Listar inscrições ativas do aluno
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas
from app.dependencies import get_usuario_aluno
from app.services import inscricao_service

router = APIRouter(prefix="/inscricoes", tags=["Inscrições"])


@router.post(
    "/provas/{prova_id}",
    response_model=schemas.InscricaoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Inscrever-se em uma prova — US44",
)
def inscrever_em_prova(
    prova_id: int,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_aluno),
):
    """
    Registra a inscrição do aluno na prova.

    **Validações:**
    - Prova deve estar publicada e dentro do período de inscrições.
    - Nível do aluno deve ser compatível com o nível da prova.
    - Aluno não pode se inscrever duas vezes nem se já realizou a prova.

    **Retorna:** tentativa criada com status `INSCRITO`.
    """
    return inscricao_service.inscrever(prova_id, aluno, db)


@router.delete(
    "/provas/{prova_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancelar inscrição em uma prova — US44",
)
def cancelar_inscricao(
    prova_id: int,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_aluno),
):
    """
    Cancela a inscrição do aluno (status `INSCRITO → CANCELADA`).

    Só é possível cancelar se a prova ainda não foi iniciada.
    """
    inscricao_service.cancelar(prova_id, aluno, db)


@router.get(
    "/minhas",
    response_model=List[schemas.InscricaoResponse],
    summary="Listar minhas inscrições ativas — US44",
)
def minhas_inscricoes(
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_aluno),
):
    """
    Retorna todas as inscrições com status `INSCRITO` do aluno autenticado.
    Usado pelo frontend para exibir o botão correto (Inscrito/Iniciar vs Inscrever-se).
    """
    return inscricao_service.minhas_inscricoes(aluno, db)
