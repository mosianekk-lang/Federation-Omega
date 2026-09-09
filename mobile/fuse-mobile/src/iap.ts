import {
  GoogleSignin,
  isNoSavedCredentialFoundResponse,
  isSuccessResponse,
} from '@react-native-google-signin/google-signin';

// This is the public OAuth client ID of the IAP-secured resource, used as the
// ID-token audience/web client. The installed native app OAuth client is a
// separate provider-side identity and must be allowlisted for IAP programmatic access.
const IAP_RESOURCE_CLIENT_ID = process.env.EXPO_PUBLIC_FUSE_IAP_RESOURCE_CLIENT_ID?.trim() ?? '';
let configuredResourceClientId = '';

export function iapConfigured(): boolean {
  return IAP_RESOURCE_CLIENT_ID.length > 0;
}

function configureGoogleOwnerIdentity(): void {
  if (!IAP_RESOURCE_CLIENT_ID) throw new Error('FUSE_IAP_RESOURCE_CLIENT_ID_REQUIRED');
  if (configuredResourceClientId === IAP_RESOURCE_CLIENT_ID) return;
  GoogleSignin.configure({
    webClientId: IAP_RESOURCE_CLIENT_ID,
    offlineAccess: false,
    scopes: ['email', 'profile'],
  });
  configuredResourceClientId = IAP_RESOURCE_CLIENT_ID;
}

async function ensureSignedIn(interactive: boolean): Promise<void> {
  configureGoogleOwnerIdentity();
  await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: interactive });

  if (interactive) {
    const response = await GoogleSignin.signIn({});
    if (!isSuccessResponse(response)) throw new Error('OWNER_SIGN_IN_CANCELLED');
    return;
  }

  if (!GoogleSignin.hasPreviousSignIn()) throw new Error('OWNER_SIGN_IN_REQUIRED');
  const response = await GoogleSignin.signInSilently();
  if (isNoSavedCredentialFoundResponse(response)) throw new Error('OWNER_SIGN_IN_REQUIRED');
  if (!isSuccessResponse(response)) throw new Error('OWNER_SIGN_IN_REQUIRED');
}

export async function getIapIdentityToken(interactive = false): Promise<string> {
  await ensureSignedIn(interactive);
  const tokens = await GoogleSignin.getTokens();
  if (!tokens.idToken?.trim()) throw new Error('IAP_ID_TOKEN_REQUIRED');
  return tokens.idToken.trim();
}

export async function signOutOwnerIdentity(): Promise<void> {
  if (!iapConfigured()) return;
  configureGoogleOwnerIdentity();
  await GoogleSignin.signOut();
}
