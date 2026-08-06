/* Busca na lista de ramais: filtra enquanto se digita, sem recarregar.
   Compara sem acentos, então "manutencao" encontra "MANUTENÇÃO". */
(function () {
  var campo = document.getElementById('busca-ramal');
  var lista = document.getElementById('lista-ramais');
  if (!campo || !lista) return;

  var vazio = document.getElementById('sem-resultado');
  var conta = document.getElementById('conta-ramais');
  var itens = Array.prototype.slice.call(lista.querySelectorAll('.ramal-item'));

  function normaliza(t) {
    return (t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  }

  itens.forEach(function (el) {
    el.dataset.busca = normaliza(el.textContent);
    var setor = el.querySelector('.ramal-setor');
    var numero = el.querySelector('.ramal-numero');
    if (setor) setor.dataset.texto = setor.textContent;
    if (numero) numero.dataset.texto = numero.textContent;
  });

  // Realça o trecho encontrado, comparando sem acentos mas destacando no
  // texto original (as posições coincidem porque NFD só separa os acentos).
  function realcar(el, termo) {
    ['.ramal-setor', '.ramal-numero'].forEach(function (sel) {
      var alvo = el.querySelector(sel);
      if (!alvo) return;
      var texto = alvo.dataset.texto || alvo.textContent;
      if (!termo) { alvo.textContent = texto; return; }
      var i = normaliza(texto).indexOf(termo);
      if (i === -1) { alvo.textContent = texto; return; }
      alvo.textContent = '';
      alvo.appendChild(document.createTextNode(texto.slice(0, i)));
      var marca = document.createElement('mark');
      marca.textContent = texto.slice(i, i + termo.length);
      alvo.appendChild(marca);
      alvo.appendChild(document.createTextNode(texto.slice(i + termo.length)));
    });
  }

  function filtrar() {
    var termo = normaliza(campo.value).trim();
    var achou = 0;
    itens.forEach(function (el) {
      var mostra = !termo || el.dataset.busca.indexOf(termo) !== -1;
      el.hidden = !mostra;
      if (mostra) { realcar(el, termo); achou++; }
    });
    if (vazio) vazio.hidden = achou !== 0;
    if (conta) conta.textContent = achou;
  }

  campo.addEventListener('input', filtrar);
  campo.addEventListener('search', filtrar);
  // O campo pode chegar preenchido pela busca do topo (?q=)
  if (campo.value.trim()) filtrar();
  campo.focus();
})();

/*  Filtro do cartão de ramais no painel.

    A lista inteira está na página; só as linhas em destaque começam visíveis.
    Buscar apenas o que já está à vista não serviria para nada — quem digita
    quer achar o ramal que NÃO está ali. Com o campo vazio, volta ao destaque. */
(function () {
  var campo = document.getElementById('filtro-ramais-painel');
  if (!campo) return;
  var linhas = document.querySelectorAll('.ramais .ramal-linha');
  var nada = document.querySelector('.ramais .ramais-nada');

  function semAcento(t) {
    return t.normalize('NFD').replace(/[̀-ͯ]/g, '');
  }

  campo.addEventListener('input', function () {
    var termo = semAcento(campo.value.trim().toLowerCase());
    var achou = 0;
    linhas.forEach(function (l) {
      var mostra = termo === ''
        ? !l.classList.contains('ramal-extra')
        : semAcento(l.dataset.setor || '').indexOf(termo) !== -1;
      l.hidden = !mostra;
      if (mostra) achou++;
    });
    if (nada) nada.hidden = !(termo !== '' && achou === 0);
  });
})();
