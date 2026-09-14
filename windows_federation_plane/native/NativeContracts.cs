using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Fuse.Windows.Native;

internal static class CanonicalJson
{
    public static byte[] Bytes(JsonElement value)
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream, new JsonWriterOptions { Indented = false }))
        {
            Write(writer, value);
        }
        return stream.ToArray();
    }

    public static string Sha256Hex(JsonElement value) => Convert.ToHexStringLower(SHA256.HashData(Bytes(value)));

    public static string Sha256Hex(byte[] value) => Convert.ToHexStringLower(SHA256.HashData(value));

    private static void Write(Utf8JsonWriter writer, JsonElement value)
    {
        switch (value.ValueKind)
        {
            case JsonValueKind.Object:
                writer.WriteStartObject();
                foreach (var property in value.EnumerateObject().OrderBy(p => p.Name, StringComparer.Ordinal))
                {
                    writer.WritePropertyName(property.Name);
                    Write(writer, property.Value);
                }
                writer.WriteEndObject();
                break;
            case JsonValueKind.Array:
                writer.WriteStartArray();
                foreach (var item in value.EnumerateArray()) Write(writer, item);
                writer.WriteEndArray();
                break;
            case JsonValueKind.String:
                writer.WriteStringValue(value.GetString());
                break;
            case JsonValueKind.Number:
                writer.WriteRawValue(value.GetRawText(), skipInputValidation: false);
                break;
            case JsonValueKind.True:
                writer.WriteBooleanValue(true);
                break;
            case JsonValueKind.False:
                writer.WriteBooleanValue(false);
                break;
            case JsonValueKind.Null:
                writer.WriteNullValue();
                break;
            default:
                throw new InvalidDataException("CANONICAL_JSON_KIND_UNSUPPORTED");
        }
    }
}

