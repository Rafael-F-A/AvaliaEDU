import os
import base64
import binascii
import tempfile
from typing import Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.utils.storage import upload_imagem_questao, upload_imagem_alternativa

EXTENSOES_PERMITIDAS = {"image/jpeg", "image/png", "image/webp"}
TAMANHO_MAXIMO = 5 * 1024 * 1024  # 5 MB


def _upload_base64(b64: str, upload_fn, owner_id: int) -> str:
    """Decodifica uma imagem (data URL ou base64 puro), valida e sobe ao storage.

    Usado para anexar imagem ao CRIAR/EDITAR a questão — sem exigir um upload
    separado depois de salvar. Retorna a URL assinada.
    """
    if b64.startswith("data:"):
        try:
            header, dados = b64.split(",", 1)
            mime = header.split(";")[0][len("data:"):]
        except ValueError:
            raise HTTPException(status_code=400, detail="Imagem base64 inválida.")
    else:
        dados = b64
        mime = "image/png"

    if mime not in EXTENSOES_PERMITIDAS:
        raise HTTPException(status_code=400, detail="Formato inválido. Use PNG, JPG ou WEBP.")

    try:
        raw = base64.b64decode(dados, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Imagem base64 inválida.")

    if len(raw) > TAMANHO_MAXIMO:
        raise HTTPException(status_code=400, detail="Imagem muito grande. Máximo 5MB.")

    ext = mime.split("/")[1]
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name
    try:
        return upload_fn(tmp_path, owner_id, ext)
    finally:
        os.unlink(tmp_path)

# Validação de alternativas

def _validar_alternativas(alternativas: list) -> None:
    if len(alternativas) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A questão deve ter no mínimo 2 alternativas.",
        )

    textos_vazios = [
        a for a in alternativas
        if (not a.texto or not a.texto.strip())
        and not a.imagem_url
        and not getattr(a, "imagem_base64", None)
    ]
    if textos_vazios:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nenhuma alternativa pode ter texto e imagem vazios ao mesmo tempo.",
        )

    total_corretas = sum(1 for a in alternativas if a.is_correta)
    if total_corretas == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A questão deve ter exatamente 1 alternativa correta. Nenhuma foi marcada.",
        )
    if total_corretas > 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"A questão deve ter exatamente 1 alternativa correta. {total_corretas} foram marcadas.",
        )


def _obter_prova_editavel(prova_id: int, db: Session) -> models.Prova:
    """
    Carrega a prova e garante que ela pode receber alterações de questões.

    Regras de proteção (preserva o gabarito de respostas já registradas):
    - Só prova em RASCUNHO pode ter questões criadas/editadas/excluídas.
    - Prova PUBLICADA é bloqueada (altere para RASCUNHO primeiro).
    - Se já existem tentativas vinculadas, qualquer alteração é bloqueada,
      pois mudar o gabarito invalidaria respostas já registradas.
    """
    prova = db.query(models.Prova).filter(models.Prova.id == prova_id).first()
    if not prova:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")

    if prova.status == "PUBLICADA":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Prova publicada não pode ter suas questões alteradas. Altere o status para RASCUNHO primeiro.",
        )

    tem_tentativas = db.query(models.Tentativa).filter(
        models.Tentativa.prova_id == prova_id,
    ).first()
    if tem_tentativas:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A prova já possui tentativas registradas; suas questões não podem mais ser alteradas para preservar o gabarito das respostas já registradas.",
        )

    return prova

# CRUD de questões

def criar_questao(dados: schemas.QuestaoCreate, db: Session) -> models.Questao:
    _validar_alternativas(dados.alternativas)

    # Só permite vincular/criar questão em prova RASCUNHO (e sem tentativas).
    prova = _obter_prova_editavel(dados.prova_id, db)

    nova_questao = models.Questao(
        enunciado=dados.enunciado,
        prova_id=dados.prova_id,
        nivel_dificuldade=dados.nivel_dificuldade,
        imagem_url=dados.imagem_url,
    )
    db.add(nova_questao)
    db.flush()

    # Imagem anexada antes de salvar (base64) — sobe agora que a questão tem id.
    if dados.imagem_base64:
        nova_questao.imagem_url = _upload_base64(
            dados.imagem_base64, upload_imagem_questao, nova_questao.id
        )

    alt_objs = []
    for idx, alt in enumerate(dados.alternativas):
        a = models.Alternativa(
            texto=alt.texto.strip() if alt.texto else "",
            questao_id=nova_questao.id,
            is_correta=alt.is_correta,
            ordem=alt.ordem if alt.ordem is not None else idx,
            imagem_url=alt.imagem_url,
        )
        db.add(a)
        alt_objs.append((a, alt))
    db.flush()  # garante os ids das alternativas

    for a, alt in alt_objs:
        if getattr(alt, "imagem_base64", None):
            a.imagem_url = _upload_base64(alt.imagem_base64, upload_imagem_alternativa, a.id)

    db.commit()
    db.refresh(nova_questao)
    return nova_questao


def listar_questoes(db: Session, prova_id: Optional[int] = None) -> list:
    query = db.query(models.Questao)
    if prova_id:
        query = query.filter(models.Questao.prova_id == prova_id)
    return query.order_by(models.Questao.ordem).all()


