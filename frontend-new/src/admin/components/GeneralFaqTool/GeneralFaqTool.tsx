import React from "react";
import { useTranslation } from "react-i18next";
import { Box, Typography, Stack } from "@mui/material";
import FaqAccordion, { FaqItem } from "src/admin/components/FaqAccordion/FaqAccordion";

const uniqueId = "b5e2d3f4-6c7a-4b81-ad9e-generalfaq0001";

export const DATA_TEST_ID = {
  GENERAL_FAQ_TOOL: `general-faq-tool-${uniqueId}`,
  CV_THUMBNAIL: `general-faq-cv-thumbnail-${uniqueId}`,
};

/**
 * Plain-language help for non-technical staff: why the code/link system exists, the
 * difference between the two code types, what each panel section does, and a thumbnail
 * so they recognise the report/informe/CV (all the same document).
 */
const GeneralFaqTool: React.FC = () => {
  const { t } = useTranslation();

  const reportAnswer = (
    <Stack spacing={1.5}>
      <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: "pre-line" }}>
        {t("admin.panel.generalFaq.report.answer")}
      </Typography>
      <Box
        component="img"
        src={`${process.env.PUBLIC_URL}/cv-report-thumbnail.png`}
        alt={t("admin.panel.generalFaq.report.thumbnailAlt")}
        data-testid={DATA_TEST_ID.CV_THUMBNAIL}
        sx={{
          width: "100%",
          maxWidth: 260,
          alignSelf: "center",
          borderRadius: 1,
          border: "1px solid",
          borderColor: "divider",
          boxShadow: 2,
        }}
      />
      <Typography variant="caption" color="text.secondary" align="center">
        {t("admin.panel.generalFaq.report.thumbnailCaption")}
      </Typography>
    </Stack>
  );

  const items: FaqItem[] = [
    {
      id: "why",
      question: t("admin.panel.generalFaq.why.question"),
      answer: t("admin.panel.generalFaq.why.answer"),
    },
    {
      id: "difference",
      question: t("admin.panel.generalFaq.difference.question"),
      answer: t("admin.panel.generalFaq.difference.answer"),
    },
    {
      id: "individualUsage",
      question: t("admin.panel.generalFaq.individualUsage.question"),
      answer: t("admin.panel.generalFaq.individualUsage.answer"),
    },
    {
      id: "validity",
      question: t("admin.panel.generalFaq.validity.question"),
      answer: t("admin.panel.generalFaq.validity.answer"),
    },
    {
      id: "sections",
      question: t("admin.panel.generalFaq.sections.question"),
      answer: t("admin.panel.generalFaq.sections.answer"),
    },
    {
      id: "report",
      question: t("admin.panel.generalFaq.report.question"),
      answer: reportAnswer,
    },
  ];

  return (
    <Box data-testid={DATA_TEST_ID.GENERAL_FAQ_TOOL}>
      <Typography variant="h6" gutterBottom>
        {t("admin.panel.generalFaq.heading")}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t("admin.panel.generalFaq.intro")}
      </Typography>
      <FaqAccordion items={items} />
    </Box>
  );
};

export default GeneralFaqTool;
