from pydantic import BaseModel
from typing import Optional

class UsuarioCreate(BaseModel):
    nome: str
    email: str
    senha: str
    perfil: str
    nivel: Optional[str] = None
    serie: Optional[str] = None

class UsuarioLogin(BaseModel):
    email: str
    senha: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UsuarioResponse(BaseModel):
    id: int
    nome: str
    email: str
    perfil: str
    nivel: Optional[str] = None
    serie: Optional[str] = None

    class Config:
        from_attributes = True

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse


class ProvaCreate(BaseModel):
    titulo: str
    descricao: Optional[str] = None
    nivel: Optional[str] = None
    serie: Optional[str] = None
    tipo: Optional[str] = None
    nota_minima: Optional[float] = None
    tempo_limite: Optional[int] = None


class ProvaResponse(BaseModel):
    id: int
    titulo: str
    descricao: Optional[str]
    nivel: Optional[str]
    serie: Optional[str]
    tipo: Optional[str]
    nota_minima: Optional[float]
    tempo_limite: Optional[int]
    status: str

    class Config:
        from_attributes = True