import { h } from "vue";
import type { Theme } from "vitepress";
import DefaultTheme from "vitepress/theme";
import Breadcrumbs from "./components/Breadcrumbs.vue";
import LandingHome from "./components/LandingHome.vue";
import "./custom.css";

export default {
  extends: DefaultTheme,
  Layout: () =>
    h(DefaultTheme.Layout, null, { "doc-before": () => h(Breadcrumbs) }),
  enhanceApp({ app }) {
    app.component("LandingHome", LandingHome);
  },
} satisfies Theme;
