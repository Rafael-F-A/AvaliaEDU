/* ============================================================
   AvaliaEdu — admin.js
   Lógica completa do Dashboard de Gestão (ADMIN).
   Depende de: global.js (apiFetch, showToast, openModal,
               closeModal, requireAuth, initUI, debounce, etc.)

   Seções cobertas:
     1.  Estado global
     2.  Inicialização
     3.  Navegação entre seções
     4.  Dashboard (métricas + provas recentes)
     5.  Provas (listagem, filtros, publicar, excluir)
     6.  Modal de Prova (criar / editar)
     7.  Questões (listar, criar, editar, excluir)
     8.  Modal de Questão + alternativas dinâmicas
     9.  Usuários (listagem, filtros, bloquear, desbloquear, excluir)
     10. Modal de Usuário (cadastrar)
     11. Locais (listagem, filtros, excluir)
     12. Modal de Local (criar / editar)
     13. Relatórios (métricas, desempenho por nível, exportar)
     14. Modal de confirmação genérico
     15. Helpers locais
   ============================================================ */

/* ─────────────────────────────────────────
   1. ESTADO GLOBAL
   ─────────────────────────────────────── */

/** Usuário admin logado (preenchido no init). */
let usuario = null;

/** Cache local para filtros de frontend. */
let _provas       = [];
let _usuarios     = [];
let _locais       = [];
let _componentes  = [];   // US36 — cache de componentes curriculares

/** ID da prova ativa na seção de questões. */
let _provaAtiva = null;

/** Callback armazenado para o modal de confirmação genérico. */
let _confirmarCallback = null;

/* ─────────────────────────────────────────
   2. INICIALIZAÇÃO
   ─────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
  usuario = requireAuth('ADMIN');
  if (!usuario) return;

  initUI(usuario);
  configurarNavegacao();
  configurarFiltros();
  carregarDashboard();
});

/* ─────────────────────────────────────────
   3. NAVEGAÇÃO ENTRE SEÇÕES
   ─────────────────────────────────────── */

/**
 * Navega para uma seção do painel, carregando os dados necessários.
 * @param {'dashboard'|'provas'|'questoes'|'usuarios'|'locais'|'relatorios'} secao
 */
