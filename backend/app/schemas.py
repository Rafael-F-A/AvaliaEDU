from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# Usuários
class UsuarioCreate(BaseModel):
    nome: str
    email: EmailStr
    senha: str
    perfil: str
    nivel: Optional[str] = None
    serie: Optional[str] = None

class UsuarioLogin(BaseModel):
    email: EmailStr
    senha: str

class UsuarioResponse(BaseModel):
    id: int
    nome: str
    email: str
    perfil: str
    nivel: Optional[str] = None
    serie: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse

# Provas
class ProvaBase(BaseModel):
    titulo: str
    descricao: Optional[str] = None
    nivel: str
    serie: str
    tipo: str
    nota_minima: Optional[float] = 6.0
    tempo_limite: Optional[int] = None
    data_inicio_inscricao: Optional[datetime] = None
    data_fim_inscricao: Optional[datetime] = None

class ProvaCreate(ProvaBase):
    pass

class ProvaResponse(ProvaBase):
    id: int
    status: str
    created_at: datetime
    criado_por: Optional[int] = None

    class Config:
        from_attributes = True

class ProvaUpdate(BaseModel):
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    nivel: Optional[str] = None
    serie: Optional[str] = None
    tipo: Optional[str] = None
    nota_minima: Optional[float] = None
    tempo_limite: Optional[int] = None
    data_inicio_inscricao: Optional[datetime] = None
    data_fim_inscricao: Optional[datetime] = None

class MensagemResponse(BaseModel):
    message: str
    
# Questões
class AlternativaBase(BaseModel):
    texto: str
    is_correta: bool = False
    ordem: Optional[int] = None

class QuestaoBase(BaseModel):
    enunciado: str
    nivel_dificuldade: Optional[str] = "MEDIO"
    ordem: Optional[int] = None

class QuestaoCreate(QuestaoBase):
    alternativas: list[AlternativaBase]

class QuestaoResponse(QuestaoBase):
    id: int
    prova_id: int
    alternativas: list[AlternativaBase]

    class Config:
        from_attributes = True

# Simulados / Tentativas
class TentativaCreate(BaseModel):
    prova_id: int

class RespostaCreate(BaseModel):
    questao_id: int
    alternativa_id: int

class ResultadoResponse(BaseModel):
    nota: float
    total_questoes: int
    acertos: int
    respostas: list[dict]

# Geolocalização
class LocalBase(BaseModel):
    nome: str
    endereco: str
    cidade: str
    estado: str
    cep: str
    contato: Optional[str] = None
    capacidade: int
    vagas_restantes: int

class LocalCreate(LocalBase):
    latitude: float
    longitude: float

class LocalResponse(LocalBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

#Questões e Alternativas
class AlternativaCreate(BaseModel):
    texto: str
    is_correta: bool = False
    ordem: Optional[int] = None

class QuestaoCreate(BaseModel):
    enunciado: str
    prova_id: int
    nivel_dificuldade: Optional[str] = "MEDIO"
    alternativas: list[AlternativaCreate]

class AlternativaResponse(BaseModel):
    id: int
    texto: str
    is_correta: bool
    ordem: Optional[int]

    class Config:
        from_attributes = True

class QuestaoResponse(BaseModel):
    id: int
    enunciado: str
    prova_id: int
    nivel_dificuldade: str
    ordem: Optional[int]
    alternativas: list[AlternativaResponse]

    class Config:
        from_attributes = True

#Simulados
class IniciarSimuladoRequest(BaseModel):
    prova_id: int

class IniciarSimuladoResponse(BaseModel):
    tentativa_id: int
    questao_id: int
    enunciado: str
    alternativas: list[AlternativaResponse]
    questao_numero: int
    total_questoes: int

class ResponderQuestaoRequest(BaseModel):
    tentativa_id: int
    questao_id: int
    alternativa_id: int

class ResponderQuestaoResponse(BaseModel):
    finalizado: bool
    proxima_questao_id: Optional[int] = None
    proxima_questao_enunciado: Optional[str] = None
    proximas_alternativas: Optional[list[AlternativaResponse]] = None
    questao_numero: Optional[int] = None
    total_questoes: Optional[int] = None
    nota_final: Optional[float] = None

class ResultadoSimuladoResponse(BaseModel):
    tentativa_id: int
    prova_titulo: str
    total_questoes: int
    total_acertos: int
    total_erros: int
    nota: float
    status: str
    respostas: list[dict]

    class Config:
        from_attributes = True