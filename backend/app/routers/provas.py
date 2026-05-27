from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth import get_usuario_atual

router = APIRouter(
    prefix="/provas",
    tags=["Provas"]
)


def verificar_admin(usuario):
    if usuario.perfil != "admin":
        raise HTTPException(
            status_code=403,
            detail="Apenas admins podem acessar"
        )


@router.post("/", response_model=schemas.ProvaResponse)
def criar_prova(
    prova: schemas.ProvaCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_atual)
):
    verificar_admin(usuario)

    nova_prova = models.Prova(
        titulo=prova.titulo,
        descricao=prova.descricao,
        nivel=prova.nivel,
        serie=prova.serie,
        tipo=prova.tipo,
        nota_minima=prova.nota_minima,
        tempo_limite=prova.tempo_limite,
        status="RASCUNHO"
    )

    db.add(nova_prova)
    db.commit()
    db.refresh(nova_prova)

    return nova_prova


@router.get("/")
def listar_provas(
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_atual)
):

    if usuario.perfil == "admin":
        provas = db.query(models.Prova).filter(
            models.Prova.deleted == 0
        ).all()

    else:
        provas = db.query(models.Prova).filter(
            models.Prova.status == "PUBLICADA",
            models.Prova.deleted == 0
        ).all()

    return provas


@router.get("/{id}")
def buscar_prova(
    id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_atual)
):

    prova = db.query(models.Prova).filter(
        models.Prova.id == id,
        models.Prova.deleted == 0
    ).first()

    if not prova:
        raise HTTPException(
            status_code=404,
            detail="Prova não encontrada"
        )

    return prova


@router.put("/{id}", response_model=schemas.ProvaResponse)
def editar_prova(
    id: int,
    dados: schemas.ProvaCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_atual)
):

    verificar_admin(usuario)

    prova = db.query(models.Prova).filter(
        models.Prova.id == id,
        models.Prova.deleted == 0
    ).first()

    if not prova:
        raise HTTPException(
            status_code=404,
            detail="Prova não encontrada"
        )

    prova.titulo = dados.titulo
    prova.descricao = dados.descricao
    prova.nivel = dados.nivel
    prova.serie = dados.serie
    prova.tipo = dados.tipo
    prova.nota_minima = dados.nota_minima
    prova.tempo_limite = dados.tempo_limite

    db.commit()
    db.refresh(prova)

    return prova


@router.delete("/{id}")
def deletar_prova(
    id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_atual)
):

    verificar_admin(usuario)

    prova = db.query(models.Prova).filter(
        models.Prova.id == id,
        models.Prova.deleted == 0
    ).first()

    if not prova:
        raise HTTPException(
            status_code=404,
            detail="Prova não encontrada"
        )

    prova.deleted = 1

    db.commit()

    return {"message": "Prova deletada com sucesso"}