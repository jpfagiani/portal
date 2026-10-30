"""Conteúdos: uma única área para localizar, criar, editar, pré-visualizar e
publicar os textos do portal.

Há três tipos, que continuam guardados nas tabelas de sempre (nada é migrado):

  cartao      cartão de texto e imagem          (cartoes_painel + cartao_conteudo)
  noticia     notícia / matéria                 (noticias)
  comunicado  item de um cartão de comunicados  (lateral)

A interface é uma só — lista com busca e filtros, e um editor compartilhado.
Cada tipo mostra só os campos que lhe dizem respeito, e o salvamento é
encaminhado ao serviço do tipo, que mantém as regras de sempre (limpeza de HTML,
validação de endereço, envio de arquivos, publicação e agendamento).
"""
import os
import secrets
from datetime import datetime

from flask import abort, flash, jsonify, redirect, render_template, request, session, url_for
from markupsafe import Markup

import app as nucleo
from . import auditoria, cartoes as mc, exibicao as ex, midia, noticias as mn

app = nucleo.app

TIPOS = {'cartao': 'Cartão', 'noticia': 'Notícia', 'comunicado': 'Comunicado'}
SITUACOES = {'visivel': 'Visível', 'oculto': 'Oculto', 'publicado': 'Publicada',
             'agendado': 'Agendada', 'rascunho': 'Rascunho', 'arquivado': 'Arquivado'}

auditoria._IGNORAR.add('conteudos_previa')      # pré-visualizar não altera nada


# ── utilidades ────────────────────────────────────────────────────────────────

def _volta(padrao=None):
    """Endereço de retorno vindo da URL, só se for do próprio portal."""
    v = request.values.get('volta', '')
    if v.startswith('/') and not v.startswith('//') and '\\' not in v:
        return v
    return padrao or url_for('conteudos')


def _erro(msg, codigo=400):
    return jsonify(ok=False, erro=msg), codigo


def _agora():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _texto_curto(html_ou_texto, n=90):
    t = nucleo.so_texto(html_ou_texto) if '<' in (html_ou_texto or '') else (html_ou_texto or '')
    t = ' '.join(t.split())
    return t if len(t) <= n else t[:n - 1] + '…'


def _casa(valor, q):
    return q.lower() in (valor or '').lower()


# ── listagem ──────────────────────────────────────────────────────────────────

def _destino_estado(tipo, url, nova, padrao=''):
    """Resumo do destino para a listagem: 'quebrado' se aponta para algo que não existe mais."""
    return ex.resolve(tipo, url, nova, padrao=padrao)['quebrado']


def _linhas():
    """Todas as linhas de gerenciamento. O NOME ADMINISTRATIVO é o rótulo principal aqui — é para isso
    que ele existe; o que o visitante vê (título público) aparece à parte, na linha de apoio."""
    con = nucleo.db()
    saida = []
    for r in con.execute(
            "SELECT p.chave,p.nome,p.ativo,k.* FROM cartoes_painel p"
            " JOIN cartao_conteudo k ON k.chave=p.chave WHERE p.tipo='conteudo' ORDER BY p.ordem,p.id"):
        modo = ex.modo_das_flags(r['exibir_titulo'], r['exibir_texto_apoio'])
        publico = (r['titulo_publico'] or '').strip()
        saida.append(dict(tipo='cartao', id=r['chave'], titulo=r['nome'],
                          extra=' · '.join(x for x in (ex.MODOS[modo], ('Título público: ' + publico) if publico else '',
                                                       _texto_curto(r['html'], 60)) if x),
                          busca=' '.join((publico, r['texto_apoio'] or '', nucleo.so_texto(r['html'] or ''))),
                          situacao='visivel' if r['ativo'] else 'oculto', atualizado='', ordem=0,
                          onde='Página inicial', quebrado=_destino_estado(r['destino_tipo'], r['url'], r['nova_aba'])))
    nomes = {c['chave']: c['nome'] for c in nucleo.cartoes_do_painel()}
    for r in con.execute('SELECT * FROM lateral WHERE cartao<>\'\' ORDER BY cartao, ordem, id'):
        modo = ex.modo_das_flags(r['exibir_titulo'], r['exibir_texto_apoio'])
        publico = (r['titulo'] or '').strip()
        saida.append(dict(tipo='comunicado', id=r['id'],
                          titulo=r['nome_admin'] or publico or _texto_curto(r['conteudo'], 60) or '(sem nome)',
                          extra=' · '.join(x for x in (ex.MODOS[modo], ('Título público: ' + publico) if publico and r['nome_admin'] else '',
                                                       _texto_curto(r['conteudo'], 60)) if x),
                          busca=' '.join((publico, r['conteudo'] or '')),
                          situacao='visivel' if r['ativo'] else 'oculto',
                          atualizado='', ordem=r['ordem'], onde=nomes.get(r['cartao'], r['cartao']),
                          cartao=r['cartao'], quebrado=_destino_estado(r['destino_tipo'], r['url'], r['nova_aba'])))
    for n in con.execute(f'SELECT * FROM noticias ORDER BY {mn.ORDEM}'):
        s = mn.situacao(n)
        chave = {'Publicada': 'publicado', 'Agendada': 'agendado', 'Rascunho': 'rascunho',
                 'Arquivado': 'arquivado'}.get(s, n['estado'])
        modo = ex.modo_das_flags(n['exibir_titulo'], n['exibir_texto_apoio'])
        saida.append(dict(tipo='noticia', id=n['id'], titulo=n['nome_admin'] or n['titulo'],
                          extra=' · '.join(x for x in (n['categoria'] or '', ex.MODOS[modo],
                                                       ('Título: ' + n['titulo']) if n['nome_admin'] else '') if x),
                          busca=' '.join((n['titulo'], n['resumo'] or '', n['subtitulo'] or '', n['categoria'] or '')),
                          situacao=chave, atualizado=(n['atualizado_em'] or '')[:16], ordem=n['ordem'],
                          onde='Últimas notícias', destaque=bool(n['destaque']), slug=n['slug'],
                          quebrado=_destino_estado(n['destino_tipo'], n['destino_url'], n['nova_aba'], '/noticias/' + n['slug'])))
    return saida