function irPara(secao) {
  document.querySelectorAll('.dash-section').forEach(s => s.classList.add('hidden'));

  const el = document.getElementById(`section-${secao}`);
  if (el) el.classList.remove('hidden');

  // Sincroniza sidebar
  document.querySelectorAll('.sidebar-nav .nav-link').forEach(a => {
    const target = a.dataset.section;
    a.classList.toggle('active', target === secao);
  });

  // Carrega dados conforme seção
  const loaders = {
    dashboard:    carregarDashboard,
    provas:       carregarProvas,
    usuarios:     carregarUsuarios,
    locais:       carregarLocais,
    componentes:  carregarComponentes,
    relatorios:   carregarRelatorios,
  };
  if (loaders[secao]) loaders[secao]();

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function configurarNavegacao() {
  document.querySelectorAll('.sidebar-nav .nav-link').forEach(a => {
    a.addEventListener('click', e => {
      e.preventDefault();
      irPara(a.dataset.section);
    });
  });
}

/* ─────────────────────────────────────────
   4. DASHBOARD
   ─────────────────────────────────────── */

async function carregarDashboard() {
  try {
    // Chamadas em paralelo — falhas individuais não quebram o painel
    const [provasRes, usuariosRes, locaisRes] = await Promise.allSettled([
      apiFetch('/provas'),
      apiFetch('/usuarios'),
      apiFetch('/locais'),
    ]);

    const provas   = provasRes.status   === 'fulfilled' ? (provasRes.value?.provas   ?? provasRes.value   ?? []) : [];
    const usuarios = usuariosRes.status === 'fulfilled' ? (usuariosRes.value?.usuarios ?? usuariosRes.value ?? []) : [];
    const locais   = locaisRes.status   === 'fulfilled' ? (locaisRes.value?.locais   ?? locaisRes.value   ?? []) : [];

    // Métricas
    const publicadas  = provas.filter(p => p.status === 'PUBLICADA');
    const alunos      = usuarios.filter(u => u.perfil === 'ALUNO');

    _setEl('dash-total-provas',    publicadas.length);
    _setEl('dash-sub-provas',      `${provas.length} no total, ${publicadas.length} publicadas`);
    _setEl('dash-total-usuarios',  alunos.length);
    _setEl('dash-sub-usuarios',    `${usuarios.length} usuário(s) cadastrado(s)`);
    _setEl('dash-total-locais',    locais.length);

    // Tentativas: não há endpoint global; exibimos traço se não disponível
    _setEl('dash-total-tentativas', '—');

    // Tabela de provas recentes (últimas 5 por created_at)
    const recentes = [...provas]
      .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
      .slice(0, 5);

    const tbody = document.getElementById('dash-provas-recentes');
    tbody.innerHTML = recentes.length
      ? recentes.map(p => `
          <tr>
            <td class="td-name">${p.titulo}</td>
            <td>${badgeTipoProva(p.tipo)}</td>
            <td>${badgeStatusProva(p.status)}</td>
          </tr>`).join('')
      : `<tr><td colspan="3" class="table-empty">Nenhuma prova cadastrada ainda.</td></tr>`;

  } catch (err) {
    showToast('Erro ao carregar dashboard.', 'danger');
  }
}

/* ─────────────────────────────────────────
   5. PROVAS — LISTAGEM E FILTROS
   ─────────────────────────────────────── */

async function carregarProvas() {
  const tbody = document.getElementById('provas-tbody');
  tbody.innerHTML = `<tr><td colspan="7" class="table-empty">Carregando provas...</td></tr>`;

  try {
    setLoading(true);
    const data = await apiFetch('/provas');
    _provas = Array.isArray(data) ? data : (data?.provas ?? []);
    _renderProvas(_provas);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="table-empty">Erro ao carregar: ${err.message}</td></tr>`;
    showToast('Falha ao carregar provas.', 'danger');
  } finally {
    setLoading(false);
  }
}

function _renderProvas(lista) {
  const tbody = document.getElementById('provas-tbody');
  if (!lista.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="table-empty">Nenhuma prova encontrada.</td></tr>`;
    return;
  }

  tbody.innerHTML = lista.map(p => `
    <tr data-titulo="${(p.titulo || '').toLowerCase()}"
        data-tipo="${p.tipo || ''}"
        data-status="${p.status || ''}"
        data-nivel="${p.nivel || ''}">
      <td class="td-name">${p.titulo || '—'}</td>
      <td class="td-muted">${nivelLabel(p.nivel)}${p.serie ? ' — ' + p.serie : ''}</td>
      <td>${badgeTipoProva(p.tipo)}</td>
      <td class="td-muted">${p.total_questoes ?? '—'}</td>
      <td class="td-muted">${p.data_inicio_inscricao ? formatarData(p.data_inicio_inscricao) : '—'}</td>
      <td>${badgeStatusProva(p.status)}</td>
      <td>
        <div class="td-actions">
          <button class="btn btn-ghost btn-sm" onclick="abrirSecaoQuestoes(${p.id}, '${_esc(p.titulo)}', '${p.status}')">
            Questões
          </button>
          ${p.status === 'RASCUNHO'
            ? `<button class="btn btn-secondary btn-sm" onclick="publicarProva(${p.id})">Publicar</button>`
            : ''}
          <button class="btn btn-ghost btn-sm" onclick="abrirModalEditarProva(${p.id})">Editar</button>
          <button class="btn btn-danger btn-sm" onclick="confirmarExclusao(
            'Excluir prova',
            'Deseja excluir a prova <strong>${_esc(p.titulo)}</strong>? Esta ação não pode ser desfeita.',
            () => excluirProva(${p.id})
          )">Excluir</button>
        </div>
      </td>
    </tr>`).join('');
}

function _filtrarProvas() {
  const busca  = (document.getElementById('provas-busca')?.value || '').toLowerCase();
  const tipo   = document.getElementById('provas-filtro-tipo')?.value   || '';
  const status = document.getElementById('provas-filtro-status')?.value || '';
  const nivel  = document.getElementById('provas-filtro-nivel')?.value  || '';

  document.querySelectorAll('#provas-tbody tr[data-titulo]').forEach(tr => {
    const ok = tr.dataset.titulo.includes(busca)
      && (!tipo   || tr.dataset.tipo   === tipo)
      && (!status || tr.dataset.status === status)
      && (!nivel  || tr.dataset.nivel  === nivel);
    tr.style.display = ok ? '' : 'none';
  });
}

async function publicarProva(id) {
  try {
    await apiFetch(`/provas/${id}/publicar`, { method: 'PATCH' });
    showToast('Prova publicada com sucesso!', 'success');
    carregarProvas();
  } catch (err) {
    showToast(err.message || 'Erro ao publicar prova.', 'danger');
  }
}

async function excluirProva(id) {
  try {
    await apiFetch(`/provas/${id}`, { method: 'DELETE' });
    showToast('Prova excluída.', 'success');
    carregarProvas();
  } catch (err) {
    showToast(err.message || 'Erro ao excluir prova.', 'danger');
  }
}

/* ─────────────────────────────────────────
   6. MODAL DE PROVA — CRIAR / EDITAR
   ─────────────────────────────────────── */

function abrirModalNovaProva() {
  _limparFormProva();
  document.getElementById('modal-prova-titulo').textContent = 'Nova prova';
  document.getElementById('prova-id').value = '';
  openModal('modal-prova');
}

async function abrirModalEditarProva(id) {
  _limparFormProva();
  document.getElementById('modal-prova-titulo').textContent = 'Editar prova';

  try {
    setLoading(true);
    const p = await apiFetch(`/provas/${id}`);
    document.getElementById('prova-id').value           = p.id;
    document.getElementById('prova-titulo').value       = p.titulo || '';
    document.getElementById('prova-descricao').value    = p.descricao || '';
    document.getElementById('prova-nivel').value        = p.nivel || '';
    document.getElementById('prova-serie').value        = p.serie || '';
    document.getElementById('prova-tipo').value         = p.tipo || '';
    document.getElementById('prova-nota-minima').value  = p.nota_minima ?? '';
    document.getElementById('prova-tempo').value        = p.tempo_limite ?? '';
    document.getElementById('prova-data-inicio').value  = _toDatetimeLocal(p.data_inicio_inscricao);
    document.getElementById('prova-data-fim').value     = _toDatetimeLocal(p.data_fim_inscricao);
    document.getElementById('prova-inscricao-inicio').value = _toDatetimeLocal(p.data_inicio_inscricao);
    document.getElementById('prova-inscricao-fim').value    = _toDatetimeLocal(p.data_fim_inscricao);
    openModal('modal-prova');
  } catch (err) {
    showToast('Erro ao carregar dados da prova.', 'danger');
  } finally {
    setLoading(false);
  }
}

async function salvarProva() {
  const id     = document.getElementById('prova-id').value;
  const titulo = document.getElementById('prova-titulo').value.trim();
  const nivel  = document.getElementById('prova-nivel').value;
  const serie  = document.getElementById('prova-serie').value.trim();
  const tipo   = document.getElementById('prova-tipo').value;

  if (!titulo || titulo.length < 3) {
    showToast('Título obrigatório (mínimo 3 caracteres).', 'warning'); return;
  }
  if (!nivel) { showToast('Selecione o nível.', 'warning'); return; }
  if (!serie) { showToast('Informe a série.', 'warning'); return; }
  if (!tipo)  { showToast('Selecione o tipo.', 'warning'); return; }

  const corpo = {
    titulo,
    descricao:             document.getElementById('prova-descricao').value.trim() || null,
    nivel,
    serie,
    tipo,
    nota_minima:           _parseNum('prova-nota-minima'),
    tempo_limite:          _parseNum('prova-tempo'),
    data_inicio_inscricao: document.getElementById('prova-inscricao-inicio').value || null,
    data_fim_inscricao:    document.getElementById('prova-inscricao-fim').value    || null,
  };

  const btn = document.getElementById('btn-salvar-prova');
  btn.disabled = true;
  btn.textContent = 'Salvando...';

  try {
    if (id) {
      await apiFetch(`/provas/${id}`, { method: 'PUT', body: JSON.stringify(corpo) });
      showToast('Prova atualizada com sucesso!', 'success');
    } else {
      await apiFetch('/provas', { method: 'POST', body: JSON.stringify(corpo) });
      showToast('Prova criada! Adicione questões agora.', 'success');
    }
    closeModal('modal-prova');
    carregarProvas();
  } catch (err) {
    showToast(err.message || 'Erro ao salvar prova.', 'danger');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Salvar prova';
  }
}

function _limparFormProva() {
  ['prova-id','prova-titulo','prova-descricao','prova-serie',
   'prova-nota-minima','prova-tempo','prova-data-inicio',
   'prova-data-fim','prova-inscricao-inicio','prova-inscricao-fim']
    .forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  document.getElementById('prova-nivel').value = '';
  document.getElementById('prova-tipo').value  = '';
}

/* ─────────────────────────────────────────
   7. QUESTÕES — LISTAGEM E AÇÕES
   ─────────────────────────────────────── */

/**
 * Navega para a subseção de questões de uma prova.
 * @param {number} provaId
 * @param {string} titulo
 * @param {string} status  – 'RASCUNHO' | 'PUBLICADA'
 */
function abrirSecaoQuestoes(provaId, titulo, status) {
  _provaAtiva = { id: provaId, titulo, status };

  _setEl('questoes-prova-titulo', `Questões — ${titulo}`);
  _setEl('questoes-prova-sub',
    status === 'PUBLICADA'
      ? 'Prova publicada. Edições de questões podem afetar tentativas em andamento.'
      : 'Rascunho. Adicione ou edite questões livremente antes de publicar.');

  document.getElementById('questao-prova-id').value = provaId;

  irPara('questoes');
  carregarQuestoes(provaId);
}

async function carregarQuestoes(provaId) {
  const lista = document.getElementById('questoes-lista');
  lista.innerHTML = `<div class="table-empty">Carregando questões...</div>`;

  try {
    const questoes = await apiFetch(`/questoes?prova_id=${provaId}`);
    const arr = Array.isArray(questoes) ? questoes : (questoes?.questoes ?? []);

    if (!arr.length) {
      lista.innerHTML = `<div class="table-empty">Nenhuma questão cadastrada. Clique em "+ Adicionar questão".</div>`;
      return;
    }

    lista.innerHTML = arr.map((q, i) => `
      <div class="card" style="padding:20px;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px;">
          <div style="flex:1;">
            <div style="font-size:12px; font-weight:600; color:var(--c-text-muted); margin-bottom:6px; text-transform:uppercase; letter-spacing:.5px;">
              Questão ${i + 1} &nbsp;·&nbsp; ${dificuldadeLabel(q.nivel_dificuldade)}
            </div>
            <p style="font-size:14px; color:var(--c-text); line-height:1.6; margin:0 0 12px;">
              ${q.enunciado || '—'}
            </p>
            <div style="display:flex; flex-direction:column; gap:6px;">
              ${(q.alternativas || [])
                .sort((a, b) => (a.ordem ?? 0) - (b.ordem ?? 0))
                .map((alt, idx) => `
                  <div style="display:flex; gap:8px; align-items:center; font-size:13px; color:${alt.is_correta ? 'var(--c-success)' : 'var(--c-text-muted)'};">
                    <span style="font-weight:700; min-width:16px;">${String.fromCharCode(65 + idx)}${alt.is_correta ? ' ✓' : ''}</span>
                    <span>${alt.texto}</span>
                  </div>`).join('')}
            </div>
          </div>
          <div class="td-actions" style="flex-shrink:0;">
            <button class="btn btn-ghost btn-sm" onclick="abrirModalEditarQuestao(${q.id})">Editar</button>
            <button class="btn btn-danger btn-sm" onclick="confirmarExclusao(
              'Excluir questão',
              'Tem certeza que deseja excluir esta questão?',
              () => excluirQuestao(${q.id})
            )">Excluir</button>
          </div>
        </div>
      </div>`).join('');

  } catch (err) {
    lista.innerHTML = `<div class="table-empty">Erro ao carregar questões: ${err.message}</div>`;
  }
}

async function excluirQuestao(id) {
  try {
    await apiFetch(`/questoes/${id}`, { method: 'DELETE' });
    showToast('Questão excluída.', 'success');
    carregarQuestoes(_provaAtiva.id);
  } catch (err) {
    showToast(err.message || 'Erro ao excluir questão.', 'danger');
  }
}

/* ─────────────────────────────────────────
   8. MODAL DE QUESTÃO + ALTERNATIVAS
   ─────────────────────────────────────── */

/** Contador interno para IDs únicos das alternativas no DOM. */
let _altCounter = 0;

function abrirModalNovaQuestao() {
  _limparFormQuestao();
  document.getElementById('modal-questao-titulo').textContent = 'Nova questão';
  document.getElementById('questao-id').value = '';
  document.getElementById('questao-prova-id').value = _provaAtiva?.id || '';
  // Inicia com 2 alternativas (mínimo obrigatório — US10)
  adicionarAlternativa();
  adicionarAlternativa();
  carregarComponentesSelect();   // US38 — preenche o select de componente
  openModal('modal-questao');
}

async function abrirModalEditarQuestao(id) {
  _limparFormQuestao();
  document.getElementById('modal-questao-titulo').textContent = 'Editar questão';

  try {
    setLoading(true);
    const q = await apiFetch(`/questoes/${id}`);
    document.getElementById('questao-id').value          = q.id;
    document.getElementById('questao-enunciado').value   = q.enunciado || '';
    document.getElementById('questao-dificuldade').value = q.nivel_dificuldade || 'MEDIO';

    // Recria as alternativas no DOM
    (q.alternativas || [])
      .sort((a, b) => (a.ordem ?? 0) - (b.ordem ?? 0))
      .forEach(alt => adicionarAlternativa(alt.texto, alt.is_correta));

    // Garante mínimo de 2 se vieram menos
    const total = document.querySelectorAll('.alt-row').length;
    for (let i = total; i < 2; i++) adicionarAlternativa();

    // US38 — preenche select de componente e seleciona o vinculado
    await carregarComponentesSelect(q.componente_id ?? null);

    openModal('modal-questao');
  } catch (err) {
    showToast('Erro ao carregar questão.', 'danger');
  } finally {
    setLoading(false);
  }
}

/**
 * Adiciona uma linha de alternativa no modal.
 * @param {string}  texto      – Texto pré-preenchido (edição)
 * @param {boolean} isCorreta  – Marcar como correta
 */
function adicionarAlternativa(texto = '', isCorreta = false) {
  const container = document.getElementById('alternativas-container');
  const total = container.querySelectorAll('.alt-row').length;

  // Máximo de 5 alternativas
  if (total >= 5) {
    showToast('Máximo de 5 alternativas por questão.', 'warning');
    return;
  }

  const uid = ++_altCounter;
  const letras = ['A', 'B', 'C', 'D', 'E'];
  const letra = letras[total] || total + 1;

  const row = document.createElement('div');
  row.className = 'alt-row';
  row.dataset.uid = uid;
  row.style.cssText = 'display:flex; align-items:center; gap:10px;';
  row.innerHTML = `
    <span style="font-weight:700; font-size:14px; min-width:20px; color:var(--c-text-muted);">${letra}</span>
    <input class="form-input alt-texto" type="text"
      placeholder="Texto da alternativa ${letra}"
      value="${_esc(texto)}"
      style="flex:1;"
      oninput="this.closest('.alt-row').querySelector('.alt-correta').disabled = false;">
    <label style="display:flex; align-items:center; gap:4px; font-size:13px; cursor:pointer; white-space:nowrap; color:var(--c-text-muted);"
      title="Marcar como correta">
      <input type="radio" class="alt-correta" name="alternativa-correta"
        ${isCorreta ? 'checked' : ''}>
      Correta
    </label>
    <button type="button" class="btn btn-ghost btn-sm"
      onclick="removerAlternativa(this)"
      title="Remover alternativa"
      style="padding:4px 8px; font-size:16px; line-height:1;">✕</button>
  `;
  container.appendChild(row);
}

function removerAlternativa(btn) {
  const container = document.getElementById('alternativas-container');
  if (container.querySelectorAll('.alt-row').length <= 2) {
    showToast('A questão precisa de pelo menos 2 alternativas.', 'warning');
    return;
  }
  btn.closest('.alt-row').remove();
  // Reatribui letras
  container.querySelectorAll('.alt-row').forEach((row, i) => {
    const letras = ['A', 'B', 'C', 'D', 'E'];
    row.querySelector('span').textContent = letras[i] || i + 1;
  });
}

async function salvarQuestao() {
  const id       = document.getElementById('questao-id').value;
  const provaId  = document.getElementById('questao-prova-id').value || _provaAtiva?.id;
  const enunciado = document.getElementById('questao-enunciado').value.trim();
  const dificuldade = document.getElementById('questao-dificuldade').value;

  if (!enunciado) { showToast('O enunciado não pode ser vazio.', 'warning'); return; }

  // Coleta alternativas
  const rows = document.querySelectorAll('#alternativas-container .alt-row');
  const alternativas = [];
  let corretaCount = 0;

  rows.forEach((row, i) => {
    const texto     = row.querySelector('.alt-texto').value.trim();
    const isCorreta = row.querySelector('.alt-correta').checked;
    if (isCorreta) corretaCount++;
    alternativas.push({ texto, is_correta: isCorreta, ordem: i + 1 });
  });

  // Validações US10
  if (alternativas.length < 2) {
    showToast('Mínimo de 2 alternativas.', 'warning'); return;
  }
  if (alternativas.some(a => !a.texto)) {
    showToast('Nenhuma alternativa pode ter texto vazio.', 'warning'); return;
  }
  if (corretaCount === 0) {
    showToast('Marque exatamente 1 alternativa como correta.', 'warning'); return;
  }
  if (corretaCount > 1) {
    showToast('Apenas 1 alternativa pode ser a correta.', 'warning'); return;
  }

  const corpo = {
    enunciado,
    prova_id: Number(provaId),
    nivel_dificuldade: dificuldade,
    alternativas,
    componente_id: Number(document.getElementById('questao-componente').value) || null,
  };

  try {
    setLoading(true);
    if (id) {
      await apiFetch(`/questoes/${id}`, { method: 'PUT', body: JSON.stringify(corpo) });
      showToast('Questão atualizada!', 'success');
    } else {
      await apiFetch('/questoes', { method: 'POST', body: JSON.stringify(corpo) });
      showToast('Questão criada!', 'success');
    }
    closeModal('modal-questao');
    carregarQuestoes(_provaAtiva.id);
  } catch (err) {
    showToast(err.message || 'Erro ao salvar questão.', 'danger');
  } finally {
    setLoading(false);
  }
}

function _limparFormQuestao() {
  document.getElementById('questao-id').value        = '';
  document.getElementById('questao-enunciado').value = '';
  document.getElementById('questao-dificuldade').value = 'MEDIO';
  document.getElementById('questao-componente').value  = '';
  document.getElementById('alternativas-container').innerHTML = '';
  _altCounter = 0;
}

/* ─────────────────────────────────────────
   9. COMPONENTES CURRICULARES (US36–38)
   ─────────────────────────────────────── */

/**
 * Carrega e renderiza a lista de componentes curriculares (US36).
 */
async function carregarComponentes() {
  const tbody = document.getElementById('comp-tbody');
  tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Carregando...</td></tr>`;

  try {
    setLoading(true);
    const data = await apiFetch('/componentes/');
    _componentes = Array.isArray(data) ? data : (data?.componentes ?? []);
    _renderComponentes(_componentes);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Erro ao carregar componentes.</td></tr>`;
    showToast('Erro ao carregar componentes.', 'danger');
  } finally {
    setLoading(false);
  }
}

