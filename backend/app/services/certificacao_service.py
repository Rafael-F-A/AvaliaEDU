import secrets
import json
import random
from datetime import datetime, timezone, date
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app import models, schemas
from app.enums import TipoProva, StatusTentativa, ResultadoTentativa
from app.services.auditoria_service import registrar_acao

def gerar_codigo_unico(db: Session) -> str:
    while True:
        codigo = secrets.token_hex(16).upper()
        existe = db.query(models.Certificado).filter(
            models.Certificado.codigo_validacao == codigo
        ).first()
        if not existe:
            return codigo

def _persistir_ordem_alternativas(tentativa: models.Tentativa, questoes: list):
    ordem = {}
    for q in questoes:
        alternativas = list(q.alternativas)
        random.shuffle(alternativas)
        ordem[str(q.id)] = [alt.id for alt in alternativas]
    tentativa.ordem_alternativas = json.dumps(ordem)
    return ordem

def solicitar_certificacao(prova_id: int, aluno: models.Usuario, db: Session, ip: str = None, user_agent: str = None):
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.tipo == TipoProva.CERTIFICACAO.value,
        models.Prova.status == "PUBLICADA",
        models.Prova.deleted == False
    ).first()
    if not prova:
        raise HTTPException(404, "Certificação não disponível.")

    # verifica se já aprovado
    if db.query(models.Certificado).join(models.Tentativa).filter(
        models.Tentativa.aluno_id == aluno.id,
        models.Tentativa.prova_id == prova_id,
        models.Tentativa.resultado == ResultadoTentativa.APROVADO.value
    ).first():
        raise HTTPException(409, "Você já possui certificado para esta prova.")

    # verifica bloqueio
    reprovada = db.query(models.Tentativa).filter(
        models.Tentativa.aluno_id == aluno.id,
        models.Tentativa.prova_id == prova_id,
        models.Tentativa.resultado == ResultadoTentativa.REPROVADO.value,
        models.Tentativa.bloqueio_ate >= date.today()
    ).first()
    if reprovada:
        raise HTTPException(403, f"Bloqueado até {reprovada.bloqueio_ate}.")

    tentativa = models.Tentativa(
        aluno_id=aluno.id,
        prova_id=prova.id,
        tipo=TipoProva.CERTIFICACAO.value,
        status=StatusTentativa.INSCRITO.value,
        data_inicio=datetime.now(timezone.utc)
    )
    db.add(tentativa)
    db.commit()
    db.refresh(tentativa)

    registrar_acao(db, aluno.id, "SOLICITAR_CERTIFICACAO", "tentativa", tentativa.id, ip, user_agent)
    return tentativa

def iniciar_certificacao(tentativa_id: int, aluno: models.Usuario, db: Session):
    tentativa = db.query(models.Tentativa).filter(
        models.Tentativa.id == tentativa_id,
        models.Tentativa.aluno_id == aluno.id,
        models.Tentativa.tipo == TipoProva.CERTIFICACAO.value
    ).first()
    if not tentativa:
        raise HTTPException(404, "Solicitação não encontrada.")
    if tentativa.status != StatusTentativa.INSCRITO.value:
        raise HTTPException(409, "Certificação já iniciada ou concluída.")

    questoes = db.query(models.Questao).filter(models.Questao.prova_id == tentativa.prova_id).all()
    if not questoes:
        raise HTTPException(400, "Esta certificação não possui questões.")

    ordem_questoes = [q.id for q in questoes]
    random.shuffle(ordem_questoes)
    ordem_alternativas = _persistir_ordem_alternativas(tentativa, questoes)

    tentativa.ordem_questoes = json.dumps(ordem_questoes)
    tentativa.status = StatusTentativa.EM_ANDAMENTO.value
    db.commit()

    primeira_q = db.query(models.Questao).filter(models.Questao.id == ordem_questoes[0]).first()
    alternativas = ordem_alternativas[str(primeira_q.id)]
    return {
        "tentativa_id": tentativa.id,
        "questao_id": primeira_q.id,
        "enunciado": primeira_q.enunciado,
        "alternativas": [db.get(models.Alternativa, alt_id) for alt_id in alternativas],
        "questao_numero": 1,
        "total_questoes": len(ordem_questoes)
    }

def responder_questao_certificacao(dados: schemas.ResponderQuestaoRequest, aluno: models.Usuario, db: Session):
    # validação de tipo
    tentativa = db.query(models.Tentativa).filter(models.Tentativa.id == dados.tentativa_id).first()
    if not tentativa or tentativa.aluno_id != aluno.id:
        raise HTTPException(404, "Tentativa não encontrada.")
    if tentativa.tipo != TipoProva.CERTIFICACAO.value:
        raise HTTPException(400, "Tentativa não é de certificação.")

    from app.services import simulado_service
    return simulado_service.responder_questao(dados, aluno, db)

