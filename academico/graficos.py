"""Gráficos SVG generados en el servidor (sin bibliotecas externas: funcionan sin internet).

Paleta categórica validada (orden fijo): establecimiento = azul, nacional = naranja, grupo similar = aqua.
Cada marca lleva <title> para el tooltip al pasar el mouse, y las vistas muestran también la tabla.
"""
from html import escape
from math import ceil

from django.utils.safestring import mark_safe

SERIES = ["#257de0", "#f47230", "#00b894"]
TEXTO = "#191919"
TEXTO_2 = "#666666"
GRILLA = "#e6e6e6"
CRITICO = "#d03b3b"
FUENTE = "font-family:inherit"


def _num(v, dec=1):
    if v is None:
        return "—"
    v = float(v)
    return (f"{v:.{dec}f}" if dec else f"{v:.0f}").replace(".", ",")


def barras(filas, maximo=None, umbral=None, umbral_txt="", dec=1, sufijo="", ancho=640, alto_fila=28,
           malo=None, rojas=()):
    """Barras horizontales. filas: [(etiqueta, valor)]. malo(valor) -> True marca la barra en rojo + ícono."""
    filas = [(e, v) for e, v in filas]
    if not filas:
        return mark_safe('<p class="text-muted small mb-0">Sin datos.</p>')
    valores = [float(v) for _, v in filas if v is not None]
    maximo = float(maximo or (max(valores) if valores else 1) or 1)
    izq, der = 175, 60
    util = ancho - izq - der
    alto = alto_fila * len(filas) + 24
    partes = [f'<svg viewBox="0 0 {ancho} {alto}" class="w-100" role="img" style="{FUENTE};max-height:{alto * 1.2:.0f}px">']
    enteros = dec == 0 and maximo <= 12  # conteos pequeños: marcas en números enteros
    if enteros:
        maximo = float(max(1, ceil(maximo)))
    marcas = ([k / maximo for k in range(int(maximo) + 1)] if maximo in (7, 7.0) or enteros
              else (0, 0.25, 0.5, 0.75, 1))
    for t in marcas:
        x = izq + util * t
        partes.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="4" y2="{alto - 18}" stroke="{GRILLA}" stroke-width="1"/>')
        partes.append(f'<text x="{x:.1f}" y="{alto - 4}" font-size="10" fill="{TEXTO_2}" text-anchor="middle">'
                      f'{_num(maximo * t, 0 if maximo >= 10 or enteros else 1)}{sufijo}</text>')
    for i, (etiqueta, valor) in enumerate(filas):
        y = 6 + i * alto_fila
        partes.append(f'<text x="{izq - 8}" y="{y + alto_fila / 2 + 1:.1f}" font-size="12" fill="{TEXTO}" '
                      f'text-anchor="end" dominant-baseline="middle">{escape(_corta(str(etiqueta), 26))}</text>')
        if valor is None:
            partes.append(f'<text x="{izq + 4}" y="{y + alto_fila / 2 + 1:.1f}" font-size="11" fill="{TEXTO_2}" '
                          f'dominant-baseline="middle">sin datos</text>')
            continue
        w = max(2.0, util * min(float(valor), maximo) / maximo)
        rojo = (malo(valor) if malo else False) or etiqueta in rojas
        color = CRITICO if rojo else SERIES[0]
        partes.append(f'<g><title>{escape(str(etiqueta))}: {_num(valor, dec)}{sufijo}</title>'
                      f'<rect x="{izq}" y="{y + 5}" width="{w:.1f}" height="{alto_fila - 10}" rx="4" fill="{color}"/>'
                      f'<rect x="{izq}" y="{y}" width="{util}" height="{alto_fila}" fill="transparent"/></g>')
        marca = " ▲" if rojo else ""
        partes.append(f'<text x="{izq + w + 6:.1f}" y="{y + alto_fila / 2 + 1:.1f}" font-size="11" fill="{TEXTO}" '
                      f'dominant-baseline="middle">{_num(valor, dec)}{sufijo}{marca}</text>')
    if umbral is not None:
        x = izq + util * float(umbral) / maximo
        partes.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="0" y2="{alto - 18}" stroke="{CRITICO}" '
                      f'stroke-width="1.5" stroke-dasharray="4 3"/>')
        if umbral_txt:
            partes.append(f'<text x="{x + 4:.1f}" y="10" font-size="10" fill="{CRITICO}">{escape(umbral_txt)}</text>')
    partes.append("</svg>")
    return mark_safe("".join(partes))


