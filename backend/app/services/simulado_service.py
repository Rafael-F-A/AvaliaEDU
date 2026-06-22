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


def _calcular_nota(tentativa: models.Tentativa, db: Session) -> float:
    """Calcula a nota com base nas respostas já dadas (mesma fórmula da
    finalização normal: acertos/total*10, arredondado). Usada também ao
    encerrar por tempo/expiração, para que tentativa.nota nunca fique NULL."""
    ordem_raw = json.loads(tentativa.ordem_questoes) if tentativa.ordem_questoes else []
    ordem_ids = ordem_raw if isinstance(ordem_raw, list) else ordem_raw.get("ordem_ids", [])
    total = len(ordem_ids)
    if total == 0:
        return 0.0
    acertos = db.query(models.Resposta).filter(
        models.Resposta.tentativa_id == tentativa.id,
        models.Resposta.is_correta == True,
    ).count()
    return round((acertos / total) * 10, 2)


def _alternativas_ordenadas(questao: models.Questao, tentativa: models.Tentativa):
    """Retorna as alternativas da questão na ordem persistida em
    tentativa.ordem_alternativas (alinha PDF, tela e revisão). Se não houver
    ordem salva para a questão, cai no comportamento de embaralhar."""
    ordem_alt_raw = tentativa.ordem_alternativas
    if ordem_alt_raw:
        ordem_alt = json.loads(ordem_alt_raw) if isinstance(ordem_alt_raw, str) else ordem_alt_raw
    else:
        ordem_alt = {}
    ids_ordem = ordem_alt.get(str(questao.id))
    if ids_ordem:
        por_id = {alt.id: alt for alt in questao.alternativas}
        ordenadas = [por_id[aid] for aid in ids_ordem if aid in por_id]
        # garante que nenhuma alternativa nova fique de fora
        ordenadas += [alt for alt in questao.alternativas if alt.id not in ids_ordem]
        return ordenadas
    alternativas = list(questao.alternativas)
    random.shuffle(alternativas)
    return alternativas


