using System.Security.Cryptography;

namespace Fuse.Windows.Native;

internal sealed class NativeIdentity : IDisposable
{
    public const string DefaultKeyName = "FUSE-WINDOWS-NATIVE-P256-V1";
    private static readonly CngProvider Provider = CngProvider.MicrosoftSoftwareKeyStorageProvider;
    private readonly CngKey _key;
    private readonly ECDsaCng _ecdsa;

    private NativeIdentity(CngKey key)
    {
        _key = key;
        _ecdsa = new ECDsaCng(_key)
        {
            HashAlgorithm = CngAlgorithm.Sha256
        };
    }

    public static NativeIdentity OpenOrCreate(string keyName)
    {
        if (!OperatingSystem.IsWindows()) throw new PlatformNotSupportedException("WINDOWS_RUNTIME_REQUIRED");
        if (string.IsNullOrWhiteSpace(keyName) || keyName.Length > 128) throw new InvalidDataException("CNG_KEY_NAME_INVALID");
        CngKey key;
        if (CngKey.Exists(keyName, Provider))
        {
            key = CngKey.Open(keyName, Provider, CngKeyOpenOptions.UserKey);
        }
        else
        {
            var parameters = new CngKeyCreationParameters
            {
                Provider = Provider,
                KeyCreationOptions = CngKeyCreationOptions.None,
                KeyUsage = CngKeyUsages.Signing
            };
            key = CngKey.Create(CngAlgorithm.ECDsaP256, keyName, parameters);
        }
        return new NativeIdentity(key);
    }

    public string PublicSpkiBase64Url => Base64Url.Encode(_ecdsa.ExportSubjectPublicKeyInfo());

    public byte[] Sign(byte[] payload) => _ecdsa.SignData(
        payload,
        HashAlgorithmName.SHA256,
        DSASignatureFormat.Rfc3279DerSequence);

    public void Dispose()
    {
        _ecdsa.Dispose();
        _key.Dispose();
    }
}