function _renderComponentes(lista) {
  const tbody = document.getElementById('comp-tbody');

  if (!lista.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Nenhum componente cadastrado ainda.</td></tr>`;
    return;
  }

  tbody.innerHTML = lista.map(c => `
    <tr data-nome="${(c.nome || '').toLowerCase()}" data-codigo="${(c.codigo || '').toLowerCase()}" data-nivel="${(c.nivel || '').toLowerCase()}">
      <td class="td-name">${c.nome}</td>
      <td><span class="badge badge-simulado">${c.codigo || '—'}</span></td>
      <td class="td-muted">${nivelLabel(c.nivel) || '—'}</td>
      <td class="td-muted">${c.serie || '—'}</td>
      <td class="td-muted" style="max-width:200px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;"
        title="${_esc(c.descricao || '')}">${c.descricao || '—'}</td>
      <td>
        <div class="td-actions">
          <button class="btn btn-ghost btn-sm" onclick="abrirModalEditarComponente(${c.id})">Editar</button>
          <button class="btn btn-ghost btn-sm btn-danger" onclick="excluirComponente(${c.id}, '${_esc(c.nome)}')">Excluir</button>
        </div>
      </td>
    </tr>`).join('');
}

/** Filtra a tabela de componentes no frontend. */
function _filtrarComponentes() {
  const q = (document.getElementById('comp-busca')?.value || '').toLowerCase();
  document.querySelectorAll('#comp-tbody tr[data-nome]').forEach(tr => {
    const match = !q
      || tr.dataset.nome.includes(q)
      || tr.dataset.codigo.includes(q)
      || tr.dataset.nivel.includes(q);
    tr.style.display = match ? '' : 'none';
  });
}

/** Abre modal para criar novo componente. */
function abrirModalNovoComponente() {
  _limparFormComponente();
  document.getElementById('modal-comp-titulo').textContent = 'Novo componente curricular';
  openModal('modal-componente');
}

/** Abre modal para editar componente existente. */
async function abrirModalEditarComponente(id) {
  _limparFormComponente();
  document.getElementById('modal-comp-titulo').textContent = 'Editar componente curricular';

  try {
    setLoading(true);
    const c = await apiFetch(`/componentes/${id}`);
    document.getElementById('comp-id').value        = c.id;
    document.getElementById('comp-nome').value      = c.nome || '';
    document.getElementById('comp-codigo').value    = c.codigo || '';
    document.getElementById('comp-nivel').value     = c.nivel || '';
    document.getElementById('comp-serie').value     = c.serie || '';
    document.getElementById('comp-descricao').value = c.descricao || '';
    openModal('modal-componente');
  } catch (err) {
    showToast('Erro ao carregar componente.', 'danger');
  } finally {
    setLoading(false);
  }
}

/** Salva (cria ou atualiza) um componente curricular. */
async function salvarComponente() {
  const id   = document.getElementById('comp-id').value;
  const nome = document.getElementById('comp-nome').value.trim();

  if (!nome) {
    showToast('O nome do componente é obrigatório.', 'warning');
    return;
  }

  const corpo = {
    nome,
    codigo:    document.getElementById('comp-codigo').value.trim().toUpperCase() || null,
    nivel:     document.getElementById('comp-nivel').value || null,
    serie:     document.getElementById('comp-serie').value.trim() || null,
    descricao: document.getElementById('comp-descricao').value.trim() || null,
  };

  try {
    setLoading(true);
    if (id) {
      await apiFetch(`/componentes/${id}`, { method: 'PUT', body: JSON.stringify(corpo) });
      showToast('Componente atualizado!', 'success');
    } else {
      await apiFetch('/componentes/', { method: 'POST', body: JSON.stringify(corpo) });
      showToast('Componente criado!', 'success');
    }
    closeModal('modal-componente');
    carregarComponentes();
  } catch (err) {
    showToast(err.message || 'Erro ao salvar componente.', 'danger');
  } finally {
    setLoading(false);
  }
}

/** Exclui um componente com confirmação. */
function excluirComponente(id, nome) {
  confirmarAcao(
    `Excluir o componente "${nome}"?`,
    `Esta ação não pode ser desfeita. Questões vinculadas a este componente não serão deletadas, mas perderão o vínculo.`,
    async () => {
      try {
        setLoading(true);
        await apiFetch(`/componentes/${id}`, { method: 'DELETE' });
        showToast('Componente excluído.', 'success');
        carregarComponentes();
      } catch (err) {
        showToast(err.message || 'Erro ao excluir componente.', 'danger');
      } finally {
        setLoading(false);
      }
    }
  );
}

/** Limpa o formulário do modal de componente. */
function _limparFormComponente() {
  ['comp-id','comp-nome','comp-codigo','comp-serie','comp-descricao'].forEach(id => {
    document.getElementById(id).value = '';
  });
  document.getElementById('comp-nivel').value = '';
}

/**
 * Preenche o <select id="questao-componente"> com os componentes disponíveis.
 * Usado nos modais de criar/editar questão (US38).
 * @param {number|null} selecionadoId – ID a pré-selecionar (edição).
 */
async function carregarComponentesSelect(selecionadoId = null) {
  const sel = document.getElementById('questao-componente');
  if (!sel) return;

  // Usa cache se já carregado; caso contrário busca da API
  if (!_componentes.length) {
    try {
      const data = await apiFetch('/componentes/');
      _componentes = Array.isArray(data) ? data : (data?.componentes ?? []);
    } catch {
      sel.innerHTML = `<option value="">Erro ao carregar componentes</option>`;
      return;
    }
  }

  sel.innerHTML =
    `<option value="">Selecione o componente</option>` +
    _componentes.map(c =>
      `<option value="${c.id}" ${c.id === selecionadoId ? 'selected' : ''}>${c.nome}${c.codigo ? ' (' + c.codigo + ')' : ''}</option>`
    ).join('');
}

/* ─────────────────────────────────────────
   10. USUÁRIOS — LISTAGEM E AÇÕES
   ─────────────────────────────────────── */

async function carregarUsuarios() {
  const tbody = document.getElementById('usuarios-tbody');
  tbody.innerHTML = `<tr><td colspan="7" class="table-empty">Carregando usuários...</td></tr>`;

  try {
    setLoading(true);
    const data = await apiFetch('/usuarios');
    _usuarios = Array.isArray(data) ? data : (data?.usuarios ?? []);
    _renderUsuarios(_usuarios);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="table-empty">Erro: ${err.message}</td></tr>`;
    showToast('Falha ao carregar usuários.', 'danger');
  } finally {
    setLoading(false);
  }
}

