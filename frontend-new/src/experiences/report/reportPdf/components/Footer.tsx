import React from "react";
import styles from "src/experiences/report/reportPdf/styles";
import { View, Text, Image } from "@react-pdf/renderer";
import { getBase64Image } from "src/experiences/report/util";
import { ReportContent } from "src/experiences/report/reportContent";

const Footer: React.FC = () => (
  <View fixed style={styles.footer}>
    <Text x={0} y={0} style={styles.footerLogoTitle}>
      Iniciativa desarrollada por
    </Text>
    <View style={styles.footerLogoRow}>
      <Image src={getBase64Image(ReportContent.IMAGE_URLS.COMPASS_LOGO)} style={styles.footerImage} source={undefined} />
      <Image src={getBase64Image(ReportContent.IMAGE_URLS.OXFORD_LOGO)} style={styles.footerImage} source={undefined} />
      <Image src={getBase64Image(ReportContent.IMAGE_URLS.YOUTH_INNOVATION_FUND_LOGO)} style={styles.footerImage} source={undefined} />
      <Image src={getBase64Image(ReportContent.IMAGE_URLS.EMPUJAR_LOGO)} style={styles.footerImage} source={undefined} />
    </View>
    <Text
      x={0}
      y={0}
      style={styles.pageNumber}
      render={({ pageNumber, totalPages }) => `${pageNumber} / ${totalPages}`}
    />
  </View>
);

export default Footer;
