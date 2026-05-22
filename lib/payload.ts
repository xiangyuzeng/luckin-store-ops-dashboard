// Static payload loader. The JSON is bundled at build time — Vercel never touches a DB.
// Importing as JSON would force Next to inline ~620 KB into the JS bundle, which is fine for a
// static client app, but we wrap it in a typed accessor so consumers see a frozen object.

import payloadJson from '@/data/payload.json';
import type { Payload } from '@/lib/types';

let cached: Payload | null = null;

export function loadPayload(): Payload {
  if (cached) return cached;
  cached = payloadJson as unknown as Payload;
  return cached;
}
