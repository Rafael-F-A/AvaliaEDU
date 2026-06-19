import random
import json
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

from app import models, schemas

DIAS_EXPIRACAO_PAUSA = 7

def _data_aware(dt: datetime) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _segundos_passados(tentativa: models.Tentativa) -> float:
    return (datetime.now(timezone.utc) - _data_aware(tentativa.data_inicio)).total_seconds()

def _verificar_tempo(tentativa: models.Tentativa, db: Session) -> None:
    if tentativa.prova.tempo_limite:
        if _segundos_passados(tentativa) > tentativa.prova.tempo_limite * 60:
            tentativa.status = "CONCLUIDA"
            tentativa.resultado = "REPROVADO"
            tentativa.data_fim = datetime.now(timezone.utc)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tempo esgotado. O simulado foi encerrado automaticamente.",
            )

def _validar_modalidade_presencial(
    prova: models.Prova,
    aluno: models.Usuario,
    reserva_id: int,
    db: Session,
) -> models.Reserva:
    """US23: valida reserva antes de iniciar prova presencial."""

    # 1. Prova tem locais ativos?
    tem_local = db.query(models.Reserva).filter(
        models.Reserva.prova_id == prova.id,
        models.Reserva.status == "ATIVA",
    ).first()

    if not tem_local:
        raise HTTPException(
            status_code=400,
            detail=(
                f"A prova '{prova.titulo}' não oferece modalidade PRESENCIAL "
                "ou não há locais com vagas disponíveis."
            ),
        )

    # 2. Reserva pertence ao aluno e à prova?
    reserva = db.query(models.Reserva).filter(
        models.Reserva.id == reserva_id,
        models.Reserva.aluno_id == aluno.id,
        models.Reserva.prova_id == prova.id,
    ).first()

    if not reserva:
        raise HTTPException(
            status_code=404,
            detail="Reserva não encontrada para este aluno e prova.",
        )

    # 3. Reserva ativa?
    if reserva.status != "ATIVA":
        raise HTTPException(
            status_code=409,
            detail=f"Reserva com status '{reserva.status}'. Apenas ATIVA permite iniciar.",
        )

    # 4. Expirou?
    if reserva.data_expiracao:
        expiracao = _data_aware(reserva.data_expiracao)
        if datetime.now(timezone.utc) > expiracao:
            reserva.status = "EXPIRADA"
            db.commit()
            raise HTTPException(
                status_code=410,
                detail="Sua reserva expirou. Crie uma nova reserva em POST /reservas/.",
            )

    # 5. Local com vaga?
    local = db.query(models.Local).filter(models.Local.id == reserva.local_id).first()
    if not local or local.vagas_restantes <= 0:
        raise HTTPException(
            status_code=409,
            detail="O local reservado não possui mais vagas disponíveis.",
        )

    return reserva


def iniciar_simulado(
    prova_id: int,
    aluno: models.Usuario,
    db: Session,
    modalidade: str = "ONLINE",
    reserva_id: int | None = None,
) -> dict:
    """US15 + US23: inicia simulado com suporte a ONLINE e PRESENCIAL."""

    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.status == "PUBLICADA",
        models.Prova.tipo == "SIMULADO",
        models.Prova.deleted == False,
    ).first()

    if not prova:
        raise HTTPException(status_code=404, detail="Prova não encontrada ou não publicada.")

    if aluno.nivel and prova.nivel != aluno.nivel:
        raise HTTPException(
            status_code=403,
            detail=f"Esta prova é para o nível {prova.nivel}. Seu perfil está em {aluno.nivel}.",
        )

    tentativa_ativa = db.query(models.Tentativa).filter(
        models.Tentativa.aluno_id == aluno.id,
        models.Tentativa.prova_id == prova_id,
        models.Tentativa.status.in_(["EM_ANDAMENTO", "PAUSADO"]),
    ).first()

    if tentativa_ativa:
        raise HTTPException(
            status_code=409,
            detail="Você já possui um simulado em andamento ou pausado para esta prova.",
        )

    # US23: validação presencial
    reserva = None
    if modalidade == "PRESENCIAL":
        reserva = _validar_modalidade_presencial(prova, aluno, reserva_id, db)

    questoes = db.query(models.Questao).filter(
        models.Questao.prova_id == prova.id
    ).all()
    if not questoes:
        raise HTTPException(status_code=400, detail="Esta prova não possui questões.")

    ordem_ids = [q.id for q in questoes]
    random.shuffle(ordem_ids)

    tentativa = models.Tentativa(
        aluno_id=aluno.id,
        prova_id=prova.id,
        tipo="SIMULADO",
        status="EM_ANDAMENTO",
        data_inicio=datetime.now(timezone.utc),
        ordem_questoes=json.dumps(ordem_ids),
        modalidade=modalidade,
    )
    db.add(tentativa)
    db.flush()

    # US23: marca reserva como utilizada
    if reserva:
        reserva.status = "UTILIZADA"
        reserva.tentativa_id = tentativa.id

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
        "modalidade": modalidade,
    }