def editar_questao(questao_id: int, dados: schemas.QuestaoCreate, db: Session) -> models.Questao:
    _validar_alternativas(dados.alternativas)

    questao = db.query(models.Questao).filter(models.Questao.id == questao_id).first()
    if not questao:
        raise HTTPException(status_code=404, detail="Questão não encontrada.")

    # Bloqueia edição se a prova estiver PUBLICADA ou já tiver tentativas.
    _obter_prova_editavel(questao.prova_id, db)

    questao.enunciado = dados.enunciado
    questao.nivel_dificuldade = dados.nivel_dificuldade
    questao.imagem_url = dados.imagem_url
    if dados.imagem_base64:
        questao.imagem_url = _upload_base64(
            dados.imagem_base64, upload_imagem_questao, questao.id
        )

    db.query(models.Alternativa).filter(
        models.Alternativa.questao_id == questao_id
    ).delete()

    alt_objs = []
    for idx, alt in enumerate(dados.alternativas):
        a = models.Alternativa(
            texto=alt.texto.strip() if alt.texto else "",
            questao_id=questao.id,
            is_correta=alt.is_correta,
            ordem=alt.ordem if alt.ordem is not None else idx,
            imagem_url=alt.imagem_url,
        )
        db.add(a)
        alt_objs.append((a, alt))
    db.flush()  # garante os ids das alternativas

    for a, alt in alt_objs:
        if getattr(alt, "imagem_base64", None):
            a.imagem_url = _upload_base64(alt.imagem_base64, upload_imagem_alternativa, a.id)

    db.commit()
    db.refresh(questao)
    return questao


def excluir_questao(questao_id: int, db: Session) -> None:
    questao = db.query(models.Questao).filter(models.Questao.id == questao_id).first()
    if not questao:
        raise HTTPException(status_code=404, detail="Questão não encontrada.")

    # Bloqueia exclusão se a prova estiver PUBLICADA ou já tiver tentativas,
    # preservando o gabarito das respostas já registradas.
    _obter_prova_editavel(questao.prova_id, db)

    db.delete(questao)
    db.commit()


def listar_alternativas(questao_id: int, db: Session) -> list:
    questao = db.query(models.Questao).filter(models.Questao.id == questao_id).first()
    if not questao:
        raise HTTPException(status_code=404, detail="Questão não encontrada.")
    return (
        db.query(models.Alternativa)
        .filter(models.Alternativa.questao_id == questao_id)
        .order_by(models.Alternativa.ordem)
        .all()
    )

# Upload de imagem de questão

def fazer_upload_imagem(questao_id: int, arquivo: UploadFile, db: Session) -> str:
    if arquivo.content_type not in EXTENSOES_PERMITIDAS:
        raise HTTPException(status_code=400, detail="Formato inválido. Use PNG, JPG ou WEBP.")

    questao = db.query(models.Questao).filter(models.Questao.id == questao_id).first()
    if not questao:
        raise HTTPException(status_code=404, detail="Questão não encontrada.")

    extensao = arquivo.content_type.split("/")[1]

    with tempfile.NamedTemporaryFile(suffix=f".{extensao}", delete=False) as tmp:
        conteudo = arquivo.file.read()
        if len(conteudo) > TAMANHO_MAXIMO:
            raise HTTPException(status_code=400, detail="Imagem muito grande. Máximo 5MB.")
        tmp.write(conteudo)
        tmp_path = tmp.name

    try:
        url = upload_imagem_questao(tmp_path, questao_id, extensao)
    finally:
        os.unlink(tmp_path)

    questao.imagem_url = url
    db.commit()
    db.refresh(questao)
    return url

# Upload de imagem de alternativa individual

def fazer_upload_imagem_alternativa(
    questao_id: int,
    alternativa_id: int,
    arquivo: UploadFile,
    db: Session,
) -> str:
    """
    Faz upload de imagem para uma alternativa específica.

    Valida que:
    - Alternativa existe e pertence à questão informada
    - Formato é PNG, JPG ou WEBP
    - Tamanho máximo 5 MB

    Atualiza alternativa.imagem_url e retorna a URL assinada.
    """
    if arquivo.content_type not in EXTENSOES_PERMITIDAS:
        raise HTTPException(status_code=400, detail="Formato inválido. Use PNG, JPG ou WEBP.")

    # Verifica que a alternativa existe E pertence à questão correta
    alternativa = db.query(models.Alternativa).filter(
        models.Alternativa.id == alternativa_id,
        models.Alternativa.questao_id == questao_id,
    ).first()

    if not alternativa:
        raise HTTPException(
            status_code=404,
            detail=f"Alternativa {alternativa_id} não encontrada na questão {questao_id}.",
        )

    extensao = arquivo.content_type.split("/")[1]

    with tempfile.NamedTemporaryFile(suffix=f".{extensao}", delete=False) as tmp:
        conteudo = arquivo.file.read()
        if len(conteudo) > TAMANHO_MAXIMO:
            raise HTTPException(status_code=400, detail="Imagem muito grande. Máximo 5 MB.")
        tmp.write(conteudo)
        tmp_path = tmp.name

    try:
        url = upload_imagem_alternativa(tmp_path, alternativa_id, extensao)
    finally:
        os.unlink(tmp_path)

    alternativa.imagem_url = url
    db.commit()
    db.refresh(alternativa)
    return url

# Remover imagem de alternativa

def remover_imagem_alternativa(
    questao_id: int,
    alternativa_id: int,
    db: Session,
) -> None:
    """Remove o campo imagem_url da alternativa (não apaga do Storage)."""
    alternativa = db.query(models.Alternativa).filter(
        models.Alternativa.id == alternativa_id,
        models.Alternativa.questao_id == questao_id,
    ).first()

    if not alternativa:
        raise HTTPException(
            status_code=404,
            detail=f"Alternativa {alternativa_id} não encontrada na questão {questao_id}.",
        )

    # Validação: alternativa não pode ficar sem texto E sem imagem
    if not alternativa.texto or not alternativa.texto.strip():
        raise HTTPException(
            status_code=400,
            detail="Não é possível remover a imagem de uma alternativa sem texto. Adicione um texto primeiro.",
        )

    alternativa.imagem_url = None
    db.commit()