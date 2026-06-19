# -*- coding: utf-8 -*-
"""
Generador de páginas traducidas para Magnifica Humanitas.

Produce  en.html · it.html · pt.html  a partir de:
  - index.html            -> plantilla (CSS, JS, maquetación del lector español)
  - en.txt / it.txt / pt.txt  -> traducción COMPLETA del documento

y actualiza  index.html  (selector de idioma + hreflang) y  sitemap.xml.

No hay que tocar el cuerpo del texto a mano: el contenido se reconstruye
alineando por número de párrafo (1–245) y de nota ([1]–[224]). La estructura
de capítulos es idéntica en todos los idiomas: hay un capítulo (h2) justo
antes de los párrafos {1, 17, 46, 90, 131, 182, 229}; entre el ¶245 y las
notas van la datación y la firma «… PP. XIV».

Uso:   python generar_traducciones.py
"""

import html as html_lib
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # consola Windows -> UTF-8
except Exception:
    pass

BASE = Path(__file__).parent
SITE = "https://magnificahumanitas.live"
CHAPTER_STARTS = {1, 17, 46, 90, 131, 182, 229}

# Idiomas que aparecen en el selector (solo los que tienen contenido).
SELECTOR_ITEMS = [
    ("es", "ES", "index.html"),
    ("en", "EN", "en.html"),
    ("it", "IT", "it.html"),
    ("pt", "PT", "pt.html"),
]

VAT = "https://www.vatican.va/content/leo-xiv/{}/encyclicals/documents/20260515-magnifica-humanitas.html"


