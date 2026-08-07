const sidebar = [
  {
    text: 'Guide',
    items: [
      { text: 'Overview', link: '/guide/' },
      { text: 'Installation', link: '/guide/installation' },
      { text: 'Quick start', link: '/guide/quickstart' },
    ],
  },
  {
    text: 'Reference',
    items: [
      { text: 'Commands', link: '/reference/commands' },
      { text: 'PLAN.md', link: '/reference/plan-fields' },
      { text: 'Briefing', link: '/reference/chief-of-staff' },
      { text: 'A/B/C decisions', link: '/reference/decision-mode' },
      { text: 'Outcome contract', link: '/reference/outcome-choice' },
      { text: 'Native hosts', link: '/reference/native-hosts' },
      { text: 'Browser', link: '/reference/browser' },
      { text: 'Configuration', link: '/reference/config' },
      { text: 'Privacy', link: '/reference/privacy' },
    ],
  },
];

export default {
  title: 'Shadow',
  description: 'Chief-of-staff briefing, local role routing, and bounded native-host execution for AI coding work.',
  base: process.env.DOCS_BASE || '/',
  cleanUrls: true,
  themeConfig: {
    siteTitle: 'Shadow',
    nav: [
      { text: 'Guide', link: '/guide/' },
      { text: 'Reference', link: '/reference/' },
    ],
    sidebar: { '/': sidebar },
    socialLinks: [{ icon: 'github', link: 'https://github.com/firstbitelabsllc/shadow' }],
    search: { provider: 'local' },
    footer: { message: 'MIT licensed.', copyright: 'Copyright © 2026 First Bite Labs LLC' },
  },
};
