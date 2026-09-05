declare module "google-auth-library" {
  export class GoogleAuth {
    constructor(options?: {scopes?: string[]});
    getClient(): Promise<{getAccessToken(): Promise<string | {token?: string | null} | null>}>;
  }
  export class Impersonated {
    constructor(options: {
      sourceClient: unknown;
      targetPrincipal: string;
      targetScopes: string[];
      lifetime: number;
    });
    getAccessToken(): Promise<string | {token?: string | null} | null>;
  }
}

declare module "@google-cloud/storage" {
  export class Storage {
    bucket(name: string): {
      file(name: string): {
        save(data: string, options: {
          contentType: string;
          resumable: boolean;
        }): Promise<void>;
      };
    };
  }
}
