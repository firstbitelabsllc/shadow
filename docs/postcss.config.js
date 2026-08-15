// Empty PostCSS config to override any parent project config
// This prevents VitePress from loading PostCSS configs from parent directories
// docs/package.json declares "type": "module", so this file must be ESM.
export default {
  plugins: []
}