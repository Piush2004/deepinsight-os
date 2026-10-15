"use client"

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Building, Plus, Search, ChevronRight, X } from 'lucide-react'
import Link from 'next/link'
import { useApiClient } from '@/hooks/useApiClient'
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/StateViews'

export default function ClientsPage() {
  const api = useApiClient()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [showCreateForm, setShowCreateForm] = useState(false)

  const clientsQuery = useQuery({
    queryKey: ['clients', 'list', search],
    queryFn: () => api.clients.list({ q: search || undefined, limit: 100 }),
  })

  const createMutation = useMutation({
    mutationFn: (data: { name: string; industry: string }) => api.clients.create(data),
    onSuccess: () => {
      toast.success('Client created')
      setShowCreateForm(false)
      queryClient.invalidateQueries({ queryKey: ['clients'] })
    },
    onError: (err: Error) => toast.error(`Failed to create client: ${err.message}`),
  })

  return (
    <div className="flex flex-col h-full space-y-12 p-8 max-w-7xl mx-auto font-body">
      <div className="flex justify-between items-end border-b border-border pb-6">
        <div>
          <h1 className="text-4xl font-heading font-medium tracking-tight text-foreground">Client Portals</h1>
          <p className="text-muted-foreground mt-2 text-sm max-w-xl">
            Access and manage strategic workspaces for all active clients.
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search clients..."
              className="pl-9 pr-4 py-2 bg-background border border-border rounded-md text-sm outline-none focus:ring-1 focus:ring-ring w-64"
            />
          </div>
          <button
            onClick={() => setShowCreateForm(true)}
            className="bg-primary text-primary-foreground hover:bg-primary/90 px-5 py-2 rounded-md transition-colors font-medium shadow-sm flex items-center space-x-2 text-sm"
          >
            <Plus className="w-4 h-4" />
            <span>New Client</span>
          </button>
        </div>
      </div>

      {showCreateForm && (
        <CreateClientForm
          onCancel={() => setShowCreateForm(false)}
          onSubmit={(data) => createMutation.mutate(data)}
          isPending={createMutation.isPending}
        />
      )}

      {clientsQuery.isLoading && <LoadingState label="Loading clients..." />}
      {clientsQuery.isError && (
        <ErrorState message={(clientsQuery.error as Error).message} onRetry={() => clientsQuery.refetch()} />
      )}
      {clientsQuery.data && clientsQuery.data.length === 0 && (
        <EmptyState
          title="No clients yet"
          description="Create your first client to start uploading knowledge, generating reports, and drafting content."
        />
      )}

      {clientsQuery.data && clientsQuery.data.length > 0 && (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {clientsQuery.data.map((client) => (
            <Link key={client.id} href={`/clients/${client.id}`} className="group block">
              <div className="p-6 bg-card border border-border rounded-xl shadow-sm hover:border-primary/50 transition-colors h-full flex flex-col">
                <div className="flex items-start justify-between mb-6">
                  <div className="w-12 h-12 bg-muted rounded-lg flex items-center justify-center text-muted-foreground group-hover:text-primary group-hover:bg-primary/10 transition-colors">
                    <Building className="w-6 h-6" />
                  </div>
                  <ChevronRight className="w-5 h-5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>

                <h3 className="text-xl font-heading font-medium text-foreground group-hover:text-primary transition-colors">{client.name}</h3>
                <p className="text-sm text-muted-foreground mt-1">{client.industry || 'No industry set'}</p>

                <div className="mt-auto pt-6 border-t border-border/50 flex items-center justify-between text-sm">
                  <span className="text-muted-foreground capitalize">{client.status}</span>
                  <span className="text-muted-foreground">
                    Since {new Date(client.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function CreateClientForm({
  onCancel,
  onSubmit,
  isPending,
}: {
  onCancel: () => void
  onSubmit: (data: { name: string; industry: string }) => void
  isPending: boolean
}) {
  const [name, setName] = useState('')
  const [industry, setIndustry] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    onSubmit({ name, industry })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 bg-card border border-border rounded-lg p-6">
      <div className="flex items-center justify-between">
        <h2 className="font-heading font-medium text-lg">New client</h2>
        <button type="button" onClick={onCancel} className="text-muted-foreground hover:text-foreground">
          <X className="w-5 h-5" />
        </button>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <label className="block text-sm font-medium text-foreground">Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full bg-background border border-border rounded-md p-3 text-foreground outline-none focus:ring-1 focus:ring-ring"
            placeholder="Acme Corp"
          />
        </div>
        <div className="space-y-2">
          <label className="block text-sm font-medium text-foreground">Industry</label>
          <input
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
            className="w-full bg-background border border-border rounded-md p-3 text-foreground outline-none focus:ring-1 focus:ring-ring"
            placeholder="B2B SaaS"
          />
        </div>
      </div>
      <button
        type="submit"
        disabled={isPending || !name.trim()}
        className="bg-primary hover:bg-primary/90 disabled:opacity-50 text-primary-foreground font-medium px-6 py-2.5 rounded-md transition-colors shadow-sm text-sm"
      >
        {isPending ? 'Creating...' : 'Create Client'}
      </button>
    </form>
  )
}
