import React from "react";
import { useTranslation } from "react-i18next";
import ErrorPage from "src/error/errorPage/ErrorPage";
import { isChunkLoadError } from "src/error/isChunkLoadError";

interface AppErrorFallbackProps {
  error?: unknown;
}

/**
 * Shared error fallback UI: ErrorPage, plus a refresh button when the error is a chunk-load error.
 * Used by the top-level Sentry.ErrorBoundary and the router's errorElement (RouterErrorBoundary).
 */
export const AppErrorFallback: React.FC<AppErrorFallbackProps> = ({ error }) => {
  const { t } = useTranslation();
  return <ErrorPage errorMessage={t("error.errorPage.defaultMessage")} showRefreshButton={isChunkLoadError(error)} />;
};
