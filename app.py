"""
Portal Interno — Centro de Detenção Provisória de Nova Independência/SP

Página inicial com os sistemas usados pela unidade, banner rotativo e barra
lateral de avisos. Tudo (links, banners, avisos, usuários, cores e a imagem
de fundo) é gerenciado pelo administrador na própria interface.

Requisitos: python3, flask, werkzeug. Banco: SQLite (arquivo dados.db).
"""

import io
import os
import re
import secrets
import sqlite3
import zipfile
from datetime import datetime
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, send_file, session, url_for)
from markupsafe import Markup, escape
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DB_PATH    = os.environ.get('INTRANET_DB', os.path.join(BASE_DIR, 'dados.db'))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
UPLOAD_DIR = os.path.join(STATIC_DIR, 'uploads')
KEY_FILE   = os.path.join(BASE_DIR, 'secret.key')
EXT_OK     = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}

# Logo e foto de fundo são arquivos fixos em static/. Basta substituir o
# arquivo (pelo painel ou copiando por cima no servidor) que o site muda — não
# há nome aleatório nem caminho guardado no banco, e nada a alterar no código.
FUNDO_NOMES = ('fundo.jpg', 'fundo.jpeg', 'fundo.png', 'fundo.webp')
LOGO_NOMES  = ('logo.png', 'logo.jpg', 'logo.jpeg', 'logo.webp', 'logo.svg',
               'brasao.png')
# O que o envio de logo pode apagar. `brasao.png` fica de fora: é o brasão que
# acompanha o repositório e o serviço roda dentro do próprio clone — apagar
# arquivo versionado sujaria a árvore e travaria o `git pull` seguinte. Como
# logo_atual() já prefere logo.* a brasao.png, manter o arquivo não muda nada
# na tela e ainda serve de reserva se o logo enviado for removido.
LOGO_ENVIADO = tuple(n for n in LOGO_NOMES if n != 'brasao.png')

# Marca d'água opcional de cada cartão do painel: static/marca-<bloco>.<ext>.
# Trocar o arquivo troca a imagem, como no logo e no fundo.
MARCA_EXTS = ('.png', '.svg', '.webp', '.jpg', '.jpeg')


def marca_atual(bloco):
    return _arquivo_versionado(tuple(f'marca-{bloco}{e}' for e in MARCA_EXTS))


def _arquivo_versionado(nomes, padrao=None):
    """(nome, versão) do primeiro arquivo existente; a versão é a data de
    modificação, para o navegador não mostrar a imagem antiga do cache."""
    for nome in nomes:
        caminho = os.path.join(STATIC_DIR, nome)
        if os.path.isfile(caminho):
            return nome, int(os.path.getmtime(caminho))
    return padrao, 0


def fundo_atual():
    return _arquivo_versionado(FUNDO_NOMES)


def logo_atual():
    return _arquivo_versionado(LOGO_NOMES, padrao='brasao.png')


# ── ícones ─────────────────────────────────────────────────────────────────────

# Desenhos em traçado, sem arquivo externo nem fonte de ícones: o mesmo símbolo
# serve no ladrilho escuro, no menu e no cartão claro porque a cor vem do texto
# (currentColor). Emoji foi o que se usou na primeira versão — cada sistema
# operacional desenha de um jeito e o painel ficava desalinhado.
ICONES = {
    'inicio':     '<path d="M3 10.8 12 3.5l9 7.3"/><path d="M5.3 9.6V20.5h13.4V9.6"/>'
                  '<path d="M9.6 20.5v-6.2h4.8v6.2"/>',
    'telefone':   '<path d="M7.6 3.5H4.8A1.8 1.8 0 0 0 3 5.3c0 8.4 7.3 15.7 15.7 15.7a1.8 '
                  '1.8 0 0 0 1.8-1.8v-2.8l-4.3-1.4-2 2a14.6 14.6 0 0 1-6.2-6.2l2-2z"/>',
    'usuarios':   '<circle cx="9" cy="8" r="3.3"/><path d="M3.2 20.3c0-3.2 2.6-5.4 5.8-5.4'
                  's5.8 2.2 5.8 5.4"/><path d="M16.4 5.1a3.3 3.3 0 0 1 0 6.2"/>'
                  '<path d="M17.6 15.2c2.1.5 3.6 2.2 3.6 5.1"/>',
    'pessoa':     '<circle cx="12" cy="8.2" r="3.8"/><path d="M4.8 20.6c0-3.9 3.2-6.4 '
                  '7.2-6.4s7.2 2.5 7.2 6.4"/>',
    'documento':  '<path d="M13.4 3.2H6.6v17.6h10.8V7.2z"/><path d="M13.4 3.2v4h4"/>'
                  '<path d="M9.4 12.4h5.2M9.4 16h5.2"/>',
    'calendario': '<rect x="3.4" y="5.2" width="17.2" height="15.4" rx="2"/>'
                  '<path d="M3.4 10h17.2M8.2 3.4v3.6M15.8 3.4v3.6"/>',
    'fone':       '<path d="M4 15.5v-3a8 8 0 0 1 16 0v3"/>'
                  '<rect x="2.6" y="14.4" width="4.6" height="6.2" rx="2"/>'
                  '<rect x="16.8" y="14.4" width="4.6" height="6.2" rx="2"/>',
    'arquivo':    '<rect x="2.8" y="4.2" width="18.4" height="4.2" rx="1.2"/>'
                  '<path d="M4.6 8.4v10.2a1.8 1.8 0 0 0 1.8 1.8h11.2a1.8 1.8 0 0 0 '
                  '1.8-1.8V8.4"/><path d="M9.8 12.4h4.4"/>',
    'grafico':    '<path d="M3.4 20.6h17.2"/><path d="M6.6 20.6v-6.4M11.4 20.6V6.8'
                  'M16.2 20.6v-9.6"/>',
    'engrenagem': '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.6v2.6M12 18.8v2.6'
                  'M21.4 12h-2.6M5.2 12H2.6M18.4 5.6l-1.8 1.8M7.4 16.6l-1.8 1.8'
                  'M18.4 18.4l-1.8-1.8M7.4 7.4 5.6 5.6"/>',
    'megafone':   '<path d="M3.4 9.6v4.8h3.4l7.4 4.4V5.2L6.8 9.6z"/>'
                  '<path d="M17.4 9a4.2 4.2 0 0 1 0 6"/><path d="M6.8 14.4v4.2h2.8"/>',
    'sino':       '<path d="M18 9.4a6 6 0 1 0-12 0c0 5.2-2 6.8-2 6.8h16s-2-1.6-2-6.8z"/>'
                  '<path d="M13.7 20a2 2 0 0 1-3.4 0"/>',
    'envelope':   '<rect x="2.8" y="5" width="18.4" height="14" rx="2"/>'
                  '<path d="m3.6 6.4 8.4 6.2 8.4-6.2"/>',
    'lupa':       '<circle cx="10.8" cy="10.8" r="6.4"/><path d="m15.6 15.6 5 5"/>',
    'barras':     '<path d="M3.6 6.6h16.8M3.6 12h16.8M3.6 17.4h16.8"/>',
    'sair':       '<path d="M9.4 20.6H5.6a1.8 1.8 0 0 1-1.8-1.8V5.2a1.8 1.8 0 0 1 '
                  '1.8-1.8h3.8"/><path d="m15.4 16.6 4.8-4.6-4.8-4.6"/><path d="M20.2 12H9"/>',
    'marcador':   '<path d="M6.4 3.6h11.2v17l-5.6-4-5.6 4z"/>',
    'grade':      '<rect x="3.4" y="3.4" width="7" height="7" rx="1.4"/>'
                  '<rect x="13.6" y="3.4" width="7" height="7" rx="1.4"/>'
                  '<rect x="3.4" y="13.6" width="7" height="7" rx="1.4"/>'
                  '<rect x="13.6" y="13.6" width="7" height="7" rx="1.4"/>',
    'escudo':     '<path d="M12 3 4.6 6v6c0 4.5 3.1 8.1 7.4 9.4 4.3-1.3 7.4-4.9 7.4-9.4V6z"/>',
    'bolo':       '<path d="M4.4 13.6c0-1.5 1.2-2.6 2.6-2.6h10c1.4 0 2.6 1.1 2.6 2.6v7H4.4z"/>'
                  '<path d="M12 11V7.8M8.2 11V8.6M15.8 11V8.6"/>'
                  '<path d="M4.4 16.4c1.6 0 1.6 1.4 3.1 1.4s1.6-1.4 3.1-1.4 1.6 1.4 3.1 1.4'
                  ' 1.6-1.4 3.1-1.4 1.6 1.4 3.1 1.4"/>',
    'relogio':    '<circle cx="12" cy="12" r="8.6"/><path d="M12 7v5.3l3.4 2"/>',
    'cifrao':     '<path d="M12 3.4v17.2"/><path d="M16.2 7.2H9.9a2.9 2.9 0 0 0 0 5.8h4.2a2.9'
                  ' 2.9 0 0 1 0 5.8H7.4"/>',
    'raio':       '<path d="M13.4 2.6 4.6 13.6h6.2l-.6 7.8 8.8-11h-6.2z"/>',
    'monitor':    '<rect x="2.8" y="4" width="18.4" height="12.4" rx="2"/>'
                  '<path d="M8.6 20.4h6.8M12 16.4v4"/>',
    'chave':      '<circle cx="7.6" cy="16.4" r="3.6"/>'
                  '<path d="m10.2 13.8 8.4-8.4M16.2 7.8l2 2M13.8 10.2l2 2"/>',
    'cadeado':    '<rect x="4.6" y="10.4" width="14.8" height="10" rx="2"/>'
                  '<path d="M8.2 10.4V7.8a3.8 3.8 0 0 1 7.6 0v2.6"/>',
    'globo':      '<circle cx="12" cy="12" r="8.8"/><path d="M3.2 12h17.6"/>'
                  '<path d="M12 3.2a13.6 13.6 0 0 1 0 17.6 13.6 13.6 0 0 1 0-17.6z"/>',
    'mapa':       '<path d="M12 21.4s6.8-6 6.8-11a6.8 6.8 0 1 0-13.6 0c0 5 6.8 11 6.8 11z"/>'
                  '<circle cx="12" cy="10.2" r="2.6"/>',
    'veiculo':    '<path d="M2.8 16.2V9.4h10.4v6.8"/><path d="M13.2 11.4h3.6l3.4 3.2v1.6h-7z"/>'
                  '<circle cx="7" cy="17.6" r="2"/><circle cx="17" cy="17.6" r="2"/>',
    'camera':     '<path d="M3.4 8.6h3.8l1.4-2.2h6.8l1.4 2.2h3.8v10.2H3.4z"/>'
                  '<circle cx="12" cy="13.4" r="3.4"/>',
    'livro':      '<path d="M4.2 4.4h5.2c1.4 0 2.6 1.1 2.6 2.5v13c0-1.1-1-2-2.2-2H4.2z"/>'
                  '<path d="M19.8 4.4h-5.2c-1.4 0-2.6 1.1-2.6 2.5v13c0-1.1 1-2 2.2-2h5.6z"/>',
    'prancheta':  '<rect x="5.4" y="4.6" width="13.2" height="16" rx="1.8"/>'
                  '<rect x="9" y="2.8" width="6" height="3.6" rx="1.2"/>'
                  '<path d="M9 11.4h6M9 15h6"/>',
    'pasta':      '<path d="M3.4 6.6a1.8 1.8 0 0 1 1.8-1.8h3.8l2 2.6h8.4a1.8 1.8 0 0 1 1.8 '
                  '1.8v9.6a1.8 1.8 0 0 1-1.8 1.8H5.2a1.8 1.8 0 0 1-1.8-1.8z"/>',
    'estrela':    '<path d="m12 3.4 2.7 5.5 6.1.9-4.4 4.3 1 6-5.4-2.9-5.4 2.9 1-6-4.4-4.3'
                  ' 6.1-.9z"/>',
    'balanca':    '<path d="M12 3.6v16.8M6.6 20.4h10.8"/><path d="M12 6.4 4.4 8.2M12 6.4l7.6 '
                  '1.8"/><path d="M4.4 8.2 1.9 14.2h5z"/><path d="M19.6 8.2l-2.5 6h5z"/>',
    'predio':     '<rect x="4.6" y="3.4" width="14.8" height="17.2" rx="1.4"/>'
                  '<path d="M8.4 7.6h2M13.6 7.6h2M8.4 11.6h2M13.6 11.6h2'
                  'M10.4 20.6v-4.4h3.2v4.4"/>',
    'saude':      '<path d="M3 12.4h4l2-4.4 3 9 2.4-6 1.6 3h5"/>',
    'ferramenta': '<path d="M20.2 6.6a5.2 5.2 0 0 1-6.9 6.9l-6.7 6.7a2 2 0 0 1-2.8-2.8l6.7-6.7'
                  'a5.2 5.2 0 0 1 6.9-6.9l-3.1 3.1.9 2.9 2.9.9z"/>',
    'alerta':     '<path d="M12 3.8 2.8 20.2h18.4z"/><path d="M12 9.8v4.6M12 17.4h.01"/>',
    'externo':    '<path d="M14.4 4.6h5v5"/><path d="m19.4 4.6-8 8"/><path d="M18.2 13.6v5.2a'
                  '1.8 1.8 0 0 1-1.8 1.8H5.2a1.8 1.8 0 0 1-1.8-1.8V7.6a1.8 1.8 0 0 1 '
                  '1.8-1.8h5.2"/>',
    'aplicativo': '<rect x="3.4" y="3.4" width="17.2" height="17.2" rx="4"/>'
                  '<circle cx="12" cy="12" r="3.2"/>',
    'confere':    '<circle cx="12" cy="12" r="8.8"/><path d="m8 12.2 2.8 2.8 5.2-5.6"/>',
    'lua':        '<path d="M20.6 14.4A8.8 8.8 0 0 1 9.6 3.4a8.8 8.8 0 1 0 11 11z"/>',
    'sol':        '<circle cx="12" cy="12" r="4.2"/><path d="M12 2.4v2.4M12 19.2v2.4'
                  'M21.6 12h-2.4M4.8 12H2.4M18.8 5.2l-1.7 1.7M6.9 17.1l-1.7 1.7'
                  'M18.8 18.8l-1.7-1.7M6.9 6.9 5.2 5.2"/>',
}

