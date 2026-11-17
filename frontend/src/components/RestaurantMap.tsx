import { useEffect, useMemo, useState } from "react"
import { divIcon, type LatLngBoundsExpression } from "leaflet"
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet"
import { AlertCircle, ExternalLink, LoaderCircle, RefreshCw, Star } from "lucide-react"
import "leaflet/dist/leaflet.css"

import { ApiError, getRestaurants, type Restaurant } from "@/services/api"

const EL_CANGREJO_CENTER: [number, number] = [8.9867, -79.5277]

type RestaurantMapProps = {
  compact?: boolean
}

export function RestaurantMap({ compact = false }: RestaurantMapProps) {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([])
  const [source, setSource] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    async function loadRestaurants() {
      setIsLoading(true)
      setError(null)

      try {
        const result = await getRestaurants(controller.signal)
        setRestaurants(result.restaurants)
        setSource(result.source)
      } catch (caughtError) {
        if (caughtError instanceof DOMException && caughtError.name === "AbortError") return
        setError(caughtError instanceof ApiError ? caughtError.message : "No se pudo conectar con la API.")
      } finally {
        if (!controller.signal.aborted) setIsLoading(false)
      }
    }

    void loadRestaurants()
    return () => controller.abort()
  }, [reloadKey])

  // isolate z-0: los paneles de Leaflet (z-index 400-1000) se quedan dentro de este contexto de
  // apilamiento y no compiten con la cabecera ni con el menú lateral de la aplicación.
  return (
    <div className={`relative isolate z-0 overflow-hidden bg-[#ece5d4] ${compact ? "h-[430px] min-h-[430px]" : "h-[calc(100svh-15rem)] min-h-[520px] lg:min-h-[620px]"}`}>
      <MapContainer center={EL_CANGREJO_CENTER} zoom={16} scrollWheelZoom className="h-full w-full" aria-label="Mapa de restaurantes de El Cangrejo">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitMapToRestaurants restaurants={restaurants} />
        {restaurants.map((restaurant) => <RestaurantMarker key={restaurant.id} restaurant={restaurant} />)}
      </MapContainer>

      <div className="absolute bottom-4 left-4 z-[1000] max-w-[calc(100%-2rem)] rounded-lg border border-[#d6ccb6] bg-[#fffdf8]/95 px-3 py-2 text-xs text-[#1e2d26] shadow-md">
        {isLoading && <span className="flex items-center gap-2"><LoaderCircle className="size-4 animate-spin text-[#2f5d50]" /> Cargando restaurantes desde la API…</span>}
        {!isLoading && !error && <span>{restaurants.length} locales · {source}</span>}
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

function RestaurantMarker({ restaurant }: { restaurant: Restaurant }) {
  const icon = useMemo(() => createRestaurantIcon(restaurant), [restaurant])

  return (
    <Marker position={[restaurant.latitude, restaurant.longitude]} icon={icon}>
      <Popup>
        <article className="min-w-56 max-w-64">
          <div className="flex items-start gap-3">
            <RestaurantIdentity restaurant={restaurant} />
            <div>
              <p className="m-0 font-semibold leading-5 text-[#1e2d26]">{restaurant.name}</p>
              {restaurant.category && <p className="mb-0 mt-1 text-xs font-medium text-[#2f5d50]">{restaurant.category}</p>}
            </div>
          </div>
          {restaurant.description && <p className="mb-0 mt-3 text-xs leading-5 text-[#6b7a71]">{restaurant.description}</p>}
          {(restaurant.rating !== null || restaurant.price_range) && (
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-[#6b7a71]">
              {restaurant.rating !== null && <span className="inline-flex items-center gap-1 rounded-md border border-[#d6ccb6] px-2 py-1 font-medium text-[#1e2d26]"><Star className="size-3 fill-current" /> {restaurant.rating.toFixed(1)}{restaurant.review_count !== null && ` · ${restaurant.review_count} reseñas`}</span>}
              {restaurant.price_range && <span className="rounded-md border border-[#d6ccb6] px-2 py-1 font-medium text-[#1e2d26]">{restaurant.price_range}</span>}
            </div>
          )}
          <a className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-[#2f5d50] hover:text-[#24493f]" href={restaurant.maps_url} rel="noreferrer" target="_blank">
            Ver en Google Maps <ExternalLink className="size-3.5" />
          </a>
        </article>
      </Popup>
    </Marker>
  )
}

function RestaurantIdentity({ restaurant }: { restaurant: Restaurant }) {
  const [imageAvailable, setImageAvailable] = useState(Boolean(restaurant.image_url))
  const logoUrl = getRestaurantLogoSource(restaurant)

  return (
    <span aria-label={`Identificador de ${restaurant.name}`} className="relative grid size-11 shrink-0 place-items-center overflow-hidden rounded-lg border border-[#d6ccb6] bg-[#ece5d4] text-xs font-extrabold tracking-tight text-[#2f5d50]">
      {getInitials(restaurant.name)}
      {imageAvailable && logoUrl && <img alt={`Logo de ${restaurant.name}`} className="absolute inset-0 size-full bg-white p-0.5 object-contain" onError={() => setImageAvailable(false)} src={logoUrl} />}
    </span>
  )
}

function createRestaurantIcon(restaurant: Restaurant) {
  const initials = `<span style="display:grid;position:absolute;inset:0;place-items:center;font:800 11px/1 system-ui;color:#2f5d50;letter-spacing:-.04em">${escapeHtml(getInitials(restaurant.name))}</span>`
  const imageUrl = getRestaurantLogoSource(restaurant)
  const image = imageUrl
    ? `<img alt="" src="${escapeHtml(imageUrl)}" onerror="this.remove()" style="position:relative;width:100%;height:100%;background:#fff;padding:2px;object-fit:contain" />`
    : ""

  return divIcon({
    className: "micangrejo-restaurant-marker",
    html: `<span aria-label="${escapeHtml(restaurant.name)}" style="position:relative;display:grid;place-items:center;overflow:hidden;width:40px;height:40px;border:3px solid #fffdf8;border-radius:50%;background:#ece5d4;box-shadow:0 3px 10px rgba(30,45,38,.35)">${initials}${image}</span>`,
    iconAnchor: [20, 20],
    iconSize: [40, 40],
  })
}

function getRestaurantLogoSource(restaurant: Restaurant) {
  return restaurant.image_url
}

function FitMapToRestaurants({ restaurants }: { restaurants: Restaurant[] }) {
  const map = useMap()

  useEffect(() => {
    if (restaurants.length === 0) return
    const bounds: LatLngBoundsExpression = restaurants.map((restaurant) => [restaurant.latitude, restaurant.longitude])
    map.fitBounds(bounds, { padding: [32, 32], maxZoom: 17 })
  }, [map, restaurants])

  return null
}

function getInitials(name: string) {
  const words = name.replace(/[^\p{L}\p{N}\s]/gu, " ").trim().split(/\s+/)
  return words.slice(0, 2).map((word) => word[0]).join("").toUpperCase() || "MC"
}

function escapeHtml(value: string) {
  return value.replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character] ?? character)
}
