#!/usr/bin/env python3
"""Verifica que cada integración de miCangrejo funciona con las credenciales de backend/.env.

Se ejecuta desde cualquier directorio con el entorno virtual del backend:

    backend/.venv/bin/python backend/scripts/verificar_entorno.py
    backend/.venv/bin/python backend/scripts/verificar_entorno.py --enviar-prueba tu@correo.com
    backend/.venv/bin/python backend/scripts/verificar_entorno.py --crear-bucket

Para cada servicio imprime ✓ (real), ○ (modo de contingencia) o ✗ (error) con una pista
accionable. NUNCA imprime el valor de una clave: solo si está definida y, como mucho,
sus 4 últimos caracteres. Cualquier valor secreto que aparezca en un mensaje de error
se sustituye por «•••» antes de imprimirlo.

Código de salida: 0 si nada está en error (real o contingencia), 1 si algo falló.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import smtplib
import socket
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from email.message import EmailMessage
from os import getenv
from pathlib import Path
from urllib.parse import quote_plus

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"

# El script vive en backend/scripts/; para importar `app` hay que poner backend/ en sys.path.
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ENV_FILE)

# Tiempo máximo para abrir la conexión a Postgres (lo lee libpq/psycopg; no toca el engine de la app).
os.environ.setdefault("PGCONNECT_TIMEOUT", "15")

from app.core.config import Settings, get_settings  # noqa: E402

REAL, CONTINGENCIA, ERROR = "real", "contingencia", "error"
SIMBOLO = {REAL: "✓", CONTINGENCIA: "○", ERROR: "✗"}
HTTP_TIMEOUT_S = 15


# --------------------------------------------------------------------------- utilidades

@dataclass
class Resultado:
    servicio: str
    modo: str
    detalle: str
    pistas: list[str] = field(default_factory=list)
    notas: list[str] = field(default_factory=list)


_SECRETOS: list[str] = []


def registrar_secreto(valor: str | None) -> None:
    """Guarda un valor secreto para borrarlo de cualquier texto antes de imprimirlo."""
    if valor and len(valor) >= 4:
        _SECRETOS.append(valor)
        codificado = quote_plus(valor)
        if codificado != valor:
            _SECRETOS.append(codificado)


def limpiar(texto: str) -> str:
    for secreto in sorted(_SECRETOS, key=len, reverse=True):
        texto = texto.replace(secreto, "•••")
    return texto


def mascara(valor: str | None) -> str:
    """'no definida' | 'definida' | 'definida (…abcd)'. Jamás el valor completo."""
    if not valor:
        return "no definida"
    if len(valor) <= 8:
        return "definida"
    return f"definida (…{valor[-4:]})"


def resumen_excepcion(exc: BaseException, limite: int = 220) -> str:
    return f"{type(exc).__name__}: {str(exc)[:limite]}"


def imprimir(r: Resultado) -> None:
    print(f"  {SIMBOLO[r.modo]} {r.modo} · {limpiar(r.detalle)}")
    for nota in r.notas:
        print(f"    info:  {limpiar(nota)}")
    for pista in r.pistas:
        print(f"    pista: {limpiar(pista)}")


# --------------------------------------------------------------------------- 1. base de datos

def _pistas_postgres(texto_error: str) -> list[str]:
    t = texto_error.lower()
    pistas: list[str] = []
    if "password authentication failed" in t or "authentication failed" in t:
        pistas.append(
            "Contraseña incorrecta en DATABASE_URL. Si tiene caracteres especiales (@ # / % :) codifícala: "
            "python -c \"import urllib.parse; print(urllib.parse.quote_plus('TU-CONTRASEÑA'))\"."
        )
        pistas.append("¿La olvidaste? Supabase → Project Settings → Database → Reset database password.")
    if "tenant or user not found" in t:
        pistas.append(
            "El pooler no reconoce el usuario: debe ser postgres.<ref-del-proyecto> (cópialo de Supabase → "
            "Connect → Transaction pooler). También ocurre si el proyecto está pausado."
        )
    if any(s in t for s in ("could not translate host", "nodename nor servname", "name or service not known",
                            "getaddrinfo", "name resolution")):
        pistas.append(
            "Host no resuelto: revisa el host de DATABASE_URL (aws-0-<región>.pooler.supabase.com) "
            "y tu conexión a internet."
        )
    if any(s in t for s in ("timeout", "timed out", "connection refused", "network is unreachable")):
        pistas.append(
            "Sin respuesta del servidor: el proyecto puede estar PAUSADO en Supabase (el plan gratis se pausa "
            "tras 7 días sin uso → botón Restore project) o el puerto está mal: 6543 = modo transacción "
            "(recomendado para Vercel), 5432 = modo sesión."
        )
    if "ssl" in t:
        pistas.append("Problema de TLS: añade ?sslmode=require al final de DATABASE_URL.")
    if "maxclientsinsessionmode" in t or "max clients" in t:
        pistas.append("Demasiadas conexiones en modo sesión: usa el puerto 6543 (modo transacción).")
    if "prepared statement" in t:
        pistas.append(
            "El pooler en modo transacción no soporta prepared statements; app.database ya usa "
            "prepare_threshold=None, revisa que no se esté creando otro engine."
        )
    if not pistas:
        pistas.append(
            "Formato esperado: postgresql://postgres.<ref>:<contraseña>@aws-0-<región>.pooler.supabase.com:6543/postgres "
            "(Supabase → Connect → Transaction pooler). Comprueba también que el proyecto no esté pausado."
        )
    return pistas


def verificar_base_datos(s: Settings) -> Resultado:
    from sqlalchemy import text
    from sqlalchemy.engine import make_url

    nombre = "Base de datos"

    if not s.uses_postgres:
        ruta = Path(s.database_url.removeprefix("sqlite:///"))
        detalle = f"SQLite local · {ruta}"
        pistas = [
            "Para usar Supabase define DATABASE_URL con la cadena del pooler en MODO TRANSACCIÓN (puerto 6543): "
            "Supabase → Connect → Transaction pooler, y sustituye [YOUR-PASSWORD]."
        ]
        if ruta.exists():
            try:
                from app.database import engine

                with engine.connect() as conn:
                    version = conn.execute(text("select sqlite_version()")).scalar()
                    tablas = conn.execute(
                        text("select count(*) from sqlite_master where type = 'table'")
                    ).scalar()
                detalle += f" (sqlite {version}, {tablas} tablas)"
            except Exception as exc:
                return Resultado(nombre, ERROR, f"SQLite no se pudo abrir: {resumen_excepcion(exc)}",
                                 ["Si el archivo está corrupto bórralo; la API lo vuelve a crear al arrancar."])
        else:
            carpeta = ruta.parent
            while not carpeta.exists():
                carpeta = carpeta.parent
            if not os.access(carpeta, os.W_OK):
                return Resultado(nombre, ERROR, f"no hay permiso de escritura en {carpeta} para crear {ruta.name}",
                                 ["Revisa los permisos de la carpeta backend/data."])
            detalle += " (aún no existe; se crea al arrancar la API)"
        return Resultado(nombre, CONTINGENCIA, detalle, pistas)

    # ---- Postgres (Supabase)
    try:
        url = make_url(s.database_url)
    except Exception as exc:
        return Resultado(nombre, ERROR, f"DATABASE_URL no se pudo interpretar: {resumen_excepcion(exc)}",
                         _pistas_postgres(""))
    registrar_secreto(url.password)
    puerto = url.port or 5432
    destino = f"{url.username}@{url.host}:{puerto}/{url.database}"

    if not url.password or "YOUR-PASSWORD" in url.password.upper():
        return Resultado(nombre, ERROR, f"DATABASE_URL no tiene contraseña ({destino})",
                         ["Sustituye [YOUR-PASSWORD] por la contraseña de la base "
                          "(Supabase → Project Settings → Database → Reset database password si no la tienes)."])

    notas = [f"contraseña {mascara(url.password)} · sslmode={url.query.get('sslmode', 'no indicado')}"]
    if puerto == 5432:
        notas.append("puerto 5432 = modo sesión/directo; en Vercel (serverless) usa el pooler en modo transacción, puerto 6543.")
    if url.host and "pooler.supabase.com" in url.host and url.username and "." not in url.username:
        notas.append("con el pooler de Supabase el usuario debe ser postgres.<ref-del-proyecto>, no solo 'postgres'.")

    try:
        from app.database import engine  # mismo engine que la API: NullPool + prepare_threshold=None

        with engine.connect() as conn:
            version = conn.execute(text("select version()")).scalar()
            tablas = conn.execute(
                text("select count(*) from information_schema.tables where table_schema = 'public'")
            ).scalar()
    except Exception as exc:
        return Resultado(nombre, ERROR, f"no se pudo conectar a {destino} → {resumen_excepcion(exc, 300)}",
                         _pistas_postgres(str(exc)), notas)

    version_corta = " ".join(str(version).split()[:2])
    if not tablas:
        notas.append("0 tablas en public: se crean al arrancar la API (SQLModel.metadata.create_all).")
    return Resultado(nombre, REAL, f"Postgres · {destino} · {version_corta} · {tablas} tablas en public",
                     notas=notas)


# --------------------------------------------------------------------------- 2. Gemini

def _listar_modelos(client, limite: int = 8) -> list[str]:
    nombres: list[str] = []
    try:
        for modelo in client.models.list():
            nombre = (modelo.name or "").removeprefix("models/")
            if "gemini" in nombre:
                nombres.append(nombre)
            if len(nombres) >= limite:
                break
    except Exception:
        pass
    return nombres


def _pistas_gemini(exc, client, s: Settings) -> list[str]:
    codigo = getattr(exc, "code", None) or 0
    mensaje = (getattr(exc, "message", None) or str(exc)).lower()
    if codigo in (401, 403) or (codigo == 400 and "api key" in mensaje):
        return ["GEMINI_API_KEY inválida o sin permiso: genera una nueva en Google AI Studio "
                "(aistudio.google.com → Get API key) y pégala completa, sin comillas ni espacios."]
    if codigo == 404:
        pistas = [f"El modelo '{s.gemini_model}' no existe o no está disponible para esta clave: cambia GEMINI_MODEL."]
        modelos = _listar_modelos(client)
        if modelos:
            pistas.append("Modelos disponibles para tu clave: " + ", ".join(modelos))
        return pistas
    if codigo == 429:
        return ["Cuota agotada (429 RESOURCE_EXHAUSTED): espera un minuto, usa un modelo -flash o revisa la cuota "
                "en AI Studio. Mientras tanto la app clasifica por reglas sin detenerse."]
    if codigo >= 500:
        return ["Error del lado de Google; reintenta en unos minutos."]
    return ["Respuesta inesperada de Gemini: revisa GEMINI_MODEL y GEMINI_API_KEY."]


def verificar_gemini(s: Settings) -> Resultado:
    nombre = "Gemini (IA)"
    if not s.gemini_enabled:
        return Resultado(nombre, CONTINGENCIA,
                         "GEMINI_API_KEY no definida → clasificación por reglas (palabras clave del catálogo)",
                         ["Crea una clave en Google AI Studio (aistudio.google.com → Get API key) y pégala en "
                          "GEMINI_API_KEY; GEMINI_MODEL ya tiene valor por defecto."])

    registrar_secreto(s.gemini_api_key)
    import httpx
    from google import genai
    from google.genai import errors, types

    # Se prueba la MISMA cadena que usa la app: principal (con su presupuesto de razonamiento) y reservas.
    cadena = [s.gemini_model, *[m for m in s.gemini_fallback_models if m and m != s.gemini_model]]
    notas = [f"clave {mascara(s.gemini_api_key)} · GEMINI_MODEL={s.gemini_model} · timeout {s.gemini_timeout_s:g} s",
             "orden de intentos: " + " → ".join(cadena) + " → reglas"]
    client = genai.Client(
        api_key=s.gemini_api_key,
        http_options=types.HttpOptions(timeout=int(s.gemini_timeout_s * 1000)),
    )

    fallos: list[str] = []
    ultimo_error: Exception | None = None
    for indice, modelo in enumerate(cadena):
        presupuesto = s.gemini_thinking_budget if indice == 0 else None
        try:
            response = client.models.generate_content(
                model=modelo,
                contents="Responde únicamente con la palabra OK.",
                config=types.GenerateContentConfig(
                    temperature=0,
                    thinking_config=types.ThinkingConfig(thinking_budget=presupuesto) if presupuesto is not None else None,
                ),
            )
        except errors.APIError as exc:
            codigo = getattr(exc, "code", "?")
            estado = getattr(exc, "status", None) or ""
            fallos.append(f"{modelo} → HTTP {codigo} {estado}".strip())
            ultimo_error = exc
            continue
        except (httpx.TimeoutException, TimeoutError) as exc:
            fallos.append(f"{modelo} → sin respuesta en {s.gemini_timeout_s:g} s")
            ultimo_error = exc
            continue
        except Exception as exc:  # red, credenciales, biblioteca…
            fallos.append(f"{modelo} → {resumen_excepcion(exc)}")
            ultimo_error = exc
            continue

        uso = getattr(response, "usage_metadata", None)
        if uso is None:
            tokens = "sin usage_metadata en la respuesta"
        else:
            tokens = f"tokens: {uso.prompt_token_count or 0} entrada + {uso.candidates_token_count or 0} salida"
            if getattr(uso, "thoughts_token_count", None):
                tokens += f" + {uso.thoughts_token_count} razonamiento"
            tokens += f" = {uso.total_token_count or 0} total"
        version = getattr(response, "model_version", None) or modelo
        respuesta = (response.text or "").strip().replace("\n", " ")[:40] or "(vacía)"
        detalle = f"modelo {version} respondió «{respuesta}» · {tokens}"
        if not fallos:
            return Resultado(nombre, REAL, detalle, notas=notas)
        # La IA sigue clasificando, pero conviene avisar de que el principal no está respondiendo.
        return Resultado(nombre, REAL, f"{detalle} · por reserva, falló {'; '.join(fallos)}",
                         ["El modelo principal no respondió; la app clasifica con la reserva. El nivel gratuito "
                          "da 20 peticiones por día y por modelo: si la demo es larga, añade más modelos en "
                          "GEMINI_FALLBACK_MODELS."], notas)

    pistas = _pistas_gemini(ultimo_error, client, s) if ultimo_error is not None else []
    return Resultado(nombre, ERROR, "ningún modelo respondió: " + "; ".join(fallos), pistas, notas)


# --------------------------------------------------------------------------- 3. SMTP

def verificar_smtp(s: Settings, enviar_a: str | None) -> Resultado:
    nombre = "Correo SMTP"
    if not s.smtp_enabled:
        pistas = ["Gmail: activa la verificación en 2 pasos → myaccount.google.com/apppasswords → crea una "
                  "contraseña de aplicación (16 letras) y ponla en SMTP_PASSWORD; SMTP_USER es tu correo completo."]
        if enviar_a:
            pistas.append(f"--enviar-prueba {enviar_a} ignorado: no hay SMTP configurado.")
        return Resultado(nombre, CONTINGENCIA,
                         "SMTP_USER/SMTP_PASSWORD no definidos → correo simulado (queda registrado en el historial del caso)",
                         pistas)

    registrar_secreto(s.smtp_password)
    es_gmail = "gmail" in s.smtp_host.lower()
    notas = [f"{s.smtp_host}:{s.smtp_port} · SMTP_USER={s.smtp_user} · MAIL_FROM={s.mail_from} · "
             f"contraseña {mascara(s.smtp_password)} · timeout {s.mail_timeout_s:g} s"]
    if s.mail_demo_override_to:
        notas.append(f"MAIL_DEMO_OVERRIDE_TO={s.mail_demo_override_to}: en la app TODO correo se desvía a ese buzón.")
    else:
        notas.append("MAIL_DEMO_OVERRIDE_TO no definido: la app escribiría a los correos reales de las entidades; "
                     "durante el reto conviene definirlo.")
    pistas_previas: list[str] = []
    if s.smtp_port == 465:
        pistas_previas.append("El mailer usa STARTTLS: el puerto 465 (SSL implícito) fallará; usa SMTP_PORT=587.")

    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=s.mail_timeout_s) as smtp:
            smtp.starttls()
            smtp.login(s.smtp_user, s.smtp_password)
            detalle = f"STARTTLS + login correctos en {s.smtp_host}:{s.smtp_port} como {s.smtp_user}"
            if enviar_a:
                msg = EmailMessage()
                msg["Subject"] = "[miCangrejo] Correo de prueba de verificar_entorno"
                msg["From"] = s.mail_from or s.smtp_user
                msg["To"] = enviar_a
                msg.set_content(
                    "Este es un correo de prueba enviado por backend/scripts/verificar_entorno.py.\n"
                    f"Fecha: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
                    f"Servidor: {s.smtp_host}:{s.smtp_port}\n\n"
                    "Si lo recibes, el envío de correo de miCangrejo funciona.\n"
                )
                smtp.send_message(msg)
                detalle += f" · correo de prueba enviado a {enviar_a}"
        return Resultado(nombre, REAL, detalle, pistas_previas, notas)
    except smtplib.SMTPAuthenticationError as exc:
        pistas = ["Usuario o contraseña rechazados (535)."]
        if es_gmail:
            pistas.append("Gmail NO acepta la contraseña normal: activa la verificación en 2 pasos y crea una "
                          "contraseña de aplicación en myaccount.google.com/apppasswords (16 letras, sin espacios).")
        if " " in (s.smtp_password or ""):
            pistas.append("La contraseña tiene espacios: pégala sin ellos.")
        return Resultado(nombre, ERROR, f"login rechazado en {s.smtp_host}:{s.smtp_port}: {resumen_excepcion(exc)}",
                         pistas + pistas_previas, notas)
    except smtplib.SMTPNotSupportedError as exc:
        return Resultado(nombre, ERROR, f"el servidor no soporta STARTTLS: {resumen_excepcion(exc)}",
                         ["Usa el puerto 587 (STARTTLS); 465 y 25 no sirven con este mailer."] + pistas_previas, notas)
    except smtplib.SMTPRecipientsRefused as exc:
        return Resultado(nombre, ERROR, f"login correcto pero el destinatario fue rechazado: {resumen_excepcion(exc)}",
                         [f"Revisa la dirección '{enviar_a}'."], notas)
    except socket.gaierror as exc:
        return Resultado(nombre, ERROR, f"host '{s.smtp_host}' no resuelto: {resumen_excepcion(exc)}",
                         ["Revisa SMTP_HOST (Gmail: smtp.gmail.com) y la conexión a internet."], notas)
    except (TimeoutError, socket.timeout, ConnectionRefusedError, OSError) as exc:
        return Resultado(nombre, ERROR, f"no se pudo conectar a {s.smtp_host}:{s.smtp_port}: {resumen_excepcion(exc)}",
                         ["Revisa SMTP_PORT (587 con STARTTLS) y si la red bloquea el puerto (algunas redes "
                          "universitarias lo hacen: prueba con datos móviles)."] + pistas_previas, notas)
    except Exception as exc:
        return Resultado(nombre, ERROR, f"fallo SMTP: {resumen_excepcion(exc)}",
                         ["Revisa SMTP_HOST, SMTP_PORT, SMTP_USER y SMTP_PASSWORD."] + pistas_previas, notas)


# --------------------------------------------------------------------------- 4. Supabase Storage

def _tipo_clave_supabase(clave: str) -> tuple[str, bool | None]:
    """Describe el tipo de clave sin revelarla. (descripción, ¿sirve como service role?)"""
    if clave.startswith("sb_secret_"):
        return "secret (service role, formato nuevo)", True
    if clave.startswith("sb_publishable_"):
        return "publishable (clave PÚBLICA)", False
    partes = clave.split(".")
    if len(partes) == 3:
        try:
            payload = partes[1] + "=" * (-len(partes[1]) % 4)
            rol = json.loads(base64.urlsafe_b64decode(payload)).get("role", "?")
        except Exception:
            return "JWT no legible", None
        return f"JWT con rol '{rol}'", rol == "service_role"
    return "formato desconocido", None


def _pistas_supabase(exc: BaseException) -> list[str]:
    t = str(exc).lower()
    estado = getattr(exc, "status", None)
    if estado in (401, 403, "401", "403") or any(s in t for s in ("jwt", "signature", "unauthorized", "invalid api key")):
        return ["La clave no es válida para este proyecto: copia la service_role de Supabase → Project Settings → "
                "API Keys (o una clave sb_secret_…). No uses la anon/publishable."]
    if "invalid url" in t:
        return ["SUPABASE_URL debe ser https://<ref>.supabase.co (sin barra final)."]
    if any(s in t for s in ("connect", "getaddrinfo", "name or service", "nodename", "timed out")):
        return ["No se llega al host: revisa SUPABASE_URL o si el proyecto está pausado (Supabase → Restore project)."]
    return ["Revisa SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en Supabase → Project Settings → API Keys."]


def verificar_storage(s: Settings, crear_bucket: bool) -> Resultado:
    nombre = "Supabase Storage"
    if not s.storage_enabled:
        pistas = ["Supabase → Project Settings → API Keys: copia Project URL en SUPABASE_URL y la clave service_role "
                  "(nunca la anon) en SUPABASE_SERVICE_ROLE_KEY. Luego crea el bucket público 'evidencias' "
                  "o ejecuta este script con --crear-bucket."]
        if crear_bucket:
            pistas.append("--crear-bucket ignorado: no hay credenciales de Supabase.")
        return Resultado(nombre, CONTINGENCIA,
                         "SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY no definidos → los reportes se guardan sin foto",
                         pistas)

    clave = s.supabase_service_role_key
    registrar_secreto(clave)
    tipo, sirve = _tipo_clave_supabase(clave)
    notas = [f"SUPABASE_URL={s.supabase_url} · clave {mascara(clave)} · tipo: {tipo} · bucket esperado: {s.supabase_bucket}"]
    if sirve is False:
        return Resultado(nombre, ERROR, f"la clave configurada es {tipo}, no la service_role",
                         ["Con la clave pública el servidor no puede listar buckets ni firmar subidas. Copia la "
                          "service_role (o una sb_secret_…) de Supabase → Project Settings → API Keys."], notas)

    try:
        from supabase import create_client

        client = create_client(s.supabase_url, clave)
        buckets = client.storage.list_buckets()
    except Exception as exc:
        return Resultado(nombre, ERROR, f"no se pudo listar buckets: {resumen_excepcion(exc)}",
                         _pistas_supabase(exc), notas)

    nombres = [b.name for b in buckets]
    notas.append(f"buckets visibles ({len(nombres)}): {', '.join(nombres) or 'ninguno'}")
    bucket = next((b for b in buckets if s.supabase_bucket in (b.name, b.id)), None)

    if bucket is None:
        if crear_bucket:
            try:
                # Firma real del SDK instalado: create_bucket(id, name=None, options=CreateOrUpdateBucketOptions)
                client.storage.create_bucket(s.supabase_bucket, options={"public": True})
                bucket = client.storage.get_bucket(s.supabase_bucket)
                notas.append(f"bucket '{s.supabase_bucket}' creado como público")
            except Exception as exc:
                return Resultado(nombre, ERROR, f"no se pudo crear el bucket '{s.supabase_bucket}': {resumen_excepcion(exc)}",
                                 _pistas_supabase(exc) + ["Créalo a mano: Supabase → Storage → New bucket → "
                                                          f"nombre '{s.supabase_bucket}', marcado como Public."], notas)
        else:
            return Resultado(nombre, ERROR, f"el bucket '{s.supabase_bucket}' no existe",
                             ["Ejecuta de nuevo con --crear-bucket, o créalo en Supabase → Storage → New bucket "
                              f"(nombre '{s.supabase_bucket}', Public).",
                              "Si el bucket SÍ aparece en el panel pero no aquí, la clave no es la service_role."], notas)

    pistas: list[str] = []
    if not bucket.public:
        pistas.append("El bucket es PRIVADO: storage_service.read_url() usa la URL pública y las fotos no se verán. "
                      "Supabase → Storage → bucket → ⋯ → Edit bucket → Public bucket.")

    ruta_prueba = f"verificacion/{uuid.uuid4().hex}.txt"
    try:
        firmada = client.storage.from_(s.supabase_bucket).create_signed_upload_url(ruta_prueba)
        if not (firmada.get("signed_url") and firmada.get("token")):
            raise RuntimeError("la respuesta no trae signed_url/token")
    except Exception as exc:
        return Resultado(nombre, ERROR, f"bucket '{s.supabase_bucket}' encontrado pero no se pudo firmar una subida: "
                                        f"{resumen_excepcion(exc)}", _pistas_supabase(exc) + pistas, notas)

    visibilidad = "público" if bucket.public else "privado"
    detalle = f"bucket '{s.supabase_bucket}' {visibilidad} · URL firmada de subida OK (no se subió nada)"
    if pistas:
        return Resultado(nombre, ERROR, detalle + " · pero el bucket debe ser público", pistas, notas)
    return Resultado(nombre, REAL, detalle, notas=notas)


# --------------------------------------------------------------------------- 5. WhatsApp (Meta)

PISTA_VERIFY_TOKEN = ("Define META_VERIFY_TOKEN (cualquier cadena larga inventada) y usa exactamente la misma en "
                      "Meta → WhatsApp → Configuration → Webhook → Verify token; sin ella Meta no puede verificar el webhook.")


def _pistas_meta(estado_http: int, codigo, subcodigo, mensaje: str, version: str) -> list[str]:
    m = mensaje.lower()
    if codigo == 190:
        if subcodigo == 463 or "expired" in m:
            return ["El token CADUCÓ: el token temporal de API Setup dura 24 h. Genera uno nuevo o, mejor, uno "
                    "permanente: business.facebook.com → Configuración del negocio → Usuarios del sistema → "
                    "Generar token (permisos whatsapp_business_messaging y whatsapp_business_management)."]
        return ["Token inválido (no caducado): cópialo completo desde Meta → WhatsApp → API Setup, sin espacios "
                "ni saltos de línea, y comprueba que pertenece a la misma app que el número."]
    if codigo == 100 or (estado_http == 400 and ("unsupported get request" in m or "does not exist" in m)):
        return ["META_PHONE_NUMBER_ID incorrecto o el token no tiene acceso a ese número: usa el 'Phone number ID' "
                "(no el número de teléfono ni el 'WhatsApp Business Account ID') de Meta → WhatsApp → API Setup."]
    if codigo in (3, 10, 200):
        return ["El token no tiene permisos sobre WhatsApp: al generarlo marca whatsapp_business_messaging y "
                "whatsapp_business_management, y asigna el activo de WhatsApp al usuario del sistema."]
    if codigo in (4, 17, 32, 613):
        return ["Límite de peticiones de Graph API alcanzado; espera unos minutos."]
    if codigo == 2500 or "unknown path" in m:
        return [f"Versión de Graph mal escrita: META_GRAPH_VERSION debe tener el formato v22.0 (actual: {version})."]
    return ["Revisa META_ACCESS_TOKEN y META_PHONE_NUMBER_ID en Meta for Developers → WhatsApp → API Setup."]


def verificar_whatsapp(s: Settings) -> Resultado:
    nombre = "WhatsApp (Meta)"
    version = getenv("META_GRAPH_VERSION") or "v22.0"   # igual que whatsapp_service.GRAPH
    registrar_secreto(s.meta_verify_token)

    if not s.whatsapp_enabled:
        pistas = ["Meta for Developers → tu app → WhatsApp → API Setup: copia el Phone number ID en "
                  "META_PHONE_NUMBER_ID y un token en META_ACCESS_TOKEN (el temporal dura 24 h; para la demo "
                  "genera uno permanente con un usuario del sistema)."]
        if not s.meta_verify_token:
            pistas.append(PISTA_VERIFY_TOKEN)
        return Resultado(nombre, CONTINGENCIA,
                         "META_ACCESS_TOKEN/META_PHONE_NUMBER_ID no definidos → el webhook responde a curl, "
                         "pero no descarga fotos ni contesta al vecino", pistas,
                         [f"META_VERIFY_TOKEN {mascara(s.meta_verify_token)} · META_GRAPH_VERSION={version}"])

    registrar_secreto(s.meta_access_token)
    import httpx

    notas = [f"token {mascara(s.meta_access_token)} · phone_number_id={s.meta_phone_number_id} · "
             f"META_GRAPH_VERSION={version} · META_VERIFY_TOKEN {mascara(s.meta_verify_token)}"]
    try:
        r = httpx.get(
            f"https://graph.facebook.com/{version}/{s.meta_phone_number_id}",
            headers={"Authorization": f"Bearer {s.meta_access_token}"},
            params={"fields": "display_phone_number,verified_name,quality_rating"},
            timeout=HTTP_TIMEOUT_S,
        )
    except httpx.HTTPError as exc:
        return Resultado(nombre, ERROR, f"no se pudo contactar a graph.facebook.com: {resumen_excepcion(exc)}",
                         ["Revisa la conexión a internet."], notas)

    try:
        cuerpo = r.json()
    except ValueError:
        cuerpo = {}

    if r.status_code == 200 and "error" not in cuerpo:
        detalle = (f"número {cuerpo.get('display_phone_number', '?')} · nombre verificado "
                   f"«{cuerpo.get('verified_name', '?')}» · calidad {cuerpo.get('quality_rating', '?')}")
        if not s.meta_verify_token:
            return Resultado(nombre, ERROR, detalle + " · pero META_VERIFY_TOKEN no está definido",
                             [PISTA_VERIFY_TOKEN], notas)
        return Resultado(nombre, REAL, detalle, notas=notas)

    error = cuerpo.get("error", {}) if isinstance(cuerpo, dict) else {}
    codigo, subcodigo = error.get("code"), error.get("error_subcode")
    mensaje = str(error.get("message") or r.text[:160])
    pistas = _pistas_meta(r.status_code, codigo, subcodigo, mensaje, version)
    if not s.meta_verify_token:
        pistas.append(PISTA_VERIFY_TOKEN)
    return Resultado(nombre, ERROR,
                     f"HTTP {r.status_code} · error {codigo}/{subcodigo or '-'}: {mensaje[:160]}", pistas, notas)


# --------------------------------------------------------------------------- principal

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Comprueba las integraciones de miCangrejo con las credenciales de backend/.env "
                    "sin imprimir ninguna clave.")
    parser.add_argument("--enviar-prueba", metavar="CORREO",
                        help="además del login SMTP, envía un correo de prueba real a esa dirección")
    parser.add_argument("--crear-bucket", action="store_true",
                        help="crea SUPABASE_BUCKET como bucket público si no existe")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

    print("miCangrejo · verificación de entorno")
    print(f"python: {sys.executable}")
    if ENV_FILE.exists():
        print(f".env:   {ENV_FILE} (encontrado)")
    else:
        print(f".env:   {ENV_FILE} NO encontrado → todo en modo de contingencia "
              "(cp backend/.env.example backend/.env y pega tus credenciales)")

    s = get_settings()
    comprobaciones = [
        ("Base de datos", lambda: verificar_base_datos(s)),
        ("Gemini (IA)", lambda: verificar_gemini(s)),
        ("Correo SMTP", lambda: verificar_smtp(s, args.enviar_prueba)),
        ("Supabase Storage", lambda: verificar_storage(s, args.crear_bucket)),
        ("WhatsApp (Meta)", lambda: verificar_whatsapp(s)),
    ]

    resultados: list[Resultado] = []
    for i, (titulo, comprobar) in enumerate(comprobaciones, 1):
        print(f"\n[{i}/{len(comprobaciones)}] {titulo}")
        try:
            resultado = comprobar()
        except Exception as exc:  # nunca reventar: un fallo inesperado también es un resultado
            resultado = Resultado(titulo, ERROR, f"fallo inesperado: {resumen_excepcion(exc)}",
                                  ["Copia esta salida al equipo para revisarla."])
        imprimir(resultado)
        resultados.append(resultado)

    print("\nResumen")
    ancho = max(len(r.servicio) for r in resultados)
    for r in resultados:
        print(f"  {r.servicio.ljust(ancho)}  {SIMBOLO[r.modo]} {r.modo}")

    errores = sum(1 for r in resultados if r.modo == ERROR)
    reales = sum(1 for r in resultados if r.modo == REAL)
    contingencia = sum(1 for r in resultados if r.modo == CONTINGENCIA)
    if errores:
        print(f"\n{errores} servicio(s) en error: corrige las pistas de arriba. Código de salida 1.")
        return 1
    print(f"\nSin errores: la API arranca con {reales} integración(es) real(es) y {contingencia} en modo de "
          "contingencia. Código de salida 0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
