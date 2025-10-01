#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para crear sesión de Telegram para el servidor de Árbol Genealógico
"""

from telethon import TelegramClient
import config

def create_session():
    """Crea una nueva sesión de Telegram."""
    print("Creando sesion de Telegram...")
    print(f"API ID: {config.API_ID}")
    print(f"API Hash: {config.API_HASH}")
    print(f"Target Bot: {config.TARGET_BOT}")
    
    # Crear cliente
    client = TelegramClient('telethon_session', config.API_ID, config.API_HASH)
    
    # Iniciar y autenticar
    with client:
        print("Sesion creada exitosamente!")
        print(f"Archivo: telethon_session.session")
        print(f"Usuario: {client.get_me().first_name}")
        print(f"Telefono: {client.get_me().phone}")
        print("Sesion lista para usar!")

if __name__ == '__main__':
    create_session()
