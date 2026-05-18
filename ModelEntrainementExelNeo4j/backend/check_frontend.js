const { execSync } = require('child_process');
const path = require('path');

const frontendDir = 'C:\\Users\\firas\\Desktop\\ModelEntrainementExelNeo4j\\ModelEntrainementExelNeo4j\\fraud-v2-frontend';

try {
  // Check TypeScript compilation
  const result = execSync(`npx tsc --noEmit --skipLibCheck src/components/ThresholdEditor.tsx src/components/GroupWeightsEditor.tsx src/components/ConfigPanel.tsx`, {
    cwd: frontendDir,
    encoding: 'utf-8',
    stdio: ['pipe', 'pipe', 'pipe']
  });
  console.log('TypeScript check: OK');
  console.log(result.stdout || '');
} catch(e) {
  console.log('TypeScript errors:');
  console.log(e.stdout || '');
  console.log(e.stderr || '');
}

try {
  // Check Vite can parse the file
  const result = execSync(`npx vite build --mode check 2>&1 | head -30`, {
    cwd: frontendDir,
    encoding: 'utf-8',
    stdio: ['pipe', 'pipe', 'pipe']
  });
  console.log('Vite build check: OK');
  console.log(result.stdout || '');
} catch(e) {
  console.log('Vite build errors:');
  console.log((e.stdout || '') + (e.stderr || ''));
}

console.log('\nDone');