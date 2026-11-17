"use client"
import { useState, useEffect } from "react";
import {
  Home,
  FileText,
  MapPin,
  Tag,
  BarChart3,
  Users,
  ShieldCheck,
  ChevronDown,
  ChevronsRight,
  Moon,
  Sun,
  TrendingUp,
  AlertTriangle,
  Bell,
  Settings,
  HelpCircle,
  User,
  CheckCircle2
} from "lucide-react";

export const Example = () => {
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDark]);

  return (
    <div className={`flex min-h-screen w-full ${isDark ? 'dark' : ''}`}>
      <div className="flex w-full bg-stone-50 dark:bg-stone-950 text-stone-900 dark:text-stone-100 font-sans transition-colors duration-300">
        <Sidebar />
        <ExampleContent isDark={isDark} setIsDark={setIsDark} />
      </div>
    </div>
  );
};

const Sidebar = () => {
  const [open, setOpen] = useState(true);
  const [selected, setSelected] = useState("Inicio");

  return (
    <nav
      className={`sticky top-0 h-screen shrink-0 border-r transition-all duration-300 ease-in-out ${
        open ? 'w-64' : 'w-20'
      } border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 p-3 shadow-sm`}
    >
      <TitleSection open={open} />

      <div className="space-y-1.5 mb-8">
        <Option Icon={Home} title="Inicio" selected={selected} setSelected={setSelected} open={open} />
        <Option Icon={FileText} title="Reportes" selected={selected} setSelected={setSelected} open={open} notifs={5} />
        <Option Icon={MapPin} title="Mapa Vecinal" selected={selected} setSelected={setSelected} open={open} />
        <Option Icon={AlertTriangle} title="Alertas" selected={selected} setSelected={setSelected} open={open} />
        <Option Icon={Tag} title="Categorías" selected={selected} setSelected={setSelected} open={open} />
        <Option Icon={BarChart3} title="Estadísticas" selected={selected} setSelected={setSelected} open={open} />
        <Option Icon={ShieldCheck} title="Autoridades" selected={selected} setSelected={setSelected} open={open} notifs={2} />
      </div>

      {open && (
        <div className="border-t border-stone-200 dark:border-stone-800 pt-4 space-y-1.5">
          <div className="px-3 py-2 text-xs font-semibold text-stone-500 dark:text-stone-400 uppercase tracking-wider">
            Cuenta
          </div>
          <Option Icon={Settings} title="Configuración" selected={selected} setSelected={setSelected} open={open} />
          <Option Icon={HelpCircle} title="Soporte" selected={selected} setSelected={setSelected} open={open} />
        </div>
      )}

      <ToggleClose open={open} setOpen={setOpen} />
    </nav>
  );
};

const Option = ({ Icon, title, selected, setSelected, open, notifs }: { Icon: any, title: string, selected: string, setSelected: any, open: boolean, notifs?: number }) => {
  const isSelected = selected === title;

  return (
    <button
      onClick={() => setSelected(title)}
      className={`relative flex h-11 w-full items-center rounded-xl transition-all duration-200 ${
        isSelected
          ? "bg-emerald-50 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-300 shadow-sm border-l-4 border-emerald-600"
          : "text-stone-600 dark:text-stone-400 hover:bg-stone-100 dark:hover:bg-stone-800/50 hover:text-stone-900 dark:hover:text-stone-200"
      }`}
    >
      <div className={`grid h-full w-14 place-content-center ${isSelected ? '-ml-1' : ''}`}>
        <Icon className="h-[1.15rem] w-[1.15rem]" />
      </div>

      {open && (
        <span className={`text-sm font-semibold transition-opacity duration-200 ${open ? 'opacity-100' : 'opacity-0'}`}>
          {title}
        </span>
      )}

      {notifs && open && (
        <span className="absolute right-3 flex h-5 w-5 items-center justify-center rounded-full bg-[#D03B26] text-[10px] text-white font-bold shadow-sm">
          {notifs}
        </span>
      )}
    </button>
  );
};

