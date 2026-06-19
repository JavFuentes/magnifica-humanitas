#!/usr/bin/env python3
"""
Generador de lector HTML dark mode para textos largos.

Uso:
    python generar_lector.py enciclica.txt
    python generar_lector.py enciclica.txt -o salida.html -t "Magnifica Humanitas"

Soporta markdown básico: # headings, **bold**, *italic*, listas, citas (>).
Si el texto es plano, lo divide en párrafos por líneas en blanco.
"""

import argparse
import html as html_lib
import re
from pathlib import Path


# ---------- PARSER DE TEXTO ----------

def escape(text: str) -> str:
    return html_lib.escape(text, quote=False)


def inline_format(text: str) -> str:
    """Aplica formato inline: **bold**, *italic*, `code`."""
    text = escape(text)
    # Code inline
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    # Bold (debe ir antes que italic)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__([^_]+)__', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
    text = re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'<em>\1</em>', text)
    return text


def slugify(text: str) -> str:
    """Convierte un heading en un id válido para anclas."""
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[\s-]+', '-', text).strip('-')
    return text or 'section'


def preprocess_text(text: str) -> str:
    """Repara texto extraído de PDFs.

    - Une palabras partidas por guión al final de línea: 'PER-\\nSONA' -> 'PERSONA'
    - Normaliza fines de línea
    """
    # Normalizar saltos de línea
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Unir palabras partidas con guión de hifenación:
    # "palabra-\nsigue" -> "palabrasigue" (cuando la línea siguiente sigue con minúscula o mayúscula sin espacio)
    # Patrón: guión al final de línea seguido de salto y palabra que continúa
    text = re.sub(
        r'(\w)-\n(\w)',
        r'\1\2',
        text,
    )

    # Limpieza de espacios múltiples al inicio de líneas (común en PDFs con sangría)
    text = re.sub(r'\n[ \t]+(?=\S)', '\n', text)

    return text


# Ordinales en español usados para detectar capítulos en texto formal
ORDINALS_ES = (
    r'(?:PRIMER[OA]?|SEGUND[OA]|TERCER[OA]?|CUART[OA]|QUINT[OA]|SEXT[OA]|'
    r'S[EÉ]PTIM[OA]|OCTAV[OA]|NOVEN[OA]|D[EÉ]CIM[OA]|UND[EÉ]CIM[OA]|'
    r'DUOD[EÉ]CIM[OA]|DECIMOTERCER[OA]?|DECIMOCUART[OA])'
)

CHAPTER_RE = re.compile(
    r'^(CAP[IÍ]TULO|PARTE|SECCI[OÓ]N|LIBRO|T[IÍ]TULO|ART[IÍ]CULO)\s+'
    r'(' + ORDINALS_ES + r'|[IVXLCDM]+|\d+)',
    re.IGNORECASE,
)


# Conectores españoles típicos: si una línea de título termina con uno de estos,
# es probable que el título continúe en la línea siguiente (partido por margen de PDF).
TITLE_CONNECTORS = {
    'DE', 'DEL', 'EN', 'LA', 'EL', 'LOS', 'LAS', 'Y', 'A', 'POR', 'PARA',
    'SU', 'SUS', 'QUE', 'CON', 'SIN', 'O', 'U', 'AL', 'DESDE', 'HASTA',
    'SOBRE', 'ANTE', 'BAJO', 'TRAS', 'ENTRE', 'HACIA', 'SEGÚN', 'CONTRA',
    'NI', 'MI', 'TU', 'UN', 'UNA', 'UNOS', 'UNAS', 'COMO',
}

# Preposiciones/artículos al INICIO de línea que indican continuación del título anterior
PREPOSITIONS_START = {
    'EN', 'DE', 'DEL', 'A', 'AL', 'PARA', 'POR', 'SOBRE', 'ENTRE',
    'HASTA', 'DESDE', 'SIN', 'CON', 'BAJO', 'ANTE', 'HACIA', 'TRAS',
    'CONTRA', 'SEGÚN', 'LA', 'EL', 'LOS', 'LAS', 'UN', 'UNA', 'UNOS',
    'UNAS', 'Y', 'O', 'U', 'NI',
}