function _renderUsuarios(lista) {
  const tbody = document.getElementById('usuarios-tbody');
  if (!lista.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="table-empty">Nenhum usuário encontrado.</td></tr>`;
    return;
  }

  tbody.innerHTML = lista.map(u => `
    <tr data-nome="${(u.nome || '').toLowerCase()}"
        data-email="${(u.email || '').toLowerCase()}"
        data-perfil="${u.perfil || ''}"
        data-status="${u.status || ''}">
      <td class="td-name">${u.nome || '—'}</td>
      <td class="td-muted">${u.email || '—'}</td>
      <td>
        <span class="badge ${u.perfil === 'ADMIN' ? 'badge-certificacao' : 'badge-aluno'}">
          ${u.perfil === 'ADMIN' ? 'Admin' : 'Aluno'}
        </span>
      </td>
      <td class="td-muted">${nivelLabel(u.nivel)}</td>
      <td>${badgeStatusUsuario(u.status || 'ATIVO')}</td>
      <td class="td-muted">${formatarData(u.created_at)}</td>
      <td>
        <div class="td-actions">
          ${u.status === 'BLOQUEADO'
            ? `<button class="btn btn-secondary btn-sm" onclick="desbloquearUsuario(${u.id}, '${_esc(u.nome)}')">Desbloquear</button>`
            : `<button class="btn btn-ghost btn-sm" onclick="confirmarExclusao(
                'Bloquear usuário',
                'Bloquear <strong>${_esc(u.nome)}</strong>? O aluno não poderá mais fazer login.',
                () => bloquearUsuario(${u.id}, '${_esc(u.nome)}')
               )">Bloquear</button>`}
          <button class="btn btn-danger btn-sm" onclick="confirmarExclusao(
            'Excluir usuário',
            'Excluir <strong>${_esc(u.nome)}</strong> permanentemente?',
            () => excluirUsuario(${u.id})
          )">Excluir</button>
        </div>
      </td>
    </tr>`).join('');
}

function _filtrarUsuarios() {
  const busca  = (document.getElementById('usuarios-busca')?.value || '').toLowerCase();
  const perfil = document.getElementById('usuarios-filtro-perfil')?.value || '';
  const status = document.getElementById('usuarios-filtro-status')?.value || '';

  document.querySelectorAll('#usuarios-tbody tr[data-nome]').forEach(tr => {
    const ok = (tr.dataset.nome.includes(busca) || tr.dataset.email.includes(busca))
      && (!perfil || tr.dataset.perfil === perfil)
      && (!status || tr.dataset.status === status);
    tr.style.display = ok ? '' : 'none';
  });
}

async function bloquearUsuario(id, nome) {
  try {
    await apiFetch(`/usuarios/${id}/bloquear`, { method: 'PATCH' });
    showToast(`${nome} foi bloqueado.`, 'success');
    carregarUsuarios();
  } catch (err) {
    showToast(err.message || 'Erro ao bloquear usuário.', 'danger');
  }
}

async function desbloquearUsuario(id, nome) {
  try {
    await apiFetch(`/usuarios/${id}/desbloquear`, { method: 'PATCH' });
    showToast(`${nome} foi desbloqueado.`, 'success');
    carregarUsuarios();
  } catch (err) {
    showToast(err.message || 'Erro ao desbloquear usuário.', 'danger');
  }
}

async function excluirUsuario(id) {
  try {
    await apiFetch(`/usuarios/${id}`, { method: 'DELETE' });
    showToast('Usuário excluído.', 'success');
    carregarUsuarios();
  } catch (err) {
    showToast(err.message || 'Erro ao excluir usuário.', 'danger');
  }
}

/* ─────────────────────────────────────────
   10. MODAL DE USUÁRIO — CADASTRAR
   ─────────────────────────────────────── */

function abrirModalNovoUsuario() {
  ['usu-nome','usu-email','usu-senha','usu-confirmar-senha','usu-serie','usu-admin-token']
    .forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  document.getElementById('usu-perfil').value = 'ALUNO';
  document.getElementById('usu-nivel').value  = 'MEDIO';
  toggleCamposAluno();
  openModal('modal-usuario');
}

/** Mostra/oculta campos de nível e token conforme o perfil selecionado. */
function toggleCamposAluno() {
  const perfil = document.getElementById('usu-perfil')?.value;
  const isAluno = perfil === 'ALUNO';
  const campoNivel  = document.getElementById('campo-nivel');
  const campoSerie  = document.getElementById('campo-serie');
  const campoAdmin  = document.getElementById('campo-admin-token');
  if (campoNivel) campoNivel.style.display = isAluno ? '' : 'none';
  if (campoSerie) campoSerie.style.display = isAluno ? '' : 'none';
  if (campoAdmin) campoAdmin.classList.toggle('hidden', isAluno);
}

async function salvarUsuario() {
  const nome   = document.getElementById('usu-nome').value.trim();
  const email  = document.getElementById('usu-email').value.trim();
  const senha  = document.getElementById('usu-senha').value;
  const conf   = document.getElementById('usu-confirmar-senha').value;
  const perfil = document.getElementById('usu-perfil').value;
  const nivel  = document.getElementById('usu-nivel').value;
  const serie  = document.getElementById('usu-serie')?.value.trim() || null;
  const token  = document.getElementById('usu-admin-token')?.value || '';

  if (!nome || nome.length < 2)  { showToast('Nome inválido (mínimo 2 caracteres).', 'warning'); return; }
  if (!email)                     { showToast('Informe o e-mail.', 'warning'); return; }
  if (senha.length < 8)           { showToast('Senha mínima de 8 caracteres.', 'warning'); return; }
  if (senha !== conf)             { showToast('As senhas não coincidem.', 'warning'); return; }
  if (perfil === 'ALUNO' && !nivel) { showToast('Selecione o nível.', 'warning'); return; }
  if (perfil === 'ADMIN' && !token) { showToast('Informe o token de administrador.', 'warning'); return; }

  const corpo = {
    nome, email,
    senha,
    confirmar_senha: conf,
    perfil,
    ...(perfil === 'ALUNO' ? { nivel, serie } : {}),
    ...(perfil === 'ADMIN' ? { admin_token: token } : {}),
  };

  try {
    setLoading(true);
    await apiFetch('/auth/register', { method: 'POST', body: JSON.stringify(corpo) });
    showToast('Usuário cadastrado com sucesso!', 'success');
    closeModal('modal-usuario');
    carregarUsuarios();
  } catch (err) {
    showToast(err.message || 'Erro ao cadastrar usuário.', 'danger');
  } finally {
    setLoading(false);
  }
}

/* ─────────────────────────────────────────
   11. LOCAIS — LISTAGEM E AÇÕES
   ─────────────────────────────────────── */

async function carregarLocais() {
  const tbody = document.getElementById('locais-tbody');
  tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Carregando locais...</td></tr>`;

  try {
    setLoading(true);
    const data = await apiFetch('/locais');
    _locais = Array.isArray(data) ? data : (data?.locais ?? []);
    _renderLocais(_locais);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Erro: ${err.message}</td></tr>`;
    showToast('Falha ao carregar locais.', 'danger');
  } finally {
    setLoading(false);
  }
}

function _renderLocais(lista) {
  const tbody = document.getElementById('locais-tbody');
  if (!lista.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Nenhum local cadastrado ainda.</td></tr>`;
    return;
  }

  tbody.innerHTML = lista.map(l => `
    <tr data-nome="${(l.nome || '').toLowerCase()}"
        data-cidade="${(l.cidade || '').toLowerCase()}">
      <td class="td-name">${l.nome || '—'}</td>
      <td class="td-muted">${l.cidade || '—'}${l.estado ? ' / ' + l.estado : ''}</td>
      <td class="td-muted" style="max-width:200px; white-space:normal;">${l.endereco || '—'}</td>
      <td class="td-muted">${l.capacidade ?? '—'}</td>
      <td>
        <span class="badge ${l.vagas_restantes > 0 ? 'badge-publicada' : 'badge-rascunho'}">
          ${l.vagas_restantes ?? 0} vaga(s)
        </span>
      </td>
      <td>
        <div class="td-actions">
          <button class="btn btn-ghost btn-sm" onclick="abrirModalEditarLocal(${l.id})">Editar</button>
          <button class="btn btn-danger btn-sm" onclick="confirmarExclusao(
            'Excluir local',
            'Excluir o local <strong>${_esc(l.nome)}</strong>? Reservas vinculadas podem ser afetadas.',
            () => excluirLocal(${l.id})
          )">Excluir</button>
        </div>
      </td>
    </tr>`).join('');
}

