import io
import json
import random
import os
import tempfile
import urllib.request
import glob
from datetime import datetime, timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    HRFlowable, Table, TableStyle, PageBreak,
    Image as RLImage,
)
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app import models
from app.utils.storage import upload_certificado

# Constantes de cor
AZUL_SEED    = colors.HexColor("#0B57C5")
AMARELO_SEED = colors.HexColor("#F2C230")
CINZA_CLARO  = colors.HexColor("#F5F5F5")
CINZA_TEXTO  = colors.HexColor("#333333")
BORDA        = colors.HexColor("#CCCCCC")

PAGE_W, PAGE_H = A4
LETRAS = ["A", "B", "C", "D", "E", "F"]

LOGO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "assets", "logo_seed.png")
)
print("LOGO PATH:", LOGO_PATH)

NIVEL_LABELS = {
    "FUNDAMENTAL_I":  "Fundamental I",
    "FUNDAMENTAL_II": "Fundamental II",
    "MEDIO":          "Médio",
    "ENEM":           "ENEM",
    "EJA":            "EJA",
}
TIPO_LABELS = {
    "SIMULADO":     "Simulado",
    "CERTIFICACAO": "Certificação",
}


# Estilos

def _estilos():
    return {
        "cabecalho": ParagraphStyle(
            "cabecalho",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=AZUL_SEED,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "subcabecalho": ParagraphStyle(
            "subcabecalho",
            fontName="Helvetica",
            fontSize=9,
            textColor=CINZA_TEXTO,
            alignment=TA_CENTER,
            spaceAfter=14,
        ),
        "titulo_prova": ParagraphStyle(
            "titulo_prova",
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=18,
            textColor=AZUL_SEED,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "meta_prova": ParagraphStyle(
            "meta_prova",
            fontName="Helvetica",
            fontSize=9,
            textColor=CINZA_TEXTO,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "aluno_label": ParagraphStyle(
            "aluno_label",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=CINZA_TEXTO,
            spaceAfter=2,
        ),
        "aluno_linha": ParagraphStyle(
            "aluno_linha",
            fontName="Helvetica",
            fontSize=10,
            textColor=CINZA_TEXTO,
            spaceAfter=10,
        ),
        "instrucoes": ParagraphStyle(
            "instrucoes",
            fontName="Helvetica",
            fontSize=8.5,
            textColor=CINZA_TEXTO,
            leading=13,
            spaceAfter=6,
        ),
        "numero_questao": ParagraphStyle(
            "numero_questao",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=AZUL_SEED,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "enunciado": ParagraphStyle(
            "enunciado",
            fontName="Helvetica",
            fontSize=10.5,
            textColor=CINZA_TEXTO,
            leading=15,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
            keepWithNext=True,
        ),
        "alternativa": ParagraphStyle(
            "alternativa",
            fontName="Helvetica",
            fontSize=10.5,
            textColor=CINZA_TEXTO,
            leading=14,
            leftIndent=16,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "rodape": ParagraphStyle(
            "rodape",
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.HexColor("#888888"),
            alignment=TA_CENTER,
        ),
    }


# Borda e rodapé de página

def _borda_prova(canvas, doc):
    canvas.saveState()
    m = 18
    canvas.setStrokeColor(AZUL_SEED)
    canvas.setLineWidth(1)
    canvas.rect(m, m, PAGE_W - 2 * m, PAGE_H - 2 * m)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawCentredString(
        PAGE_W / 2, 30,
        f"Página {doc.page} — SEED/SE — Uso exclusivo para aplicação presencial",
    )
    canvas.restoreState()


# Geração do PDF para um aluno

def gerar_pdf_prova_aluno(
    prova: models.Prova,
    aluno: models.Usuario,
    questoes_ordenadas: list,
    alternativas_por_questao: dict,
    numero_tentativa: int = 1,
) -> bytes:
    """Gera o PDF da prova personalizado para um aluno."""

    # buf deve ser definido ANTES do doc
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        title=f"{prova.titulo} — {aluno.nome}",
        author="SEED/SE",
    )

    # estilos definidos em variável local para não colidir com except
    estilos = _estilos()

    story = []

    # Logo institucional
    logo = RLImage(LOGO_PATH, width=9 * cm, height=2.5 * cm)
    logo_table = Table(
        [[logo]],
        colWidths=[PAGE_W - 5 * cm],
    )
    logo_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(logo_table)
    story.append(Spacer(1, 8))

    # Cabeçalho
    story.append(Paragraph(
        "GOVERNO DO ESTADO DE SERGIPE — SECRETARIA DE ESTADO DA EDUCAÇÃO (SEED/SE)",
        estilos["cabecalho"],
    ))

    tipo_fmt = TIPO_LABELS.get(prova.tipo, prova.tipo)
    story.append(Paragraph(
        f"{prova.serie} — {tipo_fmt}",
        estilos["subcabecalho"],
    ))

    story.append(HRFlowable(width="100%", thickness=2, color=AZUL_SEED, spaceAfter=8))

    # Título da prova
    story.append(Paragraph(prova.titulo.upper(), estilos["titulo_prova"]))

    tempo_str = (
        f"Tempo limite: {prova.tempo_limite} min"
        if prova.tempo_limite
        else "Sem tempo limite"
    )
    story.append(Paragraph(
        f"{tempo_str}  |  {len(questoes_ordenadas)} questões",
        estilos["meta_prova"],
    ))

    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDA, spaceAfter=12))

    # Identificação do aluno
    id_table = Table(
        [
            [
                Paragraph("Nome:", estilos["aluno_label"]),
                Paragraph("_" * 40, estilos["aluno_linha"]),
                Paragraph("Data:", estilos["aluno_label"]),
                Paragraph("___/___/______", estilos["aluno_linha"]),
            ],
            [
                Paragraph("Nível:", estilos["aluno_label"]),
                Paragraph("________________", estilos["aluno_linha"]),
                Paragraph("Turno:", estilos["aluno_label"]),
                Paragraph("________________", estilos["aluno_linha"]),
            ],
        ],
        colWidths=[2.2 * cm, 8.8 * cm, 1.8 * cm, 4.2 * cm],
        hAlign="LEFT",
    )
    id_table.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING",   (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LINEBELOW",    (1, 0), (1, 0), 0.5, BORDA),
        ("LINEBELOW",    (3, 0), (3, 0), 0.5, BORDA),
        ("LINEBELOW",    (1, 1), (1, 1), 0.5, BORDA),
        ("LINEBELOW",    (3, 1), (3, 1), 0.5, BORDA),
    ]))
    story.append(id_table)
    story.append(Spacer(1, 8))

    # Instruções
    instrucoes_box = Table(
        [[Paragraph(
            "<b>INSTRUÇÕES:</b> Leia cada questão com atenção. "
            "Assinale apenas uma alternativa por questão. "
            "Não é permitido o uso de calculadora. "
            "Respostas a lápis não serão aceitas.",
            estilos["instrucoes"],
        )]],
        colWidths=[PAGE_W - 5 * cm],
        hAlign="LEFT",
    )
    instrucoes_box.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), CINZA_CLARO),
        ("BOX",          (0, 0), (-1, -1), 0.5, BORDA),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
    ]))
    story.append(instrucoes_box)
    story.append(Spacer(1, 16))

    # Questões
    arquivos_tmp_imagem = []  # rastrear para limpeza após build

    for idx, questao in enumerate(questoes_ordenadas, start=1):
        print(f"Questão {idx} | id={questao.id} | enunciado={questao.enunciado[:50]}")

        story.append(Paragraph(f"Questão {idx}", estilos["numero_questao"]))

        # Imagem da questão (se houver)
        if questao.imagem_url:
            tmp_img_path = None
            try:
                suffix = ".jpg" if "jpg" in questao.imagem_url.lower() else ".png"
                with tempfile.NamedTemporaryFile(
                    suffix=suffix, delete=False
                ) as tmp_img:
                    tmp_img_path = tmp_img.name

                urllib.request.urlretrieve(questao.imagem_url, tmp_img_path)
                arquivos_tmp_imagem.append(tmp_img_path)

                from PIL import Image as PILImage
                with PILImage.open(tmp_img_path) as pil_img:
                    orig_w, orig_h = pil_img.size

                max_w = 12 * cm
                max_h = 8 * cm
                ratio = min(max_w / orig_w, max_h / orig_h)
                draw_w = orig_w * ratio
                draw_h = orig_h * ratio

                img = RLImage(tmp_img_path, width=draw_w, height=draw_h)
                img_table = Table(
                    [[img]],
                    colWidths=[PAGE_W - 5 * cm],
                )
                img_table.setStyle(TableStyle([
                    ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING",    (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]))
                story.append(img_table)

            except Exception as img_err:
                print(f"Erro ao carregar imagem da questão {questao.id}: {img_err}")
                if tmp_img_path and os.path.exists(tmp_img_path):
                    try:
                        os.unlink(tmp_img_path)
                    except Exception:
                        pass

        # Enunciado (apenas uma vez)
        story.append(Paragraph(questao.enunciado, estilos["enunciado"]))

        # Alternativas
        alts = alternativas_por_questao.get(questao.id, [])
        for i, alt in enumerate(alts):
            letra = LETRAS[i] if i < len(LETRAS) else str(i + 1)

            # Imagem da alternativa (se houver)
            if alt.imagem_url:
                tmp_alt_path = None
                try:
                    suffix = ".jpg" if "jpg" in alt.imagem_url.lower() else ".png"
                    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_alt:
                        tmp_alt_path = tmp_alt.name
                    urllib.request.urlretrieve(alt.imagem_url, tmp_alt_path)
                    arquivos_tmp_imagem.append(tmp_alt_path)

                    from PIL import Image as PILImage
                    with PILImage.open(tmp_alt_path) as pil_alt:
                        orig_w, orig_h = pil_alt.size

                    # Alternativas ficam menores que o enunciado
                    max_w = 8 * cm
                    max_h = 5 * cm
                    ratio = min(max_w / orig_w, max_h / orig_h)
                    draw_w = orig_w * ratio
                    draw_h = orig_h * ratio

                    alt_img = RLImage(tmp_alt_path, width=draw_w, height=draw_h)

                    # Linha com letra + imagem lado a lado
                    alt_table = Table(
                        [[
                            Paragraph(f"( {letra} )", estilos["alternativa"]),
                            alt_img,
                            Paragraph(alt.texto or "", estilos["alternativa"]) if alt.texto else Paragraph("", estilos["alternativa"]),
                        ]],
                        colWidths=[1.2 * cm, draw_w + 6, None],
                        hAlign="LEFT",
                    )
                    alt_table.setStyle(TableStyle([
                        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
                        ("TOPPADDING",    (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]))
                    story.append(alt_table)

                except Exception as alt_img_err:
                    print(f"Erro ao carregar imagem da alternativa {alt.id}: {alt_img_err}")
                    # Fallback: exibe como texto simples
                    story.append(Paragraph(
                        f"( {letra} )&nbsp;&nbsp;{alt.texto or '[imagem indisponível]'}",
                        estilos["alternativa"],
                    ))
                    if tmp_alt_path and os.path.exists(tmp_alt_path):
                        try:
                            os.unlink(tmp_alt_path)
                        except Exception:
                            pass
            else:
                # Sem imagem
                story.append(Paragraph(
                    f"( {letra} )&nbsp;&nbsp;{alt.texto}",
                    estilos["alternativa"],
                ))

        story.append(Spacer(1, 12))

        # Separador entre questões (exceto última)
        if idx < len(questoes_ordenadas):
            story.append(HRFlowable(
                width="100%", thickness=0.4,
                color=BORDA, spaceAfter=12,
            ))

    # Rodapé do documento
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDA, spaceAfter=8))
    story.append(Paragraph(
        f"Código da prova: {prova.id} — Documento gerado em "
        f"{datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC",
        estilos["rodape"],
    ))

    # Build do PDF
    doc.build(story, onFirstPage=_borda_prova, onLaterPages=_borda_prova)

    # Limpeza dos arquivos temporários de imagem APÓS o build
    for tmp_path in arquivos_tmp_imagem:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass

    return buf.getvalue()

# Orquestrador

def exportar_prova_para_alunos(
    prova_id: int,
    aluno_ids: list[int],
    db: Session,
) -> list[dict]:
    """
    Para cada aluno_id:
      1. Busca tentativa existente (usa a ordem já persistida).
      2. Se não existe tentativa, cria uma nova com ordem aleatória.
      3. Gera o PDF e faz upload para o Supabase Storage.
      4. Retorna lista com {aluno_id, aluno_nome, url_pdf, erro}.
    """
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.deleted == False,
        models.Prova.status == "PUBLICADA",
    ).first()
    if not prova:
        raise HTTPException(404, "Prova não encontrada ou não publicada.")

    questoes_db = db.query(models.Questao).filter(
        models.Questao.prova_id == prova_id
    ).all()
    if not questoes_db:
        raise HTTPException(422, "A prova não possui questões.")

    questoes_map = {q.id: q for q in questoes_db}
    resultados = []

    for aluno_id in aluno_ids:
        aluno = db.query(models.Usuario).filter(
            models.Usuario.id == aluno_id,
            models.Usuario.perfil == "ALUNO",
        ).first()
        if not aluno:
            resultados.append({
                "aluno_id":   aluno_id,
                "aluno_nome": None,
                "url_pdf":    None,
                "erro":       "Aluno não encontrado.",
            })
            continue

        try:
            tentativa = db.query(models.Tentativa).filter(
                models.Tentativa.aluno_id == aluno_id,
                models.Tentativa.prova_id == prova_id,
                models.Tentativa.status.in_(["INSCRITO", "EM_ANDAMENTO"]),
            ).first()

            if tentativa and tentativa.ordem_questoes:
                ordem_q = (
                    json.loads(tentativa.ordem_questoes)
                    if isinstance(tentativa.ordem_questoes, str)
                    else tentativa.ordem_questoes
                )
                ordem_alt = (
                    json.loads(tentativa.ordem_alternativas)
                    if isinstance(tentativa.ordem_alternativas, str)
                    else (tentativa.ordem_alternativas or {})
                )
            else:
                ordem_q = [q.id for q in questoes_db]
                random.shuffle(ordem_q)

                ordem_alt = {}
                for q in questoes_db:
                    alts = [a.id for a in q.alternativas]
                    random.shuffle(alts)
                    ordem_alt[str(q.id)] = alts

                tentativa = models.Tentativa(
                    aluno_id=aluno_id,
                    prova_id=prova_id,
                    tipo=prova.tipo,
                    status="INSCRITO",
                    data_inicio=datetime.now(timezone.utc),
                    ordem_questoes=json.dumps(ordem_q),
                    ordem_alternativas=json.dumps(ordem_alt),
                )
                db.add(tentativa)
                db.commit()
                db.refresh(tentativa)

            questoes_ordenadas = [
                questoes_map[qid] for qid in ordem_q if qid in questoes_map
            ]

            alts_map: dict[int, list] = {}
            for q in questoes_ordenadas:
                alts_db = {a.id: a for a in q.alternativas}
                ids_ordenados = ordem_alt.get(str(q.id), list(alts_db.keys()))
                alts_map[q.id] = [alts_db[aid] for aid in ids_ordenados if aid in alts_db]

            pdf_bytes = gerar_pdf_prova_aluno(
                prova=prova,
                aluno=aluno,
                questoes_ordenadas=questoes_ordenadas,
                alternativas_por_questao=alts_map,
            )

            nome_arquivo = f"provas/{prova_id}/aluno_{aluno_id}.pdf"
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name

            try:
                url = upload_certificado(tmp_path, nome_arquivo)
            finally:
                os.unlink(tmp_path)

            resultados.append({
                "aluno_id":   aluno_id,
                "aluno_nome": aluno.nome,
                "url_pdf":    url,
                "erro":       None,
            })

        except Exception as exc:
            db.rollback()
            resultados.append({
                "aluno_id":   aluno_id,
                "aluno_nome": getattr(aluno, "nome", None),
                "url_pdf":    None,
                "erro":       str(exc),
            })

    return resultados