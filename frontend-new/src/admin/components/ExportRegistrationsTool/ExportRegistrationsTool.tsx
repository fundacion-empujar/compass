import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { Box, Stack, Alert, CircularProgress, Typography } from "@mui/material";
import TableViewIcon from "@mui/icons-material/TableView";
import PrimaryButton from "src/theme/PrimaryButton/PrimaryButton";
import FaqAccordion from "src/admin/components/FaqAccordion/FaqAccordion";
import { AdminService } from "src/admin/services/adminService";
import { saveAs } from "src/experiences/saveAs";

const uniqueId = "e2c0d3f4-9a5b-4c73-be8d-exportregs0003";

export const DATA_TEST_ID = {
  EXPORT_TOOL: `export-tool-${uniqueId}`,
  EXPORT_BUTTON: `export-button-${uniqueId}`,
  SUCCESS: `export-success-${uniqueId}`,
  ERROR: `export-error-${uniqueId}`,
  FAQ: `export-faq-${uniqueId}`,
};

const EXPORT_FILE_NAME = "registrations.csv";

interface ExportRegistrationsToolProps {
  token: string;
}

const ExportRegistrationsTool: React.FC<ExportRegistrationsToolProps> = ({ token }) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState<boolean>(false);
  const [done, setDone] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleExport = async () => {
    setLoading(true);
    setError(null);
    setDone(false);
    try {
      const blob = await AdminService.getInstance().exportRegistrations(token);
      saveAs(blob, EXPORT_FILE_NAME);
      setDone(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("admin.panel.export.error"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box data-testid={DATA_TEST_ID.EXPORT_TOOL}>
      <Typography variant="h6" gutterBottom>
        {t("admin.panel.export.heading")}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t("admin.panel.export.help")}
      </Typography>
      <Stack spacing={2}>
        <PrimaryButton
          startIcon={loading ? undefined : <TableViewIcon />}
          disabled={loading}
          onClick={handleExport}
          data-testid={DATA_TEST_ID.EXPORT_BUTTON}
        >
          {loading ? <CircularProgress size={24} color="inherit" /> : t("admin.panel.export.submit")}
        </PrimaryButton>
        {error && (
          <Alert severity="error" data-testid={DATA_TEST_ID.ERROR}>
            {error}
          </Alert>
        )}
        {done && (
          <Alert severity="success" data-testid={DATA_TEST_ID.SUCCESS}>
            {t("admin.panel.export.success")}
          </Alert>
        )}

        <FaqAccordion
          testId={DATA_TEST_ID.FAQ}
          items={[
            {
              id: "export",
              question: t("admin.panel.export.faq.question"),
              answer: t("admin.panel.export.faq.answer"),
            },
          ]}
        />
      </Stack>
    </Box>
  );
};

export default ExportRegistrationsTool;
