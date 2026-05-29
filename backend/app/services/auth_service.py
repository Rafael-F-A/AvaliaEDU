from datetime import timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app import models, schemas
from app.security import hash_senha, verificar_senha, criar_token
import os

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24))


def registrar_usuario(dados: schemas.UsuarioCreate, db: Session) -> models.Usuario:
    """
    Cria um novo usuário.
    - Verifica se o e-mail já está cadastrado (409)
    - Nunca armazena a senha em texto puro
    """
    email_ja_existe = db.query(models.Usuario).filter(
        models.Usuario.email == dados.email
    ).first()

    if email_ja_existe:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-mail já cadastrado.",
        )

    novo_usuario = models.Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_senha(dados.senha),
        perfil=dados.perfil,
        nivel=dados.nivel,
        serie=dados.serie,
    )
    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)
    return novo_usuario


def autenticar_usuario(dados: schemas.UsuarioLogin, db: Session) -> dict:
    """
    Valida credenciais e retorna token JWT + dados do usuário.
    - Mensagem genérica para não revelar se o e-mail existe
    - Token inclui e-mail como subject (sub)
    """
    usuario = db.query(models.Usuario).filter(
        models.Usuario.email == dados.email
    ).first()

    if not usuario or not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos.",
        )

    if usuario.status == "BLOQUEADO":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário bloqueado. Entre em contato com o administrador.",
        )

    token = criar_token(
        data={"sub": usuario.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": usuario,
    }
