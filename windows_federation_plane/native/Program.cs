using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Fuse.Windows.Native;

internal static class Program
{
    private const string ReceiptSchema = "FUSE-WINDOWS-NATIVE-RESULT-ATTESTATION-V1";
    private const string TruthBoundary = "This attestation proves only the exact bounded native task on the identified Windows host under the bound source epoch. It does not prove production deployment, broader provider authority, or owner-value superiority.";

    public static async Task<int> Main(string[] args)
    {
        try
        {
            if (!OperatingSystem.IsWindows()) throw new PlatformNotSupportedException("WINDOWS_RUNTIME_REQUIRED");
            var options = ParseArgs(args);
            return options.Command switch
            {
                "execute" => ExecuteLocal(options.Values),
                "agent-once" => await RunAgentAsync(options.Values, loop: false),
                "agent-loop" => await RunAgentAsync(options.Values, loop: true),
                _ => throw new InvalidDataException("COMMAND_NOT_ALLOWLISTED")
            };
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine(ex.Message);
            return 2;
        }
    }

    private static int ExecuteLocal(Dictionary<string, string> values)
    {
        var taskPath = Required(values, "task-json");
        var stateDir = Required(values, "state-dir");
        var keyName = values.GetValueOrDefault("key-name") ?? NativeIdentity.DefaultKeyName;
        var receiptOut = values.GetValueOrDefault("receipt-out");

        var journal = new NativeJournal(stateDir);
        var task = NativeTaskEnvelope.Parse(File.ReadAllText(taskPath, Encoding.UTF8));
        task.Validate(DateTimeOffset.UtcNow);
        var taskHash = task.TaskSha256;
        var receiptsDir = Path.Combine(stateDir, "receipts");
        Directory.CreateDirectory(receiptsDir);
        var storedReceiptPath = Path.Combine(receiptsDir, task.TaskId + ".json");

        using var identity = NativeIdentity.OpenOrCreate(keyName);
        if (File.Exists(storedReceiptPath))
        {
            var existing = File.ReadAllText(storedReceiptPath, Encoding.UTF8);
            using var document = JsonDocument.Parse(existing);
            var storedHash = NativeTaskEnvelope.ReadString(document.RootElement, "task_sha256");
            if (!string.Equals(storedHash, taskHash, StringComparison.Ordinal))
            {
                journal.Append("REJECTED_COLLISION", task.TaskId, taskHash, new { stored_task_sha256 = storedHash });
                throw new InvalidDataException("TASK_ID_COLLISION");
            }
            VerifyStoredReceipt(document.RootElement, identity, taskHash, journal);
            journal.Append("REPLAY", task.TaskId, taskHash, new { receipt_sha256 = CanonicalJson.Sha256Hex(Encoding.UTF8.GetBytes(existing)) });
            if (!string.IsNullOrEmpty(receiptOut)) WriteDurable(receiptOut, existing);
            Console.Out.WriteLine(existing);
            return 0;
        }

        journal.Append("ACCEPTED", task.TaskId, taskHash, new { task_type = task.TaskType, effect = task.Effect });
        var startedAt = UtcNow();
        Dictionary<string, object?> result;
        try
        {
            result = NativeExecutor.Execute(task);
        }
        catch (Exception ex)
        {
            journal.Append("FAILED", task.TaskId, taskHash, new { error = ex.Message });
            throw;
        }
        var completedAt = UtcNow();
        var resultElement = JsonSerializer.SerializeToElement(result);
        var resultHash = CanonicalJson.Sha256Hex(resultElement);
        var completionHead = journal.Append("COMPLETED", task.TaskId, taskHash, new { result_sha256 = resultHash, state = "COMPLETED_VERIFIED_NATIVE" });
        var sourceSha = NativeRelayClient.GetBuildSourceSha();
        if (sourceSha != "UNBOUND_SOURCE" && !Regex.IsMatch(sourceSha, "^[0-9a-fA-F]{40}$", RegexOptions.CultureInvariant))
            throw new InvalidDataException("SOURCE_SHA_INVALID");

        var runner = new Dictionary<string, object?>
        {
            ["machine_name"] = Environment.MachineName,
            ["os_description"] = RuntimeInformation.OSDescription,
            ["os_architecture"] = RuntimeInformation.OSArchitecture.ToString(),
            ["process_architecture"] = RuntimeInformation.ProcessArchitecture.ToString(),
            ["logical_cores"] = Environment.ProcessorCount,
            ["process_id"] = Environment.ProcessId,
            ["runtime"] = RuntimeInformation.FrameworkDescription,
            ["identity_assurance"] = identity.Assurance,
            ["cng_provider"] = identity.ProviderName
        };
        var safety = new Dictionary<string, object?>
        {
            ["persistent_current_user_cng"] = true,
            ["accepted_before_execute"] = true,
            ["journal_hash_chain"] = true,
            ["read_only_effect_ceiling"] = true,
            ["network_usage"] = false,
            ["shell_process_usage"] = false,
            ["provider_mutation"] = false,
            ["secret_access"] = false,
            ["external_effect"] = false
        };
        var runnerHash = CanonicalJson.Sha256Hex(JsonSerializer.SerializeToElement(runner));
        var safetyHash = CanonicalJson.Sha256Hex(JsonSerializer.SerializeToElement(safety));
        var truthHash = CanonicalJson.Sha256Hex(Encoding.UTF8.GetBytes(TruthBoundary));
        var publicKey = identity.PublicSpkiBase64Url;
        var signedPayload = new Dictionary<string, object?>
        {
            ["schema"] = ReceiptSchema,
            ["task_id"] = task.TaskId,
            ["correlation_id"] = task.CorrelationId,
            ["task_type"] = task.TaskType,
            ["state"] = "COMPLETED_VERIFIED_NATIVE",
            ["started_at"] = startedAt,
            ["completed_at"] = completedAt,
            ["source_sha"] = sourceSha.ToLowerInvariant(),
            ["task_sha256"] = taskHash,
            ["result_sha256"] = resultHash,
            ["runner_sha256"] = runnerHash,
            ["safety_sha256"] = safetyHash,
            ["truth_boundary_sha256"] = truthHash,
            ["journal_head_sha256"] = completionHead,
            ["public_key_spki_b64"] = publicKey
        };
        var signedBytes = CanonicalJson.Bytes(JsonSerializer.SerializeToElement(signedPayload));
        var signature = identity.Sign(signedBytes);
        var receipt = new Dictionary<string, object?>(signedPayload, StringComparer.Ordinal)
        {
            ["runner"] = runner,
            ["result"] = result,
            ["safety"] = safety,
            ["signed_payload_b64"] = Base64Url.Encode(signedBytes),
            ["signature_der_b64"] = Base64Url.Encode(signature),
            ["truth_boundary"] = TruthBoundary
        };
        var receiptBytes = CanonicalJson.Bytes(JsonSerializer.SerializeToElement(receipt));
        var receiptJson = Encoding.UTF8.GetString(receiptBytes);
        WriteDurable(storedReceiptPath, receiptJson);
        if (!string.IsNullOrEmpty(receiptOut)) WriteDurable(receiptOut, receiptJson);
        Console.Out.WriteLine(receiptJson);
        return 0;
    }

