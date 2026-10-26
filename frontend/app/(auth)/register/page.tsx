import type { Metadata } from "next";
import { AuthScreen } from "@/components/features/auth/auth-screen";

export const metadata: Metadata = {
  title: "Create Account · AURORA",
  description: "Create an account to begin researching with evidence-grounded workspaces.",
};

export default function RegisterPage() {
  return <AuthScreen initialMode="register" />;
}
