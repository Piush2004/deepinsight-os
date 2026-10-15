import { SignUp } from "@clerk/nextjs";

export default function Page() {
  return (
    <div className="flex h-screen w-full items-center justify-center bg-zinc-50 dark:bg-zinc-950">
      <SignUp path="/sign-up" />
    </div>
  );
}