    private static async Task<int> RunAgentAsync(Dictionary<string, string> values, bool loop)
    {
        var relayUrl = Required(values, "relay-url");
        var stateDir = Required(values, "state-dir");
        var workspace = Required(values, "workspace");
        var keyName = values.GetValueOrDefault("key-name") ?? NativeIdentity.DefaultKeyName;
        var enrollmentFile = values.GetValueOrDefault("enrollment-file");
        var pollSeconds = ParsePollSeconds(values.GetValueOrDefault("poll-seconds"));
        using var client = NativeRelayClient.Create(relayUrl, stateDir, workspace, keyName);
        if (!loop)
        {
            Console.Out.WriteLine(await client.RunOnceAsync(enrollmentFile));
            return 0;
        }

        using var cts = new CancellationTokenSource();
        Console.CancelKeyPress += (_, eventArgs) =>
        {
            eventArgs.Cancel = true;
            cts.Cancel();
        };
        var backoffSeconds = pollSeconds;
        var firstEnrollmentFile = enrollmentFile;
        while (!cts.IsCancellationRequested)
        {
            try
            {
                var state = await client.RunOnceAsync(firstEnrollmentFile, cts.Token);
                firstEnrollmentFile = null;
                backoffSeconds = pollSeconds;
                Console.Out.WriteLine(state);
                await Task.Delay(TimeSpan.FromSeconds(pollSeconds), cts.Token);
            }
            catch (OperationCanceledException) when (cts.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("AGENT_RETRY:" + ex.Message);
                await Task.Delay(TimeSpan.FromSeconds(backoffSeconds), cts.Token);
                backoffSeconds = Math.Min(30d, Math.Max(pollSeconds, backoffSeconds * 2d));
            }
        }
        return 0;
    }

