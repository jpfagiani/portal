# Modernização do portal — registro das fases

Este arquivo registra o que foi feito seguindo a Especificação-Mestra do Portal Editorial
(versão 1.9.16 → 1.10.0). Tudo foi feito numa cópia de desenvolvimento; nada foi implantado.

## Fase 0 — Inventário (resumo)

- Flask + Jinja + SQLite (`dados.db`), 19 tabelas, 38 rotas (+1 nova), gunicorn com 3 processos.
- `app.py` concentra as rotas e a limpeza de HTML; `modulos/` guarda notícias, mídia, cartões,
  auditoria e segurança.
- Segurança existente: login com limite de tentativas, todas as rotas `/admin` com
  `@admin_obrigatorio`, CSRF em todo POST, lista de elementos permitidos no HTML (`limpa_html`),
  upload conferido pelo conteúdo real, `secret.key` criada uma única vez com permissão 600.
- Arquivos soltos na raiz (`index.html`, `blocos.html`, `style.css`, `encaixe.js`) parecem cópias
  antigas de `templates/` e `static/`. **Não foram apagados**: precisam de confirmação.

## Fase 1 — Linha de base

| Comando | Resultado antes das mudanças |
|---|---|
| `python3 -m py_compile app.py modulos/*.py` | passou |
| `python3 -I tests/verificacoes_portal.py` | 129 verificações, todas passaram |
| `python3 -m unittest discover -s tests -v` | não achava nenhum teste (script comum) |

## Entregas desta versão

| Fase | O que mudou |
|---|---|
| Backup | `portal-backup-*.zip` saiu do repositório; `.gitignore` agora o ignora. |
| 2–3 | Coluna de leitura de 640px como no UOL (imagem na largura da coluna e texto abaixo, nas mesmas bordas), texto de 20px/32px; resumo em tópicos nas manchetes e listas; tokens de espaçamento e raio. |
| 4 | Editor de notícias: salva por fetch (o texto nunca se perde se der erro), selo de estado (sem alterações, pendente, salvando, salvo, falha), aviso ao sair com alterações, erro junto do campo, prévia fiel à página pública (rota `/admin/noticias/previa`, mesmo template, nada gravado). |
| 5 | Biblioteca de mídia: imagens usadas na coluna lateral, no texto das páginas e nos cartões agora contam como "em uso" (antes podiam ser excluídas por engano); dimensões em pixels na listagem. |
| 6 | Cabeçalho `Content-Security-Policy` (desligável com `PORTAL_CSP=0`); testes novos; `unittest discover` funciona. |
| 7 | Sem rolagem horizontal nas telas de administração no celular; contraste e rótulos corrigidos (sem violações WCAG A/AA automáticas nas páginas testadas); testes de backup e restauração. |

## Arquivos alterados

`app.py` (versão, cores padrão), `modulos/noticias.py` (respostas JSON, prévia), `modulos/midia.py`
(usos, dimensões), `modulos/seguranca.py` (CSP), `templates/noticias.html`, `noticia.html`,
`admin_noticias.html`, `admin_midia.html`, `static/limpo.css`, `static/style.css`,
`static/editor-estado.js` (novo), `tests/verificacoes_portal.py`, `tests/test_unittest.py` (novo),
`.gitignore`, `docs/MODERNIZACAO.md` (novo).

Nenhuma tabela, coluna ou arquivo de dados foi alterado: **não há migração de banco nesta versão**.

## Testes executados

- `python3 -I tests/verificacoes_portal.py`: 153 verificações, todas passaram (inclui salvar por fetch,
  prévia, CSRF, uso de imagem, CSP, backup e restauração, entrada `../` em backup).
- `python3 -m unittest discover -s tests -v`: passa.
- Navegador real (Chromium): editor completo (estado, erro, falha do servidor, prévia, aviso de
  saída), páginas públicas e de administração em 390, 768 e 1366px; axe-core WCAG A/AA.
- Não executado: teste em celular físico, leitor de tela, Firefox/Safari, carga e desempenho,
  restauração de backup em outra máquina.

## Riscos conhecidos e decisões pendentes

