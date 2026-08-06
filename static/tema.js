/*  Alternância de tema claro/escuro.

    A escolha fica no navegador de quem acessa (localStorage), não no servidor:
    o portal é aberto a toda a rede e não há sessão para a maioria das pessoas.
    A aplicação inicial acontece num script embutido no <head> (ver base.html)
    para a página não piscar em branco antes de trocar. */
(function () {
  var CHAVE = 'portal-tema';
  var botao = document.getElementById('trocar-tema');
  if (!botao) return;

  function aplicar(tema) {
    document.documentElement.setAttribute('data-tema', tema);
    botao.setAttribute('aria-label', tema === 'escuro' ? 'Usar tema claro' : 'Usar tema escuro');
    botao.title = botao.getAttribute('aria-label');
    // Só um dos dois desenhos aparece por vez.
    var lua = botao.querySelector('.ic-lua'), sol = botao.querySelector('.ic-sol');
    if (lua && sol) {
      lua.style.display = tema === 'escuro' ? 'none' : 'block';
      sol.style.display = tema === 'escuro' ? 'block' : 'none';
    }
  }

  aplicar(document.documentElement.getAttribute('data-tema') || 'claro');

  botao.addEventListener('click', function () {
    var novo = document.documentElement.getAttribute('data-tema') === 'escuro'
      ? 'claro' : 'escuro';
    try { localStorage.setItem(CHAVE, novo); } catch (e) { /* modo privado */ }
    aplicar(novo);
  });
})();
