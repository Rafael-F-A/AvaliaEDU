import random
import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app import models, schemas


def iniciar_simulado(prova_id: int, aluno: models.Usuario, db: Session) -> dict:
    """
    Cria uma tentativa de simulado para o aluno.
    - Verifica se a prova existe e está publicada
    - Impede tentativa simultânea da mesma prova (US15)
    - Embaralha questões e alternativas; persiste a ordem em JSON (US11)
    - Retorna a primeira questão
    """
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.status == "PUBLICADA",
        models.Prova.deleted == False,
    ).first()

    if not prova:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Prova não encontrada ou não publicada.")

    tentativa_ativa = db.query(models.Tentativa).filter(
        models.Tentativa.aluno_id == aluno.id,
        models.Tentativa.prova_id == prova_id,
        models.Tentativa.status == "EM_ANDAMENTO",
    ).first()

    if tentativa_ativa:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Você já possui um simulado em andamento para esta prova.")

    questoes = db.query(models.Questao).filter(models.Questao.prova_id == prova.id).all()
    if not questoes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Esta prova não possui questões.")

    ordem_ids = [q.id for q in questoes]
    random.shuffle(ordem_ids)

    tentativa = models.Tentativa(
        aluno_id=aluno.id,
        prova_id=prova.id,
        tipo="SIMULADO",
        status="EM_ANDAMENTO",
        data_inicio=datetime.now(timezone.utc),
        ordem_questoes=json.dumps(ordem_ids),
    )
    db.add(tentativa)
    db.commit()
    db.refresh(tentativa)

    primeira_questao = db.query(models.Questao).filter(
        models.Questao.id == ordem_ids[0]
    ).first()

    alternativas = list(primeira_questao.alternativas)
    random.shuffle(alternativas)

    return {
        "tentativa_id": tentativa.id,
        "questao_id": primeira_questao.id,
        "enunciado": primeira_questao.enunciado,
        "alternativas": alternativas,
        "questao_numero": 1,
        "total_questoes": len(ordem_ids),
    }


def responder_questao(
    dados: schemas.ResponderQuestaoRequest,
    aluno: models.Usuario,
    db: Session,
) -> dict:
    """
    Registra a resposta do aluno e avança para a próxima questão.
    - Valida pertencimento da tentativa ao aluno (403)
    - Impede resposta duplicada na mesma questão (US15)
    - Verifica tempo_limite se definido na prova (US16)
    - Finaliza e calcula nota ao responder a última questão
    """
    tentativa = db.query(models.Tentativa).filter(
        models.Tentativa.id == dados.tentativa_id
    ).first()

    if not tentativa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Tentativa não encontrada.")

    if tentativa.aluno_id != aluno.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Essa tentativa não pertence a você.")

    if tentativa.status != "EM_ANDAMENTO":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Este simulado já foi finalizado.")

    # US16: verifica tempo limite
    if tentativa.prova.tempo_limite:
        segundos_passados = segundos_passados = (datetime.utcnow() - tentativa.data_inicio).total_seconds()
        limite_segundos = tentativa.prova.tempo_limite * 60
        if segundos_passados > limite_segundos:
            tentativa.status = "EXPIRADA"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tempo esgotado. O simulado foi encerrado automaticamente.",
            )

    ordem_ids = json.loads(tentativa.ordem_questoes) if tentativa.ordem_questoes else []

    if dados.questao_id not in ordem_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Questão não pertence a este simulado.")

    alternativa = db.query(models.Alternativa).filter(
        models.Alternativa.id == dados.alternativa_id,
        models.Alternativa.questao_id == dados.questao_id,
    ).first()

    if not alternativa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Alternativa inválida para esta questão.")

    ja_respondida = db.query(models.Resposta).filter(
        models.Resposta.tentativa_id == tentativa.id,
        models.Resposta.questao_id == dados.questao_id,
    ).first()

    if ja_respondida:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Você já respondeu esta questão.")

    db.add(models.Resposta(
        tentativa_id=tentativa.id,
        questao_id=dados.questao_id,
        alternativa_id=dados.alternativa_id,
        is_correta=alternativa.is_correta,
        data_resposta=datetime.now(timezone.utc),
    ))
    db.commit()

    total = len(ordem_ids)
    respondidas = db.query(models.Resposta).filter(
        models.Resposta.tentativa_id == tentativa.id
    ).count()

    # Última questão: finaliza e calcula nota
    if respondidas >= total:
        acertos = db.query(models.Resposta).filter(
            models.Resposta.tentativa_id == tentativa.id,
            models.Resposta.is_correta == True,
        ).count()
        nota = round((acertos / total) * 10, 2)
        tentativa.status = "CONCLUIDA"
        tentativa.data_fim = datetime.now(timezone.utc)
        tentativa.nota = nota
        tentativa.resultado = "APROVADO" if nota >= (tentativa.prova.nota_minima or 6.0) else "REPROVADO"
        db.commit()
        return {"finalizado": True, "nota_final": nota}

    # Próxima questão
    idx_atual = ordem_ids.index(dados.questao_id)
    proxima = db.query(models.Questao).filter(
        models.Questao.id == ordem_ids[idx_atual + 1]
    ).first()

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


def resultado_simulado(tentativa_id: int, aluno: models.Usuario, db: Session) -> dict:
    """
    Retorna o resultado detalhado de um simulado concluído.
    Inclui: nota, acertos, erros e detalhes de cada resposta (US17).
    """
    tentativa = db.query(models.Tentativa).filter(
        models.Tentativa.id == tentativa_id
    ).first()

    if not tentativa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Tentativa não encontrada.")

    if tentativa.aluno_id != aluno.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Essa tentativa não pertence a você.")

    if tentativa.status != "CONCLUIDA":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Simulado ainda não finalizado.")

    respostas = db.query(models.Resposta).filter(
        models.Resposta.tentativa_id == tentativa.id
    ).all()

    detalhes = []
    for resp in respostas:
        questao = db.query(models.Questao).filter(models.Questao.id == resp.questao_id).first()
        alt_escolhida = db.query(models.Alternativa).filter(
            models.Alternativa.id == resp.alternativa_id
        ).first()
        alt_correta = db.query(models.Alternativa).filter(
            models.Alternativa.questao_id == resp.questao_id,
            models.Alternativa.is_correta == True,
        ).first()

        detalhes.append({
            "questao_id": questao.id,
            "enunciado": questao.enunciado,
            "alternativa_escolhida": alt_escolhida.texto if alt_escolhida else "",
            "alternativa_correta": alt_correta.texto if alt_correta else "",
            "acertou": resp.is_correta,
        })

    ordem_ids = json.loads(tentativa.ordem_questoes) if tentativa.ordem_questoes else []

    return {
        "tentativa_id": tentativa.id,
        "prova_titulo": tentativa.prova.titulo,
        "total_questoes": len(ordem_ids),
        "total_acertos": sum(1 for r in respostas if r.is_correta),
        "total_erros": sum(1 for r in respostas if not r.is_correta),
        "nota": float(tentativa.nota),
        "status": tentativa.resultado,
        "respostas": detalhes,
    }
