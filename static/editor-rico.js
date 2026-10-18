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
            var h = '<img src="' + i.url + '" alt="' + alt.replace(/"/g, '&quot;') + '">';
            document.execCommand('insertHTML', false, h);
          }
        });
      });
    }

    if (form) form.addEventListener('submit', function (e) {
      oculto.value = area.innerHTML;
    });
  });
})();
