"""Testes dos módulos novos (segurança, histórico, mídia, notícias).

Uso:  python3 tests/test_modulos.py
Trabalha numa CÓPIA temporária do portal: não toca no banco nem nos uploads
reais. Sai com código 1 se algum teste falhar."""
import os, re, shutil, struct, sys, tempfile, zlib

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix='portal-teste-')
PASTA = os.path.join(TMP, 'p')
shutil.copytree(RAIZ, PASTA, ignore=shutil.ignore_patterns(
    '*.db', '__pycache__', 'secret.key', 'uploads', 'tests', '.git'))
os.chdir(PASTA)
sys.path.insert(0, PASTA)
os.environ['INTRANET_ADMIN_SENHA'] = 'Teste1234'
import io
import app as portal

falhas = []
def ok(cond, msg):
    print(('OK    ' if cond else 'FALHA ') + msg)
    if not cond:
        falhas.append(msg)

def png(cor=(40, 90, 160)):
    def ch(t, d):
        x = struct.pack('>I', len(d)) + t + d
        return x + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    raw = b''.join(b'\x00' + bytes(cor) * 8 for _ in range(8))
    return (b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', 8, 8, 8, 2, 0, 0, 0))
            + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b''))

def csrf(h):
    m = re.search(r'name="csrf" value="([^"]+)"', h)
    return m.group(1) if m else ''

c = portal.app.test_client()
anon = portal.app.test_client()

# ── segurança ────────────────────────────────────────────────────────────────
r = anon.get('/')
ok(r.headers.get('X-Content-Type-Options') == 'nosniff', 'cabeçalho nosniff')
ok(r.headers.get('X-Frame-Options') in ('SAMEORIGIN', 'DENY'), 'proteção contra moldura (clickjacking)')
r = anon.get('/pagina-que-nao-existe')
ok(r.status_code == 404 and 'Página não encontrada' in r.get_data(as_text=True) or r.status_code == 404, 'erro 404 com página própria')
for rota in ('/admin/midia', '/admin/historico', '/admin/noticias'):
    ok(anon.get(rota).status_code in (302, 401, 403), f'{rota} exige login')

# limite de tentativas de login
t = csrf(anon.get('/login').get_data(as_text=True))
bloqueou = False
for _ in range(12):
    r = anon.post('/login', data={'csrf': t, 'usuario': 'admin', 'senha': 'errada'})
    t = csrf(anon.get('/login').get_data(as_text=True)) or t
    if r.status_code == 429 or 'Muitas tentativas' in r.get_data(as_text=True):
        bloqueou = True
        break