def is_subtitle_candidate(stripped: str, lines: list, idx: int) -> bool:
    """Detecta líneas que parecen subtítulos (heading h3) en case normal.

    Criterios:
    - aislada por blancos (línea anterior y siguiente vacías)
    - 3 < len(texto) < 100
    - empieza con mayúscula
    - NO termina con signo de oración (. , ; : ! ?)
    - NO está en mayúsculas (eso lo maneja otra rama)
    - NO es un párrafo numerado ni item de lista
    """
    if not stripped or len(stripped) >= 100 or len(stripped) <= 3:
        return False
    prev_blank = (idx == 0 or not lines[idx - 1].strip())
    next_blank = (idx + 1 >= len(lines) or not lines[idx + 1].strip())
    if not (prev_blank and next_blank):
        return False
    if stripped[-1] in '.,;:!?':
        return False
    first_alpha = next((c for c in stripped if c.isalpha()), None)
    if first_alpha is None or not first_alpha.isupper():
        return False
    if re.match(r'^\d+[\.\)]\s+', stripped):
        return False
    if re.match(r'^[\-\*\+]\s+', stripped):
        return False
    letters = [c for c in stripped if c.isalpha()]
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) >= 0.85:
        return False
    return True


def parse_text(text: str):
    """Parsea el texto y devuelve (html_body, toc_items).

    toc_items es una lista de dicts: {level, title, id}
    """
    text = preprocess_text(text)
    lines = text.split('\n')
    html_parts = []
    used_ids = set()

    i = 0
    paragraph_buffer = []
    list_buffer = []
    list_type = None  # 'ul' o 'ol'
    quote_buffer = []

    def flush_paragraph():
        nonlocal paragraph_buffer
        if paragraph_buffer:
            text_joined = ' '.join(paragraph_buffer).strip()
            if text_joined:
                html_parts.append(f'<p>{inline_format(text_joined)}</p>')
            paragraph_buffer = []

    def flush_list():
        nonlocal list_buffer, list_type
        if list_buffer:
            tag = list_type
            items_html = ''.join(f'<li>{inline_format(item)}</li>' for item in list_buffer)
            html_parts.append(f'<{tag}>{items_html}</{tag}>')
            list_buffer = []
            list_type = None

    def flush_quote():
        nonlocal quote_buffer
        if quote_buffer:
            text_joined = ' '.join(quote_buffer).strip()
            if text_joined:
                html_parts.append(f'<blockquote><p>{inline_format(text_joined)}</p></blockquote>')
            quote_buffer = []

    def flush_all():
        flush_paragraph()
        flush_list()
        flush_quote()

    def make_unique_id(base: str) -> str:
        candidate = base
        n = 2
        while candidate in used_ids:
            candidate = f"{base}-{n}"
            n += 1
        used_ids.add(candidate)
        return candidate

    toc_items = []
    last_heading_text = None  # para deduplicar headings consecutivos idénticos
    seen_headings = {}  # title_normalizado_upper -> anchor_id (para dedupe global)

    def add_heading(level: int, title: str):
        nonlocal last_heading_text
        normalized = re.sub(r'\s+', ' ', title.strip())
        norm_key = normalized.upper()

        # Dedupe 1: heading idéntico al anterior consecutivo (encabezados de página repetidos)
        if norm_key == (last_heading_text or '').upper():
            return

        # Dedupe 2: ya apareció antes en otra parte del documento (típico de un índice
        # al inicio que repite los títulos de los capítulos). Eliminar la primera
        # aparición y quedarse con esta nueva (que es la que tiene contenido real).
        if norm_key in seen_headings:
            prev_anchor = seen_headings[norm_key]
            # Quitarlo de toc_items
            toc_items[:] = [t for t in toc_items if t['id'] != prev_anchor]
            # Quitarlo de html_parts (marcar como string vacío para no romper índices)
            for k, part in enumerate(html_parts):
                if f'id="{prev_anchor}"' in part and re.match(r'<h\d', part):
                    html_parts[k] = ''
                    break

        last_heading_text = normalized
        anchor_id = make_unique_id(slugify(normalized))
        toc_items.append({'level': level, 'title': normalized, 'id': anchor_id})
        seen_headings[norm_key] = anchor_id
        html_parts.append(
            f'<h{level} id="{anchor_id}">{inline_format(normalized)}</h{level}>'
        )

    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()

        # Línea vacía: cierra párrafo / lista / cita
        if not stripped:
            flush_all()
            i += 1
            continue

        # Headings markdown
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if heading_match:
            flush_all()
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            add_heading(level, title)
            i += 1
            continue

        # Lista no ordenada
        ul_match = re.match(r'^[\-\*\+]\s+(.+)$', stripped)
        if ul_match:
            if list_type != 'ul':
                flush_paragraph()
                flush_list()
                flush_quote()
                list_type = 'ul'
            list_buffer.append(ul_match.group(1))
            i += 1
            continue

        # Lista ordenada o párrafo numerado (típico de encíclicas)
        ol_match = re.match(r'^(\d+)[\.\)]\s+(.+)$', stripped)
        if ol_match:
            num = ol_match.group(1)
            rest = ol_match.group(2)

            # Mirar hacia adelante: ¿el siguiente item viene SIN línea en blanco o CON ella?
            # - Sin línea en blanco entre items cortos → lista ordenada verdadera
            # - Con línea en blanco entre items largos → párrafo numerado de encíclica
            j = i + 1
            blank_seen = False
            while j < len(lines) and not lines[j].strip():
                blank_seen = True
                j += 1
            next_is_another_item = (
                j < len(lines) and bool(re.match(r'^\d+[\.\)]\s+', lines[j].strip()))
            )

            is_numbered_paragraph = (
                (blank_seen and next_is_another_item)  # patrón clásico de encíclica
                or len(rest) > 120                       # item demasiado largo, es un párrafo
                or (list_type != 'ol' and blank_seen)    # arrancó aislado con blanco después
            )

            if is_numbered_paragraph:
                flush_all()
                # Acumular líneas continuas que pertenecen a este mismo párrafo numerado
                para_lines = [rest]
                k = i + 1
                while k < len(lines):
                    nxt = lines[k].strip()
                    if not nxt:
                        break
                    # si la siguiente línea es otro item o un heading, paramos
                    if re.match(r'^(\d+[\.\)]|#{1,6}\s|>\s|[\-\*\+]\s)', nxt):
                        break
                    para_lines.append(nxt)
                    k += 1
                joined = ' '.join(para_lines)
                html_parts.append(
                    f'<p class="numbered" id="p{num}">'
                    f'<span class="num">{num}.</span> {inline_format(joined)}</p>'
                )
                i = k
                continue
            else:
                if list_type != 'ol':
                    flush_paragraph()
                    flush_list()
                    flush_quote()
                    list_type = 'ol'
                list_buffer.append(rest)
                i += 1
                continue

        # Cita
        quote_match = re.match(r'^>\s?(.*)$', stripped)
        if quote_match:
            flush_paragraph()
            flush_list()
            quote_buffer.append(quote_match.group(1))
            i += 1
            continue

        # Separador horizontal
        if re.match(r'^([-*_])\1{2,}$', stripped):
            flush_all()
            html_parts.append('<hr>')
            i += 1
            continue

        # Detección de "heading sin marcar": líneas SOLAS en MAYÚSCULAS o tipo "CAPÍTULO ..."
        # (útil para encíclicas y documentos formales sin markdown)
        is_isolated_before = (i == 0 or not lines[i - 1].strip())
        looks_like_chapter = bool(CHAPTER_RE.match(stripped))

        # Verificar si el título continúa en líneas siguientes
        def collect_heading_block(start_idx: int) -> tuple:
            """Acumula líneas consecutivas en MAYÚSCULAS que forman el mismo
            título (partido por margen de PDF, o portada con sub-líneas).

            Para cada línea siguiente, decide si UNIR o no:
            - Si la anterior termina con conector ('DE LA', 'EN EL', ...) → unir
            - Si la anterior termina con guión → unir (palabra partida)
            - Si la siguiente empieza con preposición ('EN', 'DE', 'PARA', ...) → unir
            - Si la siguiente está seguida de CONTENIDO real (párrafo numerado o
              texto en case normal), es un título INDEPENDIENTE → no unir
            - Si la siguiente está seguida de otra línea en CAPS o nada, sigue
              siendo parte de la portada → unir

            Devuelve (texto_completo, índice_siguiente).
            """
            parts = [lines[start_idx].strip()]
            k = start_idx + 1
            while k < len(lines):
                nxt = lines[k].strip()
                if not nxt:
                    break
                letters = [c for c in nxt if c.isalpha()]
                if not letters:
                    break
                upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
                if upper_ratio < 0.85:
                    break
                if CHAPTER_RE.match(nxt):
                    break

                # Señales de continuación
                prev_line = parts[-1].rstrip()
                words_prev = prev_line.split()
                last_word_prev = words_prev[-1].rstrip('.,;:').upper() if words_prev else ''
                ends_with_connector = last_word_prev in TITLE_CONNECTORS
                ends_with_hyphen = prev_line.endswith('-')

                words_next = nxt.split()
                first_word_next = words_next[0].rstrip('.,;:').upper() if words_next else ''
                starts_with_prep = first_word_next in PREPOSITIONS_START

                # ¿La línea nxt está seguida de CONTENIDO real (no otra línea CAPS)?
                # Si lo está, entonces nxt es un título independiente y NO la unimos.
                nxt_followed_by_content = False
                m = k + 1
                while m < len(lines) and not lines[m].strip():
                    m += 1
                if m < len(lines):
                    after_nxt = lines[m].strip()
                    after_letters = [c for c in after_nxt if c.isalpha()]
                    if re.match(r'^\d+[\.\)]\s+', after_nxt):
                        nxt_followed_by_content = True
                    elif after_letters:
                        after_upper_ratio = (
                            sum(1 for c in after_letters if c.isupper()) / len(after_letters)
                        )
                        if after_upper_ratio < 0.85:
                            nxt_followed_by_content = True

                signal_continuation = (
                    ends_with_connector or ends_with_hyphen or starts_with_prep
                )

                # Si nxt es seguida de contenido y NO hay señal clara de continuación,
                # es un título independiente → parar.
                if nxt_followed_by_content and not signal_continuation:
                    break

                parts.append(nxt)
                k += 1
            return ' '.join(parts), k

        # Heurística para "all caps title" (puede ocupar varias líneas)
        letters_in_line = [c for c in stripped if c.isalpha()]
        upper_ratio_line = (
            sum(1 for c in letters_in_line if c.isupper()) / len(letters_in_line)
            if letters_in_line else 0
        )
        is_all_caps_isolated = (
            upper_ratio_line >= 0.85
            and len(letters_in_line) >= 3
            and is_isolated_before
            and len(stripped) < 200
        )

        if looks_like_chapter:
            flush_all()
            full_title, next_i = collect_heading_block(i)
            add_heading(2, full_title)
            i = next_i
            continue

        if is_all_caps_isolated:
            flush_all()
            full_title, next_i = collect_heading_block(i)
            if len(full_title) > 220:
                paragraph_buffer.append(stripped)
                i += 1
                continue
            add_heading(2, full_title)
            i = next_i
            continue

        # Detección de subtítulos en case normal (línea aislada, corta,
        # sin terminación de oración, empieza con mayúscula).
        # Típico de las subsecciones de las encíclicas.
        if is_subtitle_candidate(stripped, lines, i):
            flush_all()
            add_heading(3, stripped)
            i += 1
            continue

        # Línea normal: acumular en párrafo
        # Pero primero cierra lista/cita si veníamos arrastrando
        if list_buffer:
            flush_list()
        if quote_buffer:
            flush_quote()
        paragraph_buffer.append(stripped)
        i += 1

    flush_all()
    return '\n'.join(html_parts), toc_items


