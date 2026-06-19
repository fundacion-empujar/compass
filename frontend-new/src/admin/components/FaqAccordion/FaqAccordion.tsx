import React from "react";
import { Accordion, AccordionSummary, AccordionDetails, Typography, Stack } from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";

const uniqueId = "a4f1c2d3-5b6e-4a70-9c8d-faqaccordion01";

export const DATA_TEST_ID = {
  FAQ_ACCORDION: `faq-accordion-${uniqueId}`,
};

export interface FaqItem {
  id: string;
  question: string;
  answer: React.ReactNode;
}

interface FaqAccordionProps {
  items: FaqItem[];
  testId?: string;
}

/**
 * Collapsed-by-default help panels. One item per tool keeps the panel uncluttered for
 * low-tech staff; the General-FAQ tool passes several. String answers honour line breaks.
 */
const FaqAccordion: React.FC<FaqAccordionProps> = ({ items, testId }) => {
  return (
    <Stack spacing={1} data-testid={testId ?? DATA_TEST_ID.FAQ_ACCORDION} sx={{ mt: 1 }}>
      {items.map((item) => (
        <Accordion
          key={item.id}
          disableGutters
          elevation={0}
          sx={{
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 1,
            "&:before": { display: "none" },
          }}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />} data-testid={`faq-summary-${item.id}`}>
            <Stack direction="row" spacing={1} alignItems="center">
              <HelpOutlineIcon fontSize="small" color="action" />
              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                {item.question}
              </Typography>
            </Stack>
          </AccordionSummary>
          <AccordionDetails data-testid={`faq-details-${item.id}`}>
            {typeof item.answer === "string" ? (
              <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: "pre-line" }}>
                {item.answer}
              </Typography>
            ) : (
              item.answer
            )}
          </AccordionDetails>
        </Accordion>
      ))}
    </Stack>
  );
};

export default FaqAccordion;
