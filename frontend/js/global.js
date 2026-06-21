/* ============================================================
   AvaliaEdu — global.js
   Comunicação com backend, auth, toast, loading e utilitários
   Usado por: dashboard-admin.html e dashboard-aluno.html
   ============================================================ */

/* ─────────────────────────────────────────
   1. CONFIGURAÇÃO
   ─────────────────────────────────────── */

/** URL base da API. Altere para a URL de produção quando publicar. */
const API_BASE = (['localhost', '127.0.0.1'].includes(location.hostname)) ? 'http://localhost:8000' : 'https://avaliaedu-api.onrender.com';

/** Chave usada no localStorage para o token JWT */
const TOKEN_KEY   = 'avaliaedu_token';
/** Chave usada no localStorage para os dados do usuário */
const USUARIO_KEY = 'avaliaedu_usuario';

/* ─────────────────────────────────────────
   2. GERENCIAMENTO DE TOKEN / SESSÃO
   ─────────────────────────────────────── */

/**
 * Salva o token e os dados do usuário após login bem-sucedido.
 * @param {string} token  – JWT recebido da API
 * @param {object} usuario – Objeto com id, nome, email, perfil, etc.
 */
function salvarSessao(token, usuario) {
  localStorage.setItem(TOKEN_KEY,   token);
  localStorage.setItem(USUARIO_KEY, JSON.stringify(usuario));
}

/** Retorna o JWT armazenado ou null se não houver sessão. */
function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

/**
 * Retorna o objeto do usuário logado ou null.
 * @returns {{ id, nome, email, perfil, nivel, serie, status } | null}
 */
function getUsuario() {
  const raw = localStorage.getItem(USUARIO_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

/** Remove token e dados da sessão (logout). */
function limparSessao() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USUARIO_KEY);
}

/**
 * Faz logout: limpa sessão e redireciona para a raiz.
 * Chamado pelo botão "Sair" da sidebar.
 */
function logout() {
  limparSessao();
  window.location.href = '/';
}

/* ─────────────────────────────────────────
   3. GUARDA DE AUTENTICAÇÃO
   ─────────────────────────────────────── */

/**
 * Garante que o usuário esteja autenticado e com o perfil correto.
 * Se não estiver, redireciona para a landing page.
 *
 * @param {'ADMIN'|'ALUNO'|null} perfilEsperado
 *   Passe 'ADMIN' ou 'ALUNO' para restringir por perfil.
 *   Passe null para exigir apenas que esteja logado.
 *
 * @returns {object} O objeto do usuário logado.
 *
 * @example
 *   // No início de dashboard-admin.html:
 *   const usuario = requireAuth('ADMIN');
 */
function requireAuth(perfilEsperado = null) {
  const token   = getToken();
  const usuario = getUsuario();

  if (!token || !usuario) {
    window.location.href = '/';
    return null;
  }

  if (perfilEsperado && usuario.perfil !== perfilEsperado) {
    // Redireciona para o dashboard correto em vez de expulsar
    if (usuario.perfil === 'ADMIN') {
      window.location.href = '/dashboard-admin.html';
    } else {
      window.location.href = '/dashboard-aluno.html';
    }
    return null;
  }

  return usuario;
}

/* ─────────────────────────────────────────
   4. FETCH AUTENTICADO
   ─────────────────────────────────────── */

/**
 * Wrapper de fetch que injeta automaticamente o header Authorization.
 * Em caso de 401 (token expirado), faz logout e redireciona.
 *
 * @param {string} endpoint – Caminho relativo da API, ex: '/provas'
 * @param {RequestInit} options – Opções do fetch (method, body, etc.)
 * @returns {Promise<any>} – JSON da resposta ou lança erro com .detail
 *
 * @example
 *   const provas = await apiFetch('/provas?status=PUBLICADA');
 *   const nova = await apiFetch('/provas', {
 *     method: 'POST',
 *     body: JSON.stringify({ titulo: 'Simulado Maio', ... })
 *   });
 */