function _filtrarLocais() {
  const busca = (document.getElementById('locais-busca')?.value || '').toLowerCase();
  document.querySelectorAll('#locais-tbody tr[data-nome]').forEach(tr => {
    const ok = tr.dataset.nome.includes(busca) || tr.dataset.cidade.includes(busca);
    tr.style.display = ok ? '' : 'none';
  });
}

async function excluirLocal(id) {
  try {
    await apiFetch(`/locais/${id}`, { method: 'DELETE' });
    showToast('Local excluído.', 'success');
    carregarLocais();
  } catch (err) {
    showToast(err.message || 'Erro ao excluir local.', 'danger');
  }
}

/* ─────────────────────────────────────────
   12. MODAL DE LOCAL — CRIAR / EDITAR
   ─────────────────────────────────────── */

function abrirModalNovoLocal() {
  _limparFormLocal();
  document.getElementById('modal-local-titulo').textContent = 'Cadastrar local';
  document.getElementById('local-id').value = '';
  openModal('modal-local');
}

async function abrirModalEditarLocal(id) {
  _limparFormLocal();
  document.getElementById('modal-local-titulo').textContent = 'Editar local';

  try {
    setLoading(true);
    const l = await apiFetch(`/locais/${id}`);
    document.getElementById('local-id').value         = l.id;
    document.getElementById('local-nome').value       = l.nome || '';
    document.getElementById('local-endereco').value   = l.endereco || '';
    document.getElementById('local-cidade').value     = l.cidade || '';
    document.getElementById('local-estado').value     = l.estado || '';
    document.getElementById('local-cep').value        = l.cep || '';
    document.getElementById('local-contato').value    = l.contato || '';
    document.getElementById('local-capacidade').value = l.capacidade ?? '';
    document.getElementById('local-vagas').value      = l.vagas_restantes ?? '';

    // Extrai lat/lng do objeto GeoJSON ou campos diretos
    if (l.latitude !== undefined)  document.getElementById('local-lat').value = l.latitude;
    if (l.longitude !== undefined) document.getElementById('local-lng').value = l.longitude;
    if (l.geolocalizacao?.coordinates) {
      document.getElementById('local-lng').value = l.geolocalizacao.coordinates[0];
      document.getElementById('local-lat').value = l.geolocalizacao.coordinates[1];
    }

    openModal('modal-local');
  } catch (err) {
    showToast('Erro ao carregar local.', 'danger');
  } finally {
    setLoading(false);
  }
}

