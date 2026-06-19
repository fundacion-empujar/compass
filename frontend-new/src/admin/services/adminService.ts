import { getBackendUrl } from "src/envService";

export interface CreateRegistrationLinkResult {
  registration_code: string;
  link: string;
  already_used: boolean;
}

export type SharedCodeType = "REGISTER" | "LOGIN";

export interface CreateSharedCodeInput {
  invitation_code: string;
  invitation_type: SharedCodeType;
  allowed_usage?: number;
  valid_from?: string;
  valid_until?: string;
  sensitive_personal_data_requirement?: "NOT_AVAILABLE" | "REQUIRED" | "NOT_REQUIRED";
}

export interface CreateSharedCodeResult {
  invitation_code: string;
  invitation_type: string;
  allowed_usage: number;
  valid_from: string;
  valid_until: string;
  sensitive_personal_data_requirement: string;
}

/**
 * Talks to the ADMIN_TOKEN-gated `/admin` endpoints. The token is read from the
 * admin panel's own URL and passed as the `?token=` query param on every call.
 * Modeled on BulkDownloadReportsService (singleton + getBackendUrl + native fetch).
 */
export class AdminService {
  private static instance: AdminService;
  private readonly baseUrl: string;

  private constructor() {
    this.baseUrl = `${getBackendUrl()}/admin`;
  }

  public static getInstance(): AdminService {
    if (!AdminService.instance) {
      AdminService.instance = new AdminService();
    }
    return AdminService.instance;
  }

  public async createRegistrationLink(
    token: string,
    registrationCode: string,
    invitationCodeTemplate?: string
  ): Promise<CreateRegistrationLinkResult> {
    const response = await fetch(`${this.baseUrl}/registration-links?${this.tokenQuery(token)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        registration_code: registrationCode,
        invitation_code_template: invitationCodeTemplate ?? null,
      }),
    });
    return this.parseJson<CreateRegistrationLinkResult>(response);
  }

  public async createSharedCode(token: string, input: CreateSharedCodeInput): Promise<CreateSharedCodeResult> {
    const response = await fetch(`${this.baseUrl}/shared-codes?${this.tokenQuery(token)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    return this.parseJson<CreateSharedCodeResult>(response);
  }

  public async exportRegistrations(token: string): Promise<Blob> {
    const response = await fetch(`${this.baseUrl}/registrations/export?${this.tokenQuery(token)}`, {
      method: "GET",
      headers: { Accept: "text/csv" },
    });
    if (!response.ok) {
      throw new Error(await this.errorMessage(response));
    }
    return response.blob();
  }

  private tokenQuery(token: string): string {
    return new URLSearchParams({ token }).toString();
  }

  private async parseJson<T>(response: Response): Promise<T> {
    if (!response.ok) {
      throw new Error(await this.errorMessage(response));
    }
    return (await response.json()) as T;
  }

  private async errorMessage(response: Response): Promise<string> {
    let detail = "";
    try {
      const data = await response.json();
      detail = typeof data?.detail === "string" ? data.detail : "";
    } catch {
      // response had no JSON body
    }
    return `Request failed (${response.status} ${response.statusText})${detail ? `: ${detail}` : ""}`;
  }
}
