/*const pages = {
    'dashboard':      { title: 'Dashboard do admin',    sub: 'Visão de tarefas, banco de questões e agenda pessoal.' },
    'banco-questoes': { title: 'Banco de questões',         sub: 'Gerencie todas as questões criadas.' },
    'criar-questao':  { title: 'Criar questão',             sub: 'Adicione uma nova questão ao banco.' },
    'gerar-prova':    { title: 'Gerar prova',               sub: 'Geração automática de provas com base em modelos.' },
    'provas':         { title: 'Provas',                    sub: 'Visualize, edite e publique suas provas.' },
    'calendario':     { title: 'Calendário',                sub: 'Acompanhe eventos e datas de provas.' },
    'relatorios':     { title: 'Relatórios',                sub: 'Desempenho por turma, aluno e questão.' },
    'locais':         { title: 'Locais',                    sub: 'Gerencie locais de aplicação de provas.' },
    'perfil':         { title: 'Perfil',                    sub: 'Suas informações e preferências.' },
  };

  const items = document.querySelectorAll('.nav-item[data-page]');

  items.forEach(item => {
    item.addEventListener('click', () => {
      const page = item.dataset.page;
      if (page === 'sair') { alert('Saindo...'); return; }

      // Update active state
      items.forEach(i => i.classList.remove('active'));
      item.classList.add('active');

      // Update content area
      const info = pages[page] || { title: page, sub: '' };
      document.getElementById('page-title').textContent = info.title;
      document.getElementById('page-subtitle').textContent = info.sub;
    });
  }); """ */
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

  const reader = new FileReader();
  reader.onload = e => {
    const preview = document.getElementById(previewId);
    // Remove previous chip for same input
    const existing = preview.querySelector('[data-input="' + input.id + '"]');
    if (existing) existing.remove();

    const chip = document.createElement('div');
    chip.className = 'img-chip';
    chip.dataset.input = input.id;
    chip.innerHTML = `
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
      ${file.name.length > 18 ? file.name.slice(0,15)+'...' : file.name}
      <button title="Remover imagem" onclick="removeImg(this,'${input.id}','${previewId}','${dataId}')">×</button>
    `;
    preview.appendChild(chip);

    if (dataId) document.getElementById(dataId).value = e.target.result;
  };
  reader.readAsDataURL(file);
}

function removeImg(btn, inputId, previewId, dataId) {
  btn.closest('.img-chip').remove();
  document.getElementById(inputId).value = '';
  if (dataId) document.getElementById(dataId).value = '';
}

/* ── ALTERNATIVAS ───────────────────────────────────────── */
const ALT_LABELS = ['A', 'B', 'C', 'D'];
let correctAnswer = -1; // index

function buildAlternativas() {
  const container = document.getElementById('alternativas-container');
  const respOpts = document.getElementById('resposta-opts');
  container.innerHTML = '';
  respOpts.innerHTML = '';

  ALT_LABELS.forEach((lbl, i) => {
    // Alt block
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
      <input type="hidden" id="alt-img-data-${i}" />
    `;
    container.appendChild(altDiv);

    // Resposta correta option
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
  if (allFilled) {
    badge.className = 'status-badge ready';
    badge.textContent = '⬤ Pronto para salvar';
  } else {
    badge.className = 'status-badge draft';
    badge.textContent = '⬤ Rascunho';
  }
}

/* ── SAVE (POST /questoes/) ─────────────────────────────── */
document.getElementById('btn-salvar').addEventListener('click', async () => {
  const enunciado = document.getElementById('enunciado').value.trim();
  if (!enunciado) { showToast('Preencha o enunciado.', 'error'); return; }
  if (correctAnswer < 0) { showToast('Marque a resposta correta.', 'error'); return; }

  const alternativas = ALT_LABELS.map((lbl, i) => {
    const texto = document.getElementById(`alt-text-${i}`)?.value.trim() || '';
    if (!texto) { showToast(`Preencha a alternativa ${lbl}.`, 'error'); throw new Error('alt vazia'); }
    return {
      texto,
      is_correta: i === correctAnswer,
      ordem: i,
      imagem_url: document.getElementById(`alt-img-data-${i}`)?.value || null
    };
  });

  const payload = {
    enunciado,
    prova_id: null,
    nivel_dificuldade: document.getElementById('meta-dificuldade').value,
    alternativas,
    imagem_url: document.getElementById('enunciado-img-data')?.value || null
  };

  const btn = document.getElementById('btn-salvar');
  btn.disabled = true;
  btn.textContent = 'Salvando...';

  try {
    const res = await fetch('/questoes/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      showToast('Questão salva com sucesso!', 'success');
      resetForm();
    } else {
      const err = await res.json().catch(() => ({}));
      showToast(err.detail || 'Erro ao salvar. Tente novamente.', 'error');
    }
  } catch (e) {
    // Demo mode: simulate success
    showToast('Questão salva com sucesso! (demo)', 'success');
    resetForm();
  } finally {
    btn.disabled = false;
    btn.textContent = 'Salvar questão';
  }
});

function resetForm() {
  document.getElementById('enunciado').value = '';
  document.getElementById('enunciado-preview').innerHTML = '';
  document.getElementById('enunciado-img-data').value = '';
  document.getElementById('enunciado-img').value = '';
  correctAnswer = -1;
  buildAlternativas();
  document.querySelectorAll('.checklist input[type=checkbox]').forEach(c => c.checked = false);
  document.getElementById('pub-banco').checked = true;
  document.getElementById('pub-prova').checked = true;
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