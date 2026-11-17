import type { LucideIcon } from 'lucide-react'

import { cn } from '@/lib/utils'

export type AuthSwitchOption = {
  value: string
  label: string
  description: string
  icon: LucideIcon
}

type AuthSwitchProps = {
  value: string
  options: AuthSwitchOption[]
  onValueChange: (value: string) => void
  label: string
}

export function AuthSwitch({ value, options, onValueChange, label }: AuthSwitchProps) {
  const selectedOption = options.find((option) => option.value === value) ?? options[0]
  const SelectedIcon = selectedOption.icon

  return (
    <div aria-label={label} role="radiogroup">
      <div className="grid grid-cols-3 gap-1 rounded-xl border border-emerald-100 bg-emerald-50/70 p-1.5">
        {options.map((option) => {
          const isSelected = option.value === value
          const shortLabel = option.label === 'Administrador JDL' ? 'JDL' : option.label

          return (
            <button
              aria-checked={isSelected}
              className={cn(
                'rounded-lg px-2 py-2 text-xs font-bold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2 sm:text-sm',
                isSelected
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-emerald-900/70 hover:bg-white hover:text-emerald-900',
              )}
              key={option.value}
              onClick={() => onValueChange(option.value)}
              role="radio"
              type="button"
            >
              {shortLabel}
            </button>
          )
        })}
      </div>

      <div className="mt-3 flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-emerald-100 text-emerald-700"><SelectedIcon size={20} /></span>
        <span>
          <span className="block text-sm font-semibold text-slate-800">{selectedOption.label}</span>
          <span className="mt-0.5 block text-xs leading-5 text-slate-500">{selectedOption.description}</span>
        </span>
      </div>
    </div>
  )
}

export default AuthSwitch
