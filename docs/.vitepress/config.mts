import { defineConfig } from 'vitepress'

// Project site on GitHub Pages, so every absolute path is prefixed with the repo name.
// Change `base` to '/' if this ever moves to a user site or a custom domain.
const base = '/harbor-dev/'

export default defineConfig({
  title: 'HARBOR',
  description: 'A harness framework for agentic robot reinforcement learning. Point it at a simulator, describe a task, get a trained policy.',
  base,
  lang: 'en-US',
  cleanUrls: true,
  lastUpdated: true,
  ignoreDeadLinks: false,

  // The concepts page states the MDP and the harness tuple; both read far better set than
  // spelled out in prose. Requires markdown-it-mathjax3, which package.json pins.
  markdown: { math: true },

  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: `${base}favicon.svg` }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:title', content: 'HARBOR — agentic robot reinforcement learning' }],
    ['meta', { property: 'og:description', content: 'Point it at a simulator. Describe a task. Get a trained policy.' }],
    ['meta', { property: 'og:image', content: `${base}social-preview.png` }],
    ['meta', { name: 'twitter:card', content: 'summary_large_image' }],
  ],

  themeConfig: {
    logo: { light: '/logo.svg', dark: '/logo-dark.svg' },
    siteTitle: 'HARBOR',

    nav: [
      { text: 'Guide', link: '/guide/', activeMatch: '/guide/' },
      { text: 'Paper', link: 'https://arxiv.org/abs/2606.08610' },
    ],

    // One section. Concepts and the generated reference live under /guide/ too, so the
    // sidebar is the whole map of the site and nothing hides behind a second nav entry.
    sidebar: {
      '/guide/': [
        {
          text: 'Getting started',
          items: [
            { text: 'What is HARBOR?', link: '/guide/' },
            { text: 'Installation', link: '/guide/install' },
            { text: 'Your first benchmark', link: '/guide/first-benchmark' },
          ],
        },
        {
          text: 'Workflows',
          items: [
            { text: 'Authoring tasks', link: '/guide/tasks' },
            { text: 'Tuning rewards', link: '/guide/rewards' },
            { text: 'Training and tuning', link: '/guide/training' },
          ],
        },
        {
          text: 'Concepts',
          items: [
            { text: 'The harness', link: '/guide/harness' },
            { text: 'Gates', link: '/guide/gates' },
            { text: 'Your workspace', link: '/guide/workspace' },
          ],
        },
        {
          text: 'Reference',
          items: [
            { text: 'Commands', link: '/guide/commands' },
            { text: 'Agents', link: '/guide/agents' },
          ],
        },
      ],
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/supersglzc/harbor-dev' },
    ],

    search: { provider: 'local' },

    editLink: {
      pattern: 'https://github.com/supersglzc/harbor-dev/edit/main/docs/:path',
      text: 'Edit this page on GitHub',
    },

    footer: {
      message: 'Released under the Apache 2.0 License.',
      copyright: 'Copyright © 2026 The HARBOR Authors',
    },

    outline: [2, 3],
  },
})
