/* Texto na mesma largura da imagem que vem antes dele.

   Numa matéria ou página de conteúdo, depois de uma imagem sozinha na linha
   (Média, Grande, em pixels…), o texto, os títulos e as listas que vêm abaixo
   ficam com a mesma largura e a mesma posição dela, como nos portais de notícia.
   Imagem em largura total não limita nada, e uma nova imagem passa a valer para
   o que vem depois. Colunas e imagens com texto ao lado ficam como estão. */
(function () {
  'use strict';
  var MARCA = 'data-alinhado', MINIMA = 280;   // imagem mais estreita que isso não estreita o texto

  /* Parágrafo que só tem imagens (uma ou várias, lado a lado): devolve a lista delas. */
  function soImagens(no) {
    if (no.tagName === 'IMG') return [no];
    if (!/^(P|DIV|FIGURE|A)$/.test(no.tagName)) return null;
    var imgs = no.querySelectorAll('img');
    if (!imgs.length) return null;
    var resto = no.cloneNode(true);
    resto.querySelectorAll('img,br').forEach(function (x) { x.remove(); });
    return resto.textContent.trim() ? null : [].slice.call(imgs);
  }
  function flutua(img) { return /^(left|right)$/.test(getComputedStyle(img).cssFloat); }
  function limpa(no) {
    no.querySelectorAll('[' + MARCA + ']').forEach(function (x) {
      x.style.removeProperty('max-width'); x.style.removeProperty('margin-left'); x.removeAttribute(MARCA);
      if (!x.getAttribute('style')) x.removeAttribute('style');
    });
  }
  function aplica(f, ctx) {
    // posição da borda da imagem em relação à área de conteúdo do elemento que guarda o bloco
    var pai = f.parentNode, cs = getComputedStyle(pai), pr = pai.getBoundingClientRect();
    var base = pr.left + pai.clientLeft + (parseFloat(cs.paddingLeft) || 0);
    var x = Math.max(0, Math.round(ctx.esq - base));
    // listas já têm o recuo dos marcadores; ele continua dentro da largura da imagem
    var recuo = /^(UL|OL)$/.test(f.tagName) ? (parseFloat(getComputedStyle(f).marginLeft) || 0) : 0;
    f.style.maxWidth = (ctx.w - recuo) + 'px'; f.style.marginLeft = (x + recuo) + 'px'; f.setAttribute(MARCA, '1');
  }
  /* Faixa ocupada por um grupo de imagens. Largura total ou estreita demais não limita o texto. */
  function contexto(imgs, cont) {
    var esq = Infinity, dir = -Infinity, c = cont.getBoundingClientRect();
    for (var i = 0; i < imgs.length; i++) {
      if (flutua(imgs[i])) return undefined;                      // texto ao lado: não mexe
      var r = imgs[i].getBoundingClientRect();
      if (!r.width) return null;
      esq = Math.min(esq, r.left); dir = Math.max(dir, r.right);
    }
    var w = dir - esq;
    if (w >= c.width - 4 || w < MINIMA) return null;
    return {w: Math.round(w), esq: esq};
  }

  function alinhaCorpo(cont) {
    limpa(cont);
    if (window.innerWidth <= 560) return;
    var itens = [].slice.call(cont.children).map(function (f) {
      if (f.classList.contains('cols')) return {f: f, cols: true};
      var imgs = soImagens(f);
      return imgs ? {f: f, ctx: contexto(imgs, cont)} : {f: f, texto: !f.querySelector('img')};
    });
    // texto em cima da primeira imagem também acompanha a largura dela
    var ctx = null;
    for (var i = 0; i < itens.length; i++) { if (itens[i].cols) break; if (itens[i].ctx !== undefined && !itens[i].texto) { ctx = itens[i].ctx; break; } }
    itens.forEach(function (it) {
      if (it.cols) { ctx = null; return; }
      if (it.ctx !== undefined && !it.texto) { ctx = it.ctx; return; }
      if (ctx && it.texto) aplica(it.f, ctx);
    });
  }
  function alinhaBlocos(cont) {
    limpa(cont);
    if (window.innerWidth <= 560) return;
    var itens = [].slice.call(cont.children).filter(function (f) { return f.classList.contains('pagina-imagens') || f.classList.contains('bl'); })
      .map(function (f) {
        if (f.classList.contains('bl')) return {f: f, texto: true};
        var figs = [].slice.call(f.querySelectorAll('.pi img'));
        return {f: f, ctx: figs.length ? contexto(figs, cont) : null};
      });
    var ctx = null;
    for (var i = 0; i < itens.length; i++) { if (!itens[i].texto) { ctx = itens[i].ctx || null; break; } }
    itens.forEach(function (it) {
      if (!it.texto) { ctx = it.ctx || null; return; }
      if (ctx) aplica(it.f, ctx);
    });
  }
  window.AlinhaTexto = {corpo: alinhaCorpo, blocos: alinhaBlocos, limpa: limpa};

  function prepara(cont, fn) {
    var pendente = false;
    function agenda() { if (pendente) return; pendente = true; requestAnimationFrame(function () { pendente = false; fn(cont); }); }
    cont.querySelectorAll('img').forEach(function (i) { if (!i.complete) i.addEventListener('load', agenda); });
    if (window.ResizeObserver) new ResizeObserver(agenda).observe(cont); else window.addEventListener('resize', agenda);
    fn(cont);
  }
  function inicia() {
    document.querySelectorAll('.noticia-corpo').forEach(function (c) { prepara(c, alinhaCorpo); });
    var pg = document.querySelector('main.pagina-conteudo:not(.pagina-materia):not(.editavel)');
    if (pg) prepara(pg, alinhaBlocos);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', inicia); else inicia();
})();
