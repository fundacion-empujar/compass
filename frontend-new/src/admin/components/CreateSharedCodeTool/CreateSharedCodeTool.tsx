import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Box,
  TextField,
  Stack,
  Alert,
  AlertTitle,
  ToggleButton,
  ToggleButtonGroup,
  CircularProgress,
  Typography,
} from "@mui/material";
import PrimaryButton from "src/theme/PrimaryButton/PrimaryButton";
import FaqAccordion from "src/admin/components/FaqAccordion/FaqAccordion";
import { AdminService, CreateSharedCodeResult, SharedCodeType } from "src/admin/services/adminService";

const uniqueId = "d1b9c2e3-8f4a-4b62-ad7c-sharedcode002";

export const DATA_TEST_ID = {
  SHARED_CODE_TOOL: `shared-code-tool-${uniqueId}`,
  CODE_INPUT: `shared-code-input-${uniqueId}`,
  TYPE_REGISTER: `shared-code-type-register-${uniqueId}`,
  TYPE_LOGIN: `shared-code-type-login-${uniqueId}`,
  SUBMIT_BUTTON: `shared-code-submit-${uniqueId}`,
  SUCCESS: `shared-code-success-${uniqueId}`,
  ERROR: `shared-code-error-${uniqueId}`,
  FAQ: `shared-code-faq-${uniqueId}`,
};

interface CreateSharedCodeToolProps {
  token: string;
}

const CreateSharedCodeTool: React.FC<CreateSharedCodeToolProps> = ({ token }) => {
  const { t } = useTranslation();
  const [code, setCode] = useState<string>("");
  const [type, setType] = useState<SharedCodeType>("REGISTER");
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<CreateSharedCodeResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await AdminService.getInstance().createSharedCode(token, {
        invitation_code: code.trim(),
        invitation_type: type,
      });
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("admin.panel.sharedCode.error"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box data-testid={DATA_TEST_ID.SHARED_CODE_TOOL}>
      <Typography variant="h6" gutterBottom>
        {t("admin.panel.sharedCode.heading")}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t("admin.panel.sharedCode.help")}
      </Typography>
      <Stack spacing={2}>
        <TextField
          fullWidth
          label={t("admin.panel.sharedCode.codeLabel")}
          placeholder={t("admin.panel.sharedCode.codePlaceholder")}
          value={code}
          onChange={(event) => setCode(event.target.value)}
          inputProps={{ "data-testid": DATA_TEST_ID.CODE_INPUT }}
        />
        <Box>
          <Typography variant="body2" sx={{ mb: 1 }}>
            {t("admin.panel.sharedCode.typeLabel")}
          </Typography>
          <ToggleButtonGroup
            exclusive
            fullWidth
            value={type}
            onChange={(_event, value: SharedCodeType | null) => {
              if (value) {
                setType(value);
              }
            }}
          >
            <ToggleButton value="REGISTER" data-testid={DATA_TEST_ID.TYPE_REGISTER}>
              {t("admin.panel.sharedCode.typeRegister")}
            </ToggleButton>
            <ToggleButton value="LOGIN" data-testid={DATA_TEST_ID.TYPE_LOGIN}>
              {t("admin.panel.sharedCode.typeLogin")}
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>
        <PrimaryButton
          disabled={!code.trim() || loading}
          onClick={handleSubmit}
          data-testid={DATA_TEST_ID.SUBMIT_BUTTON}
        >
          {loading ? <CircularProgress size={24} color="inherit" /> : t("admin.panel.sharedCode.submit")}
        </PrimaryButton>

        {error && (
          <Alert severity="error" data-testid={DATA_TEST_ID.ERROR}>
            {error}
          </Alert>
        )}
        {result && (
          <Alert severity="success" data-testid={DATA_TEST_ID.SUCCESS}>
            <AlertTitle>{t("admin.panel.sharedCode.successTitle")}</AlertTitle>
            {t("admin.panel.sharedCode.successBody", { code: result.invitation_code })}
          </Alert>
        )}

        <FaqAccordion
          testId={DATA_TEST_ID.FAQ}
          items={[
            {
              id: "sharedCode",
              question: t("admin.panel.sharedCode.faq.question"),
              answer: t("admin.panel.sharedCode.faq.answer"),
            },
            {
              id: "sharedCodeValidity",
              question: t("admin.panel.sharedCode.validityFaq.question"),
              answer: t("admin.panel.sharedCode.validityFaq.answer"),
            },
          ]}
        />
      </Stack>
    </Box>
  );
};

export default CreateSharedCodeTool;
