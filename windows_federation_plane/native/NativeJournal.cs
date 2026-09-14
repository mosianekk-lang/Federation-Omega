using System.Text;
using System.Text.Json;

namespace Fuse.Windows.Native;

internal sealed class NativeJournal
{
    private readonly string _path;
    private long _sequence;
    private string _head = new('0', 64);
    private readonly List<string> _hashes = new();

    public NativeJournal(string stateDirectory)
    {
        Directory.CreateDirectory(stateDirectory);
        _path = Path.Combine(stateDirectory, "native-journal.jsonl");
        VerifyExisting();
    }

    public long Sequence => _sequence;
    public string HeadHash => _head;
    public IReadOnlyList<string> EntryHashes => _hashes;

    public string Append(string kind, string taskId, string taskSha256, object? data = null)
    {
        var body = new Dictionary<string, object?>
        {
            ["sequence"] = _sequence + 1,
            ["previous_hash"] = _head,
            ["kind"] = kind,
            ["task_id"] = taskId,
            ["task_sha256"] = taskSha256,
            ["observed_at"] = DateTimeOffset.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fffffff'Z'", System.Globalization.CultureInfo.InvariantCulture),
            ["data"] = data ?? new Dictionary<string, object?>()
        };
        var bodyElement = JsonSerializer.SerializeToElement(body);
        var hash = CanonicalJson.Sha256Hex(bodyElement);
        var full = new Dictionary<string, object?>(body, StringComparer.Ordinal)
        {
            ["entry_hash"] = hash
        };
        var fullElement = JsonSerializer.SerializeToElement(full);
        var line = Encoding.UTF8.GetString(CanonicalJson.Bytes(fullElement)) + "\n";
        var bytes = Encoding.UTF8.GetBytes(line);
        using (var stream = new FileStream(_path, FileMode.Append, FileAccess.Write, FileShare.Read,
            bufferSize: 4096, options: FileOptions.WriteThrough))
        {
            stream.Write(bytes, 0, bytes.Length);
            stream.Flush(flushToDisk: true);
        }
        _sequence++;
        _head = hash;
        _hashes.Add(hash);
        return hash;
    }

    private void VerifyExisting()
    {
        if (!File.Exists(_path)) return;
        var expectedSequence = 1L;
        var previous = new string('0', 64);
        foreach (var rawLine in File.ReadLines(_path, Encoding.UTF8))
        {
            if (string.IsNullOrWhiteSpace(rawLine)) continue;
            JsonElement root;
            try
            {
                using var document = JsonDocument.Parse(rawLine);
                root = document.RootElement.Clone();
            }
            catch (JsonException ex)
            {
                throw new InvalidDataException("JOURNAL_JSON_INVALID", ex);
            }
            if (root.ValueKind != JsonValueKind.Object) throw new InvalidDataException("JOURNAL_ENTRY_OBJECT_REQUIRED");
            var allowed = new HashSet<string>(StringComparer.Ordinal)
            {
                "sequence", "previous_hash", "kind", "task_id", "task_sha256", "observed_at", "data", "entry_hash"
            };
            foreach (var property in root.EnumerateObject())
                if (!allowed.Contains(property.Name)) throw new InvalidDataException("JOURNAL_UNKNOWN_FIELD:" + property.Name);
            foreach (var field in allowed)
                if (!root.TryGetProperty(field, out _)) throw new InvalidDataException("JOURNAL_FIELD_MISSING:" + field);
            if (!root.GetProperty("sequence").TryGetInt64(out var sequence) || sequence != expectedSequence)
                throw new InvalidDataException("JOURNAL_SEQUENCE_INVALID");
            if (root.GetProperty("previous_hash").GetString() != previous)
                throw new InvalidDataException("JOURNAL_PREDECESSOR_INVALID");
            var entryHash = root.GetProperty("entry_hash").GetString();
            if (entryHash is null || entryHash.Length != 64) throw new InvalidDataException("JOURNAL_HASH_INVALID");
            var body = new Dictionary<string, object?>
            {
                ["sequence"] = sequence,
                ["previous_hash"] = previous,
                ["kind"] = root.GetProperty("kind").GetString(),
                ["task_id"] = root.GetProperty("task_id").GetString(),
                ["task_sha256"] = root.GetProperty("task_sha256").GetString(),
                ["observed_at"] = root.GetProperty("observed_at").GetString(),
                ["data"] = root.GetProperty("data").Clone()
            };
            var calculated = CanonicalJson.Sha256Hex(JsonSerializer.SerializeToElement(body));
            if (!string.Equals(calculated, entryHash, StringComparison.Ordinal))
                throw new InvalidDataException("JOURNAL_DIGEST_INVALID");
            _hashes.Add(entryHash);
            previous = entryHash;
            expectedSequence++;
        }
        _sequence = expectedSequence - 1;
        _head = previous;
    }
}