async function salvarLocal() {
  const id        = document.getElementById('local-id').value;
  const nome      = document.getElementById('local-nome').value.trim();
  const endereco  = document.getElementById('local-endereco').value.trim();
  const cidade    = document.getElementById('local-cidade').value.trim();
  const estado    = document.getElementById('local-estado').value.trim().toUpperCase();
  const capacidade = parseInt(document.getElementById('local-capacidade').value, 10);
  const vagas     = parseInt(document.getElementById('local-vagas').value, 10);
  const lat       = parseFloat(document.getElementById('local-lat').value);
  const lng       = parseFloat(document.getElementById('local-lng').value);

  if (!nome)            { showToast('Informe o nome do local.', 'warning'); return; }
  if (!endereco)        { showToast('Informe o endereço.', 'warning'); return; }
  if (!cidade)          { showToast('Informe a cidade.', 'warning'); return; }
  if (!estado)          { showToast('Informe o estado (UF).', 'warning'); return; }
  if (!capacidade || capacidade < 1) { showToast('Capacidade inválida.', 'warning'); return; }
  if (isNaN(lat) || lat < -90  || lat > 90)  { showToast('Latitude inválida (−90 a 90).', 'warning'); return; }
  if (isNaN(lng) || lng < -180 || lng > 180) { showToast('Longitude inválida (−180 a 180).', 'warning'); return; }

  const corpo = {
    nome, endereco, cidade, estado,
    cep:       document.getElementById('local-cep').value.trim() || null,
    contato:   document.getElementById('local-contato').value.trim() || null,
    capacidade,
    vagas_restantes: isNaN(vagas) ? capacidade : vagas,
    latitude: lat,
    longitude: lng,
  };

  try {
    setLoading(true);
    if (id) {
      await apiFetch(`/locais/${id}`, { method: 'PUT', body: JSON.stringify(corpo) });
      showToast('Local atualizado!', 'success');
    } else {
      await apiFetch('/locais', { method: 'POST', body: JSON.stringify(corpo) });
      showToast('Local cadastrado!', 'success');
    }
    closeModal('modal-local');
    carregarLocais();
  } catch (err) {
    showToast(err.message || 'Erro ao salvar local.', 'danger');
  } finally {
    setLoading(false);
  }
}

