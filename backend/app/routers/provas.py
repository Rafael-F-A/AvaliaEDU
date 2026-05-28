from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas
from app.dependencies import get_usuario_atual, get_usuario_admin

router = APIRouter(prefix="/provas", tags=["Provas"])


@router.post("/", response_model=schemas.ProvaResponse, status_code=status.HTTP_201_CREATED)
def criar_prova(
    prova: schemas.ProvaCreate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_admin)
):
    """
    Cria uma nova prova com status inicial 'RASCUNHO'.
    Apenas administradores podem executar esta ação.
    """
    nova_prova = models.Prova(
        titulo=prova.titulo,
        descricao=prova.descricao,
        nivel=prova.nivel,
        serie=prova.serie,
        tipo=prova.tipo,
        nota_minima=prova.nota_minima,
        tempo_limite=prova.tempo_limite,
        status="RASCUNHO",
        criado_por=usuario.id
    )
    db.add(nova_prova)
    db.commit()
    db.refresh(nova_prova)
    return nova_prova


@router.get("/", response_model=List[schemas.ProvaResponse])
def listar_provas(
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_atual)
):
    """
    Lista todas as provas não deletadas.
    - Administradores veem todas (inclusive rascunhos).
    - Alunos veem apenas provas com status 'PUBLICADA'.
    """
    query = db.query(models.Prova).filter(models.Prova.deleted == False)
    if usuario.perfil != "ADMIN":
        query = query.filter(models.Prova.status == "PUBLICADA")
    return query.all()


@router.get("/{prova_id}", response_model=schemas.ProvaResponse)
def buscar_prova(
    prova_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_atual)
):
    """
    Busca uma prova específica pelo ID.
    - Alunos não podem acessar provas que não estejam publicadas.
    """
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.deleted == False
    ).first()
    if not prova:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")
    if usuario.perfil != "ADMIN" and prova.status != "PUBLICADA":
        raise HTTPException(status_code=403, detail="Acesso negado.")
    return prova


@router.put("/{prova_id}", response_model=schemas.ProvaResponse)
def editar_prova(
    prova_id: int,
    dados: schemas.ProvaUpdate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_admin)
):
    """
    Edita uma prova existente (apenas administradores).
    Provas com status 'PUBLICADA' não podem ser editadas diretamente.
    """
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.deleted == False
    ).first()
    if not prova:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")

    if prova.status == "PUBLICADA":
        raise HTTPException(
            status_code=409,
            detail="Prova publicada não pode ser editada. Altere o status para 'RASCUNHO' primeiro."
        )

    # Atualiza apenas os campos enviados (exclui None)
    for campo, valor in dados.dict(exclude_unset=True).items():
        setattr(prova, campo, valor)

    db.commit()
    db.refresh(prova)
    return prova


@router.delete("/{prova_id}", response_model=schemas.MensagemResponse)
def deletar_prova(
    prova_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_admin)
):
    """
    Realiza soft delete de uma prova (marca como deleted=True).
    Impede deleção se existirem tentativas (simulados) vinculadas a esta prova.
    """
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.deleted == False
    ).first()
    if not prova:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")

    # Verifica se há tentativas (simulados) usando esta prova
    tentativas_existentes = db.query(models.Tentativa).filter(
        models.Tentativa.prova_id == prova_id
    ).first()
    if tentativas_existentes:
        raise HTTPException(
            status_code=409,
            detail="Não é possível excluir uma prova que já possui tentativas registradas."
        )

    prova.deleted = True
    db.commit()
    return {"message": "Prova deletada com sucesso."}