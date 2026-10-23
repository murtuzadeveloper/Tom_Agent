"""
Generators for synthetic contact cards, screenshots, and OCR text samples.
Ensures thorough offline testing with zero external API calls.
"""

from PIL import Image, ImageDraw, ImageFont

SYNTHETIC_OCR_SAMPLES = {
    "tech_director": (
        "Sarah Jenkins\n"
        "Director of Engineering\n"
        "Apex Cloud Technologies\n"
        "Email: s.jenkins@apexcloud.tech\n"
        "Office: +1 (415) 555-0199\n"
        "Website: https://www.apexcloud.tech\n"
        "LinkedIn: linkedin.com/in/sarahjenkins-apex\n"
        "San Francisco, California"
    ),
    "sales_lead": (
        "Marcus Vance\n"
        "Head of Enterprise Growth\n"
        "Vance Logistics International\n"
        "Direct Phone: +44 20 7946 0912\n"
        "Inquiries: marcus.vance@vancelogistics.co.uk\n"
        "London, EC2A 4NE"
    ),
    "formula_injection_attack": (
        "Bad Actor\n"
        "Penetration Tester\n"
        "Hacker Org\n"
        "Email: =cmd|'/C calc'!A0@evil.com\n"
        "Phone: +1 800 555 1234"
    ),
    "empty_screen": (
        "Windows Desktop\n"
        "Recycle Bin\n"
        "No notifications\n"
        "10:45 AM"
    )
}

def generate_synthetic_contact_image(sample_key: str = "tech_director") -> Image.Image:
    """Generates a synthetic business card image containing simulated contact details."""
    text = SYNTHETIC_OCR_SAMPLES.get(sample_key, SYNTHETIC_OCR_SAMPLES["tech_director"])
    img = Image.new("RGB", (600, 320), color=(245, 247, 250))
    draw = ImageDraw.Draw(img)

    # Draw border
    draw.rectangle([(10, 10), (590, 310)], outline=(200, 205, 215), width=2)
    # Draw header band
    draw.rectangle([(10, 10), (590, 45)], fill=(79, 70, 229))

    # Text placement
    y_offset = 60
    for line in text.splitlines():
        draw.text((30, y_offset), line, fill=(30, 41, 59))
        y_offset += 28

    return img
