import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { Box, Paper, Typography, Stack, Card, CardActionArea, CardContent, Button, useTheme } from "@mui/material";
import PersonAddAlt1Icon from "@mui/icons-material/PersonAddAlt1";
import GroupAddIcon from "@mui/icons-material/GroupAdd";
import TableViewIcon from "@mui/icons-material/TableView";
import DownloadIcon from "@mui/icons-material/Download";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import LanguageContextMenu from "src/i18n/languageContextMenu/LanguageContextMenu";
import GenerateLinkTool from "src/admin/components/GenerateLinkTool/GenerateLinkTool";
import CreateSharedCodeTool from "src/admin/components/CreateSharedCodeTool/CreateSharedCodeTool";
import ExportRegistrationsTool from "src/admin/components/ExportRegistrationsTool/ExportRegistrationsTool";
import DownloadReportsMenu from "src/admin/components/DownloadReportsMenu/DownloadReportsMenu";
import GeneralFaqTool from "src/admin/components/GeneralFaqTool/GeneralFaqTool";

const uniqueId = "f3a2b1c0-6d5e-4f81-9a2b-adminpanel0000";

export const DATA_TEST_ID = {
  ADMIN_PANEL_CONTAINER: `admin-panel-container-${uniqueId}`,
  CARD_GENERATE_LINK: `admin-card-generate-link-${uniqueId}`,
  CARD_SHARED_CODE: `admin-card-shared-code-${uniqueId}`,
  CARD_EXPORT: `admin-card-export-${uniqueId}`,
  CARD_REPORTS: `admin-card-reports-${uniqueId}`,
  CARD_FAQ: `admin-card-faq-${uniqueId}`,
  BACK_BUTTON: `admin-back-button-${uniqueId}`,
};

type AdminTool = "link" | "shared" | "export" | "reports" | "faq";

const AdminPanel: React.FC = () => {
  const theme = useTheme();
  const { t } = useTranslation();

  const [activeTool, setActiveTool] = useState<AdminTool | null>(null);

  const cards = [
    {
      id: "link" as const,
      testId: DATA_TEST_ID.CARD_GENERATE_LINK,
      icon: <PersonAddAlt1Icon fontSize="large" color="primary" />,
      title: t("admin.panel.cards.generateLink.title"),
      description: t("admin.panel.cards.generateLink.description"),
      onClick: () => setActiveTool("link"),
    },
    {
      id: "shared" as const,
      testId: DATA_TEST_ID.CARD_SHARED_CODE,
      icon: <GroupAddIcon fontSize="large" color="secondary" />,
      title: t("admin.panel.cards.sharedCode.title"),
      description: t("admin.panel.cards.sharedCode.description"),
      onClick: () => setActiveTool("shared"),
    },
    {
      id: "export" as const,
      testId: DATA_TEST_ID.CARD_EXPORT,
      icon: <TableViewIcon fontSize="large" color="primary" />,
      title: t("admin.panel.cards.export.title"),
      description: t("admin.panel.cards.export.description"),
      onClick: () => setActiveTool("export"),
    },
    {
      id: "reports" as const,
      testId: DATA_TEST_ID.CARD_REPORTS,
      icon: <DownloadIcon fontSize="large" color="secondary" />,
      title: t("admin.panel.cards.reports.title"),
      description: t("admin.panel.cards.reports.description"),
      onClick: () => setActiveTool("reports"),
    },
    {
      id: "faq" as const,
      testId: DATA_TEST_ID.CARD_FAQ,
      icon: <HelpOutlineIcon fontSize="large" color="secondary" />,
      title: t("admin.panel.cards.generalFaq.title"),
      description: t("admin.panel.cards.generalFaq.description"),
      onClick: () => setActiveTool("faq"),
    },
  ];

  const renderActiveTool = () => {
    switch (activeTool) {
      case "link":
        return <GenerateLinkTool />;
      case "shared":
        return <CreateSharedCodeTool />;
      case "export":
        return <ExportRegistrationsTool />;
      case "reports":
        return <DownloadReportsMenu />;
      case "faq":
        return <GeneralFaqTool />;
      default:
        return null;
    }
  };

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#f5f5f5",
        py: theme.spacing(4),
      }}
    >
      <Paper
        elevation={3}
        sx={{ maxWidth: 700, width: "100%", padding: (sx) => sx.spacing(4), position: "relative" }}
        data-testid={DATA_TEST_ID.ADMIN_PANEL_CONTAINER}
      >
        <Box sx={{ position: "absolute", top: (sx) => sx.fixedSpacing(2), right: (sx) => sx.fixedSpacing(2) }}>
          <LanguageContextMenu removeMargin />
        </Box>

        <Typography
          variant="h4"
          component="h1"
          gutterBottom
          align="center"
          sx={{ fontWeight: 600, mb: theme.spacing(1) }}
        >
          {t("admin.panel.title")}
        </Typography>
        <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: theme.spacing(4) }}>
          {t("admin.panel.subtitle")}
        </Typography>

        {activeTool === null ? (
          <Stack spacing={2}>
            {cards.map((card) => (
              <Card key={card.id} variant="outlined">
                <CardActionArea onClick={card.onClick} data-testid={card.testId}>
                  <CardContent sx={{ display: "flex", alignItems: "center", gap: theme.spacing(2) }}>
                    {card.icon}
                    <Box>
                      <Typography variant="h6">{card.title}</Typography>
                      <Typography variant="body2" color="text.secondary">
                        {card.description}
                      </Typography>
                    </Box>
                  </CardContent>
                </CardActionArea>
              </Card>
            ))}
          </Stack>
        ) : (
          <Stack spacing={2}>
            <Button
              startIcon={<ArrowBackIcon />}
              onClick={() => setActiveTool(null)}
              sx={{ alignSelf: "flex-start" }}
              data-testid={DATA_TEST_ID.BACK_BUTTON}
            >
              {t("admin.panel.back")}
            </Button>
            {renderActiveTool()}
          </Stack>
        )}
      </Paper>
    </Box>
  );
};

export default AdminPanel;
