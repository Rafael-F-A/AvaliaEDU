import os
import io
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
            textColor=AZUL_SEED,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "subtitulo_gov": ParagraphStyle(
            "subtitulo_gov",
            fontName="Helvetica",
            fontSize=9,
            textColor=CINZA_TEXTO,
            alignment=TA_CENTER,
            spaceAfter=14,
        ),
        "titulo_cert": ParagraphStyle(
            "titulo_cert",
            fontName="Helvetica-Bold",
            fontSize=26,
            textColor=AZUL_SEED,
            alignment=TA_CENTER,
            spaceAfter=6,
            spaceBefore=20,
        ),
        "subtitulo_cert": ParagraphStyle(
            "subtitulo_cert",
            fontName="Helvetica",
            fontSize=13,
            textColor=CINZA_TEXTO,
            alignment=TA_CENTER,
            spaceAfter=24,
        ),
        "texto_conferido": ParagraphStyle(
            "texto_conferido",
            fontName="Helvetica",
            fontSize=11,
            textColor=CINZA_TEXTO,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "nome_aluno": ParagraphStyle(
            "nome_aluno",
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=AZUL_SEED,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "corpo": ParagraphStyle(
            "corpo",
            fontName="Helvetica",
            fontSize=11,
            textColor=CINZA_TEXTO,
            alignment=TA_CENTER,
            leading=18,
            spaceAfter=20,
        ),
        "rodape": ParagraphStyle(
            "rodape",
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.HexColor("#888888"),
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "codigo": ParagraphStyle(
            "codigo",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=CINZA_TEXTO,
            alignment=TA_CENTER,
        ),
    }


# Brasão / identidade visual

def _brasao_drawing(width=120, height=80) -> Drawing:
    """
    Representação gráfica institucional da SEED/SE em ReportLab Drawing.
    Inclui as cores oficiais e o texto do órgão.
    (Substitua por SVG real convertido se tiver o arquivo do brasão oficial.)
    """
    d = Drawing(width, height)

    # Faixa azul superior
    d.add(Rect(0, height - 28, width, 28, fillColor=AZUL_SEED, strokeColor=None))
    # Faixa amarela central
    d.add(Rect(0, height - 48, width, 20, fillColor=AMARELO_SEED, strokeColor=None))
    # Faixa verde inferior
    d.add(Rect(0, height - 62, width, 14, fillColor=VERDE_SEED, strokeColor=None))

    # Texto SEED
    d.add(String(
        width / 2, height - 20,
        "SEED/SE",
        fontName="Helvetica-Bold",
        fontSize=11,
        fillColor=colors.white,
        textAnchor="middle",
    ))
    # Subtexto
    d.add(String(
        width / 2, height - 42,
        "SECRETARIA DE ESTADO",
        fontName="Helvetica-Bold",
        fontSize=6.5,
        fillColor=AZUL_SEED,
        textAnchor="middle",
    ))
    d.add(String(
        width / 2, height - 51,
        "DA EDUCAÇÃO DE SERGIPE",
        fontName="Helvetica-Bold",
        fontSize=6.5,
        fillColor=AZUL_SEED,
        textAnchor="middle",
    ))
    return d


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

    # URL de validação pública
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    url_validacao = f"{base_url}/certificacoes/validar/{certificado.codigo_validacao}"

    # Data de emissão formatada
    data_emissao = certificado.data_emissao
    if isinstance(data_emissao, datetime):
        data_str = data_emissao.strftime("%d de %B de %Y").lower()
        # Capitaliza só o primeiro caractere
        data_str = data_str[0].upper() + data_str[1:]
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
    brasao = _brasao_drawing(130, 85)
    brasao_table = Table(
        [[brasao]],
        colWidths=[PAGE_W - 5.6 * cm],
    )
    brasao_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(brasao_table)
    story.append(Spacer(1, 6))

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
        color=BORDA, spaceAfter=20,
    ))

    # Corpo do certificado
    story.append(Paragraph("Certificamos que", e["texto_conferido"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(aluno.nome.upper(), e["nome_aluno"]))
    story.append(Spacer(1, 4))

    nivel_fmt = (aluno.nivel or "—").replace("_", " ")
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

    story.append(Spacer(1, 28))

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
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(assinatura_table)

    story.append(Spacer(1, 28))
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=BORDA, spaceAfter=14,
    ))

    # Rodapé com QR code e código de validação
    qr_img = _qr_image(url_validacao, size=80)

    rodape_conteudo = [
        Paragraph("Autenticidade", ParagraphStyle(
            "auth_titulo",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=AZUL_SEED,
            spaceAfter=4,
        )),
        Paragraph(
            "Escaneie o QR code ou acesse o link abaixo para verificar a autenticidade deste certificado.",
            ParagraphStyle(
                "auth_corpo",
                fontName="Helvetica",
                fontSize=8,
                textColor=CINZA_TEXTO,
                leading=12,
                spaceAfter=6,
            ),
        ),
        Paragraph(
            f'<a href="{url_validacao}" color="#0B57C5">{url_validacao}</a>',
            ParagraphStyle(
                "auth_link",
                fontName="Helvetica",
                fontSize=8,
                textColor=AZUL_SEED,
                spaceAfter=6,
            ),
        ),
        Paragraph(
            f"Código de validação: <b>{certificado.codigo_validacao}</b>",
            e["codigo"],
        ),
    ]

    rodape_table = Table(
        [[qr_img, rodape_conteudo]],
        colWidths=[90, PAGE_W - 5.6 * cm - 100],
        hAlign="LEFT",
    )
    rodape_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (1, 0), (1, 0), 14),
        ("RIGHTPADDING", (0, 0), (0, 0), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
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