/* ============================================================
   AvaliaEdu — aluno.js
   Lógica completa do Dashboard do Aluno.
   Depende de: global.js (apiFetch, showToast, openModal, etc.)
   ============================================================ */

/* ─────────────────────────────────────────
   1. ESTADO GLOBAL
   ─────────────────────────────────────── */

/** Usuário logado (preenchido no init) */
let usuario = null;

/** Cache de provas publicadas */
let provasDisponiveis = [];

/**
 * Estado completo do exame em andamento.
 * Zerado em cada nova prova iniciada.
 */
let exam = {
  tipo:                  null,   // 'SIMULADO' | 'CERTIFICACAO'
  provaId:               null,
  provaInfo:             null,   // objeto ProvaResponse
  tentativaId:           null,
  totalQuestoes:         0,
  indiceAtual:           0,      // posição atual no cache (0-based)
  questoesCache:         [],     // [{id, enunciado, alternativas, questao_numero}]
  respostasSalvas:       {},     // { questaoId: alternativaId }  (submetidas ao servidor)
  altSelecionadaAgora:   null,   // ID da alternativa selecionada na tela (não salva ainda)
  enviadas:              new Set(), // questaoIds já POSTadas em /responder
  timerInterval:         null,
  tempoRestante:         null,   // segundos
  certificadoId:         null,   // após gerar o cert de certificação
  certificadoUrlPdf:     null,   // URL real do PDF (Supabase Storage) após POST /pdf/certificados/{tentativa_id}
};

/* ─────────────────────────────────────────
   2. INICIALIZAÇÃO
   ─────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
  usuario = requireAuth('ALUNO');
  if (!usuario) return;

  initUI(usuario);
  // Preenche avatar + dados pessoais já na carga inicial (estão no localStorage),
  // sem esperar abrir a "Minha área" nem uma chamada de API.
  preencherIdentidade(usuario);
  configurarNavegacao();
  configurarFiltros();
  carregarDashboard();

  // US42 — Modo EJA: ativa automaticamente se nível = EJA ou se estava ativo
  _aplicarModoEJA(
    localStorage.getItem('avaliaedu_eja') === '1' || usuario.nivel === 'EJA'
  );
});

/* ─────────────────────────────────────────
   2. MODO EJA — ACESSIBILIDADE (US42)
   ─────────────────────────────────────── */

const _EJA_KEY = 'avaliaedu_eja';

/**
 * Liga/desliga o modo EJA e persiste a preferência no localStorage.
 * Chamado pelo botão na sidebar.
 */
function toggleModoEJA() {
  const ativo = !document.body.classList.contains('eja-mode');
  _aplicarModoEJA(ativo);
  localStorage.setItem(_EJA_KEY, ativo ? '1' : '0');

  // Aviso visual temporário
  _exibirAvisoEJA(ativo
    ? '♿ Modo EJA ativado — fonte maior e alto contraste'
    : 'Modo EJA desativado');
}

/**
 * Aplica ou remove a classe `eja-mode` no body e atualiza o botão da sidebar.
 * @param {boolean} ativo
 */
function _aplicarModoEJA(ativo) {
  document.body.classList.toggle('eja-mode', ativo);

  const btn   = document.getElementById('btn-eja-toggle');
  const icon  = document.getElementById('eja-toggle-icon');
  const label = document.getElementById('eja-toggle-label');

  if (btn)   btn.classList.toggle('ativo', ativo);
  if (icon)  icon.textContent = ativo ? '✅' : '♿';
  if (label) label.textContent = ativo ? 'Modo EJA ativo' : 'Modo EJA';
  if (btn)   btn.setAttribute('aria-pressed', ativo ? 'true' : 'false');
  if (btn)   btn.title = ativo
    ? 'Desativar modo de acessibilidade EJA'
    : 'Ativar modo de acessibilidade EJA';
}

/** Exibe um aviso flutuante por 3 segundos */
function _exibirAvisoEJA(msg) {
  let el = document.getElementById('eja-aviso');
  if (el) el.remove();

  el = document.createElement('div');
  el.id          = 'eja-aviso';
  el.textContent = msg;
  el.setAttribute('role', 'status');
  el.setAttribute('aria-live', 'polite');
  document.body.appendChild(el);

  setTimeout(() => el?.remove(), 3000);
}



/* ─────────────────────────────────────────
   3. NAVEGAÇÃO ENTRE SEÇÕES
   ─────────────────────────────────────── */

/**
 * Navega para uma seção, carregando os dados necessários.
 * @param {'dashboard'|'provas'|'certificados'|'minha-area'|'realizar-prova'|'resultado'} secao
 */