def _acao_cartao():
    """Ações sobre os cartões da página inicial, feitas na própria tela de Conteúdos."""
    con = nucleo.db()
    acao = request.form.get('acao')
    chave = request.form.get('cartao') or ''
    if acao == 'novo_cartao':
        nova = nucleo._proxima_chave_cartao(con)
        ordem = con.execute('SELECT COALESCE(MAX(ordem),0)+1 FROM cartoes_painel').fetchone()[0]
        con.execute("INSERT INTO cartoes_painel (chave,nome,icone,regiao,largura,coluna,ordem,tipo,ativo)"
                    " VALUES (?,?,'prancheta','baixo',1,0,?,'itens',1)",
                    (nova, 'Cartão ' + nova.replace('cartao', ''), ordem))
        nucleo._semear_aparencia(con, nova)
        con.commit()
        flash('Cartão criado. Arraste-o no Mapa do painel para posicioná-lo.', 'ok')
        return redirect(url_for('conteudos', tipo='comunicado', cartao=nova))
    if acao == 'aparencia_cartao':
        nucleo.salvar_aparencia_cartao(chave or 'noticias')
        return redirect(_volta(url_for('conteudos')) + ('#c-' + chave if chave else ''))
    if not nucleo.cartao_por_chave(chave):
        abort(400)
    if acao == 'titulo_cartao':
        if (request.form.get('titulo_cartao') or '').strip():
            nucleo.salvar_nome_cartao_painel(chave)
        else:
            flash('O nome do cartão não pode ficar em branco.', 'erro')
    elif acao == 'excluir_cartao':
        itens = con.execute("SELECT COUNT(*) FROM cartoes_painel WHERE tipo='itens'").fetchone()[0]
        if not con.execute("SELECT 1 FROM cartoes_painel WHERE chave=? AND tipo='itens'", (chave,)).fetchone():
            flash('Só cartões de comunicados podem ser excluídos aqui.', 'erro')
        elif itens <= 1:
            flash('Este é o último cartão de comunicados — crie outro antes de excluí-lo.', 'erro')
        else:
            for linha in con.execute('SELECT imagem, video FROM lateral WHERE cartao=?', (chave,)):
                nucleo.remove_upload(linha['imagem'])
                nucleo.remove_upload(linha['video'])
            con.execute('DELETE FROM lateral WHERE cartao=?', (chave,))
            con.execute("DELETE FROM cartoes_painel WHERE chave=? AND tipo='itens'", (chave,))
            con.commit()
            flash('Cartão e itens removidos.', 'ok')
        return redirect(url_for('conteudos') + '#cartoes')
    return redirect(url_for('conteudos') + '#c-' + chave)


