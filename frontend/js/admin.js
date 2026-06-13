/* ── ROUTER ─────────────────────────────────────────────── */
const navItems = document.querySelectorAll('.nav-item[data-page]');

navItems.forEach(item => {
  item.addEventListener('click', () => {
    const page = item.dataset.page;
    if (page === 'sair') { showToast('Saindo...', 'draft'); return; }

    navItems.forEach(i => i.classList.remove('active'));
    item.classList.add('active');

    document.querySelectorAll('.page-view').forEach(v => v.classList.remove('active'));
    const view = document.getElementById('view-' + page);
    if (view) view.classList.add('active');
  });
});

/* ── IMAGE UPLOAD HELPERS ───────────────────────────────── */
function triggerImgUpload(inputId) {
  document.getElementById(inputId).click();
}

function handleImgSelect(input, previewId, dataId) {
  const file = input.files[0];
  if (!file) return;
  if (!file.type.startsWith('image/')) { showToast('Selecione um arquivo de imagem.', 'error'); return; }
  if (file.size > 5 * 1024 * 1024) { showToast('Imagem muito grande (máx. 5MB).', 'error'); return; }

  const preview = document.getElementById(previewId);
  const existing = preview.querySelector('[data-input="' + input.id + '"]');
  if (existing) existing.remove();

  const chip = document.createElement('div');
  chip.className = 'img-chip';
  chip.dataset.input = input.id;
  chip.innerHTML = `
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
    ${file.name.length > 18 ? file.name.slice(0, 15) + '...' : file.name}
    <button title="Remover imagem" onclick="removeImg(this,'${input.id}','${previewId}','${dataId}')">×</button>
  `;
  preview.appendChild(chip);

    // Store the file data in a hidden input for later upload
}

function removeImg(btn, inputId, previewId, dataId) {
  btn.closest('.img-chip').remove();
  document.getElementById(inputId).value = '';
}

/* ── ALTERNATIVAS ───────────────────────────────────────── */
const ALT_LABELS = ['A', 'B', 'C', 'D'];
let correctAnswer = -1;

function buildAlternativas() {
  const container = document.getElementById('alternativas-container');
  const respOpts  = document.getElementById('resposta-opts');
  container.innerHTML = '';
  respOpts.innerHTML  = '';

  ALT_LABELS.forEach((lbl, i) => {
    const altDiv = document.createElement('div');
    altDiv.className = 'alt-item';
    altDiv.id = `alt-item-${i}`;
    altDiv.innerHTML = `
      <div class="alt-header">
        <span class="alt-label">Alternativa ${lbl}</span>
      </div>
      <div class="alt-body" id="alt-body-${i}">
        <textarea id="alt-text-${i}" placeholder="Texto da alternativa ${lbl}" rows="2"></textarea>
        <div class="img-upload-strip">
          <button class="btn-img" onclick="triggerImgUpload('alt-img-input-${i}')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
            Imagem
          </button>
          <input type="file" id="alt-img-input-${i}" accept="image/*" style="display:none"
            onchange="handleImgSelect(this,'alt-preview-${i}','alt-img-data-${i}')" />
          <div class="img-preview" id="alt-preview-${i}"></div>
        </div>
      </div>
    `;
    container.appendChild(altDiv);

    const opt = document.createElement('label');
    opt.className = 'cq-resposta-opt';
    opt.innerHTML = `<input type="radio" name="resposta-correta" value="${i}" /> ${lbl}`;
    opt.querySelector('input').addEventListener('change', () => {
      correctAnswer = i;
      updateCorrectHighlight();
    });
    respOpts.appendChild(opt);
  });
}

function updateCorrectHighlight() {
  ALT_LABELS.forEach((_, i) => {
    const body = document.getElementById(`alt-body-${i}`);
    if (body) body.classList.toggle('correct', i === correctAnswer);
  });
  updateStatus();
}

/* ── STATUS & VALIDATION ────────────────────────────────── */
function updateStatus() {
  const enunciado = document.getElementById('enunciado').value.trim();
  const alts = ALT_LABELS.map((_, i) => document.getElementById(`alt-text-${i}`)?.value.trim() || '');
  const allFilled = enunciado && alts.every(a => a) && correctAnswer >= 0;
  const badge = document.getElementById('status-badge');
  if (!badge) return;
  if (allFilled) {
    badge.className  = 'status-badge ready';
    badge.textContent = 'Pronto para salvar';
  } else {
    badge.className  = 'status-badge draft';
    badge.textContent = 'Rascunho';
  }
}

/* ── MULTIPART IMAGE UPLOAD HELPERS ─────────────────────── */

/**
 * Uploads a File object to POST /questoes/{questaoId}/imagem
 * Returns the imagem_url from the response, or null on failure.
 */
