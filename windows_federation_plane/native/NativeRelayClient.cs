using System.Globalization;
using System.Net;
using System.Net.Http.Headers;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Fuse.Windows.Native;

internal sealed class NativeRelayClient : IDisposable
{
    private const string RelayTaskSchema = "FEDERATION-WINDOWS-TASK-V1";
    private const string RelayReceiptSchema = "FEDERATION-WINDOWS-RECEIPT-V1";
    private readonly Uri _baseUri;
    private readonly string _originSha256;
    private readonly string _stateDirectory;
    private readonly string _workspace;
    private readonly NativeIdentity _identity;
    private readonly NativeJournal _journal;
    private readonly HttpClient _http;
    private readonly string _sourceSha;

    private NativeRelayClient(Uri baseUri, string stateDirectory, string workspace, NativeIdentity identity)
    {
        _baseUri = baseUri;
        _originSha256 = CanonicalJson.Sha256Hex(Encoding.UTF8.GetBytes(baseUri.GetLeftPart(UriPartial.Authority).ToLowerInvariant()));
        _stateDirectory = Path.GetFullPath(stateDirectory);
        _workspace = Path.GetFullPath(workspace);
        Directory.CreateDirectory(_stateDirectory);
        Directory.CreateDirectory(_workspace);
        _identity = identity;
        _journal = new NativeJournal(_stateDirectory);
        _sourceSha = GetBuildSourceSha();
        var handler = new HttpClientHandler { AllowAutoRedirect = false, AutomaticDecompression = DecompressionMethods.None };
        _http = new HttpClient(handler) { BaseAddress = _baseUri, Timeout = TimeSpan.FromSeconds(30) };
    }

    public static NativeRelayClient Create(string relayUrl, string stateDirectory, string workspace, string keyName)
    {
        if (!OperatingSystem.IsWindows()) throw new PlatformNotSupportedException("WINDOWS_RUNTIME_REQUIRED");
        var baseUri = ValidateRelayUri(relayUrl);
        return new NativeRelayClient(baseUri, stateDirectory, workspace, NativeIdentity.OpenOrCreate(keyName));
    }

    public async Task<string> RunOnceAsync(string? enrollmentFile, CancellationToken cancellationToken = default)
    {
        var device = await EnsureDeviceAsync(enrollmentFile, cancellationToken);
        var poll = await SendSignedAsync(device.DeviceId, "/agent/poll", Array.Empty<byte>(), cancellationToken);
        var pollBytes = await poll.Content.ReadAsByteArrayAsync(cancellationToken);
        if (!poll.IsSuccessStatusCode) throw new InvalidDataException("RELAY_POLL_FAILED:" + SafeStatus(poll, pollBytes));
        using var pollDocument = JsonDocument.Parse(pollBytes);
        var root = pollDocument.RootElement;
        var state = ReadString(root, "state");
        if (state == "EMPTY")
        {
            _journal.Append("RELAY_EMPTY", "relay-poll", new string('0', 64), new { device_id = device.DeviceId, relay_origin_sha256 = _originSha256 });
            return "EMPTY";
        }
        if (state != "LEASED") throw new InvalidDataException("RELAY_POLL_STATE_INVALID");
        if (!root.TryGetProperty("task", out var taskElement) || taskElement.ValueKind != JsonValueKind.Object) throw new InvalidDataException("RELAY_TASK_MISSING");
        if (!root.TryGetProperty("lease", out var leaseElement) || leaseElement.ValueKind != JsonValueKind.Object) throw new InvalidDataException("RELAY_LEASE_MISSING");
        var relayTask = RelayTask.Parse(taskElement);
        relayTask.Validate(DateTimeOffset.UtcNow);
        var leaseToken = ReadString(leaseElement, "lease_token");
        var leaseTaskId = ReadString(leaseElement, "task_id");
        var leaseDeviceId = ReadString(leaseElement, "device_id");
        if (leaseTaskId != relayTask.TaskId || leaseDeviceId != device.DeviceId) throw new InvalidDataException("RELAY_LEASE_BINDING_MISMATCH");
        var leaseExpires = NativeTaskEnvelope.ParseUtc(ReadString(leaseElement, "expires_at"));
        if (DateTimeOffset.UtcNow >= leaseExpires) throw new InvalidDataException("RELAY_LEASE_EXPIRED");

        var receipt = ExecuteOrReplay(device, relayTask);
        var completePayload = new Dictionary<string, object?>
        {
            ["task_id"] = relayTask.TaskId,
            ["lease_token"] = leaseToken,
            ["receipt"] = receipt
        };
        var completeBody = CanonicalJson.Bytes(JsonSerializer.SerializeToElement(completePayload));
        var complete = await SendSignedAsync(device.DeviceId, "/agent/complete", completeBody, cancellationToken);
        var completeBytes = await complete.Content.ReadAsByteArrayAsync(cancellationToken);
        if (!complete.IsSuccessStatusCode) throw new InvalidDataException("RELAY_COMPLETE_FAILED:" + SafeStatus(complete, completeBytes));
        using var completeDocument = JsonDocument.Parse(completeBytes);
        if (ReadString(completeDocument.RootElement, "state") != "ACCEPTED" || ReadString(completeDocument.RootElement, "task_id") != relayTask.TaskId)
            throw new InvalidDataException("RELAY_COMPLETE_READBACK_INVALID");
        _journal.Append("RELAY_COMPLETE_ACK", relayTask.TaskId, relayTask.TaskSha256, new { device_id = device.DeviceId, receipt_sha256 = CanonicalJson.Sha256Hex(CanonicalJson.Bytes(JsonSerializer.SerializeToElement(receipt))) });
        return "COMPLETED";
    }

