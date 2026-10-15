"use client"

import { useState } from 'react'
import { Check, ChevronRight } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useApiClient } from '@/hooks/useApiClient'

export default function OnboardingPage() {
  const [step, setStep] = useState(1)
  const [name, setName] = useState('')
  const [industry, setIndustry] = useState('B2B SaaS')
  const router = useRouter()
  const api = useApiClient()

  const createClientMutation = useMutation({
    mutationFn: () => api.clients.create({ name, industry }),
    onSuccess: () => {
      toast.success(`${name} workspace created`)
      router.push('/')
    },
    onError: (err: Error) => toast.error(`Failed to create workspace: ${err.message}`),
  })

  const handleNext = () => {
    if (step === 1 && !name.trim()) {
      toast.error('Enter a name for this workspace first.')
      return
    }
    if (step < 4) {
      setStep(step + 1)
    } else {
      createClientMutation.mutate()
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground font-body flex flex-col items-center justify-center p-6">

      <div className="w-full max-w-2xl space-y-12">
        {/* Progress indicator */}
        <div className="flex justify-between relative">
          <div className="absolute top-1/2 left-0 right-0 h-[2px] bg-border -z-10 -translate-y-1/2"></div>
          <div className="absolute top-1/2 left-0 h-[2px] bg-primary -z-10 -translate-y-1/2 transition-all duration-500" style={{ width: `${((step - 1) / 3) * 100}%` }}></div>

          {[1, 2, 3, 4].map((s) => (
            <div
              key={s}
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
                step > s
                  ? 'bg-primary text-primary-foreground border-2 border-primary'
                  : step === s
                    ? 'bg-background text-primary border-2 border-primary'
                    : 'bg-background text-muted-foreground border-2 border-border'
              }`}
            >
              {step > s ? <Check className="w-4 h-4" /> : s}
            </div>
          ))}
        </div>

        {/* Content Area */}
        <div className="bg-card border border-border rounded-xl p-10 shadow-sm min-h-[400px] flex flex-col">

          {step === 1 && (
            <div className="space-y-6 flex-1">
              <div>
                <h2 className="text-3xl font-heading font-medium tracking-tight">Welcome to DeepInsight OS</h2>
                <p className="text-muted-foreground mt-2">Let&apos;s set up your first client workspace.</p>
              </div>
              <div className="space-y-4 pt-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Client Name</label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Joseph Studios"
                    className="w-full p-3 bg-background border border-border rounded-md outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Primary Focus</label>
                  <select
                    value={industry}
                    onChange={(e) => setIndustry(e.target.value)}
                    className="w-full p-3 bg-background border border-border rounded-md outline-none focus:ring-1 focus:ring-ring"
                  >
                    <option>B2B SaaS</option>
                    <option>Enterprise Tech</option>
                    <option>Healthcare</option>
                    <option>Multi-Industry</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-6 flex-1">
              <div>
                <h2 className="text-3xl font-heading font-medium tracking-tight">Connect Data Sources</h2>
                <p className="text-muted-foreground mt-2">
                  You&apos;ll connect integrations from Settings once this workspace is created - GA4 and
                  Search Console are supported today.
                </p>
              </div>
              <div className="space-y-4 pt-4">
                {['Google Search Console', 'Google Analytics 4'].map(source => (
                  <div key={source} className="flex items-center justify-between p-4 border border-border rounded-md">
                    <span className="font-medium">{source}</span>
                    <span className="text-sm text-muted-foreground">Available after setup</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-6 flex-1">
              <div>
                <h2 className="text-3xl font-heading font-medium tracking-tight">What&apos;s available today</h2>
                <p className="text-muted-foreground mt-2">These agents are live and ready to use once your workspace is created.</p>
              </div>
              <div className="grid grid-cols-2 gap-4 pt-4">
                {[
                  { name: 'Reporting Agent', active: true },
                  { name: 'Content Agent', active: true },
                  { name: 'Email Agent', active: false },
                  { name: 'SEO Agent', active: false }
                ].map(agent => (
                  <div key={agent.name} className={`p-4 border rounded-md transition-colors ${agent.active ? 'border-primary bg-primary/5' : 'border-border opacity-60'}`}>
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm">{agent.name}</span>
                      <div className={`w-4 h-4 rounded-full border flex items-center justify-center ${agent.active ? 'border-primary bg-primary' : 'border-muted-foreground'}`}>
                        {agent.active && <Check className="w-3 h-3 text-primary-foreground" />}
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">{agent.active ? 'Live now' : 'Coming soon'}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-6 flex-1 flex flex-col items-center justify-center text-center">
              <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mb-4 border border-primary/20">
                <Check className="w-8 h-8 text-primary" />
              </div>
              <h2 className="text-3xl font-heading font-medium tracking-tight">Ready to create &quot;{name}&quot;</h2>
              <p className="text-muted-foreground max-w-sm">
                This creates a real client workspace you can immediately upload documents to, and generate
                reports and content for.
              </p>
            </div>
          )}

          {/* Footer Actions */}
          <div className="pt-8 border-t border-border/50 mt-auto flex justify-between">
            <button
              onClick={() => setStep(Math.max(1, step - 1))}
              className={`px-6 py-2 rounded-md font-medium text-sm ${step === 1 ? 'invisible' : 'text-muted-foreground hover:text-foreground'}`}
            >
              Back
            </button>
            <button
              onClick={handleNext}
              disabled={createClientMutation.isPending}
              className="bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 px-8 py-2 rounded-md transition-colors font-medium shadow-sm flex items-center"
            >
              <span>{step === 4 ? (createClientMutation.isPending ? 'Creating...' : 'Create Workspace') : 'Continue'}</span>
              {step !== 4 && <ChevronRight className="w-4 h-4 ml-1" />}
            </button>
          </div>
        </div>

      </div>
    </div>
  )
}
