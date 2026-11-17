"""Correo a cada entidad (RF-05, ADR-04): Gmail SMTP, síncrono, con timeout.

Sin SMTP configurado entra el modo de contingencia: el correo se "envía" de forma
simulada, queda registrado en el historial y la demo no se detiene.
Si MAIL_DEMO_OVERRIDE_TO está definido, TODO correo va a ese buzón (nunca a una
entidad real durante el reto).
"""

import smtplib
from email.message import EmailMessage

from app.core.config import get_settings
from app.models import Expediente, Participacion, Entidad


def render_email(case: Expediente, participation: Participacion, entity: Entidad, photo_url: str | None,
                 others: list[str]) -> tuple[str, str]:
    subject = f"[miCangrejo] Caso {case.folio} · {case.category or 'Sin categoría'} · urgencia {case.urgency or 'Media'}"
    lines = [
        f"Estimados {entity.name}:",
        "",
        f"La Junta de Desarrollo Local de El Cangrejo remite el caso {case.folio} para su atención.",
        "",
        f"Responsabilidad que les corresponde: {participation.responsibility}",
        f"Categoría: {case.category or 'Sin categoría'} · Urgencia: {case.urgency or 'Media'}",
        f"Ubicación: {case.location_label}"
        + (f" ({case.latitude:.5f}, {case.longitude:.5f})" if case.latitude and case.longitude else ""),
        f"Resumen: {case.summary or case.description}",
        "",
        "Descripción del vecino:",
        case.description,
    ]
    if photo_url:
        lines += ["", f"Evidencia fotográfica: {photo_url}"]
    if case.ticket_311:
        lines += ["", f"Referencia 311: {case.ticket_311}"]
    if others:
        lines += ["", "Otras entidades con participación en este caso: " + ", ".join(others)]
    if case.reports_count > 1:
        lines += ["", f"Este problema fue reportado por {case.reports_count} vecinos."]
    lines += [
        "",
        "Al atender o derivar el caso, respondan a este correo indicando el folio para que la JDL "
        "actualice el expediente. Cada derivación queda registrada con fecha.",
        "",
        "Junta de Desarrollo Local de El Cangrejo · miCangrejo",
    ]
    return subject, "\n".join(lines)


def send_email(to: str, subject: str, body: str, cc: str | None = None) -> tuple[str, str | None]:
    """Devuelve (email_status, error). Estados: enviado | simulado | fallido."""
    settings = get_settings()
    if not settings.smtp_enabled:
        return "simulado", "SMTP no configurado (modo de contingencia)"

    real_to = to
    if settings.mail_demo_override_to:
        subject = f"{subject} [demo → destinatario real: {to}]"
        to = settings.mail_demo_override_to
        cc = None

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.mail_from or settings.smtp_user
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.mail_timeout_s) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        return "enviado", None
    except Exception as exc:
        return "fallido", f"{type(exc).__name__}: {str(exc)[:200]} (destino {real_to})"