1. **Backup no GitHub.** Se `portal-backup-2026-10-23-1625.zip` já foi enviado ao repositório, ele
   continua no histórico (traz usuários, hashes de senha e uploads). Remover do histórico é decisão
   do responsável: `git rm --cached portal-backup-*.zip`, commit e, para limpar o histórico,
   `git filter-repo`. Considere trocar as senhas dos usuários daquele backup.
2. **CSP com `unsafe-inline`.** O portal usa scripts e estilos escritos dentro das páginas. A
   política limita a origem do que carrega, mas não impede script escrito na própria página; quem
   impede isso é a limpeza do HTML no servidor. Remover o `unsafe-inline` exige mover esses
   scripts para arquivos (trabalho futuro).
3. **Cores já gravadas.** Os padrões novos de cor de texto secundário (`#5b6b82`) só valem para
   instalações novas e cartões novos. Quem já personalizou em Administração → Aparência mantém o
   valor antigo (`#7c8ba1`, contraste 3,5:1); trocar a cor lá resolve.
4. **Capa enviada agora não aparece na prévia** até salvar (a prévia não grava arquivos).
5. **Notícias antigas** só ganham as caixas "figura" (texto exatamente na largura da imagem)
   depois de abertas no editor e salvas uma vez; o alinhamento em tempo real continua cobrindo as demais.
6. **Arquivos soltos na raiz** (ver Fase 0): confirmar se podem ser removidos.

## Decisão sobre o editor rico (seção 10 da especificação)

**Mantido o editor atual** nesta versão. Motivos: o conteúdo já gravado usa classes próprias
(`im-c`, `figura`, colunas) que um editor novo teria de reproduzir; o TipTap exigiria etapa de
build (Node) que o portal, instalado por `instalar.sh` no Debian, não tem hoje; e a licença de
cada extensão precisa ser conferida. Nada foi adicionado como dependência. Próximo passo
recomendado, se houver interesse: prova de conceito isolada com amostras reais de notícias
(exportar `noticias.corpo` do banco) e comparação da renderização antes e depois.

## Instalação e verificação

1. Faça um backup em Administração → Backup e guarde o `.zip` fora da pasta do portal.
2. Copie a pasta do portal (ou confirme que o `git status` está limpo).
3. Extraia `portal-atualizacao.zip` sobre a pasta do portal.
4. `sudo systemctl restart portal` (ou `./atualizar.sh`) e Ctrl+F5 no navegador.
5. Abra Administração → Notícias, edite uma notícia, clique em **Prévia** e depois em **Salvar**.
6. Para validar: `python3 -I tests/verificacoes_portal.py` (usa cópia temporária; não toca no banco real).

## Reversão

Não há alteração de banco. Para voltar à versão anterior, restaure os arquivos listados acima a
partir da cópia feita no passo 2 (ou `git checkout -- <arquivos>`), apague `static/editor-estado.js`,
`tests/test_unittest.py` e `docs/MODERNIZACAO.md` e reinicie o serviço. Para desligar só a política
de segurança de conteúdo sem mexer em arquivos: defina `PORTAL_CSP=0` no serviço e reinicie.

## Próximas fases sugeridas

- Mesma prévia, estado de salvamento e aviso de saída para a edição "na própria página" e para os
  editores de páginas e cartões (hoje só o editor completo de notícias os tem).
- Componentes de cartão e manchete compartilhados entre a página inicial e a lista de notícias.
- Mover scripts embutidos para arquivos e remover `unsafe-inline` da CSP.
- Prova de conceito do TipTap com conteúdo real.
- Teste em aparelhos e leitor de tela; Firefox e Safari.

## 1.10.1 — texto colado e conteúdo antigo na notícia

Na página pública da notícia, toda imagem (pequena, média, grande, com largura em px, flutuante ou dentro
de caixa "figura") passa a ocupar a coluna inteira, e todo texto fica na mesma largura, alinhado à
esquerda, mesmo que tenha sido colado centralizado. Vale para notícias novas e antigas, sem precisar
salvar de novo. Blocos de colunas (`.cols`) continuam livres. Reversão: apagar o último bloco de
`static/limpo.css` ("Notícia no padrão do UOL").

## 1.9.22 — Cartões dentro de Conteúdos (Fases 0 e 1 do plano de 29/10/2026)

