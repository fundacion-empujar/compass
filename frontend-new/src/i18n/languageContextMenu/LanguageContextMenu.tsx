import { LanguageOutlined } from "@mui/icons-material";
import PrimaryIconButton from "src/theme/PrimaryIconButton/PrimaryIconButton";
import React, { useCallback, useMemo, useState } from "react";
import { useTheme } from "@mui/material";
import ContextMenu from "src/theme/ContextMenu/ContextMenu";
import { useTranslation } from "react-i18next";
import { parseEnvSupportedLocales } from "src/i18n/languageContextMenu/parseEnvSupportedLocales";
import { Locale } from "src/i18n/constants";
import { MenuItemConfig } from "src/theme/ContextMenu/menuItemConfig.types";

const uniqueId = "f4d06e4b-0e0c-49c7-ad93-924c5ac89070";

export const DATA_TEST_ID = {
  AUTH_LANGUAGE_SELECTOR_BUTTON: `auth-language-selector-${uniqueId}`,
  AUTH_ENGLISH_SELECTOR_BUTTON: `auth-english-selector-${uniqueId}`,
  AUTH_SPANISH_SELECTOR_BUTTON: `auth-spanish-selector-${uniqueId}`,
  AUTH_FRENCH_SELECTOR_BUTTON: `auth-french-selector-${uniqueId}`,
};

export const MENU_ITEM_ID = {
  AUTH_ENGLISH_SELECTOR: `english-selector-${uniqueId}`,
  AUTH_SPANISH_SELECTOR: `spanish-selector-${uniqueId}`,
  AUTH_FRENCH_SELECTOR: `french-selector-${uniqueId}`,
};

export const MENU_ITEM_TEXT = {
  ENGLISH_UK: `English (UK)`,
  ENGLISH_US: `English (US)`,
  SPANISH_ES: `Español (España)`,
  SPANISH_AR: `Español (Argentina)`,
};

export type LanguageContextMenuProps = {
  /** If true, removes the margin from the button to allow consistent spacing in different contexts */
  removeMargin?: boolean;
};

const LanguageContextMenu: React.FC<LanguageContextMenuProps> = ({ removeMargin = false }) => {
  const theme = useTheme();
  const { t, i18n } = useTranslation();

  // --- Parse supported languages from environment config
  const supportedLanguages = useMemo(() => {
    return parseEnvSupportedLocales();
  }, []);

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
  };

  // --- Define all possible menu items
  const allMenuItems: MenuItemConfig[] = [
    {
      id: `language-context-menu-${uniqueId}-${Locale.EN_GB}`,
      text: MENU_ITEM_TEXT.ENGLISH_UK,
      disabled: !supportedLanguages.includes(Locale.EN_GB),
      action: () => changeLanguage(Locale.EN_GB),
    },
    {
      id: `language-context-menu-${uniqueId}-${Locale.EN_US}`,
      text: MENU_ITEM_TEXT.ENGLISH_US,
      disabled: !supportedLanguages.includes(Locale.EN_US),
      action: () => changeLanguage(Locale.EN_US),
    },
    {
      id: `language-context-menu-${uniqueId}-${Locale.ES_ES}`,
      text: MENU_ITEM_TEXT.SPANISH_ES,
      disabled: !supportedLanguages.includes(Locale.ES_ES),
      action: () => changeLanguage(Locale.ES_ES),
    },
    {
      id: `language-context-menu-${uniqueId}-${Locale.ES_AR}`,
      text: MENU_ITEM_TEXT.SPANISH_AR,
      disabled: !supportedLanguages.includes(Locale.ES_AR),
      action: () => changeLanguage(Locale.ES_AR),
    }
  ];

  // --- Filter out languages that are disabled
  let visibleMenuItems = allMenuItems.filter(item => !item.disabled);


  // --- Ensure at least English is included if nothing is present
  if (visibleMenuItems.length === 0) {
    const englishItem = allMenuItems.find(item => item.text === MENU_ITEM_TEXT.ENGLISH_UK);
    if (englishItem) visibleMenuItems = [englishItem];
  }

  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  return (
    <>
      <PrimaryIconButton
        sx={{
          color: theme.palette.common.black,
          alignSelf: "flex-start",
          justifySelf: "flex-end",
          margin: removeMargin ? 0 : theme.tabiyaSpacing.lg,
        }}
        onClick={(event) => setAnchorEl(event.currentTarget)}
        data-testid={DATA_TEST_ID.AUTH_LANGUAGE_SELECTOR_BUTTON}
        title={t("i18n.languageContextMenu.selector")}
      >
        <LanguageOutlined />
      </PrimaryIconButton>

      <ContextMenu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        notifyOnClose={() => setAnchorEl(null)}
        items={visibleMenuItems}
      />
    </>
  );
};

export default LanguageContextMenu;