# Escolha explícita de "sem símbolo" — diferente de campo vazio, que significa
# apenas que ninguém escolheu e vale o ícone genérico.
SEM_ICONE = 'nenhum'

# Ícones enviados pelo administrador, em static/icones/. Guardados no banco
# como "arquivo:<nome>" para não colidirem com os nomes do catálogo interno.
ICONES_DIR  = os.path.join(STATIC_DIR, 'icones')
ICONE_ARQ   = 'arquivo:'
ICONE_EXTS  = {'.svg', '.png', '.webp', '.jpg', '.jpeg'}


def icones_enviados():
    """Nomes dos ícones em static/icones/, em ordem alfabética."""
    try:
        return sorted(n for n in os.listdir(ICONES_DIR)
                      if os.path.splitext(n)[1].lower() in ICONE_EXTS)
    except OSError:
        return []


def icone_de_arquivo(valor):
    """Nome do arquivo se `valor` aponta para um ícone enviado que existe.

    Confere a existência para um ícone apagado não deixar imagem quebrada no
    painel — nesse caso o item volta para o símbolo genérico."""
    if not (valor or '').startswith(ICONE_ARQ):
        return None
    nome = secure_filename(valor[len(ICONE_ARQ):])
    if nome and os.path.isfile(os.path.join(ICONES_DIR, nome)):
        return nome
    return None

# A primeira versão guardava emoji nessas colunas. Traduzir aqui evita mexer no
# banco de quem já cadastrou itens — e o menu antigo continua desenhado igual.
EMOJI_ICONE = {
    '⌂': 'inicio', '☎': 'telefone', '👥': 'usuarios', '🗎': 'documento',
    '🗓': 'calendario', '🎧': 'fone', '🗄': 'arquivo', '📊': 'grafico',
    '⚙': 'engrenagem', '📢': 'megafone', '🔖': 'marcador', '🧭': 'grade',
    '🎂': 'bolo', '🛡': 'escudo', '▦': 'grade', '🔑': 'chave', '▸': 'aplicativo',
}


def nome_icone(valor):
    """Nome de ícone válido a partir do que está gravado (nome novo ou emoji).

    'nenhum' é escolha explícita de não mostrar símbolo. Vazio continua sendo
    "não escolheram nada" e cai no genérico — senão todo item já cadastrado
    perderia o ícone de uma vez."""
    valor = (valor or '').strip()
    if valor == SEM_ICONE or valor in ICONES:
        return valor
    if icone_de_arquivo(valor):
        return valor
    return EMOJI_ICONE.get(valor, 'aplicativo')


BACKUP_DIR = os.path.join(BASE_DIR, 'backups')

app = Flask(__name__)
# 64 MB: um backup carrega o banco mais a foto de fundo, o logo e as imagens
# do banner. As imagens avulsas continuam limitadas pela extensão aceita.
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024


def _secret_key():
    """Chave de sessão persistente — sem ela, todo restart desloga os usuários."""
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, 'r') as f:
            k = f.read().strip()
            if k:
                return k
    k = secrets.token_hex(32)
    with open(KEY_FILE, 'w') as f:
        f.write(k)
    os.chmod(KEY_FILE, 0o600)
    return k


app.secret_key = _secret_key()


@app.template_global()
def ic(nome, classe='ic-svg'):
    """Desenha um ícone do catálogo. Nome desconhecido cai no genérico, para um
    item mal cadastrado não deixar um buraco no lugar do símbolo; 'nenhum' não
    desenha nada, que é escolha de quem cadastrou."""
    escolhido = nome_icone(nome)
    if escolhido == SEM_ICONE:
        return Markup('')
    enviado = icone_de_arquivo(escolhido)
    if enviado:
        # Imagem própria: não herda a cor do texto como os desenhos do
        # catálogo, e é isso que se espera de um logo enviado.
        caminho = url_for('static', filename=f'icones/{enviado}')
        return Markup(f'<img class="{escape(classe)} ic-arquivo" '
                      f'src="{escape(caminho)}" alt="" aria-hidden="true">')
    return Markup(
        f'<svg class="{escape(classe)}" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{ICONES[escolhido]}</svg>')


# ── banco ──────────────────────────────────────────────────────────────────────

# A identidade da unidade vem do instalador (variáveis de ambiente) na primeira
# execução; depois disso é editável em Administração → Aparência. Outra unidade
# usa o mesmo código, só respondendo as perguntas da instalação.
PADROES = {
    'site_nome':    os.environ.get('INTRANET_ORG_NOME',
                                   'Centro de Detenção Provisória de Nova Independência'),
    'site_sigla':   os.environ.get('INTRANET_ORG_SIGLA', 'CDPNI'),
    'site_sub':     os.environ.get('INTRANET_ORG_SUB', 'Portal de Sistemas'),
    'cor_primaria': '#1c3d5a',     # azul institucional escuro (coberturas)
    'cor_destaque': '#2f7fb8',     # azul médio — botões e links
    'banner_seg':   '6',           # segundos por slide
    # Textos da capa (as linhas sobre a foto). Título em branco monta
    # "Portal <sigla>" sozinho, então trocar a sigla já arruma a capa.
    # A descrição é dividida em duas linhas para a quebra ser escolhida à mão:
    # deixada ao acaso, ela cai em lugar feio conforme a largura da tela.
    'capa_abertura': 'Bem-vindo ao',
    'capa_titulo':   '',
    'capa_texto':    'Acesse sistemas, informações',
    'capa_texto2':   'e serviços da unidade.',
    # Tipografia do que é digitado à mão. Tamanhos em rem, cores em hexa —
    # ambos validados na gravação, porque vão parar dentro de um <style>.
    'capa_titulo_tam': '1.75', 'capa_titulo_cor': '#ffffff',
    'capa_texto_tam':  '0.83', 'capa_texto_cor':  '#dde6f4',
    'botao_sigla_tam': '0.80', 'botao_sigla_cor': '#1e293b',
    'botao_nome_tam':  '0.67', 'botao_nome_cor':  '#7c8ba1',
    # Cores de fundo. A barra lateral aceita duas: iguais dão cor sólida,
    # diferentes dão degradê de cima para baixo.
    'capa_cor':     '#16294f',
    'lateral_cor1': '#101d3a',
    'lateral_cor2': '#16294f',
    # Fundo da página inteira: a foto aérea da unidade, uma cor à escolha ou
    # nada (o cinza claro do tema). O véu é o quanto a foto é clareada por
    # trás dos cartões — foto crua atrás de texto cansa a leitura.
    # Tipografia dos comunicados. A família sai de uma lista fechada: o servidor
    # é de rede interna, sem fonte de internet, então só valem pilhas que já
    # existem na máquina de quem lê.
    'com_fonte':      'padrao',    # padrao | classica | serifa | mono
    'com_titulo_tam': '0.83', 'com_titulo_cor': '#1e293b',
    'com_texto_tam':  '0.74', 'com_texto_cor':  '#7c8ba1',
    'fundo_modo': 'imagem',    # imagem | cor | nenhum
    'fundo_cor':  '#f6f8fc',
    'fundo_veu':  '82',        # 0 a 100
}
FUNDO_MODOS = ('imagem', 'cor', 'nenhum')

# Paleta oferecida nos seletores de cor. Escolher de uma lista curta evita o
# arco-íris que sai de um seletor livre — e todas aqui têm contraste suficiente
# para texto em cartão claro. O seletor livre continua ao lado, para quem
# precisar de uma cor específica da unidade.
PALETA = [
    ('#1e293b', 'Grafite'),   ('#7c8ba1', 'Cinza'),     ('#2563eb', 'Azul'),
    ('#1d4ed8', 'Azul forte'),('#16a34a', 'Verde'),     ('#0f766e', 'Verde-água'),
    ('#e08a2a', 'Âmbar'),     ('#c2410c', 'Laranja'),   ('#e0503c', 'Vermelho'),
    ('#b91c1c', 'Vermelho forte'), ('#6d5ae0', 'Roxo'), ('#a21caf', 'Magenta'),
]
# Fundos: mesmas famílias, em tom claro — texto escuro por cima continua legível.
PALETA_FUNDO = [
    ('#e5edfd', 'Azul claro'),  ('#e3f6ec', 'Verde claro'), ('#fdf0e2', 'Âmbar claro'),
    ('#fdeae7', 'Vermelho claro'), ('#ece9fc', 'Roxo claro'), ('#f0f3f9', 'Cinza claro'),
    ('#fff8d6', 'Amarelo'),     ('#e6fbff', 'Ciano claro'),
]

# Como o comunicado chama atenção, além do selo de urgência.
DESTAQUES_COMUNICADO = {
    'nenhum': 'Sem destaque',
    'fundo':  'Fundo colorido',
    'pulso':  'Título pulsando',
}

FONTES_TEXTO = {
    'padrao':   ("Padrão do portal", "'Inter','Segoe UI Variable','Segoe UI',"
                                     "system-ui,sans-serif"),
    'classica': ("Sem serifa clássica", "Arial,Helvetica,'Liberation Sans',sans-serif"),
    'serifa':   ("Com serifa", "Georgia,'Times New Roman','Liberation Serif',serif"),
    'mono':     ("Monoespaçada", "'Consolas','DejaVu Sans Mono',monospace"),
}

