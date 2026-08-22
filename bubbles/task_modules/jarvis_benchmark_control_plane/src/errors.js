export class ControlPlaneError extends Error {
  constructor(code, message, { status = 400, details = null } = {}) {
    super(message);
    this.name = 'ControlPlaneError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export function fail(code, message, options) {
  throw new ControlPlaneError(code, message, options);
}
