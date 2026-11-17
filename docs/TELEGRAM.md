# Telegram en miCangrejo

El backend expone `POST /api/v1/webhooks/telegram`. Telegram debe enviar el
encabezado `X-Telegram-Bot-Api-Secret-Token` con el mismo valor de
`TELEGRAM_WEBHOOK_SECRET`.

## Variables

En `backend/.env` configura:

```env
TELEGRAM_BOT_TOKEN=token_de_BotFather
TELEGRAM_WEBHOOK_SECRET=una_cadena_aleatoria
TELEGRAM_WEBHOOK_URL=https://tu-dominio.com/api/v1/webhooks/telegram
GEMINI_API_KEY=tu_clave_de_google_ai_studio
```

La URL debe ser pública y HTTPS. Desde la carpeta `backend`, registra el
webhook con:

```bash
python scripts/registrar_telegram_webhook.py
```

El bot soporta `/start`, `/help`, `/reporte`, `/estado`, texto libre y mensajes
de ubicación. Al iniciar un reporte solicita, en orden, la descripción, la
ubicación y una foto opcional. Escribe `omitir` para continuar sin foto. Cada
reporte se guarda con `source = "telegram"` y responde con su folio
`MC-AAAA-NNNN`.

Con `GEMINI_API_KEY`, miCangrejo clasifica cada reporte, estima la urgencia y
genera un resumen. Si Gemini no está disponible, el backend usa las reglas de
respaldo y lo indica en la respuesta del bot. En Vercel, configura esta variable
en las variables de entorno del servicio `backend`; no se sube `backend/.env`.

Para comprobar el registro del webhook puedes consultar `getWebhookInfo` en el
Bot API de Telegram. Nunca publiques `TELEGRAM_BOT_TOKEN` ni el secreto.