def _verificar_tempo(tentativa: models.Tentativa, db: Session) -> None:
    if tentativa.prova.tempo_limite:
        if _segundos_passados(tentativa) > tentativa.prova.tempo_limite * 60:
            tentativa.status = "CONCLUIDA"
            tentativa.resultado = "REPROVADO"
            tentativa.data_fim = datetime.now(timezone.utc)
            # A-01: grava a nota com base nas respostas já dadas para que
            # resultado_simulado não receba nota NULL ao encerrar por tempo.
            tentativa.nota = _calcular_nota(tentativa, db)
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
    """US23: valida a reserva do aluno antes de iniciar prova presencial.

    A disponibilidade presencial é determinada pela reserva ESPECÍFICA do
    aluno (passos abaixo) — não por reservas ATIVAS de terceiros, o que
    quebrava após a 1ª reserva virar UTILIZADA (backend-inscr-reserva-3).
    """

    # 1. Reserva pertence ao aluno e à prova?
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

    # 2. Reserva ativa?
    if reserva.status != "ATIVA":
        raise HTTPException(
            status_code=409,
            detail=f"Reserva com status '{reserva.status}'. Apenas ATIVA permite iniciar.",
        )

    # 3. Expirou?
    if reserva.data_expiracao:
        expiracao = _data_aware(reserva.data_expiracao)
        if datetime.now(timezone.utc) > expiracao:
            reserva.status = "EXPIRADA"
            # A-04: devolve a vaga ao local ao expirar (sem ultrapassar a
            # capacidade), espelhando listar_minhas_reservas — evita vazamento.
            local_exp = db.query(models.Local).filter(models.Local.id == reserva.local_id).first()
            if local_exp:
                local_exp.vagas_restantes = min(local_exp.capacidade, local_exp.vagas_restantes + 1)
            db.commit()
            raise HTTPException(
                status_code=410,
                detail="Sua reserva expirou. Crie uma nova reserva em POST /reservas/.",
            )

    # 4. Local com vaga?
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

    # provas-4 / cert-6: embaralha as alternativas UMA vez e persiste a ordem,
    # para que PDF, tela e revisão fiquem consistentes (sem reembaralhar a cada
    # chamada). Formato: {str(questao_id): [alternativa_id, ...]}.
    ordem_alt = {}
    for q in questoes:
        alt_ids = [a.id for a in q.alternativas]
        random.shuffle(alt_ids)
        ordem_alt[str(q.id)] = alt_ids

    tentativa = models.Tentativa(
        aluno_id=aluno.id,
        prova_id=prova.id,
        tipo="SIMULADO",
        status="EM_ANDAMENTO",
        data_inicio=datetime.now(timezone.utc),
        ordem_questoes=json.dumps(ordem_ids),
        ordem_alternativas=json.dumps(ordem_alt),
        modalidade=modalidade,
    )
    db.add(tentativa)
    db.flush()

    # US23: marca reserva como confirmada (usada).
    # OBS.: o CHECK do banco aceita apenas ATIVA | CANCELADA | EXPIRADA | CONFIRMADA.
    # Antes gravava "UTILIZADA", que violava a constraint e quebrava (500) o início
    # da prova presencial. Mantemos "CONFIRMADA" — a vaga continua ocupada.
    if reserva:
        reserva.status = "CONFIRMADA"
        reserva.tentativa_id = tentativa.id

    db.commit()
    db.refresh(tentativa)

    primeira_questao = db.query(models.Questao).filter(
        models.Questao.id == ordem_ids[0]
    ).first()

    alternativas = _alternativas_ordenadas(primeira_questao, tentativa)

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

    # Upsert: o aluno pode responder em QUALQUER ordem (pular e voltar) e TROCAR a
    # resposta antes de finalizar. A finalização é EXPLÍCITA (POST .../finalizar);
    # responder apenas registra/atualiza a resposta.
    resposta = db.query(models.Resposta).filter(
        models.Resposta.tentativa_id == tentativa.id,
        models.Resposta.questao_id == dados.questao_id,
    ).first()
    if resposta:
        resposta.alternativa_id = alternativa.id
        resposta.is_correta = alternativa.is_correta
        resposta.data_resposta = datetime.now(timezone.utc)
    else:
        db.add(models.Resposta(
            tentativa_id=tentativa.id,
            questao_id=dados.questao_id,
            alternativa_id=alternativa.id,
            is_correta=alternativa.is_correta,
            data_resposta=datetime.now(timezone.utc),
        ))
    db.commit()

    respondidas = db.query(models.Resposta).filter(
        models.Resposta.tentativa_id == tentativa.id
    ).count()
    return {
        "finalizado": False,
        "questao_numero": respondidas,
        "total_questoes": len(ordem_ids),
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
            # A-01: grava a nota (com base no respondido) para não ficar NULL.
            tentativa.nota = _calcular_nota(tentativa, db)
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
    alternativas = _alternativas_ordenadas(questao, tentativa)
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


def resultado_simulado(tentativa_id: int, aluno: models.Usuario, db: Session, incluir_gabarito: bool = True) -> dict:
    tentativa = db.query(models.Tentativa).filter(models.Tentativa.id == tentativa_id).first()
    if not tentativa:
        raise HTTPException(status_code=404, detail="Tentativa não encontrada.")
    if tentativa.aluno_id != aluno.id:
        raise HTTPException(status_code=403, detail="Essa tentativa não pertence a você.")
    if tentativa.status != "CONCLUIDA":
        raise HTTPException(status_code=400, detail="Simulado ainda não finalizado.")

    respostas = db.query(models.Resposta).filter(models.Resposta.tentativa_id == tentativa.id).all()
    # A-05 / LOGICA-11/12: SIMULADO detalha escolhida x correta; CERTIFICACAO
    # NÃO expõe gabarito (incluir_gabarito=False) — só aprovado/reprovado e nota.
    detalhes = []
    if incluir_gabarito:
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
        "nota": float(tentativa.nota or 0),
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
    _verificar_tempo(tentativa, db)

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

    alternativas = _alternativas_ordenadas(questao, tentativa)
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


def listar_questoes_exam(tentativa_id: int, aluno: models.Usuario, db: Session) -> dict:
    """Retorna TODAS as questões da tentativa na ordem persistida, com as
    alternativas públicas (sem gabarito) e o mapa de respostas já dadas — para o
    front carregar a prova inteira e navegar/pular/trocar respostas livremente."""
    tentativa = db.query(models.Tentativa).filter(models.Tentativa.id == tentativa_id).first()
    if not tentativa:
        raise HTTPException(status_code=404, detail="Tentativa não encontrada.")
    if tentativa.aluno_id != aluno.id:
        raise HTTPException(status_code=403, detail="Essa tentativa não pertence a você.")
    if tentativa.status == "PAUSADO":
        raise HTTPException(status_code=400, detail="Retome o simulado antes de continuar.")
    if tentativa.status != "EM_ANDAMENTO":
        raise HTTPException(status_code=400, detail="Este simulado já foi finalizado.")
    _verificar_tempo(tentativa, db)

    ordem_raw = json.loads(tentativa.ordem_questoes) if tentativa.ordem_questoes else []
    ordem_ids = ordem_raw if isinstance(ordem_raw, list) else ordem_raw.get("ordem_ids", [])

    respostas = db.query(models.Resposta).filter(
        models.Resposta.tentativa_id == tentativa.id
    ).all()
    resp_map = {str(r.questao_id): r.alternativa_id for r in respostas}

    questoes_out = []
    for i, qid in enumerate(ordem_ids):
        questao = db.query(models.Questao).filter(models.Questao.id == qid).first()
        if not questao:
            continue
        questoes_out.append({
            "questao_id": questao.id,
            "enunciado": questao.enunciado,
            "numero": i + 1,
            "imagem_url": questao.imagem_url,
            "alternativas": _alternativas_ordenadas(questao, tentativa),
        })

    tempo_restante = None
    if tentativa.prova.tempo_limite:
        seg = _segundos_passados(tentativa)
        tempo_restante = max(0, tentativa.prova.tempo_limite * 60 - seg)

    return {
        "tentativa_id": tentativa.id,
        "tipo": tentativa.tipo,
        "total_questoes": len(ordem_ids),
        "tempo_restante_segundos": tempo_restante,
        "modalidade": tentativa.modalidade,
        "questoes": questoes_out,
        "respostas": resp_map,
    }


def finalizar_simulado(tentativa_id: int, aluno: models.Usuario, db: Session) -> dict:
    """Finaliza a tentativa AGORA (explícito): calcula a nota com base nas
    respostas dadas (não respondidas contam como erradas). Idempotente se a
    tentativa já estiver concluída."""
    tentativa = db.query(models.Tentativa).filter(models.Tentativa.id == tentativa_id).first()
    if not tentativa:
        raise HTTPException(status_code=404, detail="Tentativa não encontrada.")
    if tentativa.aluno_id != aluno.id:
        raise HTTPException(status_code=403, detail="Essa tentativa não pertence a você.")

    ordem_raw = json.loads(tentativa.ordem_questoes) if tentativa.ordem_questoes else []
    ordem_ids = ordem_raw if isinstance(ordem_raw, list) else ordem_raw.get("ordem_ids", [])
    total = len(ordem_ids)
    respondidas = db.query(models.Resposta).filter(
        models.Resposta.tentativa_id == tentativa.id
    ).count()

    if tentativa.status == "CONCLUIDA":
        return {
            "finalizado": True,
            "nota": float(tentativa.nota or 0),
            "resultado": tentativa.resultado or "REPROVADO",
            "total_questoes": total,
            "total_respondidas": respondidas,
        }
    if tentativa.status not in ("EM_ANDAMENTO", "PAUSADO"):
        raise HTTPException(status_code=400, detail="Tentativa não pode ser finalizada.")

    acertos = db.query(models.Resposta).filter(
        models.Resposta.tentativa_id == tentativa.id,
        models.Resposta.is_correta == True,
    ).count()
    nota = round((acertos / total) * 10, 2) if total else 0.0
    tentativa.status = "CONCLUIDA"
    tentativa.data_fim = datetime.now(timezone.utc)
    tentativa.nota = nota
    tentativa.resultado = "APROVADO" if nota >= (tentativa.prova.nota_minima or 6.0) else "REPROVADO"
    db.commit()

    return {
        "finalizado": True,
        "nota": nota,
        "resultado": tentativa.resultado,
        "total_questoes": total,
        "total_respondidas": respondidas,
    }