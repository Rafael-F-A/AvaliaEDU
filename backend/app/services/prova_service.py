from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app import models, schemas


def criar_prova(dados: schemas.ProvaCreate, criado_por: int, db: Session) -> models.Prova:
    """
    Cria uma prova com status inicial RASCUNHO.
    Apenas admins chegam aqui (verificado no router).
    """
    nova_prova = models.Prova(
        titulo=dados.titulo,
        descricao=dados.descricao,
        nivel=dados.nivel,
        serie=dados.serie,
        tipo=dados.tipo,
        nota_minima=dados.nota_minima,
        tempo_limite=dados.tempo_limite,
        status="RASCUNHO",
        criado_por=criado_por,
    )
    db.add(nova_prova)
    db.commit()
    db.refresh(nova_prova)
    return nova_prova


def listar_provas(
    db: Session,
    usuario: models.Usuario,
    nivel: Optional[str] = None,
    serie: Optional[str] = None,
    tipo: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
) -> dict:
    """
    Lista provas com filtros e paginação.
    - Admin vê todas (inclusive rascunhos)
    - Aluno vê apenas PUBLICADAS e compatíveis com seu nível (US14)
    """
    query = db.query(models.Prova).filter(models.Prova.deleted == False)

    if usuario.perfil != "ADMIN":
        query = query.filter(models.Prova.status == "PUBLICADA")
        if usuario.nivel:
            query = query.filter(models.Prova.nivel == usuario.nivel)

    if nivel:
        query = query.filter(models.Prova.nivel == nivel)
    if serie:
        query = query.filter(models.Prova.serie == serie)
    if tipo:
        query = query.filter(models.Prova.tipo == tipo)

    total = query.count()
    provas = query.order_by(models.Prova.created_at.desc()).offset(skip).limit(limit).all()

    return {"total": total, "provas": provas}


def buscar_prova_por_id(prova_id: int, usuario: models.Usuario, db: Session) -> models.Prova:
    """
    Retorna uma prova pelo ID.
    - Aluno não acessa provas não publicadas (403)
    - Qualquer perfil recebe 404 se a prova não existir ou estiver deletada
    """
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.deleted == False,
    ).first()

    if not prova:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prova não encontrada.")

    if usuario.perfil != "ADMIN" and prova.status != "PUBLICADA":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")

    return prova


def editar_prova(prova_id: int, dados: schemas.ProvaUpdate, db: Session) -> models.Prova:
    """
    Atualiza apenas os campos enviados (PATCH semântico via ProvaUpdate).
    - Bloqueia edição de provas PUBLICADAS (409)
    - Bloquear edição se alunos já iniciaram (verifica tentativas EM_ANDAMENTO)
    """
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.deleted == False,
    ).first()

    if not prova:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prova não encontrada.")

    if prova.status == "PUBLICADA":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Prova publicada não pode ser editada. Altere o status para 'RASCUNHO' primeiro.",
        )

    tentativas_ativas = db.query(models.Tentativa).filter(
        models.Tentativa.prova_id == prova_id,
        models.Tentativa.status == "EM_ANDAMENTO",
    ).first()

    if tentativas_ativas:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não é possível editar uma prova enquanto alunos estão realizando-a.",
        )

    for campo, valor in dados.dict(exclude_unset=True).items():
        setattr(prova, campo, valor)

    db.commit()
    db.refresh(prova)
    return prova


def deletar_prova(prova_id: int, db: Session) -> None:
    """
    Soft delete da prova.
    - Impede deleção se existirem tentativas vinculadas
    """
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.deleted == False,
    ).first()

    if not prova:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prova não encontrada.")

    tentativas = db.query(models.Tentativa).filter(
        models.Tentativa.prova_id == prova_id
    ).first()

    if tentativas:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não é possível excluir uma prova que já possui tentativas registradas.",
        )

    prova.deleted = True
    db.commit()


def publicar_prova(prova_id: int, db: Session) -> models.Prova:
    """
    Publica uma prova (RASCUNHO → PUBLICADA).
    Valida que a prova tem pelo menos 1 questão antes de publicar.
    """
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.deleted == False,
    ).first()

    if not prova:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prova não encontrada.")

    if prova.status == "PUBLICADA":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Prova já está publicada.",
        )

    total_questoes = db.query(models.Questao).filter(
        models.Questao.prova_id == prova_id
    ).count()

    if total_questoes == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Não é possível publicar uma prova sem questões.",
        )

    prova.status = "PUBLICADA"
    db.commit()
    db.refresh(prova)
    return prova