# ---------------------------------------------------------------------------
# Configuración por idioma: SOLO cadenas que no están en los .txt
# (portada, footer, etiquetas de interfaz y metadatos).
# ---------------------------------------------------------------------------
LANGS = {
    "en": {
        "code": "en", "html_lang": "en", "og_locale": "en_US",
        "txt": "en.txt", "out": "en.html",
        "page_url": f"{SITE}/en.html", "vatican_url": VAT.format("en"),
        "title": "Magnifica Humanitas — Encyclical Letter of Pope Leo XIV on Artificial Intelligence",
        "meta_desc": "Full text of Pope Leo XIV's encyclical Magnifica Humanitas on safeguarding the human person in the age of artificial intelligence (2026). Optimized reading presentation.",
        "meta_keywords": "Magnifica Humanitas, encyclical, Leo XIV, Pope, artificial intelligence, social doctrine, Catholic Church, 2026",
        "og_title": "Magnifica Humanitas — Encyclical of Pope Leo XIV",
        "og_desc": "Full text of the encyclical on safeguarding the human person in the age of artificial intelligence. Optimized dark-mode reading.",
        "tw_desc": "Full text of the encyclical on AI and human dignity. Optimized reading presentation.",
        "cover_seal_alt": "Vatican Seal",
        "cover_type": "Encyclical Letter",
        "cover_pope": "Of the Holy Father Leo XIV",
        "cover_subtitle": "On the safeguarding of the human person<br>in the age of artificial intelligence",
        "footer_copyright": "© Libreria Editrice Vaticana. Text reproduced for non-profit informational purposes.",
        "footer_source_label": "Original source:",
        "search_placeholder": "Search…",
        "toc_label": "Contents",
        "btn_toc": "☰ Contents",
        "btn_toc_title": "Table of contents (T)",
        "btn_pdf_title": "Export to PDF (Ctrl+P)",
        "search_prev_title": "Previous result",
        "search_next_title": "Next result",
        "font_dec_title": "Decrease text",
        "font_inc_title": "Increase text",
        "width_dec_title": "Narrower column",
        "width_inc_title": "Wider column",
    },
    "it": {
        "code": "it", "html_lang": "it", "og_locale": "it_IT",
        "txt": "it.txt", "out": "it.html",
        "page_url": f"{SITE}/it.html", "vatican_url": VAT.format("it"),
        "title": "Magnifica Humanitas — Lettera Enciclica di Papa Leone XIV sull'Intelligenza Artificiale",
        "meta_desc": "Testo completo della Lettera enciclica Magnifica Humanitas di Papa Leone XIV sulla custodia della persona umana nel tempo dell'intelligenza artificiale (2026). Presentazione di lettura ottimizzata.",
        "meta_keywords": "Magnifica Humanitas, enciclica, Leone XIV, Papa, intelligenza artificiale, dottrina sociale, Chiesa Cattolica, 2026",
        "og_title": "Magnifica Humanitas — Enciclica di Papa Leone XIV",
        "og_desc": "Testo completo dell'enciclica sulla custodia della persona umana nel tempo dell'intelligenza artificiale. Lettura ottimizzata.",
        "tw_desc": "Testo completo dell'enciclica sull'IA e la dignità umana. Presentazione di lettura ottimizzata.",
        "cover_seal_alt": "Sigillo Vaticano",
        "cover_type": "Lettera Enciclica",
        "cover_pope": "Del Santo Padre Leone XIV",
        "cover_subtitle": "Sulla custodia della persona umana<br>nel tempo dell'intelligenza artificiale",
        "footer_copyright": "© Libreria Editrice Vaticana. Testo riprodotto a scopo divulgativo senza fini di lucro.",
        "footer_source_label": "Fonte originale:",
        "search_placeholder": "Cerca…",
        "toc_label": "Contenuti",
        "btn_toc": "☰ Indice",
        "btn_toc_title": "Indice dei contenuti (T)",
        "btn_pdf_title": "Esporta in PDF (Ctrl+P)",
        "search_prev_title": "Risultato precedente",
        "search_next_title": "Risultato successivo",
        "font_dec_title": "Riduci testo",
        "font_inc_title": "Aumenta testo",
        "width_dec_title": "Colonna più stretta",
        "width_inc_title": "Colonna più larga",
    },
    "pt": {
        "code": "pt", "html_lang": "pt", "og_locale": "pt_PT",
        "txt": "pt.txt", "out": "pt.html",
        "page_url": f"{SITE}/pt.html", "vatican_url": VAT.format("pt"),
        "title": "Magnifica Humanitas — Carta Encíclica do Papa Leão XIV sobre a Inteligência Artificial",
        "meta_desc": "Texto completo da Carta encíclica Magnifica Humanitas do Papa Leão XIV sobre a custódia da pessoa humana no tempo da inteligência artificial (2026). Apresentação de leitura otimizada.",
        "meta_keywords": "Magnifica Humanitas, encíclica, Leão XIV, Papa, inteligência artificial, doutrina social, Igreja Católica, 2026",
        "og_title": "Magnifica Humanitas — Encíclica do Papa Leão XIV",
        "og_desc": "Texto completo da encíclica sobre a custódia da pessoa humana no tempo da inteligência artificial. Leitura otimizada.",
        "tw_desc": "Texto completo da encíclica sobre a IA e a dignidade humana. Apresentação de leitura otimizada.",
        "cover_seal_alt": "Selo do Vaticano",
        "cover_type": "Carta Encíclica",
        "cover_pope": "Do Santo Padre Leão XIV",
        "cover_subtitle": "Sobre a custódia da pessoa humana<br>no tempo da inteligência artificial",
        "footer_copyright": "© Libreria Editrice Vaticana. Texto reproduzido com fins divulgativos sem fins lucrativos.",
        "footer_source_label": "Fonte original:",
        "search_placeholder": "Pesquisar…",
        "toc_label": "Conteúdo",
        "btn_toc": "☰ Índice",
        "btn_toc_title": "Índice (T)",
        "btn_pdf_title": "Exportar para PDF (Ctrl+P)",
        "search_prev_title": "Resultado anterior",
        "search_next_title": "Resultado seguinte",
        "font_dec_title": "Reduzir texto",
        "font_inc_title": "Aumentar texto",
        "width_dec_title": "Coluna mais estreita",
        "width_inc_title": "Coluna mais larga",
    },
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "utf-16", "cp1252", "latin-1"):
        try:
            d = raw.decode(enc)
            if d.strip() and any(c.isalpha() for c in d[:500]):
                return d.replace("\r\n", "\n").replace("\r", "\n")
        except (UnicodeDecodeError, UnicodeError):
            continue
    return raw.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")