# Títulos dos cartões do painel. Ficam em config para a unidade chamar cada
# bloco do jeito que fala no dia a dia — "Ramais mais utilizados" pode ser
# "Telefones úteis" sem ninguém mexer em template.
TITULOS_CARTAO = [
    ('comunicados',     'Comunicados importantes'),
    ('sistemas',        'Acesso rápido aos sistemas'),
    ('aniversariantes', 'Aniversariantes do mês'),
    ('atalhos',         'Atalhos úteis'),
    ('ramais',          'Ramais mais utilizados'),
    ('escalas',         'Escalas de hoje'),
    ('chamados',        'Chamados de TI'),
    ('reservas',        'Reservas rápidas'),
]
PADROES.update({f'titulo_{chave}': texto for chave, texto in TITULOS_CARTAO})

# Valores que entram numa folha de estilo não podem vir crus do formulário:
# um ponto-e-vírgula no meio já emenda outra regra.
_HEX = re.compile(r'^#[0-9a-fA-F]{6}$')


def medida(valor, padrao, minimo=0.5, maximo=4.0):
    """Tamanho em rem, preso a uma faixa razoável."""
    try:
        n = float(str(valor).strip().replace(',', '.'))
    except (TypeError, ValueError):
        return padrao
    return f'{max(minimo, min(maximo, n)):.2f}'


def cor_hexa(valor, padrao):
    valor = (valor or '').strip()
    return valor if _HEX.match(valor) else padrao


@app.template_global()
def rgba(hexa, alfa):
    """Mesma cor com transparência — usada no véu que escurece a foto atrás do
    texto da capa. Sem ele o texto some sobre as partes claras da imagem."""
    hexa = cor_hexa(hexa, '#16294f').lstrip('#')
    r, g, b = (int(hexa[i:i + 2], 16) for i in (0, 2, 4))
    return f'rgba({r},{g},{b},{alfa})'

SEED_LINKS = [
    ('Plataforma SP',   'https://minhaarea.sp.gov.br/plataformasp',
     'Área do servidor — Governo do Estado de São Paulo', 'PSP', '#2f7fb8'),
    ('SisDRHu',         'http://10.200.45.21:81/SisDrhu/webroot/ui/Login.php',
     'Sistema de Recursos Humanos', 'RH', '#2a8f8a'),
    ('GPU',             'https://gpu.policiapenal.sp.gov.br/',
     'Gestão Prisional Unificada — Polícia Penal', 'GPU', '#c9a227'),
    ('Cartórios SP',    'http://new.cartoriosap.sp.gov.br/',
     'Sistema de cartórios', 'CAR', '#4a5b68'),
    ('GEPEN',           'http://10.200.45.5:8080/gepen/index.do',
     'Gestão Penitenciária', 'GEP', '#6455a8'),
]