function _limparFormLocal() {
  ['local-id','local-nome','local-endereco','local-cidade','local-estado',
   'local-cep','local-contato','local-capacidade','local-vagas','local-lat','local-lng']
    .forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
}

/* ─────────────────────────────────────────
   13. RELATÓRIOS
   ─────────────────────────────────────── */

async function carregarRelatorios() {
  try {
    setLoading(true);
    const data = await apiFetch('/relatorios/desempenho');

    _setEl('rel-provas-finalizadas', data?.total_tentativas ?? '—');
    _setEl('rel-certificados',       data?.total_certificados ?? '—');
    _setEl('rel-media',
      data?.media_geral != null ? Number(data.media_geral).toFixed(1) : '—');

    _renderDesempenhoNivel(data?.por_nivel ?? []);

    // Liga filtro de nível
    const sel = document.getElementById('rel-filtro-nivel');
    if (sel) {
      sel.onchange = () => _filtrarDesempenhoNivel(data?.por_nivel ?? [], sel.value);
    }

  } catch (err) {
    showToast('Erro ao carregar relatório.', 'danger');
    _setEl('rel-provas-finalizadas', '—');
    _setEl('rel-certificados', '—');
    _setEl('rel-media', '—');
  } finally {
    setLoading(false);
  }
}

