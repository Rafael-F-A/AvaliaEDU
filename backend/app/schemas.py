from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime, date

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

class ProvaResponse(BaseModel):
    id                    : int
    titulo                : str
    descricao             : Optional[str] = None
    nivel                 : str
    serie                 : str
    tipo                  : str
    status                : str
    nota_minima           : Optional[float] = None
    tempo_limite          : Optional[int] = None
    data_inicio_inscricao : Optional[datetime] = None
    data_fim_inscricao    : Optional[datetime] = None
    criado_por            : Optional[int] = None
    created_at            : datetime

    class Config:
        from_attributes = True

class ProvaDisponivelResponse(BaseModel):
    id                    : int
    titulo                : str
    descricao             : Optional[str] = None
    nivel                 : str
    serie                 : str
    tipo                  : str
    status                : str
    nota_minima           : Optional[float] = None
    tempo_limite          : Optional[int] = None
    data_inicio_inscricao : Optional[datetime] = None
    data_fim_inscricao    : Optional[datetime] = None
    criado_por            : Optional[int] = None
    created_at            : datetime
    total_questoes        : int
    dias_restantes        : Optional[int] = None

    class Config:
        from_attributes = True

class ProvasDisponivelListResponse(BaseModel):
    total  : int
    skip   : int
    limit  : int
    provas : list[ProvaDisponivelResponse]

class MensagemResponse(BaseModel):
    message: str

# Alternativas

class AlternativaCreate(BaseModel):
    texto: str
    is_correta: bool = False
    ordem: Optional[int] = None

class AlternativaResponse(BaseModel):
    id: int
    texto: str
    is_correta: bool
    ordem: Optional[int]

    class Config:
        from_attributes = True

class AlternativaPublica(BaseModel):
    id: int
    texto: str
    ordem: Optional[int] = None

    class Config:
        from_attributes = True
# Questões

class QuestaoCreate(BaseModel):
    enunciado: str
    prova_id: int
    nivel_dificuldade: Optional[str] = "MEDIO"
    alternativas: list[AlternativaCreate]

class QuestaoResponse(BaseModel):
    id: int
    enunciado: str
    prova_id: int
    nivel_dificuldade: str
    ordem: Optional[int]
    alternativas: list[AlternativaResponse]

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

class IniciarSimuladoRequest(BaseModel):
    prova_id: int

class IniciarSimuladoResponse(BaseModel):
    tentativa_id: int
    questao_id: int
    enunciado: str
    alternativas: list[AlternativaPublica]
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
    proximas_alternativas: Optional[list[AlternativaPublica]] = None
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

class QuestaoAtualResponse(BaseModel):
    tentativa_id: int
    questao_id: int
    enunciado: str
    alternativas: list[AlternativaPublica]
    questao_numero: int
    total_questoes: int
    tempo_restante_segundos: Optional[int] = None

# Geolocalização / Locais

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
    latitude: float = Field(..., ge=-90,  le=90)
    longitude: float = Field(..., ge=-180, le=180)


class LocalResponse(LocalBase):
    id: int
    latitude: float
    longitude: float
    created_at: datetime

    class Config:
        from_attributes = True

class LocalProximoResponse(BaseModel):
    id: int
    nome: str
    cidade: str
    estado: str
    latitude: float
    longitude: float
    distancia_metros: int

    class Config:
        from_attributes = True
    

# Certificações
class CertificacaoSolicitarRequest(BaseModel):
    prova_id: int

class CertificacaoSolicitadaResponse(BaseModel):
    tentativa_id: int
    status: str

class CertificadoPublicoResponse(BaseModel):
    id           : int
    aluno_nome   : str
    prova_titulo : str
    data_emissao : datetime
    codigo       : str
    url_pdf      : Optional[str] = None
 
    class Config:
        from_attributes = True

class CertificadoValidarResponse(BaseModel):
    valido: bool
    certificado: Optional[CertificadoPublicoResponse] = None
    detalhe: Optional[str] = None

class HistoricoCertificacaoResponse(BaseModel):
    id: int
    prova_titulo: str
    data_realizacao: datetime
    nota: Optional[float] = None
    resultado: Optional[str] = None
    certificado_id: Optional[int] = None
    bloqueio_ate: Optional[date] = None

# Modelos de questão
 
class ModeloQuestaoCreate(BaseModel):
    modelo_texto  : str
    gabarito      : str
    distradores   : list[str]
    variaveis     : Optional[dict] = None
    nivel         : str
    serie         : Optional[str] = None
    componente_id : Optional[int] = None
    dificuldade   : Optional[str] = "MEDIO"
 
class ModeloQuestaoResponse(BaseModel):
    id            : int
    modelo_texto  : str
    gabarito      : str
    distradores   : list[str]
    variaveis     : Optional[dict] = None
    nivel         : str
    serie         : Optional[str] = None
    componente_id : Optional[int] = None
    dificuldade   : str
    created_at    : Optional[datetime] = None
 
    class Config:
        from_attributes = True
 
# Geração automática para uma prova
 
class GerarQuestoesRequest(BaseModel):
    quantidade    : int = 10
    nivel         : Optional[str] = None   # herda da prova se omitido
    dificuldade   : Optional[str] = None
    componente_id : Optional[int] = None
 
class GerarQuestoesResponse(BaseModel):
    prova_id          : int
    quantidade_gerada : int
    quantidade_erros  : int
    erros             : list[dict]
    questoes          : list[QuestaoResponse]
 
    class Config:
        from_attributes = True

# Exportação de prova presencial
class ExportarProvaRequest(BaseModel):
    aluno_ids : list[int]   # IDs dos alunos que vão receber o PDF
 
 
class ResultadoExportacaoAluno(BaseModel):
    aluno_id   : int
    aluno_nome : Optional[str] = None
    url_pdf    : Optional[str] = None
    erro       : Optional[str] = None
 
 
class ExportarProvaResponse(BaseModel):
    prova_id       : int
    total_gerados  : int
    total_erros    : int
    resultados     : list[ResultadoExportacaoAluno]