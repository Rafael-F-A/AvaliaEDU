import { provas, questoes, auth, simulados, certificacoes, locais } from './api.js';

// Funções de exemplo para o dashboard admin.
export const adminApi = {
  async carregarKPIs() {
    // Exemplo: ajuste endpoint conforme backend real.
    const [users, provasList, questoesList] = await Promise.all([
      // apiRequest('/usuarios', 'GET')
      Promise.resolve(null),
      provas.listar(),
      Promise.resolve(null),
    ]);

    return {
      users,
      provasCount: Array.isArray(provasList?.items)
        ? provasList.items.length
        : Array.isArray(provasList)
          ? provasList.length
          : '—',
      questoes: questoesList,
    };
  },
};

