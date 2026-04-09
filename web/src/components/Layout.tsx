import { NavLink, Outlet } from 'react-router-dom'
import {
  Heart,
  Compass,
  Store,
  Copy,
  Settings,
  Waves,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
} from 'lucide-react'
import { useState } from 'react'

const navItems = [
  { to: '/legacy', label: 'Your Legacy', icon: Heart, description: 'See your voice data' },
  { to: '/discover', label: 'Discover', icon: Compass, description: 'What\'s possible' },
  { to: '/studio', label: 'Clone Studio', icon: Store, description: 'Provider marketplace' },
  { to: '/my-clones', label: 'My Clones', icon: Copy, description: 'Status & preview' },
  { to: '/settings', label: 'Settings', icon: Settings, description: 'Preferences' },
]

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed md:relative z-50 flex flex-col border-r border-windy-border bg-windy-darker transition-all duration-300 ease-in-out h-full
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
          ${collapsed ? 'w-20' : 'w-64'}
        `}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-5 py-6 border-b border-windy-border">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-glow to-purple-glow shrink-0">
            <Waves className="w-5 h-5 text-white" />
          </div>
          {!collapsed && (
            <div className="animate-fade-in-up">
              <h1 className="text-lg font-display font-bold gradient-text-mixed leading-tight">
                Windy Clone
              </h1>
              <p className="text-[10px] text-text-muted tracking-wider uppercase">
                Your voice lives forever
              </p>
            </div>
          )}

          {/* Mobile close button */}
          <button
            className="ml-auto md:hidden text-text-muted hover:text-text-primary"
            onClick={() => setMobileOpen(false)}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                `group flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-200 ${
                  isActive
                    ? 'bg-gradient-to-r from-cyan-glow/15 to-purple-glow/10 text-cyan-bright border border-cyan-glow/20'
                    : 'text-text-secondary hover:text-text-primary hover:bg-windy-card'
                }`
              }
            >
              <item.icon className="w-5 h-5 shrink-0" />
              {!collapsed && (
                <div>
                  <span className="text-sm font-medium">{item.label}</span>
                  <p className="text-[10px] text-text-muted leading-tight mt-0.5 group-hover:text-text-secondary transition-colors">
                    {item.description}
                  </p>
                </div>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Collapse btn (desktop only) */}
        <button
          id="toggle-sidebar"
          onClick={() => setCollapsed(!collapsed)}
          className="absolute -right-3 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-windy-card border border-windy-border hidden md:flex items-center justify-center text-text-muted hover:text-text-primary hover:border-cyan-glow/30 transition-all z-10"
        >
          {collapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronLeft className="w-3 h-3" />}
        </button>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-windy-border">
          {!collapsed ? (
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-glow to-cyan-glow flex items-center justify-center text-xs font-bold text-white">
                G
              </div>
              <div>
                <p className="text-sm font-medium text-text-primary">Grant</p>
                <p className="text-[10px] text-text-muted">Windy Pro Connected</p>
              </div>
            </div>
          ) : (
            <div className="flex justify-center">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-glow to-cyan-glow flex items-center justify-center text-xs font-bold text-white">
                G
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-windy-dark">
        {/* Mobile header */}
        <div className="md:hidden flex items-center gap-3 px-4 py-3 border-b border-windy-border bg-windy-darker">
          <button
            id="mobile-menu"
            onClick={() => setMobileOpen(true)}
            className="w-10 h-10 rounded-xl bg-windy-card border border-windy-border flex items-center justify-center text-text-muted hover:text-text-primary transition-colors"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-glow to-purple-glow flex items-center justify-center">
              <Waves className="w-4 h-4 text-white" />
            </div>
            <span className="text-sm font-display font-bold gradient-text-mixed">Windy Clone</span>
          </div>
        </div>

        <div className="max-w-6xl mx-auto px-4 md:px-6 py-6 md:py-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