    private Dictionary<string, object?> ExecuteOrReplay(DeviceState device, RelayTask task)
    {
        var receiptsDirectory = Path.Combine(_stateDirectory, "relay-receipts");
        Directory.CreateDirectory(receiptsDirectory);
        var receiptPath = Path.Combine(receiptsDirectory, task.TaskId + ".json");
        if (File.Exists(receiptPath))
        {
            using var existingDocument = JsonDocument.Parse(File.ReadAllText(receiptPath, Encoding.UTF8));
            var existing = existingDocument.RootElement;
            if (ReadString(existing, "task_sha256") != task.TaskSha256) throw new InvalidDataException("RELAY_TASK_ID_COLLISION");
            VerifyEmbeddedDeviceAttestation(existing, device);
            _journal.Append("RELAY_TASK_REPLAY", task.TaskId, task.TaskSha256, new { receipt_sha256 = CanonicalJson.Sha256Hex(CanonicalJson.Bytes(existing)) });
            return JsonSerializer.Deserialize<Dictionary<string, object?>>(existing.GetRawText()) ?? throw new InvalidDataException("RELAY_RECEIPT_DESERIALIZE_FAILED");
        }

        _journal.Append("RELAY_TASK_ACCEPTED", task.TaskId, task.TaskSha256, new { task_type = task.TaskType, effect = task.Effect });
        var startedAt = UtcNow();
        Dictionary<string, object?> result;
        try
        {
            result = ExecuteRelayTask(task);
        }
        catch (Exception ex)
        {
            _journal.Append("RELAY_TASK_FAILED", task.TaskId, task.TaskSha256, new { error = ex.Message });
            throw;
        }
        var completedAt = UtcNow();
        var resultElement = JsonSerializer.SerializeToElement(result);
        var resultHash = CanonicalJson.Sha256Hex(resultElement);
        var completionHead = _journal.Append("RELAY_TASK_COMPLETED", task.TaskId, task.TaskSha256, new { result_sha256 = resultHash, state = "COMPLETED_VERIFIED_LOCAL" });
        var runner = new Dictionary<string, object?>
        {
            ["os"] = "Windows",
            ["runner_class"] = "FUSE_NATIVE_N1",
            ["device_id"] = device.DeviceId,
            ["identity_assurance"] = _identity.Assurance,
            ["cng_provider"] = _identity.ProviderName,
            ["source_sha"] = _sourceSha
        };
        var attestationPayload = new Dictionary<string, object?>
        {
            ["schema"] = "FUSE-WINDOWS-NATIVE-RELAY-ATTESTATION-V1",
            ["device_id"] = device.DeviceId,
            ["task_id"] = task.TaskId,
            ["task_sha256"] = task.TaskSha256,
            ["result_sha256"] = resultHash,
            ["source_sha"] = _sourceSha,
            ["relay_origin_sha256"] = _originSha256,
            ["journal_head_sha256"] = completionHead,
            ["completed_at"] = completedAt,
            ["public_key_spki_b64"] = _identity.PublicSpkiBase64Url
        };
        var attestationBytes = CanonicalJson.Bytes(JsonSerializer.SerializeToElement(attestationPayload));
        var deviceAttestation = new Dictionary<string, object?>
        {
            ["payload_b64"] = Base64Url.Encode(attestationBytes),
            ["payload_sha256"] = CanonicalJson.Sha256Hex(attestationBytes),
            ["signature_der_b64"] = Base64Url.Encode(_identity.Sign(attestationBytes)),
            ["public_key_spki_b64"] = _identity.PublicSpkiBase64Url
        };
        var receipt = new Dictionary<string, object?>
        {
            ["schema"] = RelayReceiptSchema,
            ["task_id"] = task.TaskId,
            ["correlation_id"] = task.CorrelationId,
            ["task_type"] = task.TaskType,
            ["state"] = "COMPLETED_VERIFIED_LOCAL",
            ["started_at"] = startedAt,
            ["completed_at"] = completedAt,
            ["runner"] = runner,
            ["task"] = task.Raw,
            ["result"] = result,
            ["task_sha256"] = task.TaskSha256,
            ["result_sha256"] = resultHash,
            ["effect"] = "READ_ONLY",
            ["truth_boundary"] = "Device-authenticated FUSE native relay execution only; no arbitrary shell, provider mutation, production promotion or market-value claim.",
            ["device_attestation"] = deviceAttestation
        };
        WriteDurable(receiptPath, Encoding.UTF8.GetString(CanonicalJson.Bytes(JsonSerializer.SerializeToElement(receipt))));
        return receipt;
    }