function irPara(secao) {
  document.querySelectorAll('.dash-section').forEach(s => s.classList.add('hidden'));

  const el = document.getElementById(`section-${secao}`);
  if (el) el.classList.remove('hidden');

  // Sincroniza sidebar (apenas itens principais)
  document.querySelectorAll('.sidebar-nav .nav-link').forEach(a => {
    const target = a.dataset.section;
    a.classList.toggle('active', target === secao);
  });

  // Carrega dados da seção
  const loaders = {
    dashboard:      carregarDashboard,
    provas:         carregarProvasAluno,
    certificados:   carregarCertificados,
    reservas:       carregarReservas,
    'minha-area':   carregarMinhaArea,
  };
  if (loaders[secao]) loaders[secao]();

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/** Liga os cliques na sidebar aos trechos. */
function configurarNavegacao() {
  document.querySelectorAll('.sidebar-nav .nav-link').forEach(a => {
    a.addEventListener('click', (e) => {
      e.preventDefault();
      irPara(a.dataset.section);
    });
  });
}

/* ─────────────────────────────────────────
   4. DASHBOARD
   ─────────────────────────────────────── */

/**
 * Preenche a identidade do usuário (iniciais no avatar + dados pessoais)
 * imediatamente a partir do objeto já salvo no localStorage — assim o avatar
 * aparece em TODAS as seções e a "Minha área" já mostra nome/e-mail/nível antes
 * mesmo de ser aberta. carregarMinhaArea() depois atualiza totais/histórico.
 */
function preencherIdentidade(u) {
  if (!u) return;
  const ini = iniciais(u.nome);
  // Avatares de todas as seções (vários sem id) — preenche por classe.
  document.querySelectorAll('.user-avatar').forEach(el => { el.textContent = ini; });

  const nomeEl = document.getElementById('area-nome');
  if (nomeEl) nomeEl.textContent = u.nome || '—';
  const nsEl = document.getElementById('area-nivel-serie');
  if (nsEl) nsEl.textContent = [nivelLabel(u.nivel), u.serie].filter(Boolean).join(' — ') || '—';
  const emailEl = document.getElementById('area-email');
  if (emailEl) emailEl.value = u.email || '';
  const ndEl = document.getElementById('area-nivel-display');
  if (ndEl) ndEl.value = nivelLabel(u.nivel) || '—';
  const sdEl = document.getElementById('area-serie-display');
  if (sdEl) sdEl.value = u.serie || '—';
  if (typeof _renderStatusLocalizacao === 'function') {
    _renderStatusLocalizacao(u.latitude, u.longitude);
  }
}

async function carregarDashboard() {
  try {
    const [historico, certs, provas] = await Promise.allSettled([
      apiFetch('/simulados/historico'),
      apiFetch('/certificacoes/historico'),
      apiFetchAll('/provas?status=PUBLICADA', 'provas'),
    ]);

    const hist  = historico.status  === 'fulfilled' ? historico.value  : [];
    const certsV = certs.status     === 'fulfilled' ? certs.value      : [];
    const provasResp = provas.status === 'fulfilled' ? provas.value : [];
    // /provas retorna objeto paginado { total, skip, limit, provas: [...] }
    const provasV = Array.isArray(provasResp) ? provasResp : (provasResp.provas || []);

    // Calcula média
    const finalizadas = hist.filter(t => t.nota !== null && t.nota !== undefined);
    const media = finalizadas.length
      ? (finalizadas.reduce((s, t) => s + t.nota, 0) / finalizadas.length).toFixed(1)
      : '—';

    // Próxima prova (primeira disponível por data_fim)
    const proxima = provasV
      .filter(p => p.data_fim && new Date(p.data_fim) > new Date())
      .sort((a, b) => new Date(a.data_fim) - new Date(b.data_fim))[0];

    // Preenche métricas
    document.getElementById('dash-proxima-data').textContent =
      proxima ? formatarData(proxima.data_fim) : '—';
    document.getElementById('dash-proxima-nome').textContent =
      proxima ? proxima.titulo : 'Nenhuma agendada';

    document.getElementById('dash-media').textContent = media;
    document.getElementById('dash-total-certs').textContent = certsV.length;
    document.getElementById('dash-provas-disponiveis').textContent = provasV.length;

    // Tabela desempenho recente (últimas 5)
    const tbody = document.getElementById('dash-desempenho');
    const recentes = hist.slice(0, 5);
    tbody.innerHTML = recentes.length
      ? recentes.map(t => `
          <tr>
            <td class="td-name">${_esc(t.prova_titulo) || '—'}</td>
            <td class="td-muted">${formatarData(t.data_inicio || t.data_realizacao)}</td>
            <td>${formatarNota(t.nota)}</td>
            <td>${badgeResultado(t.resultado)}</td>
          </tr>`).join('')
      : `<tr><td colspan="4" class="table-empty">Nenhuma prova realizada ainda.</td></tr>`;

  } catch (err) {
    showToast('Erro ao carregar dashboard.', 'danger');
  }
}

/* ─────────────────────────────────────────
   5. SEÇÃO DE PROVAS
   ─────────────────────────────────────── */

async function carregarProvasAluno() {
  try {
    setLoading(true);
    const [provas, historico, certHist, inscricoes] = await Promise.all([
      apiFetchAll('/provas?status=PUBLICADA', 'provas'),
      apiFetch('/simulados/historico'),
      apiFetch('/certificacoes/historico'),
      apiFetch('/inscricoes/minhas').catch(() => []),
    ]);

    // /provas retorna objeto paginado { total, skip, limit, provas: [...] }
    const provasList = Array.isArray(provas) ? provas : (provas?.provas ?? []);
    provasDisponiveis = provasList;

    // Mapa tentativa por prova_id
    const tentativasMap = {};
    [...historico, ...certHist].forEach(t => {
      const pid = t.prova_id;
      if (!pid) return;
      // Prefere a tentativa ATIVA (em andamento/pausada) sobre concluídas.
      if (!tentativasMap[pid] || t.status === 'PAUSADO' || t.status === 'EM_ANDAMENTO') tentativasMap[pid] = t;
    });

    // Mapa inscrição por prova_id
    const inscricoesMap = {};
    inscricoes.forEach(i => { inscricoesMap[i.prova_id] = i; });

    renderTabelaProvas(provasList, tentativasMap, inscricoesMap);

    // Histórico combinado
    const todosHistorico = [
      ...historico.map(t => ({ ...t, tipo: 'SIMULADO' })),
      ...certHist.map(t => ({ ...t, tipo: 'CERTIFICACAO' })),
    ].sort((a, b) =>
      new Date(b.data_inicio || b.data_realizacao) - new Date(a.data_inicio || a.data_realizacao));

    renderTabelaHistorico(todosHistorico);
    aplicarFiltroProvas();

  } catch (err) {
    showToast('Erro ao carregar provas.', 'danger');
  } finally {
    setLoading(false);
  }
}

function renderTabelaProvas(provas, tentativasMap = {}, inscricoesMap = {}) {
  const tbody = document.getElementById('provas-aluno-tbody');
  if (!provas.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Nenhuma prova disponível no momento.</td></tr>`;
    return;
  }

  const agora = new Date();

  tbody.innerHTML = provas.map(p => {
    const tent        = tentativasMap[p.id];
    const concluido   = tent?.status === 'CONCLUIDA';
    const emAndamento = tent?.status === 'EM_ANDAMENTO';
    const pausado     = tent?.status === 'PAUSADO';
    const inscrito    = inscricoesMap[p.id];

    // Determinar estado do período de inscrições
    const temPeriodoInscricao = p.data_inicio_inscricao || p.data_fim_inscricao;
    const aindaNaoAbriu      = p.data_inicio_inscricao && agora < new Date(p.data_inicio_inscricao);
    const inscricaoEncerrada = p.data_fim_inscricao && agora > new Date(p.data_fim_inscricao);
    const inscricaoAberta    = temPeriodoInscricao && !aindaNaoAbriu && !inscricaoEncerrada;

    // Montar coluna "Encerra em / Inscrições"
    let prazoCel = '—';
    if (inscricaoAberta && p.data_fim_inscricao) {
      prazoCel = `<span style="color:var(--c-warning,#b45309);">Inscrições até ${formatarData(p.data_fim_inscricao)}</span>`;
    } else if (p.data_fim) {
      prazoCel = formatarData(p.data_fim);
    }

    // Montar botões de ação
    let acaoBtns = '';

    if (concluido) {
      acaoBtns = `<button class="btn btn-ghost btn-sm"
        onclick="verResultadoHistorico(${tent.id}, '${p.tipo}')">Ver resultado</button>`;

    } else if (emAndamento) {
      // Tentativa em andamento — retoma na questão atual (evita o 409 de "já iniciado").
      acaoBtns = `<button class="btn btn-primary btn-sm"
        onclick="continuarProva(${tent.id}, '${p.tipo}')">Continuar</button>`;

    } else if (pausado) {
      acaoBtns = `<button class="btn btn-secondary btn-sm"
        onclick="retomarProva(${tent.id})">Retomar</button>`;

    } else if (aindaNaoAbriu) {
      // Período de inscrições definido, mas ainda não abriu
      acaoBtns = `<span class="badge badge-rascunho" style="font-size:11px;">
        Abre em ${formatarData(p.data_inicio_inscricao)}</span>`;

    } else if (inscricaoAberta && !inscrito) {
      // Período de inscrições aberto e aluno ainda não se inscreveu
      acaoBtns = `<button class="btn btn-primary btn-sm"
        onclick="inscreverProva(${p.id}, '${_esc(p.titulo)}')">Inscrever-se</button>`;

    } else if (inscricaoAberta && inscrito) {
      // Já inscrito — pode cancelar ou iniciar se prova já começou
      const provaComecou = !p.data_inicio || agora >= new Date(p.data_inicio);
      acaoBtns = provaComecou
        ? `<div class="td-actions">
            <button class="btn btn-primary btn-sm"
              onclick="iniciarProva(${p.id}, '${p.tipo}')">Iniciar</button>
            <button class="btn btn-ghost btn-sm"
              onclick="cancelarInscricaoProva(${p.id}, '${_esc(p.titulo)}')">Cancelar inscrição</button>
           </div>`
        : `<div class="td-actions">
            <span class="badge badge-publicada">Inscrito</span>
            <button class="btn btn-ghost btn-sm"
              onclick="cancelarInscricaoProva(${p.id}, '${_esc(p.titulo)}')">Cancelar</button>
           </div>`;

    } else if (inscricaoEncerrada && !inscrito) {
      // Período encerrado e não se inscreveu
      acaoBtns = `<span class="badge badge-rascunho" style="font-size:11px;">Inscrições encerradas</span>`;

    } else {
      // Sem período de inscrições definido — acesso direto
      acaoBtns = `<button class="btn btn-primary btn-sm"
        onclick="iniciarProva(${p.id}, '${p.tipo}')">Iniciar</button>`;
    }

    return `
      <tr data-titulo="${_esc((p.titulo || '').toLowerCase())}" data-tipo="${p.tipo}">
        <td class="td-name">${_esc(p.titulo)}</td>
        <td class="td-muted">${nivelLabel(p.nivel)} ${p.serie ? '— ' + _esc(p.serie) : ''}</td>
        <td>${badgeTipoProva(p.tipo)}</td>
        <td class="td-muted">${p.tempo_limite ? p.tempo_limite + ' min' : '—'}</td>
        <td class="td-muted">${prazoCel}</td>
        <td><div class="td-actions">${acaoBtns}</div></td>
      </tr>`;
  }).join('');
}

function renderTabelaHistorico(historico) {
  const tbody = document.getElementById('historico-tbody');
  if (!historico.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Nenhuma prova realizada ainda.</td></tr>`;
    return;
  }

  tbody.innerHTML = historico.map(t => `
    <tr>
      <td class="td-name">${_esc(t.prova_titulo) || '—'}</td>
      <td>${badgeTipoProva(t.tipo)}</td>
      <td class="td-muted">${formatarData(t.data_inicio || t.data_realizacao)}</td>
      <td><strong>${formatarNota(t.nota)}</strong></td>
      <td>${badgeResultado(t.resultado)}</td>
      <td><div class="td-actions">
        ${t.status !== 'FINALIZADO' && t.status !== undefined ? '' :
          `<button class="btn btn-ghost btn-sm"
            onclick="verResultadoHistorico(${t.id}, '${t.tipo}')">Ver resultado</button>`}
        ${t.certificado_id
          ? `<button class="btn btn-secondary btn-sm"
              onclick="baixarCertPorId(${t.id})">Cert. PDF</button>`
          : ''}
      </div></td>
    </tr>`).join('');
}

function configurarFiltros() {
  const busca   = document.getElementById('provas-aluno-busca');
  const tipoSel = document.getElementById('provas-aluno-tipo');
  const abaSel  = document.getElementById('provas-aluno-aba');

  if (busca)   busca.addEventListener('input',   debounce(aplicarFiltroProvas, 250));
  if (tipoSel) tipoSel.addEventListener('change', aplicarFiltroProvas);
  if (abaSel)  abaSel.addEventListener('change',  () => {
    const isDisp = abaSel.value === 'disponiveis';
    document.getElementById('painel-disponiveis').style.display = isDisp ? '' : 'none';
    document.getElementById('painel-historico').style.display   = isDisp ? 'none' : '';
  });
}

function aplicarFiltroProvas() {
  const busca = (document.getElementById('provas-aluno-busca')?.value || '').toLowerCase();
  const tipo  = document.getElementById('provas-aluno-tipo')?.value || '';

  document.querySelectorAll('#provas-aluno-tbody tr[data-titulo]').forEach(tr => {
    const titulo = tr.dataset.titulo || '';
    const tTipo  = tr.dataset.tipo   || '';
    const ok = titulo.includes(busca) && (!tipo || tTipo === tipo);
    tr.style.display = ok ? '' : 'none';
  });
}

/* ─────────────────────────────────────────
   6. INICIAR / RETOMAR PROVA
   ─────────────────────────────────────── */

/**
 * Abre o modal de escolha de modalidade (US23).
 * Disparado depois que o aluno já está inscrito (ou quando a prova
 * não exige período de inscrição) — ver seção de INSCRIÇÕES abaixo.
 * @param {number} provaId
 * @param {'SIMULADO'|'CERTIFICACAO'} tipo
 */

/* ─────────────────────────────────────────
   INSCRIÇÕES EM PROVAS (US44)
   ─────────────────────────────────────── */

/**
 * Inscreve o aluno na prova. Após sucesso, recarrega a listagem
 * para que o botão mude de "Inscrever-se" para "Inscrito / Iniciar".
 */
async function inscreverProva(provaId, provaTitulo) {
  try {
    await apiFetch(`/inscricoes/provas/${provaId}`, { method: 'POST' });
    showToast(`Inscrição confirmada em "${provaTitulo}"!`, 'success');
    carregarProvasAluno();
  } catch (err) {
    showToast(err.message || 'Não foi possível realizar a inscrição.', 'danger', 6000);
  }
}

/**
 * Cancela inscrição com confirmação antes de chamar a API.
 */
function cancelarInscricaoProva(provaId, provaTitulo) {
  confirmarExclusao(
    'Cancelar inscrição',
    `Deseja cancelar sua inscrição em "${provaTitulo}"?`,
    async () => {
      try {
        await apiFetch(`/inscricoes/provas/${provaId}`, { method: 'DELETE' });
        showToast('Inscrição cancelada.', 'success');
        carregarProvasAluno();
      } catch (err) {
        showToast(err.message || 'Erro ao cancelar inscrição.', 'danger');
      }
    }
  );
}

function iniciarProva(provaId, tipo) {
  // Guarda contexto para uso após a confirmação
  modalidade.provaId = provaId;
  modalidade.tipo    = tipo;
  modalidade.localSelecionado = null;
  modalidade.reservaId        = null;

  // Reseta visual do modal para o passo 1
  _modalidadeMostrarPasso('escolha');
  document.getElementById('modal-modalidade-titulo').textContent =
    `Como deseja realizar esta prova?`;
  document.getElementById('card-online').classList.remove('selected');
  document.getElementById('card-presencial').classList.remove('selected');
  document.getElementById('btn-confirmar-modalidade').style.display = 'none';

  openModal('modal-modalidade');
}

/* ─────────────────────────────────────────
   ESTADO DO FLUXO DE MODALIDADE (US23-25)
   ─────────────────────────────────────── */
const modalidade = {
  provaId:            null,
  tipo:               null,
  escolha:            null,   // 'ONLINE' | 'PRESENCIAL'
  localSelecionado:   null,   // objeto {id, nome, ...}
  reservaId:          null,   // id da reserva criada (US27)
  coordenadas:        null,   // {latitude, longitude}
};

/** Alterna entre os passos do modal */
function _modalidadeMostrarPasso(passo) {
  ['escolha', 'locais', 'confirmar', 'comprovante'].forEach(p => {
    const el = document.getElementById(`modal-step-${p}`);
    if (el) el.style.display = p === passo ? '' : 'none';
  });
  // Ocultar botão confirmar no passo comprovante
  const btnConf = document.getElementById('btn-confirmar-modalidade');
  if (btnConf) btnConf.style.display = passo === 'confirmar' ? '' : 'none';
}

/** Passo 1 → Passo 2 ou confirma online direto */
function selecionarModalidade(escolha) {
  modalidade.escolha = escolha;
  document.getElementById('card-online').classList.toggle('selected', escolha === 'ONLINE');
  document.getElementById('card-presencial').classList.toggle('selected', escolha === 'PRESENCIAL');

  if (escolha === 'ONLINE') {
    // Online: apenas habilita o botão de confirmação
    document.getElementById('btn-confirmar-modalidade').style.display = '';
  } else {
    // Presencial: avança para lista de locais (US24-25)
    document.getElementById('btn-confirmar-modalidade').style.display = 'none';
    _modalidadeMostrarPasso('locais');
    _obterLocalizacaoECarregar();
  }
}

/** Volta do passo de locais para a escolha de modalidade */
function voltarEscolhaModalidade() {
  modalidade.localSelecionado = null;
  _modalidadeMostrarPasso('escolha');
  document.getElementById('btn-confirmar-modalidade').style.display =
    modalidade.escolha === 'ONLINE' ? '' : 'none';
}

/** Volta do passo de confirmação para a lista de locais */
function voltarListaLocais() {
  modalidade.localSelecionado = null;
  _modalidadeMostrarPasso('locais');
  document.getElementById('btn-confirmar-modalidade').style.display = 'none';
  // Re-renderiza lista para desmarcar seleção anterior
  _renderLocais(modalidade._listaCache || []);
}

/* ─────────────────────────────────────────
   GEOLOCALIZAÇÃO E LISTA DE LOCAIS (US24-25)
   ─────────────────────────────────────── */

/** Tenta obter a posição do usuário e então carrega os locais */
function _obterLocalizacaoECarregar() {
  const msgEl = document.getElementById('locais-geo-msg');
  const btnEl = document.getElementById('btn-recarregar-locais');

  if (!navigator.geolocation) {
    msgEl.textContent = 'Geolocalização não suportada pelo seu navegador.';
    btnEl.style.display = '';
    _carregarLocaisFallback();
    return;
  }

  msgEl.textContent = 'Obtendo sua localização...';
  btnEl.style.display = 'none';
  _renderLocaisLoading();

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      modalidade.coordenadas = {
        latitude:  pos.coords.latitude,
        longitude: pos.coords.longitude,
      };
      msgEl.textContent = `Localização obtida — buscando locais próximos.`;
      btnEl.style.display = '';
      carregarLocaisProximos();
    },
    (err) => {
      const msgs = {
        1: 'Permissão de localização negada. Mostrando todos os locais.',
        2: 'Não foi possível determinar sua localização.',
        3: 'Tempo esgotado ao obter localização.',
      };
      msgEl.textContent = msgs[err.code] || 'Erro ao obter localização.';
      btnEl.style.display = '';
      _carregarLocaisFallback();
    },
    { timeout: 8000, maximumAge: 60000 }
  );
}

