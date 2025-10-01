#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API Árbol Genealógico - WolfData Dox
Servidor especializado para consultas de árbol genealógico
"""

import asyncio
import base64
import json
import logging
import os
import re
import time
import threading
from datetime import datetime, timedelta
from io import BytesIO

from flask import Flask, jsonify, request, send_file, make_response
from PIL import Image
from database_postgres import validate_api_key, init_database, register_api_key, delete_api_key
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import MessageMediaPhoto

import config

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Variables globales
client = None
loop = None

def parse_arbol_genealogico_response(text):
    """Parsea la respuesta del árbol genealógico."""
    data = {
        'TIPO_CONSULTA': 'ARBOL_GENEALOGICO',
        'FAMILIARES': []
    }
    
    # Limpiar el texto de caracteres especiales
    clean_text = text.replace('**', '').replace('`', '').replace('*', '')
    
    # Buscar todos los bloques de familiares
    # Patrón para el formato: **DNI** ➾ 42695001 **Edad** ➾ 40 **NOMBRES** ➾ BLINDER...
    # Usar lookahead más flexible para capturar el último familiar también
    familiar_pattern = r'DNI\s*[➾\-=]\s*(\d+)\s+Edad\s*[➾\-=]\s*(\d+)\s+NOMBRES\s*[➾\-=]\s*([^\n\r]+?)\s+APELLIDOS\s*[➾\-=]\s*([^\n\r]+?)\s+SEXO\s*[➾\-=]\s*([^\n\r]+?)\s+RELACION\s*[➾\-=]\s*([^\n\r]+?)\s+VERIFICACION\s*[➾\-=]\s*([^\n\r]+?)(?=\s+DNI\s*[➾\-=]|\s+\[|$)'
    
    matches = re.findall(familiar_pattern, clean_text, re.DOTALL)
    
    for match in matches:
        familiar = {
            'DNI': match[0],
            'EDAD': match[1],
            'NOMBRES': match[2].strip(),
            'APELLIDOS': match[3].strip(),
            'SEXO': match[4].strip(),
            'RELACION': match[5].strip(),
            'VERIFICACION': match[6].strip()
        }
        data['FAMILIARES'].append(familiar)
    
    # Si no encontramos familiares con el patrón principal, intentar patrón más flexible
    if not data['FAMILIARES']:
        # Patrón más flexible que busca cualquier secuencia DNI-Edad-NOMBRES-APELLIDOS-SEXO-RELACION-VERIFICACION
        flexible_pattern = r'DNI\s*[➾\-=]\s*(\d+).*?Edad\s*[➾\-=]\s*(\d+).*?NOMBRES\s*[➾\-=]\s*([^\n\r]+).*?APELLIDOS\s*[➾\-=]\s*([^\n\r]+).*?SEXO\s*[➾\-=]\s*([^\n\r]+).*?RELACION\s*[➾\-=]\s*([^\n\r]+).*?VERIFICACION\s*[➾\-=]\s*([^\n\r]+)'
        
        matches = re.findall(flexible_pattern, clean_text, re.DOTALL)
        
        for match in matches:
            familiar = {
                'DNI': match[0],
                'EDAD': match[1],
                'NOMBRES': match[2].strip(),
                'APELLIDOS': match[3].strip(),
                'SEXO': match[4].strip(),
                'RELACION': match[5].strip(),
                'VERIFICACION': match[6].strip()
            }
            data['FAMILIARES'].append(familiar)
    
    return data

def consult_arbol_sync(dni_number):
    """Consulta el árbol genealógico usando Telethon de forma síncrona."""
    global client, loop
    
    try:
        # Verificar que el cliente esté disponible
        if not client:
            return {
                'success': False,
                'error': 'Cliente de Telegram no inicializado'
            }
        
        # Ejecutar la consulta asíncrona en el loop existente
        future = asyncio.run_coroutine_threadsafe(consult_arbol_async(dni_number), loop)
        result = future.result(timeout=35)  # 35 segundos de timeout
        return result
        
    except asyncio.TimeoutError:
        logger.error(f"Timeout consultando ÁRBOL GENEALOGICO DNI {dni_number}")
        return {
            'success': False,
            'error': 'Timeout: No se recibió respuesta en 35 segundos'
        }
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error consultando ÁRBOL GENEALOGICO DNI {dni_number}: {error_msg}")
        
        # Si es error de desconexión, intentar reconectar
        if "disconnected" in error_msg.lower() or "connection" in error_msg.lower():
            logger.info("Error de desconexión detectado, intentando reconectar...")
            try:
                restart_telethon()
                # Esperar un poco para que se reconecte
                time.sleep(3)
                # Intentar la consulta nuevamente
                future = asyncio.run_coroutine_threadsafe(consult_arbol_async(dni_number), loop)
                result = future.result(timeout=35)
                return result
            except Exception as retry_error:
                logger.error(f"Error en reintento: {str(retry_error)}")
        
        return {
            'success': False,
            'error': f'Error en la consulta: {error_msg}'
        }

async def consult_arbol_async(dni_number):
    """Consulta asíncrona del árbol genealógico."""
    global client
    
    try:
        max_attempts = 3  # Máximo 3 intentos
        
        for attempt in range(1, max_attempts + 1):
            logger.info(f"Intento {attempt}/{max_attempts} para ÁRBOL GENEALOGICO DNI {dni_number}")
            
            # Enviar comando /ag
            command = f"/ag {dni_number}"
            sent_message = await client.send_message(config.TARGET_BOT, command)
            logger.info(f"Comando /ag enviado correctamente (intento {attempt})")
            
            # Esperar un poco para que llegue la respuesta
            await asyncio.sleep(3)
            
            # Obtener mensajes recientes
            messages = await client.get_messages(config.TARGET_BOT, limit=20)
            logger.info(f"Revisando {len(messages)} mensajes nuevos para ÁRBOL GENEALOGICO DNI {dni_number}...")
            
            # Recopilar todos los mensajes del árbol genealógico que sean respuestas a nuestro comando
            arbol_messages = []
            current_timestamp = time.time()
            command_timestamp = sent_message.date.timestamp()
            
            for message in messages:
                # Usar timestamp para evitar problemas de timezone
                if message.text and message.date.timestamp() > command_timestamp and message.date.timestamp() > current_timestamp - 300:  # 5 minutos
                    logger.info(f"Mensaje nuevo: {message.text[:100]}...")
                    
                    # Limpiar el texto para verificar
                    clean_text = message.text.replace('**', '').replace('`', '').replace('*', '')
                    logger.info(f"Texto limpio: {clean_text[:100]}...")
                    
                    # Verificar si es parte de la respuesta del árbol genealógico
                    # Buscar mensajes que contengan "ARBOL GENEALOGICO" o que tengan el patrón de familiares
                    # También incluir mensajes que contengan información de créditos (segundo mensaje)
                    if ("ARBOL GENEALOGICO" in clean_text or 
                        ("DNI" in clean_text and "RELACION" in clean_text and "VERIFICACION" in clean_text) or
                        ("DNI" in clean_text and "Edad" in clean_text and "NOMBRES" in clean_text) or
                        ("CREDITOS" in clean_text and "USUARIO" in clean_text)):
                        logger.info(f"Mensaje del árbol genealógico encontrado")
                        arbol_messages.append(message.text)
            
            # Si encontramos mensajes del árbol genealógico, combinarlos
            if arbol_messages:
                logger.info(f"¡Respuesta encontrada para ÁRBOL GENEALOGICO DNI {dni_number}!")
                logger.info(f"Se encontraron {len(arbol_messages)} mensajes")
                
                # Combinar todos los mensajes
                combined_text = "\n".join(arbol_messages)
                logger.info(f"Texto combinado: {combined_text[:200]}...")
                
                parsed_data = parse_arbol_genealogico_response(combined_text)
                logger.info(f"Datos parseados: {parsed_data}")
                
                return {
                    'success': True,
                    'data': parsed_data
                }
            
            # Si no se encontró respuesta, esperar antes del siguiente intento
            if attempt < max_attempts:
                logger.warning(f"No se detectó respuesta en intento {attempt}. Esperando 3 segundos...")
                await asyncio.sleep(3)
        
        logger.error(f"Timeout consultando ÁRBOL GENEALOGICO DNI {dni_number}")
        return {
            'success': False,
            'error': 'Timeout: No se recibió respuesta después de 3 intentos'
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error consultando ÁRBOL GENEALOGICO DNI {dni_number}: {error_msg}")
        
        # Si es error de desconexión, intentar reconectar
        if "disconnected" in error_msg.lower() or "connection" in error_msg.lower():
            logger.info("Error de desconexión detectado, intentando reconectar...")
            try:
                restart_telethon()
                # Esperar un poco para que se reconecte
                time.sleep(3)
                # Intentar la consulta nuevamente
                future = asyncio.run_coroutine_threadsafe(consult_arbol_async(dni_number), loop)
                result = future.result(timeout=35)
                return result
            except Exception as retry_error:
                logger.error(f"Error en reintento: {str(retry_error)}")
        
        return {
            'success': False,
            'error': f'Error en la consulta: {error_msg}'
        }

def restart_telethon():
    """Reinicia la conexión de Telethon."""
    global client, loop
    
    try:
        if client:
            logger.info("Cerrando cliente anterior...")
            try:
                # Esperar a que se desconecte
                future = client.disconnect()
                if future and not future.done():
                    # Esperar máximo 5 segundos
                    import concurrent.futures
                    try:
                        future.result(timeout=5)
                    except concurrent.futures.TimeoutError:
                        logger.warning("Timeout cerrando cliente anterior")
            except Exception as e:
                logger.warning(f"Error cerrando cliente anterior: {e}")
            time.sleep(2)
        
        # Crear nuevo cliente
        client = TelegramClient(
            'telethon_session',
            config.API_ID,
            config.API_HASH
        )
        
        # Iniciar en el loop existente
        if loop and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(client.start(), loop)
            future.result(timeout=30)
            logger.info("Cliente de Telethon reiniciado correctamente")
        else:
            logger.error("No hay loop de asyncio disponible para reiniciar")
            
    except Exception as e:
        logger.error(f"Error reiniciando Telethon: {str(e)}")

def init_telethon_thread():
    """Inicializa Telethon en un hilo separado."""
    global client, loop
    
    def run_telethon():
        global client, loop
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            client = TelegramClient(
                'telethon_session',
                config.API_ID,
                config.API_HASH
            )
            
            # Iniciar el cliente de forma asíncrona
            async def start_client():
                await client.start()
                logger.info("Cliente de Telethon iniciado correctamente")
            
            loop.run_until_complete(start_client())
            
            # Mantener el loop corriendo
            loop.run_forever()
            
        except Exception as e:
            logger.error(f"Error inicializando Telethon: {str(e)}")
    
    # Iniciar en hilo separado
    thread = threading.Thread(target=run_telethon, daemon=True)
    thread.start()
    
    # Esperar un poco para que se inicialice
    time.sleep(3)

# Crear la aplicación Flask
app = Flask(__name__)

# Inicializar base de datos
init_database()

@app.route('/')
def home():
    """Página de inicio con información de la API."""
    return jsonify({
        'servicio': 'API Árbol Genealógico',
        'comando': '/ag?dni=12345678&key=TU_API_KEY',
        'info': '@zGatoO - @WinniePoohOFC - @choco_tete'
    })

@app.route('/ag')
def ag_result():
    """Endpoint para consultar árbol genealógico."""
    # Validar API Key
    api_key = request.args.get('key') or request.headers.get('X-API-Key')
    validation = validate_api_key(api_key)
    
    if not validation['valid']:
        return jsonify({
            'success': False,
            'error': validation['error']
        }), 401
    
    dni = request.args.get('dni')
    
    if not dni:
        return jsonify({
            'success': False,
            'error': 'Parámetro DNI requerido. Use: /ag?dni=12345678&key=TU_API_KEY'
        }), 400
    
    if not dni.isdigit() or len(dni) != 8:
        return jsonify({
            'success': False,
            'error': 'DNI debe ser un número de 8 dígitos'
        }), 400
    
    try:
        result = consult_arbol_sync(dni)
        
        if result['success']:
            return jsonify(result['data'])
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Error en endpoint /ag: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500

@app.route('/health')
def health():
    """Endpoint de salud del servicio."""
    return jsonify({
        'status': 'healthy',
        'service': 'arbol-genealogico',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/register-key', methods=['POST'])
def register_key():
    """Endpoint para registrar API Keys desde el panel de administración."""
    try:
        data = request.get_json()
        
        if not data or 'key' not in data:
            return jsonify({
                'success': False,
                'error': 'Datos de API Key requeridos'
            }), 400
        
        api_key = data['key']
        description = data.get('description', 'API Key desde panel')
        expires_at = data.get('expires_at', (datetime.now() + timedelta(hours=1)).isoformat())
        
        if register_api_key(api_key, description, expires_at):
            return jsonify({
                'success': True,
                'message': 'API Key registrada correctamente'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Error registrando API Key'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500

@app.route('/delete-key', methods=['POST'])
def delete_key():
    """Endpoint para eliminar API Keys desde el panel de administración."""
    try:
        data = request.get_json()
        
        if not data or 'key' not in data:
            return jsonify({
                'success': False,
                'error': 'API Key requerida'
            }), 400
        
        api_key = data['key']
        
        if delete_api_key(api_key):
            return jsonify({
                'success': True,
                'message': 'API Key eliminada correctamente'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Error eliminando API Key'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500

# Inicializar Telethon cuando se importa el módulo (para Gunicorn)
init_telethon_thread()

def main():
    """Función principal."""
    # Iniciar Flask
    port = int(os.getenv('PORT', 8080))
    logger.info(f"Iniciando API en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    main()
