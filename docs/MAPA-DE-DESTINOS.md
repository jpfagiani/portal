# Mapa de destinos do clique (Fase 1)

Evidência de código para cada item que vira link na página inicial. Valores "se vazio" e "abre em" são os de hoje.

| Tipo | Onde se edita | Campo | Se vazio | Onde o clique é construído | Abre em |
|---|---|---|---|---|---|
| Notícia | Conteúdos → Notícia | `noticias.destino_url` | abre `/noticias/<slug>` | `templates/index.html` (`a.not-item`, `a.not-chamada`) | nova aba só se começa com http |
| Cartão de texto e imagem | Conteúdos → Cartão | `cartao_conteudo.url` | sem link | `templates/index.html` (`a.cartao-overlay`) | nova aba só se http |
| Comunicado | Conteúdos → Comunicado | `lateral.url` + `lateral.url_rot` | sem link | `templates/blocos.html` (imagem, botão "Abrir", `com-overlay`) | sempre nova aba |
| Sistema | Sistemas e atalhos | `links.url` | ladrilho sem link | `templates/blocos.html` (`a.ladrilho`) | sempre nova aba |
| Atalho | Sistemas e atalhos | `links.url` | sem link | `templates/blocos.html` (`a.atalho`) | sempre nova aba |
| Banner | Banner | `banners.url` | sem link | `templates/index.html` (`a.slide-link`) | sempre nova aba |
| Bloco de página | Páginas do menu | `pagina_blocos.url` | sem link | `app.py` (`agrupar_blocos`) | conforme o endereço |
| Link no texto | Editor de texto | `<a href>` | — | `app.py` (`limpa_html`) | nova aba se externo |
| Ramais | Ramais | — | — | só o título do cartão leva à lista | mesma aba |

## Lacunas em relação à especificação
1. Seis campos de destino em seis tabelas, sem regra única; só notícia, cartão de texto e comunicado têm a lista de páginas.
2. Link interno abre em nova aba em comunicados, sistemas, atalhos e banners.
3. `endereco_seguro` assume `http://` quando falta esquema (`ramais` vira `http://ramais`).
4. Destino quebrado (notícia excluída) não é detectado; o visitante vê 404.
5. Imagem do cartão e capa são a mesma coluna (`noticias.capa`).
6. Blocos de página: texto, imagem, subtítulo e botão; sem colunas, citação ou separador.

## Atualização 1.11.0 (regra única)
Cartão de texto, notícia e comunicado usam `modulos/exibicao.py`: `destino_tipo` (padrao | nenhum | interno | noticia | externo), endereço e `nova_aba`.
- Externo: só http/https. Interno: conferido contra rotas e notícias publicadas. Destino que não existe mais = sem link.
- Padrão: notícia → a própria página; cartão e comunicado → sem link. Registros antigos (`destino_tipo` vazio): tipo inferido do endereço; externo abre em nova aba, interno na mesma (inclusive comunicados — antes sempre nova aba).
- Nova aba: `rel="noopener noreferrer"`. O endereço nunca é exibido ao visitante.
- Ainda fora desta regra (sem mudança): sistemas, atalhos, banner e blocos de página (`links.url`, `banners.url`, `pagina_blocos.url`).
