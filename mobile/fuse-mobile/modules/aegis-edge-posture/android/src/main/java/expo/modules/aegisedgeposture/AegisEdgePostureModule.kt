package expo.modules.aegisedgeposture

import android.app.KeyguardManager
import android.content.Context
import android.content.pm.ApplicationInfo
import android.os.Build
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

/**
 * AEGIS Edge: deliberately small, permissionless Android posture adapter.
 *
 * It exposes only platform facts Android makes reliably available to the
 * calling app without collecting device identifiers, app inventory, network
 * identity, content, location, or accessibility data.
 */
class AegisEdgePostureModule : Module() {
  override fun definition() = ModuleDefinition {
    Name("AegisEdgePosture")

    AsyncFunction("getPostureAsync") {
      val context = appContext.reactContext
        ?: throw IllegalStateException("AEGIS_EDGE_ANDROID_CONTEXT_UNAVAILABLE")
      val keyguard = context.getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
      val appInfo = context.applicationInfo
      val patch = Build.VERSION.SECURITY_PATCH.trim().ifEmpty { null }
      mapOf(
        "securityPatch" to patch,
        "screenLockConfigured" to keyguard.isDeviceSecure,
        "appDebuggable" to ((appInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE) != 0),
        "sdkInt" to Build.VERSION.SDK_INT
      )
    }
  }
}
