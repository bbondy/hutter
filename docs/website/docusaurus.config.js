const repository = 'https://github.com/bbondy/hutter';

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'Hutter compression guide',
  tagline: 'Lossless compression, Rust implementations, and Hutter Prize research',
  url: 'https://bbondy.github.io',
  baseUrl: '/hutter/',
  favicon: 'img/hutter-project-logo.png',
  organizationName: 'bbondy',
  projectName: 'hutter',
  onBrokenLinks: 'throw',
  onBrokenAnchors: 'throw',
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'throw',
    },
  },
  presets: [
    [
      '@docusaurus/preset-classic',
      {
        docs: {
          routeBasePath: '/',
          sidebarPath: require.resolve('./sidebars.js'),
          editUrl: `${repository}/edit/main/docs/website/`,
        },
        blog: false,
        theme: {
          customCss: require.resolve('./src/css/custom.css'),
        },
      },
    ],
  ],
  themeConfig: {
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'Hutter compression guide',
      logo: {alt: 'Hutter project logo', src: 'img/hutter-project-logo.png'},
      items: [
        {type: 'docSidebar', sidebarId: 'guide', label: 'Guide', position: 'left'},
        {to: '/course/path', label: 'Course', position: 'left'},
        {to: '/start/quickstart', label: 'Start here', position: 'left'},
        {to: '/lab', label: 'Examples', position: 'left'},
        {to: '/codebase/overview', label: 'Codebase', position: 'left'},
        {to: '/research/competitive-baseline', label: 'Prize research', position: 'left'},
        {href: repository, label: 'GitHub', position: 'right'},
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Learn',
          items: [
            {label: 'First steps', to: '/start/quickstart'},
            {label: 'Compression basics', to: '/foundations/what-is-compression'},
            {label: 'Interactive examples', to: '/lab'},
          ],
        },
        {
          title: 'Build',
          items: [
            {label: 'Codebase overview', to: '/codebase/overview'},
            {label: 'Contributing', to: '/contribute/onboarding'},
            {label: 'Codec reference', to: '/reference/codecs'},
            {label: 'Prize research', to: '/research/competitive-baseline'},
          ],
        },
        {
          title: 'Project',
          items: [
            {label: 'Source on GitHub', href: repository},
            {label: 'License scope', href: `${repository}/blob/research/native-mac/LICENSE-SCOPE.md`},
          ],
        },
      ],
      copyright: 'Hutter compression experiments · licenses vary by component',
    },
    prism: {
      additionalLanguages: ['bash', 'rust', 'toml'],
    },
  },
};

module.exports = config;