def write_text(path: Path, content: str) -> None:
    # newline="\n": evita que el modo texto de Windows retraduzca \n y duplique \r
    path.write_text(content, encoding="utf-8", newline="\n")


def esc(s: str) -> str:
    """Escapa para contenido de elemento."""
    return html_lib.escape(s, quote=False)


def esc_attr(s: str) -> str:
    """Escapa para valor de atributo entre comillas dobles."""
    return s.replace("&", "&amp;").replace('"', "&quot;")


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s-]+", "-", text).strip("-")
    return text or "section"


# ---------------------------------------------------------------------------
# Parser del .txt  ->  (paras, foots, gap_before, final_gap)
# ---------------------------------------------------------------------------
def parse_document(text: str):
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    paras, foots, gap_before, final_gap = {}, [], {}, []
    pending = []
    seen_foot = False
    buf, buf_kind, buf_n = [], None, None

    def flush():
        nonlocal buf, buf_kind, buf_n
        if buf_kind == "num":
            paras[buf_n] = " ".join(buf).strip()
        elif buf_kind == "foot":
            foots.append((buf_n, " ".join(buf).strip()))
        buf, buf_kind, buf_n = [], None, None

    for raw in lines:
        s = raw.strip()
        if not s:
            flush()
            continue
        mfoot = re.match(r"^\[(\d+)\]\s*(.*)$", s)
        mnum = re.match(r"^(\d+)\.\s*(.*)$", s)
        if mfoot:
            flush()
            if not seen_foot:
                final_gap, pending, seen_foot = pending, [], True
            buf_kind, buf_n = "foot", int(mfoot.group(1))
            buf = [f"[{mfoot.group(1)}] {mfoot.group(2)}".strip()]
        elif mnum and not seen_foot:
            flush()
            n = int(mnum.group(1))
            gap_before[n], pending = pending, []
            buf_kind, buf_n, buf = "num", n, [mnum.group(2)]
        else:
            if buf_kind in ("num", "foot"):
                buf.append(s)              # continuación del párrafo/nota
            elif not seen_foot:
                pending.append(s)          # línea de título/subtítulo
    flush()
    return paras, foots, gap_before, final_gap


def build_chapter_title(blocks) -> str:
    """Une las líneas del encabezado del capítulo.

    La 1.ª línea es el designador ("CHAPTER ONE" / "Capitolo primo" /
    "CAPÍTULO I"); se le añade ". ". El resto es el título, que puede venir
    partido en varias líneas por el ancho del texto: se une con espacio para
    NO inventar puntos (los puntos reales del original se conservan).
    """
    parts = [re.sub(r"\s+", " ", b).strip() for b in blocks if b.strip()]
    if not parts:
        return ""
    if len(parts) == 1:
        title = parts[0]
    else:
        title = parts[0].rstrip(".") + ". " + " ".join(parts[1:])
    title = re.sub(r"\.\.+", ".", title)        # colapsa puntos duplicados
    return re.sub(r"\s+", " ", title).strip().upper()


