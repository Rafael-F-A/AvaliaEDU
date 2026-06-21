from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.dependencies import get_usuario_atual
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/register", response_model=schemas.UsuarioResponse, status_code=201)
def register(dados: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    return auth_service.registrar_usuario(dados, db)


@router.post("/login", response_model=schemas.LoginResponse)
def login(dados: schemas.UsuarioLogin, db: Session = Depends(get_db)):
    return auth_service.autenticar_usuario(dados, db)


@router.get("/me", response_model=schemas.UsuarioResponse)
def get_me(usuario=Depends(get_usuario_atual)):
    return usuario
