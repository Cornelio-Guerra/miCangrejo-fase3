import { useEffect, useState } from "react"
import { divIcon, type LatLngBoundsExpression } from "leaflet"
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet"
import { AlertCircle, LoaderCircle, RefreshCw } from "lucide-react"
import "leaflet/dist/leaflet.css"

import { ApiError, getWasteSiteImageUrl, getWasteSites, type WasteSite } from "@/services/api"

const EL_CANGREJO_CENTER: [number, number] = [8.990082, -79.527106]
const wasteMarkerIcon = divIcon({
  className: "micangrejo-waste-marker",
  html: `<span style="display:grid;place-items:center;width:38px;height:38px;border:2px solid #fffdf8;border-radius:10px;background:#d9432b;box-shadow:0 3px 10px rgba(30,45,38,.35)"><svg aria-hidden="true" fill="none" height="22" stroke="#ffffff" stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" viewBox="0 0 24 24" width="22" xmlns="http://www.w3.org/2000/svg"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v5"/><path d="M14 11v5"/></svg></span>`,
  iconAnchor: [19, 19],
  iconSize: [38, 38],
})

export function WasteMap() {
  const [sites, setSites] = useState<WasteSite[]>([])
  const [source, setSource] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    async function loadSites() {
      setIsLoading(true)
      setError(null)

      try {
        const result = await getWasteSites(controller.signal)
        setSites(result.sites)
        setSource(result.source)
      } catch (caughtError) {
        if (caughtError instanceof DOMException && caughtError.name === "AbortError") return
        setError(caughtError instanceof ApiError ? caughtError.message : "No se pudo conectar con la API.")
      } finally {
        if (!controller.signal.aborted) setIsLoading(false)
      }
    }

    void loadSites()
    return () => controller.abort()
  }, [reloadKey])

  // isolate z-0: los paneles de Leaflet (z-index 400-1000) se quedan dentro de este contexto de
  // apilamiento y no compiten con la cabecera ni con el menú lateral de la aplicación.
  return (
    <div className="relative isolate z-0 h-[calc(100svh-15rem)] min-h-[520px] overflow-hidden bg-[#ece5d4] lg:min-h-[620px]">
      <MapContainer center={EL_CANGREJO_CENTER} zoom={16} scrollWheelZoom className="h-full w-full" aria-label="Mapa de puntos de residuos y tinacos en El Cangrejo">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitMapToSites sites={sites} />
        {sites.map((site) => (
          <Marker
            position={[site.latitude, site.longitude]}
            icon={wasteMarkerIcon}
            key={site.id}
          >
            <Popup>
              <article className="min-w-52">
                {site.image_url && <img alt={`Registro de ${site.name}`} className="mb-2 h-32 w-full rounded-md object-cover" onError={(event) => { event.currentTarget.hidden = true }} src={getWasteSiteImageUrl(site.id)} />}
                <p className="m-0 font-semibold text-[#1e2d26]">{site.name}</p>
                {site.description && <p className="mb-0 mt-1 text-xs text-[#6b7a71]">Referencia: {site.description}</p>}
                <p className="mb-0 mt-1 text-xs text-[#6b7a71]">Registro comunitario: {site.kind}</p>
              </article>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      <div className="absolute bottom-4 left-4 z-[1000] max-w-[calc(100%-2rem)] rounded-lg border border-[#d6ccb6] bg-[#fffdf8]/95 px-3 py-2 text-xs text-[#1e2d26] shadow-md">
        {isLoading && <span className="flex items-center gap-2"><LoaderCircle className="size-4 animate-spin text-[#2f5d50]" /> Cargando puntos desde la API…</span>}
        {!isLoading && !error && <span>{sites.length} puntos · {source}</span>}
        {!isLoading && error && <span className="flex items-center gap-2"><AlertCircle className="size-4 text-[#d9432b]" /> {error}</span>}
      </div>

      {!isLoading && error && (
        <button className="absolute right-4 top-4 z-[1000] inline-flex items-center gap-2 rounded-lg border border-[#d6ccb6] bg-[#fffdf8] px-3 py-2 text-sm font-semibold text-[#2f5d50] shadow-md hover:bg-[#f5f0e6]" onClick={() => setReloadKey((current) => current + 1)} type="button">
          <RefreshCw className="size-4" /> Reintentar
        </button>
      )}
    </div>
  )
}

function FitMapToSites({ sites }: { sites: WasteSite[] }) {
  const map = useMap()

  useEffect(() => {
    if (sites.length === 0) return
    const bounds: LatLngBoundsExpression = sites.map((site) => [site.latitude, site.longitude])
    map.fitBounds(bounds, { padding: [32, 32], maxZoom: 17 })
  }, [map, sites])

  return null
}
