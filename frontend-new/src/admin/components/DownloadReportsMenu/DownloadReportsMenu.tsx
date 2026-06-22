import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Box, Stack, Card, CardActionArea, CardContent, Typography, Button, useTheme } from "@mui/material";
import ManageSearchIcon from "@mui/icons-material/ManageSearch";
import DownloadIcon from "@mui/icons-material/Download";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import { routerPaths } from "src/app/routerPaths";
import ReportLookupTool from "src/admin/components/ReportLookupTool/ReportLookupTool";

const uniqueId = "c9f1a7b2-3e64-4d05-9b8a-downloadmenu01";

export const DATA_TEST_ID = {
  DOWNLOAD_REPORTS_MENU: `download-reports-menu-${uniqueId}`,
  CARD_INDIVIDUAL: `download-reports-individual-${uniqueId}`,
  CARD_BULK: `download-reports-bulk-${uniqueId}`,
  BACK_TO_OPTIONS: `download-reports-back-${uniqueId}`,
};

interface DownloadReportsMenuProps {
  token: string;
}

/**
 * Groups the two report flows behind one card: pick "individual" (open one
 * student's report via the existing lookup form) or "bulk" (the existing
 * bulk-download page). The admin token is forwarded to both.
 */
const DownloadReportsMenu: React.FC<DownloadReportsMenuProps> = ({ token }) => {
  const theme = useTheme();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [view, setView] = useState<"menu" | "individual">("menu");

  if (view === "individual") {
    return (
      <Box data-testid={DATA_TEST_ID.DOWNLOAD_REPORTS_MENU}>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => setView("menu")}
          sx={{ mb: theme.spacing(1) }}
          data-testid={DATA_TEST_ID.BACK_TO_OPTIONS}
        >
          {t("admin.panel.reports.menu.back")}
        </Button>
        <ReportLookupTool token={token} />
      </Box>
    );
  }

  const options = [
    {
      testId: DATA_TEST_ID.CARD_INDIVIDUAL,
      icon: <ManageSearchIcon fontSize="large" color="primary" />,
      title: t("admin.panel.reports.menu.individual.title"),
      description: t("admin.panel.reports.menu.individual.description"),
      onClick: () => setView("individual"),
    },
    {
      testId: DATA_TEST_ID.CARD_BULK,
      icon: <DownloadIcon fontSize="large" color="secondary" />,
      title: t("admin.panel.reports.menu.bulk.title"),
      description: t("admin.panel.reports.menu.bulk.description"),
      onClick: () => navigate(`${routerPaths.BULK_DOWNLOAD_REPORTS}?token=${encodeURIComponent(token)}`),
    },
  ];

  return (
    <Box data-testid={DATA_TEST_ID.DOWNLOAD_REPORTS_MENU}>
      <Typography variant="h6" gutterBottom>
        {t("admin.panel.reports.menu.heading")}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t("admin.panel.reports.menu.help")}
      </Typography>
      <Stack spacing={2}>
        {options.map((option) => (
          <Card key={option.testId} variant="outlined">
            <CardActionArea onClick={option.onClick} data-testid={option.testId}>
              <CardContent sx={{ display: "flex", alignItems: "center", gap: theme.spacing(2) }}>
                {option.icon}
                <Box>
                  <Typography variant="h6">{option.title}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {option.description}
                  </Typography>
                </Box>
              </CardContent>
            </CardActionArea>
          </Card>
        ))}
      </Stack>
    </Box>
  );
};

export default DownloadReportsMenu;
