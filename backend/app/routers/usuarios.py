"""
Router de usuários — US33 (importação) + US40 (gestão admin) + US30 (atualizar perfil).
Substitui o arquivo backend/app/routers/usuarios.py que estava vazio.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app import models, schemas
from app.dependencies import get_usuario_atual, get_usuario_admin
from app.services import importacao_service
from app.security import hash_senha

router = APIRouter(prefix="/usuarios", tags=["Usuários"])

# US33 — Importar alunos via CSV/Excel

@router.post(
    "/importar",
    summary="Importa alunos via CSV ou Excel (US33)",
    status_code=201,
)
async def importar_alunos(
    arquivo: UploadFile = File(
        ...,
        description="Arquivo .csv ou .xlsx com colunas: nome, email, nivel, serie",
    ),
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    """
    Importa alunos em lote a partir de um arquivo CSV ou Excel.

    **Colunas obrigatórias:** `nome`, `email`, `nivel`

    **Colunas opcionais:** `serie`

    **Valores válidos para `nivel`:** `FUNDAMENTAL_I`, `FUNDAMENTAL_II`, `MEDIO`, `ENEM`, `EJA`

    O sistema gera uma senha provisória para cada aluno importado.
    O administrador deve comunicá-la ao aluno, que deve trocá-la no primeiro acesso.

    **Retorna:**
    - `total_importados`: alunos criados com sucesso
    - `total_duplicados`: e-mails já existentes (ignorados)
    - `total_erros`: linhas com dados inválidos (ignoradas)
    - `importados`: lista com dados e senha provisória de cada aluno criado
    - `duplicados` e `erros`: detalhes para correção
    """
    return await importacao_service.importar_alunos(arquivo, db)


@router.get(
    "/importar/modelo",
    summary="Baixa arquivo modelo para importação (US33)",
    response_class=Response,
)
def baixar_modelo_importacao(
    admin: models.Usuario = Depends(get_usuario_admin),
):
    """
    Retorna um arquivo .xlsx de exemplo com as colunas corretas e
    dados de demonstração para o admin preencher e enviar no import.
    """
    xlsx_bytes = importacao_service.gerar_modelo_xlsx()
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=modelo_importacao_alunos.xlsx"},
    )

# US40 — Gestão de usuários (admin)

@router.get(
    "/",
    summary="Lista todos os usuários (US40)",
)
def listar_usuarios(
    perfil: Optional[str] = None,
    status_usuario: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    """Filtra por `perfil` (ADMIN|ALUNO) e/ou `status_usuario` (ATIVO|BLOQUEADO)."""
    query = db.query(models.Usuario)
    if perfil:
        query = query.filter(models.Usuario.perfil == perfil.upper())
    if status_usuario:
        query = query.filter(models.Usuario.status == status_usuario.upper())

    total = query.count()
    usuarios = query.order_by(models.Usuario.nome).offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "usuarios": [
            {
                "id": u.id,
                "nome": u.nome,
                "email": u.email,
                "perfil": u.perfil,
                "nivel": u.nivel,
                "serie": u.serie,
                "status": u.status,
                "created_at": u.created_at,
            }
            for u in usuarios
        ],
    }


@router.get(
    "/{usuario_id}",
    response_model=schemas.UsuarioResponse,
    summary="Busca usuário por ID (US40)",
)
def buscar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return usuario


@router.put(
    "/{usuario_id}",
    response_model=schemas.UsuarioResponse,
    summary="Edita dados de um usuário (US40)",
)
def editar_usuario(
    usuario_id: int,
    dados: schemas.UsuarioUpdate,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        if campo == "senha" and valor:
            setattr(usuario, "senha_hash", hash_senha(valor))
        else:
            setattr(usuario, campo, valor)

    db.commit()
    db.refresh(usuario)
    return usuario


@router.patch(
    "/{usuario_id}/bloquear",
    response_model=schemas.UsuarioResponse,
    summary="Bloqueia um usuário (US40)",
)
def bloquear_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if usuario.id == admin.id:
        raise HTTPException(status_code=400, detail="Você não pode bloquear sua própria conta.")
    if usuario.status == "BLOQUEADO":
        raise HTTPException(status_code=409, detail="Usuário já está bloqueado.")

    usuario.status = "BLOQUEADO"
    db.commit()
    db.refresh(usuario)
    return usuario


@router.patch(
    "/{usuario_id}/desbloquear",
    response_model=schemas.UsuarioResponse,
    summary="Desbloqueia um usuário (US40)",
)
def desbloquear_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if usuario.status == "ATIVO":
        raise HTTPException(status_code=409, detail="Usuário já está ativo.")

    usuario.status = "ATIVO"
    db.commit()
    db.refresh(usuario)
    return usuario


@router.delete(
    "/{usuario_id}",
    status_code=204,
    summary="Remove um usuário (US40)",
)
def deletar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if usuario.id == admin.id:
        raise HTTPException(status_code=400, detail="Você não pode excluir sua própria conta.")

    tentativas = db.query(models.Tentativa).filter(
        models.Tentativa.aluno_id == usuario_id
    ).first()
    if tentativas:
        raise HTTPException(
            status_code=409,
            detail="Não é possível excluir usuário com tentativas registradas. Bloqueie-o em vez disso.",
        )

    db.delete(usuario)
    db.commit()

# US30 — Aluno atualiza próprio perfil (nível/série/localização)

@router.patch(
    "/me/perfil",
    response_model=schemas.UsuarioResponse,
    summary="Aluno atualiza seu próprio nível e série (US30)",
)
def atualizar_meu_perfil(
    dados: schemas.AlunoPatchPerfil,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_atual),
):
    """Permite ao aluno alterar seu nível de ensino e série a qualquer momento."""
    if dados.nivel:
        usuario.nivel = dados.nivel
    if dados.serie is not None:
        usuario.serie = dados.serie
    db.commit()
    db.refresh(usuario)
    return usuario


@router.patch(
    "/me/localizacao",
    response_model=schemas.UsuarioResponse,
    summary="Aluno atualiza sua localização (US24)",
)
def atualizar_minha_localizacao(
    dados: schemas.AlunoLocalizacao,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_usuario_atual),
):
    """
    Salva as coordenadas do aluno para uso em US25 (locais próximos).
    Validação: lat entre -90/90, lon entre -180/180.
    """
    usuario.latitude = dados.latitude
    usuario.longitude = dados.longitude
    db.commit()
    db.refresh(usuario)
    return usuario