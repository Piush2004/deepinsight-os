"use client"

import React, { useState, useEffect } from 'react'
import { Search, FileText, Settings, FolderKanban, PenTool, LayoutDashboard } from 'lucide-react'
import { useRouter } from 'next/navigation'

export function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState('')
  const router = useRouter()

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setIsOpen((open) => !open)
      }
      if (e.key === 'Escape') {
        setIsOpen(false)
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  if (!isOpen) return null

  const actions = [
    { id: 1, name: 'Go to Dashboard', icon: LayoutDashboard, route: '/' },
    { id: 2, name: 'Generate New Report', icon: FileText, route: '/reports' },
    { id: 3, name: 'Manage Clients', icon: FolderKanban, route: '/clients' },
    { id: 4, name: 'Content Platform', icon: PenTool, route: '/content' },
    { id: 5, name: 'Team Settings', icon: Settings, route: '/settings' },
  ]

  const filtered = actions.filter(action => action.name.toLowerCase().includes(query.toLowerCase()))

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] font-body bg-background/50 backdrop-blur-sm">
      <div className="absolute inset-0" onClick={() => setIsOpen(false)}></div>
      
      <div className="relative w-full max-w-xl bg-card border border-border shadow-2xl rounded-xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center px-4 border-b border-border">
          <Search className="w-5 h-5 text-muted-foreground" />
          <input 
            autoFocus
            className="w-full bg-transparent px-4 py-4 text-foreground outline-none placeholder:text-muted-foreground"
            placeholder="Search commands, clients, or reports..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <kbd className="hidden sm:inline-flex items-center gap-1 rounded border border-border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground h-5">
            <span className="text-xs">ESC</span>
          </kbd>
        </div>

        <div className="max-h-80 overflow-y-auto p-2">
          {filtered.length === 0 ? (
            <div className="py-6 text-center text-sm text-muted-foreground">No results found.</div>
          ) : (
            <div className="space-y-1">
              {filtered.map((action, idx) => (
                <button
                  key={action.id}
                  onClick={() => {
                    router.push(action.route)
                    setIsOpen(false)
                  }}
                  className={`w-full flex items-center px-4 py-3 rounded-md text-sm transition-colors ${
                    idx === 0 ? 'bg-primary/10 text-primary' : 'text-foreground hover:bg-muted'
                  }`}
                >
                  <action.icon className={`w-4 h-4 mr-3 ${idx === 0 ? 'text-primary' : 'text-muted-foreground'}`} />
                  {action.name}
                </button>
              ))}
            </div>
          )}
        </div>
        
        <div className="px-4 py-3 border-t border-border/50 bg-muted/30 text-xs text-muted-foreground flex justify-between">
          <span>Search powered by DeepInsight OS</span>
          <div className="flex items-center space-x-2">
            <span>Use</span>
            <kbd className="bg-muted border border-border rounded px-1">&uarr;</kbd>
            <kbd className="bg-muted border border-border rounded px-1">&darr;</kbd>
            <span>to navigate</span>
          </div>
        </div>
      </div>
    </div>
  )
}