const TitleSection = ({ open }: { open: boolean }) => {
  return (
    <div className="mb-6 border-b border-stone-200 dark:border-stone-800 pb-5 pt-2">
      <div className="flex cursor-pointer items-center justify-between rounded-xl p-2 transition-colors hover:bg-stone-100 dark:hover:bg-stone-800/50">
        <div className="flex items-center gap-3">
          <Logo />
          {open && (
            <div className={`transition-opacity duration-200 ${open ? 'opacity-100' : 'opacity-0'}`}>
              <div className="flex flex-col text-left">
                <span className="block text-sm font-bold text-stone-900 dark:text-stone-100 leading-tight">
                  miCangrejo
                </span>
                <span className="block text-[10px] font-bold text-emerald-700 dark:text-emerald-500 uppercase tracking-wider mt-0.5">
                  Junta de Desarrollo
                </span>
              </div>
            </div>
          )}
        </div>
        {open && (
          <ChevronDown className="h-4 w-4 text-stone-400 dark:text-stone-500" />
        )}
      </div>
    </div>
  );
};

const Logo = () => {
  return (
    <div className="shrink-0 rounded-full shadow-sm border-2 border-stone-200 dark:border-stone-700 overflow-hidden size-11 bg-white">
      <img
        src="/logo-micangrejo.jpg"
        alt="miCangrejo Logo"
        className="w-full h-full object-cover"
      />
    </div>
  );
};

const ToggleClose = ({ open, setOpen }: { open: boolean, setOpen: any }) => {
  return (
    <button
      onClick={() => setOpen(!open)}
      className="absolute bottom-0 left-0 right-0 border-t border-stone-200 dark:border-stone-800 transition-colors hover:bg-stone-100 dark:hover:bg-stone-800"
    >
      <div className="flex items-center p-4">
        <div className="grid size-8 place-content-center">
          <ChevronsRight
            className={`h-5 w-5 transition-transform duration-300 text-stone-500 dark:text-stone-400 ${
              open ? "rotate-180" : ""
            }`}
          />
        </div>
        {open && (
          <span className={`text-sm font-semibold text-stone-600 dark:text-stone-300 ml-2 transition-opacity duration-200 ${open ? 'opacity-100' : 'opacity-0'}`}>
            Ocultar Menú
          </span>
        )}
      </div>
    </button>
  );
};

