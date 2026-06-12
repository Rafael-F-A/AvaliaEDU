from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Optional
from datetime import datetime, date

# Usuários

class UsuarioCreate(BaseModel):
    nome: str = Field(..., min_length=2, description="Nome completo do usuário")
    email: EmailStr
    senha: str = Field(..., min_length=8, description="Senha com no mínimo 8 caracteres")
    confirmar_senha: str = Field(..., min_length=8, description="Confirmação da senha")
    perfil: str = Field(..., pattern="^(ADMIN|ALUNO)$", description="ADMIN ou ALUNO")
    nivel: Optional[str] = Field(
        None,
        pattern="^(FUNDAMENTAL_I|FUNDAMENTAL_II|MEDIO|ENEM|EJA)$",
        description="Obrigatório para ALUNO",
    )
    serie: Optional[str] = None
    admin_token: Optional[str] = Field(
        None,
        description="Token secreto obrigatório para registrar perfil ADMIN",
    )

    @model_validator(mode="after")
    def senhas_coincidem(self) -> "UsuarioCreate":
        if self.senha != self.confirmar_senha:
            raise ValueError("As senhas não coincidem.")
        return self

    # Aluno deve informar nível; Admin não precisa
    @model_validator(mode="after")
    def nivel_obrigatorio_para_aluno(self) -> "UsuarioCreate":
        if self.perfil == "ALUNO" and not self.nivel:
            raise ValueError("Aluno deve informar o nível de ensino.")
        return self

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
    status: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class UsuarioUpdate(BaseModel):
    nome:   Optional[str]      = Field(None, min_length=2)
    email:  Optional[EmailStr] = None
    nivel:  Optional[str]      = Field(None, pattern="^(FUNDAMENTAL_I|FUNDAMENTAL_II|MEDIO|ENEM|EJA)$")
    serie:  Optional[str]      = None
    perfil: Optional[str]      = Field(None, pattern="^(ADMIN|ALUNO)$")
    senha:  Optional[str]      = Field(None, min_length=8)

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse

class AlunoLocalizacao(BaseModel):
    latitude:  float = Field(..., ge=-90,  le=90,  description="Latitude (-90 a 90)")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude (-180 a 180)")

class AlunoPatchPerfil(BaseModel):
    nivel: Optional[str] = Field(
        None,
        pattern="^(FUNDAMENTAL_I|FUNDAMENTAL_II|MEDIO|ENEM|EJA)$",
    )
    serie: Optional[str] = None
 
# Provas

class ProvaBase(BaseModel):
    titulo: str = Field(..., min_length=3, description="Mínimo 3 caracteres (US05)")
    descricao: Optional[str] = None
    nivel: str = Field(..., pattern="^(FUNDAMENTAL_I|FUNDAMENTAL_II|MEDIO|ENEM|EJA)$")
    serie: str
    tipo: str = Field(..., pattern="^(SIMULADO|CERTIFICACAO)$")
    nota_minima: Optional[float] = 6.0
    tempo_limite: Optional[int] = None
    data_inicio: Optional[datetime] = None
    data_fim: Optional[datetime] = None
    data_inicio_inscricao: Optional[datetime] = None
    data_fim_inscricao: Optional[datetime] = None

class ProvaCreate(ProvaBase):
    pass

class ProvaUpdate(BaseModel):
    titulo: Optional[str] = Field(None, min_length=3)
    descricao: Optional[str] = None
    nivel: Optional[str] = Field(None, pattern="^(FUNDAMENTAL_I|FUNDAMENTAL_II|MEDIO|ENEM|EJA)$")
    serie: Optional[str] = None
    tipo: Optional[str] = Field(None, pattern="^(SIMULADO|CERTIFICACAO)$")
    nota_minima: Optional[float] = None
    tempo_limite: Optional[int] = None
    data_inicio: Optional[datetime] = None
    data_fim: Optional[datetime] = None
    data_inicio_inscricao: Optional[datetime] = None
    data_fim_inscricao: Optional[datetime] = None

class ProvaResponse(BaseModel):
    id: int
    titulo: str
    descricao: Optional[str] = None
    nivel: str
    serie: str
    tipo: str
    status: str
    nota_minima: Optional[float] = None
    tempo_limite: Optional[int] = None
    data_inicio: Optional[datetime] = None
    data_fim: Optional[datetime] = None
    data_inicio_inscricao: Optional[datetime] = None
    data_fim_inscricao: Optional[datetime] = None
    criado_por: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ProvaDisponivelResponse(BaseModel):
    id: int
    titulo: str
    descricao: Optional[str] = None
    nivel: str
    serie: str
    tipo: str
    status: str
    nota_minima: Optional[float] = None
    tempo_limite: Optional[int] = None
    data_inicio: Optional[datetime] = None
    data_fim: Optional[datetime] = None
    data_inicio_inscricao: Optional[datetime] = None
    data_fim_inscricao: Optional[datetime] = None
    criado_por: Optional[int] = None
    created_at: datetime
    total_questoes: int
    dias_restantes: Optional[int] = None

    class Config:
        from_attributes = True

class ProvasListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    provas: list[ProvaResponse]

class ProvasDisponivelListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    provas: list[ProvaDisponivelResponse]

class MensagemResponse(BaseModel):
    message: str

# Alternativas

class AlternativaCreate(BaseModel):
    texto: str
    is_correta: bool = False
    ordem: Optional[int] = None
    imagem_url: Optional[str] = None

