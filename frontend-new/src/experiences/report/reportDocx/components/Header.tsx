import { AlignmentType, Header, ImageRun, Paragraph, TextRun } from "docx";
import { getBase64Image } from "src/experiences/report/util";
import { ReportContent } from "src/experiences/report/reportContent";

const LOGO_SPACER = "\u00A0\u00A0";

const LOGO_CONFIG = [
  { imageUrl: ReportContent.IMAGE_URLS.INTEC_LOGO, width: 83, height: 40 },
  { imageUrl: ReportContent.IMAGE_URLS.CESSI_LOGO, width: 77, height: 40 },
  { imageUrl: ReportContent.IMAGE_URLS.CAC_LOGO, width: 55, height: 55 },
  { imageUrl: ReportContent.IMAGE_URLS.VISTAGE_LOGO, width: 40, height: 40 },
  { imageUrl: ReportContent.IMAGE_URLS.UNAJE_LOGO, width: 40, height: 40 },
  { imageUrl: ReportContent.IMAGE_URLS.MAXIMIA_LOGO, width: 71, height: 40 },
  { imageUrl: ReportContent.IMAGE_URLS.TALENTS_CO_LOGO, width: 71, height: 40 },
  { imageUrl: ReportContent.IMAGE_URLS.UIPBA_LOGO, width: 110, height: 40 },
];

const HeaderComponent = async () => {
  const logoRuns: Array<ImageRun | TextRun> = [];

  for (const [index, logo] of LOGO_CONFIG.entries()) {
    logoRuns.push(
      new ImageRun({
        data: await getBase64Image(logo.imageUrl),
        transformation: { width: logo.width, height: logo.height },
      })
    );
    if (index < LOGO_CONFIG.length - 1) {
      logoRuns.push(new TextRun({ text: LOGO_SPACER }));
    }
  }

  return new Header({
    children: [
      new Paragraph({
        children: logoRuns,
        alignment: AlignmentType.LEFT,
        spacing: { after: 300 },
      }),
    ],
  });
};

export default HeaderComponent;
