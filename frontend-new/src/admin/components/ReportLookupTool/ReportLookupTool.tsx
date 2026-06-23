import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Box, TextField, Stack, Typography } from "@mui/material";
import PrimaryButton from "src/theme/PrimaryButton/PrimaryButton";
import FaqAccordion from "src/admin/components/FaqAccordion/FaqAccordion";
import { routerPaths } from "src/app/routerPaths";

const uniqueId = "b7d3e1f4-2a98-4c61-8e5d-reportlookup01";

export const DATA_TEST_ID = {
  REPORT_LOOKUP_TOOL: `report-lookup-tool-${uniqueId}`,
  CODE_INPUT: `report-lookup-code-input-${uniqueId}`,
  SUBMIT_BUTTON: `report-lookup-submit-${uniqueId}`,
  FAQ: `report-lookup-faq-${uniqueId}`,
};

/**
 * Search for one student's individual report by registration code / user id and open it.
 * Reuses the existing public report page; access is gated by the super_admin login.
 */
const ReportLookupTool: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [identifier, setIdentifier] = useState<string>("");

  const handleSubmit = () => {
    const trimmed = identifier.trim();
    if (!trimmed) {
      return;
    }
    const path = routerPaths.REPORT.replace(":id", encodeURIComponent(trimmed));
    navigate(path);
  };

  return (
    <Box data-testid={DATA_TEST_ID.REPORT_LOOKUP_TOOL}>
      <Typography variant="h6" gutterBottom>
        {t("admin.panel.reportLookup.heading")}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t("admin.panel.reportLookup.help")}
      </Typography>
      <Stack spacing={2}>
        <TextField
          fullWidth
          label={t("admin.panel.reportLookup.codeLabel")}
          placeholder={t("admin.panel.reportLookup.codePlaceholder")}
          value={identifier}
          onChange={(event) => setIdentifier(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              handleSubmit();
            }
          }}
          inputProps={{ "data-testid": DATA_TEST_ID.CODE_INPUT }}
        />
        <PrimaryButton disabled={!identifier.trim()} onClick={handleSubmit} data-testid={DATA_TEST_ID.SUBMIT_BUTTON}>
          {t("admin.panel.reportLookup.submit")}
        </PrimaryButton>

        <FaqAccordion
          testId={DATA_TEST_ID.FAQ}
          items={[
            {
              id: "reportLookup",
              question: t("admin.panel.reportLookup.faq.question"),
              answer: t("admin.panel.reportLookup.faq.answer"),
            },
          ]}
        />
      </Stack>
    </Box>
  );
};

export default ReportLookupTool;
