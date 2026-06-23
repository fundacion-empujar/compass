import { getBackendUrl } from "src/envService";
import AuthenticationStateService from "src/auth/services/AuthenticationState.service";

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
 * Talks to the `/admin` endpoints, which are gated on the Firebase `super_admin` claim.
 * Sends the logged-in admin's Firebase ID token as a Bearer header (like the app's other
 * authenticated calls). Singleton + getBackendUrl + native fetch.
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
    registrationCode: string,
    invitationCodeTemplate?: string
  ): Promise<CreateRegistrationLinkResult> {
    const response = await fetch(`${this.baseUrl}/registration-links`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...this.authHeaders() },
      body: JSON.stringify({
        registration_code: registrationCode,
        invitation_code_template: invitationCodeTemplate ?? null,
      }),
    });
    return this.parseJson<CreateRegistrationLinkResult>(response);
  }

  public async createSharedCode(input: CreateSharedCodeInput): Promise<CreateSharedCodeResult> {
    const response = await fetch(`${this.baseUrl}/shared-codes`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...this.authHeaders() },
      body: JSON.stringify(input),
    });
    return this.parseJson<CreateSharedCodeResult>(response);
  }

  public async exportRegistrations(): Promise<Blob> {
    const response = await fetch(`${this.baseUrl}/registrations/export`, {
      method: "GET",
      headers: { Accept: "text/csv", ...this.authHeaders() },
    });
    if (!response.ok) {
      throw new Error(await this.errorMessage(response));
    }
    return response.blob();
  }

  private authHeaders(): Record<string, string> {
    const token = AuthenticationStateService.getInstance().getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
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