# ---------- PLANTILLA HTML ----------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600;8..60,700&family=Geist:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #262624;
  --bg-elevated: #30302e;
  --bg-soft: #2c2b29;
  --text: #ebe9e2;
  --text-soft: #c9c4ba;
  --text-muted: #8a857c;
  --accent: #d97757;
  --accent-soft: #c98660;
  --border: #3a3937;
  --border-soft: #322f2c;
  --shadow: 0 4px 20px rgba(0,0,0,0.3);
  --max-width: 680px;
  --font-size: 18px;
  --line-height: 1.75;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

html { scroll-behavior: smooth; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Source Serif 4', Georgia, serif;
  font-size: var(--font-size);
  line-height: var(--line-height);
  font-feature-settings: "kern", "liga", "onum";
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  min-height: 100vh;
  overflow-x: hidden;
}

/* ---------- HEADER ---------- */
.header {
  position: fixed;
  top: 0; left: 0; right: 0;
  background: rgba(38, 38, 36, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-soft);
  z-index: 100;
  padding: 14px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  font-family: 'Geist', system-ui, sans-serif;
  font-size: 14px;
}

.header-title {
  color: var(--text-soft);
  font-weight: 500;
  letter-spacing: 0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 50%;
}

.header-title span.accent { color: var(--accent); }

