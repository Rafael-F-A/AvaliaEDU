from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app import models, schemas
from app.dependencies import get_usuario_atual
from app.services import certificacao_service

router = APIRouter(prefix="/certificacoes", tags=["Certificações"])
limiter = Limiter(key_func=get_remote_address)

@router.post("/solicitar", response_model=schemas.CertificacaoSolicitadaResponse)
def solicitar_certificacao(
    dados: schemas.CertificacaoSolicitarRequest,
    request: Request,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual)
):
    tentativa = certificacao_service.solicitar_certificacao(
        dados.prova_id, aluno, db, request.client.host, request.headers.get("user-agent")
    )
    return {"tentativa_id": tentativa.id, "status": tentativa.status}

@router.post("/iniciar/{tentativa_id}", response_model=schemas.IniciarSimuladoResponse)
def iniciar_certificacao(
    tentativa_id: int,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual)
):
    return certificacao_service.iniciar_certificacao(tentativa_id, aluno, db)

@router.post("/responder", response_model=schemas.ResponderQuestaoResponse)
def responder_questao_certificacao(
    dados: schemas.ResponderQuestaoRequest,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual)
):
    return certificacao_service.responder_questao_certificacao(dados, aluno, db)

@router.get("/{tentativa_id}/resultado", response_model=schemas.ResultadoSimuladoResponse)
def resultado_certificacao(
    tentativa_id: int,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual)
):
    from app.services import simulado_service
    return simulado_service.resultado_simulado(tentativa_id, aluno, db)

@router.post("/{tentativa_id}/certificado", response_model=schemas.CertificadoPublicoResponse)
def gerar_certificado(
    tentativa_id: int,
    request: Request,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual)
):
    return certificacao_service.gerar_certificado(tentativa_id, aluno, db, request.client.host, request.headers.get("user-agent"))

@router.get("/historico", response_model=list[schemas.HistoricoCertificacaoResponse])
def historico_certificacoes(
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual)
):
    return certificacao_service.listar_historico(aluno, db)

@router.get("/validar/{codigo}", response_model=schemas.CertificadoValidarResponse)
@limiter.limit("10/minute")
def validar_certificado_publico(
    codigo: str,
    request: Request,
    db: Session = Depends(get_db)
):
    return certificacao_service.validar_certificado_publico(codigo, db, request.client.host, request.headers.get("user-agent"))