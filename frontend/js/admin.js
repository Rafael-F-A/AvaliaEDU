 // Deixar o dashboard integrar com a API futuramente.
(function () {
  document.addEventListener('DOMContentLoaded', () => {
    // substituir '—' por dados reais.
    const ids = ['kpi-users', 'kpi-provas', 'kpi-questoes', 'kpi-activity'];
    ids.forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      if (el.textContent.trim() === '' || el.textContent.trim() === '—') {
        el.textContent = '—';
      }
    });
  });
})();

