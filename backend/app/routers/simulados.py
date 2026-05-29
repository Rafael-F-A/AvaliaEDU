from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.dependencies import get_usuario_atual
from app.services import simulado_service

router = APIRouter(prefix="/simulados", tags=["Simulados"])


@router.post("/iniciar", response_model=schemas.IniciarSimuladoResponse)
def iniciar_simulado(
    dados: schemas.IniciarSimuladoRequest,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual),
):
    return simulado_service.iniciar_simulado(dados.prova_id, aluno, db)


@router.post("/responder", response_model=schemas.ResponderQuestaoResponse)
def responder_questao(
    dados: schemas.ResponderQuestaoRequest,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual),
):
    return simulado_service.responder_questao(dados, aluno, db)


@router.get("/{tentativa_id}/resultado", response_model=schemas.ResultadoSimuladoResponse)
def resultado_simulado(
    tentativa_id: int,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual),
):
    return simulado_service.resultado_simulado(tentativa_id, aluno, db)