.header-controls {
  display: flex;
  gap: 6px;
  align-items: center;
}

.btn {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-soft);
  font-family: inherit;
  font-size: 13px;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.btn:hover {
  background: var(--bg-elevated);
  color: var(--text);
  border-color: var(--accent-soft);
}

.btn.icon { padding: 6px 9px; font-size: 14px; min-width: 32px; }

.progress-bar {
  position: fixed;
  top: 0; left: 0;
  height: 2px;
  background: var(--accent);
  z-index: 101;
  transition: width 0.1s ease-out;
  width: 0%;
}

/* ---------- TOC ---------- */
.toc {
  position: fixed;
  left: 0; top: 56px;
  bottom: 0;
  width: 280px;
  background: var(--bg-soft);
  border-right: 1px solid var(--border-soft);
  overflow-y: auto;
  padding: 32px 20px 80px;
  transform: translateX(-100%);
  transition: transform 0.25s ease;
  font-family: 'Geist', system-ui, sans-serif;
  font-size: 13.5px;
  line-height: 1.5;
}

.toc.open { transform: translateX(0); }

.toc-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 16px;
  padding-left: 8px;
}

.toc a {
  display: block;
  color: var(--text-soft);
  text-decoration: none;
  padding: 6px 8px;
  border-radius: 4px;
  margin: 1px 0;
  transition: all 0.12s ease;
  border-left: 2px solid transparent;
}

