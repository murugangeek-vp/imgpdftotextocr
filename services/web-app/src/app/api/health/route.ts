import { NextResponse } from 'next/server';

/**
 * Health check endpoint for Docker healthcheck and load balancer probes.
 * GET /api/health → 200 OK
 */
export async function GET() {
  return NextResponse.json(
    { status: 'ok', service: 'ocr-platform-web', timestamp: new Date().toISOString() },
    { status: 200 }
  );
}