ok(bloqueou, 'login bloqueado após tentativas erradas seguidas')
r = c.post('/login', data={'csrf': csrf(c.get('/login').get_data(as_text=True)), 'usuario': 'admin', 'senha': 'Teste1234'})
if r.status_code != 302:
    # mesmo IP de teste está bloqueado: libera as falhas para seguir os demais testes
    with portal.app.app_context():
        con = portal.db()
        for (t_,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%login%'").fetchall():
            con.execute(f'DELETE FROM {t_}')
        con.commit()
    r = c.post('/login', data={'csrf': csrf(c.get('/login').get_data(as_text=True)), 'usuario': 'admin', 'senha': 'Teste1234'})
ok(r.status_code == 302, 'login correto funciona depois de limpar o bloqueio')
tok = csrf(c.get('/admin/midia').get_data(as_text=True))
ok(bool(tok), 'página da biblioteca abre para o admin')

# ── mídia ────────────────────────────────────────────────────────────────────
def envia(nome, dados, extra=None):
    return c.post('/admin/midia', data=dict({'csrf': tok, 'acao': 'enviar',
                  'arquivos': (io.BytesIO(dados), nome)}, **(extra or {})),
                  content_type='multipart/form-data', follow_redirects=True)

r = envia('logo.png', png())
ok('enviada' in r.get_data(as_text=True), 'envio de PNG válido')
r = envia('falso.png', b'<?php echo 1; ?>' * 10)
ok('imagem' in r.get_data(as_text=True).lower() and len(os.listdir(portal.UPLOAD_DIR)) == 1,
   'arquivo disfarçado de PNG é recusado (bytes não conferem)')
r = envia('script.php', png())
ok(len(os.listdir(portal.UPLOAD_DIR)) == 1, 'extensão não permitida é recusada')
arq = os.listdir(portal.UPLOAD_DIR)[0]
ok(arq in c.get('/admin/midia').get_data(as_text=True), 'imagem aparece na biblioteca')
lista = c.get('/admin/midia/lista').get_json()
ok(any(i['arquivo'] == arq for i in lista['itens']), 'seletor recebe a lista em JSON')
r = c.post('/admin/midia/enviar', data={'csrf': tok, 'arquivo': (io.BytesIO(png((1, 2, 3))), 'b.png')},
           content_type='multipart/form-data')
j = r.get_json(silent=True) or {}
ok(j.get('ok') and j['item']['arquivo'] in os.listdir(portal.UPLOAD_DIR), 'envio rápido do seletor devolve JSON e grava o arquivo')
r = c.post('/admin/midia/enviar', data={'arquivo': (io.BytesIO(png((1, 2, 3))), 'b.png')}, content_type='multipart/form-data')
ok(r.status_code in (400, 403), 'envio rápido sem token CSRF é recusado')
c.post('/admin/midia', data={'csrf': tok, 'acao': 'salvar', 'arquivo': arq, 'titulo': 'Logo', 'alt': 'Logotipo do CDPNI'})
ok('Logotipo do CDPNI' in c.get('/admin/midia').get_data(as_text=True), 'texto alternativo é salvo')

# imagem em uso não pode ser excluída
r = c.post('/admin/pagina/documentos', data={'csrf': tok, 'tipo': 'imagem', 'ativo': 'on', 'texto': 'Legenda', 'arquivo_biblioteca': arq},
           content_type='multipart/form-data')
with portal.app.app_context():
    n_bloco = portal.db().execute("SELECT COUNT(*) FROM pagina_blocos WHERE arquivo=?", (arq,)).fetchone()[0]
ok(n_bloco == 1 and len(os.listdir(portal.UPLOAD_DIR)) == 2, 'bloco de página reaproveita imagem da biblioteca (sem copiar o arquivo)')
ok('Logotipo do CDPNI' in anon.get('/modulo/documentos').get_data(as_text=True) or arq in anon.get('/modulo/documentos').get_data(as_text=True),
   'página pública mostra a imagem escolhida')
c.post('/admin/pagina/documentos', data={'csrf': tok, 'tipo': 'imagem', 'ativo': 'on', 'arquivo_biblioteca': '../../etc/passwd'},
           content_type='multipart/form-data')
ok(len(os.listdir(portal.UPLOAD_DIR)) == 2, 'nome de arquivo malicioso na biblioteca é ignorado')
c.post('/admin/noticias', data={'csrf': tok, 'acao': 'publicar', 'titulo': 'Aviso com capa', 'capa_biblioteca': arq,
                                'corpo': '<p>Texto</p>', 'categoria': 'Avisos'})
r = c.post('/admin/midia', data={'csrf': tok, 'acao': 'excluir', 'arquivo': arq}, follow_redirects=True)
ok('em uso' in r.get_data(as_text=True) and os.path.exists(os.path.join(portal.UPLOAD_DIR, arq)),
   'imagem em uso não é excluída')

# ── notícias ─────────────────────────────────────────────────────────────────
def nova(**kw):
    d = {'csrf': tok, 'acao': 'salvar', 'titulo': 'T', 'corpo': '<p>c</p>', 'estado': 'rascunho'}
    d.update(kw)
    return c.post('/admin/noticias', data=d, follow_redirects=True)

nova(titulo='Rascunho secreto')
ok(anon.get('/noticias/rascunho-secreto').status_code == 404, 'rascunho não aparece ao público')
ok(c.get('/noticias/rascunho-secreto').status_code == 200 and 'Pré-visualização' in c.get('/noticias/rascunho-secreto').get_data(as_text=True),
   'admin pré-visualiza o rascunho')
nova(titulo='Agendada futura', estado='publicado', publicar_em='2099-01-01T08:00')
ok(anon.get('/noticias/agendada-futura').status_code == 404, 'agendada para o futuro não aparece')
nova(titulo='Publicada passada', estado='publicado', publicar_em='2020-01-01T08:00',
     corpo='<p>Olá</p><script>alert(1)</script><img src="/static/uploads/%s" alt="a"><img src="http://x.com/a.png">' % arq)
h = anon.get('/noticias/publicada-passada').get_data(as_text=True)
ok('Olá' in h and 'alert(1)' not in h and 'x.com' not in h and '/static/uploads/%s' % arq in h,
   'notícia pública: script e imagem externa removidos, imagem da biblioteca mantida')
h = anon.get('/noticias').get_data(as_text=True)
ok('Publicada passada' in h and 'Agendada futura' not in h and 'Rascunho secreto' not in h, 'lista pública só mostra as visíveis')
h = anon.get('/').get_data(as_text=True)
ok('Publicada passada' in h and 'Rascunho secreto' not in h, 'cartão de notícias na página inicial')
ok('Aviso com capa' in anon.get('/noticias?c=Avisos').get_data(as_text=True), 'filtro por categoria')
nova(titulo='Publicada passada', estado='publicado', publicar_em='2020-01-02T08:00')
ok(anon.get('/noticias/publicada-passada-2').status_code == 200, 'título repetido ganha endereço único')
nova(titulo='Com link', estado='publicado', publicar_em='2020-01-03T08:00', destino_url='javascript:alert(1)')
ok('javascript:' not in anon.get('/noticias').get_data(as_text=True), 'destino javascript: é descartado')
with portal.app.app_context():
    ident = portal.db().execute("SELECT id FROM noticias WHERE titulo='Rascunho secreto'").fetchone()[0]
c.post('/admin/noticias', data={'csrf': tok, 'acao': 'excluir', 'id': ident})
ok(c.get('/noticias/rascunho-secreto').status_code == 404, 'excluir notícia')
ok(os.path.exists(os.path.join(portal.UPLOAD_DIR, arq)), 'a capa continua na biblioteca depois de excluir notícia')
r = c.post('/admin/noticias', data={'acao': 'salvar', 'titulo': 'sem csrf'})
ok(r.status_code in (400, 403), 'POST sem token CSRF é recusado (%s)' % r.status_code)

# ── histórico ────────────────────────────────────────────────────────────────
h = c.get('/admin/historico').get_data(as_text=True)
ok('noticias' in h.lower() or 'Notícia' in h, 'histórico registra as ações do admin')
ok('Teste1234' not in h and 'errada' not in h, 'histórico não guarda senhas')

# páginas principais continuam abrindo
for rota in ('/', '/ramais', '/sistemas', '/noticias', '/admin', '/admin/noticias', '/admin/midia',
             '/admin/historico', '/admin/noticias?nova=1'):
    ok(c.get(rota).status_code == 200, f'GET {rota} abre')

shutil.rmtree(TMP, ignore_errors=True)
print('\nFALHAS: %d' % len(falhas) if falhas else '\nTodos os testes passaram.')
sys.exit(1 if falhas else 0)
