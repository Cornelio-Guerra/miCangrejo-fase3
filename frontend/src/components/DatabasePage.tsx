import { useCallback, useEffect, useState } from 'react'
import { Database, HardDrive, RefreshCw, ShieldCheck } from 'lucide-react'

import { ApiError, getAdminCategories, getAdminEntities, getAdminStats, getRestaurants, getWasteSites, type EntityCatalogItem } from '@/services/api'
import { Button, Marginalia, Tag, serif, t } from '@/design/tokens'
import { ErrorState, Ficha, FichaHeader, LoadingState, PageIntro } from '@/design/ui'

// Base de datos real del prototipo: Supabase (Postgres para el expediente, Storage para las fotos).
// La página muestra lo que el backend expone de esas tablas y catálogos; nunca la clave de servicio.

type Snapshot = {
  totalCases: number
  entities: EntityCatalogItem[]
  categories: string[]
  restaurants: number
  restaurantsSource: string
  wasteSites: number
  wasteSource: string
}

const tables: Array<{ name: string; description: string; key?: keyof Pick<Snapshot, 'totalCases'> }> = [
  { name: 'cases', description: 'Expediente: folio, descripción, ubicación, foto, clasificación y estado.', key: 'totalCases' },
  { name: 'case_entities', description: 'Participación de cada entidad en un caso, con fechas y estado propio.' },
  { name: 'status_history', description: 'Historial de cambios: quién, cuándo y de qué estado a cuál.' },
  { name: 'entities', description: 'Catálogo de entidades competentes con su correo de notificación.' },
  { name: 'routing_rules', description: 'Reglas de enrutamiento: categoría → entidades responsables.' },
]

