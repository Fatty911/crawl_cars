const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Max-Age": "86400"
};

function json(data, init = {}) {
  return new Response(JSON.stringify(data), {
    ...init,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...corsHeaders,
      ...(init.headers || {})
    }
  });
}

function normalizeSyncId(syncId) {
  return String(syncId || "").trim().replace(/[^a-zA-Z0-9_-]/g, "").slice(0, 80);
}

async function readHistories(env, syncId) {
  const raw = await env.FILTER_HISTORY.get(`history:${syncId}`);
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed.histories) ? parsed.histories : [];
  } catch (_error) {
    return [];
  }
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    const url = new URL(request.url);
    if (!url.pathname.endsWith("/filter-history") && url.pathname !== "/") {
      return json({ error: "not_found" }, { status: 404 });
    }

    if (request.method === "GET") {
      const syncId = normalizeSyncId(url.searchParams.get("syncId"));
      if (!syncId) {
        return json({ histories: [] });
      }
      return json({ syncId, histories: await readHistories(env, syncId) });
    }

    if (request.method === "POST") {
      const body = await request.json().catch(() => ({}));
      const syncId = normalizeSyncId(body.syncId);
      if (!syncId || !body.history || typeof body.history !== "object") {
        return json({ error: "bad_request" }, { status: 400 });
      }

      const histories = await readHistories(env, syncId);
      const next = {
        id: String(body.history.id || Date.now()),
        name: String(body.history.name || "自定义筛选").slice(0, 80),
        state: body.history.state || {},
        resultCount: Number(body.history.resultCount || 0),
        createdAt: body.history.createdAt || new Date().toISOString()
      };
      histories.push(next);
      const clipped = histories.slice(-50);
      await env.FILTER_HISTORY.put(
        `history:${syncId}`,
        JSON.stringify({ histories: clipped, updatedAt: new Date().toISOString() })
      );
      return json({ syncId, histories: clipped });
    }

    return json({ error: "method_not_allowed" }, { status: 405 });
  }
};