- **Aba "Cartões do painel" removida.** Em Administração → Conteúdos há agora a seção
  "Cartões da página inicial" (nome, ícone de cada cartão, fonte e cores, vitrine de notícias, novo cartão de
  comunicados, excluir cartão) e o filtro "Comunicados → cartão", com ordem por arrastar e caixa de visível.
  `/admin/lateral` e `/admin/cartoes` continuam existindo e redirecionam para Conteúdos; o POST de ordenar e excluir
  itens segue em `/admin/lateral`. Os templates `admin_lateral.html` e `admin_cartoes.html` foram removidos.
- **Erro 405 corrigido:** o formulário de aparência de "Últimas notícias" na tela Conteúdos agora é aceito
  (`/admin/conteudos` passou a receber POST).
- **Testes:** `tests/test_modulos.py` virou `tests/verificacoes_portal.py` (o `unittest discover` tentava importá-lo e
  quebrava). 225 verificações passam; `python3 -m unittest discover -s tests` passa.
- **Texto exatamente na largura da imagem, em qualquer cartão ou conteúdo** (`agrupa_figuras` em `app.py`), tamanho da
  letra e da imagem em pixels (`static/tamanho-px.js`, `static/editor-rico.js`), grade de notícias opcional.
- **Não alterado:** banco de dados (sem migração), `secret.key`, uploads. Cópias antigas na raiz (`index.html`,
  `blocos.html`, `style.css`, `encaixe.js`) e os scripts sem uso (`static/barra-extra.js`, `static/alinha-texto.js`)
  aguardam sua confirmação para serem removidos.
- Reversão: restaurar os arquivos anteriores; não há alteração de banco.

Mapa de destinos (Fase 1): ver `docs/MAPA-DE-DESTINOS.md`.

## 1.11.0 — Plano de correções: nome administrativo × conteúdo público, destinos e editor

Feito em cópia de desenvolvimento (branch `correcoes-fase0-7`, origem: `portal-sistemas-modernizado.zip`); nada foi implantado.

### Diagnóstico (Fase 0)
| Requisito | Encontrado | Lacuna | Arquivos | Teste |
|---|---|---|---|---|
| Nome interno nunca público | `cartoes_painel.nome` era o título público do cartão (se `titulo_visivel`) e ia ao `aria-label` | vazava | `index.html`, `blocos.html`, `cartoes.py` | 1–4, 10 |
| 3 modos de apresentação | inexistentes | todo | `exibicao.py`, templates | 1–3, 6, 10 |
| Regra única nos componentes | 3 componentes, 3 regras | divergência | `chamada.html`, `index.html`, `noticias.html`, `blocos.html` | 10 |
| Destino validado | 3 colunas, sem validação forte; sem esquema virava `http://`; destino removido dava 404 | sim | `exibicao.py`, `conteudos.py` | 7–9 |
| Aba Cartões fora do menu | já feito | nenhuma | — | menu |
| Editor em áreas | campos soltos | reorganizar | `admin_conteudo_editor.html` | manual |

### Mapeamento de campos e migração
Só acrescenta colunas; nada é apagado ou sobrescrito. Antes, o banco é copiado para `dados.db.pre-exibicao-v1`.
| Conceito | Cartão | Notícia | Comunicado |
|---|---|---|---|
| nome administrativo | `cartoes_painel.nome` (já existia) | `noticias.nome_admin` (novo) | `lateral.nome_admin` (novo) |
| título público | `cartao_conteudo.titulo_publico` (novo) | `noticias.titulo` (título editorial) | `lateral.titulo` |
| texto de apoio | `texto_apoio` (novo) | `resumo` (ou `subtitulo`) | `lateral.conteudo` |
| exibir título / texto | `exibir_titulo`, `exibir_texto_apoio` | idem (padrão 1/0) | idem (padrão 1/1) |
| imagem / alt | `imagem`, `alt_imagem` (novos) | `capa`, `capa_alt` | `imagem`, `alt_imagem` (novo) |
| destino | `destino_tipo`, `url`, `nova_aba` | `destino_tipo`, `destino_url`, `nova_aba` | `destino_tipo`, `url`, `nova_aba` |

