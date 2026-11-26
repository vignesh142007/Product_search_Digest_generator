import html
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from scraper import validate_query, discover_websites, scrape_websites_concurrently
from parser import parse_scraped_pages, match_products_across_sites
from digest_generator import filter_and_sort_products, build_comparison_matrix, generate_summary_digest


def render_page(query="", sort_by="price_asc", min_rating="0", only_stock=False, show_digest=False):
    status_html = digest_html = cards_html = matrix_html = ""

    if query:
        ok, msg, params = validate_query(query)
        if not ok:
            status_html = f'<div class="alert error">{html.escape(msg)}</div>'
        else:
            sites = discover_websites(params, "sources.json")
            successes, failures = scrape_websites_concurrently(sites, max_workers=6, timeout=2.0)
            records = parse_scraped_pages(successes, params["tokens"])
            filtered = filter_and_sort_products(
                records,
                max_price=params["max_price"],
                min_rating=float(min_rating or 0),
                only_in_stock=only_stock,
                sort_by=sort_by,
            )
            grouped = match_products_across_sites(filtered)
            matrix = build_comparison_matrix(grouped)

            status_html = (
                f'<div class="alert info">Found {len(sites)} matching website(s); '
                f'scraped {len(successes)} successfully ({len(failures)} unreachable). '
                f'Showing {len(filtered)} product listing(s) across {len(matrix)} unique product(s).</div>'
            )

            if show_digest:
                digest_text = generate_summary_digest(filtered, matrix, failures)
                digest_html = f'<section class="card digest"><h2>Summary Digest (FR9)</h2><p>{html.escape(digest_text)}</p></section>'

            card_items = []
            for r in filtered:
                card_items.append(f"""
                <div class="product-card">
                  <h3>{html.escape(r.title)}</h3>
                  <p class="desc">{html.escape(r.description)}</p>
                  <p><strong>Price:</strong> Rs. {r.price:.0f} | <strong>Rating:</strong> {r.rating} &#9733; ({r.reviews} reviews) | <strong>Availability:</strong> {html.escape(r.availability)}</p>
                  <a href="{html.escape(r.source_url)}" target="_blank" rel="noopener noreferrer">View original page at {html.escape(r.source_name)}</a>
                </div>""")
            cards_html = f'<section><h2>Scraped Products (FR3, FR7, FR10)</h2><div class="grid">{"".join(card_items) or "<p>No matching products.</p>"}</div></section>'

            rows = []
            for item in matrix:
                vendor_cells = "<br>".join(
                    f'{html.escape(o["source_name"])}: Rs. {o["price"]:.0f} ({o["rating"]}&#9733;, {html.escape(o["availability"])})'
                    for o in item["offers"]
                )
                rows.append(f"""
                <tr>
                  <td>{html.escape(item["product_title"])}</td>
                  <td>Rs. {item["lowest_price"]:.0f} ({html.escape(item["lowest_price_vendor"])})</td>
                  <td>{item["highest_rating"]} &#9733; ({html.escape(item["highest_rating_vendor"])})</td>
                  <td>{vendor_cells}</td>
                </tr>""")
            if rows:
                matrix_html = f"""
                <section>
                  <h2>Cross-Site Comparison Matrix (FR4, FR5, FR8)</h2>
                  <table>
                    <thead><tr><th>Product</th><th>Best Price</th><th>Top Rating</th><th>Vendor Breakdown</th></tr></thead>
                    <tbody>{"".join(rows)}</tbody>
                  </table>
                </section>"""

    stock_checked = "checked" if only_stock else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"><title>Product Search, Comparison &amp; Digest Generator</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ font-family: 'Trebuchet MS', Arial, sans-serif; background: #eef2ff; color: #1e1b4b; margin: 0; padding-bottom: 32px; }}
    .banner {{ background: linear-gradient(135deg, #312e81, #4f46e5); color: #ffffff; padding: 24px 20px; text-align: center; }}
    .banner h1 {{ margin: 0; font-size: 24px; }}
    .banner p {{ margin: 6px 0 0; font-size: 13px; color: #c7d2fe; }}
    .wrap {{ max-width: 1100px; margin: -16px auto 0; padding: 0 16px; }}
    .panel {{ background: #ffffff; border-radius: 14px; padding: 18px; box-shadow: 0 4px 16px rgba(49, 46, 129, 0.08); margin-bottom: 18px; }}
    form {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
    input[type="text"] {{ flex: 1; min-width: 240px; padding: 9px 12px; border: 1px solid #c7d2fe; border-radius: 8px; }}
    select {{ padding: 9px 12px; border: 1px solid #c7d2fe; border-radius: 8px; background: #f8fafc; }}
    label {{ font-size: 13px; color: #312e81; }}
    button {{ padding: 9px 16px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; background: #4f46e5; color: #fff; }}
    button[value="1"] {{ background: #6d28d9; }}
    .alert {{ padding: 11px 15px; border-radius: 10px; margin-bottom: 16px; font-size: 14px; }}
    .info {{ background: #e0e7ff; border-left: 4px solid #4f46e5; color: #1e1b4b; }}
    .error {{ background: #fee2e2; border-left: 4px solid #dc2626; color: #7f1d1d; }}
    .digest {{ background: #f5f3ff; border: 1px solid #ddd6fe; border-left: 5px solid #6d28d9; padding: 14px 18px; border-radius: 12px; margin-bottom: 18px; }}
    .digest h2 {{ margin: 0 0 6px; font-size: 16px; color: #5b21b6; }}
    h2 {{ font-size: 17px; color: #312e81; margin: 0 0 12px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }}
    .product-card {{ background: #ffffff; border: 1px solid #e0e7ff; border-top: 4px solid #4f46e5; border-radius: 10px; padding: 14px; }}
    .product-card h3 {{ margin: 0 0 6px; font-size: 15px; color: #1e1b4b; }}
    .product-card a {{ display: inline-block; margin-top: 6px; color: #4338ca; font-weight: bold; font-size: 13px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border: 1px solid #e0e7ff; padding: 9px 10px; text-align: left; vertical-align: top; font-size: 13px; }}
    th {{ background: #eef2ff; color: #312e81; }}
  </style>
</head>
<body>
  <div class="banner">
    <h1>Product Search, Comparison &amp; Digest Generator</h1>
    <p>Cross-Vendor Aggregation, Filtering, Side-by-Side Comparison &amp; Summary Synthesis</p>
  </div>
  <div class="wrap">
    <div class="panel">
      <form method="GET" action="/">
        <input type="text" name="q" value="{html.escape(query)}" placeholder="e.g. Smartphone under 30000, Running Shoes, Water Bottle" required />
        <select name="sort">
          <option value="price_asc" {"selected" if sort_by=="price_asc" else ""}>Lowest Price</option>
          <option value="price_desc" {"selected" if sort_by=="price_desc" else ""}>Highest Price</option>
          <option value="rating_desc" {"selected" if sort_by=="rating_desc" else ""}>Highest Rating</option>
          <option value="recommended" {"selected" if sort_by=="recommended" else ""}>Recommended</option>
        </select>
        <select name="min_rating">
          <option value="0" {"selected" if min_rating=="0" else ""}>Any Rating</option>
          <option value="4.0" {"selected" if min_rating=="4.0" else ""}>Rating &ge; 4 &#9733;</option>
          <option value="4.5" {"selected" if min_rating=="4.5" else ""}>Rating &ge; 4.5 &#9733;</option>
        </select>
        <label><input type="checkbox" name="in_stock" value="1" {stock_checked}/> In Stock Only</label>
        <button type="submit" name="digest" value="0">Search</button>
        <button type="submit" name="digest" value="1">Generate Summary Report</button>
      </form>
    </div>
    {status_html}
    {digest_html}
    {f'<div class="panel">{matrix_html}</div>' if matrix_html else ""}
    {f'<div class="panel">{cards_html}</div>' if cards_html else ""}
  </div>
</body>
</html>"""


class DigestRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        page = render_page(
            query=qs.get("q", [""])[0],
            sort_by=qs.get("sort", ["price_asc"])[0],
            min_rating=qs.get("min_rating", ["0"])[0],
            only_stock=qs.get("in_stock", ["0"])[0] == "1",
            show_digest=qs.get("digest", ["0"])[0] == "1",
        )
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8000), DigestRequestHandler)
    print("Server running at http://127.0.0.1:8000")
    server.serve_forever()
