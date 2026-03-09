import {
  AlignmentType,
  BorderStyle,
  Header,
  ImageRun,
  Paragraph,
  Table,
  TableCell,
  TableRow,
  TextRun,
  VerticalAlign,
  WidthType,
} from "docx";
import { getBase64Image } from "src/experiences/report/util";
import { ReportContent } from "src/experiences/report/reportContent";

const LOGO_CONFIG = [
  { imageUrl: ReportContent.IMAGE_URLS.CAC_LOGO, width: 82, height: 20 },
  { imageUrl: ReportContent.IMAGE_URLS.CESSI_LOGO, width: 59, height: 20 },
  { imageUrl: ReportContent.IMAGE_URLS.INTEC_LOGO, width: 55, height: 20 },
  { imageUrl: ReportContent.IMAGE_URLS.MAXIMIA_LOGO, width: 78, height: 20 },
  { imageUrl: ReportContent.IMAGE_URLS.TALENTS_CO_LOGO, width: 91, height: 20 },
  { imageUrl: ReportContent.IMAGE_URLS.UIPBA_LOGO, width: 64, height: 20 },
  { imageUrl: ReportContent.IMAGE_URLS.UNAJE_LOGO, width: 85, height: 20 },
  { imageUrl: ReportContent.IMAGE_URLS.VISTAGE_LOGO, width: 63, height: 12 },
];

const NO_BORDER = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const NO_BORDERS = { top: NO_BORDER, bottom: NO_BORDER, left: NO_BORDER, right: NO_BORDER };

const HeaderComponent = async () => {
  const imageRuns: ImageRun[] = [];

  for (const logo of LOGO_CONFIG) {
    imageRuns.push(
      new ImageRun({
        data: await getBase64Image(logo.imageUrl),
        transformation: { width: logo.width, height: logo.height },
      })
    );
  }

  const makeCell = (imageRun: ImageRun) =>
    new TableCell({
      children: [
        new Paragraph({
          children: [imageRun],
          alignment: AlignmentType.CENTER,
          spacing: { before: 80, after: 80 },
        }),
      ],
      borders: NO_BORDERS,
      width: { size: 25, type: WidthType.PERCENTAGE },
      verticalAlign: VerticalAlign.CENTER,
    });

  const logoTable = new Table({
    rows: [
      new TableRow({ children: imageRuns.slice(0, 4).map(makeCell) }),
      new TableRow({ children: imageRuns.slice(4, 8).map(makeCell) }),
    ],
    width: { size: 75, type: WidthType.PERCENTAGE },
    alignment: AlignmentType.CENTER,
  });

  return new Header({
    children: [
      new Paragraph({
        children: [
          new TextRun({
            text: "Plataforma validada por",
            italics: true,
            size: 16,
            color: "888888",
          }),
        ],
        alignment: AlignmentType.LEFT,
        spacing: { after: 120 },
      }),
      logoTable,
      new Paragraph({ spacing: { before: 300 } }),
    ],
  });
};

export default HeaderComponent;
