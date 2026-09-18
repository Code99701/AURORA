import assert from "node:assert/strict";
import test from "node:test";

import { oauthErrorMessage } from "../lib/oauth-errors.ts";

test("maps allowlisted OAuth errors to safe guidance", () => {
  assert.match(oauthErrorMessage("oauth_account_conflict"), /password/);
  assert.match(oauthErrorMessage("oauth_invalid_state"), /verified/);
  assert.match(oauthErrorMessage("oauth_provider_unreachable"), /could not reach Google/);
  assert.equal(oauthErrorMessage(null), null);
});

test("does not render a provider-supplied error value", () => {
  const unsafe = "client_secret=do-not-render";
  const message = oauthErrorMessage(unsafe);
  assert.doesNotMatch(message, /client_secret|do-not-render/);
  assert.match(message, /could not be completed safely/);
});