async function uploadImagemQuestao(questaoId, file) {
  const form = new FormData();
  form.append('arquivo', file);

  const res = await fetch(`/questoes/${questaoId}/imagem`, {
    method: 'POST',
    body: form,
    // Do NOT set Content-Type — the browser sets it with the boundary.
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Erro ao enviar imagem da questão (HTTP ${res.status})`);
  }

  const data = await res.json();
  return data.imagem_url;
}

/**
 * Uploads a File object to POST /questoes/{questaoId}/alternativas/{altId}/imagem
 * Returns the imagem_url from the response, or null on failure.
 */
async function uploadImagemAlternativa(questaoId, alternativaId, file) {
  const form = new FormData();
  form.append('arquivo', file);

  const res = await fetch(`/questoes/${questaoId}/alternativas/${alternativaId}/imagem`, {
    method: 'POST',
    body: form,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Erro ao enviar imagem da alternativa ${alternativaId} (HTTP ${res.status})`);
  }

  const data = await res.json();
  return data.imagem_url;
}

/* ── SAVE ───────────────────────────────────────────────── */
document.getElementById('btn-salvar').addEventListener('click', async () => {

  /* ── 1. Validate ── */
  const enunciado = document.getElementById('enunciado').value.trim();
  if (!enunciado) { showToast('Preencha o enunciado.', 'error'); return; }
  if (correctAnswer < 0) { showToast('Marque a resposta correta.', 'error'); return; }

  let alternativas;
  try {
    alternativas = ALT_LABELS.map((lbl, i) => {
      const texto = document.getElementById(`alt-text-${i}`)?.value.trim() || '';
      if (!texto) {
        showToast(`Preencha a alternativa ${lbl}.`, 'error');
        throw new Error('alternativa vazia');
      }
      return { texto, is_correta: i === correctAnswer, ordem: i };
    });
  } catch {
    return; 
  }

  const btn = document.getElementById('btn-salvar');
  btn.disabled    = true;
  btn.textContent = 'Salvando...';

  try {

    /* ── 2. Create question  ── */
    const payload = {
      enunciado,
      prova_id: null,
      nivel_dificuldade: document.getElementById('meta-dificuldade').value,
      alternativas,
      
    };

    const res = await fetch('/questoes/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Erro ao salvar questão (HTTP ${res.status})`);
    }

    const questao = await res.json();
    const questaoId = questao.id; 

    /* ── 3. Upload question image (if any) ── */
    const enunciadoImgInput = document.getElementById('enunciado-img');
    if (enunciadoImgInput?.files?.[0]) {
      try {
        await uploadImagemQuestao(questaoId, enunciadoImgInput.files[0]);
      } catch (e) {
        // Non-fatal: question is already saved; warn the user but continue.
        showToast(`Questão salva, mas ${e.message}`, 'error');
      }
    }

    /* ── 4. Upload alternative images (if any) ── */

    const altRespostas = questao.alternativas ?? [];

    for (let i = 0; i < ALT_LABELS.length; i++) {
      const altInput = document.getElementById(`alt-img-input-${i}`);
      if (!altInput?.files?.[0]) continue;

      // Match by ordem (index) — adjust if your API returns them in a different order.
      const altData = altRespostas.find(a => a.ordem === i);
      if (!altData?.id) {
        showToast(`Não foi possível enviar imagem da alternativa ${ALT_LABELS[i]}: ID não encontrado.`, 'error');
        continue;
      }

      try {
        await uploadImagemAlternativa(questaoId, altData.id, altInput.files[0]);
      } catch (e) {
        showToast(`Alternativa ${ALT_LABELS[i]}: ${e.message}`, 'error');
      }
    }

    showToast('Questão salva com sucesso!', 'success');
    resetForm();

  } catch (e) {
    showToast(e.message || 'Erro inesperado. Tente novamente.', 'error');
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Salvar questão';
  }
});

/* ── RESET ──────────────────────────────────────────────── */
function resetForm() {
  document.getElementById('enunciado').value = '';
  document.getElementById('enunciado-preview').innerHTML = '';
  document.getElementById('enunciado-img').value = '';
  correctAnswer = -1;
  buildAlternativas();
  document.querySelectorAll('.checklist input[type=checkbox]').forEach(c => c.checked = false);
  const pubBanco = document.getElementById('pub-banco');
  const pubProva = document.getElementById('pub-prova');
  if (pubBanco) pubBanco.checked = true;
  if (pubProva) pubProva.checked = true;
  updateStatus();
}

/* ── TOAST ──────────────────────────────────────────────── */
function showToast(msg, type = '') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show' + (type ? ' ' + type : '');
  setTimeout(() => { t.className = 'toast'; }, 3200);
}

/* ── LIVE STATUS UPDATE ─────────────────────────────────── */
document.addEventListener('input', e => {
  if (e.target.closest('#view-criar-questao')) updateStatus();
});

/* ── INIT ───────────────────────────────────────────────── */
buildAlternativas();