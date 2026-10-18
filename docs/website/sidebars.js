/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
  guide: [
    'intro',
    'course/path',
    {
      type: 'category',
      label: 'Start here',
      items: ['start/project', 'start/quickstart', 'start/reading-path', 'lab'],
    },
    {
      type: 'category',
      label: 'Foundations',
      items: [
        'foundations/what-is-compression',
        'foundations/bytes-and-bits',
        'foundations/probability',
        'foundations/prefix-codes',
        'foundations/arithmetic-coding',
      ],
    },
    {
      type: 'category',
      label: 'Algorithms in this repo',
      items: [
        'algorithms/huffman',
        'algorithms/lz77',
        'algorithms/byte-ppm',
        'algorithms/bit-ppm',
        'algorithms/ppmd',
        'algorithms/mixing',
        'algorithms/match',
        'algorithms/wikimix5',
        'course/synthesis',
      ],
    },
    {
      type: 'category',
      label: 'Codebase',
      items: [
        'codebase/overview',
        'codebase/map',
        'codebase/rust-primer',
        'codebase/flow',
        'codebase/lz77-walkthrough',
        'codebase/huffman-walkthrough',
        'codebase/ppm-walkthrough',
        'codebase/arithmetic-coder',
        'codebase/model-families',
        'codebase/archive-format',
      ],
    },
    {
      type: 'category',
      label: 'Contribute',
      items: ['contribute/onboarding', 'contribute/experiments'],
    },
    {
      type: 'category',
      label: 'Prize research',
      items: [
        'research/competitive-baseline',
        'research/native-parity',
        'research/experiment-playbook',
        'research/article-order',
        'research/link-context',
        'research/adaptive-depth',
        'research/weight-permutations',
      ],
    },
    {
      type: 'category',
      label: 'Reference',
      items: ['reference/codecs', 'reference/glossary'],
    },
  ],
};

module.exports = sidebars;