# ---------------------------------------------------------------------------
# Ensamblado de contenido + tabla de contenidos
# ---------------------------------------------------------------------------
def build_content_and_toc(doc, cfg):
    paras, foots, gap_before, final_gap = doc
    out, toc = [], []
    out.append(cover_html(cfg))

    for n in range(1, max(paras) + 1):
        gap = gap_before.get(n, [])
        if n in CHAPTER_STARTS:
            title = build_chapter_title(gap) if gap else f"§{n}"
            sid = slugify(title)
            toc.append((sid, title))
            out.append(f'<h2 id="{sid}">{esc(title)}</h2>')
        else:
            for sub in gap:
                out.append(f"<p>{esc(sub)}</p>")
        if n in paras:
            out.append(
                f'<p class="numbered" id="p{n}">'
                f'<span class="num">{n}.</span> {esc(paras[n])}</p>'
            )

    # datación + firma (entre ¶245 y las notas)
    for blk in final_gap:
        if re.search(r"PP\.\s*XIV", blk):
            title = re.sub(r"\s+", " ", blk).strip().rstrip(".").upper()
            sid = slugify(title)
            toc.append((sid, title))
            out.append(f'<h2 id="{sid}">{esc(title)}</h2>')
        else:
            out.append(f"<p>{esc(blk)}</p>")

    # notas al pie
    for _, blk in foots:
        out.append(f"<p>{esc(blk)}</p>")

    article_inner = "\n".join(out)
    links = "".join(
        f'<a href="#{sid}" class="l2">{esc(title)}</a>' for sid, title in toc
    )
    toc_html = (
        f'<nav class="toc" id="toc"><div class="toc-label">'
        f'{esc(cfg["toc_label"])}</div>{links}</nav>'
    )
    return article_inner, toc_html


def cover_html(cfg) -> str:
    return (
        '<div class="doc-cover" id="portada">\n'
        f'  <img class="cover-seal" src="vaticano_icon.png" alt="{esc_attr(cfg["cover_seal_alt"])}">\n'
        f'  <p class="cover-type">{esc(cfg["cover_type"])}</p>\n'
        '  <div class="cover-ornament"><span>✦</span></div>\n'
        '  <h1 class="cover-title">MAGNIFICA<br>HUMANITAS</h1>\n'
        '  <div class="cover-ornament"><span>✦</span></div>\n'
        f'  <p class="cover-pope">{esc(cfg["cover_pope"])}</p>\n'
        f'  <p class="cover-subtitle">{cfg["cover_subtitle"]}</p>\n'
        "</div>"
    )


def footer_html(cfg) -> str:
    return (
        '<footer class="footer">\n'
        '    <div class="glyph">✦</div>\n'
        f'    <div style="margin-top:12px">{esc(cfg["footer_copyright"])}</div>\n'
        f'    <div style="margin-top:6px">{esc(cfg["footer_source_label"])} '
        f'<a href="{esc_attr(cfg["vatican_url"])}" target="_blank" rel="noopener" '
        'style="color:var(--text-muted);text-decoration:underline;text-underline-offset:3px;">'
        "vatican.va</a></div>\n"
        "  </footer>"
    )


# ---------------------------------------------------------------------------
# Selector de idioma + hreflang (comunes a todas las páginas)
# ---------------------------------------------------------------------------
LANG_SELECTOR_CSS = """
/* ---------- SELECTOR DE IDIOMA ---------- */
.lang-switcher {
  display: flex; flex-wrap: wrap; justify-content: center; align-items: center;
  font-family: 'Geist', system-ui, sans-serif; font-size: 14px;
  letter-spacing: 0.08em; margin: 0 0 44px;
}
.lang-switcher a, .lang-switcher .active { padding: 4px 12px; text-decoration: none; transition: color 0.15s ease; }
.lang-switcher a { color: var(--text-muted); }
.lang-switcher a:hover { color: var(--text-soft); }
.lang-switcher .active { color: var(--accent); font-weight: 600; }
.lang-switcher .sep { color: var(--border); user-select: none; }
@media print { .lang-switcher { display: none !important; } }"""


def lang_selector_html(current: str) -> str:
    parts = []
    for code, label, href in SELECTOR_ITEMS:
        if code == current:
            parts.append(f'<span class="active" aria-current="page">{label}</span>')
        else:
            parts.append(f'<a href="{href}">{label}</a>')
    inner = '<span class="sep">–</span>'.join(parts)
    return f'<nav class="lang-switcher" aria-label="Idioma / Language">{inner}</nav>'


