/* Layout livre — só para o administrador.
   O painel é um quadro de 12 colunas com linhas de 1,5rem. Em "Editar layout"
   cada cartão pode ser arrastado (mover) ou puxado pelo canto (tamanho). A
   malha e as linhas verdes mostram o alinhamento com os outros cartões e, ao
   soltar o mouse, a posição é salva.

   Três modos de encaixe (seletor "Encaixe"):
     Grade  — o cartão salta de célula em célula (como sempre foi);
     Fino   — anda de 8 em 8 pixels;
     Livre  — anda de 1 em 1 pixel.
   Nos dois últimos a posição é "célula + deslocamento em pixels" (fx, fy, fw,
   fh), e o "Ímã nos vizinhos" gruda o cartão na borda dos outros quando chega
   perto (Alt desliga). "Permitir sobrepor" deixa um cartão ficar sobre outro; o
   último movido fica na frente. Sem sobrepor, um cartão que invadiria outro
   volta para onde estava. */
(function () {
  var tela = document.querySelector('[data-livre]');
  if (!tela) return;
  var NCOL = 12, ALT_MIN = 4, TOL = 8;
  var btn = document.querySelector('[data-livre-editar]');
  var ajuda = document.querySelector('[data-livre-ajuda]');
  var btnAjustar = document.querySelector('[data-livre-ajustar]');
  var chkSobrepor = document.querySelector('[data-livre-sobrepor]');
  var selEnc = document.querySelector('[data-livre-encaixe]');
  var chkIma = document.querySelector('[data-livre-ima]');
  var editando = false, malha = null;
  var sobrepor = false, enc = 'grade', ima = true;
  try {
    sobrepor = localStorage.getItem('portal-livre-sobrepor') === '1';
    enc = localStorage.getItem('portal-livre-encaixe') || 'grade';
    ima = localStorage.getItem('portal-livre-ima') !== '0';
  } catch (_) {}
  if (['grade', '8', '1'].indexOf(enc) < 0) enc = 'grade';
  if (chkSobrepor) chkSobrepor.checked = sobrepor;
  if (selEnc) selEnc.value = enc;
  if (chkIma) chkIma.checked = ima;

  function cartoes() {
    return [].slice.call(tela.querySelectorAll(':scope > .cartao[data-chave]'));
  }
  var K = ['gx', 'gy', 'gw', 'gh', 'fx', 'fy', 'fw', 'fh'];
  function pos(c) {
    var p = {};
    K.forEach(function (k) { p[k] = +c.dataset[k] || 0; });
    return p;
  }
  function fino(p) { return !!(p.fx || p.fy || p.fw || p.fh); }

  /* medidas do quadro */
  function gap() { return parseFloat(getComputedStyle(tela).columnGap) || 0; }
  function linha() { return parseFloat(getComputedStyle(tela).gridAutoRows) || 24; }
  function mb() {
    var c = cartoes()[0];
    return c ? (parseFloat(getComputedStyle(c).marginBottom) || 0) : 14.4;
  }
  function passo() {
    var r = tela.getBoundingClientRect(), g = gap();
    return (r.width - g * (NCOL - 1)) / NCOL + g;
  }
  /* posição em pixels = célula da grade + deslocamento fino */
  function rectDe(p) {
    var ps = passo(), L = linha(), g = gap(), m = mb();
    return { x: p.gx * ps + p.fx, y: p.gy * L + p.fy,
             w: p.gw * ps - g + p.fw, h: p.gh * L - m + p.fh };
  }
  function deRect(r) {
    var ps = passo(), L = linha(), g = gap(), m = mb();
    var gx = Math.max(0, Math.min(NCOL - 1, Math.round(r.x / ps)));
    var gy = Math.max(0, Math.round(r.y / L));
    var gw = Math.max(1, Math.min(NCOL - gx, Math.round((r.w + g) / ps)));
    var gh = Math.max(ALT_MIN, Math.round((r.h + m) / L));
    return { gx: gx, gy: gy, gw: gw, gh: gh,
             fx: Math.round(r.x - gx * ps), fy: Math.round(r.y - gy * L),
             fw: Math.round(r.w - (gw * ps - g)), fh: Math.round(r.h - (gh * L - m)) };
  }
  function etiqueta(c) {
    var e = c.querySelector('.livre-etiqueta'), p = pos(c);
    if (!e) return;
    if (fino(p)) { var r = rectDe(p); e.textContent = Math.round(r.w) + ' × ' + Math.round(r.h) + ' px'; }
    else e.textContent = p.gw + ' × ' + p.gh;
  }
  function aplica(c, p) {
    K.forEach(function (k) { c.dataset[k] = p[k] || 0; });
    c.style.gridColumn = (p.gx + 1) + ' / span ' + p.gw;
    c.style.gridRow = (p.gy + 1) + ' / span ' + p.gh;
    if (fino(p)) {
      c.setAttribute('data-fino', '');
      ['fx', 'fy', 'fw', 'fh'].forEach(function (k) { c.style.setProperty('--' + k, p[k] || 0); });
    } else {
      c.removeAttribute('data-fino');
      ['fx', 'fy', 'fw', 'fh'].forEach(function (k) { c.style.removeProperty('--' + k); });
    }
    etiqueta(c);
  }

  /* colisão em pixels: cartões encostados ou com folga não colidem */
  function choca(p, ignorar) {
    var a = rectDe(p);
    return cartoes().some(function (o) {
      if (o === ignorar) return false;
      var b = rectDe(pos(o));
      return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
    });
  }
  function bate(p, ignorar) { return !sobrepor && choca(p, ignorar); }
  function topoZ() {
    return cartoes().reduce(function (m, o) { return Math.max(m, +o.dataset.gz || 0); }, 0);
  }
  function traz(c, z) {
    var n = (z === undefined) ? topoZ() + 1 : z;
    c.dataset.gz = n;
    if (n) c.style.setProperty('--z', n + 1); else c.style.removeProperty('--z');
  }

  function aviso(texto) {
    var a = document.createElement('div');
    a.className = 'livre-aviso'; a.textContent = texto;
    document.body.appendChild(a);
    setTimeout(function () { a.remove(); }, 2800);
  }
  function salva(lista) {
    var f = new FormData();
    f.set('csrf', tela.dataset.csrf);
    f.set('posicoes', JSON.stringify(lista));
    // No encaixe fino a colisão já foi conferida aqui, em pixels; o servidor só
    // enxerga células e recusaria posições válidas.
    f.set('sobrepor', (sobrepor || enc !== 'grade') ? '1' : '0');
    return fetch(tela.dataset.salvar, { method: 'POST', body: f, credentials: 'same-origin' })
      .then(function (r) {
        return r.json().catch(function () { return { ok: false, erro: 'Erro ao salvar.' }; });
      }, function () { return { ok: false, erro: 'Sem conexão com o servidor.' }; });
  }
  function item(c) {
    var p = pos(c);
    p.chave = c.dataset.chave; p.gz = +c.dataset.gz || 0;
    return p;
  }

  /* do retângulo em pixels para a posição que será gravada, conforme o encaixe */
  function alvoDe(r, modo, p0, id, semIma) {
    var ps = passo(), L = linha(), g = gap(), m = mb(), W = tela.clientWidth;
    if (enc === 'grade') {
      if (modo === 'mover')
        return { gx: Math.max(0, Math.min(NCOL - p0.gw, Math.round(r.x / ps))),
                 gy: Math.max(0, Math.round(r.y / L)), gw: p0.gw, gh: p0.gh, fx: 0, fy: 0, fw: 0, fh: 0 };
      return { gx: p0.gx, gy: p0.gy,
               gw: Math.max(1, Math.min(NCOL - p0.gx, Math.round((r.w + g) / ps))),
               gh: Math.max(ALT_MIN, Math.round((r.h + m) / L)), fx: 0, fy: 0, fw: 0, fh: 0 };
    }
    var st = enc === '8' ? 8 : 1;
    function sn(v) { return Math.round(v / st) * st; }
    if (modo === 'mover') { r.x = sn(r.x); r.y = sn(r.y); } else { r.w = sn(r.w); r.h = sn(r.h); }
    if (ima && !semIma) {
      var Lx = [], Rx = [], Ty = [], By = [];
      cartoes().forEach(function (o) {
        if (o.dataset.chave === id) return;
        var b = rectDe(pos(o));
        Lx.push(b.x, b.x + b.w, b.x + b.w + g); Rx.push(b.x + b.w, b.x, b.x - g);
        Ty.push(b.y, b.y + b.h, b.y + b.h + m); By.push(b.y + b.h, b.y, b.y - m);
      });
      var perto = function (v, alvos) {
        var best = null;
        alvos.forEach(function (t) {
          var d = t - v;
          if (Math.abs(d) <= TOL && (best === null || Math.abs(d) < Math.abs(best))) best = d;
        });
        return best;
      };
      if (modo === 'mover') {
        var d1 = perto(r.x, Lx), d2 = perto(r.x + r.w, Rx);
        var dx = (d1 !== null && (d2 === null || Math.abs(d1) <= Math.abs(d2))) ? d1 : d2;
        if (dx !== null) r.x += dx;
        var e1 = perto(r.y, Ty), e2 = perto(r.y + r.h, By);
        var dy = (e1 !== null && (e2 === null || Math.abs(e1) <= Math.abs(e2))) ? e1 : e2;
        if (dy !== null) r.y += dy;
      } else {
        var f1 = perto(r.x + r.w, Rx); if (f1 !== null) r.w += f1;
        var f2 = perto(r.y + r.h, By); if (f2 !== null) r.h += f2;
      }
    }
    if (modo === 'mover') { r.x = Math.max(0, Math.min(W - r.w, r.x)); r.y = Math.max(0, r.y); }
    else { r.w = Math.max(60, Math.min(W - r.x, r.w)); r.h = Math.max(ALT_MIN * L - m, r.h); }
    return deRect(r);
  }

  /* ── fantasma e linhas-guia (em pixels, valem para qualquer encaixe) ── */
  var fantasma = null, linhas = [];
  function mostraFantasma(p, ocupado, sobreposto) {
    if (!fantasma) {
      fantasma = document.createElement('div');
      fantasma.className = 'livre-fantasma';
      tela.appendChild(fantasma);
    }
    var r = rectDe(p);
    fantasma.style.left = r.x + 'px'; fantasma.style.top = r.y + 'px';
    fantasma.style.width = r.w + 'px'; fantasma.style.height = r.h + 'px';
    fantasma.classList.toggle('ocupado', ocupado);
    fantasma.classList.toggle('sobreposto', sobreposto && !ocupado);
  }
  function limpaGuias() {
    if (fantasma) { fantasma.remove(); fantasma = null; }
    linhas.forEach(function (l) { l.remove(); });
    linhas = [];
  }
  function linhaGuia(tipo, px) {
    var l = document.createElement('div');
    l.className = 'livre-linha ' + tipo;
    if (tipo === 'v') l.style.left = px + 'px'; else l.style.top = px + 'px';
    tela.appendChild(l); linhas.push(l);
  }
  function guias(p, atual) {
    linhas.forEach(function (l) { l.remove(); }); linhas = [];
    var a = rectDe(p), g = gap(), m = mb(), vx = {}, hy = {};
    cartoes().forEach(function (o) {
      if (o === atual) return;
      var b = rectDe(pos(o));
      [a.x, a.x + a.w].forEach(function (u) {
        [b.x, b.x + b.w, b.x + b.w + g, b.x - g].forEach(function (t) {
          if (Math.abs(u - t) < 1) vx[Math.round(u)] = 1; });
      });
      [a.y, a.y + a.h].forEach(function (u) {
        [b.y, b.y + b.h, b.y + b.h + m, b.y - m].forEach(function (t) {
          if (Math.abs(u - t) < 1) hy[Math.round(u)] = 1; });
      });
    });
    Object.keys(vx).forEach(function (x) { linhaGuia('v', +x); });
    Object.keys(hy).forEach(function (y) { linhaGuia('h', +y); });
  }

  /* ── rolagem automática enquanto arrasta ── */
  var ultimoY = 0, rolando = false;
  function rola() {
    if (!rolando) return;
    if (ultimoY > innerHeight - 60) scrollBy(0, 18);
    else if (ultimoY < 60) scrollBy(0, -18);
    requestAnimationFrame(rola);
  }

  /* ── mover e redimensionar ── */
  function arrasta(e, c, modo) {
    e.preventDefault();
    var ini = pos(c), r0 = rectDe(ini), alvo = ini;
    var x0 = e.pageX, y0 = e.pageY;
    ultimoY = e.clientY; rolando = true; requestAnimationFrame(rola);
    if (modo === 'mover') c.classList.add('movendo');
    try { c.setPointerCapture(e.pointerId); } catch (_) {}

    function mover(ev) {
      ultimoY = ev.clientY;
      var dx = ev.pageX - x0, dy = ev.pageY - y0;
      var r = modo === 'mover' ? { x: r0.x + dx, y: r0.y + dy, w: r0.w, h: r0.h }
                               : { x: r0.x, y: r0.y, w: r0.w + dx, h: r0.h + dy };
      alvo = alvoDe(r, modo, ini, c.dataset.chave, ev.altKey);
      if (modo === 'mover') {
        var rr = rectDe(alvo);
        c.style.transform = 'translate(' + (rr.x - r0.x) + 'px,' + (rr.y - r0.y) + 'px)';
      }
      mostraFantasma(alvo, bate(alvo, c), sobrepor && choca(alvo, c));
      guias(alvo, c);
    }
    function soltar() {
      rolando = false;
      c.removeEventListener('pointermove', mover);
      c.removeEventListener('pointerup', soltar);
      c.removeEventListener('pointercancel', soltar);
      c.classList.remove('movendo');
      c.style.transform = '';
      limpaGuias();
      var mudou = K.some(function (k) { return alvo[k] !== ini[k]; });
      if (!mudou) return;
      if (bate(alvo, c)) {
        aviso('Esse espaço já está ocupado por outro cartão. Marque "Permitir sobrepor" para deixar um sobre o outro.');
        return;
      }
      var gzAntes = +c.dataset.gz || 0;
      aplica(c, alvo);
      // Sobrepondo, o cartão mexido passa para a frente dos demais.
      if (sobrepor && choca(alvo, c)) traz(c);
      salva([item(c)]).then(function (r) {
        if (!r.ok) { aplica(c, ini); traz(c, gzAntes); aviso(r.erro || 'Não consegui salvar.'); }
      });
      setTimeout(marcaCortes, 50);
    }
    c.addEventListener('pointermove', mover);
    c.addEventListener('pointerup', soltar);
    c.addEventListener('pointercancel', soltar);
  }

  /* ── altura do conteúdo ── */
  function alturaIdeal(c) {
    var a = c.style.alignSelf, h = c.style.height, mh = c.style.minHeight;
    c.style.alignSelf = 'start'; c.style.height = 'auto'; c.style.minHeight = '0';
    var corpo = c.querySelector('.cartao-corpo'), of = corpo && corpo.style.overflow;
    if (corpo) corpo.style.overflow = 'visible';
    var px = c.offsetHeight + mb();
    if (corpo) corpo.style.overflow = of;
    c.style.alignSelf = a; c.style.height = h; c.style.minHeight = mh;
    return px;
  }
  function ajustaUm(c) {
    var ini = pos(c), px = alturaIdeal(c), novo;
    if (enc === 'grade') {
      novo = { gx: ini.gx, gy: ini.gy, gw: ini.gw, gh: Math.max(ALT_MIN, Math.ceil(px / linha())),
               fx: ini.fx, fy: ini.fy, fw: ini.fw, fh: 0 };
    } else {
      var r = rectDe(ini); r.h = Math.max(ALT_MIN * linha() - mb(), px - mb()); novo = deRect(r);
    }
    if (K.every(function (k) { return novo[k] === ini[k]; })) return;
    if (bate(novo, c)) { aviso('Não há espaço livre embaixo para ajustar este cartão.'); return; }
    aplica(c, novo);
    salva([item(c)]).then(function (r) {
      if (!r.ok) { aplica(c, ini); aviso(r.erro || 'Não consegui salvar.'); }
    });
    setTimeout(marcaCortes, 50);
  }
  function ajustaTodos() {
    var lista = cartoes().sort(function (a, b) {
      return (+a.dataset.gy - +b.dataset.gy) || (+a.dataset.gx - +b.dataset.gx);
    });
    var antes = lista.map(function (c) { return [c, pos(c)]; });
    var colocados = [];
    lista.forEach(function (c) {
      var p = pos(c);
      p.gh = Math.max(ALT_MIN, Math.ceil(alturaIdeal(c) / linha()));
      p.fx = p.fy = p.fw = p.fh = 0;
      function colide() {
        return colocados.some(function (q) {
          return p.gx < q.gx + q.gw && q.gx < p.gx + p.gw &&
                 p.gy < q.gy + q.gh && q.gy < p.gy + p.gh;
        });
      }
      while (colide()) p.gy++;
      colocados.push(p);
      aplica(c, p);
    });
    salva(lista.map(item)).then(function (r) {
      if (!r.ok) {
        antes.forEach(function (par) { aplica(par[0], par[1]); });
        aviso(r.erro || 'Não consegui salvar.');
      } else aviso('Cartões ajustados ao conteúdo.');
    });
    setTimeout(marcaCortes, 50);
  }

  /* ── ligar/desligar o modo de edição ── */
  function prepara(c) {
    ligaMover(c);
    if (c.querySelector('.livre-alca')) return;
    var e = document.createElement('span'); e.className = 'livre-etiqueta livre-alca-eti';
    e.style.pointerEvents = 'none';
    var a = document.createElement('span'); a.className = 'livre-alca';
    a.title = 'Arraste para mudar o tamanho; clique duas vezes para ajustar à altura do conteúdo';
    c.appendChild(e); c.appendChild(a);
    etiqueta(c);
    // O arrasto captura o ponteiro no cartão, e com isso o `dblclick` não chega
    // ao puxador; o duplo clique é reconhecido aqui, pelo intervalo entre dois.
    var ultimo = 0;
    a.addEventListener('pointerdown', function (ev) {
      if (!editando) return;
      ev.stopPropagation();
      var agora = Date.now();
      if (agora - ultimo < 400) { ultimo = 0; ev.preventDefault(); ajustaUm(c); return; }
      ultimo = agora;
      arrasta(ev, c, 'tamanho');
    });
  }
  function ligaMover(c) {
    if (c._livre) return;
    c._livre = true;
    c.tabIndex = 0;
    c.addEventListener('pointerdown', function (ev) {
      if (!editando || ev.button !== 0 || ev.target.closest('.livre-alca')) return;
      arrasta(ev, c, 'mover');
    });
    // Setas movem o cartão em foco; Shift + setas muda o tamanho.
    c.addEventListener('keydown', function (ev) {
      if (!editando || ev.key.indexOf('Arrow') !== 0) return;
      ev.preventDefault();
      var ini = pos(c), r = rectDe(ini), ps = passo(), L = linha();
      var dx = ev.key === 'ArrowRight' ? 1 : ev.key === 'ArrowLeft' ? -1 : 0;
      var dy = ev.key === 'ArrowDown' ? 1 : ev.key === 'ArrowUp' ? -1 : 0;
      var st = enc === 'grade' ? null : (enc === '8' ? 8 : 1);
      var modo = ev.shiftKey ? 'tamanho' : 'mover';
      if (modo === 'mover') { r.x += dx * (st || ps); r.y += dy * (st || L); }
      else { r.w += dx * (st || ps); r.h += dy * (st || L); }
      var novo = alvoDe(r, modo, ini, c.dataset.chave, true);
      if (K.every(function (k) { return novo[k] === ini[k]; })) return;
      if (bate(novo, c)) { aviso('Esse espaço já está ocupado por outro cartão.'); return; }
      var gzAntes = +c.dataset.gz || 0;
      aplica(c, novo);
      if (sobrepor && choca(novo, c)) traz(c);
      salva([item(c)]).then(function (r2) {
        if (!r2.ok) { aplica(c, ini); traz(c, gzAntes); aviso(r2.erro || 'Não consegui salvar.'); }
      });
      setTimeout(marcaCortes, 50);
    });
  }
  function liga(sim) {
    editando = sim;
    tela.classList.toggle('editando', sim);
    btn.textContent = sim ? 'Concluir edição' : 'Editar layout';
    if (ajuda) ajuda.hidden = !sim;
    if (btnAjustar) btnAjustar.hidden = !sim;
    [chkSobrepor, selEnc, chkIma].forEach(function (el) {
      if (el) el.closest('label').hidden = !sim;
    });
    if (sim) {
      if (!malha) {
        malha = document.createElement('div'); malha.className = 'livre-malha';
        for (var i = 0; i < NCOL; i++) malha.appendChild(document.createElement('i'));
        tela.insertBefore(malha, tela.firstChild);
      }
      cartoes().forEach(prepara);
    } else {
      if (malha) { malha.remove(); malha = null; }
      cartoes().forEach(function (c) {
        [].forEach.call(c.querySelectorAll('.livre-alca,.livre-alca-eti'),
                        function (n) { n.remove(); });
      });
    }
    marcaCortes();
  }
  // Conteúdo maior que o cartão fica cortado (sem barra de rolagem); no modo
  // de edição o cartão ganha um aviso para você aumentar a altura ou ajustar.
  function marcaCortes() {
    cartoes().forEach(function (c) {
      var k = c.querySelector('.cartao-corpo');
      var corta = editando && k && k.scrollHeight > k.clientHeight + 2;
      c.classList.toggle('corta', !!corta);
    });
  }
  // "Concluir edição" sai do editor e mostra o portal como os demais o veem.
  if (btn) btn.addEventListener('click', function () {
    if (editando) { location.href = btn.dataset.sair || '/'; } else liga(true);
  });
  if (btnAjustar) btnAjustar.addEventListener('click', ajustaTodos);
  if (chkSobrepor) chkSobrepor.addEventListener('change', function () {
    sobrepor = chkSobrepor.checked;
    try { localStorage.setItem('portal-livre-sobrepor', sobrepor ? '1' : '0'); } catch (_) {}
    aviso(sobrepor ? 'Sobreposição permitida: o cartão que você mover fica na frente.'
                   : 'Sobreposição desligada: cartões não podem ocupar o mesmo espaço.');
  });
  if (selEnc) selEnc.addEventListener('change', function () {
    enc = selEnc.value;
    try { localStorage.setItem('portal-livre-encaixe', enc); } catch (_) {}
    aviso(enc === 'grade' ? 'Encaixe na grade: o cartão salta de célula em célula.'
        : enc === '8' ? 'Encaixe fino: o cartão anda de 8 em 8 pixels.'
        : 'Encaixe livre: o cartão anda de 1 em 1 pixel.');
  });
  if (chkIma) chkIma.addEventListener('change', function () {
    ima = chkIma.checked;
    try { localStorage.setItem('portal-livre-ima', ima ? '1' : '0'); } catch (_) {}
  });
  addEventListener('resize', marcaCortes);
  // Evita que um clique no fim do arrasto abra o link do cartão.
  tela.addEventListener('click', function (e) {
    if (editando) { e.preventDefault(); e.stopPropagation(); }
  }, true);
})();