# Atalhos que toda unidade acaba pedindo. Entram sem endereço de propósito:
# metade é sistema interno, com IP diferente em cada unidade, e chutar um link
# é pior que nenhum — quem clica num atalho errado só descobre no erro do
# navegador. Sem URL a pastilha aparece na faixa e não leva a lugar nenhum, até
# alguém preencher em Administração → Links → Atalhos úteis.
SEED_ATALHOS = [
    ('Diário Oficial de SP',     'documento'),
    ('Portal da Transparência',  'globo'),
    ('Holerite',                 'cifrao'),
    ('Requisição de Materiais',  'pasta'),
    ('Ponto Eletrônico',         'relogio'),
    ('SAP',                      'escudo'),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario    TEXT UNIQUE NOT NULL,
    nome       TEXT NOT NULL,
    senha_hash TEXT NOT NULL,
    admin      INTEGER NOT NULL DEFAULT 0,
    ativo      INTEGER NOT NULL DEFAULT 1,
    criado_em  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    ultimo_acesso TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS links (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo    TEXT NOT NULL,
    url       TEXT NOT NULL,
    descricao TEXT DEFAULT '',
    icone     TEXT DEFAULT '',
    simbolo   TEXT DEFAULT '',
    categoria TEXT DEFAULT '',
    situacao  TEXT DEFAULT '',
    cor       TEXT DEFAULT '#3a6d8c',
    ordem     INTEGER NOT NULL DEFAULT 0,
    ativo     INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS banners (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    arquivo TEXT NOT NULL DEFAULT '',
    cor     TEXT DEFAULT '',
    titulo  TEXT DEFAULT '',
    texto   TEXT DEFAULT '',
    url     TEXT DEFAULT '',
    ordem   INTEGER NOT NULL DEFAULT 0,
    ativo   INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS lateral (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo     TEXT NOT NULL DEFAULT 'aviso',   -- 'aviso' | 'link'
    titulo   TEXT NOT NULL,
    conteudo TEXT DEFAULT '',
    url      TEXT DEFAULT '',
    ordem    INTEGER NOT NULL DEFAULT 0,
    ativo    INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS ramais (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    setor   TEXT NOT NULL,
    numeros TEXT NOT NULL,
    ativo   INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS aniversariantes (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    nome  TEXT NOT NULL,
    dia   INTEGER NOT NULL,
    mes   INTEGER NOT NULL,
    cargo TEXT DEFAULT '',
    ativo INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS escalas (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    turno   TEXT NOT NULL,
    equipe  TEXT DEFAULT '',
    horario TEXT DEFAULT '',
    efetivo TEXT DEFAULT '',
    ordem   INTEGER NOT NULL DEFAULT 0,
    ativo   INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS chamados (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    numero  TEXT NOT NULL,
    titulo  TEXT NOT NULL,
    situacao TEXT DEFAULT 'aberto',
    data    TEXT DEFAULT '',
    ordem   INTEGER NOT NULL DEFAULT 0,
    ativo   INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS menu_itens (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    chave TEXT NOT NULL,
    nome  TEXT NOT NULL,
    icone TEXT DEFAULT '',
    url   TEXT DEFAULT '',
    ordem INTEGER NOT NULL DEFAULT 0,
    ativo INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS config (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""

# Uma linha colada da lista de ramais: o setor vem primeiro e os números no
# fim. O grupo do setor é preguiçoso para "GAIOLA 0   307" sair como
# ("GAIOLA 0", "307") e não como ("GAIOLA", "0 307").
LINHA_RAMAL = re.compile(r'^(.*?)\s+((?:\d+\s*[/,\-–]\s*)*\d+)\s*$')


def interpretar_sistemas(texto):
    """Lê a lista colada de sistemas e devolve [(sigla, nome, url)].

    Aceita, por linha, "SIGLA | Nome | endereço" ou só "Nome | endereço"; o
    separador pode ser barra vertical, tabulação, ponto-e-vírgula ou dois ou
    mais espaços. A sigla, quando ausente, sai das iniciais do nome."""
    itens = []
    for linha in (texto or '').splitlines():
        linha = linha.strip()
        if not linha:
            continue
        partes = [p.strip() for p in re.split(r'\s*[|;	]\s*|\s{2,}', linha) if p.strip()]
        if len(partes) < 2:
            continue
        url = partes[-1]
        if not re.match(r'^(https?://|/|#)', url, re.IGNORECASE):
            url = 'http://' + url
        if len(partes) >= 3:
            sigla, nome = partes[0], ' '.join(partes[1:-1])
        else:
            nome = partes[0]
            iniciais = ''.join(p[0] for p in nome.split() if p[0].isalnum())
            sigla = (iniciais[:3] if len(iniciais) > 1 else nome[:3]).upper()
        itens.append((sigla[:5].upper(), nome, url))
    return itens


def interpretar_ramais(texto):
    """Lê o texto colado e devolve [(setor, números)]. Aceita colunas separadas
    por tabulação, ponto-e-vírgula, barra vertical ou vários espaços."""
    itens = []
    for linha in (texto or '').splitlines():
        linha = re.sub(r'[\t;|]+', '  ', linha).strip()
        if not linha:
            continue
        m = LINHA_RAMAL.match(linha)
        if not m:
            continue
        setor = m.group(1)
        # Tira rótulos de coluna que vêm junto quando a lista é copiada de uma
        # tabela ("ADMINISTRATIVO   Ramal   202 / 256").
        setor = re.sub(r'\s+(ramal|ramais|tel|telefone|fone)s?\.?\s*$', '',
                       setor, flags=re.IGNORECASE)
        setor = re.sub(r'[\s.…-]+$', '', setor).strip()
        setor = re.sub(r'\s{2,}', ' ', setor)
        numeros = re.sub(r'\s*([/,\-–])\s*', r' \1 ', m.group(2)).strip()
        numeros = re.sub(r'\s+', ' ', numeros)
        if setor and numeros:
            itens.append((setor, numeros))
    return itens


def db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


@app.teardown_appcontext
def _fecha_db(exc):
    con = g.pop('db', None)
    if con is not None:
        con.close()


def init_db():
    """Cria o banco e o conteúdo inicial.

    O gunicorn sobe vários processos e todos importam este módulo ao mesmo
    tempo. O BEGIN IMMEDIATE serializa a primeira execução: um processo semeia
    e os demais esperam e encontram tudo pronto — sem usuário admin duplicado.
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(ICONES_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.isolation_level = None
    con.executescript(SCHEMA)

    # Colunas acrescentadas depois da primeira versão. Instalações antigas já
    # têm dados, então nada de recriar tabela: só adiciona o que falta.
    for tabela, coluna, tipo in (
            ('links',    'grupo',    "TEXT NOT NULL DEFAULT 'sistema'"),
            ('links',    'simbolo',  "TEXT DEFAULT ''"),
            # Categoria agrupa os sistemas em subtítulos dentro do cartão
            # (Operacionais, Segurança, Administrativo). Vazia: sem subtítulo.
            ('links',    'categoria', "TEXT DEFAULT ''"),
            # Selo à direita nas reservas — "Disponível", "Em uso até 11:00".
            ('links',    'situacao',  "TEXT DEFAULT ''"),
            ('banners',  'cor',      "TEXT DEFAULT ''"),
            ('lateral',  'urgencia', "TEXT NOT NULL DEFAULT 'informacao'"),
            # nenhum | fundo | pulso — chama atenção sem depender de emoji
            ('lateral',  'destaque', "TEXT DEFAULT 'nenhum'"),
            # Ajustes por comunicado. Em branco: vale o padrão de Aparência.
            ('lateral',  'titulo_tam', "TEXT DEFAULT ''"),
            ('lateral',  'titulo_cor', "TEXT DEFAULT ''"),
            ('lateral',  'texto_tam',  "TEXT DEFAULT ''"),
            ('lateral',  'texto_cor',  "TEXT DEFAULT ''"),
            ('lateral',  'fundo_cor',  "TEXT DEFAULT ''"),
            ('lateral',  'data',     "TEXT DEFAULT ''"),
            ('ramais',   'destaque', 'INTEGER NOT NULL DEFAULT 0'),
            ('usuarios', 'ultimo_acesso', "TEXT DEFAULT ''")):
        existentes = {c[1] for c in con.execute(f'PRAGMA table_info({tabela})')}
        if coluna not in existentes:
            con.execute(f'ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}')

    # A chefia de plantão saiu do portal. A tabela some só se estiver vazia:
    # numa instalação que chegou a preencher, apagar seria destruir dado sem
    # aviso — ali ela fica parada, sem tela, e o backup continua levando.
    try:
        if not con.execute('SELECT 1 FROM plantao LIMIT 1').fetchone():
            con.execute('DROP TABLE plantao')
    except sqlite3.OperationalError:
        pass    # já não existe

    con.execute('BEGIN IMMEDIATE')

    for chave, valor in PADROES.items():
        con.execute('INSERT OR IGNORE INTO config (chave, valor) VALUES (?,?)',
                    (chave, valor))

    if not con.execute('SELECT 1 FROM links LIMIT 1').fetchone():
        for i, (t, u, d, sigla, cor) in enumerate(SEED_LINKS):
            con.execute('INSERT INTO links (titulo,url,descricao,icone,simbolo,cor,ordem)'
                        ' VALUES (?,?,?,?,?,?,?)', (t, u, d, sigla, 'aplicativo', cor, i))

    # Os atalhos chegaram depois da primeira versão, então o teste de "tabela
    # vazia" usado acima já não vale: quem instalou antes tem `links` cheia de
    # sistemas e nunca veria a faixa. O marcador em config resolve os dois
    # lados — entra uma vez em cada banco, e não volta se o administrador
    # apagar os atalhos por não querer nenhum.
    if not con.execute("SELECT 1 FROM config WHERE chave='seed_atalhos'").fetchone():
        ordem = con.execute("SELECT COALESCE(MAX(ordem),-1)+1 FROM links"
                            " WHERE grupo='atalho'").fetchone()[0]
        for i, (titulo, simbolo) in enumerate(SEED_ATALHOS):
            con.execute("INSERT INTO links (titulo,url,descricao,icone,simbolo,cor,"
                        "ordem,grupo) VALUES (?,'','','',?,'#3a6d8c',?,'atalho')",
                        (titulo, simbolo, ordem + i))
        con.execute("INSERT INTO config (chave,valor) VALUES ('seed_atalhos','1')")

    if not con.execute('SELECT 1 FROM menu_itens LIMIT 1').fetchone():
        for i, (chave, nome, icone, _) in enumerate(MENU):
            con.execute('INSERT INTO menu_itens (chave,nome,icone,ordem)'
                        ' VALUES (?,?,?,?)', (chave, nome, icone, i))

    if not con.execute('SELECT 1 FROM lateral LIMIT 1').fetchone():
        con.execute("INSERT INTO lateral (tipo,titulo,conteudo,ordem) VALUES"
                    " ('aviso','Bem-vindo',"
                    "'Use o painel de administração para publicar avisos, links e"
                    " imagens do banner.',0)")

    # Usuário administrador inicial. A senha vem do instalador (env) ou é
    # sorteada e impressa no log — nunca há senha fixa no código.
    if not con.execute('SELECT 1 FROM usuarios LIMIT 1').fetchone():
        senha = os.environ.get('INTRANET_ADMIN_SENHA') or secrets.token_urlsafe(9)
        con.execute('INSERT INTO usuarios (usuario,nome,senha_hash,admin)'
                    " VALUES ('admin','Administrador',?,1)",
                    (generate_password_hash(senha),))
        print('=' * 62, flush=True)
        print(' Usuário administrador criado:  admin', flush=True)
        print(f' Senha inicial:                 {senha}', flush=True)
        print(' Troque a senha após o primeiro acesso.', flush=True)
        print('=' * 62, flush=True)

    con.execute('COMMIT')
    con.close()


def cfg(chave=None):
    todas = {r['chave']: r['valor']
             for r in db().execute('SELECT chave, valor FROM config')}
    for k, v in PADROES.items():
        todas.setdefault(k, v)
    return todas if chave is None else todas.get(chave, '')


# ── autenticação ───────────────────────────────────────────────────────────────

def admin_obrigatorio(f):
    @wraps(f)
    def _wrap(*a, **kw):
        if not session.get('uid'):
            return redirect(url_for('login', proximo=request.path))
        if not session.get('admin'):
            abort(403)
        return f(*a, **kw)
    return _wrap


def token_csrf():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    return session['csrf']


@app.before_request
def _valida_csrf():
    if request.method == 'POST':
        enviado = request.form.get('csrf', '')
        if not enviado or not secrets.compare_digest(enviado, session.get('csrf', '')):
            abort(400, 'Sessão expirada. Recarregue a página e tente de novo.')


VERSAO = '1.2.0'

MESES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho',
         'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']

# Quantos itens cada cartão do painel mostra. O que passar disso fica na
# página "ver todos" — assim os cartões mantêm altura parecida e a página não
# cresce sem controle conforme os blocos vão sendo preenchidos.
GRUPOS_LINK = {
    'sistema': 'Acesso rápido aos sistemas',
    'atalho':  'Atalhos úteis',
    'reserva': 'Reservas rápidas',
}

LIMITES = {
    'comunicados': 4, 'sistemas': 16, 'atalhos': 8,
    'aniversariantes': 4, 'ramais': 5, 'escalas': 6, 'chamados': 3,
    'reservas': 4,
}

# De onde cada bloco lê os itens na página "ver todos".
FONTES = {
    'comunicados':     ('lateral', 'SELECT * FROM lateral WHERE ativo=1 ORDER BY ordem, id',
                        'Comunicados importantes', 'comunicados'),
    'atalhos':         ('links', "SELECT * FROM links WHERE ativo=1 AND grupo='atalho'"
                        ' ORDER BY ordem, id', 'Atalhos úteis', 'atalhos'),
    'reservas':        ('links', "SELECT * FROM links WHERE ativo=1 AND grupo='reserva'"
                        ' ORDER BY ordem, id', 'Reservas rápidas', 'reservas'),
    'escalas':         ('escalas', 'SELECT * FROM escalas WHERE ativo=1 ORDER BY ordem, id',
                        'Escalas', 'escalas'),
    'chamados':        ('chamados', 'SELECT * FROM chamados WHERE ativo=1 ORDER BY ordem, id',
                        'Chamados de TI', 'chamados'),
    'aniversariantes': ('aniversariantes',
                        'SELECT * FROM aniversariantes WHERE ativo=1 ORDER BY mes, dia',
                        'Aniversariantes do ano', 'aniversarios'),
}


@app.route('/lista/<chave>')
def lista(chave):
    """Página com todos os itens de um bloco — o painel mostra só os primeiros."""
    if chave == 'sistemas':
        return redirect(url_for('sistemas'))
    if chave == 'ramais':
        return redirect(url_for('ramais'))
    if chave not in FONTES:
        abort(404)
    _, consulta, titulo, macro = FONTES[chave]
    return render_template('lista.html', chave=chave, titulo=titulo, macro=macro,
                           marca_bloco=marca_atual(macro),
                           itens=db().execute(consulta).fetchall())

# Menu lateral. Os itens sem módulo próprio ainda levam a uma página que
# explica isso — some do menu é pior: o usuário procura e não acha.
MENU = [
    ('inicio',     'Início',              'inicio',     'index'),
    ('ramais',     'Ramais',              'telefone',   'ramais'),
    ('servidores', 'Servidores',          'usuarios',   None),
    ('documentos', 'Documentos',          'documento',  None),
    ('escalas',    'Escalas',             'calendario', None),
    ('chamados',   'Chamados de TI',      'fone',       None),
    ('reservas',   'Reserva de Recursos', 'arquivo',    None),
    ('relatorios', 'Relatórios',          'grafico',    None),
]


ROTAS_INTERNAS = {'inicio': 'index', 'ramais': 'ramais'}


def montar_menu():
    """Menu lateral a partir do banco. Sem endereço próprio, o item usa a rota
    interna correspondente ou, na falta dela, a página de módulo em preparação."""
    itens = []
    for r in db().execute('SELECT * FROM menu_itens WHERE ativo=1 ORDER BY ordem, id'):
        if r['url']:
            destino, externo = r['url'], not r['url'].startswith('/')
        elif r['chave'] in ROTAS_INTERNAS:
            destino, externo = url_for(ROTAS_INTERNAS[r['chave']]), False
        else:
            destino, externo = url_for('modulo', chave=r['chave']), False
        itens.append({'chave': r['chave'], 'nome': r['nome'],
                      'ic': r['icone'] or '▸', 'href': destino, 'externo': externo})
    return itens


@app.route('/modulo/<chave>')
def modulo(chave):
    row = db().execute('SELECT nome FROM menu_itens WHERE chave=?', (chave,)).fetchone()
    if not row:
        abort(404)
    return render_template('modulo.html', chave=chave, nome=row['nome'])


@app.context_processor
def _injeta():
    fundo, fundo_v = fundo_atual()
    logo, logo_v = logo_atual()
    # tem_ramais fica aqui porque o menu lateral aparece em todas as páginas
    tem_ramais = db().execute(
        'SELECT 1 FROM ramais WHERE ativo=1 LIMIT 1').fetchone() is not None
    menu = montar_menu()
    if session.get('admin'):
        menu.append({'chave': 'admin', 'nome': 'Administração', 'ic': 'engrenagem',
                     'href': url_for('admin'), 'externo': False})
    # Contadores dos sinos da barra superior. São dados reais — chamado ainda
    # não concluído e comunicado marcado como urgente; sem isso o número seria
    # enfeite com aparência de aviso.
    aviso_chamados = db().execute(
        "SELECT COUNT(*) c FROM chamados WHERE ativo=1 AND situacao<>'concluido'"
    ).fetchone()['c']
    aviso_comunicados = db().execute(
        "SELECT COUNT(*) c FROM lateral WHERE ativo=1 AND urgencia='urgente'"
    ).fetchone()['c']
    return {'cfg': cfg(), 'csrf_token': token_csrf(),
            'fundo_nome': fundo, 'fundo_versao': fundo_v,
            'logo_nome': logo, 'logo_versao': logo_v,
            'tem_ramais': tem_ramais, 'menu': menu, 'versao': VERSAO,
            # calculado a cada resposta: a virada de ano não exige reiniciar
            'ano_atual': datetime.now().year,
            'meses': MESES,
            'mes_numero': datetime.now().month,
            'mes_atual_nome': MESES[datetime.now().month - 1],
            'limites': LIMITES, 'icones': sorted(ICONES),
            # Resolvida aqui: o template não deve escolher pilha de fonte, e
            # assim só entra no <style> um valor da lista fechada.
            'fonte_comunicado': FONTES_TEXTO.get(
                cfg('com_fonte'), FONTES_TEXTO['padrao'])[1],
            'icones_proprios': icones_enviados(), 'prefixo_icone': ICONE_ARQ,
            'aviso_chamados': aviso_chamados,
            'aviso_comunicados': aviso_comunicados,
            'usuario_nome': session.get('nome'),
            'ultimo_acesso': session.get('ultimo_acesso'),
            'eh_admin': bool(session.get('admin'))}


@app.template_filter('texto_longo')
def _texto_longo(texto, linhas=5, caracteres=320):
    """O comunicado não cabe no cartão do painel?

    Decidido aqui, e não no CSS, porque a folha não tem como saber se o texto
    transbordou — e esmaecer o fim de um comunicado curto pareceria defeito.
    Conta as duas coisas: muitas linhas curtas ocupam altura igual a poucas
    linhas longas."""
    texto = texto or ''
    return len(texto.splitlines()) > linhas or len(texto) > caracteres


@app.template_filter('linhas')
def _linhas(texto):
    """Cada linha do comunicado vira um bloco próprio.

    É o que permite o recuo pendente: a linha que dobra sozinha volta alinhada
    ao texto, não à margem — e o emoji do começo fica solto à esquerda, como
    numa lista. Não dá para fazer isso digitando espaço, porque o ponto da
    quebra muda com a largura da tela.

    Linha vazia vira um bloco vazio, que o CSS transforma em respiro."""
    partes = str(escape(texto or '')).splitlines() or ['']
    return Markup(''.join(
        f'<span class="linha-com{"" if linha.strip() else " linha-vazia"}">{linha}</span>'
        for linha in partes))


@app.template_filter('iniciais')
def _iniciais(nome):
    """Iniciais para o avatar: primeiro e último nome. Nome único devolve as
    duas primeiras letras, senão o círculo fica com uma letra solta."""
    partes = [p for p in (nome or '').split() if p]
    if not partes:
        return '?'
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


@app.template_filter('sigla_turno')
def _sigla_turno(nome):
    """Sigla curta para o círculo da escala.

    "Turno I", "Turno II" e "Turno III" começam todos com as mesmas duas
    letras — cortar em dois caracteres dava "TU" em todos e o círculo deixava
    de distinguir coisa alguma. Número romano no fim vira algarismo."""
    palavras = [p for p in (nome or '').split() if p]
    if not palavras:
        return '?'
    romanos = {'I': '1', 'II': '2', 'III': '3', 'IV': '4', 'V': '5',
               'VI': '6', 'VII': '7', 'VIII': '8', 'IX': '9', 'X': '10'}
    ultimo = palavras[-1].upper().strip('.º°')
    if len(palavras) > 1 and ultimo in romanos:
        return (palavras[0][0] + romanos[ultimo]).upper()
    if len(palavras) > 1:
        return (palavras[0][0] + palavras[-1][0]).upper()
    return palavras[0][:2].upper()


@app.template_filter('partes_numeros')
def _partes_numeros(txt):
    """Separa "202 / 256" nos números que compõem o ramal, para o cartão
    alinhá-los em colunas próprias em vez de imprimir a linha inteira."""
    return [p for p in re.split(r'\s*[/,;–—-]\s*|\s{2,}', (txt or '').strip()) if p]


@app.template_filter('icone_valido')
def _icone_valido(valor):
    """Nome de ícone para marcar no seletor — traduz o emoji de instalações
    antigas para o desenho equivalente."""
    return nome_icone(valor)


# ── páginas públicas (exigem login) ────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    erro = None
    if request.method == 'POST':
        usuario = (request.form.get('usuario') or '').strip()
        senha   = request.form.get('senha') or ''
        row = db().execute('SELECT * FROM usuarios WHERE usuario=? AND ativo=1',
                           (usuario,)).fetchone()
        if row and check_password_hash(row['senha_hash'], senha):
            session.clear()
            session['uid']   = row['id']
            session['user']  = row['usuario']
            session['nome']  = row['nome']
            session['admin'] = bool(row['admin'])
            # Guarda o acesso anterior antes de gravar o de agora — quem entra
            # quer ver quando esteve aqui da última vez, não o relógio atual.
            session['ultimo_acesso'] = row['ultimo_acesso'] or ''
            con = db()
            con.execute("UPDATE usuarios SET ultimo_acesso=datetime('now','localtime')"
                        ' WHERE id=?', (row['id'],))
            con.commit()
            destino = request.args.get('proximo') or url_for('index')
            # Só aceita caminho interno — evita redirecionar para site externo
            if not destino.startswith('/') or destino.startswith('//'):
                destino = url_for('index')
            return redirect(destino)
        erro = 'Usuário ou senha inválidos.'
    return render_template('login.html', erro=erro)


@app.route('/sistemas')
def sistemas():
    """Todos os sistemas — o painel mostra só os primeiros e manda para cá."""
    con = db()
    return render_template(
        'sistemas.html',
        sistemas=agrupar_por_categoria(
            con.execute("SELECT * FROM links WHERE ativo=1 AND grupo='sistema'"
                        ' ORDER BY ordem, id').fetchall()),
        atalhos=con.execute("SELECT * FROM links WHERE ativo=1 AND grupo='atalho'"
                            ' ORDER BY ordem, id').fetchall(),
        reservas=con.execute("SELECT * FROM links WHERE ativo=1 AND grupo='reserva'"
                             ' ORDER BY ordem, id').fetchall())


@app.route('/ramais')
def ramais():
    """Lista de ramais — aberta, como a página inicial. A busca é feita no
    navegador, então filtra enquanto se digita, sem recarregar."""
    return render_template('ramais.html', itens=db().execute(
        'SELECT * FROM ramais WHERE ativo=1 ORDER BY setor COLLATE NOCASE, id'
    ).fetchall())


@app.route('/sair')
def sair():
    session.clear()
    return redirect(url_for('index'))


def saudacao():
    """Bom dia / Boa tarde / Boa noite, pelo relógio do servidor."""
    hora = datetime.now().hour
    if hora < 12:
        return 'Bom dia'
    return 'Boa tarde' if hora < 18 else 'Boa noite'


def agrupar_por_categoria(itens):
    """[(categoria, [itens])] preservando a ordem cadastrada.

    O grupo sem categoria vai sempre na frente. Ele é desenhado sem subtítulo,
    então em qualquer outra posição os itens dele apareceriam logo abaixo do
    título do grupo anterior e passariam por ser daquela categoria."""
    grupos, indice = [], {}
    for item in itens:
        chave = (item['categoria'] or '').strip()
        if chave not in indice:
            indice[chave] = len(grupos)
            grupos.append((chave, []))
        grupos[indice[chave]][1].append(item)
    return sorted(grupos, key=lambda g: g[0] != '')


def ramais_do_painel(con):
    """Ramais do cartão da página inicial.

    Sem nenhum marcado como destaque o cartão apareceria vazio mesmo com a
    lista cheia — o que acontece logo após instalar ou restaurar um backup
    antigo. Nesse caso mostra os primeiros em ordem alfabética."""
    marcados = con.execute('SELECT * FROM ramais WHERE ativo=1 AND destaque=1'
                           ' ORDER BY setor COLLATE NOCASE').fetchall()
    if marcados:
        return marcados
    return con.execute('SELECT * FROM ramais WHERE ativo=1'
                       ' ORDER BY setor COLLATE NOCASE LIMIT ?',
                       (LIMITES['ramais'],)).fetchall()


@app.route('/')
def index():
    """Painel inicial — aberto a qualquer pessoa da rede. O login existe só
    para o gerenciamento do conteúdo (ver as rotas /admin).

    Os cartões existem sempre, mesmo vazios: assim a página não muda de forma
    conforme vai sendo preenchida."""
    con = db()
    mes = datetime.now().month

    def quantos(consulta):
        return con.execute(consulta).fetchone()[0]

    # A faixa de indicadores do layout tem cinco cartões. Estes são os cinco
    # números que a unidade realmente tem no banco — contador de módulo que
    # ainda não existe seria enfeite, e enfeite com cara de dado engana quem lê.
    numeros = [
        (quantos("SELECT COUNT(*) FROM links WHERE ativo=1 AND grupo='sistema'"),
         'Sistemas', 'Disponíveis', 'grade', 'azul'),
        (quantos('SELECT COUNT(*) FROM ramais WHERE ativo=1'),
         'Ramais', 'Cadastrados', 'telefone', 'verde'),
        (quantos('SELECT COUNT(*) FROM lateral WHERE ativo=1'),
         'Comunicados', 'Publicados', 'megafone', 'laranja'),
        (quantos('SELECT COUNT(*) FROM escalas WHERE ativo=1'),
         'Escalas de hoje', 'Ativas', 'calendario', 'roxo'),
        (quantos("SELECT COUNT(*) FROM chamados WHERE ativo=1"
                 " AND situacao<>'concluido'"),
         'Chamados de TI', 'Abertos', 'fone', 'vermelho'),
    ]

    sistemas_todos = con.execute(
        "SELECT * FROM links WHERE ativo=1 AND grupo='sistema'"
        ' ORDER BY ordem, id').fetchall()

    # A busca do cartão de ramais precisa alcançar a lista inteira, não só as
    # linhas em destaque — senão procura no que já está à vista. Os demais vão
    # para a página escondidos e aparecem quando casam com o que se digita.
    destaques = ramais_do_painel(con)
    em_destaque = {r['id'] for r in destaques}

    return render_template(
        'index.html', numeros=numeros, saudacao=saudacao(),
        # O corte vem antes do agrupamento: fatiar a lista já agrupada cortaria
        # categorias inteiras, não itens, e o limite deixaria de existir.
        sistemas=agrupar_por_categoria(sistemas_todos[:LIMITES['sistemas']]),
        sistemas_total=len(sistemas_todos),
        atalhos=con.execute("SELECT * FROM links WHERE ativo=1 AND grupo='atalho'"
                            ' ORDER BY ordem, id').fetchall(),
        reservas=con.execute("SELECT * FROM links WHERE ativo=1 AND grupo='reserva'"
                             ' ORDER BY ordem, id').fetchall(),
        chamados=con.execute('SELECT * FROM chamados WHERE ativo=1 ORDER BY ordem, id'
                             ).fetchall(),
        banners=con.execute('SELECT * FROM banners WHERE ativo=1 ORDER BY ordem, id').fetchall(),
        comunicados=con.execute('SELECT * FROM lateral WHERE ativo=1 ORDER BY ordem, id').fetchall(),
        escalas=con.execute('SELECT * FROM escalas WHERE ativo=1 ORDER BY ordem, id').fetchall(),
        marca_aniversarios=marca_atual('aniversarios'),
        aniversariantes=con.execute(
            'SELECT * FROM aniversariantes WHERE ativo=1 AND mes=? ORDER BY dia',
            (mes,)).fetchall(),
        ramais_destaque=destaques,
        ramais_extras=[r for r in con.execute(
            'SELECT * FROM ramais WHERE ativo=1 ORDER BY setor COLLATE NOCASE, id')
            if r['id'] not in em_destaque],
        ramais_total=con.execute(
            'SELECT COUNT(*) FROM ramais WHERE ativo=1').fetchone()[0],
        ramais_sem_destaque=not con.execute(
            'SELECT 1 FROM ramais WHERE ativo=1 AND destaque=1 LIMIT 1').fetchone(),
    )


# ── administração ──────────────────────────────────────────────────────────────

def salva_upload(campo, atual=''):
    """Grava um arquivo enviado e devolve o nome final (ou o atual, se nada veio)."""
    arq = request.files.get(campo)
    if not arq or not arq.filename:
        return atual
    ext = os.path.splitext(arq.filename)[1].lower()
    if ext not in EXT_OK:
        raise ValueError('Formato não aceito. Use PNG, JPG, WEBP ou GIF.')
    nome = f"{secrets.token_hex(8)}{ext}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    arq.save(os.path.join(UPLOAD_DIR, nome))
    return nome


def remove_upload(nome):
    if not nome:
        return
    caminho = os.path.join(UPLOAD_DIR, secure_filename(nome))
    if os.path.isfile(caminho):
        try:
            os.remove(caminho)
        except OSError:
            pass


def _apaga_arquivos(nomes):
    """Remove os arquivos indicados de static/ — só um formato vale por vez."""
    for nome in nomes:
        caminho = os.path.join(STATIC_DIR, nome)
        if os.path.isfile(caminho):
            try:
                os.remove(caminho)
            except OSError:
                pass


def _troca_imagem_fixa(campo, base, nomes, exts):
    """Substitui static/<base>.<ext> pelo arquivo enviado no formulário.
    Devolve mensagem de erro ou None."""
    enviado = request.files.get(campo)
    if not enviado or not enviado.filename:
        return None
    ext = os.path.splitext(enviado.filename)[1].lower()
    if ext not in exts:
        return f"Formato não aceito para {campo}. Use {', '.join(sorted(exts))}."
    _apaga_arquivos(nomes)
    enviado.save(os.path.join(STATIC_DIR, base + ext))
    return None


def _int(valor, padrao=0):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return padrao


def reordenar(tabela):
    """Grava a nova ordem vinda do arrastar-e-soltar.

    Recebe os ids na sequência desejada e regrava a coluna `ordem` como
    0,1,2... — assim a ordem fica sempre normalizada, sem buracos nem empates.
    Responde 204 (sem conteúdo) porque a página não precisa recarregar.
    """
    ids = [int(x) for x in request.form.get('ids', '').split(',')
           if x.strip().lstrip('-').isdigit()]
    if not ids:
        return ('', 400)
    con = db()
    # Só reordena o que existe nesta tabela — ids forjados são ignorados.
    validos = {r['id'] for r in con.execute(f'SELECT id FROM {tabela}')}
    for posicao, ident in enumerate(i for i in ids if i in validos):
        con.execute(f'UPDATE {tabela} SET ordem=? WHERE id=?', (posicao, ident))
    con.commit()
    return ('', 204)


@app.route('/admin')
@admin_obrigatorio
def admin():
    con = db()
    return render_template('admin.html', total={
        'links':   con.execute('SELECT COUNT(*) c FROM links').fetchone()['c'],
        'banners': con.execute('SELECT COUNT(*) c FROM banners').fetchone()['c'],
        'lateral': con.execute('SELECT COUNT(*) c FROM lateral').fetchone()['c'],
        'ramais': con.execute('SELECT COUNT(*) c FROM ramais').fetchone()['c'],
        'usuarios': con.execute('SELECT COUNT(*) c FROM usuarios').fetchone()['c'],
    })


@app.route('/admin/links', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_links():
    con = db()
    if request.method == 'POST':
        acao = request.form.get('acao')
        ident = _int(request.form.get('id'))
        if acao == 'ordenar':
            return reordenar('links')
        if acao == 'importar':
            grupo = request.form.get('grupo_destino', 'sistema')
            if grupo not in ('sistema', 'atalho', 'reserva'):
                grupo = 'sistema'
            itens = interpretar_sistemas(request.form.get('lista', ''))
            if not itens:
                flash('Nenhuma linha reconhecida. Use uma linha por sistema, '
                      'no formato: SIGLA | Nome | endereço', 'erro')
            else:
                base = con.execute('SELECT COALESCE(MAX(ordem),-1)+1 o FROM links'
                                   ' WHERE grupo=?', (grupo,)).fetchone()['o']
                cores = ['#2563c9', '#2a8f8a', '#c9a227', '#4a5b68', '#6455a8', '#3a6d8c']
                simbolo = {'sistema': 'aplicativo', 'atalho': 'documento',
                           'reserva': 'calendario'}[grupo]
                for i, (sigla, nome, url) in enumerate(itens):
                    con.execute('INSERT INTO links (titulo,url,descricao,icone,simbolo,'
                                'cor,ordem,ativo,grupo) VALUES (?,?,?,?,?,?,?,1,?)',
                                (nome, url, '', sigla, simbolo, cores[i % len(cores)],
                                 base + i, grupo))
                flash(f'{len(itens)} itens importados.', 'ok')
            con.commit()
            return redirect(url_for('admin_links'))
        if acao == 'excluir':
            con.execute('DELETE FROM links WHERE id=?', (ident,))
            flash('Link removido.', 'ok')
        else:
            grupo = request.form.get('grupo', 'sistema')
            dados = (request.form.get('titulo', '').strip(),
                     request.form.get('url', '').strip(),
                     request.form.get('descricao', '').strip(),
                     request.form.get('icone', '').strip()[:5],
                     nome_icone(request.form.get('simbolo')),
                     request.form.get('categoria', '').strip(),
                     request.form.get('situacao', '').strip(),
                     request.form.get('cor', '#3a6d8c'),
                     _int(request.form.get('ordem')),
                     1 if request.form.get('ativo') else 0,
                     grupo if grupo in ('sistema', 'atalho', 'reserva') else 'sistema')
            # Só o título é obrigatório. O endereço fica para depois: monta-se
            # a fileira de botões primeiro e informa-se o link de cada um
            # conforme se descobre — em sistema interno o endereço muda de
            # unidade para unidade. Sem URL o botão aparece e não é link.
            if not dados[0]:
                flash('O título é obrigatório.', 'erro')
            elif ident:
                con.execute('UPDATE links SET titulo=?,url=?,descricao=?,icone=?,'
                            'simbolo=?,categoria=?,situacao=?,cor=?,ordem=?,ativo=?,'
                            'grupo=? WHERE id=?', dados + (ident,))
                flash('Link atualizado.', 'ok')
            else:
                con.execute('INSERT INTO links (titulo,url,descricao,icone,simbolo,'
                            'categoria,situacao,cor,ordem,ativo,grupo)'
                            ' VALUES (?,?,?,?,?,?,?,?,?,?,?)', dados)
                flash('Link adicionado.', 'ok')
        con.commit()
        return redirect(url_for('admin_links',
                                grupo=request.form.get('grupo')
                                or request.form.get('grupo_destino') or 'sistema'))

    editar = None
    if request.args.get('editar'):
        editar = con.execute('SELECT * FROM links WHERE id=?',
                             (_int(request.args['editar']),)).fetchone()
    # Cada grupo tem sua própria aba: antes atalhos e reservas ficavam
    # escondidos num seletor dentro do cadastro de sistemas.
    grupo = request.args.get('grupo', editar['grupo'] if editar else 'sistema')
    if grupo not in GRUPOS_LINK:
        grupo = 'sistema'
    return render_template(
        'admin_links.html', editar=editar, grupo=grupo, grupos=GRUPOS_LINK,
        # Alimenta o datalist do campo Categoria: reaproveitar o que já existe
        # evita "Segurança" e "Seguranca" virarem dois grupos.
        categorias=[r['categoria'] for r in con.execute(
            "SELECT DISTINCT categoria FROM links WHERE grupo='sistema'"
            " AND categoria<>'' ORDER BY categoria COLLATE NOCASE")],
        itens=con.execute('SELECT * FROM links WHERE grupo=? ORDER BY ordem, id',
                          (grupo,)).fetchall())


@app.route('/admin/banners', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_banners():
    con = db()
    if request.method == 'POST':
        acao = request.form.get('acao')
        ident = _int(request.form.get('id'))
        if acao == 'ordenar':
            return reordenar('banners')
        if acao == 'excluir':
            row = con.execute('SELECT arquivo FROM banners WHERE id=?',
                              (ident,)).fetchone()
            if row:
                remove_upload(row['arquivo'])
            con.execute('DELETE FROM banners WHERE id=?', (ident,))
            flash('Imagem removida.', 'ok')
        else:
            atual = ''
            if ident:
                row = con.execute('SELECT arquivo FROM banners WHERE id=?',
                                  (ident,)).fetchone()
                atual = row['arquivo'] if row else ''
            try:
                arquivo = salva_upload('imagem', atual)
            except ValueError as e:
                flash(str(e), 'erro')
                return redirect(url_for('admin_banners'))
            # Um slide é uma foto ou uma cor sólida. Marcar "usar cor" descarta
            # a imagem: guardar as duas deixaria a dúvida de qual manda.
            usar_cor = bool(request.form.get('usar_cor'))
            cor = cor_hexa(request.form.get('cor'), '') if usar_cor else ''
            if usar_cor and not cor:
                flash('Escolha uma cor válida.', 'erro')
                return redirect(url_for('admin_banners'))
            if usar_cor and arquivo:
                remove_upload(arquivo)
                arquivo = ''
            if not arquivo and not cor:
                flash('Escolha uma imagem ou marque "usar cor sólida".', 'erro')
                return redirect(url_for('admin_banners'))
            dados = (arquivo, cor,
                     request.form.get('titulo', '').strip(),
                     request.form.get('texto', '').strip(),
                     request.form.get('url', '').strip(),
                     _int(request.form.get('ordem')),
                     1 if request.form.get('ativo') else 0)
            if ident:
                if atual and atual != arquivo:
                    remove_upload(atual)
                con.execute('UPDATE banners SET arquivo=?,cor=?,titulo=?,texto=?,'
                            'url=?,ordem=?,ativo=? WHERE id=?', dados + (ident,))
                flash('Banner atualizado.', 'ok')
            else:
                con.execute('INSERT INTO banners (arquivo,cor,titulo,texto,url,'
                            'ordem,ativo) VALUES (?,?,?,?,?,?,?)', dados)
                flash('Banner adicionado.', 'ok')
        con.commit()
        return redirect(url_for('admin_banners'))

    editar = None
    if request.args.get('editar'):
        editar = con.execute('SELECT * FROM banners WHERE id=?',
                             (_int(request.args['editar']),)).fetchone()
    return render_template(
        'admin_banners.html', editar=editar,
        itens=con.execute('SELECT * FROM banners ORDER BY ordem, id').fetchall())


@app.route('/admin/lateral', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_lateral():
    con = db()
    if request.method == 'POST':
        acao = request.form.get('acao')
        ident = _int(request.form.get('id'))
        if acao == 'ordenar':
            return reordenar('lateral')
        if acao == 'excluir':
            con.execute('DELETE FROM lateral WHERE id=?', (ident,))
            flash('Item removido.', 'ok')
        else:
            urg  = request.form.get('urgencia', 'informacao')
            dest = request.form.get('destaque', 'nenhum')
            dados = (request.form.get('tipo', 'aviso'),
                     request.form.get('titulo', '').strip(),
                     # strip() inteiro comeria a indentacao da primeira linha:
                     # tira so as quebras das pontas e o espaco do fim.
                     request.form.get('conteudo', '').strip('\r\n').rstrip(),
                     request.form.get('url', '').strip(),
                     _int(request.form.get('ordem')),
                     1 if request.form.get('ativo') else 0,
                     urg if urg in ('urgente', 'comunicado', 'informacao') else 'informacao',
                     dest if dest in DESTAQUES_COMUNICADO else 'nenhum',
                     # Vazio quer dizer "usa o padrão de Aparência" — por isso
                     # o padrão dos validadores aqui é a string vazia.
                     medida(request.form.get('titulo_tam'), '', 0.6, 2.0)
                     if request.form.get('titulo_tam', '').strip() else '',
                     cor_hexa(request.form.get('titulo_cor'), ''),
                     medida(request.form.get('texto_tam'), '', 0.6, 2.0)
                     if request.form.get('texto_tam', '').strip() else '',
                     cor_hexa(request.form.get('texto_cor'), ''),
                     cor_hexa(request.form.get('fundo_cor'), ''),
                     request.form.get('data', '').strip())
            if not dados[1]:
                flash('O título é obrigatório.', 'erro')
            elif ident:
                con.execute('UPDATE lateral SET tipo=?,titulo=?,conteudo=?,url=?,'
                            'ordem=?,ativo=?,urgencia=?,destaque=?,titulo_tam=?,'
                            'titulo_cor=?,texto_tam=?,texto_cor=?,fundo_cor=?,'
                            'data=? WHERE id=?', dados + (ident,))
                flash('Item atualizado.', 'ok')
            else:
                con.execute('INSERT INTO lateral (tipo,titulo,conteudo,url,ordem,'
                            'ativo,urgencia,destaque,titulo_tam,titulo_cor,'
                            'texto_tam,texto_cor,fundo_cor,data)'
                            ' VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', dados)
                flash('Item adicionado.', 'ok')
        con.commit()
        return redirect(url_for('admin_lateral'))

    editar = None
    if request.args.get('editar'):
        editar = con.execute('SELECT * FROM lateral WHERE id=?',
                             (_int(request.args['editar']),)).fetchone()
    return render_template(
        'admin_lateral.html', editar=editar, destaques=DESTAQUES_COMUNICADO,
        paleta=PALETA, paleta_fundo=PALETA_FUNDO,
        itens=con.execute('SELECT * FROM lateral ORDER BY ordem, id').fetchall())


@app.route('/admin/ramais', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_ramais():
    con = db()
    if request.method == 'POST':
        acao = request.form.get('acao')
        ident = _int(request.form.get('id'))

        if acao == 'excluir':
            con.execute('DELETE FROM ramais WHERE id=?', (ident,))
            flash('Ramal removido.', 'ok')

        elif acao == 'importar':
            itens = interpretar_ramais(request.form.get('lista', ''))
            if not itens:
                flash('Nenhuma linha reconhecida. Cada linha precisa ter o setor '
                      'e o número, por exemplo: ALMOXARIFADO   245 / 253', 'erro')
            else:
                if request.form.get('substituir'):
                    con.execute('DELETE FROM ramais')
                con.executemany('INSERT INTO ramais (setor,numeros) VALUES (?,?)',
                                itens)
                flash(f'{len(itens)} ramais importados.', 'ok')

        else:
            setor = request.form.get('setor', '').strip()
            numeros = request.form.get('numeros', '').strip()
            ativo = 1 if request.form.get('ativo') else 0
            destaque = 1 if request.form.get('destaque') else 0
            if not setor or not numeros:
                flash('Informe o setor e o número.', 'erro')
            elif ident:
                con.execute('UPDATE ramais SET setor=?,numeros=?,ativo=?,destaque=?'
                            ' WHERE id=?', (setor, numeros, ativo, destaque, ident))
                flash('Ramal atualizado.', 'ok')
            else:
                con.execute('INSERT INTO ramais (setor,numeros,ativo,destaque)'
                            ' VALUES (?,?,?,?)', (setor, numeros, ativo, destaque))
                flash('Ramal adicionado.', 'ok')
        con.commit()
        return redirect(url_for('admin_ramais'))

    editar = None
    if request.args.get('editar'):
        editar = con.execute('SELECT * FROM ramais WHERE id=?',
                             (_int(request.args['editar']),)).fetchone()
    return render_template(
        'admin_ramais.html', editar=editar,
        itens=con.execute('SELECT * FROM ramais ORDER BY setor COLLATE NOCASE, id'
                          ).fetchall())


@app.route('/admin/usuarios', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_usuarios():
    con = db()
    if request.method == 'POST':
        acao = request.form.get('acao')
        ident = _int(request.form.get('id'))
        if acao == 'excluir':
            if ident == session['uid']:
                flash('Você não pode excluir o próprio usuário.', 'erro')
            elif con.execute('SELECT COUNT(*) c FROM usuarios WHERE admin=1'
                             ).fetchone()['c'] <= 1 and con.execute(
                    'SELECT admin FROM usuarios WHERE id=?', (ident,)
                    ).fetchone()['admin']:
                flash('Precisa existir ao menos um administrador.', 'erro')
            else:
                con.execute('DELETE FROM usuarios WHERE id=?', (ident,))
                flash('Usuário removido.', 'ok')
        else:
            usuario = (request.form.get('usuario') or '').strip().lower()
            nome    = (request.form.get('nome') or '').strip()
            senha   = request.form.get('senha') or ''
            admin_f = 1 if request.form.get('admin') else 0
            ativo   = 1 if request.form.get('ativo') else 0
            if not re.fullmatch(r'[a-z0-9._-]{3,32}', usuario):
                flash('Usuário: 3 a 32 caracteres (letras, números, . _ -).', 'erro')
            elif not nome:
                flash('Informe o nome.', 'erro')
            elif ident:
                if senha and len(senha) < 6:
                    flash('A senha precisa ter ao menos 6 caracteres.', 'erro')
                else:
                    # Nunca remover o último administrador ativo
                    if not admin_f and con.execute(
                            'SELECT admin FROM usuarios WHERE id=?', (ident,)
                            ).fetchone()['admin'] and con.execute(
                            'SELECT COUNT(*) c FROM usuarios WHERE admin=1'
                            ).fetchone()['c'] <= 1:
                        flash('Precisa existir ao menos um administrador.', 'erro')
                    else:
                        con.execute('UPDATE usuarios SET usuario=?,nome=?,admin=?,'
                                    'ativo=? WHERE id=?',
                                    (usuario, nome, admin_f, ativo, ident))
                        if senha:
                            con.execute('UPDATE usuarios SET senha_hash=? WHERE id=?',
                                        (generate_password_hash(senha), ident))
                        flash('Usuário atualizado.', 'ok')
            elif len(senha) < 6:
                flash('A senha precisa ter ao menos 6 caracteres.', 'erro')
            else:
                try:
                    con.execute('INSERT INTO usuarios (usuario,nome,senha_hash,'
                                'admin,ativo) VALUES (?,?,?,?,?)',
                                (usuario, nome, generate_password_hash(senha),
                                 admin_f, ativo))
                    flash('Usuário criado.', 'ok')
                except sqlite3.IntegrityError:
                    flash('Já existe um usuário com esse login.', 'erro')
        con.commit()
        return redirect(url_for('admin_usuarios'))

    editar = None
    if request.args.get('editar'):
        editar = con.execute('SELECT * FROM usuarios WHERE id=?',
                             (_int(request.args['editar']),)).fetchone()
    return render_template(
        'admin_usuarios.html', editar=editar,
        itens=con.execute('SELECT * FROM usuarios ORDER BY usuario').fetchall())


# ── blocos do painel: escalas, aniversariantes, menu e chamados ───────────────

# Cada bloco é uma tabela simples com os mesmos verbos (incluir, editar,
# excluir). Descrever os campos aqui evita repetir três rotinas quase iguais.
BLOCOS = {
    'escalas': {
        'titulo': 'Escalas de hoje',
        'campos': ['turno', 'equipe', 'horario', 'efetivo', 'ordem'],
        'obrigatorios': ['turno'],
        'ordem': 'ordem, id',
    },
    'aniversariantes': {
        'titulo': 'Aniversariantes',
        'campos': ['nome', 'dia', 'mes', 'cargo'],
        'obrigatorios': ['nome', 'dia', 'mes'],
        'ordem': 'mes, dia',
    },
    'menu': {
        'titulo': 'Menu lateral',
        'tabela': 'menu_itens',
        'campos': ['nome', 'icone', 'url', 'ordem'],
        'obrigatorios': ['nome'],
        'ordem': 'ordem, id',
    },
    'chamados': {
        'titulo': 'Chamados de TI',
        'campos': ['numero', 'titulo', 'situacao', 'data', 'ordem'],
        'obrigatorios': ['numero', 'titulo'],
        'ordem': 'ordem, id',
    },
}
NUMERICOS = {'ordem', 'dia', 'mes'}


@app.route('/admin/painel', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_painel():
    con = db()
    if request.method == 'POST':
        bloco = request.form.get('bloco', '')
        if bloco not in BLOCOS:
            abort(400)
        info = BLOCOS[bloco]
        tabela = info.get('tabela', bloco)
        acao = request.form.get('acao')
        ident = _int(request.form.get('id'))

        if acao == 'ordenar':
            return reordenar(tabela)
        if acao == 'excluir':
            con.execute(f'DELETE FROM {tabela} WHERE id=?', (ident,))
            flash('Item removido.', 'ok')
        else:
            valores, faltando = [], []
            for campo in info['campos']:
                bruto = (request.form.get(campo) or '').strip()
                if campo in info['obrigatorios'] and not bruto:
                    faltando.append(campo)
                valores.append(_int(bruto) if campo in NUMERICOS else bruto)
            if faltando:
                flash('Preencha: ' + ', '.join(faltando) + '.', 'erro')
            else:
                valores.append(1 if request.form.get('ativo') else 0)
                colunas = info['campos'] + ['ativo']
                if ident:
                    atrib = ','.join(f'{c}=?' for c in colunas)
                    con.execute(f'UPDATE {tabela} SET {atrib} WHERE id=?',
                                valores + [ident])
                    flash('Item atualizado.', 'ok')
                else:
                    if bloco == 'menu':
                        # A chave identifica o item na URL do módulo; sai do
                        # nome e ganha sufixo se já existir.
                        base = re.sub(r'[^a-z0-9]+', '-',
                                      valores[0].lower().strip()).strip('-') or 'item'
                        chave, n = base, 2
                        while con.execute('SELECT 1 FROM menu_itens WHERE chave=?',
                                          (chave,)).fetchone():
                            chave, n = f'{base}-{n}', n + 1
                        colunas = colunas + ['chave']
                        valores = valores + [chave]
                    marcas = ','.join('?' * len(colunas))
                    con.execute(f"INSERT INTO {tabela} ({','.join(colunas)})"
                                f' VALUES ({marcas})', valores)
                    flash('Item adicionado.', 'ok')
        con.commit()
        return redirect(url_for('admin_painel', bloco=bloco))

    bloco = request.args.get('bloco', 'escalas')
    if bloco not in BLOCOS:
        bloco = 'escalas'
    info = BLOCOS[bloco]
    tabela = info.get('tabela', bloco)
    editar = None
    if request.args.get('editar'):
        editar = con.execute(f'SELECT * FROM {tabela} WHERE id=?',
                             (_int(request.args['editar']),)).fetchone()
    return render_template(
        'admin_painel.html', bloco=bloco, info=info, blocos=BLOCOS, editar=editar,
        itens=con.execute(f"SELECT * FROM {tabela} ORDER BY {info['ordem']}").fetchall())


# ── backup e restauração ───────────────────────────────────────────────────────

def _itens_do_backup():
    """(caminho no disco, nome dentro do zip) de tudo que é conteúdo da unidade:
    o banco e as imagens enviadas. A chave de sessão fica de fora — é segredo
    desta instalação e sua ausência só faz os usuários entrarem de novo."""
    itens = [(DB_PATH, 'dados.db')]
    for nome in FUNDO_NOMES + LOGO_NOMES:
        caminho = os.path.join(STATIC_DIR, nome)
        if os.path.isfile(caminho):
            itens.append((caminho, f'static/{nome}'))
    # Marcas d'água: nome fixo, extensão variável — vão pelo prefixo.
    for nome in sorted(os.listdir(STATIC_DIR)):
        if nome.startswith('marca-') and os.path.splitext(nome)[1].lower() in MARCA_EXTS:
            itens.append((os.path.join(STATIC_DIR, nome), f'static/{nome}'))
    for pasta, prefixo in ((UPLOAD_DIR, 'static/uploads'), (ICONES_DIR, 'static/icones')):
        if os.path.isdir(pasta):
            for nome in sorted(os.listdir(pasta)):
                caminho = os.path.join(pasta, nome)
                if os.path.isfile(caminho):
                    itens.append((caminho, f'{prefixo}/{nome}'))
    return itens


def _monta_backup():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for caminho, interno in _itens_do_backup():
            z.write(caminho, interno)
    buf.seek(0)
    return buf


def _destino_seguro(nome):
    """Converte um nome de dentro do zip no caminho real, recusando qualquer
    tentativa de escapar da pasta do portal (../.. ou caminho absoluto)."""
    nome = nome.replace('\\', '/')
    if nome.startswith('/') or '..' in nome.split('/'):
        return None
    if nome == 'dados.db':
        return DB_PATH
    if nome.startswith('static/'):
        relativo = nome[len('static/'):]
        for inicio, destino in (('uploads/', UPLOAD_DIR), ('icones/', ICONES_DIR)):
            if relativo.startswith(inicio):
                arquivo = secure_filename(os.path.basename(relativo))
                return os.path.join(destino, arquivo) if arquivo else None
        if relativo in FUNDO_NOMES + LOGO_NOMES:
            return os.path.join(STATIC_DIR, relativo)
        if (relativo.startswith('marca-') and '/' not in relativo
                and os.path.splitext(relativo)[1].lower() in MARCA_EXTS):
            return os.path.join(STATIC_DIR, relativo)
    return None


@app.route('/admin/backup', methods=['GET'])
@admin_obrigatorio
def admin_backup():
    copias = []
    if os.path.isdir(BACKUP_DIR):
        for nome in sorted(os.listdir(BACKUP_DIR), reverse=True):
            caminho = os.path.join(BACKUP_DIR, nome)
            if os.path.isfile(caminho):
                copias.append({'nome': nome,
                               'kb': round(os.path.getsize(caminho) / 1024),
                               'data': datetime.fromtimestamp(
                                   os.path.getmtime(caminho)).strftime('%d/%m/%Y %H:%M')})
    con = db()
    return render_template('admin_backup.html', copias=copias[:10], conteudo={
        'links':    con.execute('SELECT COUNT(*) c FROM links').fetchone()['c'],
        'banners':  con.execute('SELECT COUNT(*) c FROM banners').fetchone()['c'],
        'lateral':  con.execute('SELECT COUNT(*) c FROM lateral').fetchone()['c'],
        'ramais':   con.execute('SELECT COUNT(*) c FROM ramais').fetchone()['c'],
        'usuarios': con.execute('SELECT COUNT(*) c FROM usuarios').fetchone()['c'],
    })


@app.route('/admin/backup/baixar', methods=['POST'])
@admin_obrigatorio
def backup_baixar():
    nome = f"portal-backup-{datetime.now():%Y-%m-%d-%H%M}.zip"
    return send_file(_monta_backup(), mimetype='application/zip',
                     as_attachment=True, download_name=nome)


@app.route('/admin/backup/restaurar', methods=['POST'])
@admin_obrigatorio
def backup_restaurar():
    arq = request.files.get('arquivo')
    if not arq or not arq.filename:
        flash('Escolha o arquivo de backup.', 'erro')
        return redirect(url_for('admin_backup'))

    try:
        dados = io.BytesIO(arq.read())
        with zipfile.ZipFile(dados) as z:
            nomes = z.namelist()
            if 'dados.db' not in nomes:
                flash('Este arquivo não parece um backup do portal '
                      '(não contém dados.db).', 'erro')
                return redirect(url_for('admin_backup'))

            # Salva o estado atual ANTES de sobrescrever — é o que permite
            # voltar atrás se o backup restaurado não for o esperado.
            os.makedirs(BACKUP_DIR, exist_ok=True)
            anterior = os.path.join(
                BACKUP_DIR, f"antes-de-restaurar-{datetime.now():%Y-%m-%d-%H%M%S}.zip")
            with open(anterior, 'wb') as f:
                f.write(_monta_backup().read())

            restaurados, ignorados = 0, 0
            for interno in nomes:
                if interno.endswith('/'):
                    continue
                destino = _destino_seguro(interno)
                if not destino:
                    ignorados += 1
                    continue
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                with z.open(interno) as origem, open(destino, 'wb') as saida:
                    saida.write(origem.read())
                restaurados += 1
    except zipfile.BadZipFile:
        flash('Arquivo inválido: não é um .zip.', 'erro')
        return redirect(url_for('admin_backup'))
    except Exception as e:
        flash(f'Falha ao restaurar: {e}', 'erro')
        return redirect(url_for('admin_backup'))

    # O banco restaurado pode ser de uma versão anterior, sem as tabelas e
    # colunas criadas depois. A migração roda no start do serviço, e restaurar
    # troca o arquivo por baixo do processo — sem isto o portal quebra inteiro
    # (erro 500) até alguém reiniciar o serviço.
    try:
        init_db()
    except Exception as e:
        flash(f'Backup restaurado, mas a atualização do banco falhou: {e}. '
              'Reinicie o serviço (systemctl restart intranet).', 'erro')
        session.clear()
        return redirect(url_for('login'))

    aviso = f'Backup restaurado ({restaurados} itens).'
    if ignorados:
        aviso += f' {ignorados} entrada(s) fora do padrão foram ignoradas.'
    aviso += ' Entre novamente com a senha daquele backup.'
    # A ordem importa: o Flask guarda os avisos na sessão, então limpar depois
    # de avisar apagaria a mensagem. Limpa primeiro (o banco mudou, os usuários
    # podem ser outros) e só então registra o aviso.
    session.clear()
    flash(aviso, 'ok')
    return redirect(url_for('login'))


@app.route('/admin/icones', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_icones():
    """Ícones próprios da unidade — logos de sistemas, brasões, o que for.

    Ficam em static/icones/ como arquivos soltos, do mesmo jeito que o logo e
    a foto de fundo: dá para enviar por aqui ou copiar direto no servidor."""
    os.makedirs(ICONES_DIR, exist_ok=True)
    if request.method == 'POST':
        if request.form.get('acao') == 'excluir':
            nome = secure_filename(request.form.get('nome', ''))
            caminho = os.path.join(ICONES_DIR, nome)
            if nome and os.path.isfile(caminho):
                os.remove(caminho)
                # Quem usava o ícone volta ao símbolo genérico sozinho, porque
                # icone_de_arquivo() confere a existência antes de desenhar.
                flash(f'Ícone {nome} removido. Os itens que o usavam voltam '
                      'ao símbolo padrão.', 'ok')
            return redirect(url_for('admin_icones'))

        enviado = request.files.get('icone')
        if not enviado or not enviado.filename:
            flash('Escolha um arquivo.', 'erro')
            return redirect(url_for('admin_icones'))
        ext = os.path.splitext(enviado.filename)[1].lower()
        if ext not in ICONE_EXTS:
            flash('Formato não aceito. Use SVG, PNG, WEBP ou JPG.', 'erro')
            return redirect(url_for('admin_icones'))
        # Nome escolhido pelo administrador, para o seletor ficar legível.
        base = secure_filename(os.path.splitext(
            request.form.get('nome', '').strip() or enviado.filename)[0])
        if not base:
            flash('Dê um nome ao ícone.', 'erro')
            return redirect(url_for('admin_icones'))
        enviado.save(os.path.join(ICONES_DIR, base + ext))
        flash(f'Ícone {base}{ext} enviado.', 'ok')
        return redirect(url_for('admin_icones'))

    return render_template('admin_icones.html', itens=icones_enviados())


@app.route('/admin/aparencia', methods=['GET', 'POST'])
@admin_obrigatorio
def admin_aparencia():
    con = db()
    if request.method == 'POST':
        if request.form.get('acao') == 'remover_fundo':
            _apaga_arquivos(FUNDO_NOMES)
            flash('Imagem de fundo removida.', 'ok')
            return redirect(url_for('admin_aparencia'))
        if request.form.get('acao') == 'remover_marca':
            _apaga_arquivos(tuple(f'marca-aniversarios{e}' for e in MARCA_EXTS))
            flash("Marca d'água removida.", 'ok')
            return redirect(url_for('admin_aparencia'))

        # Os uploads substituem os arquivos fixos static/fundo.<ext> e
        # static/logo.<ext>; trocar esses arquivos direto no servidor tem
        # exatamente o mesmo efeito.
        marca_nomes = tuple(f'marca-aniversarios{e}' for e in MARCA_EXTS)
        for campo, base, nomes, exts in (
                ('fundo', 'fundo', FUNDO_NOMES, {'.jpg', '.jpeg', '.png', '.webp'}),
                ('logo',  'logo',  LOGO_ENVIADO, {'.png', '.jpg', '.jpeg', '.webp', '.svg'}),
                ('marca_aniversarios', 'marca-aniversarios', marca_nomes, set(MARCA_EXTS))):
            erro = _troca_imagem_fixa(campo, base, nomes, exts)
            if erro:
                flash(erro, 'erro')
                return redirect(url_for('admin_aparencia'))

        novos = {
            'site_nome':    request.form.get('site_nome', '').strip(),
            'site_sigla':   request.form.get('site_sigla', '').strip(),
            'site_sub':     request.form.get('site_sub', '').strip(),
            'capa_abertura': request.form.get('capa_abertura', '').strip(),
            'capa_titulo':   request.form.get('capa_titulo', '').strip(),
            'capa_texto':    request.form.get('capa_texto', '').strip(),
            'capa_texto2':   request.form.get('capa_texto2', '').strip(),
            'capa_titulo_tam': medida(request.form.get('capa_titulo_tam'),
                                      PADROES['capa_titulo_tam'], 0.8, 4.0),
            'capa_texto_tam':  medida(request.form.get('capa_texto_tam'),
                                      PADROES['capa_texto_tam'], 0.6, 2.0),
            'botao_sigla_tam': medida(request.form.get('botao_sigla_tam'),
                                      PADROES['botao_sigla_tam'], 0.6, 1.6),
            'botao_nome_tam':  medida(request.form.get('botao_nome_tam'),
                                      PADROES['botao_nome_tam'], 0.5, 1.4),
            'capa_titulo_cor': cor_hexa(request.form.get('capa_titulo_cor'),
                                        PADROES['capa_titulo_cor']),
            'capa_texto_cor':  cor_hexa(request.form.get('capa_texto_cor'),
                                        PADROES['capa_texto_cor']),
            'botao_sigla_cor': cor_hexa(request.form.get('botao_sigla_cor'),
                                        PADROES['botao_sigla_cor']),
            'botao_nome_cor':  cor_hexa(request.form.get('botao_nome_cor'),
                                        PADROES['botao_nome_cor']),
            'com_fonte':    (request.form.get('com_fonte')
                             if request.form.get('com_fonte') in FONTES_TEXTO
                             else PADROES['com_fonte']),
            'com_titulo_tam': medida(request.form.get('com_titulo_tam'),
                                     PADROES['com_titulo_tam'], 0.6, 2.0),
            'com_texto_tam':  medida(request.form.get('com_texto_tam'),
                                     PADROES['com_texto_tam'], 0.6, 2.0),
            'com_titulo_cor': cor_hexa(request.form.get('com_titulo_cor'),
                                       PADROES['com_titulo_cor']),
            'com_texto_cor':  cor_hexa(request.form.get('com_texto_cor'),
                                       PADROES['com_texto_cor']),
            'fundo_modo':   (request.form.get('fundo_modo')
                             if request.form.get('fundo_modo') in FUNDO_MODOS
                             else PADROES['fundo_modo']),
            'fundo_cor':    cor_hexa(request.form.get('fundo_cor'),
                                     PADROES['fundo_cor']),
            'fundo_veu':    medida(request.form.get('fundo_veu'),
                                   PADROES['fundo_veu'], 0, 100),
            'capa_cor':     cor_hexa(request.form.get('capa_cor'),
                                     PADROES['capa_cor']),
            'lateral_cor1': cor_hexa(request.form.get('lateral_cor1'),
                                     PADROES['lateral_cor1']),
            'lateral_cor2': cor_hexa(request.form.get('lateral_cor2'),
                                     PADROES['lateral_cor2']),
            'cor_primaria': cor_hexa(request.form.get('cor_primaria'),
                                     PADROES['cor_primaria']),
            'cor_destaque': cor_hexa(request.form.get('cor_destaque'),
                                     PADROES['cor_destaque']),
            'banner_seg':   str(max(2, min(60, _int(request.form.get('banner_seg'), 6)))),
        }
        # Título em branco volta ao padrão: cartão sem cabeçalho não ajuda
        # ninguém, e é fácil apagar sem querer.
        for chave, padrao in TITULOS_CARTAO:
            campo = f'titulo_{chave}'
            novos[campo] = request.form.get(campo, '').strip() or padrao

        for k, v in novos.items():
            con.execute('INSERT INTO config (chave,valor) VALUES (?,?) '
                        'ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor',
                        (k, v))
        con.commit()
        flash('Aparência salva.', 'ok')
        return redirect(url_for('admin_aparencia'))
    return render_template('admin_aparencia.html',
                           titulos_cartao=TITULOS_CARTAO, fontes=FONTES_TEXTO,
                           marca_aniversarios=marca_atual('aniversarios'))


init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORTA', 8000)), debug=False)
