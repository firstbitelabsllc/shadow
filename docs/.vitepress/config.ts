import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Shadow',
  description:
    'One durable workboard per computer, PLAN.md per project, atomic claims and proof receipts — stop any AI coding chat and resume without losing the work',
  base: process.env.DOCS_BASE || '/',
  srcExclude: ['plan-archive/**', 'superpowers/**'],
  themeConfig: {
    outline: { level: [2, 3], label: 'On this page' },
    nav: [
      { text: 'Guide', link: '/guide/installation' },
      { text: 'Reference', link: '/reference/commands' },
      { text: 'GitHub', link: 'https://github.com/firstbitelabsllc/shadow' },
    ],
    sidebar: {
      '/guide/': [
        {
          text: 'Guide',
          items: [
            { text: 'Installation', link: '/guide/installation' },
            { text: 'Quick start', link: '/guide/quickstart' },
            { text: 'Other-computer handoff', link: '/guide/other-computer-handoff' },
            { text: 'Use Shadow in more places', link: '/guide/publishing' },
          ],
        },
      ],
      '/reference/': [
        {
          text: 'Core',
          items: [
            { text: 'Commands', link: '/reference/commands' },
            { text: 'Method', link: '/reference/method' },
          ],
        },
        {
          text: 'Plans',
          collapsed: true,
          items: [
            { text: 'Plan grammar', link: '/reference/grammar' },
            { text: 'Plan scale', link: '/reference/plan-scale' },
            { text: 'Amp', link: '/reference/amp' },
          ],
        },
        {
          text: 'Extending',
          collapsed: true,
          items: [
            { text: 'Extensions', link: '/reference/slots' },
            { text: 'Config', link: '/reference/config' },
          ],
        },
        {
          text: 'Hosts',
          collapsed: true,
          items: [
            { text: 'Host integration', link: '/reference/host-integration' },
            { text: 'Native hosts', link: '/reference/native-hosts' },
          ],
        },
        {
          text: 'Surfaces',
          collapsed: true,
          items: [
            { text: 'Browser', link: '/reference/browser' },
            { text: 'Decision mode', link: '/reference/decision-mode' },
            { text: 'Outcome choice', link: '/reference/outcome-choice' },
            { text: 'Chief of staff', link: '/reference/chief-of-staff' },
          ],
        },
        {
          text: 'Operations',
          collapsed: true,
          items: [
            { text: 'Telemetry', link: '/reference/telemetry' },
            { text: 'Privacy', link: '/reference/privacy' },
          ],
        },
      ],
    },
  },
})