@app.route('/admin/conteudos', methods=['GET', 'POST'])
@nucleo.admin_obrigatorio
def conteudos():
    if request.method == 'POST':
        return _acao_cartao()
    q = (request.args.get('q') or '').strip()
    tipo = request.args.get('tipo') if request.args.get('tipo') in TIPOS else ''
    sit = request.args.get('situacao') if request.args.get('situacao') in SITUACOES else ''
    cartao = request.args.get('cartao') or ''
    cartao = cartao if (tipo == 'comunicado' and nucleo.cartao_por_chave(cartao)) else ''
    linhas = [l for l in _linhas()
              if (not tipo or l['tipo'] == tipo) and (not sit or l['situacao'] == sit)
              and (not cartao or l.get('cartao') == cartao)
              and (not q or _casa(l['titulo'], q) or _casa(l['extra'], q) or _casa(l.get('busca'), q))]
    for l in linhas:
        l['rotulo_tipo'] = TIPOS[l['tipo']]
        l['rotulo_situacao'] = SITUACOES.get(l['situacao'], l['situacao'])
    cartoes_itens = [c for c in nucleo.cartoes_do_painel() if c['tipo'] == 'itens']
    return render_template('admin_conteudos.html', linhas=linhas, tipos=TIPOS, situacoes=SITUACOES,
                           filtro_tipo=tipo, filtro_sit=sit, q=q, cartoes_itens=cartoes_itens,
                           ordenavel=((tipo == 'noticia' or (tipo == 'comunicado' and cartao)) and not sit and not q),
                           url_ordenar=(url_for('admin_noticias') if tipo == 'noticia'
                                        else url_for('admin_lateral', cartao=cartao)),
                           filtro_cartao=cartao, cartoes=nucleo.cartoes_para_gerenciar(),
                           fontes=nucleo.FONTES_TEXTO, noticias_vitrine=mn.vitrine())


# ── leitura de um conteúdo para o editor ──────────────────────────────────────

def _destino_form(tipo, url, nova, padrao_externo_nova=True):
    """Valores do bloco "Destino do clique" para o formulário, inclusive de registros antigos
    (destino_tipo vazio): o tipo sai do endereço e a nova aba segue a regra de sempre."""
    tipo, url = (tipo or ''), (url or '')
    if not tipo:
        tipo = 'padrao' if not url else ('interno' if url.startswith('/') else 'externo')
        if tipo == 'interno' and url.startswith('/noticias/'):
            tipo = 'noticia'
    if nova is None or nova == -1:
        nova = tipo == 'externo' and padrao_externo_nova
    return dict(destino_tipo=tipo, destino_valor=url, nova_aba=bool(nova))


def _obter(tipo, ident):
    """Dicionário com os valores do formulário, ou None se não existir."""
    con = nucleo.db()
    if tipo == 'cartao':
        r = con.execute("SELECT p.chave,p.nome,k.* FROM cartoes_painel p"
                        " JOIN cartao_conteudo k ON k.chave=p.chave WHERE p.chave=? AND p.tipo='conteudo'",
                        (ident,)).fetchone()
        if not r:
            return None
        return dict(id=r['chave'], nome_admin=r['nome'], titulo_publico=r['titulo_publico'], texto_apoio=r['texto_apoio'],
                    corpo=nucleo.limpa_html(r['html']), imagem=r['imagem'], alt=r['alt_imagem'],
                    modo=ex.modo_das_flags(r['exibir_titulo'], r['exibir_texto_apoio']),
                    **_destino_form(r['destino_tipo'], r['url'], r['nova_aba']))
    if tipo == 'noticia':
        r = con.execute('SELECT * FROM noticias WHERE id=?', (nucleo._int(ident),)).fetchone()
        if not r:
            return None
        d = dict(r)
        d['corpo'] = nucleo.limpa_html(d['corpo'])
        d['publicar_em_campo'] = mn._para_campo(d['publicar_em'])
        d['situacao'] = mn.situacao(r)
        d['modo'] = ex.modo_das_flags(r['exibir_titulo'], r['exibir_texto_apoio'])
        d['alt'] = r['capa_alt']
        d['imagem'] = r['capa']
        d.update(_destino_form(r['destino_tipo'], r['destino_url'], r['nova_aba']))
        return d
    if tipo == 'comunicado':
        r = con.execute('SELECT * FROM lateral WHERE id=?', (nucleo._int(ident),)).fetchone()
        if not r:
            return None
        d = dict(r)
        d['modo'] = ex.modo_das_flags(r['exibir_titulo'], r['exibir_texto_apoio'])
        d['alt'] = r['alt_imagem']
        d.update(_destino_form(r['destino_tipo'], r['url'], r['nova_aba']))
        return d
    return None


