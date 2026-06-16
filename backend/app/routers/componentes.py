"""
Router: /componentes  — Componentes Curriculares (US36, US37, US38)

US36 — Admin cadastra disciplinas (Matemática, Português, etc.)
US37 — Prova pode ter um ou mais componentes (vinculação via provas_componentes)
US38 — Cada questão pertence a um componente (campo componente_id em Questao)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app import models
from app.dependencies import get_usuario_admin, get_usuario_atual

router = APIRouter(prefix="/componentes", tags=["Componentes Curriculares (US36-38)"])


# ─── Schemas inline (adicione ao schemas.py se preferir centralizar) ──────────

class ComponenteCreate(BaseModel):
    nome: str
    codigo: Optional[str] = None
    descricao: Optional[str] = None
    nivel: Optional[str] = None
    serie: Optional[str] = None


class ComponenteUpdate(BaseModel):
    nome: Optional[str] = None
    codigo: Optional[str] = None
    descricao: Optional[str] = None
    nivel: Optional[str] = None
    serie: Optional[str] = None


class ComponenteResponse(BaseModel):
    id: int
    nome: str
    codigo: Optional[str] = None
    descricao: Optional[str] = None
    nivel: Optional[str] = None
    serie: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/", response_model=ComponenteResponse, status_code=201,
             summary="Cadastrar componente curricular (US36)")
def criar_componente(
    dados: ComponenteCreate,
    db: Session = Depends(get_db),
    _admin=Depends(get_usuario_admin),
):
    """
    Admin cadastra uma nova disciplina/componente curricular.
    Retorna 409 se já existe um componente com o mesmo nome.
    """
    nome = dados.nome.strip()
    if len(nome) < 2:
        raise HTTPException(400, "Nome do componente deve ter pelo menos 2 caracteres.")

    duplicado = db.query(models.ComponenteCurricular).filter(
        models.ComponenteCurricular.nome == nome
    ).first()
    if duplicado:
        raise HTTPException(409, f"Já existe um componente com o nome '{nome}'.")

    comp = models.ComponenteCurricular(
        nome=nome,
        codigo=dados.codigo.strip().upper() if dados.codigo else None,
        descricao=dados.descricao,
        nivel=dados.nivel,
        serie=dados.serie,
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)
    return comp


@router.get("/", response_model=List[ComponenteResponse],
            summary="Listar todos os componentes curriculares")
def listar_componentes(
    nivel: Optional[str] = None,
    db: Session = Depends(get_db),
    _usuario=Depends(get_usuario_atual),
):
    """
    Lista componentes. Qualquer usuário autenticado pode consultar
    (necessário para preencher selects no frontend).
    Filtro opcional por nível.
    """
    q = db.query(models.ComponenteCurricular)
    if nivel:
        q = q.filter(models.ComponenteCurricular.nivel == nivel)
    return q.order_by(models.ComponenteCurricular.nome).all()


@router.get("/{comp_id}", response_model=ComponenteResponse,
            summary="Detalhe de um componente curricular")
def buscar_componente(
    comp_id: int,
    db: Session = Depends(get_db),
    _usuario=Depends(get_usuario_atual),
):
    comp = db.query(models.ComponenteCurricular).filter(
        models.ComponenteCurricular.id == comp_id
    ).first()
    if not comp:
        raise HTTPException(404, "Componente não encontrado.")
    return comp


@router.put("/{comp_id}", response_model=ComponenteResponse,
            summary="Editar componente curricular (US36)")
def editar_componente(
    comp_id: int,
    dados: ComponenteUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(get_usuario_admin),
):
    comp = db.query(models.ComponenteCurricular).filter(
        models.ComponenteCurricular.id == comp_id
    ).first()
    if not comp:
        raise HTTPException(404, "Componente não encontrado.")

    if dados.nome is not None:
        nome = dados.nome.strip()
        if len(nome) < 2:
            raise HTTPException(400, "Nome deve ter pelo menos 2 caracteres.")
        duplicado = db.query(models.ComponenteCurricular).filter(
            models.ComponenteCurricular.nome == nome,
            models.ComponenteCurricular.id != comp_id,
        ).first()
        if duplicado:
            raise HTTPException(409, f"Já existe outro componente com o nome '{nome}'.")
        comp.nome = nome

    if dados.codigo is not None:
        comp.codigo = dados.codigo.strip().upper() or None
    if dados.descricao is not None:
        comp.descricao = dados.descricao
    if dados.nivel is not None:
        comp.nivel = dados.nivel or None
    if dados.serie is not None:
        comp.serie = dados.serie or None

    db.commit()
    db.refresh(comp)
    return comp


@router.delete("/{comp_id}", status_code=204,
               summary="Excluir componente curricular")
def excluir_componente(
    comp_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_usuario_admin),
):
    comp = db.query(models.ComponenteCurricular).filter(
        models.ComponenteCurricular.id == comp_id
    ).first()
    if not comp:
        raise HTTPException(404, "Componente não encontrado.")

    # Não bloqueia exclusão, mas as questões vinculadas perderão o componente_id
    # (a FK é nullable, então não há risco de erro de integridade referencial)
    db.delete(comp)
    db.commit()


# ─── US37: vincular / desvincular componentes de uma prova ───────────────────

@router.post("/prova/{prova_id}/vincular",
             summary="Vincular componente a uma prova (US37)",
             status_code=204)
def vincular_componente_prova(
    prova_id: int,
    comp_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_usuario_admin),
):
    """
    Vincula um componente curricular a uma prova (tabela provas_componentes).
    Idempotente — não lança erro se o vínculo já existir.
    """
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.deleted == False,
    ).first()
    if not prova:
        raise HTTPException(404, "Prova não encontrada.")

    comp = db.query(models.ComponenteCurricular).filter(
        models.ComponenteCurricular.id == comp_id
    ).first()
    if not comp:
        raise HTTPException(404, "Componente não encontrado.")

    if comp not in prova.componentes:
        prova.componentes.append(comp)
        db.commit()


@router.delete("/prova/{prova_id}/vincular",
               summary="Desvincular componente de uma prova (US37)",
               status_code=204)
def desvincular_componente_prova(
    prova_id: int,
    comp_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(get_usuario_admin),
):
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.deleted == False,
    ).first()
    if not prova:
        raise HTTPException(404, "Prova não encontrada.")

    comp = db.query(models.ComponenteCurricular).filter(
        models.ComponenteCurricular.id == comp_id
    ).first()
    if not comp:
        raise HTTPException(404, "Componente não encontrado.")

    if comp in prova.componentes:
        prova.componentes.remove(comp)
        db.commit()