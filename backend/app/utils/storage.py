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
    return _upload("certificados", caminho_local, nome_destino)


def upload_prova(caminho_local: str, nome_destino: str) -> str:
    return _upload("provas", caminho_local, nome_destino, expires_in=86400)


def upload_imagem_questao(caminho_local: str, questao_id: int, extensao: str = "png") -> str:
    nome_destino = f"questoes/{questao_id}/imagem.{extensao}"
    return _upload("questoes", caminho_local, nome_destino, expires_in=604800)


def upload_imagem_modelo(caminho_local: str, modelo_id: int, extensao: str = "png") -> str:
    nome_destino = f"modelos/{modelo_id}/imagem.{extensao}"
    return _upload("questoes", caminho_local, nome_destino, expires_in=604800)


# NOVO: imagem de alternativa individual
def upload_imagem_alternativa(caminho_local: str, alternativa_id: int, extensao: str = "png") -> str:
    """
    Faz upload da imagem de uma alternativa para o bucket 'questoes'.
    Caminho: alternativas/{alternativa_id}/imagem.{extensao}
    URL assinada válida por 7 dias.
    """
    nome_destino = f"alternativas/{alternativa_id}/imagem.{extensao}"
    return _upload("questoes", caminho_local, nome_destino, expires_in=604800)


def _upload(bucket: str, caminho_local: str, nome_destino: str, expires_in: int = 3600) -> str:
    sb = _supabase()

    with open(caminho_local, "rb") as f:
        conteudo = f.read()

    # Detecta content-type pelo nome do arquivo
    ext = nome_destino.rsplit(".", 1)[-1].lower()
    content_type_map = {
        "pdf":  "application/pdf",
        "png":  "image/png",
        "jpg":  "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
    }
    content_type = content_type_map.get(ext, "application/octet-stream")

    sb.storage.from_(bucket).upload(
        path=nome_destino,
        file=conteudo,
        file_options={"content-type": content_type, "upsert": "true"},
    )

    resultado = sb.storage.from_(bucket).create_signed_url(nome_destino, expires_in)

    if isinstance(resultado, dict):
        return resultado.get("signedURL") or resultado.get("signedUrl", "")
    return getattr(resultado, "signed_url", str(resultado))


def _extrair_bucket_path(url_ou_path: str):
    """
    A partir de uma URL de Storage (assinada/pública) ou de um caminho
    'bucket/objeto', devolve (bucket, caminho_do_objeto).

    Ex.: '.../object/sign/questoes/alternativas/187/imagem.jpeg?token=...'
         -> ('questoes', 'alternativas/187/imagem.jpeg')
    """
    s = url_ou_path.split("?", 1)[0]  # remove a query string (token assinado)
    for marcador in ("/object/sign/", "/object/public/", "/object/authenticated/"):
        if marcador in s:
            s = s.split(marcador, 1)[1]
            break
    s = s.lstrip("/")
    partes = s.split("/", 1)
    if len(partes) != 2:
        raise ValueError(f"Caminho de Storage invalido: {url_ou_path!r}")
    return partes[0], partes[1]


def baixar_objeto(url_ou_path: str) -> bytes:
    """
    Baixa um objeto do Supabase Storage usando a SERVICE KEY, a partir da URL
    salva no banco (ignora o token assinado, que expira em poucos dias) ou de um
    caminho 'bucket/objeto'. Use isto para ler imagens no servidor em vez de
    baixar a URL assinada direto — que falha quando o token vence.
    """
    bucket, caminho = _extrair_bucket_path(url_ou_path)
    sb = _supabase()
    return sb.storage.from_(bucket).download(caminho)


def url_assinada_fresca(url_ou_path: str, expires_in: int = 3600) -> str:
    """
    Gera uma URL assinada NOVA para o objeto, a partir da URL salva (que pode
    estar vencida) ou de um caminho 'bucket/objeto'. Use ao servir imagens para
    o frontend, garantindo que o link nunca esteja expirado em tela. Em qualquer
    erro, devolve o valor original (degradacao graciosa, sem quebrar a resposta).
    """
    if not url_ou_path:
        return url_ou_path
    try:
        bucket, caminho = _extrair_bucket_path(url_ou_path)
        resultado = _supabase().storage.from_(bucket).create_signed_url(caminho, expires_in)
        if isinstance(resultado, dict):
            return resultado.get("signedURL") or resultado.get("signedUrl") or url_ou_path
        return getattr(resultado, "signed_url", url_ou_path)
    except Exception:
        return url_ou_path