def _corta(texto, n):
    return texto if len(texto) <= n else texto[:n - 1].rstrip() + "…"


def lineas(anios, series, ancho=440, alto=220, dec=0):
    """Líneas en el tiempo. series: [(nombre, {anio: valor})] en orden fijo (máx. 3)."""
    puntos = [v for _, d in series for v in d.values() if v is not None]
    if not puntos or not anios:
        return mark_safe('<p class="text-muted small mb-0">Sin datos.</p>')
    lo, hi = min(puntos), max(puntos)
    margen = max(5, (hi - lo) * 0.15)
    lo, hi = lo - margen, hi + margen
    izq, der, arr, aba = 40, 70, 14, 26
    w, h = ancho - izq - der, alto - arr - aba

    def X(a):
        return izq + (w * (anios.index(a) / (len(anios) - 1)) if len(anios) > 1 else w / 2)

    def Y(v):
        return arr + h - (float(v) - lo) / (hi - lo) * h

    partes = [f'<svg viewBox="0 0 {ancho} {alto}" class="w-100" role="img" style="{FUENTE};max-height:260px">']
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        partes.append(f'<line x1="{izq}" x2="{izq + w}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{GRILLA}"/>'
                      f'<text x="{izq - 6}" y="{Y(v):.1f}" font-size="10" fill="{TEXTO_2}" text-anchor="end" '
                      f'dominant-baseline="middle">{v:.0f}</text>')
    for a in anios:
        partes.append(f'<text x="{X(a):.1f}" y="{alto - 8}" font-size="10" fill="{TEXTO_2}" text-anchor="middle">{a}</text>')
    finales = []
    for i, (nombre, datos) in enumerate(series):
        color = SERIES[i]
        pts = [(X(a), Y(datos[a]), a, datos[a]) for a in anios if datos.get(a) is not None]
        if len(pts) > 1:
            d = " ".join(f"{'M' if j == 0 else 'L'}{x:.1f},{y:.1f}" for j, (x, y, _, _) in enumerate(pts))
            partes.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>')
        for x, y, a, v in pts:
            partes.append(f'<g><title>{escape(nombre)} {a}: {_num(v, dec)}</title>'
                          f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{color}" stroke="#fff" stroke-width="2"/>'
                          f'<circle cx="{x:.1f}" cy="{y:.1f}" r="12" fill="transparent"/></g>')
        if pts:
            finales.append([pts[-1][1], pts[-1][0], pts[-1][3]])
    finales.sort()
    for k in range(1, len(finales)):  # separa etiquetas finales que se topan
        if finales[k][0] - finales[k - 1][0] < 13:
            finales[k][0] = finales[k - 1][0] + 13
    for y, x, v in finales:
        partes.append(f'<text x="{x + 9:.1f}" y="{y:.1f}" font-size="11" fill="{TEXTO}" dominant-baseline="middle">'
                      f'{_num(v, dec)}</text>')
    partes.append("</svg>")
    leyenda = "".join(
        f'<span class="me-3 text-nowrap"><span style="display:inline-block;width:14px;height:3px;background:{SERIES[i]};'
        f'vertical-align:middle;border-radius:2px"></span> {escape(n)}</span>'
        for i, (n, d) in enumerate(series) if any(v is not None for v in d.values()))
    return mark_safe(f'<div class="small mb-1" style="color:{TEXTO_2}">{leyenda}</div>' + "".join(partes))
