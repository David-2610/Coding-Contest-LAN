import {build} from 'esbuild';
import {fileURLToPath} from 'node:url';
await build({
  absWorkingDir:fileURLToPath(new URL('.',import.meta.url)),
  entryPoints:['src/site.jsx'],
  bundle:true,
  minify:true,
  outfile:'dist/workspace.js'
});
