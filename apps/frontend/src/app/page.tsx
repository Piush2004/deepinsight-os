import React from 'react'
import Link from 'next/link'

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground font-body flex flex-col">
      <header className="py-6 px-10 flex justify-between items-center border-b border-border/40">
        <div className="font-heading font-medium text-xl tracking-tight">DeepInsight OS</div>
        <nav className="space-x-8 text-sm font-medium">
          <Link href="/sign-in" className="text-muted-foreground hover:text-foreground transition-colors">Client Portal</Link>
          <Link href="/sign-in" className="text-primary hover:text-primary/80 transition-colors">Agency Login</Link>
        </nav>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center text-center px-6 -mt-20">
        <h1 className="text-5xl md:text-7xl font-heading font-medium tracking-tight max-w-4xl leading-tight">
          Organic Marketing,<br/> Powered by Intelligence.
        </h1>
        <p className="mt-8 text-lg text-muted-foreground max-w-2xl leading-relaxed">
          The internal AI operating system driving authentic strategy, premium content, and measurable authority for Joseph Studios clients.
        </p>
        
        <div className="mt-12">
          <Link 
            href="/sign-in"
            className="inline-flex items-center justify-center bg-primary text-primary-foreground hover:bg-primary/90 px-8 py-4 rounded-md transition-colors font-medium shadow-sm text-lg"
          >
            Access Your Portal
          </Link>
        </div>
      </main>

      <footer className="py-8 text-center text-sm text-muted-foreground border-t border-border/40">
        &copy; {new Date().getFullYear()} Joseph Studios. All rights reserved.
      </footer>
    </div>
  )
}
