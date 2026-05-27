from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from app.database import Base

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    senha_hash = Column(String, nullable=False)
    perfil = Column(String, nullable=False)
    nivel = Column(String)
    serie = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Prova(Base):
    __tablename__ = "provas"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, nullable=False)
    descricao = Column(String)
    nivel = Column(String)
    serie = Column(String)
    tipo = Column(String)
    nota_minima = Column(Float)
    tempo_limite = Column(Integer)
    status = Column(String, default="RASCUNHO")
    deleted = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())