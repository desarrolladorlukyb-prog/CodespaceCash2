#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de scraping para Rama Judicial - Version Codespaces.
Usa Playwright (funciona en contenedores). No requiere captcha.

Uso:
    python scrape_rama_judicial_codespace.py "NOMBRE COMPLETO" ["Natural"|"Juridica"]

Variables de entorno opcionales:
    (ninguna requerida)
"""

import sys
import json
import time
from collections import defaultdict
from playwright.sync_api import sync_playwright


URL_RAMA = "https://consultaprocesos.ramajudicial.gov.co/Procesos/NombreRazonSocial"

DEPARTAMENTOS = [
    'AMAZONAS', 'ANTIOQUIA', 'ARAUCA', 'ATLANTICO', 'ATLÁNTICO',
    'BOLIVAR', 'BOLÍVAR', 'BOYACA', 'BOYACÁ', 'CALDAS', 'CAQUETA',
    'CAQUETÁ', 'CASANARE', 'CAUCA', 'CESAR', 'CHOCO', 'CHOCÓ',
    'CORDOBA', 'CÓRDOBA', 'CUNDINAMARCA', 'GUAINIA', 'GUAINÍA',
    'GUAVIARE', 'HUILA', 'LA GUAJIRA', 'MAGDALENA', 'META',
    'NARINO', 'NARIÑO', 'NORTE DE SANTANDER', 'PUTUMAYO',
    'QUINDIO', 'QUINDÍO', 'RISARALDA', 'SAN ANDRES', 'SAN ANDRÉS',
    'SANTANDER', 'SUCRE', 'TOLIMA', 'VALLE DEL CAUCA', 'VAUPES',
    'VAUPÉS', 'VICHADA', 'BOGOTA', 'BOGOTÁ'
]


def extraer_departamento(texto: str) -> str:
    """Extrae el nombre del departamento del texto del despacho."""
    # Buscar entre parentesis
    if '(' in texto and ')' in texto:
        dept = texto[texto.rfind('(') + 1:texto.rfind(')')]
        return dept.strip().title()

    texto_upper = texto.upper()
    for depto in DEPARTAMENTOS:
        if depto in texto_upper:
            return depto.title()

    # Buscar por ciudad capital
    ciudades = {
        'BOGOTÁ': 'Bogota', 'BOGOTA': 'Bogota',
        'MEDELLÍN': 'Antioquia', 'MEDELLIN': 'Antioquia',
        'CALI': 'Valle Del Cauca',
        'BARRANQUILLA': 'Atlantico',
        'CARTAGENA': 'Bolivar',
    }
    for ciudad, depto in ciudades.items():
        if ciudad in texto_upper:
            return depto

    return 'Desconocido'


def consultar_procesos(nombre_completo: str, tipo_persona: str = "Natural") -> dict:
    """Realiza la consulta de procesos judiciales por nombre."""

    with sync_playwright() as p:
        browser = None
        try:
            print("Iniciando navegador...", file=sys.stderr)
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
            )

            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            page.set_default_timeout(60000)

            # Navegar a la pagina
            print(f"Navegando a: {URL_RAMA}", file=sys.stderr)
            page.goto(URL_RAMA, wait_until='domcontentloaded')
            page.wait_for_timeout(5000)  # Esperar que Vue.js cargue

            # Seleccionar "Todos los Procesos" (consulta completa)
            print("Seleccionando: Todos los Procesos...", file=sys.stderr)
            try:
                radio = page.locator('#input-67')
                if radio.count() > 0:
                    radio.click()
                    print("Radio 'Todos los Procesos' seleccionado", file=sys.stderr)
                else:
                    # Fallback: buscar por label
                    label = page.locator("label:has-text('Todos los Procesos')")
                    if label.count() > 0:
                        label.click()
                        print("Radio seleccionado por label", file=sys.stderr)
            except Exception as e:
                print(f"Advertencia al seleccionar radio: {e}", file=sys.stderr)

            page.wait_for_timeout(1000)

            # Seleccionar tipo de persona
            print(f"Seleccionando tipo de persona: {tipo_persona}", file=sys.stderr)
            try:
                select = page.locator('#input-72')
                select.click()
                page.wait_for_timeout(1000)

                if tipo_persona.lower() == "natural":
                    option = page.locator("div[role='listbox'] >> text=Natural")
                else:
                    option = page.locator("div[role='listbox'] >> text=/Jur/")

                option.click()
                print(f"Tipo de persona seleccionado: {tipo_persona}", file=sys.stderr)
            except Exception as e:
                print(f"Advertencia al seleccionar tipo persona: {e}", file=sys.stderr)
                # Intentar con send_keys
                try:
                    select = page.locator('#input-72')
                    select.fill(tipo_persona)
                except Exception:
                    pass

            page.wait_for_timeout(1000)

            # Ingresar nombre
            print(f"Ingresando nombre: {nombre_completo}", file=sys.stderr)
            page.fill('#input-78', nombre_completo)
            page.wait_for_timeout(1000)

            # Click en Consultar
            print("Haciendo click en Consultar...", file=sys.stderr)
            try:
                consultar_btn = page.locator("button[aria-label='Consultar por nombre o razón social']")
                consultar_btn.click()
            except Exception:
                # Fallback: buscar por texto
                consultar_btn = page.locator("button:has-text('Consultar')")
                consultar_btn.first.click()

            # Esperar resultados
            print("Esperando resultados...", file=sys.stderr)
            page.wait_for_timeout(10000)

            # Extraer resultados
            body_text = page.inner_text("body")

            if "No se encontraron resultados" in body_text or "no matches found" in body_text.lower():
                print("No se encontraron resultados", file=sys.stderr)
                return {
                    'success': True,
                    'tiene_resultados': False,
                    'total_resultados': 0,
                    'mensaje': 'No se encontraron procesos judiciales',
                    'nombre_consultado': nombre_completo,
                    'tipo_persona': tipo_persona,
                    'resultados_por_departamento': {}
                }

            # Buscar filas de la tabla
            filas = page.locator("div.v-data-table tbody tr").all()

            if not filas:
                filas = page.locator("table tbody tr").all()

            if not filas:
                filas = page.locator("[role='row']").all()

            if not filas:
                print("No se encontraron filas de resultados", file=sys.stderr)
                return {
                    'success': True,
                    'tiene_resultados': False,
                    'total_resultados': 0,
                    'mensaje': 'No se pudieron extraer los resultados de la tabla',
                    'nombre_consultado': nombre_completo,
                    'tipo_persona': tipo_persona,
                    'resultados_por_departamento': {}
                }

            print(f"Encontradas {len(filas)} filas", file=sys.stderr)

            # Organizar resultados por departamento
            resultados_por_depto = defaultdict(list)
            total_procesos = 0

            for idx, fila in enumerate(filas, 1):
                try:
                    celdas = fila.locator("td").all()

                    if len(celdas) < 4:
                        continue

                    proceso = {'numero': idx}

                    # Columna 1: Numero de Radicacion
                    if len(celdas) > 1:
                        numero_rad = celdas[1].inner_text().strip()
                        if numero_rad:
                            proceso['numero_radicacion'] = numero_rad

                    # Columna 2: Fechas
                    if len(celdas) > 2:
                        fechas = celdas[2].inner_text().strip()
                        if fechas:
                            proceso['fechas'] = fechas
                            partes_fecha = fechas.split('\n')
                            if len(partes_fecha) >= 2:
                                proceso['fecha_radicacion'] = partes_fecha[0].strip()
                                proceso['ultima_actuacion'] = partes_fecha[1].strip()

                    # Columna 3: Despacho y Departamento
                    departamento = 'Desconocido'
                    if len(celdas) > 3:
                        despacho_texto = celdas[3].inner_text().strip()
                        if despacho_texto:
                            proceso['despacho_departamento'] = despacho_texto
                            departamento = extraer_departamento(despacho_texto)
                            proceso['departamento'] = departamento

                    # Columna 4: Sujetos Procesales
                    if len(celdas) > 4:
                        sujetos = celdas[4].inner_text().strip()
                        if sujetos:
                            proceso['sujetos_procesales'] = sujetos
                            if 'Demandante:' in sujetos:
                                partes = sujetos.split('Demandado:')
                                proceso['demandante'] = partes[0].replace('Demandante:', '').strip()
                                if len(partes) > 1:
                                    proceso['demandado'] = partes[1].strip()

                    proceso['texto_completo'] = fila.inner_text().strip()
                    resultados_por_depto[departamento].append(proceso)
                    total_procesos += 1

                except Exception as e:
                    print(f"Error en fila {idx}: {e}", file=sys.stderr)
                    continue

            resultados_por_depto = dict(resultados_por_depto)

            print(f"Total procesos: {total_procesos}", file=sys.stderr)
            print(f"Departamentos: {list(resultados_por_depto.keys())}", file=sys.stderr)

            return {
                'success': True,
                'tiene_resultados': total_procesos > 0,
                'total_resultados': total_procesos,
                'mensaje': f'Se encontraron {total_procesos} proceso(s) judicial(es)',
                'nombre_consultado': nombre_completo,
                'tipo_persona': tipo_persona,
                'resultados_por_departamento': resultados_por_depto
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)[:300],
                'nombre_consultado': nombre_completo,
                'tipo_persona': tipo_persona
            }
        finally:
            if browser:
                browser.close()


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            'success': False,
            'error': 'Uso: python scrape_rama_judicial_codespace.py <nombre_completo> [tipo_persona]'
        }))
        return

    nombre_completo = sys.argv[1]
    tipo_persona = sys.argv[2] if len(sys.argv) > 2 else "Natural"

    result = consultar_procesos(nombre_completo, tipo_persona)

    # Solo el JSON al stdout (los logs van a stderr)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
