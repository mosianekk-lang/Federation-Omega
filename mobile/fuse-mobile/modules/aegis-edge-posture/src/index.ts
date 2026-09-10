import { requireOptionalNativeModule } from 'expo';
import { Platform } from 'react-native';

export type AegisAndroidNativePosture = {
  securityPatch: string | null;
  screenLockConfigured: boolean;
  appDebuggable: boolean;
  sdkInt: number;
};

type NativeContract = {
  getPostureAsync(): Promise<AegisAndroidNativePosture>;
};

const Native = requireOptionalNativeModule<NativeContract>('AegisEdgePosture');

export async function getAegisAndroidNativePosture(): Promise<AegisAndroidNativePosture | null> {
  if (Platform.OS !== 'android' || !Native) return null;
  const value = await Native.getPostureAsync();
  if (!Number.isInteger(value.sdkInt) || value.sdkInt <= 0) throw new Error('AEGIS_EDGE_NATIVE_SDK_INVALID');
  return {
    securityPatch: value.securityPatch?.trim() || null,
    screenLockConfigured: Boolean(value.screenLockConfigured),
    appDebuggable: Boolean(value.appDebuggable),
    sdkInt: value.sdkInt,
  };
}
