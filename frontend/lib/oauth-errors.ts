export const OAUTH_ERROR_MESSAGES: Readonly<Record<string, string>> = {
  oauth_cancelled: "Google sign-in was cancelled. You can try again or use email.",
  oauth_invalid_state: "This Google sign-in request expired or could not be verified. Please try again.",
  oauth_invalid_response: "Google could not verify this sign-in. Please try again.",
  oauth_provider_unreachable: "AURORA could not reach Google's sign-in service. Please try again in a moment.",
  oauth_provider_error: "Google sign-in is temporarily unavailable. Please try again later.",
  oauth_account_conflict: "An AURORA account already uses this email. Sign in with your password; Google is not linked automatically.",
  oauth_inactive_account: "This AURORA account is inactive. Contact an administrator for access.",
  oauth_unavailable: "Google sign-in is not configured. Please use your email and password.",
};

export function oauthErrorMessage(code: string | null): string | null {
  if (!code) return null;
  return OAUTH_ERROR_MESSAGES[code] ?? "Google sign-in could not be completed safely. Please try again.";
}
