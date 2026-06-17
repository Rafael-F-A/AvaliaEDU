import { provas as apiProvas } from './api.js';

export const provas = {
  listar: apiProvas.listar,
  criar: apiProvas.criar,
  publicar: apiProvas.publicar,
};

