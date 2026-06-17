const API_BASE_URL = 'http://localhost:8000';

function getToken() {
  return localStorage.getItem('token');
}

function safeJsonParse(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export async function apiRequest(endpoint, method = 'GET', body = undefined) {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;

  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const options = {
    method,
    headers,
  };

  if (body !== undefined) {
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(url, options);
  } catch (err) {
    throw new Error(`Falha de rede ao chamar ${method} ${endpoint}: ${err.message}`);
  }

  const text = await response.text();
  const data = text ? safeJsonParse(text) : null;

  if (response.ok) return data;

  if (response.status === 401) {
    // Token expirado/ inválido
    localStorage.removeItem('token');
    window.location.href = './tela_login.html';
    const error = new Error('Sessão expirada. Redirecionando para login...');
    error.status = 401;
    error.data = data;
    throw error;
  }

  // Normaliza erro para facilitar debug
  const message =
    (data && (data.detail || data.message || data.error)) ||
    `HTTP ${response.status} ao chamar ${method} ${endpoint}`;

  const error = new Error(message);
  error.status = response.status;
  error.data = data;

  if (response.status === 403) {
    // Forbidden - manter mensagem clara
    console.warn('Acesso negado (403).');
  }

  if (response.status >= 500) {
    console.error('Erro do servidor (5xx).');
  }

  throw error;
}

// auth
export const auth = {
  async login(email, senha) {
    return apiRequest('/login', 'POST', { email, senha });
  },

  async register(dados) {
    return apiRequest('/register', 'POST', dados);
  },
};

// provas 
export const provas = {
  async listar(filtros = {}) {
    const qs = new URLSearchParams(filtros).toString();
    return apiRequest(`/provas${qs ? `?${qs}` : ''}`, 'GET');
  },

  async criar(dados) {
    return apiRequest('/provas', 'POST', dados);
  },

  async publicar(id) {
    return apiRequest(`/provas/${id}/publicar`, 'POST');
  },
};

// Questoes
export const questoes = {
  async listar(provaId) {
    return apiRequest(`/provas/${provaId}/questoes`, 'GET');
  },

  async criar(dados) {
    return apiRequest('/questoes', 'POST', dados);
  },
};

// simulados 
export const simulados = {
  async iniciar(provaId) {
    return apiRequest(`/provas/${provaId}/simulados/iniciar`, 'POST');
  },

  async responder(tentativaId, questaoId, alternativaId) {
    return apiRequest(`/tentativas/${tentativaId}/questoes/${questaoId}/responder`, 'POST', {
      alternativa_id: alternativaId,
    });
  },

  async resultado(tentativaId) {
    return apiRequest(`/tentativas/${tentativaId}/resultado`, 'GET');
  },
};

// certificações
export const certificacoes = {
  async solicitar(provaId) {
    return apiRequest(`/provas/${provaId}/certificacoes/solicitar`, 'POST');
  },

  async iniciar(tentativaId) {
    return apiRequest(`/tentativas/${tentativaId}/certificacoes/iniciar`, 'POST');
  },

  async responder(...args) {
    // Ajuste a rota conforme o backend.
    // Ex: certificacoes.responder(tentativaId, questaoId, alternativaId)
    const [tentativaId, questaoId, alternativaId] = args;
    return apiRequest(`/tentativas/${tentativaId}/questoes/${questaoId}/certificar`, 'POST', {
      alternativa_id: alternativaId,
    });
  },

  async gerarCertificado(tentativaId) {
    return apiRequest(`/tentativas/${tentativaId}/certificados/gerar`, 'POST');
  },
};

//  locais 
export const locais = {
  async listar() {
    return apiRequest('/locais', 'GET');
  },

  async proximos(lat, lon) {
    return apiRequest(`/locais?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`, 'GET');
  },

  async reservar(localId, provaId) {
    return apiRequest(`/locais/${localId}/reservar`, 'POST', { prova_id: provaId });
  },
};

