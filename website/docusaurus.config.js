const path = require('node:path');

const repositoryRoot = path.resolve(__dirname, '..');

/** @type {import('@docusaurus/types').Config} */
module.exports = {
  title: 'rapid-ship',
  tagline: 'Ship more. Supervise less.',
  url: 'https://proxy-hatch.github.io',
  baseUrl: '/rapid-ship/',
  organizationName: 'proxy-hatch',
  projectName: 'rapid-ship',
  trailingSlash: true,
  onBrokenLinks: 'throw',
  onBrokenAnchors: 'throw',
  staticDirectories: ['../asset'],
  markdown: {
    format: 'md',
    hooks: {
      onBrokenMarkdownLinks: 'throw',
      onBrokenMarkdownImages: 'throw',
    },
    async parseFrontMatter(params) {
      const result = await params.defaultParseFrontMatter(params);
      // Supply site metadata without adding website-only fields to GitHub docs.
      if (params.filePath === path.join(repositoryRoot, 'README.md')) {
        Object.assign(result.frontMatter, {
          title: 'rapid-ship',
          sidebar_label: 'Start here',
          slug: '/',
          hide_title: true,
        });
      } else if (params.filePath === path.join(repositoryRoot, 'ARCHITECTURE.md')) {
        Object.assign(result.frontMatter, {slug: '/architecture'});
      }
      return result;
    },
  },
  presets: [
    [
      '@docusaurus/preset-classic',
      {
        docs: {
          path: '..',
          include: ['README.md', 'ARCHITECTURE.md', 'docs/**/*.md'],
          routeBasePath: '/',
          sidebarPath: './sidebars.js',
          editUrl: ({docPath}) =>
            `https://github.com/proxy-hatch/rapid-ship/edit/main/${docPath}`,
          numberPrefixParser: false,
        },
        blog: false,
        theme: {customCss: './src/css/custom.css'},
      },
    ],
  ],
  themeConfig: {
    colorMode: {respectPrefersColorScheme: true},
    navbar: {
      title: 'rapid-ship',
      logo: {alt: 'rapid-ship boat', src: 'logo.jpeg'},
      items: [
        {type: 'doc', docId: 'README', label: 'Get started', position: 'left'},
        {type: 'doc', docId: 'ARCHITECTURE', label: 'Architecture', position: 'left'},
        {href: 'https://github.com/proxy-hatch/rapid-ship', label: 'GitHub', position: 'right'},
      ],
    },
    footer: {
      style: 'light',
      copyright: 'rapid-ship · Early preview. Build trust before adding autonomy.',
    },
  },
};