def hreflang_block() -> str:
    lines = []
    for code, _, href in SELECTOR_ITEMS:
        url = SITE + "/" if href == "index.html" else f"{SITE}/{href}"
        lines.append(f'<link rel="alternate" hreflang="{code}" href="{url}">')
    lines.append(f'<link rel="alternate" hreflang="x-default" href="{SITE}/">')
    return "\n".join(lines)


def inject_common(html: str, current: str) -> str:
    """Añade (idempotente) el CSS y HTML del selector y los hreflang."""
    if ".lang-switcher {" not in html:
        html = html.replace("</style>", LANG_SELECTOR_CSS + "\n</style>", 1)
    sel = lang_selector_html(current)
    if '<nav class="lang-switcher"' in html:
        html = re.sub(r'<nav class="lang-switcher".*?</nav>', lambda m: sel, html, count=1, flags=re.S)
    else:
        html = html.replace('<main class="main">', '<main class="main">\n  ' + sel, 1)
    if 'hreflang="en"' not in html:
        html = re.sub(r"(<link rel=\"canonical\"[^>]*>)",
                      lambda m: m.group(1) + "\n" + hreflang_block(), html, count=1)
    return html


# ---------------------------------------------------------------------------
# Transformación de la plantilla
# ---------------------------------------------------------------------------
def sub_attr(html: str, pattern: str, value: str) -> str:
    return re.sub(pattern, lambda m: m.group(1) + esc_attr(value) + m.group(2),
                  html, count=1, flags=re.S)


def build_page(template: str, cfg: dict) -> str:
    doc = parse_document(read_text(BASE / cfg["txt"]))
    report(cfg["code"], doc)
    article_inner, toc_html = build_content_and_toc(doc, cfg)
    url = cfg["page_url"]
    h = template

    h = h.replace('<html lang="es">', f'<html lang="{cfg["html_lang"]}">', 1)
    h = re.sub(r"<title>.*?</title>", lambda m: f'<title>{esc(cfg["title"])}</title>', h, count=1, flags=re.S)
    h = sub_attr(h, r'(<meta name="description" content=")[^"]*(">)', cfg["meta_desc"])
    h = sub_attr(h, r'(<meta name="keywords" content=")[^"]*(">)', cfg["meta_keywords"])
    h = sub_attr(h, r'(<link rel="canonical" href=")[^"]*(">)', url)
    h = sub_attr(h, r'(<meta property="og:title" content=")[^"]*(">)', cfg["og_title"])
    h = sub_attr(h, r'(<meta property="og:description" content=")[^"]*(">)', cfg["og_desc"])
    h = sub_attr(h, r'(<meta property="og:url" content=")[^"]*(">)', url)
    h = sub_attr(h, r'(<meta property="og:locale" content=")[^"]*(">)', cfg["og_locale"])
    h = sub_attr(h, r'(<meta name="twitter:title" content=")[^"]*(">)', cfg["og_title"])
    h = sub_attr(h, r'(<meta name="twitter:description" content=")[^"]*(">)', cfg["tw_desc"])
    # JSON-LD (la primera "description": es la del bloque schema.org)
    h = sub_attr(h, r'("description":\s*")[^"]*(")', cfg["meta_desc"])
    h = sub_attr(h, r'("inLanguage":\s*")[^"]*(")', cfg["html_lang"])
    h = sub_attr(h, r'("url":\s*")https://magnificahumanitas\.live/(")', url)
    h = sub_attr(h, r'("isBasedOn":\s*")[^"]*(")', cfg["vatican_url"])

    h = re.sub(r'<nav class="toc" id="toc">.*?</nav>', lambda m: toc_html, h, count=1, flags=re.S)
    # article_inner ya incluye la portada (cover) al principio
    new_article = '<article class="content">\n' + article_inner + "\n  </article>"
    h = re.sub(r'<article class="content">.*?</article>', lambda m: new_article, h, count=1, flags=re.S)
    h = re.sub(r'<footer class="footer">.*?</footer>', lambda m: footer_html(cfg), h, count=1, flags=re.S)

    # Interfaz (tooltips y etiquetas que quedan en el header/ajustes)
    h = h.replace('placeholder="Buscar…"', f'placeholder="{esc_attr(cfg["search_placeholder"])}"')
    h = h.replace('title="Tabla de contenidos (T)"', f'title="{esc_attr(cfg["btn_toc_title"])}"')
    h = h.replace(">☰ Índice<", f'>{cfg["btn_toc"]}<')
    h = h.replace('title="Exportar a PDF (Ctrl+P)"', f'title="{esc_attr(cfg["btn_pdf_title"])}"')
    h = h.replace('title="Resultado anterior"', f'title="{esc_attr(cfg["search_prev_title"])}"')
    h = h.replace('title="Resultado siguiente"', f'title="{esc_attr(cfg["search_next_title"])}"')
    h = h.replace('title="Reducir texto"', f'title="{esc_attr(cfg["font_dec_title"])}"')
    h = h.replace('title="Aumentar texto"', f'title="{esc_attr(cfg["font_inc_title"])}"')
    h = h.replace('title="Columna más angosta"', f'title="{esc_attr(cfg["width_dec_title"])}"')
    h = h.replace('title="Columna más ancha"', f'title="{esc_attr(cfg["width_inc_title"])}"')

    return inject_common(h, cfg["code"])


