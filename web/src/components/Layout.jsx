import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext.jsx'

export default function Layout() {
  const { user, logout } = useAuth()
  return (
    <div className="min-h-screen bg-[#f6f5f1] text-slate-900">
      <header className="border-b border-slate-200 bg-white/95">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <NavLink to="/dashboard" className="self-center text-sm font-bold tracking-tight sm:self-auto">AI Interviewer</NavLink>
          <nav aria-label="Main navigation" className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-sm sm:justify-end sm:gap-5">
            <NavLink to="/dashboard" className={({ isActive }) => `min-h-9 inline-flex items-center ${isActive ? 'font-semibold text-indigo-700' : 'text-slate-600 hover:text-indigo-700'}`}>Dashboard</NavLink>
            <NavLink to="/upload-resume" className={({ isActive }) => `min-h-9 inline-flex items-center ${isActive ? 'font-semibold text-indigo-700' : 'text-slate-600 hover:text-indigo-700'}`}>Upload resume</NavLink>
            <NavLink to="/sessions/new" className={({ isActive }) => `min-h-9 inline-flex items-center ${isActive ? 'font-semibold text-indigo-700' : 'text-slate-600 hover:text-indigo-700'}`}>New interview</NavLink>
            <span className="hidden max-w-32 truncate text-slate-500 md:inline">{user?.name}</span>
            <button onClick={() => logout()} className="min-h-9 font-semibold text-slate-700 hover:text-indigo-700">Log out</button>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-7 sm:px-6 sm:py-10"><Outlet /></main>
    </div>
  )
}
