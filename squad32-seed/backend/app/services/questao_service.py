import os
import tempfile
from typing import Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.utils.storage import upload_imagem_questao, upload_imagem_alternativa

EXTENSOES_PERMITIDAS = {"image/jpeg", "image/png", "image/webp"}
TAMANHO_MAXIMO = 5 * 1024 * 1024  # 5 MB

# Validação de alternativas

def _validar_alternativas(alternativas: list) -> None:
    if len(alternativas) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A questão deve ter no mínimo 2 alternativas.",
        )

    textos_vazios = [
        a for a in alternativas
        if (not a.texto or not a.texto.strip()) and not a.imagem_url
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
    
# CRUD de questões

def criar_questao(dados: schemas.QuestaoCreate, db: Session) -> models.Questao:
    _validar_alternativas(dados.alternativas)

    prova = db.query(models.Prova).filter(models.Prova.id == dados.prova_id).first()
    if not prova:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")

    nova_questao = models.Questao(
        enunciado=dados.enunciado,
        prova_id=dados.prova_id,
        nivel_dificuldade=dados.nivel_dificuldade,
        imagem_url=dados.imagem_url,
    )
    db.add(nova_questao)
    db.flush()

    for idx, alt in enumerate(dados.alternativas):
        db.add(models.Alternativa(
            texto=alt.texto.strip() if alt.texto else "",
            questao_id=nova_questao.id,
            is_correta=alt.is_correta,
            ordem=alt.ordem if alt.ordem is not None else idx,
            imagem_url=alt.imagem_url,   # NOVO
        ))

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

    questao.enunciado = dados.enunciado
    questao.nivel_dificuldade = dados.nivel_dificuldade
    questao.imagem_url = dados.imagem_url

    db.query(models.Alternativa).filter(
        models.Alternativa.questao_id == questao_id
    ).delete()

    for idx, alt in enumerate(dados.alternativas):
        db.add(models.Alternativa(
            texto=alt.texto.strip() if alt.texto else "",
            questao_id=questao.id,
            is_correta=alt.is_correta,
            ordem=alt.ordem if alt.ordem is not None else idx,
            imagem_url=alt.imagem_url,   # NOVO
        ))

    db.commit()
    db.refresh(questao)
    return questao


def excluir_questao(questao_id: int, db: Session) -> None:
    questao = db.query(models.Questao).filter(models.Questao.id == questao_id).first()
    if not questao:
        raise HTTPException(status_code=404, detail="Questão não encontrada.")
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