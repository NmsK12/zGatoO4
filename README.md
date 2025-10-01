# API Árbol Genealógico - WolfData Dox

Servidor especializado para consultas de árbol genealógico mediante el comando `/ag`.

## 🚀 Características

- **Comando `/ag`**: Consulta el árbol genealógico de una persona
- **Parsing inteligente**: Extrae información de familiares automáticamente
- **Reconexión automática**: Maneja errores de desconexión de Telegram
- **API REST**: Endpoints fáciles de usar

## 📱 Endpoints

### `GET /ag?dni=12345678`
Consulta el árbol genealógico de una persona.

**Parámetros:**
- `dni` (requerido): Número de DNI de 8 dígitos

**Respuesta:**
```json
{
  "success": true,
  "data": {
    "TIPO_CONSULTA": "ARBOL_GENEALOGICO",
    "FAMILIARES": [
      {
        "DNI": "62686980",
        "EDAD": "29",
        "NOMBRES": "AMERICO LUIS",
        "APELLIDOS": "MOSCOSO PACAHUALA",
        "SEXO": "MASCULINO",
        "RELACION": "HIJO",
        "VERIFICACION": "ALTA"
      }
    ]
  },
  "raw_text": "Texto completo de la respuesta..."
}
```

### `GET /health`
Verifica el estado del servicio.

## 🛠️ Instalación

1. Clona el repositorio
2. Instala las dependencias: `pip install -r requirements.txt`
3. Configura las credenciales en `config.py`
4. Ejecuta: `python api_arbol.py`

## 🚀 Despliegue en Railway

1. Conecta el repositorio a Railway
2. Railway detectará automáticamente la configuración
3. El servicio estará disponible en la URL proporcionada

## 📋 Dependencias

- Flask 2.3.3
- Telethon 1.37.0
- Pillow 10.0.1
- Gunicorn 21.2.0

## 🔧 Configuración

Edita `config.py` con tus credenciales de Telegram:

```python
API_ID = tu_api_id
API_HASH = "tu_api_hash"
TARGET_BOT = "@OlimpoDataBot"
PORT = 8080
```

## 📞 Soporte

Para soporte técnico, contacta a @zGatoO