    private Dictionary<string, object?> ExecuteRelayTask(RelayTask task)
    {
        if (task.TaskType is "health" or "inventory")
        {
            var native = new NativeTaskEnvelope
            {
                Schema = "FUSE-WINDOWS-NATIVE-TASK-V1",
                TaskId = task.TaskId,
                CorrelationId = task.CorrelationId,
                IssuedBy = task.IssuedBy,
                TaskType = "system_status",
                IssuedAt = task.IssuedAt,
                ExpiresAt = task.ExpiresAt,
                Parameters = JsonSerializer.SerializeToElement(new Dictionary<string, object?>()),
                Effect = task.Effect,
                Raw = JsonSerializer.SerializeToElement(new Dictionary<string, object?>())
            };
            var result = NativeExecutor.Execute(native);
            result["status"] = task.TaskType == "health" ? "healthy" : "inventory_ready";
            return result;
        }
        if (task.TaskType == "heavy_sha256")
        {
            var native = new NativeTaskEnvelope
            {
                Schema = "FUSE-WINDOWS-NATIVE-TASK-V1",
                TaskId = task.TaskId,
                CorrelationId = task.CorrelationId,
                IssuedBy = task.IssuedBy,
                TaskType = "heavy_sha256",
                IssuedAt = task.IssuedAt,
                ExpiresAt = task.ExpiresAt,
                Parameters = task.Parameters,
                Effect = task.Effect,
                Raw = task.Raw
            };
            return NativeExecutor.Execute(native);
        }
        if (task.TaskType == "hash_workspace_file")
        {
            var relative = ReadString(task.Parameters, "relative_path");
            if (Path.IsPathRooted(relative) || relative.Contains('\0')) throw new InvalidDataException("RELATIVE_PATH_INVALID");
            var root = Path.GetFullPath(_workspace).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
            var target = Path.GetFullPath(Path.Combine(_workspace, relative));
            if (!target.StartsWith(root, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("WORKSPACE_ESCAPE_BLOCKED");
            var info = new FileInfo(target);
            if (!info.Exists) throw new FileNotFoundException("WORKSPACE_FILE_NOT_FOUND");
            if ((info.Attributes & FileAttributes.ReparsePoint) != 0) throw new InvalidDataException("REPARSE_POINT_BLOCKED");
            if (info.Length > 10L * 1024 * 1024 * 1024) throw new InvalidDataException("FILE_SIZE_LIMIT");
            using var stream = new FileStream(target, FileMode.Open, FileAccess.Read, FileShare.Read, 1024 * 1024, FileOptions.SequentialScan);
            var digest = Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
            return new Dictionary<string, object?>
            {
                ["status"] = "hashed",
                ["path_disclosed"] = false,
                ["name"] = info.Name,
                ["size_bytes"] = info.Length,
                ["sha256"] = digest,
                ["filesystem_usage"] = true,
                ["network_usage"] = false,
                ["shell_process_usage"] = false,
                ["external_effect"] = false
            };
        }
        throw new InvalidDataException("TASK_TYPE_NOT_ALLOWLISTED");
    }

    private async Task<DeviceState> EnsureDeviceAsync(string? enrollmentFile, CancellationToken cancellationToken)
    {
        var statePath = Path.Combine(_stateDirectory, "relay-device.json");
        if (File.Exists(statePath))
        {
            using var existingDocument = JsonDocument.Parse(File.ReadAllText(statePath, Encoding.UTF8));
            var existingRoot = existingDocument.RootElement;
            if (ReadString(existingRoot, "schema") != "FUSE-WINDOWS-NATIVE-RELAY-DEVICE-V1") throw new InvalidDataException("DEVICE_STATE_SCHEMA_INVALID");
            if (ReadString(existingRoot, "relay_origin_sha256") != _originSha256) throw new InvalidDataException("RELAY_ORIGIN_DRIFT_REENROLL_REQUIRED");
            var publicKey = ReadString(existingRoot, "public_key_spki_b64");
            if (publicKey != _identity.PublicSpkiBase64Url) throw new InvalidDataException("DEVICE_IDENTITY_DRIFT_REENROLL_REQUIRED");
            return new DeviceState(ReadString(existingRoot, "device_id"), publicKey, ReadString(existingRoot, "enrolled_at"));
        }
        if (string.IsNullOrWhiteSpace(enrollmentFile)) throw new InvalidDataException("ONE_TIME_ENROLLMENT_FILE_REQUIRED");
        var enrollmentPath = Path.GetFullPath(enrollmentFile);
        var info = new FileInfo(enrollmentPath);
        if (!info.Exists || info.Length < 8 || info.Length > 16 * 1024) throw new InvalidDataException("ENROLLMENT_FILE_INVALID");
        using var document = JsonDocument.Parse(File.ReadAllText(enrollmentPath, Encoding.UTF8));
        var root = document.RootElement;
        var allowed = new HashSet<string>(StringComparer.Ordinal) { "schema", "relay_url", "enrollment_id", "enrollment_token", "device_label" };
        foreach (var property in root.EnumerateObject()) if (!allowed.Contains(property.Name)) throw new InvalidDataException("ENROLLMENT_UNKNOWN_FIELD:" + property.Name);
        if (ReadString(root, "schema") != "FUSE-WINDOWS-NATIVE-ENROLLMENT-BOOTSTRAP-V1") throw new InvalidDataException("ENROLLMENT_SCHEMA_INVALID");
        var boundRelay = ValidateRelayUri(ReadString(root, "relay_url"));
        if (boundRelay.GetLeftPart(UriPartial.Authority) != _baseUri.GetLeftPart(UriPartial.Authority)) throw new InvalidDataException("ENROLLMENT_RELAY_MISMATCH");
        var deviceLabel = root.TryGetProperty("device_label", out var label) && label.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(label.GetString()) ? label.GetString()! : Environment.MachineName;
        var body = new Dictionary<string, object?>
        {
            ["enrollment_id"] = ReadString(root, "enrollment_id"),
            ["enrollment_token"] = ReadString(root, "enrollment_token"),
            ["device_label"] = deviceLabel,
            ["public_key_spki_b64"] = _identity.PublicSpkiBase64Url
        };
        var response = await PostUnsignedAsync("/agent/enroll", CanonicalJson.Bytes(JsonSerializer.SerializeToElement(body)), cancellationToken);
        var bytes = await response.Content.ReadAsByteArrayAsync(cancellationToken);
        if (response.StatusCode != HttpStatusCode.Created) throw new InvalidDataException("RELAY_ENROLL_FAILED:" + SafeStatus(response, bytes));
        using var responseDocument = JsonDocument.Parse(bytes);
        var responseRoot = responseDocument.RootElement;
        if (ReadString(responseRoot, "schema") != "FUSE-WINDOWS-DEVICE-CREDENTIAL-V2") throw new InvalidDataException("DEVICE_CREDENTIAL_SCHEMA_INVALID");
        if (ReadString(responseRoot, "public_key_spki_b64") != _identity.PublicSpkiBase64Url) throw new InvalidDataException("ENROLLED_PUBLIC_KEY_MISMATCH");
        var device = new DeviceState(ReadString(responseRoot, "device_id"), _identity.PublicSpkiBase64Url, ReadString(responseRoot, "enrolled_at"));
        var state = new Dictionary<string, object?>
        {
            ["schema"] = "FUSE-WINDOWS-NATIVE-RELAY-DEVICE-V1",
            ["device_id"] = device.DeviceId,
            ["public_key_spki_b64"] = device.PublicKeySpkiB64,
            ["enrolled_at"] = device.EnrolledAt,
            ["relay_origin_sha256"] = _originSha256,
            ["identity_assurance"] = _identity.Assurance,
            ["cng_provider"] = _identity.ProviderName,
            ["source_sha"] = _sourceSha
        };
        WriteDurable(statePath, Encoding.UTF8.GetString(CanonicalJson.Bytes(JsonSerializer.SerializeToElement(state))));
        File.Delete(enrollmentPath);
        _journal.Append("RELAY_ENROLLED", "device-enrollment", new string('0', 64), new { device_id = device.DeviceId, relay_origin_sha256 = _originSha256, identity_assurance = _identity.Assurance });
        return device;
    }

    private async Task<HttpResponseMessage> PostUnsignedAsync(string path, byte[] body, CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, path);
        request.Content = new ByteArrayContent(body);
        request.Content.Headers.ContentType = new MediaTypeHeaderValue("application/json");
        var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        RejectRedirect(response);
        return response;
    }

    private async Task<HttpResponseMessage> SendSignedAsync(string deviceId, string path, byte[] body, CancellationToken cancellationToken)
    {
        var timestamp = UtcNow();
        var nonce = "nonce-" + Guid.NewGuid().ToString("N");
        var signingPayload = BuildSigningPayload("POST", path, timestamp, nonce, body);
        var signature = Base64Url.Encode(_identity.Sign(signingPayload));
        using var request = new HttpRequestMessage(HttpMethod.Post, path);
        request.Headers.TryAddWithoutValidation("x-fuse-device-id", deviceId);
        request.Headers.TryAddWithoutValidation("x-fuse-timestamp", timestamp);
        request.Headers.TryAddWithoutValidation("x-fuse-nonce", nonce);
        request.Headers.TryAddWithoutValidation("x-fuse-signature", signature);
        request.Content = new ByteArrayContent(body);
        request.Content.Headers.ContentType = new MediaTypeHeaderValue("application/json");
        var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        RejectRedirect(response);
        return response;
    }

    private static byte[] BuildSigningPayload(string method, string path, string timestamp, string nonce, byte[] body)
    {
        return Encoding.UTF8.GetBytes(string.Join("\n", method.ToUpperInvariant(), path, timestamp, nonce, CanonicalJson.Sha256Hex(body)));
    }

    private void VerifyEmbeddedDeviceAttestation(JsonElement receipt, DeviceState device)
    {
        if (!receipt.TryGetProperty("device_attestation", out var attestation) || attestation.ValueKind != JsonValueKind.Object) throw new InvalidDataException("DEVICE_ATTESTATION_MISSING");
        if (ReadString(attestation, "public_key_spki_b64") != device.PublicKeySpkiB64) throw new InvalidDataException("DEVICE_ATTESTATION_KEY_MISMATCH");
        var payload = Base64Url.Decode(ReadString(attestation, "payload_b64"));
        if (CanonicalJson.Sha256Hex(payload) != ReadString(attestation, "payload_sha256")) throw new InvalidDataException("DEVICE_ATTESTATION_PAYLOAD_HASH_INVALID");
        if (!_identity.Verify(payload, Base64Url.Decode(ReadString(attestation, "signature_der_b64")))) throw new InvalidDataException("DEVICE_ATTESTATION_SIGNATURE_INVALID");
        using var document = JsonDocument.Parse(payload);
        if (ReadString(document.RootElement, "device_id") != device.DeviceId) throw new InvalidDataException("DEVICE_ATTESTATION_DEVICE_MISMATCH");
        if (ReadString(document.RootElement, "task_sha256") != ReadString(receipt, "task_sha256")) throw new InvalidDataException("DEVICE_ATTESTATION_TASK_HASH_MISMATCH");
        if (ReadString(document.RootElement, "result_sha256") != ReadString(receipt, "result_sha256")) throw new InvalidDataException("DEVICE_ATTESTATION_RESULT_HASH_MISMATCH");
    }

    public static string GetBuildSourceSha()
    {
        var env = Environment.GetEnvironmentVariable("FEDERATION_SOURCE_SHA");
        if (!string.IsNullOrWhiteSpace(env) && env.Length == 40 && env.All(Uri.IsHexDigit)) return env.ToLowerInvariant();
        var metadata = Assembly.GetExecutingAssembly().GetCustomAttributes<AssemblyMetadataAttribute>().FirstOrDefault(x => x.Key == "FederationSourceSha")?.Value;
        return !string.IsNullOrWhiteSpace(metadata) ? metadata : "UNBOUND_SOURCE";
    }

    private static Uri ValidateRelayUri(string value)
    {
        if (!Uri.TryCreate(value.TrimEnd('/') + "/", UriKind.Absolute, out var uri)) throw new InvalidDataException("RELAY_URL_INVALID");
        if (!string.IsNullOrEmpty(uri.UserInfo) || !string.IsNullOrEmpty(uri.Query) || !string.IsNullOrEmpty(uri.Fragment)) throw new InvalidDataException("RELAY_URL_COMPONENT_INVALID");
        if (uri.Scheme == Uri.UriSchemeHttps) return uri;
        var loopbackTest = Environment.GetEnvironmentVariable("FUSE_TEST_ALLOW_LOOPBACK_HTTP") == "1" && uri.Scheme == Uri.UriSchemeHttp && (uri.IsLoopback || uri.Host == "localhost");
        if (!loopbackTest) throw new InvalidDataException("RELAY_HTTPS_REQUIRED");
        return uri;
    }

    private static void RejectRedirect(HttpResponseMessage response)
    {
        var status = (int)response.StatusCode;
        if (status is >= 300 and < 400) throw new InvalidDataException("RELAY_REDIRECT_FORBIDDEN");
    }

    private static string SafeStatus(HttpResponseMessage response, byte[] body)
    {
        var value = Encoding.UTF8.GetString(body);
        if (value.Length > 512) value = value[..512];
        return ((int)response.StatusCode).ToString(CultureInfo.InvariantCulture) + ":" + value;
    }

    private static string ReadString(JsonElement obj, string name)
    {
        if (!obj.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.String || string.IsNullOrWhiteSpace(value.GetString())) throw new InvalidDataException("STRING_FIELD_INVALID:" + name);
        return value.GetString()!;
    }

    private static void WriteDurable(string path, string content)
    {
        var fullPath = Path.GetFullPath(path);
        Directory.CreateDirectory(Path.GetDirectoryName(fullPath)!);
        var temp = fullPath + ".tmp-" + Guid.NewGuid().ToString("N");
        var bytes = Encoding.UTF8.GetBytes(content);
        using (var stream = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None, 4096, FileOptions.WriteThrough))
        {
            stream.Write(bytes, 0, bytes.Length);
            stream.Flush(flushToDisk: true);
        }
        File.Move(temp, fullPath, overwrite: true);
    }

