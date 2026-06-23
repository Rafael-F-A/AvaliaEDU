import os
import tempfile
import random
import json
import re
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, UploadFile

from app import models, schemas

# Helpers de template

_SAFE_NAMES = {"abs", "max", "min", "round", "int", "float", "str", "len"}

def _safe_eval(expr: str, ctx: dict) -> str:
    """Avalia uma expressão matemática simples usando apenas o contexto fornecido."""
    # Rejeita qualquer coisa com imports, dunder ou chamadas suspeitas
    if re.search(r"(__|\bimport\b|\bexec\b|\beval\b|open|os\.|sys\.)", expr):
        return expr
    try:
        result = eval(expr, {"__builtins__": {}}, ctx)  # noqa: S307
        # Formata inteiros sem casa decimal
        if isinstance(result, float) and result.is_integer():
            return str(int(result))
        return str(result)
    except Exception:
        return expr


def _resolver_variaveis(variaveis_def: Optional[dict]) -> dict:
    """Sorteia um valor de cada variável definida no modelo."""
    if not variaveis_def:
        return {}
    ctx = {}
    for nome, opcoes in variaveis_def.items():
        if isinstance(opcoes, list) and opcoes:
            ctx[nome] = random.choice(opcoes)
    return ctx


def _aplicar_template(texto: str, ctx: dict) -> str:
    """
    Substitui {var} pelo valor do contexto e {expressao} pelo resultado avaliado.
    Ex: "Quanto é {a} + {b}? Resultado: {a+b}" → "Quanto é 3 + 20? Resultado: 23"
    """
    if not ctx:
        return texto

    def substituir(match):
        expr = match.group(1).strip()
        # Variável simples
        if expr in ctx:
            return str(ctx[expr])
        # Expressão composta: tenta avaliar
        return _safe_eval(expr, ctx)

    return re.sub(r"\{([^}]+)\}", substituir, texto)

# Lógica principal

def _gerar_questao_a_partir_de_modelo(
    modelo: models.ModeloQuestao,
    prova_id: int,
    db: Session,
) -> models.Questao:
    """
    Instancia uma Questao real (persistida) a partir de um ModeloQuestao,
    substituindo os templates por valores únicos sorteados.
    """
    variaveis_def = modelo.variaveis if isinstance(modelo.variaveis, dict) else {}
    ctx = _resolver_variaveis(variaveis_def)

    enunciado   = _aplicar_template(modelo.modelo_texto, ctx)
    gabarito    = _aplicar_template(modelo.gabarito or "", ctx)
    distradores_raw = modelo.distradores if isinstance(modelo.distradores, list) else []
    distradores = [_aplicar_template(d, ctx) for d in distradores_raw]

    # Garante exatamente 3 distratores (preenche ou trunca)
    while len(distradores) < 3:
        distradores.append(f"(alternativa {len(distradores)+1})")
    distradores = distradores[:3]

    questao = models.Questao(
        enunciado=enunciado,
        prova_id=prova_id,
        nivel_dificuldade=modelo.dificuldade,
        imagem_url=modelo.imagem_url,
    )
    db.add(questao)
    db.flush()  # obtém o ID sem commit

    # Cria alternativas: 1 correta + 3 distratores, em ordem aleatória
    alternativas = [(gabarito, True)] + [(d, False) for d in distradores]
    random.shuffle(alternativas)

    for idx, (texto, is_correta) in enumerate(alternativas):
        db.add(models.Alternativa(
            texto=texto,
            questao_id=questao.id,
            is_correta=is_correta,
            ordem=idx,
        ))

    return questao