class AlternativaResponse(BaseModel):
    id: int
    texto: str
    is_correta: bool
    ordem: Optional[int]
    imagem_url: Optional[str] = None

    class Config:
        from_attributes = True

class AlternativaPublica(BaseModel):
    id: int
    texto: str
    ordem: Optional[int] = None
    imagem_url: Optional[str] = None

    class Config:
        from_attributes = True

class ImagemAltUploadResponse(BaseModel):
    alternativa_id: int
    imagem_url: str

# Questões

class QuestaoCreate(BaseModel):
    enunciado: str
    prova_id: int
    nivel_dificuldade: Optional[str] = "MEDIO"
    alternativas: list[AlternativaCreate]
    imagem_url: Optional[str] = None

class QuestaoResponse(BaseModel):
    id: int
    enunciado: str
    prova_id: int
    nivel_dificuldade: str
    ordem: Optional[int]
    imagem_url: Optional[str] = None
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
    modalidade: str = Field("ONLINE", pattern="^(ONLINE|PRESENCIAL)$")
    reserva_id: Optional[int] = None

    @model_validator(mode="after")
    def reserva_obrigatoria_para_presencial(self) -> "IniciarSimuladoRequest":
        if self.modalidade == "PRESENCIAL" and not self.reserva_id:
            raise ValueError(
                "reserva_id é obrigatório para modalidade PRESENCIAL."
            )
        return self

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
    tempo_restante_segundos: Optional[float] = None

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
    latitude: float = Field(..., ge=-90, le=90)
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
    id: int
    aluno_nome: str
    prova_titulo: str
    data_emissao: datetime
    codigo: str
    url_pdf: Optional[str] = None

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
    modelo_texto: str
    gabarito: str
    distradores: list[str]
    variaveis: Optional[dict] = None
    nivel: str
    serie: Optional[str] = None
    componente_id: Optional[int] = None
    dificuldade: Optional[str] = "MEDIO"

class ModeloQuestaoResponse(BaseModel):
    id: int
    modelo_texto: str
    gabarito: str
    distradores: list[str]
    variaveis: Optional[dict] = None
    nivel: str
    serie: Optional[str] = None
    componente_id: Optional[int] = None
    dificuldade: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Geração automática

class GerarQuestoesRequest(BaseModel):
    quantidade: int = 10
    nivel: Optional[str] = None
    dificuldade: Optional[str] = None
    componente_id: Optional[int] = None


class GerarQuestoesResponse(BaseModel):
    prova_id: int
    quantidade_gerada: int
    quantidade_erros: int
    erros: list[dict]
    questoes: list[QuestaoResponse]

    class Config:
        from_attributes = True

# Exportação de prova presencial

class ExportarProvaRequest(BaseModel):
    aluno_ids: list[int]

class ResultadoExportacaoAluno(BaseModel):
    aluno_id: int
    aluno_nome: Optional[str] = None
    url_pdf: Optional[str] = None
    erro: Optional[str] = None

class ExportarProvaResponse(BaseModel):
    prova_id: int
    total_gerados: int
    total_erros: int
    resultados: list[ResultadoExportacaoAluno]

class ImagemUploadResponse(BaseModel):
    questao_id: int
    imagem_url: str

# Response de importação de alunos

class AlunoImportadoItem(BaseModel):
    linha:            int
    nome:             str
    email:            str
    nivel:            str
    serie:            Optional[str] = None
    senha_provisoria: str
 
 
class ErroImportacaoItem(BaseModel):
    linha:  int
    dados:  dict
    erros:  list[str]
 
 
class DuplicataImportacaoItem(BaseModel):
    linha:  int
    email:  str
    motivo: str
 
 
class ImportacaoAlunosResponse(BaseModel):
    total_linhas:      int
    total_importados:  int
    total_duplicados:  int
    total_erros:       int
    importados:        list[AlunoImportadoItem]
    duplicados:        list[DuplicataImportacaoItem]
    erros:             list[ErroImportacaoItem]

# =============================================================================
# US27 — Reservas (prova presencial)
# =============================================================================

class ReservaCreate(BaseModel):
    local_id: int
    prova_id: int
    necessidades_especiais: Optional[str] = Field(
        None,
        description="Ex: acessibilidade, sala de leitura, etc. (opcional)",
    )


class ReservaLocalInfo(BaseModel):
    id: int
    nome: str
    endereco: str
    cidade: str
    estado: str

    class Config:
        from_attributes = True


class ReservaResponse(BaseModel):
    id: int
    local_id: int
    prova_id: int
    status: str
    data_reserva: datetime
    data_expiracao: Optional[datetime] = None
    necessidades_especiais: Optional[str] = None
    local: Optional[ReservaLocalInfo] = None
    prova_titulo: Optional[str] = None

    class Config:
        from_attributes = True


class ReservaAlunoInfo(BaseModel):
    id: int
    nome: str
    email: str

    class Config:
        from_attributes = True


class ReservaAdminResponse(BaseModel):
    id: int
    status: str
    data_reserva: datetime
    data_expiracao: Optional[datetime] = None
    necessidades_especiais: Optional[str] = None
    aluno: Optional[ReservaAlunoInfo] = None
    local: Optional[ReservaLocalInfo] = None
    prova_titulo: Optional[str] = None

    class Config:
        from_attributes = True