import { questoes as apiQuestoes } from './api.js';

export const questoes = {
  listar: apiQuestoes.listar,
  criar: apiQuestoes.criar,
};