.toc a:hover {
  color: var(--text);
  background: var(--bg-elevated);
}

.toc a.active {
  color: var(--accent);
  border-left-color: var(--accent);
  background: rgba(217, 119, 87, 0.06);
}

.toc a.l1 { font-weight: 600; padding-left: 8px; }
.toc a.l2 { padding-left: 16px; }
.toc a.l3 { padding-left: 28px; font-size: 12.5px; color: var(--text-muted); }
.toc a.l4, .toc a.l5, .toc a.l6 { padding-left: 40px; font-size: 12px; color: var(--text-muted); }

/* ---------- MAIN ---------- */
.main {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 120px 32px 160px;
  transition: margin-left 0.25s ease;
}

body.toc-open .main {
  margin-left: 280px;
}

@media (max-width: 1100px) {
  body.toc-open .main { margin-left: 0; }
}

.doc-title {
  font-family: 'Fraunces', 'Source Serif 4', serif;
  font-weight: 500;
  font-size: clamp(2.2rem, 5vw, 3.4rem);
  line-height: 1.1;
  letter-spacing: -0.02em;
  color: var(--text);
  margin-bottom: 48px;
  font-variation-settings: "opsz" 144, "SOFT" 50;
}

.doc-title::after {
  content: '';
  display: block;
  width: 60px;
  height: 2px;
  background: var(--accent);
  margin-top: 24px;
}

.content h1, .content h2, .content h3, .content h4 {
  font-family: 'Fraunces', 'Source Serif 4', serif;
  font-weight: 600;
  color: var(--text);
  line-height: 1.25;
  letter-spacing: -0.01em;
  margin-top: 2.5em;
  margin-bottom: 0.7em;
  font-variation-settings: "opsz" 60;
}

.content h1 { font-size: 1.9em; }
.content h2 { font-size: 1.55em; }
.content h3 { font-size: 1.25em; color: var(--text-soft); }
.content h4 { font-size: 1.08em; color: var(--text-soft); }

.content h2::before {
  content: '';
  display: block;
  width: 32px;
  height: 1px;
  background: var(--accent);
  margin-bottom: 18px;
  opacity: 0.6;
}

