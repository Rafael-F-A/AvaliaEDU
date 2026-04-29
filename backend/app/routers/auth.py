from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth import (
    hash_senha,
    verificar_senha,
    criar_token,
    get_usuario_atual,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

router = APIRouter(prefix="/auth", tags=["Autenticação"])


#POST /auth/register
@router.post(
    "/register",
    response_model=schemas.UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(usuario_data: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    # Verifica e-mail duplicado
    existente = db.query(models.Usuario).filter(
        models.Usuario.email == usuario_data.email
    ).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="E-mail já cadastrado",
        )

    novo_usuario = models.Usuario(
        nome=usuario_data.nome,
        email=usuario_data.email,
        senha_hash=hash_senha(usuario_data.senha),
        perfil=usuario_data.perfil,
        nivel=usuario_data.nivel,
        serie=usuario_data.serie,
    )
    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)
    return novo_usuario


#POST /auth/login
@router.post("/login", response_model=schemas.LoginResponse)
def login(credenciais: schemas.UsuarioLogin, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(
        models.Usuario.email == credenciais.email
    ).first()

    if not usuario or not verificar_senha(credenciais.senha, usuario.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = criar_token(
        data={"sub": usuario.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": token, "token_type": "bearer", "usuario": usuario}


#GET /auth/me
@router.get("/me", response_model=schemas.UsuarioResponse)
def me(usuario_atual: models.Usuario = Depends(get_usuario_atual)):
    """Retorna os dados do usuário logado a partir do token JWT."""
    return usuario_atual