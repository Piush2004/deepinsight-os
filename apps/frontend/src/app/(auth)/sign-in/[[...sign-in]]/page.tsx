import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-6 font-body">
      <div className="w-full max-w-md space-y-8 text-center">
        <div>
          <h1 className="text-3xl font-heading font-medium tracking-tight text-foreground">DeepInsight OS</h1>
          <p className="mt-2 text-sm text-muted-foreground">Secure access to your strategic intelligence.</p>
        </div>
        
        <div className="bg-card border border-border p-8 rounded-xl shadow-sm">
          <SignIn 
            appearance={{
              elements: {
                card: "shadow-none p-0 border-0 bg-transparent",
                headerTitle: "hidden",
                headerSubtitle: "hidden",
                formButtonPrimary: "bg-primary hover:bg-primary/90 text-primary-foreground shadow-sm rounded-md",
                formFieldInput: "bg-background border-border rounded-md",
                formFieldLabel: "text-foreground font-medium",
                footerActionLink: "text-primary hover:text-primary/80",
                identityPreviewText: "text-foreground",
                identityPreviewEditButtonIcon: "text-muted-foreground"
              }
            }}
          />
        </div>

        <div className="pt-6 border-t border-border/50 text-xs text-muted-foreground">
          <p>Protected by enterprise-grade security.</p>
        </div>
      </div>
    </div>
  );
}
