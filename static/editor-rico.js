/* Editor de texto formatado (contêineres com [data-rico]).

   Barra de formatação, link para páginas do portal, imagem da biblioteca. O
   conteúdo vai para o campo oculto ao enviar o formulário; o servidor limpa o
   HTML antes de guardar (nunca confie só no navegador). */
(function () {
  'use strict';
  document.querySelectorAll('[data-rico]').forEach(function (raiz) {
    var area = raiz.querySelector('.re-area');
    var oculto = raiz.querySelector('input[type=hidden]');
    var form = raiz.closest('form');
    try { document.execCommand('defaultParagraphSeparator', false, 'p'); document.execCommand('styleWithCSS', false, false); } catch (e) {}

    var salva = null;
    /* Imagem nova entra na largura da coluna de texto, como nos portais de notícia; depois dá para arrastar as alças. */
    function classeNova() { return 'im-c'; }
    document.addEventListener('selectionchange', function () {
      var s = window.getSelection();
      if (s.rangeCount && area.contains(s.anchorNode)) salva = s.getRangeAt(0).cloneRange();
    });
    function comando(c, v) {
      area.focus();
      if (salva) { var s = window.getSelection(); s.removeAllRanges(); s.addRange(salva); }
      document.execCommand(c, false, v || null);
    }
    raiz.querySelectorAll('[data-cmd]').forEach(function (b) {
      b.addEventListener('mousedown', function (e) { e.preventDefault(); });
      b.addEventListener('click', function () {
        var c = b.dataset.cmd, v = b.dataset.val;
        if (c === 'formatBlock') { comando(c, '<' + v + '>'); return; }
        if (c === 'createLink') {
          var u = window.prompt('Endereço do link (https://... ou /pagina):', 'https://');
          if (!u || u === 'https://') return; comando(c, u); return;
        }
        comando(c, v);
      });
    });
    var cor = raiz.querySelector('.re-cor-campo');
    if (cor) cor.addEventListener('input', function () { comando('foreColor', cor.value); });
    var tam = raiz.querySelector('.re-tam');
    if (tam) tam.addEventListener('change', function () { if (tam.value) comando('fontSize', tam.value); tam.value = ''; });
    var pag = raiz.querySelector('.re-pag');
    if (pag) pag.addEventListener('change', function () { if (pag.value) comando('createLink', pag.value); pag.value = ''; });

    var img = raiz.querySelector('[data-img]');
    if (img && window.SeletorMidia) {
      img.addEventListener('mousedown', function (e) { e.preventDefault(); });
      img.addEventListener('click', function () {
        window.SeletorMidia.abrir({
          lista: raiz.dataset.lista, enviar: raiz.dataset.enviar, csrf: raiz.dataset.csrf,
          aoEscolher: function (i) {
            area.focus();
            if (salva) { var s = window.getSelection(); s.removeAllRanges(); s.addRange(salva); }
            var alt = window.prompt('Texto alternativo da imagem (descreve a imagem para quem não a enxerga):', i.alt || '') || '';
            var h = '<img class="' + classeNova() + '" src="' + i.url + '" alt="' + alt.replace(/"/g, '&quot;') + '">';
            document.execCommand('insertHTML', false, h);
            depoisDeInserir(i.url);
          }
        });
      });
    }

    /* ── arrastar ou colar uma imagem do computador direto no texto ── */
    var aviso = document.createElement('p'); aviso.className = 're-aviso'; aviso.hidden = true;
    area.parentNode.insertBefore(aviso, area.nextSibling);
    function envia(arquivo, ponto) {
      if (!/^image\//.test(arquivo.type)) { aviso.textContent = 'Só imagens (PNG, JPG, WEBP ou GIF) podem ser colocadas no texto.'; aviso.hidden = false; return; }
      aviso.textContent = 'Enviando ' + (arquivo.name || 'imagem') + '…'; aviso.hidden = false;
      var fd = new FormData(); fd.set('csrf', raiz.dataset.csrf); fd.set('arquivo', arquivo, arquivo.name || 'imagem.png');
      fetch(raiz.dataset.enviar, {method: 'POST', body: fd, credentials: 'same-origin'})
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (!d.ok) { aviso.textContent = d.erro || 'Não foi possível enviar a imagem.'; return; }
          area.focus();
          var s = window.getSelection();
          if (ponto && document.caretRangeFromPoint) {
            var r = document.caretRangeFromPoint(ponto.x, ponto.y);
            if (r && area.contains(r.startContainer)) { s.removeAllRanges(); s.addRange(r); }
          } else if (salva) { s.removeAllRanges(); s.addRange(salva); }
          var alt = (d.item.nome || '').replace(/\.[^.]+$/, '').replace(/[<>"&]/g, '');
          document.execCommand('insertHTML', false, '<img class="' + classeNova() + '" src="' + d.item.url + '" alt="' + alt + '">');
          aviso.hidden = true;
          depoisDeInserir(d.item.url);
        })
        .catch(function () { aviso.textContent = 'Sem conexão com o servidor.'; });
    }
    function imagens(lista) { return Array.prototype.filter.call(lista || [], function (f) { return f && /^image\//.test(f.type); }); }
    area.addEventListener('dragover', function (e) {
      if (e.dataTransfer && Array.prototype.indexOf.call(e.dataTransfer.types || [], 'Files') >= 0) { e.preventDefault(); area.classList.add('re-sobre'); }
    });
    area.addEventListener('dragleave', function () { area.classList.remove('re-sobre'); });
    area.addEventListener('drop', function (e) {
      area.classList.remove('re-sobre');
      var fs = e.dataTransfer && e.dataTransfer.files;
      if (!fs || !fs.length) return;
      e.preventDefault();
      Array.prototype.forEach.call(fs, function (f) { envia(f, {x: e.clientX, y: e.clientY}); });
    });
    area.addEventListener('paste', function (e) {
      var fs = imagens((e.clipboardData || {}).files);
      if (!fs.length) return;
      e.preventDefault();
      fs.forEach(function (f) { envia(f, null); });
    });

    /* ── imagem no texto: clique para mudar tamanho, posição, descrição ── */
    var TAM = [['im-p', 'Pequena'], ['im-m', 'Média'], ['im-g', 'Grande'], ['im-c', 'Largura total']];
    var POS = [['im-esq', 'À esquerda, texto ao lado'], ['im-dir', 'À direita, texto ao lado'],
               ['im-bloco', 'Sozinha à esquerda'], ['im-centro', 'Sozinha no centro'], ['im-bloco-dir', 'Sozinha à direita']];
    var barra = document.createElement('div'); barra.className = 're-img-barra'; barra.hidden = true;
    var atual = null;
    function botao(txt, fn, cls) {
      var b = document.createElement('button'); b.type = 'button'; b.textContent = txt; if (cls) b.className = cls;
      b.addEventListener('mousedown', function (e) { e.preventDefault(); });
      b.addEventListener('click', fn); barra.appendChild(b); return b;
    }
    function troca(grupo, cls) {
      if (!atual) return;
      grupo.forEach(function (g) { atual.classList.remove(g[0]); });
      if (cls) atual.classList.add(cls);
      if (grupo === TAM) { atual.style.removeProperty('width'); atual.removeAttribute('data-w'); if (!atual.getAttribute('style')) atual.removeAttribute('style'); }
      marca(); posicionaAlca();
    }
    function marca() {
      if (typeof larg !== 'undefined' && larg !== document.activeElement) larg.value = atual ? Math.round(atual.getBoundingClientRect().width) : '';
      barra.querySelectorAll('button[data-c]').forEach(function (b) {
        b.classList.toggle('on', !!atual && atual.classList.contains(b.dataset.c));
      });
    }
    function rotulo(t) { var r = document.createElement('span'); r.className = 're-rot'; r.textContent = t; barra.appendChild(r); }
    rotulo('Imagem — tamanho:');
    TAM.forEach(function (t) { botao(t[1], function () { troca(TAM, atual && atual.classList.contains(t[0]) ? '' : t[0]); }).dataset.c = t[0]; });
    barra.appendChild(document.createElement('span')).className = 're-sep';
    rotulo('posição (texto ao lado, ou em cima e embaixo):');
    POS.forEach(function (t) { botao(t[1], function () { troca(POS, atual && atual.classList.contains(t[0]) ? '' : t[0]); }).dataset.c = t[0]; });
    barra.appendChild(document.createElement('span')).className = 're-sep';
    rotulo('largura:');
    var larg = document.createElement('input'); larg.type = 'number'; larg.min = 24; larg.max = 2000; larg.step = 'any'; larg.className = 're-larg'; larg.setAttribute('form', ''); larg.setAttribute('novalidate', '');
    larg.title = 'Largura da imagem em pixels'; larg.setAttribute('aria-label', 'Largura da imagem em pixels');
    barra.appendChild(larg); rotulo('px');
    larg.addEventListener('change', function () {
      var v = parseInt(larg.value, 10);
      if (!atual || isNaN(v)) return;
      v = Math.max(24, Math.min(2000, v));
      TAM.forEach(function (g) { atual.classList.remove(g[0]); });
      atual.style.width = v + 'px'; atual.removeAttribute('data-w');
      marca(); posicionaAlca();
    });
    larg.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); larg.dispatchEvent(new Event('change')); } });
    barra.appendChild(document.createElement('span')).className = 're-sep';
    botao('↑ Subir', function () { mover(-1); });
    botao('↓ Descer', function () { mover(1); });
    botao('Descrição…', function () {
      if (!atual) return;
      var v = window.prompt('Texto alternativo (descreve a imagem para quem não a enxerga):', atual.getAttribute('alt') || '');
      if (v !== null) atual.setAttribute('alt', v);
    });
    botao('Remover', function () { if (atual) { atual.remove(); desmarca(); } }, 'perigo');
    area.parentNode.insertBefore(barra, area);
    function desmarca() {
      if (atual) atual.removeAttribute('data-sel');
      atual = null; barra.hidden = true; alca.hidden = true;
    }
    /* Sobe ou desce a imagem um bloco do texto. */
    function mover(d) {
      if (!atual) return;
      var bloco = atual; while (bloco.parentNode !== area) bloco = bloco.parentNode;
      var so = bloco === atual || (bloco.children.length === 1 && !bloco.textContent.trim());
      var vizinho = d < 0 ? bloco.previousElementSibling : bloco.nextElementSibling;
      if (so) {
        if (!vizinho) return;
        if (d < 0) area.insertBefore(bloco, vizinho); else area.insertBefore(bloco, vizinho.nextSibling);
      } else {
        var p = document.createElement('p'); p.appendChild(atual);
        if (d < 0) area.insertBefore(p, bloco); else area.insertBefore(p, bloco.nextSibling);
      }
      posicionaAlca(); atual.scrollIntoView({block: 'nearest'});
    }
    /* Alças nos quatro cantos da imagem: arraste para esticar ou encolher (proporção mantida).
       O texto abaixo acompanha a largura enquanto se arrasta. */
    var alca = document.createElement('div'); alca.className = 're-alcas'; alca.hidden = true;
    var dica = document.createElement('span'); dica.className = 're-alca-dica'; alca.appendChild(dica);
    ['nw', 'ne', 'sw', 'se'].forEach(function (d) {
      var h = document.createElement('div'); h.className = 're-alca re-alca-' + d; h.dataset.d = d; h.title = 'Arraste para mudar o tamanho da imagem';
      h.addEventListener('pointerdown', arrastaAlca); alca.appendChild(h);
    });
    raiz.style.position = 'relative'; raiz.appendChild(alca);
    function posicionaAlca() {
      if (!atual || !atual.isConnected) { alca.hidden = true; return; }
      var a = atual.getBoundingClientRect(), r = raiz.getBoundingClientRect(), c = area.getBoundingClientRect();
      alca.hidden = !(a.bottom > c.top + 4 && a.top < c.bottom - 4);
      alca.style.left = (a.left - r.left) + 'px'; alca.style.top = (a.top - r.top) + 'px';
      alca.style.width = a.width + 'px'; alca.style.height = a.height + 'px';
    }
    area.addEventListener('scroll', posicionaAlca);
    window.addEventListener('resize', posicionaAlca);
    function arrastaAlca(e) {
      if (!atual) return;
      var h = e.currentTarget; e.preventDefault(); h.setPointerCapture(e.pointerId);
      var sx = h.dataset.d.charAt(1) === 'e' ? 1 : -1, sy = h.dataset.d.charAt(0) === 's' ? 1 : -1;
      var x0 = e.clientX, y0 = e.clientY, a0 = atual.getBoundingClientRect(), w0 = a0.width, prop = a0.width / Math.max(1, a0.height);
      var c0 = area.getBoundingClientRect();
      var centrada = Math.abs((a0.left + a0.right) / 2 - (c0.left + c0.right) / 2) < 8;   // imagem centralizada cresce para os dois lados
      var cs = getComputedStyle(area), limite = area.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      function move(ev) {
        var dx = sx * (ev.clientX - x0), dy = sy * (ev.clientY - y0) * prop;
        var d = Math.abs(dy) > Math.abs(dx) ? dy : dx;
        var px = Math.max(24, Math.min(Math.round(limite), Math.round(w0 + d * (centrada ? 2 : 1))));
        ['im-p', 'im-m', 'im-g', 'im-c'].forEach(function (c) { atual.classList.remove(c); });
        atual.style.width = px + 'px'; atual.removeAttribute('data-w');
        dica.textContent = Math.round(atual.getBoundingClientRect().width) + ' px'; posicionaAlca(); marca();
      }
      function fim() { h.removeEventListener('pointermove', move); h.removeEventListener('pointerup', fim); h.removeEventListener('pointercancel', fim); dica.textContent = ''; }
      h.addEventListener('pointermove', move); h.addEventListener('pointerup', fim); h.addEventListener('pointercancel', fim);
    }

    /* O texto acompanha a largura da imagem também aqui no editor (a mesma regra da página publicada). */
    var realinhando = false, obs = null;
    function realinha() {
      if (realinhando || !window.AlinhaTexto) return;
      realinhando = true;
      requestAnimationFrame(function () {
        window.AlinhaTexto.corpo(area, {isola: false}); posicionaAlca();
        if (obs) obs.takeRecords();            // as mudanças feitas pelo próprio alinhamento não disparam outro
        realinhando = false;
      });
    }
    obs = new MutationObserver(function (muts) {
      for (var i = 0; i < muts.length; i++) {
        var m = muts[i];
        if (m.type === 'childList' || (m.target && m.target.tagName === 'IMG')) { realinha(); return; }
      }
    });
    obs.observe(area, {childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'style']});
    if (window.ResizeObserver) new ResizeObserver(realinha).observe(area);   // a janela de edição abre escondida
    area.addEventListener('load', realinha, true);
    window.addEventListener('load', realinha);
    window.addEventListener('resize', realinha);
    function seleciona(img) {
      if (atual && atual !== img) atual.removeAttribute('data-sel');
      atual = img; atual.setAttribute('data-sel', '1'); barra.hidden = false; marca(); posicionaAlca();
    }
    // Imagem nova entra em tamanho médio e já selecionada, com a barra à vista.
    window.__reSelecionaNova = null;
    function depoisDeInserir(url) {
      var todas = area.querySelectorAll('img[src="' + url + '"]');
      if (window.AlinhaTexto) window.AlinhaTexto.isola(area);   // imagem no meio do parágrafo vira bloco próprio
      if (todas.length) seleciona(todas[todas.length - 1]);
    }
    area.addEventListener('click', function (e) {
      if (e.target.tagName === 'IMG') seleciona(e.target); else desmarca();
    });
    document.addEventListener('mousedown', function (e) { if (atual && !raiz.contains(e.target)) desmarca(); });


    /* ── colunas: cada uma começa no topo, texto e imagem em qualquer uma ── */
    var LAYOUTS = {c2: 2, c3: 3, c13: 2, c23: 2, c31: 2};
    function novaCol() { var c = document.createElement('div'); c.className = 'col'; c.innerHTML = '<p><br></p>'; return c; }
    function colunasDoCursor() {
      var s = window.getSelection(), n = (s.rangeCount && area.contains(s.anchorNode)) ? s.anchorNode : (salva && salva.startContainer);
      if (!n) return null;
      if (n.nodeType === 3) n = n.parentNode;
      var c = n.closest ? n.closest('.cols') : null;
      return c && area.contains(c) ? c : null;
    }
    function blocoTopo(n) {
      if (!n) return null;
      while (n && n.parentNode !== area) n = n.parentNode;
      return n || null;
    }
    function ajustaColunas(box, layout) {
      var n = LAYOUTS[layout], cols = [].filter.call(box.children, function (x) { return x.classList.contains('col'); });
      while (cols.length < n) { var c = novaCol(); box.appendChild(c); cols.push(c); }
      while (cols.length > n) {                       // sobrou coluna: o conteúdo vai para a última que fica
        var extra = cols.pop(), alvo = cols[cols.length - 1];
        while (extra.firstChild) alvo.appendChild(extra.firstChild);
        extra.remove();
      }
      Object.keys(LAYOUTS).forEach(function (k) { box.classList.remove(k); });
      box.classList.add(layout);
    }
    function colocaCursor(no) {
      var r = document.createRange(); r.selectNodeContents(no); r.collapse(true);
      var s = window.getSelection(); s.removeAllRanges(); s.addRange(r); salva = r.cloneRange();
    }
    /* Modelo "manchete": foto na coluna da esquerda, título grande e texto ao lado, lista de links embaixo. */
    function inserirManchete() {
      area.focus();
      var box = document.createElement('div'); box.className = 'cols';
      ajustaColunas(box, 'c23');
      var esq = box.children[0], dir = box.children[1];
      dir.innerHTML = '<h2>Título da manchete</h2><p>Texto de apoio, ao lado da imagem.</p>';
      var tinha = atual && atual.isConnected && area.contains(atual) ? atual : null;
      if (tinha) {                                   // a imagem já selecionada vai para a coluna da esquerda
        ['im-p', 'im-m', 'im-g', 'im-esq', 'im-dir', 'im-centro', 'im-bloco', 'im-bloco-dir'].forEach(function (c) { tinha.classList.remove(c); });
        tinha.classList.add('im-c'); tinha.style.removeProperty('width'); tinha.removeAttribute('data-w');
        if (!tinha.getAttribute('style')) tinha.removeAttribute('style');
        var velho = tinha.parentNode, onde = blocoTopo(tinha);
        if (onde) area.insertBefore(box, onde);       // a manchete nasce no lugar onde estava a imagem
        esq.innerHTML = '<p></p>'; esq.firstChild.appendChild(tinha);
        if (velho && velho !== area && !velho.textContent.trim() && !velho.querySelector('img') && /^(P|DIV)$/.test(velho.tagName)) velho.remove();
      }
      var lista = document.createElement('ul');
      lista.innerHTML = '<li>Primeira notícia relacionada</li><li>Segunda notícia relacionada</li><li>Terceira notícia relacionada</li>';
      var ref = tinha ? null : blocoTopo(salva && area.contains(salva.startContainer) ? salva.startContainer : null);
      var existente = colunasDoCursor(); if (existente) ref = existente;
      if (box.parentNode !== area) { if (ref && ref.isConnected) area.insertBefore(box, ref.nextSibling); else area.appendChild(box); }
      area.insertBefore(lista, box.nextSibling);
      if (!lista.nextSibling) { var p = document.createElement('p'); p.innerHTML = '<br>'; area.appendChild(p); }
      var h = dir.firstChild, r = document.createRange(); r.selectNodeContents(h);
      var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r); salva = r.cloneRange();
      if (tinha) seleciona(tinha);
      else { aviso.textContent = 'Agora clique em "+ Imagem" com o cursor na coluna da esquerda, ou arraste uma imagem para ela.'; aviso.hidden = false; setTimeout(function () { aviso.hidden = true; }, 6000); }
      box.scrollIntoView({block: 'nearest'});
    }
    var selCol = raiz.querySelector('.re-col');
    if (selCol) selCol.addEventListener('change', function () {
      var layout = selCol.value; selCol.value = '';
      if (layout === 'manchete') { inserirManchete(); return; }
      if (!LAYOUTS[layout]) return;
      area.focus();
      var existente = colunasDoCursor();
      if (existente) { ajustaColunas(existente, layout); return; }
      var box = document.createElement('div'); box.className = 'cols';
      ajustaColunas(box, layout);
      var ref = blocoTopo(salva && area.contains(salva.startContainer) ? salva.startContainer : null);
      if (ref) area.insertBefore(box, ref.nextSibling); else area.appendChild(box);
      if (!box.nextSibling) { var p = document.createElement('p'); p.innerHTML = '<br>'; area.appendChild(p); }
      colocaCursor(box.firstChild);
      box.scrollIntoView({block: 'nearest'});
    });
    var fimCol = raiz.querySelector('.re-col-fim');
    if (fimCol) {
      fimCol.addEventListener('mousedown', function (e) { e.preventDefault(); });
      fimCol.addEventListener('click', function () {
        area.focus();
        var box = colunasDoCursor();
        if (!box) { aviso.textContent = 'Clique dentro das colunas que quer desfazer.'; aviso.hidden = false; setTimeout(function () { aviso.hidden = true; }, 3000); return; }
        [].slice.call(box.children).forEach(function (c) { while (c.firstChild) box.parentNode.insertBefore(c.firstChild, box); });
        box.remove(); desmarca();
      });
    }

    /* ── arrastar a imagem com o mouse para qualquer lugar do texto ── */
    var arrasto = null, engoleClique = false;
    function pontoNoTexto(x, y, img) {
      var r = null;
      if (document.caretRangeFromPoint) r = document.caretRangeFromPoint(x, y);
      else if (document.caretPositionFromPoint) {
        var cp = document.caretPositionFromPoint(x, y);
        if (cp) { r = document.createRange(); r.setStart(cp.offsetNode, cp.offset); r.collapse(true); }
      }
      var el = document.elementFromPoint(x, y), col = el && el.closest ? el.closest('.col') : null;
      if (col && !area.contains(col)) col = null;
      // Dentro de uma coluna, a imagem sempre cai nessa coluna (mesmo no espaço vazio dela).
      if (col && (!r || !col.contains(r.startContainer))) { r = document.createRange(); r.selectNodeContents(col); r.collapse(false); }
      if (!r || !area.contains(r.startContainer) || img.contains(r.startContainer)) return null;
      return {range: r, col: col};
    }
    function retanguloDe(r) {
      var rs = r.getClientRects(), q = rs.length ? rs[0] : r.getBoundingClientRect();
      if (q && (q.height || q.width)) return q;
      var n = r.startContainer.nodeType === 3 ? r.startContainer.parentNode : r.startContainer;
      return n.getBoundingClientRect();
    }
    area.addEventListener('dragstart', function (e) { if (e.target && e.target.tagName === 'IMG') e.preventDefault(); }, true);
    area.addEventListener('mousedown', function (e) { if (e.target && e.target.tagName === 'IMG') e.target.draggable = false; }, true);
    area.addEventListener('pointerdown', function (e) {
      if (e.button !== 0 || !e.target || e.target.tagName !== 'IMG') return;
      e.target.draggable = false;          // sem isso o navegador inicia o arrasto dele e cancela o nosso
      arrasto = {img: e.target, x0: e.clientX, y0: e.clientY, ativo: false, ghost: null, linha: null, alvo: null};
    });
    document.addEventListener('pointermove', function (e) {
      if (!arrasto) return;
      var a = arrasto;
      if (!a.ativo) {
        if (Math.abs(e.clientX - a.x0) + Math.abs(e.clientY - a.y0) < 6) return;
        a.ativo = true; seleciona(a.img); alca.hidden = true;
        a.ghost = a.img.cloneNode(false); a.ghost.className = 're-fantasma'; a.ghost.removeAttribute('style');
        a.ghost.style.width = Math.min(160, a.img.getBoundingClientRect().width) + 'px';
        a.linha = document.createElement('div'); a.linha.className = 're-soltar'; a.linha.hidden = true;
        document.body.appendChild(a.ghost); document.body.appendChild(a.linha);
        area.classList.add('re-arrastando'); a.img.style.opacity = '.35';
      }
      a.ghost.style.left = (e.clientX + 12) + 'px'; a.ghost.style.top = (e.clientY + 12) + 'px';
      // rolar a área quando o mouse chega perto da borda de cima ou de baixo
      var c = area.getBoundingClientRect();
      if (e.clientY < c.top + 28) area.scrollTop -= 14; else if (e.clientY > c.bottom - 28) area.scrollTop += 14;
      area.querySelectorAll('.re-col-alvo').forEach(function (k) { k.classList.remove('re-col-alvo'); });
      var dentro = e.clientX >= c.left && e.clientX <= c.right && e.clientY >= c.top && e.clientY <= c.bottom;
      var p = dentro ? pontoNoTexto(e.clientX, e.clientY, a.img) : null;
      a.alvo = p;
      if (!p) { a.linha.hidden = true; return; }
      if (p.col) p.col.classList.add('re-col-alvo');
      var q = retanguloDe(p.range);
      a.linha.hidden = false;
      a.linha.style.left = q.left + 'px'; a.linha.style.top = q.top + 'px'; a.linha.style.height = Math.max(18, q.height) + 'px';
    });
    function terminaArrasto(e, cancela) {
      var a = arrasto; arrasto = null;
      if (!a || !a.ativo) return;
      engoleClique = true; setTimeout(function () { engoleClique = false; }, 0);
      a.ghost.remove(); a.linha.remove(); a.img.style.opacity = '';
      if (!a.img.getAttribute('style')) a.img.removeAttribute('style');
      area.classList.remove('re-arrastando');
      area.querySelectorAll('.re-col-alvo').forEach(function (k) { k.classList.remove('re-col-alvo'); });
      if (cancela || !a.alvo) { posicionaAlca(); return; }
      var img = a.img, velho = img.parentNode, r = a.alvo.range;
      r.insertNode(img);                                // move (o nó sai do lugar antigo sozinho)
      // imagem solta direto na área ou na coluna ganha um parágrafo, para dar para escrever ao lado
      if (img.parentNode === area || img.parentNode.classList.contains('col') || img.parentNode.classList.contains('cols')) {
        var p = document.createElement('p'); img.parentNode.insertBefore(p, img); p.appendChild(img);
      }
      // limpa o parágrafo que ficou vazio e garante que a coluna esvaziada continue editável
      if (velho && velho !== img.parentNode && velho.isConnected && velho !== area) {
        var vazio = !velho.textContent.trim() && !velho.querySelector('img');
        if (vazio && /^(P|H2|H3|H4|LI)$/.test(velho.tagName)) { var pai = velho.parentNode; velho.remove(); if (pai && pai.classList && pai.classList.contains('col') && !pai.children.length) pai.appendChild(novaCol().firstChild); }
        else if (vazio && velho.classList && velho.classList.contains('col') && !velho.children.length) velho.appendChild(novaCol().firstChild);
      }
      if (window.AlinhaTexto) window.AlinhaTexto.isola(area);
      seleciona(img); posicionaAlca();
    }
    document.addEventListener('pointerup', function (e) { terminaArrasto(e, false); arrasto = null; });
    document.addEventListener('pointercancel', function (e) { terminaArrasto(e, true); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && arrasto && arrasto.ativo) terminaArrasto(e, true); });
    area.addEventListener('click', function (e) { if (engoleClique) { e.stopImmediatePropagation(); e.preventDefault(); } }, true);

    if (form) form.addEventListener('submit', function (e) {
      if (atual) atual.removeAttribute('data-sel');
      if (window.AlinhaTexto) { window.AlinhaTexto.limpa(area); window.AlinhaTexto.isola(area); }
      oculto.value = area.innerHTML;
      setTimeout(realinha, 0);
    });
  });
})();
