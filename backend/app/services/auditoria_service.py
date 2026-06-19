from sqlalchemy.orm import Session
from app import models

def registrar_acao(
    db: Session,
    usuario_id: int,
    acao: str,
    entidade: str,
    entidade_id: int,
    ip: str = None,
    user_agent: str = None
):
    """
    Registra um log de auditoria no banco de dados.
    """
    log = models.Auditoria(
        usuario_id=usuario_id,
        acao=acao,
        entidade=entidade,
        entidade_id=entidade_id,
        ip=ip,
        user_agent=user_agent
    )
    db.add(log)
    db.commit()