def responder_questao(dados, aluno, db):
    tentativa = db.query(models.Tentativa).filter(
        models.Tentativa.id == dados.tentativa_id
    ).first()
    if not tentativa:
        raise HTTPException(status_code=404, detail="Tentativa não encontrada.")
    if tentativa.aluno_id != aluno.id:
        raise HTTPException(status_code=403, detail="Essa tentativa não pertence a você.")
    if tentativa.status == "PAUSADO":
        raise HTTPException(status_code=400, detail="Retome o simulado antes de responder.")
    if tentativa.status != "EM_ANDAMENTO":
        raise HTTPException(status_code=400, detail="Este simulado já foi finalizado.")
    _verificar_tempo(tentativa, db)

    ordem_raw = json.loads(tentativa.ordem_questoes) if tentativa.ordem_questoes else []
    ordem_ids = ordem_raw if isinstance(ordem_raw, list) else ordem_raw.get("ordem_ids", [])

    if dados.questao_id not in ordem_ids:
        raise HTTPException(status_code=400, detail="Questão não pertence a este simulado.")

    alternativa = db.query(models.Alternativa).filter(
        models.Alternativa.id == dados.alternativa_id,
        models.Alternativa.questao_id == dados.questao_id,
    ).first()
    if not alternativa:
        raise HTTPException(status_code=404, detail="Alternativa inválida para esta questão.")

    ja_respondida = db.query(models.Resposta).filter(
        models.Resposta.tentativa_id == tentativa.id,
        models.Resposta.questao_id == dados.questao_id,
    ).first()
    if ja_respondida:
        raise HTTPException(status_code=400, detail="Você já respondeu esta questão.")

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

def pausar_simulado(tentativa_id: int, aluno: models.Usuario, db: Session) -> dict:
    tentativa = db.query(models.Tentativa).filter(
        models.Tentativa.id == tentativa_id,
        models.Tentativa.aluno_id == aluno.id,
    ).first()
    if not tentativa:
        raise HTTPException(status_code=404, detail="Tentativa não encontrada.")
    if tentativa.tipo != "SIMULADO":
        raise HTTPException(status_code=400, detail="Certificações não podem ser pausadas.")
    if tentativa.status != "EM_ANDAMENTO":
        raise HTTPException(status_code=400, detail="Apenas simulados em andamento podem ser pausados.")
    _verificar_tempo(tentativa, db)

    agora = datetime.now(timezone.utc)
    expiracao = agora + timedelta(days=DIAS_EXPIRACAO_PAUSA)
    ordem_raw = json.loads(tentativa.ordem_questoes) if tentativa.ordem_questoes else []
    ordem_ids = ordem_raw if isinstance(ordem_raw, list) else ordem_raw.get("ordem_ids", [])
    estado = {"ordem_ids": ordem_ids, "pausado_em": agora.isoformat(), "expira_em": expiracao.isoformat()}
    tentativa.ordem_questoes = json.dumps(estado)
    tentativa.status = "PAUSADO"
    db.commit()
    return {
        "tentativa_id": tentativa.id,
        "status": "PAUSADO",
        "expira_em": expiracao.isoformat(),
        "mensagem": f"Simulado pausado. Você tem até {expiracao.strftime('%d/%m/%Y %H:%M')} UTC para retomar.",
    }