    private static double ParsePollSeconds(string? value)
    {
        if (string.IsNullOrWhiteSpace(value)) return 5d;
        if (!double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var parsed) || parsed < 1d || parsed > 300d)
            throw new InvalidDataException("POLL_SECONDS_OUT_OF_RANGE");
        return parsed;
    }

    private static void VerifyStoredReceipt(JsonElement receipt, NativeIdentity identity, string expectedTaskHash, NativeJournal journal)
    {
        if (NativeTaskEnvelope.ReadString(receipt, "schema") != ReceiptSchema) throw new InvalidDataException("STORED_RECEIPT_SCHEMA_INVALID");
        if (NativeTaskEnvelope.ReadString(receipt, "task_sha256") != expectedTaskHash) throw new InvalidDataException("STORED_RECEIPT_TASK_HASH_INVALID");
        if (NativeTaskEnvelope.ReadString(receipt, "public_key_spki_b64") != identity.PublicSpkiBase64Url) throw new InvalidDataException("STORED_RECEIPT_IDENTITY_MISMATCH");
        var result = receipt.GetProperty("result");
        var runner = receipt.GetProperty("runner");
        var safety = receipt.GetProperty("safety");
        if (CanonicalJson.Sha256Hex(result) != NativeTaskEnvelope.ReadString(receipt, "result_sha256")) throw new InvalidDataException("STORED_RESULT_HASH_INVALID");
        if (CanonicalJson.Sha256Hex(runner) != NativeTaskEnvelope.ReadString(receipt, "runner_sha256")) throw new InvalidDataException("STORED_RUNNER_HASH_INVALID");
        if (CanonicalJson.Sha256Hex(safety) != NativeTaskEnvelope.ReadString(receipt, "safety_sha256")) throw new InvalidDataException("STORED_SAFETY_HASH_INVALID");
        var truth = NativeTaskEnvelope.ReadString(receipt, "truth_boundary");
        if (CanonicalJson.Sha256Hex(Encoding.UTF8.GetBytes(truth)) != NativeTaskEnvelope.ReadString(receipt, "truth_boundary_sha256")) throw new InvalidDataException("STORED_TRUTH_HASH_INVALID");
        var signedBytes = Base64Url.Decode(NativeTaskEnvelope.ReadString(receipt, "signed_payload_b64"));
        var signature = Base64Url.Decode(NativeTaskEnvelope.ReadString(receipt, "signature_der_b64"));
        if (!identity.Verify(signedBytes, signature)) throw new InvalidDataException("STORED_RECEIPT_SIGNATURE_INVALID");
        using var signedDocument = JsonDocument.Parse(signedBytes);
        foreach (var field in new[] { "schema", "task_id", "correlation_id", "task_type", "state", "started_at", "completed_at", "source_sha", "task_sha256", "result_sha256", "runner_sha256", "safety_sha256", "truth_boundary_sha256", "journal_head_sha256", "public_key_spki_b64" })
        {
            if (!receipt.TryGetProperty(field, out var outer) || !signedDocument.RootElement.TryGetProperty(field, out var inner) || outer.GetRawText() != inner.GetRawText())
                throw new InvalidDataException("STORED_SIGNED_FIELD_MISMATCH:" + field);
        }
        var head = NativeTaskEnvelope.ReadString(receipt, "journal_head_sha256");
        if (!journal.EntryHashes.Contains(head, StringComparer.Ordinal)) throw new InvalidDataException("STORED_RECEIPT_JOURNAL_HEAD_MISSING");
    }

    private sealed record ParsedArgs(string Command, Dictionary<string, string> Values);

    private static ParsedArgs ParseArgs(string[] args)
    {
        if (args.Length < 1) throw new InvalidDataException("COMMAND_REQUIRED");
        var command = args[0];
        var allowed = new HashSet<string>(StringComparer.Ordinal)
        {
            "task-json", "state-dir", "key-name", "receipt-out",
            "relay-url", "workspace", "enrollment-file", "poll-seconds"
        };
        var values = new Dictionary<string, string>(StringComparer.Ordinal);
        for (var index = 1; index < args.Length; index += 2)
        {
            if (index + 1 >= args.Length || !args[index].StartsWith("--", StringComparison.Ordinal)) throw new InvalidDataException("ARGUMENT_PAIR_INVALID");
            var name = args[index][2..];
            if (!allowed.Contains(name)) throw new InvalidDataException("ARGUMENT_NOT_ALLOWLISTED:" + name);
            if (!values.TryAdd(name, args[index + 1])) throw new InvalidDataException("ARGUMENT_DUPLICATE:" + name);
        }
        return new ParsedArgs(command, values);
    }

    private static string Required(Dictionary<string, string> values, string name)
    {
        if (!values.TryGetValue(name, out var value) || string.IsNullOrWhiteSpace(value)) throw new InvalidDataException("ARGUMENT_REQUIRED:" + name);
        return value;
    }

    private static void WriteDurable(string path, string content)
    {
        var fullPath = Path.GetFullPath(path);
        Directory.CreateDirectory(Path.GetDirectoryName(fullPath)!);
        var tempPath = fullPath + ".tmp-" + Guid.NewGuid().ToString("N");
        var bytes = Encoding.UTF8.GetBytes(content);
        using (var stream = new FileStream(tempPath, FileMode.CreateNew, FileAccess.Write, FileShare.None, 4096, FileOptions.WriteThrough))
        {
            stream.Write(bytes, 0, bytes.Length);
            stream.Flush(flushToDisk: true);
        }
        File.Move(tempPath, fullPath, overwrite: true);
    }

    private static string UtcNow() => DateTimeOffset.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss.fffffff'Z'", CultureInfo.InvariantCulture);
}