def build_sitemap() -> str:
    rows = []
    pages = [("index.html", "1.0"), ("en.html", "0.9"), ("it.html", "0.9"), ("pt.html", "0.9")]
    for href, prio in pages:
        loc = SITE + "/" if href == "index.html" else f"{SITE}/{href}"
        alts = []
        for code, _, h in SELECTOR_ITEMS:
            u = SITE + "/" if h == "index.html" else f"{SITE}/{h}"
            alts.append(f'    <xhtml:link rel="alternate" hreflang="{code}" href="{u}"/>')
        alts.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{SITE}/"/>')
        rows.append(
            "  <url>\n"
            f"    <loc>{loc}</loc>\n" + "\n".join(alts) + "\n"
            "    <lastmod>2026-05-15</lastmod>\n"
            "    <changefreq>monthly</changefreq>\n"
            f"    <priority>{prio}</priority>\n"
            "  </url>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(rows) + "\n</urlset>\n"
    )


def report(code: str, doc) -> None:
    paras, foots, gap_before, final_gap = doc
    mx = max(paras)
    miss_p = [n for n in range(1, mx + 1) if n not in paras]
    fnums = {n for n, _ in foots}
    miss_f = [n for n in range(1, max(fnums) + 1) if n not in fnums]
    print(f"  [{code}] párrafos={len(paras)} (1..{mx}) faltan={miss_p or '—'}; "
          f"notas={len(foots)} (max {max(fnums)}) faltan={miss_f or '—'}")


# ---------------------------------------------------------------------------
def main():
    template = read_text(BASE / "index.html")

    print("Generando traducciones:")
    for code, cfg in LANGS.items():
        page = build_page(template, cfg)
        write_text(BASE / cfg["out"], page)
        print(f"  ✓ {cfg['out']}  ({len(page):,} bytes)")

    # index.html (ES): solo selector + hreflang, sin tocar el contenido
    es_html = inject_common(template, "es")
    write_text(BASE / "index.html", es_html)
    print("  ✓ index.html actualizado (selector + hreflang)")

    write_text(BASE / "sitemap.xml", build_sitemap())
    print("  ✓ sitemap.xml")
    print("Listo.")


if __name__ == "__main__":
    main()