def retomar_simulado(tentativa_id: int, aluno: models.Usuario, db: Session) -> dict:
    tentativa = db.query(models.Tentativa).filter(
        models.Tentativa.id == tentativa_id,
        models.Tentativa.aluno_id == aluno.id,
    ).first()
    if not tentativa:
        raise HTTPException(status_code=404, detail="Tentativa não encontrada.")
    if tentativa.status != "PAUSADO":
        raise HTTPException(status_code=400, detail="Este simulado não está pausado.")

    estado_raw = json.loads(tentativa.ordem_questoes) if tentativa.ordem_questoes else {}
    expira_em_str = estado_raw.get("expira_em")
    if expira_em_str:
        expira_em = datetime.fromisoformat(expira_em_str)
        if datetime.now(timezone.utc) > expira_em:
            tentativa.status = "CONCLUIDA"
            tentativa.resultado = "REPROVADO"
            tentativa.data_fim = datetime.now(timezone.utc)
            db.commit()
            raise HTTPException(status_code=410, detail="O prazo para retomar expirou. Simulado encerrado.")

    pausado_em_str = estado_raw.get("pausado_em")
    if pausado_em_str and tentativa.prova.tempo_limite:
        pausado_em = datetime.fromisoformat(pausado_em_str)
        tempo_pausado = (datetime.now(timezone.utc) - pausado_em).total_seconds()
        tentativa.data_inicio = _data_aware(tentativa.data_inicio) + timedelta(seconds=tempo_pausado)

    ordem_ids = estado_raw.get("ordem_ids", [])
    tentativa.ordem_questoes = json.dumps(ordem_ids)
    tentativa.status = "EM_ANDAMENTO"
    db.commit()
    db.refresh(tentativa)

    respondidas = db.query(models.Resposta).filter(models.Resposta.tentativa_id == tentativa.id).count()
    questao = db.query(models.Questao).filter(models.Questao.id == ordem_ids[respondidas]).first()
    alternativas = list(questao.alternativas)
    random.shuffle(alternativas)
    tempo_restante = None
    if tentativa.prova.tempo_limite:
        seg = _segundos_passados(tentativa)
        tempo_restante = max(0, tentativa.prova.tempo_limite * 60 - seg)
    return {
        "tentativa_id": tentativa.id,
        "status": "EM_ANDAMENTO",
        "questao_id": questao.id,
        "enunciado": questao.enunciado,
        "alternativas": alternativas,
        "questao_numero": respondidas + 1,
        "total_questoes": len(ordem_ids),
        "tempo_restante_segundos": tempo_restante,
        "modalidade": tentativa.modalidade,
    }


def resultado_simulado(tentativa_id: int, aluno: models.Usuario, db: Session) -> dict:
    tentativa = db.query(models.Tentativa).filter(models.Tentativa.id == tentativa_id).first()
    if not tentativa:
        raise HTTPException(status_code=404, detail="Tentativa não encontrada.")
    if tentativa.aluno_id != aluno.id:
        raise HTTPException(status_code=403, detail="Essa tentativa não pertence a você.")
    if tentativa.status != "CONCLUIDA":
        raise HTTPException(status_code=400, detail="Simulado ainda não finalizado.")

    respostas = db.query(models.Resposta).filter(models.Resposta.tentativa_id == tentativa.id).all()
    detalhes = []
    for resp in respostas:
        questao = db.query(models.Questao).filter(models.Questao.id == resp.questao_id).first()
        alt_escolhida = db.query(models.Alternativa).filter(models.Alternativa.id == resp.alternativa_id).first()
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

    ordem_raw = json.loads(tentativa.ordem_questoes) if tentativa.ordem_questoes else []
    ordem_ids = ordem_raw if isinstance(ordem_raw, list) else ordem_raw.get("ordem_ids", [])
    return {
        "tentativa_id": tentativa.id,
        "prova_titulo": tentativa.prova.titulo,
        "total_questoes": len(ordem_ids),
        "total_acertos": sum(1 for r in respostas if r.is_correta),
        "total_erros": sum(1 for r in respostas if not r.is_correta),
        "nota": float(tentativa.nota),
        "status": tentativa.resultado,
        "modalidade": tentativa.modalidade,
        "respostas": detalhes,
    }


