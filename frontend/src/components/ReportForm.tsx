import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { Camera, CheckCircle2, FilePlus2, LoaderCircle, LocateFixed, MapPin, Send } from 'lucide-react'

import { ApiError, createReport, type Report } from '@/services/api'
import { rememberReport } from '@/services/reportService'
import { Button, Field, Marginalia, inputClass, inputStyle, serif, t, textareaClass } from '@/design/tokens'
import { Ficha, Folio } from '@/design/ui'

const MAX_PHOTO_SIZE = 5 * 1024 * 1024
/** Duración del plegado de la carta; debe coincidir con .micangrejo-carta-enviada en index.css. */
const CARTA_MS = 760

function prefiereMenosMovimiento(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

type FormErrors = {
  description?: string
  location?: string
  photo?: string
}

export function ReportForm() {
  const photoInputRef = useRef<HTMLInputElement>(null)
  const [description, setDescription] = useState('')
  const [location, setLocation] = useState('')
  const [coordinates, setCoordinates] = useState<{ latitude: number; longitude: number } | null>(null)
  const [photo, setPhoto] = useState<File | null>(null)
  const [errors, setErrors] = useState<FormErrors>({})
  const [submitError, setSubmitError] = useState('')
  const [isLocating, setIsLocating] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [createdReport, setCreatedReport] = useState<Report | null>(null)
  // 'form' mientras se escribe, 'enviando' mientras la carta se pliega y vuela, 'recibido' con el folio.
  const [phase, setPhase] = useState<'form' | 'enviando' | 'recibido'>('form')

  useEffect(() => {
    if (phase !== 'enviando') return
    const timer = window.setTimeout(() => setPhase('recibido'), CARTA_MS)
    return () => window.clearTimeout(timer)
  }, [phase])

  const handlePhotoChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selectedPhoto = event.target.files?.[0] ?? null

    if (selectedPhoto && !['image/jpeg', 'image/png', 'image/webp'].includes(selectedPhoto.type)) {
      setPhoto(null)
      setErrors((current) => ({ ...current, photo: 'Usa una imagen JPG, PNG o WEBP.' }))
      event.target.value = ''
      return
    }

    if (selectedPhoto && selectedPhoto.size > MAX_PHOTO_SIZE) {
      setPhoto(null)
      setErrors((current) => ({ ...current, photo: 'La imagen debe pesar 5 MB o menos.' }))
      event.target.value = ''
      return
    }

    setPhoto(selectedPhoto)
    setErrors((current) => ({ ...current, photo: undefined }))
  }

  const getCurrentLocation = () => {
    if (!navigator.geolocation) {
      setSubmitError('Tu navegador no permite obtener la ubicación. Escribe una referencia para continuar.')
      return
    }

    setIsLocating(true)
    setSubmitError('')
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setCoordinates({ latitude: coords.latitude, longitude: coords.longitude })
        setLocation((current) => current || 'Ubicación actual en El Cangrejo')
        setErrors((current) => ({ ...current, location: undefined }))
        setIsLocating(false)
      },
      () => {
        setSubmitError('No pudimos obtener tu ubicación. Escribe una referencia para continuar.')
        setIsLocating(false)
      },
      { enableHighAccuracy: true, timeout: 8000 },
    )
  }

  const validate = () => {
    const nextErrors: FormErrors = {}

    if (description.trim().length < 10) {
      nextErrors.description = 'Describe el problema con al menos 10 caracteres.'
    }

    if (!location.trim()) {
      nextErrors.location = 'Indica una referencia o usa tu ubicación actual.'
    }

    setErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setCreatedReport(null)
    setSubmitError('')

    if (!validate()) return

    setIsSubmitting(true)
    try {
      const report = await createReport({
        description: description.trim(),
        location: {
          label: location.trim(),
          latitude: coordinates?.latitude ?? null,
          longitude: coordinates?.longitude ?? null,
        },
      }, photo)

      rememberReport(report)
      setCreatedReport(report)
      setPhase(prefiereMenosMovimiento() ? 'recibido' : 'enviando')
      setDescription('')
      setLocation('')
      setCoordinates(null)
      setPhoto(null)
      if (photoInputRef.current) photoInputRef.current.value = ''
    } catch (caughtError) {
      setSubmitError(caughtError instanceof ApiError ? caughtError.message : 'No pudimos guardar el reporte. Intenta nuevamente.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const enviarOtro = () => {
    setCreatedReport(null)
    setPhase('form')
  }

  if (phase === 'recibido' && createdReport) {
    return (
      <Ficha className="micangrejo-aparece w-full max-w-lg" hero>
        <div className="flex items-start gap-3">
          <CheckCircle2 className="mt-0.5 shrink-0" size={22} style={{ color: t.forest }} />
          <div className="min-w-0">
            <Marginalia className="block">Reporte recibido · {new Date(createdReport.created_at).toLocaleDateString('es-PA', { day: '2-digit', month: 'short' }).toUpperCase()}</Marginalia>
            <h2 className="mt-1 text-[26px] font-medium leading-tight" style={{ fontFamily: serif }}>Tu nota llegó al buzón</h2>
            <p className="mt-2 text-[14px] leading-6">Guarda el folio <Folio value={createdReport.folio} /> para consultar su estado.</p>
            <p className="mt-2 text-[13px] leading-5" style={{ color: t.muted }}>Estado: {createdReport.status} · Categoría: {createdReport.classification.category ?? 'Pendiente de clasificación'} · Urgencia: {createdReport.classification.urgency ?? 'Pendiente'}</p>
            {createdReport.classification.entities.length > 0 && <p className="mt-1 text-[13px] leading-5" style={{ color: t.muted }}>Entidades sugeridas: {createdReport.classification.entities.map((entity) => entity.name).join(', ')}</p>}
            {createdReport.reports_count > 1 && <p className="mt-2 text-[13px] leading-5" style={{ color: t.muted }}>Este problema ya fue reportado por {createdReport.reports_count} vecinos; tu folio quedó registrado para el seguimiento.</p>}
          </div>
        </div>
        <Button className="mt-5 w-full" onClick={enviarOtro} tone="outline">
          <FilePlus2 className="size-4" /> Enviar otro reporte
        </Button>
      </Ficha>
    )
  }

  return (
    <Ficha className={`w-full max-w-lg ${phase === 'enviando' ? 'micangrejo-carta-enviada' : ''}`} hero>
      <Marginalia className="block">Nuevo reporte · sin folio todavía</Marginalia>
      <h2 className="mt-1 text-[26px] font-medium leading-tight" style={{ fontFamily: serif }}>
        Deja tu nota en el buzón
      </h2>
      <p className="mt-1.5 text-[14px] leading-6" style={{ color: t.muted }}>
        Describe el problema de tu comunidad. La clasificación quedará lista para revisión de la JDL.
      </p>

      <form className="mt-6 space-y-5" noValidate onSubmit={handleSubmit}>
        <div>
          <span className="text-[13px] font-semibold">
            Evidencia fotográfica <span className="font-normal" style={{ color: t.muted }}>(opcional)</span>
          </span>
          <label className="mt-1.5 flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center transition hover:bg-black/[.02]" htmlFor="photo" style={{ borderColor: photo ? t.forest : t.rule, background: photo ? t.paper : t.white }}>
            {photo ? <CheckCircle2 className="mb-2 size-8" style={{ color: t.forest }} /> : <Camera className="mb-2 size-8" style={{ color: t.muted }} />}
            <span className="text-[14px] font-medium">{photo ? photo.name : 'Toca para tomar una foto'}</span>
            <span className="mt-1 text-[12px]" style={{ color: t.muted }}>{photo ? `${Math.round(photo.size / 1024)} KB` : 'o sube un archivo JPG, PNG o WEBP (máx. 5 MB)'}</span>
            <input accept="image/png,image/jpeg,image/webp" capture="environment" className="hidden" id="photo" onChange={handlePhotoChange} ref={photoInputRef} type="file" />
          </label>
          {errors.photo && <p className="mt-1.5 text-[13px] font-medium" role="alert" style={{ color: t.coral }}>{errors.photo}</p>}
        </div>

        <div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-[13px] font-semibold">Ubicación</span>
            <button className="inline-flex items-center gap-1.5 text-[13px] font-semibold disabled:opacity-60" disabled={isLocating} onClick={getCurrentLocation} style={{ color: t.forest }} type="button">
              {isLocating ? <LoaderCircle className="size-4 animate-spin" /> : <LocateFixed className="size-4" />}
              {isLocating ? 'Buscando...' : 'Usar ubicación actual'}
            </button>
          </div>
          <div className="relative mt-1.5">
            <MapPin className="absolute left-4 top-1/2 size-4 -translate-y-1/2" style={{ color: t.muted }} />
            <input
              aria-invalid={Boolean(errors.location)}
              className={`${inputClass} pl-11`}
              id="location"
              onChange={(event) => {
                setLocation(event.target.value)
                setErrors((current) => ({ ...current, location: undefined }))
              }}
              placeholder="Ej. Frente al Parque Andrés Bello"
              style={inputStyle}
              value={location}
            />
          </div>
          {coordinates ? (
            <Marginalia className="mt-1.5 block" color={t.forest}>
              Ubicación lista <span className="sm:hidden">✓</span>
              <span className="hidden sm:inline"> · {coordinates.latitude.toFixed(5)}, {coordinates.longitude.toFixed(5)}</span>
            </Marginalia>
          ) : (
            <p className="mt-1.5 text-[12px]" style={{ color: t.muted }}>Puedes escribir una referencia o usar la ubicación actual de tu dispositivo.</p>
          )}
          {errors.location && <p className="mt-1.5 text-[13px] font-medium" role="alert" style={{ color: t.coral }}>{errors.location}</p>}
        </div>

        <div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-[13px] font-semibold">Descripción del problema</span>
            <Marginalia>{description.length}/500</Marginalia>
          </div>
          <textarea
            aria-invalid={Boolean(errors.description)}
            className={`${textareaClass} mt-1.5 min-h-[110px] resize-none`}
            id="description"
            maxLength={500}
            onChange={(event) => {
              setDescription(event.target.value)
              setErrors((current) => ({ ...current, description: undefined }))
            }}
            placeholder="Ej. Hay un bote de agua en la acera que impide el paso..."
            style={inputStyle}
            value={description}
          />
          {errors.description && <p className="mt-1.5 text-[13px] font-medium" role="alert" style={{ color: t.coral }}>{errors.description}</p>}
        </div>

        {submitError && <p className="rounded-lg border px-3 py-2 text-[13px]" role="alert" style={{ borderColor: t.rule, color: t.coral, background: t.white }}>{submitError}</p>}
        <Button className="w-full" disabled={isSubmitting} type="submit">
          {isSubmitting ? <><LoaderCircle className="size-4 animate-spin" /> Guardando...</> : <><Send className="size-4" /> Enviar reporte</>}
        </Button>
      </form>
    </Ficha>
  )
}

// Se conserva por compatibilidad con importaciones antiguas de campos etiquetados.
export { Field }
