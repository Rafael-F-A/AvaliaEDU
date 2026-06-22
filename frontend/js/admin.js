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
     6B. Exportar prova em PDF (aplicação presencial)
     7.  Questões (listar, criar, editar, excluir)
     7B. Geração automática de questões (US11)
     8.  Modal de Questão + alternativas dinâmicas
     9.  Componentes curriculares (US36-38)
     9B. Modelos de questão (US11) — CRUD + upload de imagem
     10. Usuários (listagem, filtros, bloquear, desbloquear, excluir)
     11. Modal de Usuário (cadastrar)
     11B. Importar alunos via CSV / XLSX (US33)
     12. Locais (listagem, filtros, excluir)
     12B. Reservas (US27) — visão admin
     13. Modal de Local (criar / editar)
     14. Relatórios (métricas, desempenho por nível, exportar)
     15. Modal de confirmação genérico
     16. Configuração dos filtros (event listeners)
     17. Helpers locais
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
let _modelos      = [];   // US11 — cache de modelos de questão
let _reservas     = [];   // US27 — cache de reservas (visão admin)

/** Evita repopular os selects de filtro de Local/Prova em toda chamada. */
let _filtrosReservasCarregados = false;

/** ID da prova ativa na seção de questões. */
let _provaAtiva = null;

/** Prova ativa no modal de exportação de PDF (nova versão). */
let _provaExportarAtiva = null;

/** ID do modelo de questão aguardando upload de imagem (US11). */
let _modeloUploadAtivo = null;

/** URL da imagem atual da questão aberta no modal (null = sem imagem). */
let _questaoImagemAtual = null;

