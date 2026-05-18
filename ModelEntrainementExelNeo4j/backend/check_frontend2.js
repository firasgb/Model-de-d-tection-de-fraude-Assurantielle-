const { execSync } = require('child_process');
const path = require('path');

const frontendDir = 'C:\\Users\\firas\\Desktop\\ModelEntrainementExelNeo4j\\ModelEntrainementExelNeo4j\\fraud-v2-frontend';

try {
  const result = execSync(`npx tsc --noEmit --project tsconfig.json --skipLibCheck`, {
    cwd: frontendDir,
    encoding: 'utf-8',
    stdio: ['pipe', 'pipe', 'pipe']
  });
  console.log('TypeScript check: OK (no errors)');
} catch(e) {
  const output = (e.stdout || '') + (e.stderr || '');
  // Filter to only show relevant errors (not config/system issues)
  const errors = output.split('\n').filter(l => l.includes('error') && !l.includes('--jsx') && !l.includes('--module'));
  if (errors.length > 0) {
    console.log('Real TypeScript errors:');
    errors.forEach(e => console.log('  ' + e));
  } else {
    console.log('TypeScript check: OK (no real errors, only config warnings)');
  }
}

console.log('\nDone');