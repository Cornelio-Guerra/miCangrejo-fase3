import { jsPDF } from "jspdf"

import type { Report } from "@/services/api"

const PAGE_WIDTH = 210
const PAGE_HEIGHT = 297
const MARGIN = 18
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2

export async function downloadReportPdf(report: Report): Promise<void> {
  const pdf = new jsPDF({ unit: "mm", format: "a4" })
  let y = 0

  const addFooter = () => {
    const pages = pdf.getNumberOfPages()
    for (let page = 1; page <= pages; page += 1) {
      pdf.setPage(page)
      pdf.setDrawColor(226, 232, 240)
      pdf.line(MARGIN, PAGE_HEIGHT - 15, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 15)
      pdf.setFontSize(8)
      pdf.setTextColor(100, 116, 139)
      pdf.text("miCangrejo · Expediente comunitario", MARGIN, PAGE_HEIGHT - 9)
      pdf.text(`Página ${page} de ${pages}`, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 9, { align: "right" })
    }
  }

  const newPage = () => {
    pdf.addPage()
    y = MARGIN
  }

  const ensureSpace = (height: number) => {
    if (y + height > PAGE_HEIGHT - 22) newPage()
  }

  const paragraph = (text: string, size = 12, color: [number, number, number] = [51, 65, 85]) => {
    pdf.setFont("helvetica", "normal")
    pdf.setFontSize(size)
    pdf.setTextColor(...color)
    const lines = pdf.splitTextToSize(text, CONTENT_WIDTH)
    ensureSpace(lines.length * (size * 0.62) + 4)
    pdf.text(lines, MARGIN, y)
    y += lines.length * (size * 0.62) + 4
  }

  const section = (title: string) => {
    ensureSpace(15)
    y += 4
    pdf.setFillColor(238, 242, 255)
    pdf.roundedRect(MARGIN, y, CONTENT_WIDTH, 10, 2, 2, "F")
    pdf.setFont("helvetica", "bold")
    pdf.setFontSize(12)
    pdf.setTextColor(67, 56, 202)
    pdf.text(title.toUpperCase(), MARGIN + 4, y + 6.7)
    y += 15
  }

  const labelValue = (label: string, value: string) => {
    ensureSpace(11)
    pdf.setFont("helvetica", "bold")
    pdf.setFontSize(10.5)
    pdf.setTextColor(71, 85, 105)
    pdf.text(`${label}:`, MARGIN, y)
    pdf.setFont("helvetica", "normal")
    pdf.setTextColor(15, 23, 42)
    const offset = pdf.getTextWidth(`${label}: `)
    const lines = pdf.splitTextToSize(value, CONTENT_WIDTH - offset)
    pdf.text(lines, MARGIN + offset, y)
    y += Math.max(7, lines.length * 5.5) + 2
  }

  pdf.setFillColor(15, 23, 42)
  pdf.rect(0, 0, PAGE_WIDTH, 45, "F")
  pdf.setFont("helvetica", "bold")
  pdf.setFontSize(22)
  pdf.setTextColor(255, 255, 255)
  pdf.text("miCangrejo", MARGIN, 20)
  pdf.setFontSize(11)
  pdf.setTextColor(167, 243, 208)
  pdf.text("EXPEDIENTE COMUNITARIO", MARGIN, 28)
  pdf.setFontSize(10)
  pdf.setTextColor(226, 232, 240)
  pdf.text(`Folio ${report.folio}`, MARGIN, 36)
  y = 55

  section("Resumen del reporte")
  labelValue("Estado", report.status)
  labelValue("Canal", report.source === "whatsapp" ? "WhatsApp" : "Plataforma web")
  labelValue("Registrado", formatDate(report.created_at))
  labelValue("Última actualización", formatDate(report.updated_at))
  labelValue("Descripción", report.description)
  if (report.reports_count > 1) labelValue("Reportes agrupados", String(report.reports_count))
  if (report.merged_into) labelValue("Expediente principal", report.merged_into)

  section("Ubicación")
  labelValue("Referencia", report.location.label)
  if (report.location.latitude !== null && report.location.longitude !== null) {
    labelValue("Coordenadas", `${report.location.latitude.toFixed(6)}, ${report.location.longitude.toFixed(6)}`)
  }

  section("Clasificación")
  labelValue("Categoría", report.classification.category ?? "Pendiente de clasificación")
  labelValue("Urgencia", report.classification.urgency ?? "Pendiente")
  labelValue("Resumen", report.classification.summary ?? "Sin resumen disponible")
  labelValue("Estado de clasificación", report.classification.status)
  if (report.ticket_311) labelValue("Ticket 311", report.ticket_311)

  section("Entidades responsables")
  if (report.current_entities.length === 0) {
    paragraph("Aún no se ha asignado una entidad responsable.")
  } else {
    report.current_entities.forEach((item) => {
      labelValue(item.entity.name, `${item.status}${item.since ? ` · desde ${formatDate(item.since)}` : ""}`)
    })
  }

  if (report.photo_url) {
    section("Evidencia fotográfica")
    try {
      const image = await loadImage(report.photo_url)
      const maxWidth = CONTENT_WIDTH
      const maxHeight = 88
      const ratio = Math.min(maxWidth / image.width, maxHeight / image.height)
      const width = image.width * ratio
      const height = image.height * ratio
      ensureSpace(height + 6)
      pdf.addImage(image.element, "JPEG", MARGIN, y, width, height)
      y += height + 4
    } catch {
      paragraph("La evidencia está disponible en la plataforma, pero no pudo incorporarse a este PDF.", 9)
    }
  }

  section("Historial del expediente")
  if (report.history.length === 0) {
    paragraph("No hay movimientos registrados todavía.")
  } else {
    report.history.forEach((entry) => {
      ensureSpace(18)
      pdf.setFillColor(99, 102, 241)
      pdf.circle(MARGIN + 1.5, y - 1.3, 1.5, "F")
      pdf.setFont("helvetica", "bold")
      pdf.setFontSize(10.5)
      pdf.setTextColor(30, 41, 59)
      const event = `${entry.event.replaceAll("_", " ")}${entry.entity ? ` · ${entry.entity}` : ""}`
      pdf.text(event, MARGIN + 6, y)
      y += 6
      paragraph(`${formatDate(entry.created_at)}${entry.previous && entry.new ? ` · ${entry.previous} → ${entry.new}` : ""}`, 8, [100, 116, 139])
      if (entry.note) paragraph(redactHistoryNote(entry.note), 10.5)
    })
  }

  addFooter()
  pdf.save(`miCangrejo-${report.folio}.pdf`)
}

type LoadedImage = { element: HTMLImageElement; width: number; height: number }

async function loadImage(url: string): Promise<LoadedImage> {
  const response = await fetch(url)
  if (!response.ok) throw new Error("No se pudo descargar la evidencia")
  const objectUrl = URL.createObjectURL(await response.blob())
  try {
    const element = await new Promise<HTMLImageElement>((resolve, reject) => {
      const image = new Image()
      image.onload = () => resolve(image)
      image.onerror = () => reject(new Error("No se pudo leer la evidencia"))
      image.src = objectUrl
    })
    return { element, width: element.naturalWidth, height: element.naturalHeight }
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("es-PA", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))
}

function redactHistoryNote(note: string): string {
  if (/SMTPAuthenticationError|smtp|Please log in|authentication/i.test(note)) {
    return "No fue posible completar la entrega por correo. La entidad puede reenviar el expediente cuando la configuracion de correo este disponible."
  }
  if (/Gemini|UNAVAILABLE|503|model.*unavailable/i.test(note)) {
    return "La clasificacion automatica no estuvo disponible en ese momento; el reporte conservo una clasificacion de respaldo."
  }
  return note.length > 400 ? `${note.slice(0, 397)}...` : note
}
