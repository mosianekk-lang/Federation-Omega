/* ============================================================================
 * COMMON EXECUTION WRAPPER
 * ========================================================================== */

function ARCHON_CODE_execute_(
  command,
  context,
  handler
) {
  const started = new Date();

  try {
    const payload = handler();

    return {
      ok: true,
      command: command,
      status: 'COMPLETED',
      startedAt: started.toISOString(),
      completedAt: new Date().toISOString(),
      durationMs: Date.now() - started.getTime(),
      payload: payload
    };

  } catch (error) {
    return {
      ok: false,
      command: command,
      status: 'FAILED',
      startedAt: started.toISOString(),
      completedAt: new Date().toISOString(),
      durationMs: Date.now() - started.getTime(),
      error: ARCHON_CODE_error_(error)
    };
  }
}


function ARCHON_CODE_getParameters_(context) {
  if (
    context &&
    context.parameters &&
    typeof context.parameters === 'object'
  ) {
    return context.parameters;
  }

  return context || {};
}


function ARCHON_CODE_error_(error) {
  return {
    name:
      error && error.name
        ? error.name
        : 'Error',
    message:
      error && error.message
        ? error.message
        : String(error),
    stack:
      error && error.stack
        ? error.stack
        : ''
  };
}


function ARCHON_CODE_limitCell_(text) {
  const value = String(text || '');

  if (value.length <= 45000) {
    return value;
  }

  return value.substring(0, 44950) +
    '[ARCHON_TRUNCATED]';
}
