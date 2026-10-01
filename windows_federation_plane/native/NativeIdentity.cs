using System.Security.Cryptography;

namespace Fuse.Windows.Native;

internal sealed class NativeIdentity : IDisposable
{
    public const string DefaultKeyName = "FUSE-WINDOWS-NATIVE-P256-V1";
    private static readonly CngProvider PlatformProvider = new("Microsoft Platform Crypto Provider");
    private static readonly CngProvider SoftwareProvider = CngProvider.MicrosoftSoftwareKeyStorageProvider;
    private readonly CngKey _key;
    private readonly ECDsaCng _ecdsa;

    private NativeIdentity(CngKey key, string assurance)
    {
        _key = key;
        Assurance = assurance;
        ProviderName = key.Provider.Provider;
        _ecdsa = new ECDsaCng(_key)
        {
            HashAlgorithm = CngAlgorithm.Sha256
        };
    }

    public string Assurance { get; }
    public string ProviderName { get; }

    public static NativeIdentity OpenOrCreate(string keyName)
    {
        if (!OperatingSystem.IsWindows()) throw new PlatformNotSupportedException("WINDOWS_RUNTIME_REQUIRED");
        if (string.IsNullOrWhiteSpace(keyName) || keyName.Length > 128) throw new InvalidDataException("CNG_KEY_NAME_INVALID");

        foreach (var candidate in new[]
        {
            (Provider: PlatformProvider, Assurance: "TPM_PLATFORM"),
            (Provider: SoftwareProvider, Assurance: "SOFTWARE_CNG_LOWER_ASSURANCE")
        })
        {
            try
            {
                if (CngKey.Exists(keyName, candidate.Provider))
                {
                    return new NativeIdentity(CngKey.Open(keyName, candidate.Provider), candidate.Assurance);
                }
            }
            catch (CryptographicException)
            {
                // Provider unavailable or inaccessible. Fall through without weakening any security setting.
            }
        }

        try
        {
            var platformParameters = new CngKeyCreationParameters
            {
                Provider = PlatformProvider,
                KeyCreationOptions = CngKeyCreationOptions.None,
                KeyUsage = CngKeyUsages.Signing,
                ExportPolicy = CngExportPolicies.None
            };
            return new NativeIdentity(
                CngKey.Create(CngAlgorithm.ECDsaP256, keyName, platformParameters),
                "TPM_PLATFORM");
        }
        catch (CryptographicException)
        {
            var softwareParameters = new CngKeyCreationParameters
            {
                Provider = SoftwareProvider,
                KeyCreationOptions = CngKeyCreationOptions.None,
                KeyUsage = CngKeyUsages.Signing,
                ExportPolicy = CngExportPolicies.None
            };
            return new NativeIdentity(
                CngKey.Create(CngAlgorithm.ECDsaP256, keyName, softwareParameters),
                "SOFTWARE_CNG_LOWER_ASSURANCE");
        }
    }

    public string PublicSpkiBase64Url => Base64Url.Encode(_ecdsa.ExportSubjectPublicKeyInfo());

    public byte[] Sign(byte[] payload) => _ecdsa.SignData(
        payload,
        HashAlgorithmName.SHA256,
        DSASignatureFormat.Rfc3279DerSequence);

    public bool Verify(byte[] payload, byte[] signature) => _ecdsa.VerifyData(
        payload,
        signature,
        HashAlgorithmName.SHA256,
        DSASignatureFormat.Rfc3279DerSequence);

    public void Dispose()
    {
        _ecdsa.Dispose();
        _key.Dispose();
    }
}
