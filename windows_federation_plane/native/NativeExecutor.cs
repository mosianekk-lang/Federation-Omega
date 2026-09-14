using System.Buffers.Binary;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;

namespace Fuse.Windows.Native;

internal static class NativeExecutor
{
    public static Dictionary<string, object?> Execute(NativeTaskEnvelope task)
    {
        return task.TaskType switch
        {
            "system_status" => SystemStatus(),
            "heavy_sha256" => HeavySha256(task.Parameters),
            _ => throw new InvalidDataException("TASK_TYPE_NOT_ALLOWLISTED")
        };
    }

    private static Dictionary<string, object?> SystemStatus()
    {
        return new Dictionary<string, object?>
        {
            ["operation"] = "system_status",
            ["machine_name"] = Environment.MachineName,
            ["os_description"] = RuntimeInformation.OSDescription,
            ["os_architecture"] = RuntimeInformation.OSArchitecture.ToString(),
            ["process_architecture"] = RuntimeInformation.ProcessArchitecture.ToString(),
            ["logical_cores"] = Environment.ProcessorCount,
            ["process_id"] = Environment.ProcessId,
            ["filesystem_usage"] = false,
            ["network_usage"] = false,
            ["shell_process_usage"] = false,
            ["gpu_usage"] = false,
            ["external_effect"] = false
        };
    }

    private static Dictionary<string, object?> HeavySha256(JsonElement parameters)
    {
        var bytesPerRound = NativeTaskEnvelope.ReadInt64(parameters, "bytes_per_round");
        var rounds = NativeTaskEnvelope.ReadInt32(parameters, "rounds");
        var requestedWorkers = NativeTaskEnvelope.ReadInt32(parameters, "requested_workers");
        var requestedMemoryMb = NativeTaskEnvelope.ReadInt32(parameters, "requested_memory_mb");
        var maxSeconds = NativeTaskEnvelope.ReadInt32(parameters, "max_seconds");
        var seed = Convert.FromHexString(NativeTaskEnvelope.ReadString(parameters, "seed_hex"));
        var grantedWorkers = Math.Max(1, Math.Min(requestedWorkers, Math.Min(16, Math.Max(1, Environment.ProcessorCount - 1))));
        var grantedMemoryMb = Math.Max(64, Math.Min(requestedMemoryMb, 1024));
        var totalBytes = checked(bytesPerRound * rounds);
        var sw = Stopwatch.StartNew();
        var roundDigests = new byte[rounds][];
        var options = new ParallelOptions { MaxDegreeOfParallelism = grantedWorkers };

        try
        {
            Parallel.For(0, rounds, options, round =>
            {
                using var hasher = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
                long remaining = bytesPerRound;
                long block = 0;
                while (remaining > 0)
                {
                    if (sw.Elapsed.TotalSeconds > maxSeconds) throw new TimeoutException("HEAVY_DEADLINE_EXCEEDED");
                    var count = (int)Math.Min(1L * 1024 * 1024, remaining);
                    var chunk = new byte[count];
                    FillDeterministic(chunk, seed, round, block);
                    hasher.AppendData(chunk);
                    remaining -= count;
                    block++;
                }
                roundDigests[round] = hasher.GetHashAndReset();
            });
        }
        catch (AggregateException ex) when (ex.Flatten().InnerExceptions.Any(e => e is TimeoutException))
        {
            throw new TimeoutException("HEAVY_DEADLINE_EXCEEDED");
        }

        using var finalHasher = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        for (var round = 0; round < rounds; round++)
        {
            Span<byte> index = stackalloc byte[4];
            BinaryPrimitives.WriteInt32LittleEndian(index, round);
            finalHasher.AppendData(index);
            finalHasher.AppendData(roundDigests[round]);
        }
        var digest = Convert.ToHexString(finalHasher.GetHashAndReset()).ToLowerInvariant();
        sw.Stop();
        var seconds = Math.Max(sw.Elapsed.TotalSeconds, 0.000001d);
        var throughput = totalBytes / 1048576d / seconds;
        return new Dictionary<string, object?>
        {
            ["operation"] = "heavy_sha256",
            ["sha256"] = digest,
            ["total_bytes"] = totalBytes,
            ["rounds"] = rounds,
            ["bytes_per_round"] = bytesPerRound,
            ["requested_workers"] = requestedWorkers,
            ["granted_workers"] = grantedWorkers,
            ["requested_memory_mb"] = requestedMemoryMb,
            ["granted_memory_mb"] = grantedMemoryMb,
            ["max_seconds"] = maxSeconds,
            ["wall_seconds"] = seconds.ToString("F6", CultureInfo.InvariantCulture),
            ["throughput_mib_s"] = throughput.ToString("F3", CultureInfo.InvariantCulture),
            ["resource_governor_bound"] = true,
            ["generated_in_memory"] = true,
            ["filesystem_usage"] = false,
            ["network_usage"] = false,
            ["shell_process_usage"] = false,
            ["gpu_usage"] = false,
            ["external_effect"] = false
        };
    }

    private static void FillDeterministic(byte[] destination, byte[] seed, int round, long blockBase)
    {
        var offset = 0;
        long counter = blockBase * 32768;
        Span<byte> suffix = stackalloc byte[12];
        BinaryPrimitives.WriteInt32LittleEndian(suffix[..4], round);
        while (offset < destination.Length)
        {
            BinaryPrimitives.WriteInt64LittleEndian(suffix[4..], counter++);
            var input = new byte[seed.Length + suffix.Length];
            Buffer.BlockCopy(seed, 0, input, 0, seed.Length);
            suffix.CopyTo(input.AsSpan(seed.Length));
            var digest = SHA256.HashData(input);
            var count = Math.Min(digest.Length, destination.Length - offset);
            Buffer.BlockCopy(digest, 0, destination, offset, count);
            offset += count;
        }
    }
}
