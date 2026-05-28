from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, Date
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
from geoalchemy2 import Geometry
from sqlalchemy.types import JSON

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    senha_hash = Column(String(255), nullable=False)
    perfil = Column(String(20), nullable=False)
    nivel = Column(String(20))
    serie = Column(String(20))
    latitude = Column(Float)
    longitude = Column(Float)
    status = Column(String(20), default="ATIVO")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos
    tentativas = relationship("Tentativa", back_populates="aluno", cascade="all, delete-orphan")
    reservas = relationship("Reserva", back_populates="aluno", cascade="all, delete-orphan")
    certificados = relationship("Certificado", back_populates="aluno")

class Prova(Base):
    __tablename__ = "provas"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(255), nullable=False)
    descricao = Column(Text)
    nivel = Column(String(50), nullable=False)
    serie = Column(String(50), nullable=False)
    tipo = Column(String(15), nullable=False)
    status = Column(String(20), default="RASCUNHO")
    nota_minima = Column(Float, default=6.0)
    tempo_limite = Column(Integer)
    criado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos
    questoes = relationship("Questao", back_populates="prova", cascade="all, delete-orphan")
    tentativas = relationship("Tentativa", back_populates="prova")
    reservas = relationship("Reserva", back_populates="prova")
    certificados = relationship("Certificado", back_populates="prova")

class Questao(Base):
    __tablename__ = "questoes"

    id = Column(Integer, primary_key=True, index=True)
    enunciado = Column(Text, nullable=False)
    prova_id = Column(Integer, ForeignKey("provas.id", ondelete="CASCADE"), nullable=False)
    nivel_dificuldade = Column(String(20), default="MEDIO")
    ordem = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos
    prova = relationship("Prova", back_populates="questoes")
    alternativas = relationship("Alternativa", back_populates="questao", cascade="all, delete-orphan")
    respostas = relationship("Resposta", back_populates="questao")

class Alternativa(Base):
    __tablename__ = "alternativas"

    id = Column(Integer, primary_key=True, index=True)
    texto = Column(Text, nullable=False)
    questao_id = Column(Integer, ForeignKey("questoes.id", ondelete="CASCADE"), nullable=False)
    is_correta = Column(Boolean, default=False)
    ordem = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    questao = relationship("Questao", back_populates="alternativas")
    respostas = relationship("Resposta", back_populates="alternativa")

class Local(Base):
    __tablename__ = "locais"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    endereco = Column(Text, nullable=False)
    cidade = Column(String(100), nullable=False)
    estado = Column(String(2), nullable=False)
    cep = Column(String(20), nullable=False)
    contato = Column(String(255))
    capacidade = Column(Integer, nullable=False)
    vagas_restantes = Column(Integer, nullable=False)
    geolocalizacao = Column(Geometry('POINT', srid=4326))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos
    reservas = relationship("Reserva", back_populates="local", cascade="all, delete-orphan")

class Reserva(Base):
    __tablename__ = "reservas"

    id = Column(Integer, primary_key=True, index=True)
    aluno_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    local_id = Column(Integer, ForeignKey("locais.id", ondelete="CASCADE"), nullable=False)
    prova_id = Column(Integer, ForeignKey("provas.id", ondelete="CASCADE"), nullable=False)
    data_reserva = Column(DateTime(timezone=True), server_default=func.now())
    data_expiracao = Column(DateTime(timezone=True))
    status = Column(String(20), default="ATIVA")
    necessidades_especiais = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos
    aluno = relationship("Usuario", back_populates="reservas")
    local = relationship("Local", back_populates="reservas")
    prova = relationship("Prova", back_populates="reservas")

class Tentativa(Base):
    __tablename__ = "tentativas"

    id = Column(Integer, primary_key=True, index=True)
    aluno_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    prova_id = Column(Integer, ForeignKey("provas.id", ondelete="CASCADE"), nullable=False)
    tipo = Column(String(15), nullable=False)
    status = Column(String(20), default="INSCRITO")
    data_inicio = Column(DateTime(timezone=True))
    data_fim = Column(DateTime(timezone=True))
    nota = Column(Float)
    resultado = Column(String(20))
    bloqueio_ate = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    ordem_questoes = Column(JSON, nullable=True)  # importar JSON do sqlalchemy.types

    # Relacionamentos
    aluno = relationship("Usuario", back_populates="tentativas")
    prova = relationship("Prova", back_populates="tentativas")
    respostas = relationship("Resposta", back_populates="tentativa", cascade="all, delete-orphan")
    certificado = relationship("Certificado", back_populates="tentativa", uselist=False)

class Resposta(Base):
    __tablename__ = "respostas"

    id = Column(Integer, primary_key=True, index=True)
    tentativa_id = Column(Integer, ForeignKey("tentativas.id", ondelete="CASCADE"), nullable=False)
    questao_id = Column(Integer, ForeignKey("questoes.id", ondelete="CASCADE"), nullable=False)
    alternativa_id = Column(Integer, ForeignKey("alternativas.id", ondelete="SET NULL"))
    is_correta = Column(Boolean)
    data_resposta = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    tentativa = relationship("Tentativa", back_populates="respostas")
    questao = relationship("Questao", back_populates="respostas")
    alternativa = relationship("Alternativa", back_populates="respostas")

class Certificado(Base):
    __tablename__ = "certificados"

    id = Column(Integer, primary_key=True, index=True)
    tentativa_id = Column(Integer, ForeignKey("tentativas.id", ondelete="CASCADE"), unique=True, nullable=False)
    aluno_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    prova_id = Column(Integer, ForeignKey("provas.id", ondelete="CASCADE"), nullable=False)
    codigo_validacao = Column(String(50), unique=True, nullable=False)
    url_pdf = Column(String(500))
    data_emissao = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    tentativa = relationship("Tentativa", back_populates="certificado")
    aluno = relationship("Usuario", back_populates="certificados")
    prova = relationship("Prova", back_populates="certificados")