from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.dependencies import get_usuario_atual, get_usuario_admin
from app.services.certificacao_service import gerar_certificado as _gerar_registro
from app.services.pdf_certificado_service import salvar_e_fazer_upload
from app.services.pdf_prova_service import exportar_prova_para_alunos

router = APIRouter(prefix="/pdf", tags=["PDF"])


# US21: aluno baixa/gera seu certificado em PDF

@router.post(
    "/certificados/{tentativa_id}",
    response_model=schemas.CertificadoPublicoResponse,
    summary="Gera e armazena o PDF do certificado (US21)",
)
def gerar_pdf_certificado(
    tentativa_id : int,
    request      : Request,
    db           : Session = Depends(get_db),
    aluno        : models.Usuario = Depends(get_usuario_atual),
):
    """
    1. Garante que o registro de certificado existe (cria se necessário).
    2. Gera o PDF formal com brasão, dados completos e QR code.
    3. Faz upload para o Supabase Storage.
    4. Atualiza `url_pdf` no registro do certificado.
    5. Retorna os dados do certificado com a URL de download.
    """
    ip         = request.client.host
    user_agent = request.headers.get("user-agent")

    # Garante que o certificado foi aprovado e cria o registro se não existir
    cert_data = _gerar_registro(tentativa_id, aluno, db, ip, user_agent)

    certificado = db.query(models.Certificado).filter(
        models.Certificado.id == cert_data["id"]
    ).first()

    # Gera o PDF e faz upload — mesmo que já exista, regenera com URL fresca
    url_pdf = salvar_e_fazer_upload(certificado)

    # Atualiza a URL no banco
    certificado.url_pdf = url_pdf
    db.commit()

    return {
        "id"          : certificado.id,
        "aluno_nome"  : certificado.aluno.nome,
        "prova_titulo": certificado.prova.titulo,
        "data_emissao": certificado.data_emissao,
        "codigo"      : certificado.codigo_validacao,
        "url_pdf"     : url_pdf,
    }


# Exportação de prova para aplicação presencial (admin)

@router.post(
    "/provas/{prova_id}/exportar",
    response_model=schemas.ExportarProvaResponse,
    summary="Exporta a prova em PDF por aluno para aplicação presencial",
)
def exportar_prova_pdf(
    prova_id : int,
    dados    : schemas.ExportarProvaRequest,
    db       : Session = Depends(get_db),
    admin    : models.Usuario = Depends(get_usuario_admin),
):
    """
    Gera um PDF personalizado (questões e alternativas embaralhadas) para cada
    aluno informado em `aluno_ids`. Se o aluno já tem tentativa para a prova,
    usa a ordem já persistida. Caso contrário, cria a tentativa e gera a ordem.

    Retorna lista com URL do PDF por aluno e eventuais erros.
    """
    resultados = exportar_prova_para_alunos(
        prova_id=prova_id,
        aluno_ids=dados.aluno_ids,
        db=db,
    )
    sucesso = [r for r in resultados if r["erro"] is None]
    erros   = [r for r in resultados if r["erro"] is not None]

    return {
        "prova_id"          : prova_id,
        "total_gerados"     : len(sucesso),
        "total_erros"       : len(erros),
        "resultados"        : resultados,
    }