    private static string UtcNow() => DateTimeOffset.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fffffff'Z'", CultureInfo.InvariantCulture);

    public void Dispose()
    {
        _http.Dispose();
        _identity.Dispose();
    }

    private sealed record DeviceState(string DeviceId, string PublicKeySpkiB64, string EnrolledAt);

    private sealed class RelayTask
    {
        private static readonly HashSet<string> Expected = new(StringComparer.Ordinal)
        {
            "schema", "task_id", "correlation_id", "issued_by", "task_type", "issued_at", "expires_at", "parameters", "effect"
        };
        private static readonly HashSet<string> AllowedTypes = new(StringComparer.Ordinal)
        {
            "health", "inventory", "hash_workspace_file", "heavy_sha256"
        };

        public required string Schema { get; init; }
        public required string TaskId { get; init; }
        public required string CorrelationId { get; init; }
        public required string IssuedBy { get; init; }
        public required string TaskType { get; init; }
        public required string IssuedAt { get; init; }
        public required string ExpiresAt { get; init; }
        public required JsonElement Parameters { get; init; }
        public required string Effect { get; init; }
        public required JsonElement Raw { get; init; }
        public string TaskSha256 => CanonicalJson.Sha256Hex(Raw);

        public static RelayTask Parse(JsonElement root)
        {
            var names = root.EnumerateObject().Select(p => p.Name).ToArray();
            var unknown = names.Where(n => !Expected.Contains(n)).OrderBy(n => n, StringComparer.Ordinal).ToArray();
            if (unknown.Length > 0) throw new InvalidDataException("UNKNOWN_TASK_FIELDS:" + string.Join(',', unknown));
            var missing = Expected.Where(n => !root.TryGetProperty(n, out _)).OrderBy(n => n, StringComparer.Ordinal).ToArray();
            if (missing.Length > 0) throw new InvalidDataException("TASK_FIELDS_MISSING:" + string.Join(',', missing));
            return new RelayTask
            {
                Schema = ReadString(root, "schema"),
                TaskId = ReadString(root, "task_id"),
                CorrelationId = ReadString(root, "correlation_id"),
                IssuedBy = ReadString(root, "issued_by"),
                TaskType = ReadString(root, "task_type"),
                IssuedAt = ReadString(root, "issued_at"),
                ExpiresAt = ReadString(root, "expires_at"),
                Parameters = root.GetProperty("parameters").Clone(),
                Effect = ReadString(root, "effect"),
                Raw = root.Clone()
            };
        }