/** Carrega locais usando as coordenadas obtidas (US25) */
async function carregarLocaisProximos() {
  if (!modalidade.coordenadas) {
    _carregarLocaisFallback();
    return;
  }

  const raio  = document.getElementById('select-raio').value;
  const { latitude, longitude } = modalidade.coordenadas;

  _renderLocaisLoading();
  try {
    const lista = await apiFetch(
      `/locais/proximos?latitude=${latitude}&longitude=${longitude}&raio_km=${raio}&limite=20`
    );
    modalidade._listaCache = lista;
    _renderLocais(lista);
    document.getElementById('locais-geo-msg').textContent =
      `${lista.length} local(is) encontrado(s) em até ${raio} km.`;
  } catch (err) {
    document.getElementById('locais-geo-msg').textContent =
      'Erro ao buscar locais. Tente novamente.';
    document.getElementById('locais-lista').innerHTML =
      `<p style="text-align:center; padding:24px; color:var(--c-text-muted); font-size:14px;">
        Não foi possível carregar os locais.
       </p>`;
  }
}

/** Fallback: lista todos os locais sem filtro de proximidade */
async function _carregarLocaisFallback() {
  _renderLocaisLoading();
  try {
    const lista = await apiFetch('/locais/');
    // Adiciona distancia_km nula para manter compatibilidade com _renderLocais
    modalidade._listaCache = lista.map(l => ({ ...l, distancia_km: null }));
    _renderLocais(modalidade._listaCache);
  } catch {
    document.getElementById('locais-lista').innerHTML =
      `<p style="text-align:center; padding:24px; color:var(--c-text-muted); font-size:14px;">
        Não foi possível carregar os locais.
       </p>`;
  }
}

/** Skeletons de carregamento */
function _renderLocaisLoading() {
  document.getElementById('locais-lista').innerHTML =
    [1, 2, 3].map(() => `<div class="local-skeleton"></div>`).join('');
}

/** Renderiza a lista de locais disponíveis */
function _renderLocais(lista) {
  const el = document.getElementById('locais-lista');
  if (!lista.length) {
    el.innerHTML = `
      <p style="text-align:center; padding:32px; color:var(--c-text-muted); font-size:14px;">
        Nenhum local com vagas disponíveis neste raio.<br>
        <small>Tente aumentar o raio de busca.</small>
      </p>`;
    return;
  }

  el.innerHTML = lista.map(local => {
    const semVagas  = local.vagas_restantes <= 0;
    const distTxt   = local.distancia_km != null
      ? `${local.distancia_km.toFixed(1)} km`
      : '—';
    const vagasCls  = semVagas ? ' sem-vagas' : '';
    const vagasTxt  = semVagas
      ? 'Sem vagas'
      : `${local.vagas_restantes} vaga(s)`;
    const disabled  = semVagas ? 'style="opacity:.5; pointer-events:none;"' : '';

    return `
      <div class="local-card" id="local-card-${local.id}"
           onclick="selecionarLocal(${local.id})" ${disabled}>
        <div class="local-card-icon">
          <svg viewBox="0 0 24 24" fill="currentColor" style="width:18px;height:18px;">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
          </svg>
        </div>
        <div class="local-card-info">
          <p class="local-card-nome">${_esc(local.nome)}</p>
          <p class="local-card-end">${_esc(local.endereco)}${local.cidade ? ', ' + _esc(local.cidade) : ''}</p>
        </div>
        <div class="local-card-meta">
          <span class="local-dist">${distTxt}</span>
          <span class="local-vagas${vagasCls}">${vagasTxt}</span>
        </div>
      </div>`;
  }).join('');
}

/** Passo 2 → Passo 3: seleciona local e exibe confirmação */
function selecionarLocal(localId) {
  const local = (modalidade._listaCache || []).find(l => l.id === localId);
  if (!local) return;

  modalidade.localSelecionado = local;

  // Destaca visualmente o card selecionado
  document.querySelectorAll('.local-card').forEach(c => c.classList.remove('selected'));
  const card = document.getElementById(`local-card-${localId}`);
  if (card) card.classList.add('selected');

  // Monta o painel de confirmação
  const distTxt = local.distancia_km != null
    ? `${local.distancia_km.toFixed(1)} km de distância`
    : '';
  document.getElementById('confirmar-local-info').innerHTML = `
    <p style="font-weight:600; font-size:15px; color:var(--c-primary); margin:0 0 6px;">${_esc(local.nome)}</p>
    <p style="font-size:13px; color:var(--c-text-muted); margin:0 0 4px;">
      ${_esc(local.endereco)}${local.cidade ? ' — ' + _esc(local.cidade) : ''}
    </p>
    ${distTxt ? `<p style="font-size:12px; color:var(--c-text-muted); margin:0;">📍 ${distTxt}</p>` : ''}
    <p style="font-size:12px; color:var(--c-text-muted); margin:4px 0 0;">
      Vagas disponíveis: <strong>${local.vagas_restantes}</strong>
    </p>`;

  _modalidadeMostrarPasso('confirmar');
  document.getElementById('btn-confirmar-modalidade').style.display = '';
}

/* ─────────────────────────────────────────
   CONFIRMAÇÃO FINAL E INÍCIO DA PROVA (US23, US27)
   ─────────────────────────────────────── */

/**
 * Executado ao clicar "Confirmar e reservar vaga" (presencial) ou
 * "Confirmar e iniciar" (online).
 * - Online      → inicia a prova diretamente (US15/US19-20)
 * - Presencial  → cria a reserva, exibe comprovante e aguarda
 *                 o aluno clicar "Iniciar prova agora" (US27)
 */
