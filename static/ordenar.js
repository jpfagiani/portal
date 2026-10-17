/* Reordenação por arrastar e soltar nas listas do painel.

   Serve para qualquer container marcado com [data-ordenavel] cujos filhos
   diretos tenham data-id — tanto <tbody> com <tr> quanto uma lista de cartões.
   Ao soltar, a nova sequência é gravada na hora; o campo "Ordem" do formulário
   continua valendo para quem preferir digitar (e para navegação por teclado,
   já que arrastar exige mouse). */
(function () {
  var containers = document.querySelectorAll('[data-ordenavel]');
  if (!containers.length) return;

  function aviso(texto, erro) {
    var d = document.createElement('div');
    d.className = 'toast-ordem' + (erro ? ' toast-erro' : '');
    d.textContent = texto;
    document.body.appendChild(d);
    setTimeout(function () { d.classList.add('sumindo'); }, 1800);
    setTimeout(function () { d.remove(); }, 2400);
  }

  containers.forEach(function (caixa) {
    function itens() {
      return Array.prototype.filter.call(caixa.children, function (e) {
        return e.dataset && e.dataset.id;
      });
    }
    var arrastado = null;

    itens().forEach(preparar);

    function limparMarcas() {
      itens().forEach(function (e) { e.classList.remove('alvo-acima', 'alvo-abaixo'); });
    }

    function preparar(el) {
      el.draggable = true;
      el.addEventListener('dragstart', function (e) {
        arrastado = el;
        el.classList.add('arrastando');
        e.dataTransfer.effectAllowed = 'move';
        // Firefox só inicia o arrasto se algum dado for definido
        e.dataTransfer.setData('text/plain', el.dataset.id);
      });
      el.addEventListener('dragend', function () {
        el.classList.remove('arrastando');
        limparMarcas();
        arrastado = null;
      });
      el.addEventListener('dragover', function (e) {
        if (!arrastado || arrastado === el) return;
        e.preventDefault();
        var r = el.getBoundingClientRect();
        var antes = (e.clientY - r.top) < r.height / 2;
        el.classList.toggle('alvo-acima', antes);
        el.classList.toggle('alvo-abaixo', !antes);
      });
      el.addEventListener('dragleave', function () {
        el.classList.remove('alvo-acima', 'alvo-abaixo');
      });
      el.addEventListener('drop', function (e) {
        if (!arrastado || arrastado === el) return;
        e.preventDefault();
        var r = el.getBoundingClientRect();
        var antes = (e.clientY - r.top) < r.height / 2;
        caixa.insertBefore(arrastado, antes ? el : el.nextSibling);
        limparMarcas();
        salvar();
      });
    }

    function salvar() {
      var ids = itens().map(function (e) { return e.dataset.id; });
      var dados = new FormData();
      dados.append('csrf', caixa.dataset.csrf);
      dados.append('acao', 'ordenar');
      dados.append('ids', ids.join(','));
      // Campos extras exigidos pela rota (ex.: qual bloco do painel),
      // no formato "chave=valor&outra=valor".
      (caixa.dataset.extra || '').split('&').forEach(function (par) {
        if (!par) return;
        var i = par.indexOf('=');
        if (i > 0) dados.append(par.slice(0, i), par.slice(i + 1));
      });
      fetch(caixa.dataset.ordenavel, { method: 'POST', body: dados, credentials: 'same-origin' })
        .then(function (r) {
          if (r.ok) {
            aviso('Ordem salva.');
            itens().forEach(function (e, i) {
              var c = e.querySelector('[data-coluna-ordem]');
              if (c) c.textContent = i;
            });
          } else {
            aviso('Não foi possível salvar a ordem (' + r.status + ').', true);
          }
        })
        .catch(function () { aviso('Falha de conexão ao salvar a ordem.', true); });
    }
  });
})();
