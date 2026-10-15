"""Gera site/index.html (página completa para hospedagem própria) e
artefato.html (só o conteúdo, para o protótipo no Claude) a partir de index.src.html."""
import pathlib
AQUI = pathlib.Path(__file__).parent
css = (AQUI / "vendor" / "leaflet.css").read_text()
src = (AQUI / "index.src.html").read_text().replace("/*LEAFLET_CSS*/", css)
(AQUI / "artefato.html").write_text(src)
titulo, _, resto = src.partition("\n")
(AQUI / "index.html").write_text(
    '<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
    '<link rel="alternate" type="application/rss+xml" title="Alerta Árvore SP" href="feed.xml">\n'
    + titulo + "\n" + resto.replace("<div class=\"app\">", "</head>\n<body>\n<div class=\"app\">", 1)
    + "\n</body>\n</html>\n")
print("ok")
