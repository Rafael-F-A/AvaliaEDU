import os
import base64
import binascii
import tempfile
import random
import json
import re
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, UploadFile

from app import models, schemas
from app.utils.storage import upload_imagem_modelo_slot

_EXT_IMG = {"image/jpeg": "jpeg", "image/png": "png", "image/webp": "webp"}
_MAX_IMG = 5 * 1024 * 1024  # 5 MB


def _subir_imagem_base64_modelo(b64: str, modelo_id: int, slot: str) -> str:
    """Decodifica imagem (data URL/base64), valida e sobe ao storage do modelo
    com um nome único por slot (gabarito / distrator_N)."""
    if b64.startswith("data:"):
        try:
            header, dados = b64.split(",", 1)
            mime = header.split(";")[0][len("data:"):]
        except ValueError:
            raise HTTPException(status_code=400, detail="Imagem base64 inválida.")
    else:
        dados, mime = b64, "image/png"
    ext = _EXT_IMG.get(mime)
    if not ext:
        raise HTTPException(status_code=400, detail="Formato inválido. Use PNG, JPG ou WEBP.")
    try:
        raw = base64.b64decode(dados, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Imagem base64 inválida.")
    if len(raw) > _MAX_IMG:
        raise HTTPException(status_code=400, detail="Imagem muito grande. Máximo 5MB.")
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name
    try:
        return upload_imagem_modelo_slot(tmp_path, modelo_id, slot, ext)
    finally:
        os.unlink(tmp_path)


def _normalizar_distradores(raw) -> list:
    """Normaliza distradores legados (list[str]) e novos (list[{texto,imagem_url}])
    para sempre [{'texto': str, 'imagem_url': str|None}]."""
    out = []
    if isinstance(raw, list):
        for d in raw:
            if isinstance(d, str):
                out.append({"texto": d, "imagem_url": None})
            elif isinstance(d, dict):
                out.append({"texto": d.get("texto", ""), "imagem_url": d.get("imagem_url")})
    return out

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
    distradores = [
        {"texto": _aplicar_template(d["texto"], ctx), "imagem_url": d["imagem_url"]}
        for d in _normalizar_distradores(modelo.distradores)
    ]

    # Garante exatamente 3 distratores (preenche ou trunca)
    while len(distradores) < 3:
        distradores.append({"texto": f"(alternativa {len(distradores)+1})", "imagem_url": None})
    distradores = distradores[:3]

    questao = models.Questao(
        enunciado=enunciado,
        prova_id=prova_id,
        nivel_dificuldade=modelo.dificuldade,
        imagem_url=modelo.imagem_url,
    )
    db.add(questao)
    db.flush()  # obtém o ID sem commit

    # Cria alternativas: 1 correta + 3 distratores (com imagens), em ordem aleatória
    alternativas = [{"texto": gabarito, "is_correta": True, "imagem_url": modelo.gabarito_imagem_url}]
    alternativas += [
        {"texto": d["texto"], "is_correta": False, "imagem_url": d["imagem_url"]}
        for d in distradores
    ]
    random.shuffle(alternativas)

    for idx, a in enumerate(alternativas):
        db.add(models.Alternativa(
            texto=a["texto"],
            questao_id=questao.id,
            is_correta=a["is_correta"],
            ordem=idx,
            imagem_url=a["imagem_url"],
        ))

    return questao


def instanciar_modelo(modelo_id: int, db: Session) -> dict:
    """Resolve um modelo em uma questão concreta (variáveis sorteadas) SEM
    persistir. Usado para pré-preencher o modal de nova questão (US11)."""
    modelo = db.query(models.ModeloQuestao).filter(
        models.ModeloQuestao.id == modelo_id
    ).first()
    if not modelo:
        raise HTTPException(status_code=404, detail="Modelo não encontrado.")

    variaveis_def = modelo.variaveis if isinstance(modelo.variaveis, dict) else {}
    ctx = _resolver_variaveis(variaveis_def)

    enunciado = _aplicar_template(modelo.modelo_texto, ctx)
    gabarito  = _aplicar_template(modelo.gabarito or "", ctx)

    alternativas = [{"texto": gabarito, "is_correta": True, "imagem_url": modelo.gabarito_imagem_url}]
    alternativas += [
        {"texto": _aplicar_template(d["texto"], ctx), "is_correta": False, "imagem_url": d["imagem_url"]}
        for d in _normalizar_distradores(modelo.distradores)
    ]

    return {
        "enunciado": enunciado,
        "nivel_dificuldade": modelo.dificuldade,
        "componente_id": modelo.componente_id,
        "imagem_url": modelo.imagem_url,
        "alternativas": alternativas,
    }


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

def _processar_imagens_modelo(dados: schemas.ModeloQuestaoCreate, modelo_id: int):
    """Sobe as imagens enviadas em base64 (enunciado, gabarito e distratores) e
    devolve (imagem_enunciado_url, gabarito_imagem_url, distradores_json)."""
    img_enunciado = dados.imagem_url
    if dados.imagem_base64:
        img_enunciado = _subir_imagem_base64_modelo(dados.imagem_base64, modelo_id, "imagem")

    gab_img = dados.gabarito_imagem_url
    if dados.gabarito_imagem_base64:
        gab_img = _subir_imagem_base64_modelo(dados.gabarito_imagem_base64, modelo_id, "gabarito")

    distradores = []
    for i, d in enumerate(dados.distradores):
        url = d.imagem_url
        if d.imagem_base64:
            url = _subir_imagem_base64_modelo(d.imagem_base64, modelo_id, f"distrator_{i}")
        distradores.append({"texto": d.texto or "", "imagem_url": url})

    return img_enunciado, gab_img, distradores


def criar_modelo(dados: schemas.ModeloQuestaoCreate, db: Session) -> models.ModeloQuestao:
    """Cadastra um novo modelo de questão (com imagens de alternativas, se houver)."""
    modelo = models.ModeloQuestao(
        modelo_texto  = dados.modelo_texto,
        gabarito      = dados.gabarito,
        distradores   = [],
        variaveis     = dados.variaveis,
        nivel         = dados.nivel,
        serie         = dados.serie,
        componente_id = dados.componente_id,
        dificuldade   = dados.dificuldade,
    )
    db.add(modelo)
    db.flush()  # obtém o id para nomear as imagens

    img_en, gab_img, distradores = _processar_imagens_modelo(dados, modelo.id)
    modelo.imagem_url = img_en
    modelo.gabarito_imagem_url = gab_img
    modelo.distradores = distradores

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


def atualizar_modelo(
    modelo_id: int,
    dados: schemas.ModeloQuestaoCreate,
    db: Session,
) -> models.ModeloQuestao:
    """Edita um modelo de questão (substituição completa dos campos)."""
    modelo = db.query(models.ModeloQuestao).filter(
        models.ModeloQuestao.id == modelo_id
    ).first()
    if not modelo:
        raise HTTPException(status_code=404, detail="Modelo não encontrado.")

    modelo.modelo_texto  = dados.modelo_texto
    modelo.gabarito      = dados.gabarito
    modelo.variaveis     = dados.variaveis
    modelo.nivel         = dados.nivel
    modelo.serie         = dados.serie
    modelo.componente_id = dados.componente_id
    modelo.dificuldade   = dados.dificuldade

    img_en, gab_img, distradores = _processar_imagens_modelo(dados, modelo.id)
    modelo.imagem_url = img_en
    modelo.gabarito_imagem_url = gab_img
    modelo.distradores = distradores

    db.commit()
    db.refresh(modelo)
    return modelo


def deletar_modelo(modelo_id: int, db: Session) -> None:
    modelo = db.query(models.ModeloQuestao).filter(
        models.ModeloQuestao.id == modelo_id
    ).first()
    if not modelo:
        raise HTTPException(status_code=404, detail="Modelo não encontrado.")
    db.delete(modelo)
    db.commit()


def remover_imagem_modelo(modelo_id: int, db: Session) -> None:
    """Remove a imagem associada a um modelo (zera imagem_url)."""
    modelo = db.query(models.ModeloQuestao).filter(
        models.ModeloQuestao.id == modelo_id
    ).first()
    if not modelo:
        raise HTTPException(status_code=404, detail="Modelo não encontrado.")
    modelo.imagem_url = None
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