.content p {
  margin-bottom: 1.3em;
  color: var(--text);
  hyphens: auto;
  text-align: justify;
  text-justify: inter-word;
}

.content p:first-of-type::first-letter {
  /* drop cap sutil para el primer párrafo */
  font-family: 'Fraunces', serif;
  font-weight: 500;
  font-size: 3.3em;
  float: left;
  line-height: 0.85;
  margin: 0.1em 0.1em 0 0;
  color: var(--accent);
}

/* Si el primer párrafo es numerado, no aplicar drop cap */
.content p.numbered:first-of-type::first-letter {
  font-family: inherit;
  font-weight: inherit;
  font-size: inherit;
  float: none;
  line-height: inherit;
  margin: 0;
  color: inherit;
}

/* Párrafos numerados estilo encíclica */
.content p.numbered {
  position: relative;
  padding-left: 3.2em;
  margin-bottom: 1.5em;
  text-indent: 0;
}

.content p.numbered .num {
  position: absolute;
  left: 0;
  top: 0.05em;
  width: 2.6em;
  text-align: right;
  padding-right: 0.5em;
  color: var(--accent);
  font-family: 'Geist', system-ui, sans-serif;
  font-weight: 500;
  font-size: 0.85em;
  letter-spacing: 0.02em;
  user-select: none;
}

.content p.numbered:target {
  /* resaltar el párrafo cuando se navega con #pN */
  background: rgba(217, 119, 87, 0.07);
  border-radius: 4px;
  padding-top: 8px;
  padding-bottom: 8px;
  margin-left: -8px;
  margin-right: -8px;
  padding-right: 8px;
  transition: background 0.5s;
}

@media (max-width: 640px) {
  .content p.numbered { padding-left: 2.4em; }
  .content p.numbered .num { width: 2em; font-size: 0.8em; }
}

.content strong { color: var(--text); font-weight: 600; }
.content em { color: var(--text-soft); font-style: italic; }

.content blockquote {
  border-left: 3px solid var(--accent);
  padding: 4px 0 4px 24px;
  margin: 1.8em 0;
  color: var(--text-soft);
  font-style: italic;
}

.content blockquote p { margin-bottom: 0.6em; }
.content blockquote p:last-child { margin-bottom: 0; }

.content ul, .content ol {
  margin: 1.2em 0 1.2em 1.5em;
  padding-left: 0.8em;
}

.content li { margin-bottom: 0.5em; }

.content li::marker { color: var(--accent); }

.content code {
  font-family: 'Geist Mono', ui-monospace, monospace;
  font-size: 0.88em;
  background: var(--bg-elevated);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--accent-soft);
}

.content hr {
  border: none;
  height: 1px;
  background: var(--border);
  margin: 3em 0;
  position: relative;
}

.content hr::after {
  content: '✦';
  position: absolute;
  top: -10px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--bg);
  padding: 0 12px;
  color: var(--accent);
  font-size: 12px;
}

.content a {
  color: var(--accent);
  text-decoration: none;
  border-bottom: 1px solid rgba(217, 119, 87, 0.3);
  transition: border-color 0.15s;
}

.content a:hover { border-bottom-color: var(--accent); }

/* ---------- FOOTER ---------- */
.footer {
  text-align: center;
  margin-top: 80px;
  padding-top: 40px;
  border-top: 1px solid var(--border-soft);
  font-family: 'Geist', system-ui, sans-serif;
  font-size: 13px;
  color: var(--text-muted);
}

.footer .glyph { color: var(--accent); font-size: 14px; }

/* ---------- SETTINGS PANEL ---------- */
.settings {
  position: fixed;
  right: 24px;
  bottom: 24px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px;
  display: flex;
  gap: 6px;
  box-shadow: var(--shadow);
  z-index: 50;
  font-family: 'Geist', system-ui, sans-serif;
}

