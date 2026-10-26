import type { Metadata } from "next";
import { AuthScreen } from "@/components/features/auth/auth-screen";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return <AuthScreen />;
}