/** Linha (.alt-row) de alternativa aguardando upload de imagem. */
let _altImagemUploadAtiva = null;

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
 * @param {'dashboard'|'provas'|'questoes'|'usuarios'|'locais'|'reservas'|'componentes'|'modelos'|'relatorios'} secao
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
    reservas:     carregarReservas,
    componentes:  carregarComponentes,
    modelos:      carregarModelosSecao,
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
    const [provasRes, usuariosRes, locaisRes, relatorioRes] = await Promise.allSettled([
      apiFetchAll('/provas', 'provas'),
      apiFetchAll('/usuarios', 'usuarios'),
      apiFetch('/locais'),
      apiFetch('/relatorios/desempenho'),
    ]);

    const provas   = provasRes.status   === 'fulfilled' ? (provasRes.value?.provas   ?? provasRes.value   ?? []) : [];
    const usuarios = usuariosRes.status === 'fulfilled' ? (usuariosRes.value?.usuarios ?? usuariosRes.value ?? []) : [];
    const locais   = locaisRes.status   === 'fulfilled' ? (locaisRes.value?.locais   ?? locaisRes.value   ?? []) : [];
    const relatorio = relatorioRes.status === 'fulfilled' ? (relatorioRes.value ?? {}) : {};

    // Métricas
    const publicadas  = provas.filter(p => p.status === 'PUBLICADA');
    const alunos      = usuarios.filter(u => u.perfil === 'ALUNO');

    _setEl('dash-total-provas',    publicadas.length);
    _setEl('dash-sub-provas',      `${provas.length} no total, ${publicadas.length} publicadas`);
    _setEl('dash-total-usuarios',  alunos.length);
    _setEl('dash-sub-usuarios',    `${usuarios.length} usuário(s) cadastrado(s)`);
    _setEl('dash-total-locais',    locais.length);

    // Tentativas: total de tentativas realizadas, vindo do relatório de desempenho.
    _setEl('dash-total-tentativas', relatorio.estatisticas_gerais?.total_tentativas ?? '—');

    // Tabela de provas recentes (últimas 5 por created_at)
    const recentes = [...provas]
      .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
      .slice(0, 5);

    const tbody = document.getElementById('dash-provas-recentes');
    tbody.innerHTML = recentes.length
      ? recentes.map(p => `
          <tr>
            <td class="td-name">${_esc(p.titulo)}</td>
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
    _provas = await apiFetchAll('/provas', 'provas');
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
      <td class="td-name">${_esc(p.titulo) || '—'}</td>
      <td class="td-muted">${nivelLabel(p.nivel)}${p.serie ? ' — ' + _esc(p.serie) : ''}</td>
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
          ${p.status === 'PUBLICADA'
            ? `<button class="btn btn-ghost btn-sm" onclick="abrirModalExportarPDF(${p.id}, '${_esc(p.titulo)}')">📄 Gerar PDFs</button>`
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
  _renderComponentesChecklist();
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

    // NOVO — US37
    if (!_componentes.length) {
      try {
        const dataComp = await apiFetch('/componentes/');
        _componentes = Array.isArray(dataComp) ? dataComp : (dataComp?.componentes ?? []);
      } catch { /* checklist mostrará a mensagem de erro padrão */ }
    }
    _renderComponentesChecklist(p.componentes || []);

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

/** Renderiza os checkboxes de componentes curriculares vinculados à prova (US37). */
function _renderComponentesChecklist(componentesVinculados = []) {
  const container = document.getElementById('prova-componentes-checklist');
  const provaId = document.getElementById('prova-id').value;

  if (!provaId) {
    container.innerHTML = `<span class="table-empty" style="padding:4px;">Salve a prova para poder vincular componentes.</span>`;
    return;
  }
  if (!_componentes.length) {
    container.innerHTML = `<span class="table-empty" style="padding:4px;">Nenhum componente cadastrado ainda.</span>`;
    return;
  }

  const idsVinculados = new Set(componentesVinculados.map(c => c.id));

  container.innerHTML = _componentes.map(c => `
    <label style="display:flex; align-items:center; gap:6px; font-size:13px; padding:4px 8px; border-radius:6px; background:var(--c-surface-2,#f4f6fa); cursor:pointer;">
      <input type="checkbox" ${idsVinculados.has(c.id) ? 'checked' : ''}
        onchange="toggleComponenteProva(${c.id}, this.checked)">
      ${_esc(c.nome)}
    </label>`).join('');
}

/** Vincula ou desvincula um componente da prova em edição (US37). Ação imediata. */
async function toggleComponenteProva(compId, vincular) {
  const provaId = document.getElementById('prova-id').value;
  if (!provaId) return;

  try {
    await apiFetch(`/componentes/prova/${provaId}/vincular?comp_id=${compId}`, {
      method: vincular ? 'POST' : 'DELETE',
    });
    showToast(vincular ? 'Componente vinculado.' : 'Componente desvinculado.', 'success', 1800);
  } catch (err) {
    showToast(err.message || 'Erro ao atualizar vínculo do componente.', 'danger');
  }
}

/* ─────────────────────────────────────────
   6B. EXPORTAR PROVA EM PDF — APLICAÇÃO PRESENCIAL
   ─────────────────────────────────────── */

async function abrirModalExportarPDF(provaId, titulo) {
  _provaExportarAtiva = { id: provaId, titulo };

  document.getElementById('modal-exportar-titulo').textContent = `Gerar PDFs — ${titulo}`;
  document.getElementById('exportar-busca-aluno').value = '';
  document.getElementById('exportar-selecionar-todos').checked = false;
  document.getElementById('exportar-fase-selecao').style.display = '';
  document.getElementById('exportar-fase-resultado').style.display = 'none';
  document.getElementById('exportar-modal-footer').innerHTML = `
    <button class="btn btn-ghost" data-close-modal="modal-exportar-pdf">Cancelar</button>
    <button class="btn btn-primary" id="btn-gerar-pdfs" onclick="confirmarExportarPDF()" disabled>Gerar PDFs (0)</button>
  `;

  openModal('modal-exportar-pdf');

  const container = document.getElementById('exportar-lista-alunos');
  container.innerHTML = `<div class="table-empty">Carregando alunos...</div>`;

  try {
    const alunos = await apiFetchAll('/usuarios?perfil=ALUNO', 'usuarios');
    _renderListaAlunosExportar(alunos);
  } catch (err) {
    container.innerHTML = `<div class="table-empty">Erro ao carregar alunos: ${err.message}</div>`;
  }
}

function _renderListaAlunosExportar(lista) {
  const container = document.getElementById('exportar-lista-alunos');
  if (!lista.length) {
    container.innerHTML = `<div class="table-empty">Nenhum aluno cadastrado.</div>`;
    return;
  }
  container.innerHTML = lista.map(a => `
    <label class="exportar-aluno-item"
      data-nome="${(a.nome || '').toLowerCase()}"
      data-email="${(a.email || '').toLowerCase()}"
      style="display:flex; align-items:center; gap:10px; padding:8px 10px; border-radius:6px; cursor:pointer;">
      <input type="checkbox" class="exportar-aluno-check" value="${a.id}" onchange="_atualizarContagemExportar()">
      <span style="flex:1;">
        <div style="font-size:13px; font-weight:600; color:var(--c-text);">${_esc(a.nome)}</div>
        <div style="font-size:12px; color:var(--c-text-muted);">${_esc(a.email)}</div>
      </span>
    </label>`).join('');
}

function _filtrarAlunosExportar() {
  const busca = (document.getElementById('exportar-busca-aluno')?.value || '').toLowerCase();
  document.querySelectorAll('#exportar-lista-alunos .exportar-aluno-item').forEach(el => {
    const ok = el.dataset.nome.includes(busca) || el.dataset.email.includes(busca);
    el.style.display = ok ? '' : 'none';
  });
}

function exportarToggleTodos(checked) {
  document.querySelectorAll('#exportar-lista-alunos .exportar-aluno-item').forEach(item => {
    if (item.style.display !== 'none') {
      item.querySelector('.exportar-aluno-check').checked = checked;
    }
  });
  _atualizarContagemExportar();
}

function _atualizarContagemExportar() {
  const total = document.querySelectorAll('#exportar-lista-alunos .exportar-aluno-check:checked').length;
  const btn = document.getElementById('btn-gerar-pdfs');
  if (btn) {
    btn.textContent = `Gerar PDFs (${total})`;
    btn.disabled = total === 0;
  }
}

async function confirmarExportarPDF() {
  const ids = [...document.querySelectorAll('#exportar-lista-alunos .exportar-aluno-check:checked')]
    .map(el => Number(el.value));
  if (!ids.length) { showToast('Selecione ao menos um aluno.', 'warning'); return; }

  const btn = document.getElementById('btn-gerar-pdfs');
  if (btn) { btn.disabled = true; btn.textContent = 'Gerando...'; }

  try {
    setLoading(true);
    const resp = await apiFetch(`/pdf/provas/${_provaExportarAtiva.id}/exportar`, {
      method: 'POST',
      body: JSON.stringify({ aluno_ids: ids }),
    });

    document.getElementById('exportar-fase-selecao').style.display   = 'none';
    document.getElementById('exportar-fase-resultado').style.display = '';

    document.getElementById('exportar-resumo-cards').innerHTML = `
      <div class="metric-card">
        <div class="metric-card-header"><span class="metric-label">PDFs gerados</span></div>
        <div class="metric-value success">${resp.total_gerados}</div>
      </div>
      <div class="metric-card">
        <div class="metric-card-header"><span class="metric-label">Erros</span></div>
        <div class="metric-value" style="color:var(--c-danger);">${resp.total_erros}</div>
      </div>`;

    document.getElementById('exportar-resultado-tbody').innerHTML = resp.resultados.map(r => `
      <tr>
        <td class="td-name">${_esc(r.aluno_nome || `Aluno #${r.aluno_id}`)}</td>
        <td>${r.url_pdf
          ? `<a href="${r.url_pdf}" target="_blank" class="btn btn-ghost btn-sm">⬇ Baixar PDF</a>`
          : `<span style="color:var(--c-danger); font-size:13px;">${_esc(r.erro || 'Erro desconhecido')}</span>`}
        </td>
      </tr>`).join('');

    document.getElementById('exportar-modal-footer').innerHTML =
      `<button class="btn btn-primary" data-close-modal="modal-exportar-pdf">Fechar</button>`;

    showToast(`${resp.total_gerados} PDF(s) gerado(s) com sucesso!`, 'success');

  } catch (err) {
    showToast(err.message || 'Erro ao gerar PDFs.', 'danger');
    if (btn) { btn.disabled = false; btn.textContent = `Gerar PDFs (${ids.length})`; }
  } finally {
    setLoading(false);
  }
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
              ${_esc(q.enunciado) || '—'}
            </p>
            <div style="display:flex; flex-direction:column; gap:6px;">
              ${(q.alternativas || [])
                .sort((a, b) => (a.ordem ?? 0) - (b.ordem ?? 0))
                .map((alt, idx) => `
                  <div style="display:flex; gap:8px; align-items:center; font-size:13px; color:${alt.is_correta ? 'var(--c-success)' : 'var(--c-text-muted)'};">
                    <span style="font-weight:700; min-width:16px;">${String.fromCharCode(65 + idx)}${alt.is_correta ? ' ✓' : ''}</span>
                    <span>${_esc(alt.texto)}</span>
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
  carregarComponentesSelect('questao-componente');   // US38 — preenche o select de componente
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

    _questaoImagemAtual = q.imagem_url || null;
    _renderImagemQuestao();

    // Recria as alternativas no DOM (com id e imagem, já que ambos existem no backend)
    (q.alternativas || [])
      .sort((a, b) => (a.ordem ?? 0) - (b.ordem ?? 0))
      .forEach(alt => adicionarAlternativa(alt.texto, alt.is_correta, alt.id, alt.imagem_url));

    // Garante mínimo de 2 se vieram menos
    const total = document.querySelectorAll('.alt-row').length;
    for (let i = total; i < 2; i++) adicionarAlternativa();

    // US38 — preenche select de componente e seleciona o vinculado
    await carregarComponentesSelect('questao-componente', q.componente_id ?? null);

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
function adicionarAlternativa(texto = '', isCorreta = false, altId = null, imagemUrl = null) {
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
  row.dataset.altId = altId || '';
  row.dataset.imagemUrl = imagemUrl || '';
  row.style.cssText = 'display:flex; align-items:center; gap:10px;';
  row.innerHTML = `
    <span style="font-weight:700; font-size:14px; min-width:20px; color:var(--c-text-muted);">${letra}</span>
    <input class="form-input alt-texto" type="text"
      placeholder="Texto da alternativa ${letra}"
      value="${_esc(texto)}"
      style="flex:1;"
      oninput="this.closest('.alt-row').querySelector('.alt-correta').disabled = false;">
    <button type="button" class="btn btn-ghost btn-sm alt-btn-imagem"
      onclick="dispararUploadImagemAlternativa(this)"
      title="${altId ? 'Anexar imagem' : 'Salve a questão antes de anexar imagem nesta alternativa'}"
      ${altId ? '' : 'disabled'}
      style="padding:4px 6px; font-size:14px; line-height:1;">🖼</button>
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
  _renderImagemAlternativa(row);
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
    alternativas.push({
      texto,
      is_correta: isCorreta,
      ordem: i + 1,
      // Preserva a imagem já enviada: o PUT recria as alternativas do zero,
      // então precisamos reenviar a URL ou ela se perde na edição.
      imagem_url: row.dataset.imagemUrl || null,
    });
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
    imagem_url: _questaoImagemAtual || null,
  };

  try {
    setLoading(true);
    if (id) {
      await apiFetch(`/questoes/${id}`, { method: 'PUT', body: JSON.stringify(corpo) });
      showToast('Questão atualizada!', 'success');
      closeModal('modal-questao');
    } else {
      const criada = await apiFetch('/questoes', { method: 'POST', body: JSON.stringify(corpo) });
      showToast('Questão criada! Agora você já pode anexar imagens nela.', 'success', 5000);
      // Mantém o modal aberto, em modo edição: upload de imagem exige
      // que a questão/alternativa já tenha um id, que só existe após o POST.
      _aplicarResultadoQuestaoSalva(criada);
    }
    carregarQuestoes(_provaAtiva.id);
  } catch (err) {
    showToast(err.message || 'Erro ao salvar questão.', 'danger');
  } finally {
    setLoading(false);
  }
}

/**
 * Aplica o resultado de uma questão recém-criada ao modal sem fechá-lo:
 * preenche o id da questão e o id/imagem de cada alternativa, e libera
 * os botões de upload de imagem (antes desabilitados por falta de id).
 */
function _aplicarResultadoQuestaoSalva(q) {
  document.getElementById('questao-id').value = q.id;
  document.getElementById('modal-questao-titulo').textContent = 'Editar questão';

  _questaoImagemAtual = q.imagem_url || null;
  _renderImagemQuestao();

  const rows = document.querySelectorAll('#alternativas-container .alt-row');
  (q.alternativas || []).forEach((alt, i) => {
    const row = rows[i];
    if (!row) return;
    row.dataset.altId = alt.id;
    row.dataset.imagemUrl = alt.imagem_url || '';
    const btnImagem = row.querySelector('.alt-btn-imagem');
    btnImagem.disabled = false;
    btnImagem.title = 'Anexar imagem';
    _renderImagemAlternativa(row);
  });
}

function _limparFormQuestao() {
  document.getElementById('questao-id').value        = '';
  document.getElementById('questao-enunciado').value = '';
  document.getElementById('questao-dificuldade').value = 'MEDIO';
  document.getElementById('questao-componente').value  = '';
  document.getElementById('alternativas-container').innerHTML = '';
  _altCounter = 0;
  _questaoImagemAtual = null;
  _renderImagemQuestao();
}

/* ─────────────────────────────────────────
   8B. UPLOAD DE IMAGEM — QUESTÃO E ALTERNATIVA
   ─────────────────────────────────────── */

/** Abre o seletor de arquivo para a imagem do enunciado (exige questão já salva). */
function dispararUploadImagemQuestao() {
  const questaoId = document.getElementById('questao-id').value;
  if (!questaoId) {
    showToast('Salve a questão antes de anexar uma imagem.', 'warning');
    return;
  }
  document.getElementById('questao-imagem-input').click();
}

/** Envia a imagem escolhida via POST /questoes/{id}/imagem (multipart). */
async function _uploadImagemQuestaoSelecionada(event) {
  const arquivo = event.target.files[0];
  event.target.value = '';
  const questaoId = document.getElementById('questao-id').value;
  if (!arquivo || !questaoId) return;

  const formData = new FormData();
  formData.append('arquivo', arquivo);

  try {
    setLoading(true);
    const resp = await apiFetch(`/questoes/${questaoId}/imagem`, {
      method: 'POST',
      body: formData,
    });
    _questaoImagemAtual = resp.imagem_url;
    _renderImagemQuestao();
    showToast('Imagem da questão enviada!', 'success');
  } catch (err) {
    showToast(err.message || 'Erro ao enviar imagem (máx. 5MB, PNG/JPG/WEBP).', 'danger', 5000);
  } finally {
    setLoading(false);
  }
}

/** Atualiza a miniatura e o texto do botão conforme _questaoImagemAtual. */
function _renderImagemQuestao() {
  const preview = document.getElementById('questao-imagem-preview');
  const btn = document.getElementById('btn-questao-imagem');
  if (!preview || !btn) return;

  if (_questaoImagemAtual) {
    preview.src = _questaoImagemAtual;
    preview.style.display = 'inline-block';
    btn.textContent = '🖼 Trocar imagem';
  } else {
    preview.style.display = 'none';
    preview.src = '';
    btn.textContent = '🖼 Adicionar imagem';
  }
}

/** Abre o seletor de arquivo para a imagem de uma alternativa (exige alternativa já salva). */
function dispararUploadImagemAlternativa(btn) {
  const row = btn.closest('.alt-row');
  if (!row.dataset.altId) {
    showToast('Salve a questão antes de anexar imagem nesta alternativa.', 'warning');
    return;
  }
  _altImagemUploadAtiva = row;
  document.getElementById('alternativa-imagem-input').click();
}

/** Envia a imagem escolhida via POST /questoes/{id}/alternativas/{id}/imagem (multipart). */
async function _uploadImagemAlternativaSelecionada(event) {
  const arquivo = event.target.files[0];
  event.target.value = '';
  const row = _altImagemUploadAtiva;
  if (!arquivo || !row) return;

  const questaoId = document.getElementById('questao-id').value;
  const altId = row.dataset.altId;

  const formData = new FormData();
  formData.append('arquivo', arquivo);

  try {
    setLoading(true);
    const resp = await apiFetch(`/questoes/${questaoId}/alternativas/${altId}/imagem`, {
      method: 'POST',
      body: formData,
    });
    row.dataset.imagemUrl = resp.imagem_url;
    _renderImagemAlternativa(row);
    showToast('Imagem da alternativa enviada!', 'success');
  } catch (err) {
    showToast(err.message || 'Erro ao enviar imagem (máx. 5MB, PNG/JPG/WEBP).', 'danger', 5000);
  } finally {
    setLoading(false);
    _altImagemUploadAtiva = null;
  }
}

/** Remove a imagem de uma alternativa via DELETE /questoes/{id}/alternativas/{id}/imagem. */
async function removerImagemAlternativa(btn) {
  const row = btn.closest('.alt-row');
  const questaoId = document.getElementById('questao-id').value;
  const altId = row.dataset.altId;
  if (!altId) return;

  try {
    setLoading(true);
    await apiFetch(`/questoes/${questaoId}/alternativas/${altId}/imagem`, { method: 'DELETE' });
    row.dataset.imagemUrl = '';
    _renderImagemAlternativa(row);
    showToast('Imagem removida.', 'success');
  } catch (err) {
    showToast(err.message || 'Erro ao remover imagem (a alternativa precisa de texto ou imagem).', 'danger');
  } finally {
    setLoading(false);
  }
}

/** Sincroniza a miniatura + botão de remover de uma linha de alternativa com row.dataset.imagemUrl. */
function _renderImagemAlternativa(row) {
  const imagemUrl = row.dataset.imagemUrl;
  const btnImagem = row.querySelector('.alt-btn-imagem');
  let preview = row.querySelector('.alt-imagem-preview');
  let btnRemover = row.querySelector('.alt-btn-remover-imagem');

  if (imagemUrl) {
    if (!preview) {
      preview = document.createElement('img');
      preview.className = 'alt-imagem-preview';
      preview.alt = 'Imagem da alternativa';
      preview.style.cssText = 'max-height:32px; border-radius:4px; border:1px solid var(--c-border);';
      btnImagem.insertAdjacentElement('beforebegin', preview);
    }
    preview.src = imagemUrl;

    if (!btnRemover) {
      btnRemover = document.createElement('button');
      btnRemover.type = 'button';
      btnRemover.className = 'btn btn-ghost btn-sm alt-btn-remover-imagem';
      btnRemover.title = 'Remover imagem';
      btnRemover.textContent = '✕🖼';
      btnRemover.style.cssText = 'padding:4px 6px; font-size:13px; color:var(--c-danger);';
      btnRemover.onclick = () => removerImagemAlternativa(btnRemover);
      btnImagem.insertAdjacentElement('afterend', btnRemover);
    }
  } else {
    if (preview) preview.remove();
    if (btnRemover) btnRemover.remove();
  }
}

/* ─────────────────────────────────────────
   7B. GERAÇÃO AUTOMÁTICA DE QUESTÕES (US11)
   ─────────────────────────────────────── */

/** Abre o modal de geração automática para a prova atualmente em foco. */
function abrirModalGerarQuestoes() {
  if (!_provaAtiva) return;
  document.getElementById('gerar-prova-id').value    = _provaAtiva.id;
  document.getElementById('gerar-quantidade').value  = 10;
  document.getElementById('gerar-dificuldade').value = '';
  carregarComponentesSelect('gerar-componente', null, 'Qualquer componente');
  openModal('modal-gerar-questoes');
}

/**
 * US11 — Gera questões automaticamente a partir do banco de modelos.
 * POST /geracao/provas/{id}/questoes. O nível é herdado da prova pelo
 * próprio backend quando não informado, por isso não há campo "nível" aqui.
 */
async function gerarQuestoesAutomaticamente() {
  const provaId      = document.getElementById('gerar-prova-id').value;
  const quantidade   = _parseNum('gerar-quantidade');
  const dificuldade  = document.getElementById('gerar-dificuldade').value || null;
  const componenteId = document.getElementById('gerar-componente').value || null;

  if (!quantidade || quantidade < 1) {
    showToast('Informe uma quantidade válida (mínimo 1).', 'warning');
    return;
  }

  const corpo = {
    quantidade,
    dificuldade,
    componente_id: componenteId ? Number(componenteId) : null,
  };

  try {
    setLoading(true);
    const res = await apiFetch(`/geracao/provas/${provaId}/questoes`, {
      method: 'POST',
      body: JSON.stringify(corpo),
    });
    closeModal('modal-gerar-questoes');

    if (res.quantidade_erros > 0) {
      showToast(
        `${res.quantidade_gerada} questões geradas, ${res.quantidade_erros} falharam.`,
        'warning', 5000
      );
    } else {
      showToast(`${res.quantidade_gerada} questões geradas com sucesso!`, 'success');
    }
    carregarQuestoes(provaId);
  } catch (err) {
    // Backend retorna 409 (prova já publicada) ou 422 (nenhum modelo
    // encontrado para os filtros) — a mensagem já vem pronta em err.message.
    showToast(err.message || 'Erro ao gerar questões.', 'danger', 5000);
  } finally {
    setLoading(false);
  }
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
      <td class="td-name">${_esc(c.nome)}</td>
      <td><span class="badge badge-simulado">${_esc(c.codigo) || '—'}</span></td>
      <td class="td-muted">${nivelLabel(c.nivel) || '—'}</td>
      <td class="td-muted">${_esc(c.serie) || '—'}</td>
      <td class="td-muted" style="max-width:200px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;"
        title="${_esc(c.descricao || '')}">${_esc(c.descricao) || '—'}</td>
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
  confirmarExclusao(
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
 * Preenche um <select> de componente curricular com os componentes disponíveis.
 * Reutilizado pelos modais de questão, geração automática e modelo de questão (US11/US38).
 * @param {string} selectId        – ID do elemento <select> a preencher.
 * @param {number|null} selecionadoId – ID a pré-selecionar (edição).
 * @param {string} placeholder     – Texto da opção vazia inicial.
 */
async function carregarComponentesSelect(selectId, selecionadoId = null, placeholder = 'Selecione o componente') {
  const sel = document.getElementById(selectId);
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
    `<option value="">${placeholder}</option>` +
    _componentes.map(c =>
      `<option value="${c.id}" ${c.id === selecionadoId ? 'selected' : ''}>${c.nome}${c.codigo ? ' (' + c.codigo + ')' : ''}</option>`
    ).join('');
}

/* ─────────────────────────────────────────
   9B. MODELOS DE QUESTÃO (US11)
   Banco de templates usado pela geração automática.
   O backend só expõe criar / listar / excluir / upload de
   imagem para modelos — não existe endpoint de edição (PUT).
   ─────────────────────────────────────── */

/** Chamada ao entrar na seção: popula o filtro de componente e carrega a lista. */
async function carregarModelosSecao() {
  await carregarComponentesSelect('modelos-filtro-componente', null, 'Todos os componentes');
  carregarModelos();
}

/** Busca os modelos respeitando os filtros ativos (GET /geracao/modelos). */
async function carregarModelos() {
  const tbody = document.getElementById('modelos-tbody');
  tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Carregando...</td></tr>`;

  const nivel       = document.getElementById('modelos-filtro-nivel')?.value || '';
  const dificuldade = document.getElementById('modelos-filtro-dificuldade')?.value || '';
  const componenteId = document.getElementById('modelos-filtro-componente')?.value || '';

  const params = new URLSearchParams();
  if (nivel) params.set('nivel', nivel);
  if (dificuldade) params.set('dificuldade', dificuldade);
  if (componenteId) params.set('componente_id', componenteId);

  try {
    setLoading(true);
    const qs = params.toString();
    const data = await apiFetch(`/geracao/modelos${qs ? '?' + qs : ''}`);
    _modelos = Array.isArray(data) ? data : (data?.modelos ?? []);
    _renderModelos(_modelos);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Erro ao carregar modelos.</td></tr>`;
    showToast('Erro ao carregar modelos de questão.', 'danger');
  } finally {
    setLoading(false);
  }
}

function _renderModelos(lista) {
  const tbody = document.getElementById('modelos-tbody');

  if (!lista.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Nenhum modelo cadastrado. Clique em "+ Novo modelo".</td></tr>`;
    return;
  }

  tbody.innerHTML = lista.map(m => {
    const comp = _componentes.find(c => c.id === m.componente_id);
    const numVars = m.variaveis ? Object.keys(m.variaveis).length : 0;
    return `
    <tr>
      <td class="td-name" style="max-width:280px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;"
        title="${_esc(m.modelo_texto)}">${_esc(m.modelo_texto)}</td>
      <td class="td-muted">${nivelLabel(m.nivel)}</td>
      <td><span class="badge badge-simulado">${dificuldadeLabel(m.dificuldade)}</span></td>
      <td class="td-muted">${comp ? comp.nome : (m.componente_id ? '#' + m.componente_id : '—')}</td>
      <td class="td-muted">${numVars > 0 ? numVars + ' var.' : '—'}${m.imagem_url ? ' · 🖼' : ''}</td>
      <td>
        <div class="td-actions">
          <button class="btn btn-ghost btn-sm" onclick="dispararUploadImagemModelo(${m.id})">Imagem</button>
          <button class="btn btn-ghost btn-sm btn-danger" onclick="excluirModelo(${m.id})">Excluir</button>
        </div>
      </td>
    </tr>`;
  }).join('');
}

/** Abre o modal de criação de modelo (não há edição — backend não expõe PUT). */
function abrirModalNovoModelo() {
  _limparFormModelo();
  carregarComponentesSelect('modelo-componente', null, 'Nenhum (genérico)');
  openModal('modal-modelo');
}

/** Salva um novo modelo de questão via POST /geracao/modelos. */
async function salvarModelo() {
  const modeloTexto = document.getElementById('modelo-texto').value.trim();
  const gabarito     = document.getElementById('modelo-gabarito').value.trim();
  const nivel        = document.getElementById('modelo-nivel').value;

  if (!modeloTexto || !gabarito || !nivel) {
    showToast('Preencha o enunciado, o gabarito e o nível.', 'warning');
    return;
  }

  const distradores = ['modelo-distrator-1', 'modelo-distrator-2', 'modelo-distrator-3']
    .map(id => document.getElementById(id).value.trim())
    .filter(Boolean);

  let variaveis = null;
  const variaveisRaw = document.getElementById('modelo-variaveis').value.trim();
  if (variaveisRaw) {
    try {
      variaveis = JSON.parse(variaveisRaw);
    } catch {
      showToast('O campo "Variáveis" precisa ser um JSON válido. Ex: {"a":[1,2,3]}', 'warning', 5000);
      return;
    }
  }

  const corpo = {
    modelo_texto  : modeloTexto,
    gabarito,
    distradores,
    variaveis,
    nivel,
    serie         : document.getElementById('modelo-serie').value.trim() || null,
    componente_id : document.getElementById('modelo-componente').value
                      ? Number(document.getElementById('modelo-componente').value) : null,
    dificuldade   : document.getElementById('modelo-dificuldade').value || 'MEDIO',
  };

  try {
    setLoading(true);
    await apiFetch('/geracao/modelos', { method: 'POST', body: JSON.stringify(corpo) });
    showToast('Modelo de questão criado!', 'success');
    closeModal('modal-modelo');
    carregarModelos();
  } catch (err) {
    showToast(err.message || 'Erro ao salvar modelo.', 'danger');
  } finally {
    setLoading(false);
  }
}

/** Exclui um modelo de questão com confirmação. */
function excluirModelo(id) {
  confirmarExclusao(
    'Excluir modelo de questão',
    'Tem certeza? Questões já geradas anteriormente a partir deste modelo não são afetadas.',
    async () => {
      try {
        setLoading(true);
        await apiFetch(`/geracao/modelos/${id}`, { method: 'DELETE' });
        showToast('Modelo excluído.', 'success');
        carregarModelos();
      } catch (err) {
        showToast(err.message || 'Erro ao excluir modelo.', 'danger');
      } finally {
        setLoading(false);
      }
    }
  );
}

/** Abre o seletor de arquivo para anexar uma imagem a um modelo (input oculto). */
function dispararUploadImagemModelo(modeloId) {
  _modeloUploadAtivo = modeloId;
  document.getElementById('modelo-imagem-input').click();
}

/** Envia a imagem escolhida via POST /geracao/modelos/{id}/imagem (multipart). */
async function _uploadImagemSelecionada(event) {
  const arquivo = event.target.files[0];
  event.target.value = ''; // permite selecionar o mesmo arquivo novamente depois
  if (!arquivo || !_modeloUploadAtivo) return;

  const formData = new FormData();
  formData.append('arquivo', arquivo);

  try {
    setLoading(true);
    await apiFetch(`/geracao/modelos/${_modeloUploadAtivo}/imagem`, {
      method: 'POST',
      body: formData,
    });
    showToast('Imagem enviada!', 'success');
    carregarModelos();
  } catch (err) {
    showToast(err.message || 'Erro ao enviar imagem (máx. 5MB, PNG/JPG/WEBP).', 'danger', 5000);
  } finally {
    setLoading(false);
    _modeloUploadAtivo = null;
  }
}

function _limparFormModelo() {
  ['modelo-texto', 'modelo-gabarito', 'modelo-distrator-1', 'modelo-distrator-2',
   'modelo-distrator-3', 'modelo-serie', 'modelo-variaveis'].forEach(id => {
    document.getElementById(id).value = '';
  });
  document.getElementById('modelo-nivel').value       = '';
  document.getElementById('modelo-dificuldade').value = 'MEDIO';
}

/* ─────────────────────────────────────────
   10. USUÁRIOS — LISTAGEM E AÇÕES
   ─────────────────────────────────────── */

async function carregarUsuarios() {
  const tbody = document.getElementById('usuarios-tbody');
  tbody.innerHTML = `<tr><td colspan="7" class="table-empty">Carregando usuários...</td></tr>`;

  try {
    setLoading(true);
    _usuarios = await apiFetchAll('/usuarios', 'usuarios');
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
      <td class="td-name">${_esc(u.nome) || '—'}</td>
      <td class="td-muted">${_esc(u.email) || '—'}</td>
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
   11. MODAL DE USUÁRIO — CADASTRAR
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
   11B. IMPORTAR ALUNOS — CSV / XLSX (US33)
   ─────────────────────────────────────── */

/**
 * Abre o modal de importação com estado limpo.
 */
function abrirModalImportar() {
  importarReiniciar();
  openModal('modal-importar');
}

/**
 * Reseta o modal para a fase inicial de upload.
 * Chamado tanto na abertura quanto no botão "Importar outro arquivo".
 */
function importarReiniciar() {
  const input = document.getElementById('importar-arquivo-input');
  if (input) input.value = '';

  const faseUpload    = document.getElementById('importar-fase-upload');
  const faseResultado = document.getElementById('importar-fase-resultado');
  if (faseUpload)    faseUpload.style.display    = '';
  if (faseResultado) faseResultado.style.display = 'none';

  const preview = document.getElementById('importar-arquivo-preview');
  if (preview) preview.style.display = 'none';

  const dz = document.getElementById('importar-drop-zone');
  if (dz) {
    dz.style.borderColor = 'var(--c-border,#d1d5db)';
    dz.style.background  = 'transparent';
  }

  const btn = document.getElementById('btn-processar-importacao');
  if (btn) { btn.disabled = true; btn.textContent = 'Importar alunos'; }

  // Restaura o footer original
  const footer = document.getElementById('importar-modal-footer');
  if (footer) footer.innerHTML = `
    <button class="btn btn-ghost" data-close-modal="modal-importar">Cancelar</button>
    <button class="btn btn-primary" id="btn-processar-importacao"
      onclick="processarImportacao()" disabled>Importar alunos</button>
  `;
}

/**
 * Handler de drop na drop zone.
 * Valida extensão e injeta o arquivo no input para reutilizar importarArquivoSelecionado().
 */
function importarHandleDrop(event) {
  event.preventDefault();
  const dz = document.getElementById('importar-drop-zone');
  if (dz) { dz.style.borderColor = 'var(--c-border,#d1d5db)'; dz.style.background = 'transparent'; }

  const file = event.dataTransfer?.files?.[0];
  if (!file) return;

  const nome = file.name.toLowerCase();
  if (!nome.endsWith('.csv') && !nome.endsWith('.xlsx') && !nome.endsWith('.xls')) {
    showToast('Formato inválido. Use .csv ou .xlsx', 'warning');
    return;
  }

  // Injeta no input via DataTransfer para manter consistência
  const input = document.getElementById('importar-arquivo-input');
  try {
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
  } catch {
    // DataTransfer não suportado em alguns browsers antigos — apenas mostra preview
  }
  importarMostrarPreview(file);
}

/**
 * Chamado pelo oninput do input[type=file].
 */
function importarArquivoSelecionado(input) {
  if (!input.files.length) return;
  importarMostrarPreview(input.files[0]);
}

/**
 * Atualiza o preview com nome e tamanho do arquivo.
 */
function importarMostrarPreview(file) {
  document.getElementById('importar-preview-nome').textContent     = file.name;
  document.getElementById('importar-preview-tamanho').textContent  = _importarFormatarTamanho(file.size);

  const preview = document.getElementById('importar-arquivo-preview');
  if (preview) preview.style.display = 'flex';

  const btn = document.getElementById('btn-processar-importacao');
  if (btn) btn.disabled = false;
}

/**
 * Remove o arquivo selecionado e desabilita o botão de envio.
 */
function importarLimparArquivo() {
  const input = document.getElementById('importar-arquivo-input');
  if (input) input.value = '';

  const preview = document.getElementById('importar-arquivo-preview');
  if (preview) preview.style.display = 'none';

  const btn = document.getElementById('btn-processar-importacao');
  if (btn) btn.disabled = true;
}

/**
 * GET /usuarios/importar/modelo → baixa o arquivo XLSX de exemplo.
 */
async function baixarModeloImportacao() {
  try {
    const resp = await fetch(`${API_BASE}/usuarios/importar/modelo`, {
      headers: { 'Authorization': `Bearer ${getToken()}` },
    });
    if (!resp.ok) throw new Error('Falha ao baixar modelo.');
    const blob = await resp.blob();
    const link = document.createElement('a');
    link.href     = URL.createObjectURL(blob);
    link.download = 'modelo_importacao_alunos.xlsx';
    link.click();
    URL.revokeObjectURL(link.href);
    showToast('Modelo baixado com sucesso!', 'success');
  } catch (err) {
    showToast(err.message || 'Erro ao baixar modelo.', 'danger');
  }
}

/**
 * POST /usuarios/importar → envia o arquivo via FormData (multipart/form-data).
 * NÃO usa apiFetch() porque o endpoint não aceita JSON.
 */
async function processarImportacao() {
  const input = document.getElementById('importar-arquivo-input');
  if (!input?.files.length) {
    showToast('Selecione um arquivo para importar.', 'warning');
    return;
  }

  const arquivo = input.files[0];
  if (arquivo.size > 5 * 1024 * 1024) {
    showToast('Arquivo muito grande. Limite máximo: 5 MB.', 'warning');
    return;
  }

  const btn = document.getElementById('btn-processar-importacao');
  if (btn) { btn.disabled = true; btn.textContent = 'Importando...'; }

  const formData = new FormData();
  formData.append('arquivo', arquivo);

  try {
    setLoading(true);
    // Não definir Content-Type — o browser insere o boundary multipart automaticamente
    const resp = await fetch(`${API_BASE}/usuarios/importar`, {
      method:  'POST',
      headers: { 'Authorization': `Bearer ${getToken()}` },
      body:    formData,
    });

    const resultado = await resp.json();
    if (!resp.ok) {
      const detalhe = resultado?.detail;
      throw new Error(typeof detalhe === 'string' ? detalhe : JSON.stringify(detalhe));
    }

    _importarRenderResultado(resultado);
    carregarUsuarios(); // atualiza tabela de usuários em segundo plano

  } catch (err) {
    showToast(err.message || 'Erro ao importar arquivo.', 'danger');
    if (btn) { btn.disabled = false; btn.textContent = 'Importar alunos'; }
  } finally {
    setLoading(false);
  }
}

/**
 * Renderiza os resultados da importação na Fase 2 do modal.
 */
function _importarRenderResultado(resultado) {
  const { total_linhas, total_importados, total_duplicados, total_erros,
          importados = [], duplicados = [], erros = [] } = resultado;

  // Alterna fases
  document.getElementById('importar-fase-upload').style.display    = 'none';
  document.getElementById('importar-fase-resultado').style.display = '';

  // Substitui footer por Fechar + Importar outro
  const footer = document.getElementById('importar-modal-footer');
  if (footer) footer.innerHTML = `
    <button class="btn btn-ghost" data-close-modal="modal-importar">Fechar</button>
    <button class="btn btn-secondary" onclick="importarReiniciar()">↩ Importar outro arquivo</button>
  `;

  // Cards de resumo
  document.getElementById('importar-resumo-cards').innerHTML = `
    <div class="metric-card">
      <div class="metric-card-header"><span class="metric-label">Total de linhas</span></div>
      <div class="metric-value" style="font-size:26px;">${total_linhas}</div>
      <div class="metric-sub">no arquivo</div>
    </div>
    <div class="metric-card">
      <div class="metric-card-header"><span class="metric-label">Importados</span></div>
      <div class="metric-value success" style="font-size:26px;">${total_importados}</div>
      <div class="metric-sub">alunos criados</div>
    </div>
    <div class="metric-card">
      <div class="metric-card-header"><span class="metric-label">Duplicados</span></div>
      <div class="metric-value" style="font-size:26px; color:var(--c-warning,#d97706);">${total_duplicados}</div>
      <div class="metric-sub">e-mails já existentes</div>
    </div>
    <div class="metric-card">
      <div class="metric-card-header"><span class="metric-label">Erros</span></div>
      <div class="metric-value" style="font-size:26px; color:var(--c-danger,#dc2626);">${total_erros}</div>
      <div class="metric-sub">linhas inválidas</div>
    </div>
  `;

  // Toast de resumo
  const toastTipo = total_importados === 0 ? 'danger' : total_erros > 0 ? 'warning' : 'success';
  const toastMsg  = total_importados === 0
    ? 'Nenhum aluno foi importado. Verifique o arquivo.'
    : `${total_importados} aluno(s) importado(s)${total_erros ? ` · ${total_erros} erro(s) detectado(s)` : ''}.`;
  showToast(toastMsg, toastTipo);

  // Tabela de importados + senhas provisórias
  const blocoImp = document.getElementById('importar-bloco-importados');
  if (importados.length) {
    blocoImp.style.display = '';
    document.getElementById('importar-importados-tbody').innerHTML = importados.map(a => `
      <tr>
        <td class="td-name">${_esc(a.nome)}</td>
        <td class="td-muted">${_esc(a.email)}</td>
        <td class="td-muted">${nivelLabel(a.nivel)}</td>
        <td class="td-muted">${a.serie || '—'}</td>
        <td>
          <code style="background:var(--c-surface-2,#f4f6fa); padding:3px 8px; border-radius:4px; font-size:13px; font-family:monospace; user-select:all;">
            ${_esc(a.senha_provisoria)}
          </code>
        </td>
      </tr>`).join('');
  } else {
    blocoImp.style.display = 'none';
  }

  // Tabela de duplicados
  const blocoDup = document.getElementById('importar-bloco-duplicados');
  if (duplicados.length) {
    blocoDup.style.display = '';
    document.getElementById('importar-duplicados-tbody').innerHTML = duplicados.map(d => `
      <tr>
        <td class="td-muted">${d.linha}</td>
        <td class="td-muted">${_esc(d.email)}</td>
        <td class="td-muted" style="font-size:12px;">${_esc(d.motivo)}</td>
      </tr>`).join('');
  } else {
    blocoDup.style.display = 'none';
  }

  // Tabela de erros
  const blocoErr = document.getElementById('importar-bloco-erros');
  if (erros.length) {
    blocoErr.style.display = '';
    document.getElementById('importar-erros-tbody').innerHTML = erros.map(e => `
      <tr>
        <td class="td-muted">${e.linha}</td>
        <td class="td-muted">${_esc(e.dados?.nome || '—')}</td>
        <td class="td-muted">${_esc(e.dados?.email || '—')}</td>
        <td style="font-size:12px; color:var(--c-danger,#dc2626);">${(e.erros || []).map(_esc).join('<br>')}</td>
      </tr>`).join('');
  } else {
    blocoErr.style.display = 'none';
  }
}

/**
 * Copia a tabela de importados para o clipboard no formato TSV
 * (compatível com Excel e Google Sheets para colar diretamente).
 */
async function importarCopiarSenhas() {
  const rows = document.querySelectorAll('#importar-importados-tbody tr');
  if (!rows.length) { showToast('Nenhum dado para copiar.', 'warning'); return; }

  const cabecalho = 'nome\temail\tnivel\tserie\tsenha_provisoria';
  const linhas = [...rows].map(tr => {
    const tds = tr.querySelectorAll('td');
    return [
      tds[0]?.textContent.trim(),
      tds[1]?.textContent.trim(),
      tds[2]?.textContent.trim(),
      tds[3]?.textContent.trim(),
      tds[4]?.querySelector('code')?.textContent.trim() || '',
    ].join('\t');
  });

  try {
    await navigator.clipboard.writeText([cabecalho, ...linhas].join('\n'));
    showToast('Tabela copiada! Cole em uma planilha para salvar as senhas.', 'success');
  } catch {
    showToast('Não foi possível copiar automaticamente. Selecione a tabela manualmente.', 'warning');
  }
}

/** Formata bytes em string legível (B / KB / MB). */
function _importarFormatarTamanho(bytes) {
  if (bytes < 1024)         return `${bytes} B`;
  if (bytes < 1024 * 1024)  return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

/* ─────────────────────────────────────────
   12. LOCAIS — LISTAGEM E AÇÕES
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
      <td class="td-name">${_esc(l.nome) || '—'}</td>
      <td class="td-muted">${_esc(l.cidade) || '—'}${l.estado ? ' / ' + _esc(l.estado) : ''}</td>
      <td class="td-muted" style="max-width:200px; white-space:normal;">${_esc(l.endereco) || '—'}</td>
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
   12B. RESERVAS — VISÃO DO ADMIN (US27)
   ─────────────────────────────────────── */

async function carregarReservas() {
  const tbody = document.getElementById('reservas-tbody');
  tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Carregando reservas...</td></tr>`;

  try {
    setLoading(true);
    const data = await apiFetch('/reservas/admin/todas');
    _reservas = Array.isArray(data) ? data : [];
    _renderReservas(_reservas);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Erro ao carregar: ${err.message}</td></tr>`;
    showToast('Falha ao carregar reservas.', 'danger');
  } finally {
    setLoading(false);
  }
}

function _renderReservas(lista) {
  const tbody = document.getElementById('reservas-tbody');
  if (!lista.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Nenhuma reserva encontrada.</td></tr>`;
    return;
  }

  tbody.innerHTML = lista.map(r => `
    <tr data-aluno="${_esc((r.aluno?.nome || '').toLowerCase())}"
        data-email="${_esc((r.aluno?.email || '').toLowerCase())}"
        data-prova="${_esc((r.prova_titulo || '').toLowerCase())}"
        data-status="${r.status || ''}">
      <td class="td-name">
        ${_esc(r.aluno?.nome) || '—'}
        <div class="td-muted" style="font-size:12px;">${_esc(r.aluno?.email)}</div>
      </td>
      <td class="td-muted">${_esc(r.prova_titulo) || '—'}</td>
      <td class="td-muted">${_esc(r.local?.nome) || '—'}${r.local?.cidade ? ' — ' + _esc(r.local.cidade) : ''}</td>
      <td class="td-muted">${formatarDataHora(r.data_reserva)}</td>
      <td class="td-muted">${r.data_expiracao ? formatarDataHora(r.data_expiracao) : '—'}</td>
      <td>${_badgeReserva(r.status)}</td>
    </tr>`).join('');
}

function _filtrarReservas() {
  const busca  = (document.getElementById('reservas-busca')?.value || '').toLowerCase();
  const status = document.getElementById('reservas-filtro-status')?.value || '';

  document.querySelectorAll('#reservas-tbody tr[data-aluno]').forEach(tr => {
    const ok = (tr.dataset.aluno.includes(busca) || tr.dataset.email.includes(busca) || tr.dataset.prova.includes(busca))
      && (!status || tr.dataset.status === status);
    tr.style.display = ok ? '' : 'none';
  });
}

/** Badge colorido por status — mesmo padrão de cores usado em aluno.js */
function _badgeReserva(status) {
  const map = {
    ATIVA:      ['badge-publicada', 'Ativa'],
    UTILIZADA:  ['badge-aprovado',  'Utilizada'],
    CANCELADA:  ['badge-reprovado', 'Cancelada'],
    EXPIRADA:   ['badge-rascunho',  'Expirada'],
  };
  const [cls, label] = map[status] || ['badge-rascunho', status];
  return `<span class="badge ${cls}">${label}</span>`;
}

/* ─────────────────────────────────────────
   13. MODAL DE LOCAL — CRIAR / EDITAR
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
   14. RELATÓRIOS — US28, US29, US35
   ─────────────────────────────────────── */

/** Cache do último resultado para evitar re-fetch ao limpar filtro */
let _relCache = null;

/** Monta query string a partir dos filtros do painel */
function _relQueryParams() {
  const inicio  = document.getElementById('rel-data-inicio')?.value;
  const fim     = document.getElementById('rel-data-fim')?.value;
  const nivel   = document.getElementById('rel-filtro-nivel')?.value;
  const serie   = document.getElementById('rel-filtro-serie')?.value.trim();

  const params = new URLSearchParams();
  if (inicio) params.set('data_inicio', new Date(inicio).toISOString());
  if (fim)    params.set('data_fim',    new Date(fim + 'T23:59:59').toISOString());
  if (nivel)  params.set('nivel', nivel);
  if (serie)  params.set('serie', serie);
  return params.toString() ? '?' + params.toString() : '';
}

async function carregarRelatorios() {
  await _buscarEExibirRelatorio();
}

async function aplicarFiltrosRelatorio() {
  await _buscarEExibirRelatorio();
}

function limparFiltrosRelatorio() {
  document.getElementById('rel-data-inicio').value  = '';
  document.getElementById('rel-data-fim').value     = '';
  document.getElementById('rel-filtro-nivel').value = '';
  document.getElementById('rel-filtro-serie').value = '';
  _buscarEExibirRelatorio();
}

async function _buscarEExibirRelatorio() {
  const btnAplicar = document.getElementById('btn-aplicar-filtros');
  if (btnAplicar) { btnAplicar.disabled = true; btnAplicar.textContent = 'Carregando...'; }

  try {
    const qs   = _relQueryParams();
    const data = await apiFetch(`/relatorios/desempenho${qs}`);
    _relCache  = data;

    // ── Métricas gerais ──────────────────────────────────
    const eg = data.estatisticas_gerais || {};
    _setEl('rel-total-tentativas', eg.total_tentativas ?? '—');
    _setEl('rel-certificados',     data.total_certificados ?? '—');
    _setEl('rel-media',
      eg.media_geral != null ? Number(eg.media_geral).toFixed(1) : '—');

    const taxa = eg.taxa_aprovacao_percentual;
    _setEl('rel-taxa-aprovacao',
      taxa != null ? Number(taxa).toFixed(1) + '%' : '—');

    const sub = document.getElementById('rel-sub-aprovados');
    if (sub && eg.aprovados != null) {
      sub.textContent = `${eg.aprovados} aprovados / ${eg.reprovados ?? 0} reprovados`;
    }

    // ── Desempenho por nível ─────────────────────────────
    _renderTabelaDesempenho(
      'rel-desempenho-lista',
      data.distribuicao_por_nivel ?? [],
      ['Nível', 'Alunos', 'Tentativas', 'Média', 'Aprovação'],
      r => [
        `<td class="td-name">${nivelLabel(r.nivel)}</td>`,
        `<td class="td-muted">${r.total_alunos ?? '—'}</td>`,
        `<td class="td-muted">${r.total_tentativas ?? '—'}</td>`,
        `<td><strong>${r.media_notas != null ? Number(r.media_notas).toFixed(1) : '—'}</strong></td>`,
        `<td>${_badgeTaxa(r.taxa_aprovacao_percentual)}</td>`,
      ]
    );

    // ── Desempenho por série ─────────────────────────────
    _renderTabelaDesempenho(
      'rel-desempenho-serie',
      data.distribuicao_por_serie ?? [],
      ['Série', 'Alunos', 'Tentativas', 'Média', 'Aprovação'],
      r => [
        `<td class="td-name">${r.serie || '—'}</td>`,
        `<td class="td-muted">${r.total_alunos ?? '—'}</td>`,
        `<td class="td-muted">${r.total_tentativas ?? '—'}</td>`,
        `<td><strong>${r.media_notas != null ? Number(r.media_notas).toFixed(1) : '—'}</strong></td>`,
        `<td>${_badgeTaxa(r.taxa_aprovacao_percentual)}</td>`,
      ]
    );

    // ── Detalhes por prova ───────────────────────────────
    const provas  = data.detalhes_por_prova ?? [];
    const badgeEl = document.getElementById('rel-total-provas-badge');
    if (badgeEl) badgeEl.textContent = provas.length ? `${provas.length} provas` : '';

    const tbody = document.getElementById('rel-provas-tbody');
    if (tbody) {
      tbody.innerHTML = provas.length
        ? provas.map(p => `
            <tr>
              <td class="td-name">${_esc(p.prova_titulo) || '—'}</td>
              <td>${badgeTipoProva(p.tipo)}</td>
              <td class="td-muted">${nivelLabel(p.nivel)}</td>
              <td class="td-muted">${p.total_tentativas ?? '—'}</td>
              <td><strong>${p.media_notas != null ? Number(p.media_notas).toFixed(1) : '—'}</strong></td>
              <td>${_badgeTaxa(p.taxa_aprovacao_percentual)}</td>
            </tr>`).join('')
        : `<tr><td colspan="6" class="table-empty">Nenhuma prova encontrada com estes filtros.</td></tr>`;
    }

  } catch (err) {
    showToast('Erro ao carregar relatório: ' + (err.message || ''), 'danger');
    ['rel-total-tentativas','rel-certificados','rel-media','rel-taxa-aprovacao'].forEach(id =>
      _setEl(id, '—'));
  } finally {
    if (btnAplicar) { btnAplicar.disabled = false; btnAplicar.textContent = 'Aplicar filtros'; }
  }
}

/** Renderiza uma tabela de desempenho genérica num container */
function _renderTabelaDesempenho(containerId, lista, headers, rowFn) {
  const el = document.getElementById(containerId);
  if (!el) return;

  if (!lista.length) {
    el.innerHTML = `<div class="table-empty" style="padding:16px;">Sem dados para este filtro.</div>`;
    return;
  }

  el.innerHTML = `
    <div class="table-wrapper">
      <table>
        <thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead>
        <tbody>
          ${lista.map(r => `<tr>${rowFn(r).join('')}</tr>`).join('')}
        </tbody>
      </table>
    </div>`;
}

/** Badge colorido para taxa de aprovação */
function _badgeTaxa(taxa) {
  if (taxa == null) return '<span class="td-muted">—</span>';
  const cls = taxa >= 60 ? 'badge-aprovado' : 'badge-reprovado';
  return `<span class="badge ${cls}">${Number(taxa).toFixed(0)}%</span>`;
}

/** Exporta relatório com os filtros ativos e formato selecionado (US29 / US35) */
async function exportarRelatorio() {
  const btn     = document.getElementById('btn-exportar');
  const formato = document.getElementById('rel-formato-export')?.value || 'excel';
  const ext     = formato === 'excel' ? 'xlsx' : 'csv';

  if (btn) { btn.disabled = true; btn.textContent = '⏳ Gerando...'; }

  try {
    const qs    = _relQueryParams();
    // Adiciona parâmetro formato à query string
    const sep   = qs ? '&' : '?';
    const url   = `${API_BASE}/relatorios/exportar${qs}${sep}formato=${formato}`;
    const token = getToken();

    const resp = await fetch(url, {
      headers: { 'Authorization': `Bearer ${token}` },
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || 'Falha ao gerar exportação.');
    }

    const blob = await resp.blob();
    const link = document.createElement('a');
    link.href  = URL.createObjectURL(blob);
    link.download = `relatorio_desempenho_${new Date().toISOString().slice(0,10)}.${ext}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
    showToast(`Relatório exportado (${ext.toUpperCase()})!`, 'success');

  } catch (err) {
    showToast(err.message || 'Erro ao exportar.', 'danger');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '⬇ Exportar relatório'; }
  }
}

/* ─────────────────────────────────────────
   15. MODAL DE CONFIRMAÇÃO GENÉRICO
   ─────────────────────────────────────── */

// confirmarExclusao(titulo, msg, callback) agora vive em global.js
// (carregado ANTES de admin.js) e é autossuficiente.

/* ─────────────────────────────────────────
   16. CONFIGURAÇÃO DOS FILTROS (event listeners)
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

  // Reservas (US27)
  const resBusca  = document.getElementById('reservas-busca');
  const resStatus = document.getElementById('reservas-filtro-status');
  if (resBusca)  resBusca.addEventListener('input', debounce(_filtrarReservas, 250));
  if (resStatus) resStatus.addEventListener('change', _filtrarReservas);

  // Exportar PDF (aplicação presencial)
  const expBusca = document.getElementById('exportar-busca-aluno');
  if (expBusca) expBusca.addEventListener('input', debounce(_filtrarAlunosExportar, 200));
}

/* ─────────────────────────────────────────
   17. HELPERS LOCAIS
   ─────────────────────────────────────── */

/** Define o textContent de um elemento pelo ID, sem lançar erro. */
function _setEl(id, valor) {
  const el = document.getElementById(id);
  if (el) el.textContent = valor ?? '—';
}

// _esc(str) agora vive em global.js (carregado ANTES de admin.js)
// e é exposto como window._esc — não redefinir aqui.

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