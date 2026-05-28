import random
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.dependencies import get_usuario_atual

router = APIRouter(prefix="/simulados", tags=["Simulados"])


@router.post("/iniciar", response_model=schemas.IniciarSimuladoResponse)
def iniciar_simulado(
    dados: schemas.IniciarSimuladoRequest,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual),
):
    prova = db.query(models.Prova).filter(
        models.Prova.id == dados.prova_id,
        models.Prova.status == "PUBLICADA"
    ).first()
    if not prova:
        raise HTTPException(404, "Prova não encontrada ou não publicada")

    # Verifica se já tem simulado em andamento
    tentativa_existente = db.query(models.Tentativa).filter(
        models.Tentativa.aluno_id == aluno.id,
        models.Tentativa.prova_id == dados.prova_id,
        models.Tentativa.status == "EM_ANDAMENTO"
    ).first()
    if tentativa_existente:
        raise HTTPException(409, "Você já possui um simulado em andamento para esta prova")

    # Busca as questões da prova
    questoes = db.query(models.Questao).filter(models.Questao.prova_id == prova.id).all()
    if not questoes:
        raise HTTPException(400, "Esta prova não possui questões")

    # Embaralha e guarda a ordem
    ordem_ids = [q.id for q in questoes]
    random.shuffle(ordem_ids)

    # Cria a tentativa
    nova_tentativa = models.Tentativa(
        aluno_id=aluno.id,
        prova_id=prova.id,
        tipo="SIMULADO",
        status="EM_ANDAMENTO",
        data_inicio=datetime.now(timezone.utc),
        ordem_questoes=json.dumps(ordem_ids)   # salva a ordem como texto JSON
    )
    db.add(nova_tentativa)
    db.commit()
    db.refresh(nova_tentativa)

    # Primeira questão
    primeira_id = ordem_ids[0]
    primeira_questao = db.query(models.Questao).filter(models.Questao.id == primeira_id).first()
    alternativas = list(primeira_questao.alternativas)
    random.shuffle(alternativas)

    return {
        "tentativa_id": nova_tentativa.id,
        "questao_id": primeira_questao.id,
        "enunciado": primeira_questao.enunciado,
        "alternativas": alternativas,
        "questao_numero": 1,
        "total_questoes": len(ordem_ids),
    }


@router.post("/responder", response_model=schemas.ResponderQuestaoResponse)
def responder_questao(
    dados: schemas.ResponderQuestaoRequest,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual),
):
    tentativa = db.query(models.Tentativa).filter(models.Tentativa.id == dados.tentativa_id).first()
    if not tentativa:
        raise HTTPException(404, "Tentativa não encontrada")
    if tentativa.aluno_id != aluno.id:
        raise HTTPException(403, "Essa tentativa não pertence a você")
    if tentativa.status != "EM_ANDAMENTO":
        raise HTTPException(400, "Este simulado já foi finalizado")

    # Recupera a ordem guardada
    ordem_ids = json.loads(tentativa.ordem_questoes) if tentativa.ordem_questoes else []
    if not ordem_ids:
        raise HTTPException(400, "Ordem das questões não definida")

    if dados.questao_id not in ordem_ids:
        raise HTTPException(400, "Questão não pertence a este simulado")

    alternativa = db.query(models.Alternativa).filter(
        models.Alternativa.id == dados.alternativa_id,
        models.Alternativa.questao_id == dados.questao_id
    ).first()
    if not alternativa:
        raise HTTPException(404, "Alternativa inválida")

    ja_respondida = db.query(models.Resposta).filter(
        models.Resposta.tentativa_id == tentativa.id,
        models.Resposta.questao_id == dados.questao_id
    ).first()
    if ja_respondida:
        raise HTTPException(400, "Você já respondeu esta questão")

    # Registra resposta
    resposta = models.Resposta(
        tentativa_id=tentativa.id,
        questao_id=dados.questao_id,
        alternativa_id=dados.alternativa_id,
        is_correta=alternativa.is_correta,
        data_resposta=datetime.now(timezone.utc)
    )
    db.add(resposta)
    db.commit()

    # Conta quantas já respondeu
    respondidas = db.query(models.Resposta).filter(
        models.Resposta.tentativa_id == tentativa.id
    ).count()
    total = len(ordem_ids)

    if respondidas >= total:
        acertos = db.query(models.Resposta).filter(
            models.Resposta.tentativa_id == tentativa.id,
            models.Resposta.is_correta == True
        ).count()
        nota = round((acertos / total) * 10, 2)
        tentativa.status = "CONCLUIDA"
        tentativa.data_fim = datetime.now(timezone.utc)
        tentativa.nota = nota
        tentativa.resultado = "APROVADO" if nota >= (tentativa.prova.nota_minima or 6.0) else "REPROVADO"
        db.commit()
        return {"finalizado": True, "nota_final": nota}

    # Descobre qual é a próxima questão na ordem
    idx_atual = ordem_ids.index(dados.questao_id)
    proxima_id = ordem_ids[idx_atual + 1]
    proxima = db.query(models.Questao).filter(models.Questao.id == proxima_id).first()
    alternativas = list(proxima.alternativas)
    random.shuffle(alternativas)

    return {
        "finalizado": False,
        "proxima_questao_id": proxima.id,
        "proxima_questao_enunciado": proxima.enunciado,
        "proximas_alternativas": alternativas,
        "questao_numero": respondidas + 1,
        "total_questoes": total,
    }


@router.get("/{tentativa_id}/resultado", response_model=schemas.ResultadoSimuladoResponse)
def resultado_simulado(
    tentativa_id: int,
    db: Session = Depends(get_db),
    aluno: models.Usuario = Depends(get_usuario_atual),
):
    tentativa = db.query(models.Tentativa).filter(models.Tentativa.id == tentativa_id).first()
    if not tentativa:
        raise HTTPException(404, "Tentativa não encontrada")
    if tentativa.aluno_id != aluno.id:
        raise HTTPException(403, "Essa tentativa não pertence a você")
    if tentativa.status != "CONCLUIDA":
        raise HTTPException(400, "Simulado ainda não finalizado")

    respostas = db.query(models.Resposta).filter(models.Resposta.tentativa_id == tentativa.id).all()
    detalhes = []
    for resp in respostas:
        q = db.query(models.Questao).filter(models.Questao.id == resp.questao_id).first()
        alt_escolhida = db.query(models.Alternativa).filter(models.Alternativa.id == resp.alternativa_id).first()
        alt_correta = db.query(models.Alternativa).filter(
            models.Alternativa.questao_id == resp.questao_id,
            models.Alternativa.is_correta == True
        ).first()
        detalhes.append({
            "questao_id": q.id,
            "enunciado": q.enunciado,
            "alternativa_escolhida": alt_escolhida.texto if alt_escolhida else "",
            "alternativa_correta": alt_correta.texto if alt_correta else "",
            "acertou": resp.is_correta,
        })

    return {
        "tentativa_id": tentativa.id,
        "prova_titulo": tentativa.prova.titulo,
        "total_questoes": len(json.loads(tentativa.ordem_questoes)) if tentativa.ordem_questoes else 0,
        "total_acertos": sum(1 for r in respostas if r.is_correta),
        "total_erros": sum(1 for r in respostas if not r.is_correta),
        "nota": float(tentativa.nota),
        "status": tentativa.status,
        "respostas": detalhes,
    }