def _valores_novos(tipo):
    base = dict(id='', nome_admin='', modo='imagem_titulo', alt='', destino_tipo='padrao', destino_valor='', nova_aba=False)
    if tipo == 'cartao':
        return dict(base, titulo_publico='', texto_apoio='', corpo='', imagem='')
    if tipo == 'noticia':
        return dict(base, titulo='', subtitulo='', resumo='', corpo='', capa='', imagem='', capa_alt='', legenda='',
                    categoria='', estado='rascunho', publicar_em_campo='', destaque=0, meta='',
                    slug='', titulo_fonte='', titulo_cor='', titulo_tam='', situacao='Rascunho')
    return dict(base, modo='imagem_titulo_texto', titulo='', conteudo='', url='', url_rot='', imagem='', video='', img_pos='topo',
                urgencia='informacao', destaque='nenhum', data='', titulo_cor='', texto_cor='', fundo_cor='',
                titulo_tam='', texto_tam='', tipo='aviso', ativo=1)


@app.route('/admin/conteudos/<tipo>/<ident>')
@nucleo.admin_obrigatorio
def conteudos_editor(tipo, ident):
    if tipo not in TIPOS:
        abort(404)
    novo = ident == 'novo'
    d = _valores_novos(tipo) if novo else _obter(tipo, ident)
    if d is None:
        abort(404)
    cartao_chave = ''
    if tipo == 'comunicado':
        cartao_chave = d.get('cartao') if not novo else (request.args.get('cartao') or '')
        c = nucleo.cartao_por_chave(cartao_chave)
        if not c or c['tipo'] != 'itens':
            c = next((x for x in nucleo.cartoes_do_painel() if x['tipo'] == 'itens'), None)
            if not c:
                abort(404)
            cartao_chave = c['chave']
    return render_template(
        'admin_conteudo_editor.html', tipo=tipo, rotulo=TIPOS[tipo], novo=novo, d=d,
        cartao_chave=cartao_chave, volta=_volta(),
        estados=mn.ESTADOS, categorias=mn.categorias(), fontes=nucleo.FONTES_TEXTO,
        destinos_links=nucleo.destinos_de_links(), destaques=nucleo.DESTAQUES_COMUNICADO,
        destinos_paginas=ex.destinos_paginas(), destinos_noticias=ex.destinos_noticias(),
        img_pos=nucleo.CARTAO_IMG_POS, paleta=nucleo.PALETA,
        cartoes_itens=[c for c in nucleo.cartoes_do_painel() if c['tipo'] == 'itens'])


# ── salvamento (um serviço por tipo) ──────────────────────────────────────────

class Invalido(Exception):
    pass


def _destino(f):
    """Destino do clique validado no servidor (a validação do navegador não vale como proteção)."""
    try:
        return ex.le_destino(f)
    except ex.DestinoInvalido as e:
        raise Invalido(str(e))


def _apresentacao(f, padrao, tem_imagem, alt):
    """Modo de apresentação pública e o par de flags que ele grava."""
    modo = ex.modo_do_form(f, padrao)
    try:
        ex.confere_modo(modo, tem_imagem, alt)
    except ex.DestinoInvalido as e:
        raise Invalido(str(e))
    return (modo,) + ex.flags_do_modo(modo)


def _salva_cartao(f, ident):
    con = nucleo.db()
    nome = f.get('nome_admin', '').strip()[:80]
    if not nome:
        raise Invalido('Informe o nome interno do cartão (só aparece aqui no painel, nunca no portal).')
    html = nucleo.limpa_html(f.get('corpo', ''))
    titulo_pub = f.get('titulo_publico', '').strip()[:200]
    apoio = f.get('texto_apoio', '').strip()[:600]
    atual = con.execute('SELECT imagem FROM cartao_conteudo WHERE chave=?', (ident,)).fetchone() if ident else None
    if ident and not con.execute("SELECT 1 FROM cartoes_painel WHERE chave=? AND tipo='conteudo'", (ident,)).fetchone():
        raise Invalido('Cartão não encontrado.')
    imagem = _capa_noticia(f, atual['imagem'] if atual else '')
    alt = f.get('alt_imagem', '').strip()[:300]
    modo, exibir_t, exibir_x = _apresentacao(f, 'imagem_titulo', bool(imagem) or '<img' in html,
                                             alt if imagem else 'ok')
    d_tipo, d_url, nova = _destino(f)
    # titulo_visivel acompanha exibir_titulo: quem voltar à versão anterior continua com o cartão coerente.
    colunas = ('html,titulo_visivel,url,titulo_publico,texto_apoio,exibir_titulo,exibir_texto_apoio,'
               'imagem,alt_imagem,destino_tipo,nova_aba').split(',')
    valores = (html, exibir_t, d_url, titulo_pub, apoio, exibir_t, exibir_x, imagem, alt, d_tipo, nova)
    if ident:
        con.execute('UPDATE cartoes_painel SET nome=? WHERE chave=?', (nome, ident))
        con.execute('INSERT INTO cartao_conteudo (chave,' + ','.join(colunas) + ') VALUES (' + ','.join('?' * 12) + ')'
                    ' ON CONFLICT(chave) DO UPDATE SET ' + ','.join(f'{c}=excluded.{c}' for c in colunas),
                    (ident,) + valores)
        chave = ident
    else:
        chave = 'conteudo-' + secrets.token_hex(4)
        ordem = con.execute('SELECT COALESCE(MAX(ordem),0)+1 FROM cartoes_painel').fetchone()[0]
        pos = mc.vaga_livre(con) if nucleo.layout_livre_ativo() else {'gx': 0, 'gy': 0, 'gw': 0, 'gh': 0}
        con.execute("INSERT INTO cartoes_painel (chave,nome,icone,regiao,largura,coluna,ordem,tipo,ativo,gx,gy,gw,gh)"
                    " VALUES (?,?,'prancheta','baixo',1,0,?,'conteudo',1,?,?,?,?)",
                    (chave, nome, ordem, pos['gx'], pos['gy'], pos['gw'], pos['gh']))
        con.execute('INSERT INTO cartao_conteudo (chave,' + ','.join(colunas) + ') VALUES (' + ','.join('?' * 12) + ')',
                    (chave,) + valores)
    con.commit()
    return chave