def gerar_questoes_para_prova(
    prova_id: int,
    quantidade: int,
    db: Session,
    nivel: Optional[str] = None,
    dificuldade: Optional[str] = None,
    componente_id: Optional[int] = None,
) -> dict:
    """
    US11 — Gera `quantidade` questões para a prova a partir do banco de modelos.
    """
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.deleted == False,
    ).first()

    if not prova:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")

    if prova.status == "PUBLICADA":
        raise HTTPException(
            status_code=409,
            detail="Não é possível gerar questões para uma prova já publicada.",
        )

    # Monta query de modelos
    query = db.query(models.ModeloQuestao)

    filtro_nivel = nivel or prova.nivel
    query = query.filter(models.ModeloQuestao.nivel == filtro_nivel)

    if dificuldade:
        query = query.filter(models.ModeloQuestao.dificuldade == dificuldade)
    if componente_id:
        query = query.filter(models.ModeloQuestao.componente_id == componente_id)

    modelos_disponiveis = query.all()

    if not modelos_disponiveis:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Nenhum modelo de questão encontrado para os filtros informados "
                f"(nível={filtro_nivel}, dificuldade={dificuldade or 'qualquer'})."
            ),
        )

    # Sem repetição: cada questão vem de um modelo DISTINTO (evita duplicar
    # enunciado/imagem). Se foram pedidas mais questões do que há modelos,
    # gera o máximo possível e devolve um aviso.
    n_gerar = min(quantidade, len(modelos_disponiveis))
    modelos_selecionados = random.sample(modelos_disponiveis, k=n_gerar)

    aviso = None
    if quantidade > len(modelos_disponiveis):
        aviso = (
            f"Você pediu {quantidade} questões, mas só há "
            f"{len(modelos_disponiveis)} modelo(s) para os filtros. "
            f"Foram geradas {len(modelos_disponiveis)} (sem repetir modelos). "
            "Cadastre mais modelos para gerar mais questões distintas."
        )

    geradas = []
    erros   = []

    for modelo in modelos_selecionados:
        try:
            q = _gerar_questao_a_partir_de_modelo(modelo, prova_id, db)
            geradas.append(q)
        except Exception as exc:
            erros.append({"modelo_id": modelo.id, "erro": str(exc)})

    db.commit()

    # Recarrega com alternativas para poder serializar
    for q in geradas:
        db.refresh(q)

    return {
        "prova_id"          : prova_id,
        "quantidade_gerada" : len(geradas),
        "quantidade_erros"  : len(erros),
        "erros"             : erros,
        "questoes"          : geradas,
        "aviso"             : aviso,
    }

# CRUD de modelos (admin)

def criar_modelo(dados: schemas.ModeloQuestaoCreate, db: Session) -> models.ModeloQuestao:
    """Cadastra um novo modelo de questão."""
    modelo = models.ModeloQuestao(
        modelo_texto  = dados.modelo_texto,
        gabarito      = dados.gabarito,
        distradores   = dados.distradores,
        variaveis     = dados.variaveis,
        nivel         = dados.nivel,
        serie         = dados.serie,
        componente_id = dados.componente_id,
        dificuldade   = dados.dificuldade,
    )
    db.add(modelo)
    db.commit()
    db.refresh(modelo)
    return modelo


def listar_modelos(
    db: Session,
    nivel: Optional[str] = None,
    dificuldade: Optional[str] = None,
    componente_id: Optional[int] = None,
) -> list:
    query = db.query(models.ModeloQuestao)
    if nivel:
        query = query.filter(models.ModeloQuestao.nivel == nivel)
    if dificuldade:
        query = query.filter(models.ModeloQuestao.dificuldade == dificuldade)
    if componente_id:
        query = query.filter(models.ModeloQuestao.componente_id == componente_id)
    return query.order_by(models.ModeloQuestao.id).all()


def deletar_modelo(modelo_id: int, db: Session) -> None:
    modelo = db.query(models.ModeloQuestao).filter(
        models.ModeloQuestao.id == modelo_id
    ).first()
    if not modelo:
        raise HTTPException(status_code=404, detail="Modelo não encontrado.")
    db.delete(modelo)
    db.commit()

def fazer_upload_imagem_modelo(modelo_id: int, arquivo, db: Session) -> str:
    EXTENSOES_PERMITIDAS = {"image/jpeg", "image/png", "image/webp"}
    TAMANHO_MAXIMO = 5 * 1024 * 1024

    if arquivo.content_type not in EXTENSOES_PERMITIDAS:
        raise HTTPException(400, "Formato inválido. Use PNG, JPG ou WEBP.")

    modelo = db.query(models.ModeloQuestao).filter(
        models.ModeloQuestao.id == modelo_id
    ).first()
    if not modelo:
        raise HTTPException(404, "Modelo não encontrado.")

    extensao = arquivo.content_type.split("/")[1]

    with tempfile.NamedTemporaryFile(suffix=f".{extensao}", delete=False) as tmp:
        conteudo = arquivo.file.read()
        if len(conteudo) > TAMANHO_MAXIMO:
            raise HTTPException(400, "Imagem muito grande. Máximo 5MB.")
        tmp.write(conteudo)
        tmp_path = tmp.name

    try:
        from app.utils.storage import upload_imagem_modelo
        url = upload_imagem_modelo(tmp_path, modelo_id, extensao)
    finally:
        os.unlink(tmp_path)

    modelo.imagem_url = url
    db.commit()
    db.refresh(modelo)
    return url