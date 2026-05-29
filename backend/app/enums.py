from enum import Enum

class TipoProva(str, Enum):
    SIMULADO = "SIMULADO"
    CERTIFICACAO = "CERTIFICACAO"

class StatusProva(str, Enum):
    RASCUNHO = "RASCUNHO"
    PUBLICADA = "PUBLICADA"

class StatusTentativa(str, Enum):
    INSCRITO = "INSCRITO"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    CONCLUIDA = "CONCLUIDA"

class ResultadoTentativa(str, Enum):
    APROVADO = "APROVADO"
    REPROVADO = "REPROVADO"