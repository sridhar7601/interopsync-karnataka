import { Routes, Route, NavLink } from 'react-router-dom'
import {
  ArrowLeftRight,
  LayoutDashboard,
  FileText,
  Activity,
  AlertTriangle,
} from 'lucide-react'
import SyncDashboard from './pages/SyncDashboard'
import ConflictResolution from './pages/ConflictResolution'
import AuditTrail from './pages/AuditTrail'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/applications', label: 'Applications', icon: FileText },
  { to: '/sync-events', label: 'Sync Events', icon: Activity },
  { to: '/conflicts', label: 'Conflicts', icon: AlertTriangle },
]

function App() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <div className="bg-gradient-to-br from-amber-500 to-orange-600 text-white p-1.5 rounded-lg shadow-sm shadow-amber-500/30">
                <ArrowLeftRight className="h-5 w-5" />
              </div>
              <div>
                <div className="text-base font-bold text-gray-900 leading-tight">InteropSync</div>
                <div className="text-[10px] uppercase tracking-wider text-gray-500">SWS ↔ Department</div>
              </div>
            </div>
            <nav className="flex items-center gap-1">
              {navItems.map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    `flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-amber-500 text-white shadow-sm'
                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                    }`
                  }
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </NavLink>
              ))}
            </nav>
            <div className="hidden lg:flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500"></span>
              </span>
              <span className="text-xs font-medium text-emerald-700">Live</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Routes>
          <Route path="/" element={<SyncDashboard />} />
          <Route path="/applications" element={<SyncDashboard showApplicationsOnly />} />
          <Route path="/sync-events" element={<AuditTrail />} />
          <Route path="/conflicts" element={<ConflictResolution />} />
        </Routes>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 py-4 text-center text-xs text-gray-400">
        InteropSync &mdash; SWS &harr; Department Interoperability Middleware &mdash; PanIIT Hackathon 2026
      </footer>
    </div>
  )
}

export default App
