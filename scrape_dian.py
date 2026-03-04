#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de scraping para DIAN RUT - Version Codespaces.
Usa Playwright + CapMonster (Turnstile captcha solver).

Uso:
    python scrape_dian_codespace.py "1234567890"

Variables de entorno requeridas:
    CAPMONSTER_API_KEY: API key de CapMonster Cloud
"""

import sys
import os
import json
import re
import time
import requests
from playwright.sync_api import sync_playwright


# Configuracion
CAPMONSTER_API_KEY = os.environ.get('CAPMONSTER_API_KEY', '')
URL_DIAN = "https://muisca.dian.gov.co/WebRutMuisca/DefConsultaEstadoRUT.faces"
TURNSTILE_SITE_KEY = '0x4AAAAAAAg1YFKr1lxPdUIL'


def solve_turnstile_captcha(page_url: str) -> str:
    """
    Resuelve el captcha de Cloudflare Turnstile usando CapMonster Cloud API REST.

    Args:
        page_url: URL de la pagina donde esta el captcha

    Returns:
        str: Token del captcha resuelto, o None si falla
    """
    if not CAPMONSTER_API_KEY:
        print("ERROR: CAPMONSTER_API_KEY no configurada", file=sys.stderr)
        return None

    try:
        print("Resolviendo Cloudflare Turnstile con CapMonster...", file=sys.stderr)
        print(f"  Website URL: {page_url}", file=sys.stderr)
        print(f"  Website Key: {TURNSTILE_SITE_KEY}", file=sys.stderr)

        create_task_url = "https://api.capmonster.cloud/createTask"
        get_result_url = "https://api.capmonster.cloud/getTaskResult"

        # Paso 1: Crear tarea
        create_payload = {
            "clientKey": CAPMONSTER_API_KEY,
            "task": {
                "type": "TurnstileTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": TURNSTILE_SITE_KEY
            }
        }

        print("Enviando tarea a CapMonster...", file=sys.stderr)
        create_response = requests.post(create_task_url, json=create_payload, timeout=30)
        create_data = create_response.json()

        if create_data.get('errorId', 1) != 0:
            error_code = create_data.get('errorCode', 'UNKNOWN')
            error_desc = create_data.get('errorDescription', 'Sin descripcion')
            print(f"ERROR creando tarea: {error_code} - {error_desc}", file=sys.stderr)
            return None

        task_id = create_data.get('taskId')
        if not task_id:
            print("ERROR: No se recibio taskId", file=sys.stderr)
            return None

        print(f"Tarea creada. TaskId: {task_id}", file=sys.stderr)

        # Paso 2: Polling para obtener el resultado
        max_attempts = 40  # 40 x 3s = 120s max
        for attempt in range(max_attempts):
            time.sleep(3)

            get_result_payload = {
                "clientKey": CAPMONSTER_API_KEY,
                "taskId": task_id
            }

            result_response = requests.post(get_result_url, json=get_result_payload, timeout=30)
            result_data = result_response.json()

            if result_data.get('errorId', 1) != 0:
                error_code = result_data.get('errorCode', 'UNKNOWN')
                print(f"ERROR obteniendo resultado: {error_code}", file=sys.stderr)
                return None

            status = result_data.get('status')

            if status == 'ready':
                solution = result_data.get('solution', {})
                token = solution.get('token')
                if token:
                    print(f"Turnstile resuelto en {(attempt + 1) * 3}s", file=sys.stderr)
                    return token
                return None

            elif status == 'processing':
                if attempt % 5 == 0:
                    print(f"Procesando... ({(attempt + 1) * 3}s)", file=sys.stderr)
                continue

        print("ERROR: Timeout esperando resolucion del captcha", file=sys.stderr)
        return None

    except Exception as e:
        print(f"ERROR resolviendo Turnstile: {str(e)}", file=sys.stderr)
        return None


def extract_result(page) -> dict:
    """Extrae los datos del resultado de la consulta DIAN RUT."""
    datos = {
        'numero_documento': None,
        'primer_apellido': None,
        'segundo_apellido': None,
        'primer_nombre': None,
        'otros_nombres': None,
        'fecha_actualizacion': None,
        'estado': None,
        'tiene_registro': True
    }

    try:
        body_text = page.inner_text("body")

        # Verificar si no esta inscrito en el RUT
        if 'NO ESTÁ INSCRITO EN EL RUT' in body_text.upper() or 'NO ESTA INSCRITO EN EL RUT' in body_text.upper():
            datos['tiene_registro'] = False
            datos['estado'] = 'NO INSCRITO'

            nit_match = re.search(r'(\d{9,10})', body_text)
            if nit_match:
                datos['numero_documento'] = nit_match.group(1)

            print("Documento NO inscrito en el RUT", file=sys.stderr)
            return datos

        # Si esta inscrito, extraer la informacion completa
        print("Documento inscrito en el RUT. Extrayendo info...", file=sys.stderr)

        ids_exactos = {
            'numero_documento': 'vistaConsultaEstadoRUT:formConsultaEstadoRUT:numNit',
            'primer_apellido': 'vistaConsultaEstadoRUT:formConsultaEstadoRUT:primerApellido',
            'segundo_apellido': 'vistaConsultaEstadoRUT:formConsultaEstadoRUT:segundoApellido',
            'primer_nombre': 'vistaConsultaEstadoRUT:formConsultaEstadoRUT:primerNombre',
            'otros_nombres': 'vistaConsultaEstadoRUT:formConsultaEstadoRUT:otrosNombres',
            'estado': 'vistaConsultaEstadoRUT:formConsultaEstadoRUT:estado'
        }

        for campo, elem_id in ids_exactos.items():
            try:
                elem = page.locator(f'#{elem_id.replace(":", "\\\\:")}')
                if elem.count() > 0:
                    value = elem.input_value() if elem.get_attribute('value') is not None else elem.inner_text()
                    if value:
                        datos[campo] = value.strip()
                        print(f"  {campo}: {value.strip()}", file=sys.stderr)
            except Exception:
                pass

        # Extraer fecha de actualizacion del texto
        fecha_match = re.search(r'(\d{1,2}-\d{1,2}-\d{4})\s+(\d{2}:\d{2}:\d{2})', body_text)
        if fecha_match:
            datos['fecha_actualizacion'] = f"{fecha_match.group(1)} {fecha_match.group(2)}"
        else:
            fecha_match = re.search(r'(\d{1,2}-\d{1,2}-\d{4})', body_text)
            if fecha_match:
                datos['fecha_actualizacion'] = fecha_match.group(1)

    except Exception as e:
        print(f"Error extrayendo resultado: {str(e)}", file=sys.stderr)

    return datos


def consultar_rut(numero_documento: str) -> dict:
    """Realiza la consulta completa del estado RUT en la DIAN."""

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
            print(f"Navegando a: {URL_DIAN}", file=sys.stderr)
            page.goto(URL_DIAN, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)

            # Verificar errores HTTP del sitio
            page_title = page.title() or ''
            body_text = page.inner_text('body') or ''
            current_url = page.url or ''

            if ('500' in page_title and 'Error' in page_title) or \
               'Internal Server Error' in body_text or \
               '503 Service' in page_title or \
               'Service Temporarily Unavailable' in body_text:
                return {
                    'status': 'error',
                    'message': f'El sitio de la DIAN no esta disponible (titulo: {page_title.strip() or "vacio"})'
                }

            if 'dian.gov.co/Paginas' in current_url or 'Inicio.aspx' in current_url:
                return {
                    'status': 'error',
                    'message': 'El sistema MUISCA de la DIAN esta en mantenimiento'
                }

            # Verificar que el formulario existe
            nit_input_id = 'vistaConsultaEstadoRUT\\:formConsultaEstadoRUT\\:numNit'
            try:
                page.wait_for_selector(f'#{nit_input_id}', timeout=15000)
            except Exception:
                return {
                    'status': 'error',
                    'message': 'La pagina de la DIAN no cargo correctamente (formulario no encontrado)'
                }

            # Resolver Turnstile captcha
            print("Resolviendo Cloudflare Turnstile...", file=sys.stderr)
            turnstile_token = solve_turnstile_captcha(page.url)

            if not turnstile_token:
                return {
                    'status': 'error',
                    'message': 'No se pudo resolver el captcha de Cloudflare Turnstile'
                }

            # Inyectar el token en la pagina
            print("Inyectando token de Turnstile...", file=sys.stderr)
            inject_result = page.evaluate(f"""() => {{
                var tokenInput = document.querySelector('input[name="cf-turnstile-response"]');
                if (tokenInput) {{
                    tokenInput.value = '{turnstile_token}';
                    var hddToken = document.getElementById('vistaConsultaEstadoRUT:formConsultaEstadoRUT:hddToken');
                    if (hddToken) {{
                        hddToken.value = '{turnstile_token}';
                    }}
                    return true;
                }}
                return false;
            }}""")

            if not inject_result:
                return {
                    'status': 'error',
                    'message': 'No se pudo inyectar el token del captcha'
                }

            page.wait_for_timeout(1000)

            # Llenar numero de documento
            print(f"Ingresando documento: {numero_documento}", file=sys.stderr)
            page.fill(f'#{nit_input_id}', str(numero_documento))
            page.wait_for_timeout(1000)

            # Click en buscar
            print("Haciendo click en buscar...", file=sys.stderr)
            buscar_id = 'vistaConsultaEstadoRUT\\:formConsultaEstadoRUT\\:btnBuscar'
            page.click(f'#{buscar_id}')
            page.wait_for_timeout(5000)

            # Extraer resultado
            print("Extrayendo resultado...", file=sys.stderr)
            datos = extract_result(page)

            return {
                'status': 'success',
                'message': 'Consulta de RUT realizada correctamente',
                'datos': datos,
                'numero_documento_solicitado': numero_documento
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': f'Error inesperado: {str(e)[:300]}'
            }
        finally:
            if browser:
                browser.close()


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            'status': 'error',
            'message': 'Uso: python scrape_dian_codespace.py <numero_documento>'
        }))
        return

    numero_documento = sys.argv[1]

    result = consultar_rut(numero_documento)

    # Solo el JSON al stdout (los logs van a stderr)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
