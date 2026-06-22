import os
import io
import logging
import tempfile
import qrcode
from datetime import datetime, timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    Table, TableStyle, Image as RLImage
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle
from reportlab.graphics import renderPDF
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app import models
from app.utils.storage import upload_certificado

MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março",
    4: "abril",   5: "maio",      6: "junho",
    7: "julho",   8: "agosto",    9: "setembro",
    10: "outubro", 11: "novembro", 12: "dezembro",
}

# Paleta de cores SEED / Sergipe
AZUL_SEED    = colors.HexColor("#0B57C5")
VERDE_SEED   = colors.HexColor("#1D9E75")
AMARELO_SEED = colors.HexColor("#F2C230")
CINZA_CLARO  = colors.HexColor("#F5F5F5")
CINZA_TEXTO  = colors.HexColor("#333333")
BORDA        = colors.HexColor("#CCCCCC")

PAGE_W, PAGE_H = A4   # 595 x 842 pts


# Estilos tipográficos 

def _estilos():
    return {
        "titulo_gov": ParagraphStyle(
            "titulo_gov",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=16,
            textColor=AZUL_SEED,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "subtitulo_gov": ParagraphStyle(
            "subtitulo_gov",
            fontName="Helvetica",
            fontSize=9,
            leading=14,
            textColor=CINZA_TEXTO,
            alignment=TA_CENTER,
            spaceAfter=18,
        ),
        "titulo_cert": ParagraphStyle(
            "titulo_cert",
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=34,
            textColor=AZUL_SEED,
            alignment=TA_CENTER,
            spaceAfter=10,
            spaceBefore=14,
        ),
        "subtitulo_cert": ParagraphStyle(
            "subtitulo_cert",
            fontName="Helvetica",
            fontSize=13,
            leading=20,
            textColor=CINZA_TEXTO,
            alignment=TA_CENTER,
            spaceAfter=18,
        ),
        "texto_conferido": ParagraphStyle(
            "texto_conferido",
            fontName="Helvetica",
            fontSize=11,
            leading=17,
            textColor=CINZA_TEXTO,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "nome_aluno": ParagraphStyle(
            "nome_aluno",
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=30,
            textColor=AZUL_SEED,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "corpo": ParagraphStyle(
            "corpo",
            fontName="Helvetica",
            fontSize=11,
            leading=20,
            textColor=CINZA_TEXTO,
            alignment=TA_CENTER,
            spaceAfter=24,
        ),
        "rodape": ParagraphStyle(
            "rodape",
            fontName="Helvetica",
            fontSize=8,
            leading=13,
            textColor=colors.HexColor("#888888"),
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "codigo": ParagraphStyle(
            "codigo",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=14,
            textColor=CINZA_TEXTO,
            alignment=TA_CENTER,
        ),
    }


# Brasão / identidade visual

LOGO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "assets", "logo_seed.png")
)

# Log de diagnóstico do caminho do logo (silencioso em produção)
logging.debug("LOGO PATH: %s", LOGO_PATH)

def _qr_image(conteudo: str, size: int = 90) -> RLImage:
    """Gera QR code como ReportLab Image a partir de uma string URL."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(conteudo)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return RLImage(buf, width=size, height=size)


# Borda decorativa da página

def _adicionar_borda(canvas, doc):
    """Callback de page template — desenha borda dupla ao redor da página."""
    canvas.saveState()
    m = 18       # margem externa
    m2 = 24      # margem interna
    w, h = PAGE_W, PAGE_H

    # Borda externa fina azul
    canvas.setStrokeColor(AZUL_SEED)
    canvas.setLineWidth(1.2)
    canvas.rect(m, m, w - 2 * m, h - 2 * m)

    # Borda interna tracejada amarela
    canvas.setStrokeColor(AMARELO_SEED)
    canvas.setLineWidth(0.6)
    canvas.setDash(4, 4)
    canvas.rect(m2, m2, w - 2 * m2, h - 2 * m2)

    canvas.restoreState()


# Função principal

def gerar_pdf_certificado(certificado: models.Certificado) -> bytes:
    """
    Gera o PDF formal do certificado e retorna os bytes.
    Não faz upload — responsabilidade do chamador.
    """
    aluno  = certificado.aluno
    prova  = certificado.prova
    tent   = certificado.tentativa
    e      = _estilos()

    # URL de validação pública — aponta para a TELA do frontend (não para o
    # endpoint JSON da API). O parâmetro ?codigo preenche e valida sozinho.
    frontend_url = (os.getenv("FRONTEND_URL") or "https://frontend-ten-beryl-38.vercel.app").rstrip("/")
    url_validacao = f"{frontend_url}/?codigo={certificado.codigo_validacao}#validar"

    # Data de emissão formatada
    data_emissao = certificado.data_emissao
    if isinstance(data_emissao, datetime):
        data_str = f"{data_emissao.day} de {MESES_PT[data_emissao.month]} de {data_emissao.year}"
    else:
        data_str = str(data_emissao)

    nota_str = f"{tent.nota:.1f}" if tent and tent.nota is not None else "—"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2.8 * cm,
        rightMargin=2.8 * cm,
        topMargin=2.8 * cm,
        bottomMargin=2.8 * cm,
        title=f"Certificado — {aluno.nome}",
        author="SEED/SE",
        subject=prova.titulo,
    )

    story = []

    # Cabeçalho institucional
    logo = RLImage(LOGO_PATH, width=10 * cm, height=2.8 * cm)
    logo_table = Table(
    [[logo]],
    colWidths=[PAGE_W - 5.6 * cm],
    )
    logo_table.setStyle(TableStyle([
    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(logo_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("GOVERNO DO ESTADO DE SERGIPE", e["titulo_gov"]))
    story.append(Paragraph(
        "Secretaria de Estado da Educação — SEED/SE",
        e["subtitulo_gov"],
    ))

    story.append(HRFlowable(
        width="100%", thickness=1.5,
        color=AMARELO_SEED, spaceAfter=10,
    ))

    # Título principal
    story.append(Paragraph("CERTIFICADO", e["titulo_cert"]))
    story.append(Paragraph("de Conclusão e Aprovação", e["subtitulo_cert"]))

    story.append(HRFlowable(
        width="60%", thickness=0.5,
        color=BORDA, spaceAfter=28,
    ))

    # Corpo do certificado
    story.append(Paragraph("Certificamos que", e["texto_conferido"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(aluno.nome.upper(), e["nome_aluno"]))
    story.append(Spacer(1, 6))

    NIVEL_LABELS = {
    "FUNDAMENTAL_I":  "Fundamental I",
    "FUNDAMENTAL_II": "Fundamental II",
    "MEDIO":          "Médio",
    "ENEM":           "ENEM",
    "EJA":            "EJA",
    }
    nivel_fmt = NIVEL_LABELS.get(aluno.nivel or "", aluno.nivel or "—")
    serie_fmt  = aluno.serie or ""
    serie_txt  = f", {serie_fmt}" if serie_fmt else ""

    story.append(Paragraph(
        f"concluiu com êxito a avaliação de <b>{prova.titulo}</b>, "
        f"referente ao nível <b>{nivel_fmt}{serie_txt}</b>, "
        f"obtendo a nota <b>{nota_str}</b>, "
        f"sendo considerado <b>APROVADO</b>.",
        e["corpo"],
    ))

    story.append(Paragraph(
        f"Aracaju, {data_str}.",
        e["corpo"],
    ))

    story.append(Spacer(1, 20))

    # Linha de assinatura
    assinatura_data = [
        [
            HRFlowable(width="80%", thickness=0.8, color=CINZA_TEXTO),
        ]
    ]
    assinatura_table = Table(
        [
            [HRFlowable(width="100%", thickness=0.8, color=CINZA_TEXTO)],
            [Paragraph(
                "Secretário(a) de Estado da Educação de Sergipe",
                ParagraphStyle(
                    "ass",
                    fontName="Helvetica",
                    fontSize=9,
                    textColor=CINZA_TEXTO,
                    alignment=TA_CENTER,
                ),
            )],
        ],
        colWidths=[(PAGE_W - 5.6 * cm) * 0.5],
        hAlign="CENTER",
    )
    assinatura_table.setStyle(TableStyle([
    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ("TOPPADDING", (0, 0), (-1, -1), 8),   # era 4
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6), # era 2
    ]))
    story.append(assinatura_table)

    story.append(Spacer(1, 16))
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=BORDA, spaceAfter=14,
    ))

     # Rodapé com QR code e código de validação
    qr_img = _qr_image(url_validacao, size=80)

    estilo_auth_titulo = ParagraphStyle(
        "auth_titulo",
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=14,
        textColor=AZUL_SEED,
        spaceAfter=6,
    )
    estilo_auth_corpo = ParagraphStyle(
        "auth_corpo",
        fontName="Helvetica",
        fontSize=8,
        leading=13,
        textColor=CINZA_TEXTO,
        spaceAfter=5,
    )
    estilo_auth_link = ParagraphStyle(
        "auth_link",
        fontName="Helvetica",
        fontSize=8,
        leading=13,
        textColor=AZUL_SEED,
        spaceAfter=5,
    )

    rodape_texto = Table(
        [
            [Paragraph("Autenticidade", estilo_auth_titulo)],
            [Paragraph(
                "Escaneie o QR code ou acesse o link abaixo para verificar "
                "a autenticidade deste certificado.",
                estilo_auth_corpo,
            )],
            [Paragraph(
                f'<a href="{url_validacao}" color="#0B57C5">{url_validacao}</a>',
                estilo_auth_link,
            )],
            [Paragraph(
                f"Código de validação: <b>{certificado.codigo_validacao}</b>",
                e["codigo"],
            )],
        ],
        colWidths=[PAGE_W - 5.6 * cm - 106],
    )
    rodape_texto.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))

    rodape_table = Table(
        [[qr_img, rodape_texto]],
        colWidths=[96, PAGE_W - 5.6 * cm - 106],
        hAlign="LEFT",
    )
    rodape_table.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (1, 0), (1, 0),   12),
        ("RIGHTPADDING",  (0, 0), (0, 0),   0),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    story.append(rodape_table)
    
    # Build com borda
    doc.build(
        story,
        onFirstPage=_adicionar_borda,
        onLaterPages=_adicionar_borda,
    )

    return buf.getvalue()


# Integração com Supabase Storage

def salvar_e_fazer_upload(certificado: models.Certificado) -> str:
    """
    Gera o PDF, salva em arquivo temporário, faz upload para Supabase Storage
    e retorna a URL assinada.
    """
    pdf_bytes = gerar_pdf_certificado(certificado)
    nome_arquivo = f"{certificado.codigo_validacao}.pdf"

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        url = upload_certificado(tmp_path, nome_arquivo)
    finally:
        os.unlink(tmp_path)

    return url