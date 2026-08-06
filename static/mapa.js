/*  Mapa do painel: arrastar os cartões para a região e a coluna desejadas.

    Usa o arrastar-e-soltar do próprio navegador, sem biblioteca — o portal é
    de rede interna e não baixa nada de fora.

    Nada é gravado enquanto se arrasta: as mudanças ficam na tela até alguém
    clicar em Salvar. Assim dá para experimentar arranjos sem deixar o painel
    da unidade mudando a cada movimento do mouse.  */
(function () {
  'use strict';
  var mapa = document.querySelector('[data-mapa]');
  if (!mapa) return;

  var arrastado = null;
  var salvar = mapa.querySelector('[data-salvar]');
  var aviso = mapa.querySelector('[data-aviso]');

  function sujo() {
    if (aviso) aviso.hidden = false;
    if (salvar) salvar.disabled = false;
  }

  /*  A largura do cartão é quantas colunas ele ocupa. Presa entre 1 e 3: a
      grade tem três, e um cartão mais largo que a grade transbordaria.  */
  function larguraDe(cartao) {
    return Math.min(3, Math.max(1, parseInt(cartao.dataset.larg, 10) || 1));
  }

  function pintaLargura(cartao) {
    var n = larguraDe(cartao);
    cartao.dataset.larg = n;
    cartao.style.gridColumnEnd = 'span ' + n;
    var rotulo = cartao.querySelector('[data-larg-rotulo]');
    if (rotulo) rotulo.textContent = n + (n > 1 ? ' colunas' : ' coluna');
  }

  mapa.querySelectorAll('[data-cartao]').forEach(function (cartao) {
    pintaLargura(cartao);

    cartao.addEventListener('dragstart', function (e) {
      arrastado = cartao;
      cartao.classList.add('arrastando');
      e.dataTransfer.effectAllowed = 'move';
      /*  Firefox só inicia o arrasto se houver dado no dataTransfer.  */
      e.dataTransfer.setData('text/plain', cartao.dataset.cartao);
    });

    cartao.addEventListener('dragend', function () {
      cartao.classList.remove('arrastando');
      mapa.querySelectorAll('.alvo').forEach(function (c) {
        c.classList.remove('alvo');
      });
      arrastado = null;
    });

    cartao.querySelectorAll('[data-larg-menos],[data-larg-mais]').forEach(function (b) {
      b.addEventListener('click', function () {
        var passo = b.hasAttribute('data-larg-mais') ? 1 : -1;
        cartao.dataset.larg = larguraDe(cartao) + passo;
        pintaLargura(cartao);
        sujo();
      });
    });
  });

  mapa.querySelectorAll('[data-celula]').forEach(function (celula) {
    celula.addEventListener('dragover', function (e) {
      if (!arrastado) return;
      e.preventDefault();                 /* sem isto o soltar não acontece */
      e.dataTransfer.dropEffect = 'move';
      celula.classList.add('alvo');
    });

    celula.addEventListener('dragleave', function () {
      celula.classList.remove('alvo');
    });

    celula.addEventListener('drop', function (e) {
      if (!arrastado) return;
      e.preventDefault();
      celula.classList.remove('alvo');
      celula.appendChild(arrastado);
      sujo();
    });
  });

  /*  Ao salvar, a posição de cada cartão é lida da tela: região e coluna vêm
      da célula onde ele parou, e a ordem, da sequência em que aparecem. Ler do
      DOM em vez de acompanhar cada movimento evita que um arrasto perdido
      deixe o estado guardado diferente do que se vê.  */
  if (salvar) {
    salvar.addEventListener('click', function () {
      var posicoes = [];
      var n = 0;
      mapa.querySelectorAll('[data-celula]').forEach(function (celula) {
        celula.querySelectorAll('[data-cartao]').forEach(function (cartao) {
          posicoes.push({
            ref: cartao.dataset.cartao,
            regiao: celula.dataset.regiao,
            coluna: parseInt(celula.dataset.coluna, 10),
            largura: larguraDe(cartao),
            ordem: n++
          });
        });
      });
      mapa.querySelector('[data-posicoes]').value = JSON.stringify(posicoes);
      mapa.querySelector('form').submit();
    });
  }
})();