async function apiFetch(endpoint, options = {}) {
  const token = getToken();

  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  // Remover Content-Type para uploads multipart (FormData)
  if (options.body instanceof FormData) {
    delete headers['Content-Type'];
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  // Token expirado ou inválido → desloga
  if (response.status === 401) {
    limparSessao();
    window.location.href = '/';
    return;
  }

  // Sem conteúdo (204 Delete, etc.)
  if (response.status === 204) return null;

  const data = await response.json();

  if (!response.ok) {
    const mensagem = data?.detail || `Erro ${response.status}`;
    throw new Error(typeof mensagem === 'string' ? mensagem : JSON.stringify(mensagem));
  }

  return data;
}

/* ─────────────────────────────────────────
   5. TOAST NOTIFICATIONS
   ─────────────────────────────────────── */

/**
 * Exibe uma notificação flutuante no canto inferior direito.
 *
 * @param {string} mensagem  – Texto a exibir
 * @param {'success'|'danger'|'warning'|'info'} tipo – Cor do toast
 * @param {number} duracao   – Milissegundos antes de sumir (padrão 3500)
 *
 * @example
 *   showToast('Prova salva com sucesso!', 'success');
 *   showToast('Falha ao excluir.', 'danger');
 */
function showToast(mensagem, tipo = 'info', duracao = 3500) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const icones = {
    success: '✓',
    danger:  '✕',
    warning: '⚠',
    info:    'ℹ',
  };

  const toast = document.createElement('div');
  toast.className = `toast ${tipo}`;
  toast.innerHTML = `
    <span class="toast-icon">${icones[tipo] || 'ℹ'}</span>
    <span class="toast-msg">${mensagem}</span>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, duracao);
}

/* ─────────────────────────────────────────
   6. LOADING OVERLAY
   ─────────────────────────────────────── */

/**
 * Exibe ou esconde o overlay de carregamento global.
 * @param {boolean} visivel
 *
 * @example
 *   setLoading(true);
 *   await apiFetch('/provas');
 *   setLoading(false);
 */
function setLoading(visivel) {
  let overlay = document.getElementById('loading-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'loading-overlay';
    overlay.innerHTML = '<div class="spinner"></div>';
    document.body.appendChild(overlay);
  }
  overlay.classList.toggle('show', visivel);
}

/* ─────────────────────────────────────────
   7. MODAL
   ─────────────────────────────────────── */

/**
 * Abre um modal pelo seu ID.
 * @param {string} modalId – ID do elemento .modal-overlay
 */
function openModal(modalId) {
  const el = document.getElementById(modalId);
  if (el) el.classList.add('open');
}

/**
 * Fecha um modal pelo seu ID.
 * @param {string} modalId
 */
function closeModal(modalId) {
  const el = document.getElementById(modalId);
  if (el) el.classList.remove('open');
}

/** Fecha o modal ao clicar fora (no overlay escuro). */
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('open');
  }
});

/** Fecha qualquer modal com [data-close-modal]. */
document.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-close-modal]');
  if (btn) {
    const modalId = btn.dataset.closeModal;
    closeModal(modalId);
  }
});

/* ─────────────────────────────────────────
   8. FORMATAÇÃO DE DADOS
   ─────────────────────────────────────── */

/**
 * Formata uma string ISO de data para pt-BR (DD/MM/AAAA).
 * @param {string|null} iso
 * @returns {string}
 */
function formatarData(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleDateString('pt-BR');
}

/**
 * Formata data e hora para pt-BR (DD/MM/AAAA HH:mm).
 */
function formatarDataHora(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

/**
 * Formata uma nota numérica para exibição com 1 decimal.
 * @param {number|null} nota
 */
function formatarNota(nota) {
  if (nota === null || nota === undefined) return '—';
  return Number(nota).toFixed(1);
}

/**
 * Retorna as iniciais de um nome para o avatar.
 * @param {string} nome
 * @returns {string} Ex: "João Silva" → "JS"
 */
function iniciais(nome) {
  if (!nome) return '?';
  return nome.trim().split(/\s+/).slice(0, 2).map(p => p[0]).join('').toUpperCase();
}

/**
 * Delay simples (await esperar(500)).
 * @param {number} ms
 */
function esperar(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Debounce: executa fn após ms de inatividade.
 * Útil para campos de busca.
 * @param {Function} fn
 * @param {number} ms
 */
function debounce(fn, ms = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

/* ─────────────────────────────────────────
   9. HELPERS DE HTML (BADGES, ETC.)
   ─────────────────────────────────────── */

/**
 * Retorna o HTML de um badge de status de usuário.
 * @param {'ATIVO'|'BLOQUEADO'} status
 */
function badgeStatusUsuario(status) {
  const map = {
    ATIVO:      { cls: 'badge-ativo',    label: 'Ativo' },
    BLOQUEADO:  { cls: 'badge-bloqueado', label: 'Bloqueado' },
  };
  const b = map[status] || { cls: 'badge-warning', label: status };
  return `<span class="badge ${b.cls}">${b.label}</span>`;
}

/**
 * Retorna o HTML de um badge de status de prova.
 * @param {'RASCUNHO'|'PUBLICADA'} status
 */
function badgeStatusProva(status) {
  const map = {
    RASCUNHO:  { cls: 'badge-rascunho',  label: 'Rascunho' },
    PUBLICADA: { cls: 'badge-publicada', label: 'Publicada' },
  };
  const b = map[status] || { cls: 'badge-warning', label: status };
  return `<span class="badge ${b.cls}">${b.label}</span>`;
}

/**
 * Retorna o HTML de um badge de tipo de prova.
 * @param {'SIMULADO'|'CERTIFICACAO'} tipo
 */
function badgeTipoProva(tipo) {
  const map = {
    SIMULADO:     { cls: 'badge-simulado',     label: 'Simulado' },
    CERTIFICACAO: { cls: 'badge-certificacao', label: 'Certificação' },
  };
  const b = map[tipo] || { cls: 'badge-info', label: tipo };
  return `<span class="badge ${b.cls}">${b.label}</span>`;
}

/**
 * Retorna o HTML de um badge de resultado.
 * @param {'APROVADO'|'REPROVADO'} resultado
 */
function badgeResultado(resultado) {
  const map = {
    APROVADO:  { cls: 'badge-aprovado',  label: 'Aprovado' },
    REPROVADO: { cls: 'badge-reprovado', label: 'Reprovado' },
  };
  const b = map[resultado] || { cls: 'badge-warning', label: resultado || '—' };
  return `<span class="badge ${b.cls}">${b.label}</span>`;
}

/* ─────────────────────────────────────────
   10. INICIALIZAÇÃO DA PÁGINA
   ─────────────────────────────────────── */

/**
 * Inicializa elementos globais da interface:
 * - Preenche o nome do usuário na sidebar
 * - Ativa o item de navegação atual
 * - Conecta o botão de logout
 * - Define o avatar com as iniciais
 *
 * Chame no início do script de cada página, após requireAuth().
 *
 * @param {object} usuario – Objeto retornado por requireAuth()
 *
 * @example
 *   const usuario = requireAuth('ADMIN');
 *   initUI(usuario);
 */
function initUI(usuario) {
  if (!usuario) return;

  // Nome na sidebar
  const elNome = document.getElementById('sidebar-username');
  if (elNome) elNome.textContent = usuario.nome || usuario.email;

  // Avatar com iniciais
  const elAvatar = document.getElementById('user-avatar');
  if (elAvatar) elAvatar.textContent = iniciais(usuario.nome);

  // Botão de logout
  const elLogout = document.getElementById('btn-logout');
  if (elLogout) elLogout.addEventListener('click', logout);

  // Ativa item de nav correspondente à URL atual
  const path = window.location.pathname.split('/').pop() || '/';
  document.querySelectorAll('.sidebar-nav a').forEach(a => {
    const href = a.getAttribute('href') || '';
    if (href && path && href.includes(path)) {
      a.classList.add('active');
    }
  });
}

/* ─────────────────────────────────────────
   11. ROTAS DA API (referência rápida)
   ─────────────────────────────────────── */

/**
 * Objeto com todos os endpoints usados no projeto.
 * Evita strings repetidas espalhadas pelo código.
 *
 * @example
 *   const provas = await apiFetch(API.provas.listar + '?status=PUBLICADA');
 *   const nova = await apiFetch(API.provas.criar, { method:'POST', body: JSON.stringify(dados) });
 */
const API = {
  auth: {
    login:    '/auth/login',
    registro: '/auth/register',
    me:       '/auth/me',
  },
  usuarios: {
    listar:      '/usuarios',
    buscar:      (id)   => `/usuarios/${id}`,
    editar:      (id)   => `/usuarios/${id}`,
    bloquear:    (id)   => `/usuarios/${id}/bloquear`,
    desbloquear: (id)   => `/usuarios/${id}/desbloquear`,
    deletar:     (id)   => `/usuarios/${id}`,
    meuPerfil:   '/usuarios/me/perfil',
  },
  provas: {
    listar:    '/provas',
    criar:     '/provas',
    buscar:    (id) => `/provas/${id}`,
    editar:    (id) => `/provas/${id}`,
    publicar:  (id) => `/provas/${id}/publicar`,
    deletar:   (id) => `/provas/${id}`,
    disponiveis: '/provas',               // com filtro status=PUBLICADA
  },
  questoes: {
    criar:    '/questoes',
    editar:   (id) => `/questoes/${id}`,
    deletar:  (id) => `/questoes/${id}`,
    listar:   (provaId) => `/questoes?prova_id=${provaId}`,
  },
  simulados: {
    iniciar:        '/simulados',
    responder:      '/simulados/responder',
    questaoAtual:   (id) => `/simulados/${id}/questao_atual`,
    resultado:      (id) => `/simulados/${id}/resultado`,
    historico:      '/simulados/historico',
  },
  certificacoes: {
    solicitar:  '/certificacoes',
    historico:  '/certificacoes/historico',
    download:   (id)     => `/certificacoes/${id}/download`,
    validar:    (codigo) => `/certificacoes/validar/${codigo}`,
  },
  locais: {
    listar:   '/locais',
    criar:    '/locais',
    buscar:   (id) => `/locais/${id}`,
    editar:   (id) => `/locais/${id}`,
    deletar:  (id) => `/locais/${id}`,
    proximos: '/locais/proximos',
  },
  relatorios: {
    desempenho: '/relatorios/desempenho',
    exportar:   '/relatorios/exportar',
  },
};

/* ─────────────────────────────────────────
   12. EXPORTAÇÕES (para uso em outros scripts)
   ─────────────────────────────────────── */
// Todos os símbolos acima ficam no escopo global (window).
// admin.js, aluno.js e auth.js podem usá-los diretamente.