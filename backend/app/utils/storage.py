from supabase import create_client
import os

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

def upload_certificado(caminho_local: str, nome_destino: str) -> str:
    with open(caminho_local, "rb") as f:
        supabase.storage.from_("certificados").upload(nome_destino, f)
    # Gera URL assinada válida por 1 hora (3600 segundos)
    signed_url = supabase.storage.from_("certificados").create_signed_url(nome_destino, 3600)
    return signed_url