export function DatabasePage() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const load = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const [stats, entities, categories, restaurants, waste] = await Promise.all([getAdminStats(), getAdminEntities(), getAdminCategories(), getRestaurants(), getWasteSites()])
      setSnapshot({
        totalCases: stats.total_cases,
        entities,
        categories,
        restaurants: restaurants.restaurants.length,
        restaurantsSource: restaurants.source,
        wasteSites: waste.sites.length,
        wasteSource: waste.source,
      })
    } catch (caughtError) {
      setError(caughtError instanceof ApiError ? caughtError.message : 'No fue posible consultar la base de datos.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- La página se hidrata con los catálogos remotos al entrar.
    void load()
  }, [load])

  return (
    <section className="space-y-6">
      <PageIntro action={<Button onClick={() => void load()} size="sm" tone="outline"><RefreshCw size={15} /> Actualizar</Button>} description="El expediente vive en Supabase: Postgres para los casos y Storage para las fotos. Esta vista muestra lo que el backend expone de esas tablas." marginalia="Administrador JDL · Supabase" title="Base de datos" />

      <div className="grid gap-4 lg:grid-cols-[.8fr_1.2fr]">
        <div className="grid content-start gap-4">
          <Ficha>
            <span className="grid size-10 place-items-center rounded-lg" style={{ background: t.paper2, color: t.forest }}>
              <Database size={20} />
            </span>
            <h2 className="mt-4 text-[22px] font-medium leading-tight" style={{ fontFamily: serif }}>
              Postgres en Supabase
            </h2>
            <p className="mt-2 text-[14px] leading-6" style={{ color: t.muted }}>
              El backend se conecta por el pooler en modo transacción. Sin la cadena de conexión, usa SQLite local como contingencia.
            </p>
            <Marginalia className="mt-4 block" color={t.forest}>
              {tables.length} tablas · pooler 6543
            </Marginalia>
          </Ficha>
          <Ficha>
            <span className="grid size-10 place-items-center rounded-lg" style={{ background: t.paper2, color: t.forest }}>
              <HardDrive size={20} />
            </span>
            <h2 className="mt-4 text-[22px] font-medium leading-tight" style={{ fontFamily: serif }}>
              Storage para las fotos
            </h2>
            <p className="mt-2 text-[14px] leading-6" style={{ color: t.muted }}>
              Las evidencias se suben desde el navegador con una URL firmada que emite el backend. El bucket se llama <span style={{ fontFamily: 'ui-monospace, monospace' }}>evidencias</span>.
            </p>
            <p className="mt-4 flex items-center gap-2 text-[13px]" style={{ color: t.forest }}>
              <ShieldCheck size={15} /> La clave de servicio nunca sale del servidor.
            </p>
          </Ficha>
        </div>

        <div className="grid content-start gap-4">
          <Ficha className="overflow-hidden" padded={false}>
            <FichaHeader className="border-b px-5 py-4" description="Tablas del expediente y cuántos registros expone hoy el backend." title="Tablas" />
            {isLoading ? (
              <LoadingState label="Consultando Supabase a través del backend…" />
            ) : error ? (
              <div className="p-5"><ErrorState error={error} onRetry={load} /></div>
            ) : (
              <div className="divide-y" style={{ borderColor: t.rule }}>
                {tables.map((table, index) => (
                  <div className="flex items-start gap-3 px-5 py-3.5" key={table.name} style={{ borderColor: t.rule }}>
                    <Marginalia className="mt-1 w-5 shrink-0">{String(index + 1).padStart(2, '0')}</Marginalia>
                    <div className="min-w-0 flex-1">
                      <p className="text-[14px] font-semibold" style={{ fontFamily: 'ui-monospace, monospace' }}>{table.name}</p>
                      <p className="mt-0.5 text-[13px]" style={{ color: t.muted }}>{table.description}</p>
                    </div>
                    <Tag tone={table.key ? 'forest' : 'muted'}>
                      {table.key && snapshot ? `${snapshot[table.key]} registros` : 'Sincronizada'}
                    </Tag>
                  </div>
                ))}
              </div>
            )}
          </Ficha>

          {snapshot && (
            <>
              <Ficha className="overflow-hidden" padded={false}>
                <FichaHeader aside={<Marginalia>{snapshot.entities.length} activas</Marginalia>} className="border-b px-5 py-4" description="Catálogo de entidades competentes y su correo de notificación." title="Entidades" />
                <div className="divide-y" style={{ borderColor: t.rule }}>
                  {snapshot.entities.map((entity) => (
                    <div className="flex flex-wrap items-center justify-between gap-2 px-5 py-3" key={entity.code} style={{ borderColor: t.rule }}>
                      <div className="min-w-0">
                        <p className="text-[14px] font-medium">{entity.name}</p>
                        <Marginalia className="block">{entity.code}</Marginalia>
                      </div>
                      <span className="text-[13px]" style={{ color: t.muted, fontFamily: 'ui-monospace, monospace' }}>{entity.email}</span>
                    </div>
                  ))}
                </div>
              </Ficha>

              <div className="grid gap-4 sm:grid-cols-3">
                <Ficha>
                  <Marginalia className="block">Categorías</Marginalia>
                  <p className="mt-2 text-[36px] font-medium leading-none tabular-nums" style={{ fontFamily: serif }}>{snapshot.categories.length}</p>
                  <p className="mt-2 text-[12px]" style={{ color: t.muted }}>{snapshot.categories.join(' · ')}</p>
                </Ficha>
                <Ficha>
                  <Marginalia className="block">Restaurantes</Marginalia>
                  <p className="mt-2 text-[36px] font-medium leading-none tabular-nums" style={{ fontFamily: serif }}>{snapshot.restaurants}</p>
                  <p className="mt-2 text-[12px]" style={{ color: t.muted }}>{snapshot.restaurantsSource}</p>
                </Ficha>
                <Ficha>
                  <Marginalia className="block">Puntos de residuos</Marginalia>
                  <p className="mt-2 text-[36px] font-medium leading-none tabular-nums" style={{ fontFamily: serif }}>{snapshot.wasteSites}</p>
                  <p className="mt-2 text-[12px]" style={{ color: t.muted }}>{snapshot.wasteSource}</p>
                </Ficha>
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  )
}
