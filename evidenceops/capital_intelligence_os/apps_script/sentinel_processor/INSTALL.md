# SENTINEL Apps Script Processor — Activation

Candidate Apps Script project IDs:

- `1cUQy4k_IE_9BNhIJzk5ik49Xhus3xWD7qLjIv6yf8ncEKwzCqjjGhh7D`
- `1z4wkTnk3TF3NG6T-1f5PsSl08-3SFUQw4STcYwsiPptdGSVrfSE-4r_R`

The processor binds to spreadsheet `1LSVjK9YK6u2CMrvetOcXpun4VQnOh5cE6b3w6z_KTHg` and tab `SENTINEL_Activation_Queue`.

## One activation transaction

From an authenticated environment with `clasp`:

```bash
bash ops/activate_apps_script_processor.sh
```

The activation script attempts the primary candidate first, then the secondary candidate. It pushes `Code.gs` and `appsscript.json`, runs `installSentinelProcessor`, and requires a receipt containing `FEDOMEGA-GAS-INSTALLED`.

## Completion proof

Activation is complete only when all are true:

- source push succeeded;
- `installSentinelProcessor` executed;
- exactly one `processSentinelQueue` trigger exists;
- a new Heartbeat row identifies the installed script ID;
- the receipt contains the processor version and queue spreadsheet ID.

No scheduled ChatGPT task is used. The only schedule created is the native Apps Script five-minute trigger that performs the intended queue processing.
