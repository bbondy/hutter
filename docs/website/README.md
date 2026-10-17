# Compression guide website

This is the Docusaurus course for [Hutter compression experiments](https://github.com/bbondy/hutter). The [course sequence](docs/course/path.md) orders the concepts from bytes and lossless reconstruction through the codecs, then separates source-code reading and contributor material. Chapters use worked explanations rather than exercises. The interactive examples are simplified; the Rust source defines the actual codecs.

## Run locally

Requires Node.js 20 or newer and npm.

```sh
cd docs/website
npm ci
npm run start
```

`npm run build` creates the static site in `docs/website/build` and checks internal links. `npm run serve` serves a completed build. The site is configured for `https://bbondy.github.io/hutter/`, including its `/hutter/` base path.

## Publish with GitHub Pages

The repository workflow at `.github/workflows/docs.yml` builds on pushes to `main`, uploads the static build, and deploys it through GitHub Pages. Pull requests run the build check without deployment.

The repository's Pages build type is configured as **GitHub Actions**. A push that brings this site and workflow to `main` will build and deploy it. The generated site is hosted under `/hutter/`; no `gh-pages` branch or manual copy of build output is needed. For a fork, select **GitHub Actions** under **Settings → Pages → Build and deployment** and adjust `url` and `baseUrl` in `docusaurus.config.js`.

To add a lesson, create a file in `docs/`, add its ID to `sidebars.js`, and link it from the relevant neighboring page. Keep examples small and make claims about codec behavior checkable against the source. Run `npm run build` before merging.