def _capa_noticia(f, atual):
    """Capa enviada, escolhida na biblioteca ou removida (nesta ordem)."""
    arq = request.files.get('imagem')
    try:
        if arq and arq.filename:
            capa = midia._salva_imagem(arq)
            midia.registrar_arquivo(capa, arq.filename, os.path.getsize(midia._caminho(capa)))
            return capa
        escolhida = os.path.basename(f.get('imagem_biblioteca', '') or '')
        if escolhida and midia.registrada(escolhida):
            return escolhida
    except ValueError as e:
        raise Invalido(str(e))
    return '' if f.get('remover_imagem') else atual


def _salva_noticia(f, ident):
    con = nucleo.db()
    atual = con.execute('SELECT * FROM noticias WHERE id=?', (ident,)).fetchone() if ident else None
    if ident and not atual:
        raise Invalido('Notícia não encontrada.')
    acao = f.get('acao', 'salvar')
    titulo = f.get('titulo', '').strip()[:200]
    if not titulo:
        raise Invalido('Informe o título.')
    # Salvar nunca publica sozinho: só o botão Publicar (ou a situação escolhida).
    estado = f.get('estado') if f.get('estado') in mn.ESTADOS else 'rascunho'
    if acao == 'rascunho':
        estado = 'rascunho'
    elif acao == 'publicar':
        estado = 'publicado'
    publicar_em = mn._para_banco(f.get('publicar_em'))
    if estado == 'publicado' and not publicar_em:
        publicar_em = _agora()
    capa = _capa_noticia(f, atual['capa'] if atual else '')
    capa_alt = f.get('capa_alt', '').strip()[:300]
    modo, exibir_t, exibir_x = _apresentacao(f, 'imagem_titulo', bool(capa), capa_alt)
    d_tipo, d_url, nova = _destino(f)
    slug = mn._slug_livre(con, mn.slugify(f.get('slug') or titulo), ident or 0)
    dados = (slug, titulo, f.get('subtitulo', '').strip()[:300], f.get('resumo', '').strip()[:600],
             nucleo.limpa_html(f.get('corpo', '')), capa, capa_alt,
             f.get('legenda', '').strip()[:300], f.get('categoria', '').strip()[:60], estado, publicar_em,
             1 if f.get('em_destaque') else 0, d_url,
             f.get('meta', '').strip()[:300]) + mn._titulo_do_form(f)
    if atual:
        if dados[11] and not atual['destaque']:
            con.execute('UPDATE noticias SET ordem=? WHERE id=?', (mn._topo(con), ident))
        con.execute("UPDATE noticias SET slug=?,titulo=?,subtitulo=?,resumo=?,corpo=?,capa=?,capa_alt=?,"
                    "legenda=?,categoria=?,estado=?,publicar_em=?,destaque=?,destino_url=?,meta=?,"
                    "titulo_fonte=?,titulo_cor=?,titulo_tam=?,atualizado_em=datetime('now','localtime')"
                    " WHERE id=?", dados + (ident,))
        novo = ident
    else:
        novo = con.execute(
            "INSERT INTO noticias (slug,titulo,subtitulo,resumo,corpo,capa,capa_alt,legenda,categoria,estado,"
            "publicar_em,destaque,destino_url,meta,titulo_fonte,titulo_cor,titulo_tam,autor,ordem)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            dados + (session.get('nome') or session.get('user', ''), mn._topo(con))).lastrowid
    con.execute('UPDATE noticias SET nome_admin=?, exibir_titulo=?, exibir_texto_apoio=?, destino_tipo=?, nova_aba=? WHERE id=?',
                (f.get('nome_admin', '').strip()[:120], exibir_t, exibir_x, d_tipo, nova, novo))
    con.commit()
    return novo


def _salva_comunicado(f, ident):
    con = nucleo.db()
    atuais = con.execute('SELECT * FROM lateral WHERE id=?', (ident,)).fetchone() if ident else None
    if ident and not atuais:
        raise Invalido('Comunicado não encontrado.')
    chave = atuais['cartao'] if atuais else f.get('cartao', '')
    c = nucleo.cartao_por_chave(chave)
    if not c or c['tipo'] != 'itens':
        raise Invalido('Escolha o cartão onde o comunicado aparece.')
    ant_img = atuais['imagem'] if atuais else ''
    ant_vid = atuais['video'] if atuais else ''
    # Tudo o que pode recusar o salvamento é conferido ANTES de mexer em arquivos: um erro de
    # validação não pode apagar a imagem anterior nem deixar um envio órfão.
    d_tipo, d_url, nova = _destino(f)
    arq_img, arq_vid = request.files.get('imagem'), request.files.get('video')
    tem_img = bool(arq_img and arq_img.filename) or bool(ant_img and not f.get('remover_imagem'))
    tem_vid = bool(arq_vid and arq_vid.filename) or bool(ant_vid and not f.get('remover_video'))
    alt = f.get('alt_imagem', '').strip()[:300]
    modo, exibir_t, exibir_x = _apresentacao(f, 'imagem_titulo_texto', tem_img, alt)
    texto = f.get('texto', '').strip('\r\n').rstrip()
    if not (f.get('titulo', '').strip() or texto or d_url or tem_img or tem_vid):
        raise Invalido('Preencha ao menos um destes: título, texto, destino, imagem ou vídeo.')
    try:
        imagem = nucleo.salva_upload('imagem', ant_img)
        video = nucleo.salva_upload('video', ant_vid, nucleo.VIDEO_EXTS)
    except ValueError as e:
        raise Invalido(str(e))
    for novo, ant in ((imagem, ant_img), (video, ant_vid)):
        if novo != ant:
            nucleo.remove_upload(ant)
    if f.get('remover_imagem'):
        nucleo.remove_upload(imagem)
        imagem = ''
    if f.get('remover_video'):
        nucleo.remove_upload(video)
        video = ''
    urg = f.get('urgencia', 'informacao')
    dest = f.get('destaque', 'nenhum')

    def medida(campo):
        return nucleo.medida(f.get(campo), '', 0.6, 2.0) if f.get(campo, '').strip() else ''
    dados = (atuais['tipo'] if atuais else 'aviso', f.get('titulo', '').strip(), texto,
             d_url,
             1 if f.get('ativo') else 0,
             urg if urg in ('urgente', 'comunicado', 'informacao') else 'informacao',
             dest if dest in nucleo.DESTAQUES_COMUNICADO else 'nenhum',
             medida('titulo_tam'), nucleo.cor_hexa(f.get('titulo_cor'), ''),
             medida('texto_tam'), nucleo.cor_hexa(f.get('texto_cor'), ''),
             nucleo.cor_hexa(f.get('fundo_cor'), ''), f.get('data', '').strip(), imagem, video,
             f.get('url_rot', '').strip(),
             f.get('img_pos') if f.get('img_pos') in nucleo.CARTAO_IMG_POS else 'topo',
             f.get('nome_admin', '').strip()[:120], exibir_t, exibir_x, alt, d_tipo, nova)
    campos = ('tipo,titulo,conteudo,url,ativo,urgencia,destaque,titulo_tam,titulo_cor,texto_tam,texto_cor,'
              'fundo_cor,data,imagem,video,url_rot,img_pos,nome_admin,exibir_titulo,exibir_texto_apoio,'
              'alt_imagem,destino_tipo,nova_aba').split(',')
    if atuais:
        con.execute('UPDATE lateral SET ' + ','.join(k + '=?' for k in campos) + ' WHERE id=?', dados + (ident,))
        novo = ident
    else:
        ordem = con.execute('SELECT COALESCE(MAX(ordem),-1)+1 FROM lateral WHERE cartao=?', (chave,)).fetchone()[0]
        novo = con.execute('INSERT INTO lateral (' + ','.join(campos) + ',ordem,cartao) VALUES ('
                           + ','.join('?' * (len(campos) + 2)) + ')', dados + (ordem, chave)).lastrowid
    con.commit()
    return novo


SALVAR = {'cartao': _salva_cartao, 'noticia': _salva_noticia, 'comunicado': _salva_comunicado}


@app.route('/admin/conteudos/salvar', methods=['POST'])
@nucleo.admin_obrigatorio
def conteudos_salvar():
    tipo = request.form.get('tipo', '')
    if tipo not in SALVAR:
        return _erro('Tipo de conteúdo desconhecido.')
    ident = request.form.get('id', '').strip()
    if tipo != 'cartao':
        ident = nucleo._int(ident)
    try:
        novo = SALVAR[tipo](request.form, ident)
    except (Invalido, ex.DestinoInvalido) as e:
        return _erro(str(e))
    acao = request.form.get('acao', 'salvar')
    msg = {'publicar': 'Publicada.', 'rascunho': 'Rascunho salvo.'}.get(acao, 'Salvo.')
    return jsonify(ok=True, id=novo, mensagem=msg,
                   editar=url_for('conteudos_editor', tipo=tipo, ident=novo, volta=request.form.get('volta') or None))


# ── pré-visualização (não grava nada) ─────────────────────────────────────────

@app.route('/admin/conteudos/previa', methods=['POST'])
@nucleo.admin_obrigatorio
def conteudos_previa():
    tipo = request.form.get('tipo', '')
    if tipo not in TIPOS:
        return _erro('Tipo de conteúdo desconhecido.')
    f = request.form
    ident = f.get('id', '')
    con = nucleo.db()
    corpo = Markup(nucleo.agrupa_figuras(nucleo.limpa_html(f.get('corpo', ''))))

    def imagem_atual(sql, chave, coluna):
        """Imagem que o item terá: a gravada, a escolhida na biblioteca, nenhuma, ou 'pendente' (envio novo)."""
        img = ''
        if ident:
            r = con.execute(sql, (chave,)).fetchone()
            img = r[coluna] if r else ''
        escolhida = os.path.basename(f.get('imagem_biblioteca', '') or '')
        if escolhida and midia.registrada(escolhida):
            img = escolhida
        if f.get('remover_imagem'):
            img = ''
        if f.get('imagem_nova') and not img:
            img = 'pendente'
        return img

    def destino():
        try:
            t, u, n = ex.le_destino(f)
        except ex.DestinoInvalido:
            return None            # a prévia não reclama; o erro sai ao salvar
        return t, u, n

    if tipo in ('cartao', 'noticia'):
        modo = ex.modo_do_form(f, 'imagem_titulo')
        et, ex_ = ex.flags_do_modo(modo)
        d = destino()
        padrao = ''
        if tipo == 'cartao':
            img = imagem_atual('SELECT imagem FROM cartao_conteudo WHERE chave=?', ident, 'imagem')
            it = ex.monta(exibir_titulo=et, titulo=f.get('titulo_publico', ''), exibir_texto=ex_, texto=f.get('texto_apoio', ''),
                          imagem=img, alt=f.get('alt_imagem', ''),
                          destino=ex.resolve(*d) if d else None, html=corpo)
            return jsonify(ok=True, html=render_template('admin_conteudo_previa.html', tipo=tipo, it=it))
        img = imagem_atual('SELECT capa FROM noticias WHERE id=?', nucleo._int(ident), 'capa')
        it = ex.monta(exibir_titulo=et, titulo=f.get('titulo', '').strip(), exibir_texto=ex_,
                      texto=f.get('resumo', '') or f.get('subtitulo', ''), imagem=img, alt=f.get('capa_alt', ''),
                      destino=ex.resolve(*d) if d else None)
        estilo = mn.estilo_titulo(dict(zip(('titulo_fonte', 'titulo_cor', 'titulo_tam'), mn._titulo_do_form(f))))
        return jsonify(ok=True, html=render_template(
            'admin_conteudo_previa.html', tipo=tipo, it=it, titulo=f.get('titulo', '').strip(), corpo=corpo,
            subtitulo=f.get('subtitulo', ''), resumo=f.get('resumo', ''), capa=img, legenda=f.get('legenda', ''),
            capa_alt=f.get('capa_alt', ''), categoria=f.get('categoria', ''), estilo=estilo))

    modo = ex.modo_do_form(f, 'imagem_titulo_texto')
    et, ex_ = ex.flags_do_modo(modo)
    d = destino() or ('padrao', '', 0)
    item = dict(titulo=f.get('titulo', '').strip(), conteudo=f.get('texto', ''),
                url=d[1], destino_tipo=d[0], nova_aba=d[2], url_rot=f.get('url_rot', ''),
                exibir_titulo=et, exibir_texto_apoio=ex_, alt_imagem=f.get('alt_imagem', ''),
                urgencia=f.get('urgencia', 'informacao'), destaque=f.get('destaque', 'nenhum'),
                data=f.get('data', ''), img_pos=f.get('img_pos', 'topo'), tipo='aviso', id=0,
                imagem='', video='', titulo_tam='', titulo_cor=nucleo.cor_hexa(f.get('titulo_cor'), ''),
                texto_tam='', texto_cor=nucleo.cor_hexa(f.get('texto_cor'), ''),
                fundo_cor=nucleo.cor_hexa(f.get('fundo_cor'), ''), img_larg=0, img_x=0)
    if ident:
        r = con.execute('SELECT video FROM lateral WHERE id=?', (nucleo._int(ident),)).fetchone()
        if r:
            item['video'] = r['video']
    item['imagem'] = imagem_atual('SELECT imagem FROM lateral WHERE id=?', nucleo._int(ident), 'imagem')
    if f.get('remover_video'):
        item['video'] = ''
    return jsonify(ok=True, html=render_template('admin_conteudo_previa.html', tipo=tipo, item=item))


# ── excluir e duplicar ────────────────────────────────────────────────────────

@app.route('/admin/conteudos/excluir', methods=['POST'])
@nucleo.admin_obrigatorio
def conteudos_excluir():
    tipo, ident = request.form.get('tipo', ''), request.form.get('id', '')
    con = nucleo.db()
    if tipo == 'cartao':
        if not con.execute("SELECT 1 FROM cartoes_painel WHERE chave=? AND tipo='conteudo'", (ident,)).fetchone():
            return _erro('Conteúdo não encontrado.', 404)
        con.execute('DELETE FROM cartao_conteudo WHERE chave=?', (ident,))
        con.execute('DELETE FROM cartoes_painel WHERE chave=?', (ident,))
    elif tipo == 'noticia':
        # A capa continua na biblioteca: outra publicação pode usá-la.
        con.execute('DELETE FROM noticias WHERE id=?', (nucleo._int(ident),))
    elif tipo == 'comunicado':
        r = con.execute('SELECT imagem,video FROM lateral WHERE id=?', (nucleo._int(ident),)).fetchone()
        if not r:
            return _erro('Conteúdo não encontrado.', 404)
        nucleo.remove_upload(r['imagem'])
        nucleo.remove_upload(r['video'])
        con.execute('DELETE FROM lateral WHERE id=?', (nucleo._int(ident),))
    else:
        return _erro('Tipo de conteúdo desconhecido.')
    con.commit()
    return jsonify(ok=True)


@app.route('/admin/conteudos/duplicar', methods=['POST'])
@nucleo.admin_obrigatorio
def conteudos_duplicar():
    tipo, ident = request.form.get('tipo', ''), request.form.get('id', '')
    con = nucleo.db()
    if tipo == 'cartao':
        nova = mc._duplica(con, ident)
        if not nova:
            return _erro('Este conteúdo não pode ser copiado.')
        con.commit()
        return jsonify(ok=True, id=nova)
    if tipo == 'noticia':
        r = con.execute('SELECT * FROM noticias WHERE id=?', (nucleo._int(ident),)).fetchone()
        if not r:
            return _erro('Conteúdo não encontrado.', 404)
        d = dict(r)
        d.pop('id')
        d.update(titulo=(d['titulo'] + ' (cópia)')[:200], estado='rascunho', publicar_em='', destaque=0,
                 slug=mn._slug_livre(con, mn.slugify(d['titulo'] + ' copia'), 0), ordem=mn._topo(con))
        cols = list(d)
        novo = con.execute(f"INSERT INTO noticias ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                           [d[k] for k in cols]).lastrowid
        con.commit()
        return jsonify(ok=True, id=novo)
    if tipo == 'comunicado':
        r = con.execute('SELECT * FROM lateral WHERE id=?', (nucleo._int(ident),)).fetchone()
        if not r:
            return _erro('Conteúdo não encontrado.', 404)
        d = dict(r)
        d.pop('id')
        d['titulo'] = ((d['titulo'] or 'Sem título') + ' (cópia)')[:200]
        d['ordem'] = con.execute('SELECT COALESCE(MAX(ordem),-1)+1 FROM lateral WHERE cartao=?',
                                 (d['cartao'],)).fetchone()[0]
        d['imagem'] = mc._copia_arquivo(d['imagem'])
        d['video'] = mc._copia_arquivo(d['video'])
        cols = list(d)
        novo = con.execute(f"INSERT INTO lateral ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                           [d[k] for k in cols]).lastrowid
        con.commit()
        return jsonify(ok=True, id=novo)
    return _erro('Tipo de conteúdo desconhecido.')
