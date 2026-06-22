import { NextResponse } from "next/server";

/**
 * Thin upload proxy: the browser posts the swing video here (same-origin, clean
 * CORS) and we forward the multipart body to the stateless FastAPI `/analyze`
 * service. The backend URL stays server-side; nothing is persisted here.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function backendUrl(): string {
  const base =
    process.env.API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000";
  return `${base.replace(/\/$/, "")}/analyze`;
}

export async function POST(request: Request): Promise<Response> {
  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return NextResponse.json(
      { error: "Expected a multipart/form-data upload." },
      { status: 400 },
    );
  }

  try {
    const upstream = await fetch(backendUrl(), {
      method: "POST",
      body: form,
    });

    const body = await upstream.text();
    return new NextResponse(body, {
      status: upstream.status,
      headers: {
        "content-type":
          upstream.headers.get("content-type") ?? "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      { error: "The analysis service is unavailable. Please try again." },
      { status: 502 },
    );
  }
}