def historico_simulados(aluno: models.Usuario, db: Session) -> list:
    tentativas = (
        db.query(models.Tentativa)
        .options(joinedload(models.Tentativa.prova))
        .filter(
            models.Tentativa.aluno_id == aluno.id,
            models.Tentativa.tipo == "SIMULADO",
        )
        .order_by(models.Tentativa.data_inicio.desc())
        .all()
    )
    historico = []
    for tent in tentativas:
        respondidas = db.query(models.Resposta).filter(models.Resposta.tentativa_id == tent.id).count()
        ordem_raw = json.loads(tent.ordem_questoes) if tent.ordem_questoes else []
        ordem_ids = ordem_raw if isinstance(ordem_raw, list) else ordem_raw.get("ordem_ids", [])
        tempo_gasto = None
        if tent.data_inicio and tent.data_fim:
            delta = _data_aware(tent.data_fim) - _data_aware(tent.data_inicio)
            tempo_gasto = int(delta.total_seconds())
        historico.append({
            "id": tent.id,
            "prova_id": tent.prova_id,
            "prova_titulo": tent.prova.titulo,
            "prova_nivel": tent.prova.nivel,
            "status": tent.status,
            "resultado": tent.resultado,
            "nota": float(tent.nota) if tent.nota is not None else None,
            "modalidade": tent.modalidade,
            "total_questoes": len(ordem_ids),
            "questoes_respondidas": respondidas,
            "data_inicio": tent.data_inicio,
            "data_fim": tent.data_fim,
            "tempo_gasto_segundos": tempo_gasto,
        })
    return historico


def questao_atual(tentativa_id: int, aluno: models.Usuario, db: Session) -> dict:
    tentativa = db.query(models.Tentativa).filter(models.Tentativa.id == tentativa_id).first()
    if not tentativa:
        raise HTTPException(status_code=404, detail="Tentativa não encontrada.")
    if tentativa.aluno_id != aluno.id:
        raise HTTPException(status_code=403, detail="Essa tentativa não pertence a você.")
    if tentativa.status != "EM_ANDAMENTO":
        raise HTTPException(status_code=400, detail="Simulado não está em andamento.")

    ordem_raw = json.loads(tentativa.ordem_questoes) if tentativa.ordem_questoes else []
    ordem_ids = ordem_raw if isinstance(ordem_raw, list) else ordem_raw.get("ordem_ids", [])
    if not ordem_ids:
        raise HTTPException(status_code=400, detail="Ordem das questões não definida.")

    respondidas = db.query(models.Resposta).filter(models.Resposta.tentativa_id == tentativa.id).count()
    if respondidas >= len(ordem_ids):
        raise HTTPException(status_code=400, detail="Simulado já finalizado.")

    questao = db.query(models.Questao).filter(models.Questao.id == ordem_ids[respondidas]).first()
    if not questao:
        raise HTTPException(status_code=404, detail="Questão não encontrada.")

    alternativas = list(questao.alternativas)
    random.shuffle(alternativas)
    tempo_restante = None
    if tentativa.prova.tempo_limite:
        seg = _segundos_passados(tentativa)
        tempo_restante = max(0, tentativa.prova.tempo_limite * 60 - seg)
    return {
        "tentativa_id": tentativa.id,
        "questao_id": questao.id,
        "enunciado": questao.enunciado,
        "alternativas": alternativas,
        "questao_numero": respondidas + 1,
        "total_questoes": len(ordem_ids),
        "tempo_restante_segundos": tempo_restante,
        "modalidade": tentativa.modalidade,
    }