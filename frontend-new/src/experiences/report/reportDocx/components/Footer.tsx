import { Footer, Paragraph, AlignmentType, TextRun, ImageRun, PageNumber } from "docx";
import { getBase64Image } from "src/experiences/report/util";
import { ReportContent } from "src/experiences/report/reportContent";

const LOGO_SPACER = "\u00A0\u00A0\u00A0";

const FOOTER_LOGO_CONFIG = [
  { imageUrl: ReportContent.IMAGE_URLS.COMPASS_LOGO, width: 99, height: 24 },
  { imageUrl: ReportContent.IMAGE_URLS.EMPUJAR_LOGO, width: 72, height: 24 },
  { imageUrl: ReportContent.IMAGE_URLS.OXFORD_LOGO, width: 83, height: 24 },
  { imageUrl: ReportContent.IMAGE_URLS.YOUTH_INNOVATION_FUND_LOGO, width: 71, height: 24 },
];

const FooterComponent = async () => {
  const logoRuns: Array<ImageRun | TextRun> = [];

  for (const [index, logo] of FOOTER_LOGO_CONFIG.entries()) {
    logoRuns.push(
      new ImageRun({
        data: await getBase64Image(logo.imageUrl),
        transformation: { width: logo.width, height: logo.height },
      })
    );
    if (index < FOOTER_LOGO_CONFIG.length - 1) {
      logoRuns.push(new TextRun({ text: LOGO_SPACER }));
    }
  }

  return new Footer({
    children: [
      new Paragraph({
        children: [
          new TextRun({
            text: "Iniciativa desarrollada por",
            italics: true,
            size: 14,
            color: "888888",
          }),
        ],
        alignment: AlignmentType.LEFT,
        spacing: { after: 80 },
      }),
      new Paragraph({
        children: logoRuns,
        alignment: AlignmentType.CENTER,
        spacing: { after: 100 },
      }),
      new Paragraph({
        children: [
          new TextRun({
            children: [PageNumber.CURRENT, "/", PageNumber.TOTAL_PAGES],
          }),
        ],
        alignment: AlignmentType.CENTER,
        spacing: { before: 100 },
      }),
    ],
  });
};

export default FooterComponent;
