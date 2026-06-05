import os
from supabase import create_client

_client = None

def _supabase():
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL e SUPABASE_SERVICE_KEY precisam estar no .env"
            )
        _client = create_client(url, key)
    return _client


def upload_certificado(caminho_local: str, nome_destino: str) -> str:
    """
    Faz upload de um arquivo para o bucket 'certificados'.
    Retorna URL assinada válida por 1 hora.
    nome_destino: apenas o nome do arquivo, ex: "ABC123.pdf"
    """
    return _upload("certificados", caminho_local, nome_destino)


def upload_prova(caminho_local: str, nome_destino: str) -> str:
    """
    Faz upload de um arquivo para o bucket 'provas'.
    Retorna URL assinada válida por 24 horas.
    nome_destino: caminho dentro do bucket, ex: "provas/42/aluno_7.pdf"
    """
    return _upload("provas", caminho_local, nome_destino, expires_in=86400)

def upload_imagem_questao(caminho_local: str, questao_id: int, extensao: str = "png") -> str:
    """
    Faz upload de imagem de questão para o bucket 'questoes'.
    Retorna URL assinada válida por 7 dias.
    """
    nome_destino = f"questoes/{questao_id}/imagem.{extensao}"
    return _upload("questoes", caminho_local, nome_destino, expires_in=604800)

def upload_imagem_modelo(caminho_local: str, modelo_id: int, extensao: str = "png") -> str:
    nome_destino = f"modelos/{modelo_id}/imagem.{extensao}"
    return _upload("questoes", caminho_local, nome_destino, expires_in=604800)

def _upload(bucket: str, caminho_local: str, nome_destino: str, expires_in: int = 3600) -> str:
    sb = _supabase()

    with open(caminho_local, "rb") as f:
        conteudo = f.read()

    # Tenta fazer o upload; se o arquivo já existir, atualiza (upsert)
    sb.storage.from_(bucket).upload(
        path=nome_destino,
        file=conteudo,
        file_options={"content-type": "application/pdf", "upsert": "true"},
    )

    resultado = sb.storage.from_(bucket).create_signed_url(nome_destino, expires_in)

    # O SDK pode retornar dict ou objeto dependendo da versão
    if isinstance(resultado, dict):
        return resultado.get("signedURL") or resultado.get("signedUrl", "")
    return getattr(resultado, "signed_url", str(resultado))