const ExampleContent = ({ isDark, setIsDark }: { isDark: boolean, setIsDark: any }) => {
  return (
    <div className="flex-1 bg-stone-50 dark:bg-stone-950/80 p-8 overflow-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-10">
        <div>
          <h1 className="text-3xl font-extrabold text-stone-900 dark:text-stone-100 tracking-tight">Panel de Control</h1>
          <p className="text-stone-500 dark:text-stone-400 mt-1.5 font-medium">Monitoreo de reportes y actividades del vecindario</p>
        </div>
        <div className="flex items-center gap-4">
          <button className="relative p-2.5 rounded-xl bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800 text-stone-500 dark:text-stone-400 hover:text-emerald-700 dark:hover:text-emerald-400 transition-colors shadow-sm">
            <Bell className="h-[1.15rem] w-[1.15rem]" />
            <span className="absolute top-2 right-2 h-2.5 w-2.5 bg-[#D03B26] rounded-full ring-2 ring-white dark:ring-stone-900"></span>
          </button>
          <button
            onClick={() => setIsDark(!isDark)}
            className="flex h-[2.6rem] w-[2.6rem] items-center justify-center rounded-xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 text-stone-500 dark:text-stone-400 hover:bg-stone-100 dark:hover:bg-stone-800 hover:text-stone-900 dark:hover:text-stone-100 transition-colors shadow-sm"
          >
            {isDark ? <Sun className="h-[1.15rem] w-[1.15rem]" /> : <Moon className="h-[1.15rem] w-[1.15rem]" />}
          </button>
          <button className="p-2.5 rounded-xl bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800 text-stone-500 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100 transition-colors shadow-sm">
            <User className="h-[1.15rem] w-[1.15rem]" />
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="p-6 rounded-2xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 shadow-sm hover:shadow-md transition-all">
          <div className="flex items-center justify-between mb-4">
            <div className="p-3 bg-emerald-100/80 dark:bg-emerald-900/30 rounded-xl">
              <FileText className="h-5 w-5 text-emerald-700 dark:text-emerald-400" />
            </div>
            <TrendingUp className="h-4 w-4 text-emerald-600 dark:text-emerald-500" />
          </div>
          <h3 className="font-semibold text-stone-500 dark:text-stone-400 mb-1">Nuevos Reportes</h3>
          <p className="text-3xl font-bold text-stone-900 dark:text-stone-100">12</p>
          <p className="text-sm text-emerald-600 dark:text-emerald-500 mt-2 font-medium">+3 desde ayer</p>
        </div>

        <div className="p-6 rounded-2xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 shadow-sm hover:shadow-md transition-all">
          <div className="flex items-center justify-between mb-4">
            <div className="p-3 bg-orange-100/80 dark:bg-[#D03B26]/20 rounded-xl">
              <AlertTriangle className="h-5 w-5 text-[#D03B26] dark:text-orange-400" />
            </div>
            <TrendingUp className="h-4 w-4 text-[#D03B26] dark:text-orange-500" />
          </div>
          <h3 className="font-semibold text-stone-500 dark:text-stone-400 mb-1">En Revisión</h3>
          <p className="text-3xl font-bold text-stone-900 dark:text-stone-100">5</p>
          <p className="text-sm text-[#D03B26] dark:text-orange-400 mt-2 font-medium">Atención requerida</p>
        </div>

        <div className="p-6 rounded-2xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 shadow-sm hover:shadow-md transition-all">
          <div className="flex items-center justify-between mb-4">
            <div className="p-3 bg-blue-100/80 dark:bg-blue-900/30 rounded-xl">
              <CheckCircle2 className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            <TrendingUp className="h-4 w-4 text-emerald-600 dark:text-emerald-500" />
          </div>
          <h3 className="font-semibold text-stone-500 dark:text-stone-400 mb-1">Casos Resueltos</h3>
          <p className="text-3xl font-bold text-stone-900 dark:text-stone-100">128</p>
          <p className="text-sm text-emerald-600 dark:text-emerald-500 mt-2 font-medium">+15% efectividad</p>
        </div>

        <div className="p-6 rounded-2xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 shadow-sm hover:shadow-md transition-all">
          <div className="flex items-center justify-between mb-4">
            <div className="p-3 bg-stone-100 dark:bg-stone-800 rounded-xl">
              <Users className="h-5 w-5 text-stone-600 dark:text-stone-400" />
            </div>
            <TrendingUp className="h-4 w-4 text-emerald-600 dark:text-emerald-500" />
          </div>
          <h3 className="font-semibold text-stone-500 dark:text-stone-400 mb-1">Vecinos Activos</h3>
          <p className="text-3xl font-bold text-stone-900 dark:text-stone-100">892</p>
          <p className="text-sm text-emerald-600 dark:text-emerald-500 mt-2 font-medium">+24 esta semana</p>
        </div>
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Recent Activity */}
        <div className="lg:col-span-2">
          <div className="rounded-2xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 p-7 shadow-sm">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold text-stone-900 dark:text-stone-100">Actividad Reciente</h3>
              <button className="text-sm text-emerald-700 dark:text-emerald-400 hover:text-emerald-800 dark:hover:text-emerald-300 font-bold transition-colors">
                Ver todos
              </button>
            </div>
            <div className="space-y-4">
              {[
                { icon: FileText, title: "Nuevo reporte: Bote de agua", desc: "Calle 5, Frente al parque", time: "Hace 10 min", color: "orange" },
                { icon: CheckCircle2, title: "Reporte #102 resuelto", desc: "Falla eléctrica solventada por autoridad", time: "Hace 2 horas", color: "emerald" },
                { icon: Users, title: "Nuevo vecino validado", desc: "Ana G. completó su registro", time: "Hace 4 horas", color: "blue" },
                { icon: AlertTriangle, title: "Alerta vecinal emitida", desc: "Precaución: Trabajos en vía principal", time: "Ayer", color: "orange" },
                { icon: ShieldCheck, title: "Autoridad asignada", desc: "Policía Municipal tomó el caso #098", time: "Ayer", color: "stone" },
              ].map((activity, i) => (
                <div key={i} className="flex items-center space-x-4 p-3.5 rounded-xl hover:bg-stone-50 dark:hover:bg-stone-800/50 transition-colors cursor-pointer group">
                  <div className={`p-2.5 rounded-xl transition-colors ${
                    activity.color === 'emerald' ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 group-hover:bg-emerald-100' :
                    activity.color === 'blue' ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 group-hover:bg-blue-100' :
                    activity.color === 'orange' ? 'bg-[#D03B26]/10 dark:bg-[#D03B26]/20 text-[#D03B26] dark:text-orange-400 group-hover:bg-[#D03B26]/20' :
                    'bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-400 group-hover:bg-stone-200'
                  }`}>
                    <activity.icon className="h-4 w-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold text-stone-900 dark:text-stone-100 truncate">
                      {activity.title}
                    </p>
                    <p className="text-xs font-medium text-stone-500 dark:text-stone-400 truncate mt-0.5">
                      {activity.desc}
                    </p>
                  </div>
                  <div className="text-xs font-bold text-stone-400 dark:text-stone-500">
                    {activity.time}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Quick Stats / Categorias */}
        <div className="space-y-6">
          <div className="rounded-2xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 p-7 shadow-sm">
            <h3 className="text-lg font-bold text-stone-900 dark:text-stone-100 mb-6">Estado de Reportes</h3>
            <div className="space-y-5">
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-semibold text-stone-600 dark:text-stone-400">Resueltos</span>
                  <span className="text-sm font-bold text-stone-900 dark:text-stone-100">65%</span>
                </div>
                <div className="w-full bg-stone-100 dark:bg-stone-800 rounded-full h-2">
                  <div className="bg-emerald-500 dark:bg-emerald-600 h-2 rounded-full" style={{ width: '65%' }}></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-semibold text-stone-600 dark:text-stone-400">En Proceso</span>
                  <span className="text-sm font-bold text-stone-900 dark:text-stone-100">25%</span>
                </div>
                <div className="w-full bg-stone-100 dark:bg-stone-800 rounded-full h-2">
                  <div className="bg-[#D03B26] h-2 rounded-full" style={{ width: '25%' }}></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-semibold text-stone-600 dark:text-stone-400">Pendientes</span>
                  <span className="text-sm font-bold text-stone-900 dark:text-stone-100">10%</span>
                </div>
                <div className="w-full bg-stone-100 dark:bg-stone-800 rounded-full h-2">
                  <div className="bg-orange-400 h-2 rounded-full" style={{ width: '10%' }}></div>
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 p-7 shadow-sm">
            <h3 className="text-lg font-bold text-stone-900 dark:text-stone-100 mb-4">Zonas Críticas</h3>
            <div className="space-y-3">
              {[
                { name: 'Parque Andrés Bello', count: 12 },
                { name: 'Vía Argentina', count: 8 },
                { name: 'Calle Eusebio A. Morales', count: 5 },
                { name: 'Plaza Einstein', count: 3 }
              ].map((zone, i) => (
                <div key={i} className="flex items-center justify-between py-2.5 border-b border-stone-100 dark:border-stone-800 last:border-0">
                  <span className="text-sm font-semibold text-stone-600 dark:text-stone-400">{zone.name}</span>
                  <span className="text-[11px] font-bold px-2.5 py-1 rounded-full bg-[#D03B26]/10 dark:bg-[#D03B26]/20 text-[#D03B26] dark:text-orange-400">
                    {zone.count} casos
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Example;