def gerar_certificado(tentativa_id: int, aluno: models.Usuario, db: Session, ip: str = None, user_agent: str = None):
    tentativa = db.query(models.Tentativa).filter(
        models.Tentativa.id == tentativa_id,
        models.Tentativa.aluno_id == aluno.id,
        models.Tentativa.tipo == TipoProva.CERTIFICACAO.value
    ).first()
    if not tentativa:
        raise HTTPException(404, "Tentativa não encontrada.")
    if tentativa.status != StatusTentativa.CONCLUIDA.value or tentativa.resultado != ResultadoTentativa.APROVADO.value:
        raise HTTPException(400, "Não é possível gerar certificado.")

    try:
        codigo = gerar_codigo_unico(db)
        # URL do PDF – pode ser assinada depois; por enquanto, placeholder
        url_pdf = f"/certificados/{codigo}.pdf"
        certificado = models.Certificado(
            tentativa_id=tentativa.id,
            aluno_id=aluno.id,
            prova_id=tentativa.prova_id,
            codigo_validacao=codigo,
            url_pdf=url_pdf
        )
        db.add(certificado)
        db.commit()
        registrar_acao(db, aluno.id, "GERAR_CERTIFICADO", "certificado", certificado.id, ip, user_agent)

        return {
            "id": certificado.id,
            "aluno_nome": certificado.aluno.nome,
            "prova_titulo": certificado.prova.titulo,
            "codigo": certificado.codigo_validacao,
            "data_emissao": certificado.data_emissao,
            "url_pdf": certificado.url_pdf,
            "tentativa_id": certificado.tentativa_id,
            "aluno_id": certificado.aluno_id,
            "prova_id": certificado.prova_id,
            "ativo": certificado.ativo,
            "created_at": certificado.created_at
        }
    except IntegrityError:
        db.rollback()
        certificado_existente = db.query(models.Certificado).filter_by(tentativa_id=tentativa.id).first()
        if certificado_existente:
            return {
                "id": certificado_existente.id,
                "aluno_nome": certificado_existente.aluno.nome,
                "prova_titulo": certificado_existente.prova.titulo,
                "codigo": certificado_existente.codigo_validacao,
                "data_emissao": certificado_existente.data_emissao,
                "url_pdf": certificado_existente.url_pdf,
                "tentativa_id": certificado_existente.tentativa_id,
                "aluno_id": certificado_existente.aluno_id,
                "prova_id": certificado_existente.prova_id,
                "ativo": certificado_existente.ativo,
                "created_at": certificado_existente.created_at
            }
        raise HTTPException(500, "Erro ao gerar certificado.")

def listar_historico(aluno: models.Usuario, db: Session) -> list:
    tentativas = db.query(models.Tentativa).options(
        joinedload(models.Tentativa.prova),
        joinedload(models.Tentativa.certificado)
    ).filter(
        models.Tentativa.aluno_id == aluno.id,
        models.Tentativa.tipo == TipoProva.CERTIFICACAO.value
    ).order_by(models.Tentativa.data_inicio.desc()).all()

    historico = []
    for tent in tentativas:
        nota = tent.nota if tent.nota is not None else 0.0
        resultado = tent.resultado if tent.resultado is not None else "REPROVADO"
        historico.append({
            "id": tent.id,
            "prova_titulo": tent.prova.titulo,
            "data_realizacao": tent.data_inicio,
            "nota": nota,
            "resultado": resultado,
            "certificado_id": tent.certificado.id if tent.certificado else None,
            "codigo_validacao": tent.certificado.codigo_validacao if tent.certificado else None,
            "bloqueio_ate": tent.bloqueio_ate,
        })
    return historico

def validar_certificado_publico(codigo: str, db: Session, ip: str = None, user_agent: str = None):
    certificado = db.query(models.Certificado).filter_by(codigo_validacao=codigo, ativo=True).first()
    if not certificado:
        return {"valido": False, "detalhe": "Código inválido"}
    nome = certificado.aluno.nome.split()
    nome_publico = f"{nome[0]} {nome[-1][0]}." if len(nome) > 1 else nome[0]
    return {
        "valido": True,
        "certificado": {
            "id": certificado.id,
            "aluno_nome": nome_publico,
            "prova_titulo": certificado.prova.titulo,
            "data_emissao": certificado.data_emissao,
            "codigo": certificado.codigo_validacao
        }
    }