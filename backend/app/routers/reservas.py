from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app import models, schemas
from app.dependencies import get_usuario_atual, get_usuario_aluno, get_usuario_admin
from app.services import reserva_service

router = APIRouter(prefix="/reservas", tags=["Reservas (US27)"])


@router.post(
    "/",
    response_model=schemas.ReservaResponse,
    status_code=201,
    summary="Cria uma reserva de vaga em local presencial (US27)",
)
def criar_reserva(
    dados: schemas.ReservaCreate,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_aluno),
):
    """
    Cria uma reserva para o aluno em um local presencial.

    - Valida que a prova existe e está PUBLICADA
    - Valida que o local existe e tem `vagas_restantes > 0`
    - Impede reserva duplicada (já existe uma ATIVA para a mesma prova) → 409
    - Decrementa `vagas_restantes` do local
    - Define expiração em 48h

    O `id` retornado deve ser usado como `reserva_id` ao chamar
    `POST /simulados/iniciar` com `modalidade: "PRESENCIAL"`.
    """
    return reserva_service.criar_reserva(dados, aluno, db)


@router.get(
    "/",
    response_model=List[schemas.ReservaResponse],
    summary="Lista as reservas do aluno autenticado",
)
def listar_minhas_reservas(
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual),
):
    """Reservas ATIVAS vencidas são automaticamente marcadas como EXPIRADA."""
    return reserva_service.listar_minhas_reservas(aluno, db)


@router.get(
    "/{reserva_id}",
    response_model=schemas.ReservaResponse,
    summary="Detalhe de uma reserva",
)
def buscar_reserva(
    reserva_id: int,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual),
):
    return reserva_service.buscar_reserva(reserva_id, aluno, db)


@router.delete(
    "/{reserva_id}",
    response_model=schemas.MensagemResponse,
    summary="Cancela uma reserva e devolve a vaga",
)
def cancelar_reserva(
    reserva_id: int,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual),
):
    """Apenas reservas com status ATIVA podem ser canceladas."""
    return reserva_service.cancelar_reserva(reserva_id, aluno, db)

# Admin — visão geral das reservas

@router.get(
    "/admin/todas",
    response_model=List[schemas.ReservaAdminResponse],
    summary="[ADMIN] Lista todas as reservas com filtros",
)
def listar_todas_reservas(
    prova_id: Optional[int] = Query(None),
    local_id: Optional[int] = Query(None),
    status_filtro: Optional[str] = Query(
        None, alias="status", description="ATIVA | CONFIRMADA | CANCELADA | EXPIRADA"
    ),
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    return reserva_service.listar_todas_admin(db, prova_id, local_id, status_filtro)


@router.post(
    "/admin",
    response_model=schemas.ReservaAdminResponse,
    status_code=201,
    summary="[ADMIN] Cria uma reserva em nome de um aluno",
)
def criar_reserva_admin(
    dados: schemas.ReservaAdminCreate,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    return reserva_service.criar_reserva_admin(dados, db)


@router.patch(
    "/admin/{reserva_id}",
    response_model=schemas.ReservaAdminResponse,
    summary="[ADMIN] Edita uma reserva (datas, status, local, prova, necessidades)",
)
def editar_reserva_admin(
    reserva_id: int,
    dados: schemas.ReservaAdminUpdate,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    return reserva_service.editar_reserva_admin(reserva_id, dados, db)


@router.delete(
    "/admin/{reserva_id}",
    response_model=schemas.MensagemResponse,
    summary="[ADMIN] Cancela qualquer reserva e devolve a vaga",
)
def cancelar_reserva_admin(
    reserva_id: int,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    return reserva_service.cancelar_reserva_admin(reserva_id, db)