/* ---------- PRINT / PDF ---------- */
@media print {
  :root { --max-width: 100%; --font-size: 11pt; --line-height: 1.5; }
  body { background: white; color: #1a1a1a; }
  .header, .toc, .settings, .progress-bar { display: none !important; }
  .main { padding: 0; margin: 0; max-width: 100%; }
  body.toc-open .main { margin-left: 0; }
  .doc-title { color: #1a1a1a; page-break-after: avoid; }
  .content h1, .content h2, .content h3 { color: #1a1a1a; page-break-after: avoid; }
  .content h2::before { background: #999; }
  .content p { color: #1a1a1a; orphans: 3; widows: 3; }
  .content p:first-of-type::first-letter { color: #555; }
  .content blockquote { color: #444; border-left-color: #999; }
  .content a { color: #1a1a1a; border-bottom: none; }
  .content code { background: #f0f0f0; color: #1a1a1a; }
  .content hr::after { background: white; color: #999; }
  .footer { color: #666; border-top-color: #ccc; }
}

/* ---------- MOBILE ---------- */
@media (max-width: 640px) {
  :root { --font-size: 17px; }
  .main { padding: 100px 20px 80px; }
  .header { padding: 12px 16px; }
  .header-title { font-size: 13px; }
  .btn { padding: 5px 10px; font-size: 12px; }
  .toc { width: 85%; }
  .settings { right: 12px; bottom: 12px; }
}

/* Scrollbar */
::-webkit-scrollbar { width: 10px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 5px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
</style>
</head>
<body>

<div class="progress-bar" id="progressBar"></div>

<header class="header">
  <div class="header-title">
    <span class="accent">✦</span> __TITLE__
  </div>
  <div class="header-controls">
    __TOC_BUTTON__
    <button class="btn" onclick="window.print()" title="Exportar a PDF (Ctrl+P)">PDF</button>
  </div>
</header>

__TOC_HTML__

<main class="main">
  __COVER__
  <article class="content">
__CONTENT__
  </article>
  <footer class="footer">
    <div class="glyph">✦</div>
    <div style="margin-top:8px">fin del documento</div>
  </footer>
</main>

<div class="settings">
  <button class="btn icon" onclick="changeFontSize(-1)" title="Reducir texto">A−</button>
  <button class="btn icon" onclick="changeFontSize(1)" title="Aumentar texto">A+</button>
  <button class="btn icon" onclick="changeWidth(-40)" title="Columna más angosta">◀▶</button>
  <button class="btn icon" onclick="changeWidth(40)" title="Columna más ancha">◀  ▶</button>
</div>

<script>
// ---------- Barra de progreso ----------
const progressBar = document.getElementById('progressBar');
function updateProgress() {
  const scrollTop = window.scrollY;
  const docHeight = document.documentElement.scrollHeight - window.innerHeight;
  const progress = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
  progressBar.style.width = progress + '%';
}
window.addEventListener('scroll', updateProgress, { passive: true });
updateProgress();

// ---------- TOC toggle + scroll spy ----------
function toggleToc() {
  document.body.classList.toggle('toc-open');
  const toc = document.querySelector('.toc');
  if (toc) toc.classList.toggle('open');
}

const headings = Array.from(document.querySelectorAll('.content h1, .content h2, .content h3, .content h4'));
const tocLinks = Array.from(document.querySelectorAll('.toc a'));

function updateActiveToc() {
  const scrollPos = window.scrollY + 150;
  let current = null;
  for (const h of headings) {
    if (h.offsetTop <= scrollPos) current = h.id;
    else break;
  }
  tocLinks.forEach(a => {
    a.classList.toggle('active', a.getAttribute('href') === '#' + current);
  });
}
window.addEventListener('scroll', updateActiveToc, { passive: true });
updateActiveToc();

// ---------- Controles de tipografía ----------
function changeFontSize(delta) {
  const root = document.documentElement;
  const current = parseFloat(getComputedStyle(root).getPropertyValue('--font-size'));
  const next = Math.max(13, Math.min(26, current + delta));
  root.style.setProperty('--font-size', next + 'px');
  localStorage.setItem('reader-font-size', next);
}

function changeWidth(delta) {
  const root = document.documentElement;
  const current = parseFloat(getComputedStyle(root).getPropertyValue('--max-width'));
  const next = Math.max(520, Math.min(900, current + delta));
  root.style.setProperty('--max-width', next + 'px');
  localStorage.setItem('reader-max-width', next);
}

// Restaurar preferencias
const savedSize = localStorage.getItem('reader-font-size');
if (savedSize) document.documentElement.style.setProperty('--font-size', savedSize + 'px');
const savedWidth = localStorage.getItem('reader-max-width');
if (savedWidth) document.documentElement.style.setProperty('--max-width', savedWidth + 'px');

// Restaurar posición de scroll
window.addEventListener('beforeunload', () => {
  localStorage.setItem('reader-scroll', window.scrollY);
});
window.addEventListener('load', () => {
  const saved = localStorage.getItem('reader-scroll');
  if (saved) window.scrollTo(0, parseInt(saved));
});

// ---------- Atajos ----------
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === '+' || e.key === '=') { changeFontSize(1); e.preventDefault(); }
  if (e.key === '-' || e.key === '_') { changeFontSize(-1); e.preventDefault(); }
  if (e.key === 't' || e.key === 'T') { toggleToc(); e.preventDefault(); }
});
</script>

</body>
</html>
"""


def build_toc_html(toc_items):
    if not toc_items:
        return '', ''
    links = []
    for item in toc_items:
        cls = f"l{item['level']}"
        links.append(
            f'<a href="#{item["id"]}" class="{cls}">{escape(item["title"])}</a>'
        )
    toc_html = (
        '<nav class="toc" id="toc">'
        '<div class="toc-label">Contenido</div>'
        + ''.join(links)
        + '</nav>'
    )
    toc_button = '<button class="btn" onclick="toggleToc()" title="Tabla de contenidos (T)">☰ Índice</button>'
    return toc_html, toc_button


def generate_html(title: str, text: str, show_cover: bool = True) -> str:
    content_html, toc_items = parse_text(text)
    toc_html, toc_button = build_toc_html(toc_items)
    cover_html = (
        f'<h1 class="doc-title">{escape(title)}</h1>' if show_cover else ''
    )
    return (
        HTML_TEMPLATE
        .replace('__TITLE__', escape(title))
        .replace('__CONTENT__', content_html)
        .replace('__TOC_HTML__', toc_html)
        .replace('__TOC_BUTTON__', toc_button)
        .replace('__COVER__', cover_html)
    )


# ---------- MAIN ----------

def main():
    parser = argparse.ArgumentParser(
        description='Genera un lector HTML dark mode estilo Claude a partir de un archivo de texto.'
    )
    parser.add_argument('input', help='Archivo de texto (.txt o .md) de entrada')
    parser.add_argument(
        '-o', '--output',
        help='Archivo HTML de salida (por defecto: <nombre>.html)',
        default=None,
    )
    parser.add_argument(
        '-t', '--title',
        help='Título del documento (por defecto: nombre del archivo)',
        default=None,
    )
    parser.add_argument(
        '--no-cover',
        action='store_true',
        help='No mostrar el título grande al inicio del documento',
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f'Error: no se encontró el archivo "{input_path}"')
        return 1

    size = input_path.stat().st_size
    if size == 0:
        print(f'Error: el archivo "{input_path}" está vacío (0 bytes).')
        return 1

    # Detección automática de encoding (Windows suele usar utf-16 o cp1252)
    raw = input_path.read_bytes()
    encodings_to_try = ['utf-8-sig', 'utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'cp1252', 'latin-1']
    text = None
    used_encoding = None
    for enc in encodings_to_try:
        try:
            decoded = raw.decode(enc)
            # Verificar que tenga contenido legible (no solo bytes nulos o basura)
            if decoded.strip() and any(c.isalpha() for c in decoded[:500]):
                text = decoded
                used_encoding = enc
                break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if text is None:
        print(f'Error: no se pudo decodificar "{input_path}". ¿Es un archivo de texto?')
        return 1

    print(f'  Encoding detectado: {used_encoding} ({size:,} bytes en disco)')
    title = args.title or input_path.stem.replace('_', ' ').replace('-', ' ').title()
    output_path = Path(args.output) if args.output else input_path.with_suffix('.html')

    html_out = generate_html(title, text, show_cover=not args.no_cover)
    output_path.write_text(html_out, encoding='utf-8')

    chars = len(text)
    words = len(text.split())
    print(f'✓ Generado: {output_path}')
    print(f'  {chars:,} caracteres · {words:,} palabras · ~{words // 200} min de lectura')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())