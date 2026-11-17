import { useState } from 'react'
import { LoginScreen, type AppSession } from '@/components/LoginScreen'
import { Workspace } from '@/components/Workspace'

export default function App() {
  const [session, setSession] = useState<AppSession | null>(null)

  if (!session) return <LoginScreen onLogin={setSession} />

  return <Workspace session={session} onLogout={() => setSession(null)} />
}