async function confirmarInicioProva() {
  const { provaId, tipo, escolha, localSelecionado } = modalidade;
  const btn = document.getElementById('btn-confirmar-modalidade');
  // frontend-aluno-3: guarda o rótulo original para destravar o botão no
  // finally (o fluxo ONLINE antes deixava o botão preso em "Aguarde...").
  const btnLabelOriginal = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.textContent = 'Aguarde...'; }

  try {
    if (escolha === 'PRESENCIAL') {
      // US27 — cria reserva primeiro e exibe comprovante
      const necessidades = document.getElementById('reserva-necessidades')?.value.trim() || null;
      const reserva = await apiFetch('/reservas/', {
        method: 'POST',
        body: JSON.stringify({
          prova_id:               provaId,
          local_id:               localSelecionado.id,
          necessidades_especiais: necessidades || undefined,
        }),
      });
      modalidade.reservaId = reserva.id;

      // Preencher comprovante
      document.getElementById('comprovante-id').textContent        = `#${reserva.id}`;
      document.getElementById('comprovante-local').textContent     = localSelecionado.nome || '—';
      document.getElementById('comprovante-prova').textContent     =
        provasDisponiveis.find(p => p.id === provaId)?.titulo || `#${provaId}`;
      document.getElementById('comprovante-expiracao').textContent =
        reserva.data_expiracao ? formatarDataHora(reserva.data_expiracao) : '48h';

      const elNec     = document.getElementById('comprovante-necessidades');
      const elNecRow  = document.getElementById('comprovante-necessidades-row');
      if (necessidades && elNec && elNecRow) {
        elNec.textContent        = necessidades;
        elNecRow.style.display   = 'flex';
      } else if (elNecRow) {
        elNecRow.style.display   = 'none';
      }

      // Ir para passo do comprovante
      _modalidadeMostrarPasso('comprovante');
      if (btn) { btn.disabled = false; btn.textContent = 'Confirmar e reservar vaga'; }
      document.getElementById('btn-cancelar-modalidade').textContent = 'Fechar';
      const btnIniciar = document.getElementById('btn-iniciar-apos-reserva');
      if (btnIniciar) btnIniciar.style.display = '';

    } else {
      // Online → inicia diretamente
      await _iniciarProva(provaId, tipo, escolha);
      closeModal('modal-modalidade');
    }

  } catch (err) {
    showToast(err.message || 'Não foi possível criar a reserva.', 'danger', 6000);
  } finally {
    // Destrava o botão sempre (online com sucesso fecha o modal; online com erro
    // e presencial continuam com o modal aberto e o botão restaurado).
    if (btn) {
      btn.disabled = false;
      // No fluxo PRESENCIAL com sucesso o passo já trocou para "comprovante" e o
      // botão foi ajustado para "Confirmar e reservar vaga"; nos demais casos
      // restauramos o rótulo original capturado no início.
      if (btn.textContent === 'Aguarde...') btn.textContent = btnLabelOriginal;
    }
  }
}

/** Chamado pelo botão "Iniciar prova agora →" após exibir o comprovante. */
async function iniciarProvaAposReserva() {
  const { provaId, tipo, escolha, localSelecionado } = modalidade;
  const btn = document.getElementById('btn-iniciar-apos-reserva');
  if (btn) { btn.disabled = true; btn.textContent = 'Iniciando...'; }

  try {
    await _iniciarProva(provaId, tipo, escolha);
    closeModal('modal-modalidade');
    showToast(`Vaga reservada em ${localSelecionado?.nome || 'local selecionado'}. Boa prova!`, 'success', 4000);
  } catch (err) {
    if (btn) { btn.disabled = false; btn.textContent = 'Iniciar prova agora →'; }
    showToast(err.message || 'Não foi possível iniciar a prova.', 'danger');
  }
}

/** Lógica de início de prova compartilhada entre online e presencial. */
async function _iniciarProva(provaId, tipo, escolha) {
  setLoading(true);
  try {
    let dados;

    if (tipo === 'SIMULADO') {
      dados = await apiFetch('/simulados/iniciar', {
        method: 'POST',
        body: JSON.stringify({
          prova_id:   provaId,
          modalidade: escolha,
          ...(escolha === 'PRESENCIAL' && modalidade.reservaId
            ? { reserva_id: modalidade.reservaId } : {}),
        }),
      });
    } else {
      const sol = await apiFetch('/certificacoes/solicitar', {
        method: 'POST',
        body: JSON.stringify({ prova_id: provaId }),
      });
      dados = await apiFetch(`/certificacoes/iniciar/${sol.tentativa_id}`, { method: 'POST' });
    }

    const info = provasDisponiveis.find(p => p.id === provaId) || null;
    resetarExam();
    exam.tipo          = tipo;
    exam.provaId       = provaId;
    exam.provaInfo     = info;
    exam.tentativaId   = dados.tentativa_id;
    exam.totalQuestoes = dados.total_questoes;

    exam.questoesCache.push({
      id:             dados.questao_id,
      enunciado:      dados.enunciado,
      alternativas:   dados.alternativas || [],
      questao_numero: dados.questao_numero,
    });

    renderQuestaoExam();
    irPara('realizar-prova');

    const tempoSegundos = dados.tempo_restante_segundos
      ?? (info?.tempo_limite ? info.tempo_limite * 60 : null);
    if (tempoSegundos) iniciarTimer(tempoSegundos);

  } finally {
    setLoading(false);
  }
}

/* ─────────────────────────────────────────
   12. MINHAS RESERVAS — US27
   ─────────────────────────────────────── */

let _reservasCache = [];

async function carregarReservas() {
  const elLista = document.getElementById('res-lista');
  if (elLista) elLista.innerHTML = `<div class="table-empty">Carregando...</div>`;

  try {
    _reservasCache = await apiFetch('/reservas/');
    _renderMetricasReservas(_reservasCache);
    _renderListaReservas(_reservasCache);
  } catch (err) {
    if (elLista) elLista.innerHTML = `<div class="table-empty">Erro ao carregar reservas: ${err.message}</div>`;
  }
}

function _renderMetricasReservas(lista) {
  const ativas     = lista.filter(r => r.status === 'ATIVA').length;
  const utilizadas = lista.filter(r => r.status === 'UTILIZADA').length;
  const inativas   = lista.filter(r => r.status === 'CANCELADA' || r.status === 'EXPIRADA').length;

  const elA = document.getElementById('res-stat-ativas');
  const elU = document.getElementById('res-stat-utilizadas');
  const elI = document.getElementById('res-stat-inativas');
  if (elA) elA.textContent = ativas;
  if (elU) elU.textContent = utilizadas;
  if (elI) elI.textContent = inativas;
}

function filtrarReservas() {
  const filtro = document.getElementById('res-filtro-status')?.value || '';
  const filtrada = filtro ? _reservasCache.filter(r => r.status === filtro) : _reservasCache;
  _renderListaReservas(filtrada);
}

function _renderListaReservas(lista) {
  const elLista = document.getElementById('res-lista');
  if (!elLista) return;

  if (!lista.length) {
    elLista.innerHTML = `<div class="table-empty">Nenhuma reserva encontrada.</div>`;
    return;
  }

  elLista.innerHTML = lista.map(r => {
    const ativa     = r.status === 'ATIVA';
    const expirada  = r.status === 'EXPIRADA';
    const agora     = new Date();
    const expDt     = r.data_expiracao ? new Date(r.data_expiracao) : null;
    const expiraEm  = expDt && ativa ? _tempoRestante(expDt) : null;

    const statusBadge = _badgeReserva(r.status);

    return `
      <div style="background:var(--c-card-bg, var(--c-white));
           border-radius:12px; border:1px solid var(--c-border);
           padding:18px 20px;
           ${ativa ? 'border-left:3px solid var(--c-primary);' : ''}">
        <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:12px; flex-wrap:wrap;">
          <div style="flex:1; min-width:180px;">
            <div style="font-size:15px; font-weight:700; color:var(--c-text); margin-bottom:4px;">
              ${_esc(r.prova_titulo) || '—'}
            </div>
            <div style="font-size:13px; color:var(--c-text-muted); margin-bottom:6px;">
              📍 ${_esc(r.local?.nome) || '—'}
              ${r.local?.cidade ? ` — ${_esc(r.local.cidade)}` : ''}
            </div>
            <div style="font-size:12px; color:var(--c-text-muted);">
              ${_esc(r.local?.endereco) || ''}
            </div>
          </div>

          <div style="display:flex; flex-direction:column; align-items:flex-end; gap:6px; flex-shrink:0;">
            ${statusBadge}
            <span style="font-size:11px; color:var(--c-text-muted);">
              Reservado em ${formatarData(r.data_reserva)}
            </span>
            ${expiraEm ? `<span style="font-size:11px; color:var(--c-warning, #e67e22);">⏰ Expira em ${expiraEm}</span>` : ''}
            ${expirada ? `<span style="font-size:11px; color:var(--c-text-muted);">Expirou em ${formatarData(r.data_expiracao)}</span>` : ''}
          </div>
        </div>

        ${r.necessidades_especiais ? `
          <div style="margin-top:10px; font-size:12px; color:var(--c-text-muted);
               background:var(--c-bg); padding:6px 10px; border-radius:6px;">
            ♿ ${_esc(r.necessidades_especiais)}
          </div>` : ''}

        ${ativa ? `
          <div style="margin-top:14px; padding-top:12px; border-top:1px solid var(--c-border);
               display:flex; gap:8px; justify-content:flex-end;">
            <button class="btn btn-ghost btn-sm" onclick="cancelarMinhaReserva(${r.id}, '${(r.prova_titulo || '').replace(/'/g, '')}')">
              Cancelar reserva
            </button>
          </div>` : ''}
      </div>`;
  }).join('');
}

/** Badge colorido por status de reserva */
function _badgeReserva(status) {
  const map = {
    ATIVA:      ['badge-publicada',    'Ativa'],
    UTILIZADA:  ['badge-aprovado',     'Utilizada'],
    CANCELADA:  ['badge-reprovado',    'Cancelada'],
    EXPIRADA:   ['badge-rascunho',     'Expirada'],
  };
  const [cls, label] = map[status] || ['badge-rascunho', status];
  return `<span class="badge ${cls}">${label}</span>`;
}

