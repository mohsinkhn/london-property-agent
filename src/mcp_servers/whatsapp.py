"""MCP server for sending property results via WhatsApp (Twilio)."""

import json
import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("whatsapp")


def _get_twilio_client():
    """Lazy import + init Twilio client."""
    from twilio.rest import Client

    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not sid or not token:
        raise ValueError(
            "TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables required"
        )
    return Client(sid, token)


WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")  # Twilio sandbox default


@mcp.tool()
async def send_whatsapp(to_number: str, message: str) -> str:
    """Send a WhatsApp message with property search results.

    Args:
        to_number: Recipient phone number with country code (e.g. "+447700900000").
        message: Message text to send. Supports basic formatting.

    Returns:
        JSON with message SID on success, or error details.
    """
    if not to_number.startswith("whatsapp:"):
        to_number = f"whatsapp:{to_number}"

    try:
        client = _get_twilio_client()
        msg = client.messages.create(
            body=message,
            from_=WHATSAPP_FROM,
            to=to_number,
        )
        return json.dumps({"status": "sent", "sid": msg.sid})
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"WhatsApp send failed: {str(e)}"})


@mcp.tool()
async def send_property_summary(to_number: str, properties: str) -> str:
    """Format and send a ranked property summary via WhatsApp.

    Args:
        to_number: Recipient phone number with country code.
        properties: JSON string of ranked properties (from score-and-rank skill output).

    Returns:
        JSON with send status.
    """
    try:
        props = json.loads(properties)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid properties JSON"})

    if isinstance(props, dict):
        props = props.get("properties", props.get("results", [props]))

    lines = ["*Top London Properties*\n"]
    for i, p in enumerate(props[:10], 1):
        price = p.get("price", "?")
        price_str = f"£{price:,}" if isinstance(price, (int, float)) else price
        addr = p.get("address", "?")
        beds = p.get("bedrooms", "?")
        score = p.get("total_score", p.get("scores", {}).get("total", "?"))
        url = p.get("listingUrl", p.get("url", ""))

        lines.append(f"*{i}.* {price_str} — {beds} bed")
        lines.append(f"   {addr}")
        if score != "?":
            lines.append(f"   Score: {score}/100")
        if url:
            lines.append(f"   {url}")
        lines.append("")

    message = "\n".join(lines)

    if not to_number.startswith("whatsapp:"):
        to_number = f"whatsapp:{to_number}"

    try:
        client = _get_twilio_client()
        msg = client.messages.create(body=message, from_=WHATSAPP_FROM, to=to_number)
        return json.dumps({"status": "sent", "sid": msg.sid, "properties_sent": min(len(props), 10)})
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"WhatsApp send failed: {str(e)}"})


if __name__ == "__main__":
    mcp.run()
