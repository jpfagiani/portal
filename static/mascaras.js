/*  Máscara de horário para os campos de escala.

    Digita-se só os números — "06001800" — e o campo vira "06:00 às 18:00"
    sozinho. Evita "6h as 18", "06:00-18:00" e "06:00 ate 18:00" convivendo na
    mesma lista, que é o que acontece quando o campo é texto livre.

    O valor continua sendo texto no banco: quem quiser escrever outra coisa
    ("12x36", "sob escala") apaga e digita — a máscara só age sobre dígitos. */
(function () {
  var campos = document.querySelectorAll('[data-mascara="horario"]');
  if (!campos.length) return;

  function formatar(bruto) {
    var d = bruto.replace(/\D/g, '').slice(0, 8);
    if (!d) return '';
    var saida = d.slice(0, 2);
    if (d.length > 2) saida += ':' + d.slice(2, 4);
    if (d.length > 4) saida += ' às ' + d.slice(4, 6);
    if (d.length > 6) saida += ':' + d.slice(6, 8);
    return saida;
  }

  campos.forEach(function (campo) {
    campo.addEventListener('input', function () {
      // Texto sem nenhum dígito é escolha de quem escreveu: não mexe.
      if (!/\d/.test(campo.value)) return;
      // Só reescreve o que é claramente uma sequência de horário; assim
      // "Plantão 12x36" sobrevive a uma correção no meio da palavra.
      if (/[^\d\s:hàas\-àe]/i.test(campo.value)) return;
      var pos = campo.selectionStart === campo.value.length;
      campo.value = formatar(campo.value);
      if (pos) campo.setSelectionRange(campo.value.length, campo.value.length);
    });
  });
})();
