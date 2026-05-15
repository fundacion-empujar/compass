import React, { useMemo, useState } from "react";
import { Alert, IconButton, Link, useTheme } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import { useTranslation } from "react-i18next";

import { getBackendUrl, getTargetEnvironmentName } from "src/envService";

const uniqueId = "9b3c9f44-1d8a-4d92-9b21-d8a3c1f0a9b1";

export const DATA_TEST_ID = {
  BANNER: `test-environment-banner-${uniqueId}`,
  LINK: `test-environment-banner-link-${uniqueId}`,
  CLOSE_BUTTON: `test-environment-banner-close-${uniqueId}`,
};

export const DISMISSED_STORAGE_KEY = "test-env-banner-dismissed";

const TEST_ENV_PREFIX = "test-";
const DEV_ENV_PREFIX = "dev-";

/**
 * Derive the recommended (production-like) frontend URL from the current env's BACKEND_URL.
 * On the test stack BACKEND_URL is e.g. "https://test-brujula.compass.tabiya.tech/api"; we strip
 * the "/api" suffix and replace the "test-" host prefix with "dev-".
 * Returns null if the derivation cannot produce a safe https URL different from the input origin.
 */
export const deriveRecommendedFrontendUrl = (backendUrl: string): string | null => {
  if (!backendUrl.startsWith("https://")) return null;

  const origin = backendUrl.replace(/\/api\/?$/, "");
  const replaced = origin.replace(`//${TEST_ENV_PREFIX}`, `//${DEV_ENV_PREFIX}`);

  if (replaced === origin) return null;
  return replaced;
};

const TestEnvironmentBanner: React.FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();

  const envName = getTargetEnvironmentName();
  const recommendedUrl = useMemo(() => deriveRecommendedFrontendUrl(getBackendUrl()), []);

  const [dismissed, setDismissed] = useState<boolean>(() => {
    try {
      return sessionStorage.getItem(DISMISSED_STORAGE_KEY) === "true";
    } catch {
      return false;
    }
  });

  if (!envName.startsWith(TEST_ENV_PREFIX)) return null;
  if (!recommendedUrl) return null;
  if (dismissed) return null;

  const handleClose = () => {
    try {
      sessionStorage.setItem(DISMISSED_STORAGE_KEY, "true");
    } catch {
      // ignore — fall back to hiding for the current render
    }
    setDismissed(true);
  };

  return (
    <Alert
      severity="warning"
      variant="filled"
      data-testid={DATA_TEST_ID.BANNER}
      action={
        <IconButton
          aria-label={t("testEnvironmentBanner.closeAriaLabel")}
          color="inherit"
          size="small"
          onClick={handleClose}
          data-testid={DATA_TEST_ID.CLOSE_BUTTON}
        >
          <CloseIcon fontSize="inherit" />
        </IconButton>
      }
      sx={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        width: "100%",
        borderRadius: 0,
        justifyContent: "center",
        alignItems: "center",
        zIndex: theme.zIndex.modal + 1,
      }}
    >
      {t("testEnvironmentBanner.message")}{" "}
      <Link
        href={recommendedUrl}
        target="_blank"
        rel="noopener noreferrer"
        color="inherit"
        underline="always"
        data-testid={DATA_TEST_ID.LINK}
      >
        {t("testEnvironmentBanner.linkLabel")}
      </Link>
    </Alert>
  );
};

export default TestEnvironmentBanner;
