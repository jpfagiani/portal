/* Banner rotativo: troca automática, setas, pontos e pausa ao passar o mouse. */
(function () {
  var banner = document.querySelector('.capa');
  if (!banner) return;

  var slides = banner.querySelectorAll('.slide');
  var pontos = banner.querySelectorAll('.ponto');
  if (slides.length < 2) return;

  var atual = 0;
  var segundos = parseInt(banner.dataset.intervalo, 10) || 6;
  var timer = null;

  function mostrar(i) {
    atual = (i + slides.length) % slides.length;
    slides.forEach(function (s, n) { s.classList.toggle('ativo', n === atual); });
    pontos.forEach(function (p, n) { p.classList.toggle('ativo', n === atual); });
  }

  function iniciar() {
    parar();
    timer = setInterval(function () { mostrar(atual + 1); }, segundos * 1000);
  }
  function parar() { if (timer) { clearInterval(timer); timer = null; } }

  var ant = banner.querySelector('.banner-seta.ant');
  var prox = banner.querySelector('.banner-seta.prox');
  if (ant) ant.addEventListener('click', function () { mostrar(atual - 1); iniciar(); });
  if (prox) prox.addEventListener('click', function () { mostrar(atual + 1); iniciar(); });

  pontos.forEach(function (p, n) {
    p.addEventListener('click', function () { mostrar(n); iniciar(); });
  });

  banner.addEventListener('mouseenter', parar);
  banner.addEventListener('mouseleave', iniciar);
  document.addEventListener('visibilitychange', function () {
    document.hidden ? parar() : iniciar();
  });

  iniciar();
})();
