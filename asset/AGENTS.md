# Brand assets

[public/](public/) contains the banner and logo served by the documentation website. This small resource folder inherits this guide.

Use the [branding reference](../docs/branding.md) when replacing images. Keep the README's image links and the website's logo reference consistent with the filenames.

The website copies only `public/` into its static output. Keep maintainer instructions here so they do not become public site assets. Validate asset changes with `npm --prefix website run build`.
