from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.dependencies import get_usuario_atual
from app.services import simulado_service

router = APIRouter(prefix="/simulados", tags=["Simulados"])


@router.post(
    "/iniciar",
    response_model=schemas.IniciarSimuladoResponse,
    summary="Inicia simulado — US15 + US23",
)
def iniciar_simulado(
    dados: schemas.IniciarSimuladoRequest,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual),
):
    """
    Modalidade ONLINE (padrão): body simples.
    Modalidade PRESENCIAL: exige reserva_id de uma reserva ATIVA.

    ```json
    { "prova_id": 1, "modalidade": "ONLINE" }
    { "prova_id": 1, "modalidade": "PRESENCIAL", "reserva_id": 42 }
    ```
    """
    return simulado_service.iniciar_simulado(
        prova_id=dados.prova_id,
        aluno=aluno,
        db=db,
        modalidade=dados.modalidade,
        reserva_id=dados.reserva_id,
    )


@router.post("/responder", response_model=schemas.ResponderQuestaoResponse)
def responder_questao(
    dados: schemas.ResponderQuestaoRequest,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual),
):
    return simulado_service.responder_questao(dados, aluno, db)


@router.patch("/{tentativa_id}/pausar", summary="Pausa simulado — US18")
def pausar_simulado(
    tentativa_id: int,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual),
):
    return simulado_service.pausar_simulado(tentativa_id, aluno, db)


@router.patch(
    "/{tentativa_id}/retomar",
    response_model=schemas.QuestaoAtualResponse,
    summary="Retoma simulado pausado — US18",
)
def retomar_simulado(
    tentativa_id: int,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual),
):
    return simulado_service.retomar_simulado(tentativa_id, aluno, db)


@router.get("/{tentativa_id}/resultado", response_model=schemas.ResultadoSimuladoResponse)
def resultado_simulado(
    tentativa_id: int,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual),
):
    return simulado_service.resultado_simulado(tentativa_id, aluno, db)


@router.get("/{tentativa_id}/questao_atual", response_model=schemas.QuestaoAtualResponse)
def questao_atual(
    tentativa_id: int,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual),
):
    return simulado_service.questao_atual(tentativa_id, aluno, db)


@router.get("/historico", summary="Histórico de simulados — US31")
def historico_simulados(
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual),
):
    return simulado_service.historico_simulados(aluno, db)