        public void Validate(DateTimeOffset now)
        {
            if (Schema != RelayTaskSchema) throw new InvalidDataException("TASK_SCHEMA_INVALID");
            if (IssuedBy != "FUSE/FDOF") throw new InvalidDataException("TASK_ISSUER_INVALID");
            if (!AllowedTypes.Contains(TaskType)) throw new InvalidDataException("TASK_TYPE_NOT_ALLOWLISTED");
            if (Effect != "READ_ONLY") throw new InvalidDataException("TASK_EFFECT_NOT_AUTHORIZED");
            if (Parameters.ValueKind != JsonValueKind.Object) throw new InvalidDataException("TASK_PARAMETERS_OBJECT_REQUIRED");
            var issued = NativeTaskEnvelope.ParseUtc(IssuedAt);
            var expires = NativeTaskEnvelope.ParseUtc(ExpiresAt);
            if (expires <= issued || (expires - issued).TotalSeconds > 900) throw new InvalidDataException("TASK_TIME_WINDOW_INVALID");
            if (now >= expires) throw new InvalidDataException("TASK_EXPIRED");
            if (issued > now.AddSeconds(5)) throw new InvalidDataException("TASK_NOT_YET_VALID");
            if (TaskType is "health" or "inventory")
            {
                if (Parameters.EnumerateObject().Any()) throw new InvalidDataException("TASK_PARAMETERS_MUST_BE_EMPTY");
            }
            else if (TaskType == "hash_workspace_file")
            {
                var names = Parameters.EnumerateObject().Select(p => p.Name).ToArray();
                if (names.Length != 1 || names[0] != "relative_path") throw new InvalidDataException("HASH_PARAMETERS_INVALID");
                _ = ReadString(Parameters, "relative_path");
            }
            else
            {
                var native = new NativeTaskEnvelope
                {
                    Schema = "FUSE-WINDOWS-NATIVE-TASK-V1",
                    TaskId = TaskId,
                    CorrelationId = CorrelationId,
                    IssuedBy = IssuedBy,
                    TaskType = "heavy_sha256",
                    IssuedAt = IssuedAt,
                    ExpiresAt = ExpiresAt,
                    Parameters = Parameters,
                    Effect = Effect,
                    Raw = Raw
                };
                native.Validate(now);
            }
        }
    }
}