function _renderDesempenhoNivel(porNivel) {
  const el = document.getElementById('rel-desempenho-lista');
  if (!porNivel.length) {
    el.innerHTML = `<div class="table-empty">Sem dados de desempenho ainda.</div>`;
    return;
  }

  el.innerHTML = `
    <div class="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>Nível</th>
            <th>Tentativas</th>
            <th>Média</th>
            <th>Taxa aprovação</th>
          </tr>
        </thead>
        <tbody id="rel-desempenho-tbody">
          ${porNivel.map(r => `
            <tr data-nivel="${r.nivel || ''}">
              <td class="td-name">${nivelLabel(r.nivel)}</td>
              <td class="td-muted">${r.total_tentativas ?? '—'}</td>
              <td><strong>${r.media != null ? Number(r.media).toFixed(1) : '—'}</strong></td>
              <td>
                <span class="badge ${(r.taxa_aprovacao ?? 0) >= 60 ? 'badge-aprovado' : 'badge-reprovado'}">
                  ${r.taxa_aprovacao != null ? Number(r.taxa_aprovacao).toFixed(0) + '%' : '—'}
                </span>
              </td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
}

function _filtrarDesempenhoNivel(porNivel, nivel) {
  const filtrado = nivel ? porNivel.filter(r => r.nivel === nivel) : porNivel;
  _renderDesempenhoNivel(filtrado);
}

async function exportarRelatorio(tipo = 'desempenho') {
  const btn = document.getElementById('btn-exportar');
  if (btn) { btn.disabled = true; btn.textContent = 'Gerando...'; }

  try {
    const token = getToken();
    const url   = `${API_BASE}/relatorios/exportar?tipo=${tipo}`;
    const resp  = await fetch(url, {
      headers: { 'Authorization': `Bearer ${token}` },
    });

    if (!resp.ok) throw new Error('Falha ao gerar exportação.');

    const blob = await resp.blob();
    const link = document.createElement('a');
    link.href  = URL.createObjectURL(blob);
    link.download = `relatorio_${tipo}_${new Date().toISOString().slice(0,10)}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
    showToast('Relatório exportado com sucesso!', 'success');

  } catch (err) {
    showToast(err.message || 'Erro ao exportar.', 'danger');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Exportar dados'; }
  }
}

/* ─────────────────────────────────────────
   14. MODAL DE CONFIRMAÇÃO GENÉRICO
   ─────────────────────────────────────── */

/**
 * Abre o modal de confirmação (exclusão, bloqueio, etc.)
 * @param {string}   titulo    – Título do modal
 * @param {string}   msg       – Mensagem HTML da confirmação
 * @param {Function} callback  – Executado ao confirmar
 */
function confirmarExclusao(titulo, msg, callback) {
  document.getElementById('modal-confirmar-titulo').textContent = titulo;
  document.getElementById('modal-confirmar-msg').innerHTML = msg;
  _confirmarCallback = callback;

  const btn = document.getElementById('btn-confirmar-acao');
  btn.onclick = async () => {
    closeModal('modal-confirmar');
    if (typeof _confirmarCallback === 'function') {
      await _confirmarCallback();
      _confirmarCallback = null;
    }
  };

  openModal('modal-confirmar');
}

/* ─────────────────────────────────────────
   15. CONFIGURAÇÃO DOS FILTROS (event listeners)
   ─────────────────────────────────────── */

function configurarFiltros() {
  // Provas
  const provasBusca  = document.getElementById('provas-busca');
  const provasTipo   = document.getElementById('provas-filtro-tipo');
  const provasStatus = document.getElementById('provas-filtro-status');
  const provasNivel  = document.getElementById('provas-filtro-nivel');
  if (provasBusca)  provasBusca.addEventListener('input',  debounce(_filtrarProvas, 250));
  if (provasTipo)   provasTipo.addEventListener('change',  _filtrarProvas);
  if (provasStatus) provasStatus.addEventListener('change', _filtrarProvas);
  if (provasNivel)  provasNivel.addEventListener('change',  _filtrarProvas);

  // Usuários
  const usuBusca  = document.getElementById('usuarios-busca');
  const usuPerfil = document.getElementById('usuarios-filtro-perfil');
  const usuStatus = document.getElementById('usuarios-filtro-status');
  if (usuBusca)  usuBusca.addEventListener('input',  debounce(_filtrarUsuarios, 250));
  if (usuPerfil) usuPerfil.addEventListener('change', _filtrarUsuarios);
  if (usuStatus) usuStatus.addEventListener('change', _filtrarUsuarios);

  // Locais
  const locaisBusca = document.getElementById('locais-busca');
  if (locaisBusca)  locaisBusca.addEventListener('input', debounce(_filtrarLocais, 250));

  // Componentes curriculares (US36)
  const compBusca = document.getElementById('comp-busca');
  if (compBusca) compBusca.addEventListener('input', debounce(_filtrarComponentes, 250));
}

/* ─────────────────────────────────────────
   16. HELPERS LOCAIS
   ─────────────────────────────────────── */

/** Define o textContent de um elemento pelo ID, sem lançar erro. */
function _setEl(id, valor) {
  const el = document.getElementById(id);
  if (el) el.textContent = valor ?? '—';
}

/** Escapa HTML para uso em atributos e innerHTML seguro. */
function _esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/** Converte ISO string para formato datetime-local (YYYY-MM-DDTHH:mm). */
function _toDatetimeLocal(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toISOString().slice(0, 16);
  } catch {
    return '';
  }
}

/** Lê um input numérico pelo ID e retorna number ou null. */
function _parseNum(id) {
  const val = parseFloat(document.getElementById(id)?.value);
  return isNaN(val) ? null : val;
}

/** Converte enum de nível para label legível. */
function nivelLabel(nivel) {
  const map = {
    FUNDAMENTAL_I:  'Fundamental I',
    FUNDAMENTAL_II: 'Fundamental II',
    MEDIO:          'Médio',
    ENEM:           'ENEM',
    EJA:            'EJA',
  };
  return map[nivel] || nivel || '—';
}

/** Converte enum de dificuldade para label legível. */
function dificuldadeLabel(d) {
  const map = { FACIL: 'Fácil', MEDIO: 'Médio', DIFICIL: 'Difícil' };
  return map[d] || d || '—';
}