Itens antigos: `destino_tipo=''` e `nova_aba=-1` significam "regra antiga" (tipo inferido do endereço; externo em nova aba, interno na mesma). Uma única vez (`config.exibicao_v1`), o nome que o visitante já via nos cartões é **copiado** para `titulo_publico` e `titulo_visivel` vira `exibir_titulo`; assim nada muda para o visitante. `titulo_visivel` continua sendo gravado, o que mantém a volta à versão anterior coerente.

### Regras implementadas (`modulos/exibicao.py`)
- Título vazio ou desligado = nenhum título; sem fallback para nome interno, chave, slug ou arquivo. Nome acessível do link = título público ou texto alternativo.
- “Somente imagem” exige imagem e texto alternativo; não exige título.
- Destino: página do portal, notícia ou externo (**apenas http/https**). Interno é conferido contra as rotas reais e notícias publicadas; `/admin` é recusado. Destino que sumiu vira "sem link" (o painel avisa "destino indisponível"). Nova aba leva `rel="noopener noreferrer"`. O endereço não é exibido ao visitante. Tudo validado no servidor, antes de mexer em arquivos.
- Mudança de comportamento: endereço sem esquema (ex.: `exemplo.com`) agora é recusado em vez de virar `http://`; link interno de comunicado abre na mesma aba.

### Arquivos alterados
`app.py` (colunas, migração, backup, versão), `modulos/exibicao.py` (novo), `modulos/conteudos.py`, `modulos/cartoes.py`, `modulos/midia.py`, `modulos/__init__.py`, `templates/chamada.html` (novo), `index.html`, `noticias.html`, `blocos.html`, `admin_conteudo_editor.html`, `admin_conteudo_previa.html`, `admin_conteudos.html`, `static/destino-editor.js` (novo), `static/limpo.css`, `tests/*`.

### Testes executados (resultados reais)
- `python3 -I tests/verificacoes_portal.py`: 225 verificações, todas passaram (suíte anterior; 8 asserções atualizadas ao novo contrato).
- `python3 -I tests/verificacoes_exibicao.py`: 81 verificações, todas passaram (modos, sem vazamento do nome interno, busca, destinos válidos/inválidos/removidos, migração, CSRF/login, sanitização, prévia, duplicar).
- `python3 -I tests/migracao_antes_depois.py <versão-anterior>`: 49 verificações. Banco criado pela versão anterior aberto pela nova: nenhuma linha perdida, nenhum valor alterado, cópia pré-migração idêntica.
- `python3 -m unittest discover -s tests`: passa.
- Chromium (desktop 1366 e celular 390): página inicial nos três modos, listagem de notícias, matéria, lista de Conteúdos, editor; sem rolagem horizontal; erro de salvamento mostra mensagem e mantém o que foi digitado. Capturas em `docs/capturas/`.
- **Não executado:** axe-core/leitor de tela, Firefox/Safari, celular físico, restauração de backup em outra máquina.

### Limitações e decisões pendentes
1. O título editorial da notícia é o título público da chamada (não há `titulo_publico` separado nelas).
2. Cabeçalhos dos cartões-contêiner (Sistemas, Atalhos, Ramais, Últimas notícias, Comunicados) continuam sendo títulos de seção editáveis pelo administrador; só os itens/chamadas seguem os modos.
3. No cartão de texto e imagem, o texto formatado (área 6) é conteúdo e sempre aparece.
4. Crédito da imagem não foi implementado (legenda existe só em notícia). Troca de tipo de conteúdo (cartão↔notícia) no editor não foi implementada.
5. Arquivos soltos na raiz e scripts sem uso seguem aguardando sua confirmação para remoção.
6. Em telas estreitas, a vitrine em grade na lateral com 3 colunas fica apertada; use 1–2 colunas.

### Backup, implantação e rollback
1. Backup em Administração → Backup (guardar fora da pasta). 2. Copiar a pasta do portal. 3. Extrair o zip por cima e `./atualizar.sh`. 4. Na primeira subida surge `dados.db.pre-exibicao-v1`.
Rollback: parar o serviço, restaurar os arquivos da cópia e, se desejar, `dados.db.pre-exibicao-v1` → `dados.db`. Mesmo sem restaurar o banco, a versão anterior roda: colunas novas são ignoradas.