/** Retorna string "Xh Ym" ou "Xm" de tempo restante até uma data */
function _tempoRestante(dataFim) {
  const diff = Math.max(0, dataFim - new Date());
  const h    = Math.floor(diff / 3_600_000);
  const m    = Math.floor((diff % 3_600_000) / 60_000);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

/** Cancela uma reserva com confirmação */
function cancelarMinhaReserva(reservaId, provaTitulo) {
  confirmarExclusao(
    'Cancelar reserva',
    `Tem certeza que deseja cancelar a reserva para "${provaTitulo}"? A vaga será liberada.`,
    async () => {
      try {
        await apiFetch(`/reservas/${reservaId}`, { method: 'DELETE' });
        showToast('Reserva cancelada. A vaga foi liberada.', 'success');
        carregarReservas();
      } catch (err) {
        showToast(err.message || 'Erro ao cancelar reserva.', 'danger');
      }
    }
  );
}



/** Continua uma tentativa EM ANDAMENTO entrando na questão atual (questao_atual). */
async function continuarProva(tentativaId, tipo = 'SIMULADO') {
  setLoading(true);
  try {
    const dados = await apiFetch(`/simulados/${tentativaId}/questao_atual`);

    resetarExam();
    exam.tipo          = tipo;
    exam.tentativaId   = tentativaId;
    exam.totalQuestoes = dados.total_questoes;

    exam.questoesCache.push({
      id:             dados.questao_id,
      enunciado:      dados.enunciado,
      alternativas:   dados.alternativas || [],
      questao_numero: dados.questao_numero,
    });

    renderQuestaoExam();
    irPara('realizar-prova');

    if (dados.tempo_restante_segundos) iniciarTimer(dados.tempo_restante_segundos);

  } catch (err) {
    showToast(err.message || 'Não foi possível continuar a prova.', 'danger');
  } finally {
    setLoading(false);
  }
}

/** Retoma um simulado pausado. */
async function retomarProva(tentativaId) {
  setLoading(true);
  try {
    const dados = await apiFetch(`/simulados/${tentativaId}/retomar`, { method: 'PATCH' });

    resetarExam();
    exam.tipo         = 'SIMULADO';
    exam.tentativaId  = tentativaId;
    exam.totalQuestoes = dados.total_questoes;

    exam.questoesCache.push({
      id:            dados.questao_id,
      enunciado:     dados.enunciado,
      alternativas:  dados.alternativas || [],
      questao_numero: dados.questao_numero,
    });

    renderQuestaoExam();
    irPara('realizar-prova');

    if (dados.tempo_restante_segundos) iniciarTimer(dados.tempo_restante_segundos);

  } catch (err) {
    showToast(err.message || 'Não foi possível retomar a prova.', 'danger');
  } finally {
    setLoading(false);
  }
}

function resetarExam() {
  pararTimer();
  Object.assign(exam, {
    tipo: null, provaId: null, provaInfo: null, tentativaId: null,
    totalQuestoes: 0, indiceAtual: 0, questoesCache: [],
    respostasSalvas: {}, altSelecionadaAgora: null,
    enviadas: new Set(), timerInterval: null,
    tempoRestante: null, certificadoId: null, certificadoUrlPdf: null,
  });
}

/* ─────────────────────────────────────────
   7. RENDERIZAÇÃO DO EXAME
   ─────────────────────────────────────── */

/**
 * Valida que uma URL é http(s) (evita javascript:, data:, etc.) antes de
 * usá-la em atributos src. Retorna true só para http:// e https://.
 */
function _urlSegura(url) {
  if (!url || typeof url !== 'string') return false;
  try {
    const u = new URL(url, window.location.origin);
    return u.protocol === 'http:' || u.protocol === 'https:';
  } catch {
    return false;
  }
}

/** Renderiza a questão atual (baseado em exam.indiceAtual). */
function renderQuestaoExam() {
  // interrompe a leitura em voz da questão anterior
  if (window.Narrador) Narrador.parar();

  const q = exam.questoesCache[exam.indiceAtual];
  if (!q) return;

  const num   = q.questao_numero || (exam.indiceAtual + 1);
  const total = exam.totalQuestoes;

  // Cabeçalho
  document.getElementById('exam-titulo').textContent =
    exam.provaInfo?.titulo || 'Realizando prova';
  document.getElementById('exam-progresso').textContent =
    `Questão ${num} de ${total}`;
  document.getElementById('exam-questao-numero').textContent =
    `Questão ${num}`;
  document.getElementById('exam-enunciado').textContent = q.enunciado;

  // Imagem
  const imgWrap = document.getElementById('exam-imagem-wrap');
  const imgEl   = document.getElementById('exam-imagem');
  if (q.imagem_url && _urlSegura(q.imagem_url)) {
    imgEl.src = q.imagem_url;
    imgWrap.style.display = '';
  } else {
    imgWrap.style.display = 'none';
  }

  // Alternativas
  const altDiv    = document.getElementById('exam-alternativas');
  const subWrap   = document.getElementById('exam-subjetiva-wrap');
  const altSalva  = exam.respostasSalvas[q.id] ?? null;
  exam.altSelecionadaAgora = altSalva;

  if (q.alternativas && q.alternativas.length > 0) {
    altDiv.style.display = 'flex';
    subWrap.style.display = 'none';

    const letras = ['A', 'B', 'C', 'D', 'E', 'F'];
    altDiv.innerHTML = q.alternativas
      .sort((a, b) => (a.ordem ?? 0) - (b.ordem ?? 0))
      .map((alt, i) => {
        const ativa = altSalva === alt.id ? 'alt-selecionada' : '';
        return `
          <div class="alternativa-item ${ativa}" id="alt-${alt.id}"
               onclick="selecionarAlternativa(${alt.id}, this)" role="radio"
               aria-checked="${altSalva === alt.id}" tabindex="0">
            <span class="alt-letra">${letras[i] || i + 1}</span>
            <span class="alt-texto">${_esc(alt.texto)}</span>
            ${alt.imagem_url && _urlSegura(alt.imagem_url)
              ? `<img src="${_esc(alt.imagem_url)}" alt="Imagem da alternativa"
                  style="max-width:200px;margin-top:8px;border-radius:6px;">`
              : ''}
            ${Narrador.suportado()
              ? `<button type="button" class="alt-ouvir" title="Ouvir esta opção"
                   aria-label="Ouvir esta opção"
                   onclick="event.stopPropagation(); narrarAlternativaEl(this)">🔊</button>`
              : ''}
          </div>`;
      }).join('');
  } else {
    // Questão subjetiva (sem alternativas)
    altDiv.style.display = 'none';
    subWrap.style.display = '';
    document.getElementById('exam-resposta-texto').value = '';
  }

  // Botões de navegação
  document.getElementById('btn-anterior').disabled = exam.indiceAtual === 0;
  document.getElementById('btn-proxima').textContent =
    exam.indiceAtual === exam.totalQuestoes - 1 ? 'Finalizar ✓' : 'Próxima →';

  // Alerta inline
  const alerta = document.getElementById('exam-alert');
  alerta.className = 'alert-box';
  alerta.textContent = '';

  atualizarNavGrid();
}

/** Seleciona uma alternativa visualmente (sem salvar ainda). */
function selecionarAlternativa(altId, el) {
  document.querySelectorAll('.alternativa-item').forEach(d => {
    d.classList.remove('alt-selecionada');
    d.setAttribute('aria-checked', 'false');
  });
  el.classList.add('alt-selecionada');
  el.setAttribute('aria-checked', 'true');
  exam.altSelecionadaAgora = altId;
}

/** Atualiza o grid de navegação por número. */
function atualizarNavGrid() {
  const grid = document.getElementById('exam-nav-grid');
  if (!grid) return;

  const atual = exam.indiceAtual;
  const total = exam.totalQuestoes;

  let html = '';
  for (let i = 0; i < total; i++) {
    const q = exam.questoesCache[i];
    const qId      = q?.id;
    const respondida = qId && exam.respostasSalvas[qId] !== undefined;
    const isAtual  = i === atual;

    let cls = 'nav-q-btn';
    if (isAtual)    cls += ' nav-q-atual';
    else if (respondida) cls += ' nav-q-ok';
    else if (q)     cls += ' nav-q-vista';

    html += `<button class="${cls}" onclick="irParaQuestaoN(${i})"
      title="Questão ${i + 1}">${i + 1}</button>`;
  }
  grid.innerHTML = html;
}

/** Vai para uma questão específica pelo índice (se já estiver no cache). */
async function irParaQuestaoN(indice) {
  if (indice === exam.indiceAtual) return;

  // Salva a resposta atual antes de pular
  if (exam.altSelecionadaAgora !== null
      && !exam.enviadas.has(exam.questoesCache[exam.indiceAtual]?.id)) {
    await salvarResposta(true); // silencioso
  }

  if (indice < exam.questoesCache.length) {
    exam.indiceAtual = indice;
    renderQuestaoExam();
  } else {
    showToast('Responda as questões anteriores para chegar aqui.', 'warning');
  }
}

/* ─────────────────────────────────────────
   8. SALVAR RESPOSTA E NAVEGAR
   ─────────────────────────────────────── */

/**
 * Salva a resposta da questão atual via API e avança para a próxima.
 * @param {boolean} silencioso – não exibe toast de confirmação
 * @returns {Promise<boolean>} true se foi possível avançar
 */
async function salvarResposta(silencioso = false) {
  const q   = exam.questoesCache[exam.indiceAtual];
  const alt = exam.altSelecionadaAgora;

  if (!alt) {
    if (!silencioso) {
      const alerta = document.getElementById('exam-alert');
      alerta.textContent = 'Selecione uma alternativa antes de salvar.';
      alerta.className = 'alert-box error show';
    }
    return false;
  }

  // Se já enviada, só atualiza localmente
  if (exam.enviadas.has(q.id)) {
    exam.respostasSalvas[q.id] = alt;
    return true;
  }

  try {
    const endpoint = exam.tipo === 'SIMULADO' ? '/simulados/responder' : '/certificacoes/responder';
    const resp = await apiFetch(endpoint, {
      method: 'POST',
      body: JSON.stringify({
        tentativa_id: exam.tentativaId,
        questao_id:   q.id,
        alternativa_id: alt,
      }),
    });

    exam.respostasSalvas[q.id] = alt;
    exam.enviadas.add(q.id);

    // Se o servidor retornou a próxima questão, adiciona ao cache
    if (!resp.finalizado && resp.proxima_questao_id) {
      const jaTemProxima = exam.questoesCache.length > exam.indiceAtual + 1;
      if (!jaTemProxima) {
        exam.questoesCache.push({
          id:            resp.proxima_questao_id,
          enunciado:     resp.proxima_questao_enunciado,
          alternativas:  resp.proximas_alternativas || [],
          questao_numero: resp.questao_numero,
        });
        exam.totalQuestoes = resp.total_questoes || exam.totalQuestoes;
      }
    }

    if (!silencioso) showToast('Resposta salva!', 'success', 1800);

    // Prova finalizada automaticamente pelo servidor
    if (resp.finalizado) {
      pararTimer();
      await carregarResultado();
      return true;
    }

    return true;

  } catch (err) {
    if (!silencioso) showToast(err.message || 'Erro ao salvar resposta.', 'danger');
    return false;
  }
}

/** Botão Anterior / Próxima */
async function navegarQuestao(direcao) {
  if (direcao === 1) {
    // Avançar: salva primeiro
    const q = exam.questoesCache[exam.indiceAtual];
    const temAlt = exam.questoesCache[exam.indiceAtual]?.alternativas?.length > 0;

    if (temAlt && exam.altSelecionadaAgora === null && !exam.enviadas.has(q?.id)) {
      document.getElementById('exam-alert').textContent = 'Selecione uma alternativa.';
      document.getElementById('exam-alert').className   = 'alert-box error show';
      return;
    }

    const isUltima = exam.indiceAtual === exam.totalQuestoes - 1;

    if (exam.altSelecionadaAgora !== null && !exam.enviadas.has(q?.id)) {
      const ok = await salvarResposta(true);
      if (!ok) return;
    }

    if (isUltima) {
      confirmarFinalizarProva();
      return;
    }

    if (exam.indiceAtual < exam.questoesCache.length - 1) {
      exam.indiceAtual++;
      exam.altSelecionadaAgora = exam.respostasSalvas[exam.questoesCache[exam.indiceAtual]?.id] ?? null;
      renderQuestaoExam();
    } else {
      showToast('Sem próxima questão disponível ainda.', 'warning');
    }

  } else {
    // Voltar
    if (exam.indiceAtual > 0) {
      exam.indiceAtual--;
      exam.altSelecionadaAgora = exam.respostasSalvas[exam.questoesCache[exam.indiceAtual]?.id] ?? null;
      renderQuestaoExam();
    }
  }
}

/* ─────────────────────────────────────────
   9. TIMER
   ─────────────────────────────────────── */

function iniciarTimer(totalSegundos) {
  pararTimer();
  exam.tempoRestante = Math.floor(totalSegundos);

  atualizarDisplayTimer();

  exam.timerInterval = setInterval(() => {
    exam.tempoRestante--;
    atualizarDisplayTimer();

    if (exam.tempoRestante <= 0) {
      pararTimer();
      showToast('Tempo esgotado! Enviando prova automaticamente.', 'warning', 4000);
      finalizarProva();
    }

    // Alerta vermelho nos últimos 5 minutos
    const timerEl = document.getElementById('exam-timer');
    if (timerEl && exam.tempoRestante <= 300) {
      timerEl.style.color = 'var(--c-danger)';
      timerEl.style.fontWeight = '700';
    }
  }, 1000);
}

function pararTimer() {
  if (exam.timerInterval) {
    clearInterval(exam.timerInterval);
    exam.timerInterval = null;
  }
}

function atualizarDisplayTimer() {
  const el = document.getElementById('exam-timer');
  if (!el) return;
  const s = exam.tempoRestante ?? 0;
  const mm = String(Math.floor(s / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  el.textContent = `⏱ ${mm}:${ss}`;
}

/* ─────────────────────────────────────────
   10. FINALIZAR / SAIR DA PROVA
   ─────────────────────────────────────── */

function confirmarFinalizarProva() {
  const pendentes = exam.totalQuestoes - Object.keys(exam.respostasSalvas).length;

  const msg = document.getElementById('modal-finalizar-msg');
  if (msg) {
    msg.textContent = pendentes > 0
      ? `Você ainda tem ${pendentes} questão(ões) sem resposta. Ao finalizar, a nota será calculada com base nas respondidas. Deseja continuar?`
      : 'Ao finalizar, sua nota será calculada e não será possível alterar as respostas.';
  }
  openModal('modal-finalizar');
}

async function finalizarProva() {
  closeModal('modal-finalizar');
  pararTimer();
  await carregarResultado();
}

function confirmarSairProva() {
  openModal('modal-sair-prova');
}

async function pausarESair() {
  closeModal('modal-sair-prova');
  if (exam.tipo === 'SIMULADO' && exam.tentativaId) {
    try {
      await apiFetch(`/simulados/${exam.tentativaId}/pausar`, { method: 'PATCH' });
      showToast('Prova pausada. Você pode retomá-la depois.', 'info');
    } catch {
      // Ignora erro de pausa — vai sair mesmo assim
    }
  }
  resetarExam();
  irPara('provas');
}

/* ─────────────────────────────────────────
   11. RESULTADO
   ─────────────────────────────────────── */

async function carregarResultado() {
  setLoading(true);
  try {
    const endpoint = exam.tipo === 'SIMULADO'
      ? `/simulados/${exam.tentativaId}/resultado`
      : `/certificacoes/${exam.tentativaId}/resultado`;

    const res = await apiFetch(endpoint);

    irPara('resultado');

    // Métricas
    const nota = res.nota ?? 0;
    const acertos = res.total_acertos ?? 0;
    const total   = res.total_questoes ?? 1;
    const pct     = Math.round((acertos / total) * 100);
    const aprovado = res.status === 'APROVADO';

    document.getElementById('res-nota').textContent       = formatarNota(nota);
    // res-prova-nome usa textContent — já é seguro, sem necessidade de _esc.
    document.getElementById('res-prova-nome').textContent = res.prova_titulo || 'Prova';
    document.getElementById('res-percentual').textContent = `${pct}%`;
    document.getElementById('res-acertos-label').textContent = `${acertos} de ${total} acertos`;
    document.getElementById('res-resultado').textContent  = aprovado ? 'Aprovado' : 'Reprovado';
    document.getElementById('res-resultado').style.color  = aprovado ? 'var(--c-success)' : 'var(--c-danger)';
    document.getElementById('res-nota-minima').textContent =
      exam.provaInfo?.nota_minima ? `Nota mínima: ${exam.provaInfo.nota_minima}` : '';

    const badge = document.getElementById('res-badge-resultado');
    badge.textContent  = aprovado ? 'Aprovado' : 'Reprovado';
    badge.className    = `badge ${aprovado ? 'badge-aprovado' : 'badge-reprovado'}`;

    // Gabarito / revisão (LOGICA-11 / frontend-aluno-6)
    // SIMULADO detalha escolhida x correta; CERTIFICAÇÃO não traz "respostas"
    // (o backend omite o gabarito), caindo no "Gabarito não disponível".
    const tbody = document.getElementById('res-gabarito-tbody');
    const ehSimulado = exam.tipo === 'SIMULADO';
    if (res.respostas && res.respostas.length) {
      tbody.innerHTML = res.respostas.map((r, i) => {
        const ok = r.acertou;
        // No SIMULADO mostramos a alternativa escolhida e a correta abaixo do
        // enunciado; tudo escapado com _esc (enunciado/alternativas digitados
        // por professores). data: e < > não devem injetar HTML.
        const revisao = ehSimulado
          ? `<div style="margin-top:6px; font-size:12px; line-height:1.5;">
               <div style="color:var(--c-text-muted);">
                 Sua resposta:
                 <strong style="color:${ok ? 'var(--c-success)' : 'var(--c-danger)'};">
                   ${_esc(r.alternativa_escolhida) || '— (sem resposta)'}
                 </strong>
               </div>
               ${!ok ? `<div style="color:var(--c-text-muted);">
                 Correta: <strong style="color:var(--c-success);">${_esc(r.alternativa_correta) || '—'}</strong>
               </div>` : ''}
             </div>`
          : '';
        return `<tr>
          <td>${i + 1}</td>
          <td class="td-muted" style="max-width:300px; white-space:normal;">
            ${_esc(r.enunciado) || _esc(r.questao_id) || '—'}
            ${revisao}
          </td>
          <td>
            <span class="badge ${ok ? 'badge-aprovado' : 'badge-reprovado'}">
              ${ok ? 'Correto' : 'Errado'}
            </span>
          </td>
        </tr>`;
      }).join('');
    } else {
      tbody.innerHTML = `<tr><td colspan="3" class="table-empty">Gabarito não disponível.</td></tr>`;
    }

    // Certificado (só para CERTIFICACAO aprovada)
    if (exam.tipo === 'CERTIFICACAO' && aprovado) {
      await gerarCertificado();
    } else {
      document.getElementById('res-cert-status').textContent = 'Não disponível';
      document.getElementById('res-cert-codigo').textContent  = exam.tipo !== 'CERTIFICACAO'
        ? 'Apenas em certificações' : 'Nota insuficiente';
      document.getElementById('res-cert-card').style.display = 'none';
      document.getElementById('btn-baixar-cert').style.display = 'none';
    }

  } catch (err) {
    // frontend-aluno-7: não existe endpoint dedicado de "finalizar" — a
    // finalização ocorre ao responder a última questão (ou por tempo). Se o
    // aluno acionou /resultado antes de a tentativa estar concluída, o backend
    // responde 400 com "ainda não finalizado". Tratamos de forma graciosa, sem
    // quebrar: continuamos na prova e orientamos o aluno.
    const msg = err.message || '';
    if (/ainda não finalizad/i.test(msg)) {
      showToast(
        'Ainda há questões a responder. Responda todas as questões (ou aguarde o término do tempo) para ver o resultado.',
        'warning',
        6000
      );
    } else {
      showToast(msg || 'Erro ao carregar resultado.', 'danger');
    }
  } finally {
    setLoading(false);
  }
}

async function gerarCertificado() {
  try {
    // POST /pdf/certificados/{tentativa_id} garante o registro do certificado,
    // gera o PDF de fato (brasão + QR code) e faz upload para o Supabase Storage,
    // retornando uma url_pdf real (não mais o placeholder de /certificacoes/.../certificado).
    const cert = await apiFetch(`/pdf/certificados/${exam.tentativaId}`, {
      method: 'POST',
    });

    exam.certificadoId     = cert.id;
    exam.certificadoUrlPdf = cert.url_pdf;

    document.getElementById('res-cert-status').textContent = 'Disponível';
    document.getElementById('res-cert-codigo').textContent  = cert.codigo;
    document.getElementById('res-cert-codigo-display').textContent = cert.codigo;
    document.getElementById('res-cert-card').style.display = '';

    if (cert.url_pdf) {
      document.getElementById('btn-baixar-cert').style.display = '';
    }

  } catch (err) {
    document.getElementById('res-cert-status').textContent = 'Erro ao gerar';
    document.getElementById('res-cert-codigo').textContent  = err.message || 'Tente novamente.';
  }
}

/** Abre o PDF já gerado por gerarCertificado() — é uma URL pública/assinada do Storage, sem necessidade de Authorization. */
function baixarCertificado() {
  if (!exam.certificadoUrlPdf) { showToast('Certificado não disponível.', 'warning'); return; }
  window.open(exam.certificadoUrlPdf, '_blank');
}

/**
 * Gera (ou regenera) e abre o PDF a partir do ID da TENTATIVA — não existe
 * endpoint de download por certificado_id, então os pontos de chamada desta
 * função foram ajustados para passar t.id (tentativa) em vez de t.certificado_id.
 */
async function baixarCertPorId(tentativaId) {
  const win = window.open('', '_blank'); // abre a aba já no clique, ainda síncrono
  try {
    const cert = await apiFetch(`/pdf/certificados/${tentativaId}`, { method: 'POST' });
    if (!cert.url_pdf) { win.close(); showToast('PDF não disponível.', 'warning'); return; }
    win.location.href = cert.url_pdf;
  } catch (err) {
    win.close();
    showToast(err.message || 'Erro ao baixar PDF.', 'danger');
  }
}

/** Ver resultado de uma tentativa histórica. */
async function verResultadoHistorico(tentativaId, tipo) {
  exam.tentativaId  = tentativaId;
  exam.tipo         = tipo;
  exam.provaInfo    = null;
  exam.certificadoId = null;
  await carregarResultado();
}

/* ─────────────────────────────────────────
   12. CERTIFICADOS
   ─────────────────────────────────────── */

/** Cache do histórico para filtro local sem refetch */
let _certHistCache = [];

async function carregarCertificados() {
  const tbody = document.getElementById('certs-tbody');
  tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Carregando...</td></tr>`;

  // Sincronizar avatar
  const me = getUsuario();
  const avatarEl = document.getElementById('certs-avatar');
  if (avatarEl && me) avatarEl.textContent = iniciais(me.nome);

  try {
    _certHistCache = await apiFetch('/certificacoes/historico');
    _renderMetricasCerts(_certHistCache);
    _renderTabelaCerts(_certHistCache);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Erro ao carregar: ${err.message}</td></tr>`;
  }
}

function _renderMetricasCerts(lista) {
  const aprovados = lista.filter(t => t.resultado === 'APROVADO');
  const comCert   = lista.filter(t => t.certificado_id);

  const elTotal   = document.getElementById('cert-stat-total');
  const elAprov   = document.getElementById('cert-stat-aprovados');
  const elCerts   = document.getElementById('cert-stat-certs');
  if (elTotal) elTotal.textContent = lista.length;
  if (elAprov) elAprov.textContent = aprovados.length;
  if (elCerts) elCerts.textContent = comCert.length;
}

function filtrarCertificados() {
  const filtroResult = document.getElementById('cert-filtro-resultado')?.value || '';
  const filtroBusca  = (document.getElementById('cert-filtro-busca')?.value || '').toLowerCase();

  const filtrada = _certHistCache.filter(t => {
    const matchResult = !filtroResult || t.resultado === filtroResult;
    const matchBusca  = !filtroBusca  || (t.prova_titulo || '').toLowerCase().includes(filtroBusca);
    return matchResult && matchBusca;
  });

  _renderTabelaCerts(filtrada);
}

function _renderTabelaCerts(lista) {
  const tbody = document.getElementById('certs-tbody');

  if (!lista.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Nenhuma tentativa encontrada.</td></tr>`;
    return;
  }

  tbody.innerHTML = lista.map(t => {
    const aprovado    = t.resultado === 'APROVADO';
    const temCert     = !!t.certificado_id;
    const bloqueado   = t.bloqueio_ate && new Date(t.bloqueio_ate) > new Date();
    const bloqData    = t.bloqueio_ate ? formatarData(t.bloqueio_ate) : null;

    // Coluna "Código / Situação"
    let codigoCol;
    if (aprovado && t.codigo_validacao) {
      codigoCol = `<code style="font-size:11px; background:var(--c-bg); padding:3px 8px;
        border-radius:4px; border:1px solid var(--c-border); letter-spacing:.04em;">
        ${t.codigo_validacao}
      </code>`;
    } else if (bloqueado) {
      codigoCol = `<span style="font-size:12px; color:var(--c-danger, #d32f2f);">
        🔒 Bloqueado até ${bloqData}
      </span>`;
    } else if (!aprovado && !bloqueado && t.resultado === 'REPROVADO') {
      codigoCol = `<span style="font-size:12px; color:var(--c-text-muted);">Pode tentar novamente</span>`;
    } else {
      codigoCol = `<span style="color:var(--c-text-muted);">—</span>`;
    }

    // Coluna Ações
    let acoes;
    if (temCert) {
      acoes = `
        <div class="td-actions">
          <button class="btn btn-primary btn-sm" onclick="baixarCertPorId(${t.id})">
            Baixar PDF
          </button>
          <button class="btn btn-ghost btn-sm" onclick="copiarCodigo('${t.codigo_validacao}')"
            title="Copiar código de validação">
            Copiar código
          </button>
        </div>`;
    } else if (bloqueado) {
      acoes = `<span class="badge badge-reprovado" style="font-size:11px;">Aguardando</span>`;
    } else {
      acoes = `<span style="color:var(--c-text-muted); font-size:12px;">—</span>`;
    }

    return `
      <tr>
        <td class="td-name">${t.prova_titulo || '—'}</td>
        <td class="td-muted">${formatarData(t.data_realizacao)}</td>
        <td><strong>${formatarNota(t.nota)}</strong></td>
        <td>${badgeResultado(t.resultado)}</td>
        <td>${codigoCol}</td>
        <td>${acoes}</td>
      </tr>`;
  }).join('');
}

/** Copia o código de validação para a área de transferência */
function copiarCodigo(codigo) {
  if (!codigo) return;
  navigator.clipboard.writeText(codigo)
    .then(() => showToast('Código copiado!', 'success', 2000))
    .catch(() => showToast('Não foi possível copiar. Código: ' + codigo, 'info', 5000));
}


/* ─────────────────────────────────────────
   13. MINHA ÁREA
   ─────────────────────────────────────── */

/* ─────────────────────────────────────────
   13. MINHA ÁREA — US24 (perfil + localização)
   ─────────────────────────────────────── */

/** Dados do usuário atual em memória (evita refetch repetido) */
let _meCache = null;

async function carregarMinhaArea() {
  try {
    const [me, hist, certs] = await Promise.all([
      apiFetch('/auth/me'),
      apiFetch('/simulados/historico'),
      apiFetch('/certificacoes/historico'),
    ]);

    _meCache = me;

    // Cabeçalho de identidade
    document.getElementById('area-nome').textContent = me.nome || '—';
    document.getElementById('area-nivel-serie').textContent =
      [nivelLabel(me.nivel), me.serie].filter(Boolean).join(' — ') || '—';
    const ini = iniciais(me.nome);
    ['area-avatar', 'area-avatar-big'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = ini;
    });

    // Campos de leitura
    document.getElementById('area-email').value         = me.email || '';
    document.getElementById('area-nivel-display').value = nivelLabel(me.nivel) || '—';
    document.getElementById('area-serie-display').value = me.serie || '—';

    // Totais
    document.getElementById('area-total-provas').textContent = hist.length;
    document.getElementById('area-total-certs').textContent  =
      certs.filter(t => t.certificado_id).length;

    // Status de localização salva (US24)
    _renderStatusLocalizacao(me.latitude, me.longitude);

    // Histórico combinado com coluna Tipo
    const combinados = [
      ...hist.map(t => ({ ...t, tipoLabel: 'Simulado' })),
      ...certs.map(t => ({ ...t, tipoLabel: 'Certificação' })),
    ].sort((a, b) =>
      new Date(b.data_inicio || b.data_realizacao || 0) -
      new Date(a.data_inicio || a.data_realizacao || 0));

    const tbody = document.getElementById('area-historico-tbody');
    tbody.innerHTML = combinados.length
      ? combinados.map(t => `
          <tr>
            <td class="td-name">${t.prova_titulo || '—'}</td>
            <td class="td-muted">${t.tipoLabel}</td>
            <td class="td-muted">${formatarData(t.data_inicio || t.data_realizacao)}</td>
            <td><strong>${formatarNota(t.nota)}</strong></td>
            <td>${badgeResultado(t.resultado)}</td>
          </tr>`).join('')
      : `<tr><td colspan="5" class="table-empty">Nenhuma tentativa registrada.</td></tr>`;

  } catch (err) {
    showToast('Erro ao carregar perfil.', 'danger');
  }
}

/** Renderiza o bloco de status de localização */
function _renderStatusLocalizacao(lat, lon) {
  const label  = document.getElementById('area-loc-label');
  const coords = document.getElementById('area-loc-coords');
  const badge  = document.getElementById('area-loc-badge');
  const icon   = document.getElementById('area-loc-icon');

  if (lat != null && lon != null) {
    icon.textContent      = '✅';
    label.textContent     = 'Localização cadastrada';
    coords.textContent    = `Lat: ${lat.toFixed(5)}  |  Lon: ${lon.toFixed(5)}`;
    badge.style.display   = 'inline-flex';
    badge.className       = 'badge badge-simulado';
    badge.textContent     = 'Salva';
  } else {
    icon.textContent      = '📍';
    label.textContent     = 'Não cadastrada';
    coords.textContent    = 'Cadastre para encontrar locais de prova próximos.';
    badge.style.display   = 'none';
  }
}

/* ── Edição de dados pessoais ── */

function abrirEdicaoDados() {
  if (!_meCache) return;
  document.getElementById('edit-nome').value  = _meCache.nome  || '';
  document.getElementById('edit-serie').value = _meCache.serie || '';
  const sel = document.getElementById('edit-nivel');
  if (_meCache.nivel) sel.value = _meCache.nivel;

  document.getElementById('area-dados-readonly').style.display = 'none';
  document.getElementById('area-dados-edit').style.display     = 'flex';
  document.getElementById('btn-editar-dados').style.display    = 'none';
}

function cancelarEdicaoDados() {
  document.getElementById('area-dados-readonly').style.display = 'flex';
  document.getElementById('area-dados-edit').style.display     = 'none';
  document.getElementById('btn-editar-dados').style.display    = '';
}

async function salvarDadosPessoais() {
  const nome  = document.getElementById('edit-nome').value.trim();
  const nivel = document.getElementById('edit-nivel').value;
  const serie = document.getElementById('edit-serie').value.trim();

  if (!nome || nome.length < 2) {
    showToast('Nome deve ter pelo menos 2 caracteres.', 'warning'); return;
  }

  const btn = document.getElementById('btn-salvar-dados');
  btn.disabled = true; btn.textContent = 'Salvando...';

  try {
    const atualizado = await apiFetch('/usuarios/me/perfil', {
      method: 'PATCH',
      body: JSON.stringify({ nome, nivel, serie }),
    });

    _meCache = { ..._meCache, ...atualizado };

    // Atualiza UI
    document.getElementById('area-nome').textContent      = atualizado.nome;
    document.getElementById('area-nivel-serie').textContent =
      [nivelLabel(atualizado.nivel), atualizado.serie].filter(Boolean).join(' — ') || '—';
    document.getElementById('area-nivel-display').value   = nivelLabel(atualizado.nivel) || '—';
    document.getElementById('area-serie-display').value   = atualizado.serie || '—';
    const ini = iniciais(atualizado.nome);
    ['user-avatar', 'area-avatar', 'area-avatar-big'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = ini;
    });
    const unEl = document.getElementById('sidebar-username');
    if (unEl) unEl.textContent = atualizado.nome;

    cancelarEdicaoDados();
    showToast('Dados atualizados com sucesso!', 'success');
  } catch (err) {
    showToast(err.message || 'Erro ao salvar dados.', 'danger');
  } finally {
    btn.disabled = false; btn.textContent = 'Salvar';
  }
}

/* ── Edição de senha ── */

function abrirEdicaoSenha() {
  document.getElementById('edit-senha').value         = '';
  document.getElementById('edit-senha-confirm').value = '';
  document.getElementById('area-senha-readonly').style.display = 'none';
  document.getElementById('area-senha-edit').style.display     = 'flex';
  document.getElementById('btn-editar-senha').style.display    = 'none';
}

function cancelarEdicaoSenha() {
  document.getElementById('area-senha-readonly').style.display = '';
  document.getElementById('area-senha-edit').style.display     = 'none';
  document.getElementById('btn-editar-senha').style.display    = '';
}

async function salvarSenha() {
  const senha   = document.getElementById('edit-senha').value;
  const confirm = document.getElementById('edit-senha-confirm').value;

  if (senha.length < 8) {
    showToast('A senha deve ter pelo menos 8 caracteres.', 'warning'); return;
  }
  if (senha !== confirm) {
    showToast('As senhas não coincidem.', 'warning'); return;
  }

  try {
    await apiFetch('/usuarios/me/perfil', {
      method: 'PATCH',
      body: JSON.stringify({ senha }),
    });
    cancelarEdicaoSenha();
    showToast('Senha alterada com sucesso!', 'success');
  } catch (err) {
    showToast(err.message || 'Erro ao alterar senha.', 'danger');
  }
}

/* ── Localização (US24) ── */

async function usarLocalizacaoGPS() {
  const btn = document.getElementById('btn-usar-gps');
  if (!navigator.geolocation) {
    showToast('Geolocalização não suportada pelo seu navegador.', 'warning'); return;
  }

  btn.disabled = true; btn.textContent = '⏳ Obtendo localização...';

  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      const latitude  = pos.coords.latitude;
      const longitude = pos.coords.longitude;
      await _salvarLocalizacao(latitude, longitude);
      btn.disabled = false; btn.textContent = '📡 Usar minha localização atual';
    },
    (err) => {
      const msgs = {
        1: 'Permissão negada. Tente informar manualmente.',
        2: 'Não foi possível determinar sua localização.',
        3: 'Tempo esgotado ao obter localização.',
      };
      showToast(msgs[err.code] || 'Erro ao obter localização.', 'warning');
      btn.disabled = false; btn.textContent = '📡 Usar minha localização atual';
    },
    { timeout: 10000 }
  );
}

function abrirLocManual() {
  if (_meCache?.latitude != null) {
    document.getElementById('edit-lat').value = _meCache.latitude;
    document.getElementById('edit-lon').value = _meCache.longitude;
  }
  document.getElementById('area-loc-manual').style.display = '';
  document.getElementById('btn-loc-manual').style.display  = 'none';
}

function fecharLocManual() {
  document.getElementById('area-loc-manual').style.display = 'none';
  document.getElementById('btn-loc-manual').style.display  = '';
}

async function salvarLocalizacaoManual() {
  const lat = parseFloat(document.getElementById('edit-lat').value);
  const lon = parseFloat(document.getElementById('edit-lon').value);

  if (isNaN(lat) || lat < -90  || lat > 90)  {
    showToast('Latitude inválida. Use um valor entre −90 e 90.', 'warning'); return;
  }
  if (isNaN(lon) || lon < -180 || lon > 180) {
    showToast('Longitude inválida. Use um valor entre −180 e 180.', 'warning'); return;
  }

  await _salvarLocalizacao(lat, lon);
  fecharLocManual();
}

async function _salvarLocalizacao(latitude, longitude) {
  try {
    const atualizado = await apiFetch('/usuarios/me/localizacao', {
      method: 'PATCH',
      body: JSON.stringify({ latitude, longitude }),
    });
    _meCache = { ..._meCache, latitude: atualizado.latitude, longitude: atualizado.longitude };
    _renderStatusLocalizacao(atualizado.latitude, atualizado.longitude);
    showToast('Localização salva com sucesso!', 'success');
  } catch (err) {
    showToast(err.message || 'Erro ao salvar localização.', 'danger');
  }
}

/* ─────────────────────────────────────────
   14. UTILITÁRIOS LOCAIS
   ─────────────────────────────────────── */

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

/** Formata data + hora no padrão brasileiro. */
function formatarDataHora(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

/* ─────────────────────────────────────────
   15. NARRADOR DE QUESTÃO (leitura em voz alta)
   ─────────────────────────────────────── */

/** Lê em voz alta a questão atual: enunciado + todas as alternativas. */
function narrarQuestaoAtual() {
  const q = exam.questoesCache[exam.indiceAtual];
  if (!q) return;
  const num = q.questao_numero || (exam.indiceAtual + 1);
  const trechos = [`Questão ${num}. ${q.enunciado || ''}`];
  if (q.imagem_url) trechos.push('Esta questão tem uma imagem.');

  const letras = ['A', 'B', 'C', 'D', 'E', 'F'];
  (q.alternativas || [])
    .slice()
    .sort((a, b) => (a.ordem ?? 0) - (b.ordem ?? 0))
    .forEach((alt, i) => {
      const letra = letras[i] || (i + 1);
      const txt = (alt.texto || '').trim();
      trechos.push(txt ? `Opção ${letra}. ${txt}` : `Opção ${letra}. Imagem.`);
    });

  Narrador.falar(trechos);
}

/** Lê em voz alta apenas a alternativa do botão clicado (lê do DOM). */
function narrarAlternativaEl(btn) {
  const item = btn.closest('.alternativa-item');
  if (!item) return;
  const letra = (item.querySelector('.alt-letra')?.textContent || '').trim();
  const texto = (item.querySelector('.alt-texto')?.textContent || '').trim();
  Narrador.falar(texto ? `Opção ${letra}. ${texto}` : `Opção ${letra}. Imagem.`);
}

/** Botão único Pausar/Continuar — decide pela label atual. */
function narradorPausarContinuar() {
  const btn = document.getElementById('narrador-pausar');
  if (btn && btn.textContent.includes('Continuar')) Narrador.continuar();
  else Narrador.pausar();
}

/** Define a velocidade e destaca o botão escolhido. */
function narradorSetVeloc(rate, btn) {
  Narrador.setVelocidade(rate);
  document.querySelectorAll('.narrador-veloc-btn').forEach(b => {
    b.classList.remove('ativo');
    b.setAttribute('aria-pressed', 'false');
  });
  if (btn) {
    btn.classList.add('ativo');
    btn.setAttribute('aria-pressed', 'true');
  }
}

/** Atualiza a UI da barra conforme o estado do narrador. */
function narradorAtualizarUI(estado) {
  const pausar = document.getElementById('narrador-pausar');
  const parar  = document.getElementById('narrador-parar');
  if (!pausar || !parar) return;
  const ativo = (estado === 'falando' || estado === 'pausado');
  // sempre visíveis; apenas habilita/desabilita conforme o estado
  pausar.disabled = !ativo;
  parar.disabled  = !ativo;
  const pausado = estado === 'pausado';
  pausar.textContent = pausado ? '▶ Continuar' : '⏸ Pausar';
  pausar.setAttribute('aria-label', pausado ? 'Continuar leitura' : 'Pausar leitura');
}

/** Wrapper para o onclick do botão Parar (Narrador é módulo). */
function narradorParar() {
  Narrador.parar();
}

/** Inicializa a barra do narrador (suporte, estado, velocidade persistida). */
function initNarradorUI() {
  const bar = document.getElementById('narrador-bar');
  if (!bar || !window.Narrador) return;

  if (!Narrador.suportado()) {
    bar.classList.add('narrador-indisponivel');
    bar.innerHTML = '<span class="narrador-aviso">🔇 Seu navegador não suporta leitura em voz.</span>';
    return;
  }

  Narrador.onEstado(narradorAtualizarUI);
  narradorAtualizarUI('parado');

  // reflete a velocidade salva nos botões
  const r = Narrador.getVelocidade();
  document.querySelectorAll('.narrador-veloc-btn').forEach(b => {
    const ativo = Math.abs(parseFloat(b.dataset.rate) - r) < 0.001;
    b.classList.toggle('ativo', ativo);
    b.setAttribute('aria-pressed', ativo ? 'true' : 'false');
  });
}

document.addEventListener('DOMContentLoaded', initNarradorUI);