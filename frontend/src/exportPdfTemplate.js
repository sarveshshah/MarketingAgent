/**
 * Builds a self-contained HTML document from a rendered markdown report
 * for server-side PDF generation via Playwright.
 *
 * The template embeds all CSS inline so Playwright can render it
 * without external dependencies (except Google Fonts CDN).
 */

export function buildExportHtml(markdownHtml, meta = {}) {
    const title = meta.campaignType
        ? `${meta.campaignType} — Marketing Strategy`
        : 'Marketing Strategy Report';

    const date = new Date().toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
    });

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${escapeHtml(title)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@600;700&display=swap" rel="stylesheet" />
  <style>
    /* ── Reset & Base ────────────────────────────────── */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      font-size: 11pt;
      line-height: 1.7;
      color: #1A1714;
      background: #FFFFFF;
      -webkit-font-smoothing: antialiased;
    }

    /* ── Page / Print ────────────────────────────────── */
    @page {
      size: A4;
      margin: 20mm 15mm;
    }

    @media print {
      body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
      .page-break { page-break-before: always; }
      h1, h2, h3 { page-break-after: avoid; }
      table, figure, pre { page-break-inside: avoid; }
    }

    /* ── Header ──────────────────────────────────────── */
    .pdf-header {
      text-align: center;
      padding-bottom: 24px;
      margin-bottom: 32px;
      border-bottom: 2px solid #0061FF;
    }
    .pdf-header h1 {
      font-family: 'Outfit', system-ui, sans-serif;
      font-size: 22pt;
      font-weight: 700;
      color: #1A1714;
      margin-bottom: 6px;
    }
    .pdf-header .meta {
      font-size: 9pt;
      color: #6B6860;
      letter-spacing: 0.03em;
    }

    /* ── Content ─────────────────────────────────────── */
    .content {
      max-width: 100%;
    }

    .content h1 {
      font-family: 'Outfit', system-ui, sans-serif;
      font-size: 20pt;
      font-weight: 700;
      color: #1A1714;
      margin: 32px 0 16px;
      letter-spacing: -0.01em;
    }

    .content h2 {
      font-family: 'Outfit', system-ui, sans-serif;
      font-size: 15pt;
      font-weight: 600;
      color: #1A1714;
      margin: 28px 0 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid rgba(0, 97, 255, 0.25);
    }

    .content h3 {
      font-size: 12pt;
      font-weight: 600;
      color: #0061FF;
      margin: 20px 0 8px;
    }

    .content p {
      color: #6B6860;
      margin: 8px 0;
    }

    .content ul, .content ol {
      color: #6B6860;
      padding-left: 24px;
      margin: 8px 0;
    }

    .content li {
      margin: 4px 0;
    }

    .content strong {
      color: #1A1714;
      font-weight: 600;
    }

    .content em {
      color: #0061FF;
      font-style: italic;
    }

    /* ── Tables ──────────────────────────────────────── */
    .content table {
      width: 100%;
      border-collapse: collapse;
      margin: 16px 0;
      font-size: 10pt;
    }

    .content th {
      background: #F5F3F0;
      color: #1A1714;
      font-weight: 600;
      text-align: left;
      padding: 10px 14px;
      border: 1px solid #E8E3DB;
    }

    .content td {
      padding: 10px 14px;
      border: 1px solid #E8E3DB;
      color: #6B6860;
    }

    .content tr:nth-child(even) td {
      background: #FAFAF8;
    }

    /* ── Code ────────────────────────────────────────── */
    .content code {
      font-family: 'SF Mono', 'Fira Code', monospace;
      font-size: 9.5pt;
      background: #F5F3F0;
      color: #0061FF;
      padding: 2px 6px;
      border-radius: 4px;
    }

    .content pre {
      background: #F5F3F0;
      border: 1px solid #E8E3DB;
      border-radius: 8px;
      padding: 16px;
      overflow-x: auto;
      margin: 12px 0;
    }

    .content pre code {
      background: none;
      padding: 0;
      color: #1A1714;
    }

    /* ── Blockquotes ─────────────────────────────────── */
    .content blockquote {
      border-left: 3px solid #0061FF;
      padding: 8px 16px;
      margin: 12px 0;
      background: #F0F6FF;
      color: #6B6860;
      border-radius: 0 6px 6px 0;
    }

    /* ── Horizontal rule ─────────────────────────────── */
    .content hr {
      border: none;
      border-top: 1px solid #E8E3DB;
      margin: 24px 0;
    }

    /* ── Footer ──────────────────────────────────────── */
    .pdf-footer {
      margin-top: 40px;
      padding-top: 16px;
      border-top: 1px solid #E8E3DB;
      text-align: center;
      font-size: 8pt;
      color: #A89F94;
    }
  </style>
</head>
<body>
  <div class="pdf-header">
    <h1>${escapeHtml(title)}</h1>
    <div class="meta">Generated on ${escapeHtml(date)}${meta.targetIndustry ? ` · ${escapeHtml(meta.targetIndustry)}` : ''}${meta.budget ? ` · Budget: ${escapeHtml(meta.budget)}` : ''}</div>
  </div>
  <div class="content">
    ${markdownHtml}
  </div>
  <div class="pdf-footer">
    Generated by MarketingAgent · AI-Powered Campaign Strategy
  </div>
</body>
</html>`;
}

function escapeHtml(str) {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