internal sealed class NativeTaskEnvelope
{
    private static readonly Regex IdPattern = new("^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$", RegexOptions.CultureInvariant);
    private static readonly HashSet<string> ExpectedFields = new(StringComparer.Ordinal)
    {
        "schema", "task_id", "correlation_id", "issued_by", "task_type",
        "issued_at", "expires_at", "parameters", "effect"
    };
    private static readonly HashSet<string> AllowedTaskTypes = new(StringComparer.Ordinal)
    {
        "system_status", "heavy_sha256"
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

    public static NativeTaskEnvelope Parse(string json)
    {
        using var document = JsonDocument.Parse(json, new JsonDocumentOptions
        {
            AllowTrailingCommas = false,
            CommentHandling = JsonCommentHandling.Disallow,
            MaxDepth = 16
        });
        if (document.RootElement.ValueKind != JsonValueKind.Object) throw new InvalidDataException("ENVELOPE_OBJECT_REQUIRED");
        var root = document.RootElement;
        var names = root.EnumerateObject().Select(p => p.Name).ToArray();
        var unknown = names.Where(n => !ExpectedFields.Contains(n)).OrderBy(n => n, StringComparer.Ordinal).ToArray();
        if (unknown.Length > 0) throw new InvalidDataException("UNKNOWN_ENVELOPE_FIELDS:" + string.Join(',', unknown));
        var missing = ExpectedFields.Where(n => !root.TryGetProperty(n, out _)).OrderBy(n => n, StringComparer.Ordinal).ToArray();
        if (missing.Length > 0) throw new InvalidDataException("MISSING_ENVELOPE_FIELDS:" + string.Join(',', missing));

        var envelope = new NativeTaskEnvelope
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
        return envelope;
    }

    public void Validate(DateTimeOffset now)
    {
        if (Schema != "FUSE-WINDOWS-NATIVE-TASK-V1") throw new InvalidDataException("UNSUPPORTED_TASK_SCHEMA");
        if (!IdPattern.IsMatch(TaskId)) throw new InvalidDataException("TASK_ID_INVALID");
        if (!IdPattern.IsMatch(CorrelationId)) throw new InvalidDataException("CORRELATION_ID_INVALID");
        if (IssuedBy != "FUSE/FDOF") throw new InvalidDataException("UNTRUSTED_TASK_ISSUER");
        if (!AllowedTaskTypes.Contains(TaskType)) throw new InvalidDataException("TASK_TYPE_NOT_ALLOWLISTED");
        if (Effect != "READ_ONLY") throw new InvalidDataException("EFFECT_NOT_AUTHORIZED");
        if (Parameters.ValueKind != JsonValueKind.Object) throw new InvalidDataException("PARAMETERS_OBJECT_REQUIRED");
        var issued = ParseUtc(IssuedAt);
        var expires = ParseUtc(ExpiresAt);
        if (expires <= issued) throw new InvalidDataException("INVALID_TASK_TIME_WINDOW");
        if (now > expires) throw new InvalidDataException("TASK_EXPIRED");
        if (issued > now.AddSeconds(5)) throw new InvalidDataException("TASK_NOT_YET_VALID");
        if ((expires - issued).TotalSeconds > 900) throw new InvalidDataException("TASK_TTL_EXCEEDS_900_SECONDS");
        ValidateParameters();
    }

    private void ValidateParameters()
    {
        if (TaskType == "system_status")
        {
            if (Parameters.EnumerateObject().Any()) throw new InvalidDataException("SYSTEM_STATUS_PARAMETERS_MUST_BE_EMPTY");
            return;
        }

        var expected = new HashSet<string>(StringComparer.Ordinal)
        {
            "bytes_per_round", "rounds", "requested_workers", "requested_memory_mb", "max_seconds", "seed_hex"
        };
        var names = Parameters.EnumerateObject().Select(p => p.Name).ToArray();
        var unknown = names.Where(n => !expected.Contains(n)).OrderBy(n => n, StringComparer.Ordinal).ToArray();
        if (unknown.Length > 0) throw new InvalidDataException("UNKNOWN_HEAVY_PARAMETERS:" + string.Join(',', unknown));
        var missing = expected.Where(n => !Parameters.TryGetProperty(n, out _)).OrderBy(n => n, StringComparer.Ordinal).ToArray();
        if (missing.Length > 0) throw new InvalidDataException("MISSING_HEAVY_PARAMETERS:" + string.Join(',', missing));

        var bytesPerRound = ReadInt64(Parameters, "bytes_per_round");
        var rounds = ReadInt32(Parameters, "rounds");
        var workers = ReadInt32(Parameters, "requested_workers");
        var memoryMb = ReadInt32(Parameters, "requested_memory_mb");
        var maxSeconds = ReadInt32(Parameters, "max_seconds");
        var seed = ReadString(Parameters, "seed_hex");
        if (bytesPerRound < 1 || bytesPerRound > 64L * 1024 * 1024) throw new InvalidDataException("BYTES_PER_ROUND_OUT_OF_RANGE");
        if (rounds < 1 || rounds > 64) throw new InvalidDataException("ROUNDS_OUT_OF_RANGE");
        if (checked(bytesPerRound * rounds) > 2L * 1024 * 1024 * 1024) throw new InvalidDataException("TOTAL_BYTES_EXCEEDS_2_GIB");
        if (workers < 1 || workers > 16) throw new InvalidDataException("REQUESTED_WORKERS_OUT_OF_RANGE");
        if (memoryMb < 64 || memoryMb > 1024) throw new InvalidDataException("REQUESTED_MEMORY_MB_OUT_OF_RANGE");
        if (maxSeconds < 1 || maxSeconds > 300) throw new InvalidDataException("MAX_SECONDS_OUT_OF_RANGE");
        if (!Regex.IsMatch(seed, "^[0-9a-fA-F]{64}$", RegexOptions.CultureInvariant)) throw new InvalidDataException("SEED_HEX_INVALID");
    }

    public static DateTimeOffset ParseUtc(string value)
    {
        if (!value.EndsWith('Z')) throw new InvalidDataException("TIMESTAMP_MUST_BE_UTC_Z");
        if (!DateTimeOffset.TryParse(value, System.Globalization.CultureInfo.InvariantCulture,
            System.Globalization.DateTimeStyles.AssumeUniversal | System.Globalization.DateTimeStyles.AdjustToUniversal,
            out var result)) throw new InvalidDataException("TIMESTAMP_INVALID");
        return result;
    }

    public static string ReadString(JsonElement obj, string name)
    {
        if (!obj.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.String || string.IsNullOrEmpty(value.GetString()))
            throw new InvalidDataException("STRING_FIELD_INVALID:" + name);
        return value.GetString()!;
    }

    public static int ReadInt32(JsonElement obj, string name)
    {
        if (!obj.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.Number || !value.TryGetInt32(out var result))
            throw new InvalidDataException("INTEGER_FIELD_INVALID:" + name);
        return result;
    }

    public static long ReadInt64(JsonElement obj, string name)
    {
        if (!obj.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.Number || !value.TryGetInt64(out var result))
            throw new InvalidDataException("INTEGER_FIELD_INVALID:" + name);
        return result;
    }
}

internal static class Base64Url
{
    public static string Encode(byte[] bytes) => Convert.ToBase64String(bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_');
}
