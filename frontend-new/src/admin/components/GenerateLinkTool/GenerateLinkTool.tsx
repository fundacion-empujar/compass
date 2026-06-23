import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { Box, TextField, Stack, Alert, AlertTitle, CircularProgress, Typography } from "@mui/material";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import PrimaryButton from "src/theme/PrimaryButton/PrimaryButton";
import FaqAccordion from "src/admin/components/FaqAccordion/FaqAccordion";
import { AdminService, CreateRegistrationLinkResult } from "src/admin/services/adminService";

const uniqueId = "c0a8b1d2-7e3f-4a51-9c6b-generatelink01";

export const DATA_TEST_ID = {
  GENERATE_LINK_TOOL: `generate-link-tool-${uniqueId}`,
  CODE_INPUT: `generate-link-code-input-${uniqueId}`,
  SUBMIT_BUTTON: `generate-link-submit-${uniqueId}`,
  LINK_READY: `generate-link-ready-${uniqueId}`,
  RESULT_LINK: `generate-link-result-${uniqueId}`,
  COPY_BUTTON: `generate-link-copy-${uniqueId}`,
  ALREADY_USED_WARNING: `generate-link-already-used-${uniqueId}`,
  ERROR: `generate-link-error-${uniqueId}`,
  FAQ: `generate-link-faq-${uniqueId}`,
};

const GenerateLinkTool: React.FC = () => {
  const { t } = useTranslation();
  const [code, setCode] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<CreateRegistrationLinkResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);
  // Clipboard can fail (permissions / insecure context). Only then do we reveal the raw URL.
  const [copyFailed, setCopyFailed] = useState<boolean>(false);

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setCopied(false);
    setCopyFailed(false);
    try {
      const res = await AdminService.getInstance().createRegistrationLink(code.trim());
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("admin.panel.generateLink.error"));
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!result) {
      return;
    }
    try {
      await navigator.clipboard.writeText(result.link);
      setCopied(true);
      setCopyFailed(false);
    } catch {
      // Surface the URL as a manual-copy fallback instead of silently failing.
      setCopyFailed(true);
      setCopied(false);
    }
  };

  return (
    <Box data-testid={DATA_TEST_ID.GENERATE_LINK_TOOL}>
      <Typography variant="h6" gutterBottom>
        {t("admin.panel.generateLink.heading")}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t("admin.panel.generateLink.help")}
      </Typography>
      <Stack spacing={2}>
        <TextField
          fullWidth
          label={t("admin.panel.generateLink.codeLabel")}
          placeholder={t("admin.panel.generateLink.codePlaceholder")}
          value={code}
          onChange={(event) => setCode(event.target.value)}
          inputProps={{ "data-testid": DATA_TEST_ID.CODE_INPUT }}
        />
        <PrimaryButton
          disabled={!code.trim() || loading}
          onClick={handleSubmit}
          data-testid={DATA_TEST_ID.SUBMIT_BUTTON}
        >
          {loading ? <CircularProgress size={24} color="inherit" /> : t("admin.panel.generateLink.submit")}
        </PrimaryButton>

        {error && (
          <Alert severity="error" data-testid={DATA_TEST_ID.ERROR}>
            {error}
          </Alert>
        )}

        {result && (
          <>
            {result.already_used && (
              <Alert severity="warning" data-testid={DATA_TEST_ID.ALREADY_USED_WARNING}>
                <AlertTitle>{t("admin.panel.generateLink.alreadyUsedTitle")}</AlertTitle>
                {t("admin.panel.generateLink.alreadyUsedBody")}
              </Alert>
            )}
            {/* The raw URL is intentionally hidden — staff just copy & share it. */}
            <Alert severity="success" data-testid={DATA_TEST_ID.LINK_READY}>
              <AlertTitle>{t("admin.panel.generateLink.linkReadyTitle")}</AlertTitle>
              {t("admin.panel.generateLink.linkReadyBody")}
            </Alert>
            <PrimaryButton startIcon={<ContentCopyIcon />} onClick={handleCopy} data-testid={DATA_TEST_ID.COPY_BUTTON}>
              {copied ? t("admin.panel.generateLink.copied") : t("admin.panel.generateLink.copy")}
            </PrimaryButton>
            {copyFailed && (
              <TextField
                fullWidth
                label={t("admin.panel.generateLink.resultLabel")}
                value={result.link}
                InputProps={{ readOnly: true }}
                helperText={t("admin.panel.generateLink.copyFailedHint")}
                inputProps={{ "data-testid": DATA_TEST_ID.RESULT_LINK }}
              />
            )}
          </>
        )}

        <FaqAccordion
          testId={DATA_TEST_ID.FAQ}
          items={[
            {
              id: "generateLink",
              question: t("admin.panel.generateLink.faq.question"),
              answer: t("admin.panel.generateLink.faq.answer"),
            },
            {
              id: "generateLinkUsage",
              question: t("admin.panel.generateLink.usageFaq.question"),
              answer: t("admin.panel.generateLink.usageFaq.answer"),
            },
          ]}
        />
      </Stack>
    </Box>
  );
};

export default GenerateLinkTool;
