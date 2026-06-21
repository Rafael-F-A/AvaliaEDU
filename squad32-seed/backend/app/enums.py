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
    PAUSADO = "PAUSADO"
    CONCLUIDA = "CONCLUIDA"
    CANCELADA = "CANCELADA"

class ResultadoTentativa(str, Enum):
    APROVADO = "APROVADO"
    REPROVADO = "REPROVADO"