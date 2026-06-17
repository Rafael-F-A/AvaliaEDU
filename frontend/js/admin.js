import { apiRequest, provas, questoes } from './api.js';

function setText(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = value;
}

document.addEventListener('DOMContentLoaded', async () => {
  // Placeholder: enquanto endpoints reais de KPI não existem/ não mapear.
  // Mantém '—' mas já deixa pronto para integração via apiRequest.
  setText('kpi-users', '—');
  setText('kpi-provas', '—');
  setText('kpi-questoes', '—');
  setText('kpi-activity', '—');
});


